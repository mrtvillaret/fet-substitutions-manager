"""
Routes per grups sense classe (grups alliberats), professors i activitats alliberats:
- GET /{data}: el que s'ha marcat aquell dia, el que ve d'alliberaments per període,
  i les dades per mostrar la taula
- PUT /{data}: desar el que es marca aquell dia
- /periode: canvis d'estat que duren fins al canvi següent (cada setmana)
"""

import json
from datetime import datetime
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.alliberats import (
    activitats_de,
    clau_activitat,
    clau_ocupat,
    clau_professor,
    nomes_grups,
    ocupats_de,
    professors_de,
)
from dependencies import dia_de_la_peticio, get_db
from noms import NomNet
from repositories import (
    AlliberamentsPeriodeRepository,
    ConfiguracioRepository,
    GrupsAlliberatsRepository,
)
from routes.parametres import DataISO, data_iso
from serveis.dia import Dia
from substitucions.domain import treu_substituts_no_valids
from substitucions.generacio import genera_substitucions_dia

router = APIRouter(prefix="/api/grups", tags=["Grups Sense Classe"])


# Activitats sense grup que es poden alliberar (p.ex. Reforç, un equip docent):
# es configuren a Prioritats i surten com a files a la taula de grups
CLAU_ACTIVITATS_ALLIBERABLES = "activitats_alliberables"


def activitats_alliberables(db: Session) -> List[str]:
    try:
        return [a for a in json.loads(ConfiguracioRepository.get(db, CLAU_ACTIVITATS_ALLIBERABLES) or "[]") if a]
    except (ValueError, TypeError):
        return []


class AlliberatsDia(BaseModel):
    grups: Dict[str, List[str]] = {}  # {hora: [grups sense classe]}
    professors: Dict[str, List[NomNet]] = {}  # {hora: [professors alliberats]}
    activitats: Dict[str, List[NomNet]] = {}  # {hora: [activitats alliberades]}
    ocupats: Dict[str, List[NomNet]] = {}  # {hora: [reforços sense alumnes que aquell dia sí en tenen]}


class CanviPeriode(BaseModel):
    tipus: str  # grup | professor | activitat
    clau: str  # nom del grup, professor o activitat
    hores: List[str]
    data: str  # a partir d'aquest dia
    alliberat: bool = True
    dia_setmana: str = ""  # el dia de la setmana (per defecte, el de `data`)


def _reconcilia_dia(data: str, hores_afectades: set, db: Session) -> list:
    """Després de canviar què està alliberat un dia: treu els substituts que ja
    no poden fer la substitució (p. ex. han perdut la condició d'alliberat),
    actualitza les files del dia sense assignar cap substitut nou i reconcilia
    les cobertures de vigilància de les hores afectades. Retorna els substituts
    trets (substitucions.substituts_no_valids), amb la data."""

    trets = [{**fila, "data": data} for fila in treu_substituts_no_valids(db, data)]
    # Les files que han quedat sense substitut queden pendents: no s'omplen soles.
    genera_substitucions_dia(db, data, Dia.de_text(data).gestors(), regenerar_tot=False, omplir=False)

    # Reconciliar les cobertures de vigilància (Tipus B) de les hores afectades.
    # En alliberar un grup, un professor que abans "calia substituir" pot quedar alliberat
    # (el seu grup fa examen) i la seva cobertura VIGILANCIA esdevé innecessària. Si no es
    # reconcilia, queda un registre ranci amb substitut buit que provoca falsos avisos
    # ("vigilàncies cobertes automàticament sense substitut assignat").
    # Reutilitzem la mateixa reconciliació que ja s'executa en crear/editar vigilàncies,
    # perquè el resultat NO depengui de l'ordre d'entrada de dades (abans calia editar
    # l'hora manualment perquè es netegés).
    from substitucions.cobertures import refresca_cobertures
    from vigilancies.repositories import VigilanciaRepository

    vig_dict = VigilanciaRepository.get_by_date(db, data)
    hores_amb_vig = {
        (v.get("hora") or "").strip() for vigs in vig_dict.values() for v in vigs if (v.get("hora") or "").strip()
    }
    for hora in hores_amb_vig | {h.strip() for h in hores_afectades if h and h.strip()}:
        refresca_cobertures(data, hora, db)
    return trets


# ===== Alliberaments per període (definides abans de /{data}) =====


@router.get("/periode/canvis")
async def llista_canvis_periode(tipus: str = None, clau: str = None, db: Session = Depends(get_db)):
    """Canvis d'estat (d'un grup, professor o activitat, si s'indica)."""
    return {"canvis": AlliberamentsPeriodeRepository.canvis(db, tipus, clau)}


@router.post("/periode")
async def afegeix_canvi_periode(canvi: CanviPeriode, db: Session = Depends(get_db)):
    """A partir de `data`, cada setmana el mateix dia, a les `hores` indicades,
    el grup / professor / activitat queda alliberat (o deixa de ser-ho)."""
    data_obj = data_iso(canvi.data)
    if canvi.tipus not in AlliberamentsPeriodeRepository.TIPUS:
        raise HTTPException(status_code=400, detail="Tipus desconegut")
    clau = canvi.clau.strip()
    hores = [h.strip() for h in canvi.hores if h and h.strip()]
    if not clau or not hores:
        raise HTTPException(status_code=400, detail="Cal indicar qui i a quines hores")

    horari = Dia.de_text(canvi.data).horari
    if canvi.dia_setmana:
        dia = canvi.dia_setmana.strip()
        dies = {horari.get_dia_name(i): i for i in range(7) if horari.get_dia_name(i) in horari.dies}
        if dia not in dies:
            raise HTTPException(status_code=400, detail="Dia de la setmana desconegut")
        num_dia = dies[dia]
    else:
        num_dia = data_obj.weekday()
        dia = horari.get_dia_name(num_dia)
    AlliberamentsPeriodeRepository.afegeix(db, canvi.tipus, clau, dia, hores, canvi.data, canvi.alliberat)
    trets = _reconcilia_dies_afectats(canvi.data, num_dia, set(hores), db)
    db.commit()
    return {"success": True, "dia_setmana": dia, "substituts_trets": trets}


@router.get("/reforcos/{activitat}")
async def franges_activitat_per_defecte(
    activitat: NomNet, data: DataISO, db: Session = Depends(get_db), dia_peticio: Dia = Depends(dia_de_la_peticio)
):
    """Per a una activitat «alliberada fins que tingui alumnes» (p.ex. Reforç):
    les franges de la setmana de cada professor que la fa, i si en aquella data
    ja tenen alumnes."""
    data_iso(data)
    if activitat not in GrupsAlliberatsRepository.activitats_per_defecte(db):
        raise HTTPException(status_code=404, detail="Activitat no configurada")
    horari = dia_peticio.horari
    darrers = AlliberamentsPeriodeRepository.darrers(db, data)
    # Historial de cada franja (tots els canvis, també posteriors a `data`)
    historial = {}
    for c in AlliberamentsPeriodeRepository.canvis(db, tipus="professor"):
        historial.setdefault((c["clau"], c["dia_setmana"], c["hora"]), []).append(
            {"des_de": c["des_de"], "amb_alumnes": not c["alliberat"]}
        )
    professors = {}
    for dia in horari.dies:
        for hora in horari.hores:
            for professor in sorted(horari.professors):
                act = horari.get_activitat(dia, hora, professor) or {}
                if act.get("grup") or (act.get("assignatura") or "") != activitat:
                    continue
                canvi = darrers.get(("professor", professor, dia, hora))
                amb_alumnes = canvi is not None and not canvi.alliberat
                professors.setdefault(professor, []).append(
                    {
                        "dia": dia,
                        "hora": hora,
                        "amb_alumnes": amb_alumnes,
                        "des_de": canvi.des_de.isoformat() if canvi is not None else None,
                        "historial": historial.get((professor, dia, hora), []),
                    }
                )
    return {"dies": horari.dies, "hores": horari.hores, "professors": professors}


@router.delete("/periode/{canvi_id}")
async def esborra_canvi_periode(canvi_id: int, db: Session = Depends(get_db)):
    info = AlliberamentsPeriodeRepository.esborra(db, canvi_id)
    if not info:
        raise HTTPException(status_code=404, detail="Canvi no trobat")
    data_obj = datetime.strptime(info["des_de"], "%Y-%m-%d")
    trets = _reconcilia_dies_afectats(info["des_de"], data_obj.weekday(), {info["hora"]}, db)
    db.commit()
    return {"success": True, "substituts_trets": trets}


def _reconcilia_dies_afectats(des_de: str, dia_setmana: int, hores: set, db: Session) -> list:
    """Un canvi per període afecta tots els dies següents del mateix dia de la
    setmana: es reconcilien els que ja tenen substitucions o vigilàncies."""
    from models import Substitucio, Vigilancia
    from repositories import parse_date

    dates = set()
    for model in (Substitucio, Vigilancia):
        for (d,) in db.query(model.data).filter(model.data >= parse_date(des_de)).distinct():
            if d.weekday() == dia_setmana:
                dates.add(d.isoformat())
    trets = []
    for d in sorted(dates):
        trets += _reconcilia_dia(d, hores, db)
    return trets


@router.get("/{data}")
async def obtenir_grups_sense_classe(
    data: DataISO, db: Session = Depends(get_db), dia_peticio: Dia = Depends(dia_de_la_peticio)
):
    """
    Retorna grups sense classe per una data (SQLite)
    Format compatible amb GrupsView.vue
    """
    data_iso(data)

    # Obtenir gestors per carregar horari
    substitucions_mgr, horari, alliberats, absencies = dia_peticio.gestors()

    # horari.grups ja és el conjunt de grups de treball (selecció manual;
    # si no n'hi ha, tots els detectats). El filtre viu al parser.
    tots_grups = sorted(horari.grups)

    # El que s'ha marcat aquell dia (els períodes es retornen a part)
    alliberats_per_hora = GrupsAlliberatsRepository.get_dia_by_date(db, data)

    # Hores del dia: les que algun grup visible té classe o algú fa una
    # activitat alliberable (la taula només en té files), i les que ja
    # tenen alguna cosa marcada aquell dia (perquè es pugui desmarcar)
    dia_hores = horari.get_dia_name(datetime.strptime(data, "%Y-%m-%d").weekday())
    grups_de_la_taula = set(horari.grups)
    activitats_de_la_taula = set(activitats_alliberables(db))

    def te_files(hora):
        for professor in horari.professors:
            act = horari.get_activitat(dia_hores, hora, professor) or {}
            grup = act.get("grup") or ""
            if grup in grups_de_la_taula if grup else (act.get("assignatura") or "") in activitats_de_la_taula:
                return True
        return False

    hores = [h for h in horari.hores if alliberats_per_hora.get(h) or te_files(h)]

    # Grups que a una hora tenen classe amb més d'un professor (p.ex. una
    # optativa): només en aquests té sentit alliberar un professor sol. Si
    # n'hi ha un de sol, alliberar-lo és deixar el grup sense classe.
    dia = horari.get_dia_name(datetime.strptime(data, "%Y-%m-%d").weekday())
    professors_per_grup_hora = {}
    grups_visibles = set(tots_grups)
    for hora in hores:
        per_grup = {}
        for professor in sorted(horari.professors):
            activitat = horari.get_activitat(dia, hora, professor) or {}
            grup = activitat.get("grup", "")
            if grup in grups_visibles and activitat.get("assignatura"):
                per_grup.setdefault(grup, []).append(professor)
        compartits = {grup: profs for grup, profs in per_grup.items() if len(profs) > 1}
        if compartits:
            professors_per_grup_hora[hora] = compartits

    # Reforços (alliberats fins que tenen alumnes) d'aquell dia, amb l'estat de
    # cada professor: {activitat: {hora: [{professor, amb_alumnes}]}}. Els que
    # tenen alumnes es poden alliberar només aquell dia (👤).
    per_defecte_noms = set(GrupsAlliberatsRepository.activitats_per_defecte(db))
    reforcs_del_dia = {}
    if per_defecte_noms:
        darrers = AlliberamentsPeriodeRepository.darrers(db, data, dia)
        for hora in hores:
            for professor in sorted(horari.professors):
                activitat = horari.get_activitat(dia, hora, professor) or {}
                nom = activitat.get("assignatura") or ""
                if nom not in per_defecte_noms or activitat.get("grup"):
                    continue
                canvi = darrers.get(("professor", professor, dia, hora))
                reforcs_del_dia.setdefault(nom, {}).setdefault(hora, []).append(
                    {
                        "professor": professor,
                        "amb_alumnes": canvi is not None and not canvi.alliberat,
                    }
                )

    # Activitats alliberables (Prioritats) que algú fa aquell dia: {activitat: {hora: [professors]}}
    # Les «alliberades fins que tenen alumnes» no hi surten: es gestionen a part
    per_defecte = GrupsAlliberatsRepository.activitats_per_defecte(db)
    configurades = set(activitats_alliberables(db)) - set(per_defecte)
    activitats_per_hora = {}
    if configurades:
        for hora in hores:
            for professor in sorted(horari.professors):
                activitat = horari.get_activitat(dia, hora, professor) or {}
                nom = activitat.get("assignatura") or ""
                if nom in configurades and not activitat.get("grup"):
                    activitats_per_hora.setdefault(nom, {}).setdefault(hora, []).append(professor)

    # Retornar en format esperat pel frontend
    return {
        "hores": hores,
        "grups_disponibles": tots_grups,
        "grups_seleccionats_per_hora": {
            hora: nomes_grups(valors) for hora, valors in alliberats_per_hora.items() if nomes_grups(valors)
        },
        "professors_per_grup_hora": professors_per_grup_hora,
        "professors_alliberats_per_hora": {
            hora: professors_de(valors) for hora, valors in alliberats_per_hora.items() if professors_de(valors)
        },
        "activitats_per_hora": {act: activitats_per_hora[act] for act in sorted(activitats_per_hora)},
        "activitats_seleccionades_per_hora": {
            hora: activitats_de(valors) for hora, valors in alliberats_per_hora.items() if activitats_de(valors)
        },
        # Alliberats per període aquell dia: {hora: [{tipus, clau, des_de}]}
        "periode": AlliberamentsPeriodeRepository.estats(db, data, dia),
        "dia_setmana": dia,
        "activitats_per_defecte": per_defecte,
        "reforcs_per_hora": reforcs_del_dia,
        "ocupats_per_hora": {
            hora: ocupats_de(valors) for hora, valors in alliberats_per_hora.items() if ocupats_de(valors)
        },
    }


@router.put("/{data}")
async def desar_grups_sense_classe(data: DataISO, payload: AlliberatsDia, db: Session = Depends(get_db)):
    """
    Desa grups sense classe per una data (SQLite)

    IMPORTANT: Després de desar, regenera substitucions pendents (sense substitut)
    perquè canviar els grups sense classe afecta quines substitucions són necessàries.

    Args:
        payload.grups: Dict[hora, List[grups]]
        payload.professors: Dict[hora, List[professors]] (alliberats sense el seu grup)
    """
    data_iso(data)

    # Els professors alliberats es desen a la mateixa llista per hora que els
    # grups, amb un prefix (veure core/alliberats.py).
    grups_per_hora = {}
    for hora, grups in payload.grups.items():
        valors = [g.strip() for g in nomes_grups(grups) if g and g.strip()]
        if valors:
            grups_per_hora[hora] = valors
    for hora, professors in payload.professors.items():
        claus = [clau_professor(p.strip()) for p in professors if p and p.strip()]
        if claus:
            grups_per_hora.setdefault(hora, []).extend(dict.fromkeys(claus))
    for hora, activitats in payload.activitats.items():
        claus = [clau_activitat(a.strip()) for a in activitats if a and a.strip()]
        if claus:
            grups_per_hora.setdefault(hora, []).extend(dict.fromkeys(claus))
    for hora, professors in payload.ocupats.items():
        claus = [clau_ocupat(p.strip()) for p in professors if p and p.strip()]
        if claus:
            grups_per_hora.setdefault(hora, []).extend(dict.fromkeys(claus))

    # Les hores que es desmarquen també s'han de reconciliar
    hores_anteriors = set(GrupsAlliberatsRepository.get_dia_by_date(db, data).keys())
    GrupsAlliberatsRepository.set_for_date(db, data, grups_per_hora)
    trets = _reconcilia_dia(data, set(grups_per_hora) | hores_anteriors, db)
    db.commit()

    return {
        "success": True,
        "substituts_trets": trets,
        "message": f"Grups sense classe actualitzats per {data}",
        "total_hores": len(grups_per_hora),
        "total_grups": sum(len(nomes_grups(v)) for v in grups_per_hora.values()),
        "total_professors": sum(len(professors_de(v)) for v in grups_per_hora.values()),
    }
