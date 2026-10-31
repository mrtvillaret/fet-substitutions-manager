"""La lògica dels grups i alliberats, sense HTTP: la taula de cada dia i el que
s'hi desa, els alliberaments per període (reforços), les activitats
alliberables i els grups amagats. Després de cada canvi del que està
alliberat, es reconcilien les substitucions i les cobertures dels dies
afectats."""

import json
from datetime import datetime
from typing import Dict, List

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
from grups.domain import ActivitatNoConfigurada, PeriodeNoValid
from grups.repositories import AlliberamentsPeriodeRepository, GrupsAlliberatsRepository, GrupsAmagatsRepository
from helpers import MissingXmlError, invalidar_horari
from repositories import ConfiguracioRepository
from routes.parametres import data_iso
from serveis.dia import Dia
from substitucions.cobertures import refresca_cobertures
from substitucions.domain import treu_substituts_no_valids
from substitucions.generacio import genera_substitucions_dia
from vigilancies.repositories import VigilanciaRepository

# Activitats sense grup que es poden alliberar (p.ex. Reforç, un equip docent):
# es configuren a Prioritats i surten com a files a la taula de grups
CLAU_ACTIVITATS_ALLIBERABLES = "activitats_alliberables"
CLAU_ACTIVITATS_PER_DEFECTE = "activitats_alliberades_per_defecte"


def activitats_alliberables(db: Session) -> List[str]:
    try:
        return [a for a in json.loads(ConfiguracioRepository.get(db, CLAU_ACTIVITATS_ALLIBERABLES) or "[]") if a]
    except (ValueError, TypeError):
        return []


# ===== Reconciliació després d'un canvi =====


def _reconcilia_dia(db: Session, data: str, hores_afectades: set) -> list:
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
    vig_dict = VigilanciaRepository.get_by_date(db, data)
    hores_amb_vig = {
        (v.get("hora") or "").strip() for vigs in vig_dict.values() for v in vigs if (v.get("hora") or "").strip()
    }
    for hora in hores_amb_vig | {h.strip() for h in hores_afectades if h and h.strip()}:
        refresca_cobertures(data, hora, db)
    return trets


def _reconcilia_dies_afectats(db: Session, des_de: str, dia_setmana: int, hores: set) -> list:
    """Un canvi per període afecta tots els dies següents del mateix dia de la
    setmana: es reconcilien els que ja tenen substitucions o vigilàncies."""
    trets = []
    for d in AlliberamentsPeriodeRepository.dates_afectades(db, des_de, dia_setmana):
        trets += _reconcilia_dia(db, d, hores)
    return trets


# ===== Alliberaments per període =====


def afegeix_canvi_periode(
    db: Session, tipus: str, clau: str, hores: List[str], data: str, alliberat: bool, dia_setmana: str
) -> dict:
    """A partir de `data`, cada setmana el mateix dia (o `dia_setmana`), a les
    `hores` indicades, el professor queda alliberat (o deixa de ser-ho)."""
    data_obj = data_iso(data)
    if tipus not in AlliberamentsPeriodeRepository.TIPUS:
        raise PeriodeNoValid("Tipus desconegut", codi="tipus_desconegut")
    clau = clau.strip()
    hores = [h.strip() for h in hores if h and h.strip()]
    if not clau or not hores:
        raise PeriodeNoValid("Cal indicar qui i a quines hores", codi="periode_incomplet")

    horari = Dia.de_text(data).horari
    if dia_setmana:
        dia = dia_setmana.strip()
        dies = {horari.get_dia_name(i): i for i in range(7) if horari.get_dia_name(i) in horari.dies}
        if dia not in dies:
            raise PeriodeNoValid("Dia de la setmana desconegut", codi="dia_setmana_desconegut")
        num_dia = dies[dia]
    else:
        num_dia = data_obj.weekday()
        dia = horari.get_dia_name(num_dia)
    AlliberamentsPeriodeRepository.afegeix(db, tipus, clau, dia, hores, data, alliberat)
    trets = _reconcilia_dies_afectats(db, data, num_dia, set(hores))
    db.commit()
    return {"dia_setmana": dia, "substituts_trets": trets}


def franges_reforc(db: Session, horari, activitat: str, data: str) -> dict:
    """Per a una activitat «alliberada fins que tingui alumnes» (p.ex. Reforç):
    les franges de la setmana de cada professor que la fa, i si en aquella data
    ja tenen alumnes."""
    if activitat not in GrupsAlliberatsRepository.activitats_per_defecte(db):
        raise ActivitatNoConfigurada("Activitat no configurada", codi="activitat_no_configurada")
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


# ===== La taula d'un dia =====


def dades_del_dia(db: Session, dia_peticio: Dia, data: str) -> dict:
    """El que s'ha marcat `data`, el que ve d'alliberaments per període i el
    que cal per mostrar la taula (GrupsView.vue)."""
    _, horari, _, _ = dia_peticio.gestors()

    # horari.grups ja és el conjunt de grups de treball (selecció manual;
    # si no n'hi ha, tots els detectats). El filtre viu al parser.
    tots_grups = sorted(horari.grups)

    # El que s'ha marcat aquell dia (els períodes es retornen a part)
    alliberats_per_hora = GrupsAlliberatsRepository.get_dia_by_date(db, data)

    # Hores del dia: les que algun grup visible té classe o algú fa una
    # activitat alliberable (la taula només en té files), i les que ja
    # tenen alguna cosa marcada aquell dia (perquè es pugui desmarcar)
    dia = horari.get_dia_name(datetime.strptime(data, "%Y-%m-%d").weekday())
    grups_de_la_taula = set(horari.grups)
    activitats_de_la_taula = set(activitats_alliberables(db))

    def te_files(hora):
        for professor in horari.professors:
            act = horari.get_activitat(dia, hora, professor) or {}
            grup = act.get("grup") or ""
            if grup in grups_de_la_taula if grup else (act.get("assignatura") or "") in activitats_de_la_taula:
                return True
        return False

    hores = [h for h in horari.hores if alliberats_per_hora.get(h) or te_files(h)]

    # Grups que a una hora tenen classe amb més d'un professor (p.ex. una
    # optativa): només en aquests té sentit alliberar un professor sol. Si
    # n'hi ha un de sol, alliberar-lo és deixar el grup sense classe.
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
    per_defecte = GrupsAlliberatsRepository.activitats_per_defecte(db)
    reforcs_del_dia = {}
    if per_defecte:
        darrers = AlliberamentsPeriodeRepository.darrers(db, data, dia)
        for hora in hores:
            for professor in sorted(horari.professors):
                activitat = horari.get_activitat(dia, hora, professor) or {}
                nom = activitat.get("assignatura") or ""
                if nom not in per_defecte or activitat.get("grup"):
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
    configurades = set(activitats_alliberables(db)) - set(per_defecte)
    activitats_per_hora = {}
    if configurades:
        for hora in hores:
            for professor in sorted(horari.professors):
                activitat = horari.get_activitat(dia, hora, professor) or {}
                nom = activitat.get("assignatura") or ""
                if nom in configurades and not activitat.get("grup"):
                    activitats_per_hora.setdefault(nom, {}).setdefault(hora, []).append(professor)

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


def desa_dia(
    db: Session,
    data: str,
    grups: Dict[str, List[str]],
    professors: Dict[str, List[str]],
    activitats: Dict[str, List[str]],
    ocupats: Dict[str, List[str]],
) -> dict:
    """Desa el que es marca `data` (substitueix el que hi hagués) i
    reconcilia les substitucions i les cobertures de les hores que canvien.
    Els professors, les activitats i els ocupats es desen a la mateixa llista
    per hora que els grups, amb un prefix (core/alliberats.py)."""
    grups_per_hora = {}
    for hora, valors_grups in grups.items():
        valors = [g.strip() for g in nomes_grups(valors_grups) if g and g.strip()]
        if valors:
            grups_per_hora[hora] = valors
    for hora, noms in professors.items():
        claus = [clau_professor(p.strip()) for p in noms if p and p.strip()]
        if claus:
            grups_per_hora.setdefault(hora, []).extend(dict.fromkeys(claus))
    for hora, noms in activitats.items():
        claus = [clau_activitat(a.strip()) for a in noms if a and a.strip()]
        if claus:
            grups_per_hora.setdefault(hora, []).extend(dict.fromkeys(claus))
    for hora, noms in ocupats.items():
        claus = [clau_ocupat(p.strip()) for p in noms if p and p.strip()]
        if claus:
            grups_per_hora.setdefault(hora, []).extend(dict.fromkeys(claus))

    # Les hores que es desmarquen també s'han de reconciliar
    hores_anteriors = set(GrupsAlliberatsRepository.get_dia_by_date(db, data).keys())
    GrupsAlliberatsRepository.set_for_date(db, data, grups_per_hora)
    trets = _reconcilia_dia(db, data, set(grups_per_hora) | hores_anteriors)
    db.commit()

    return {
        "substituts_trets": trets,
        "total_hores": len(grups_per_hora),
        "total_grups": sum(len(nomes_grups(v)) for v in grups_per_hora.values()),
        "total_professors": sum(len(professors_de(v)) for v in grups_per_hora.values()),
    }


# ===== Configuració (admins) =====


def grups_amagats(db: Session) -> List[str]:
    return GrupsAmagatsRepository.get_all(db)


def desa_grups_amagats(db: Session, grups: List[str]) -> int:
    """Reemplaça la llista de grups amagats sencera; en retorna quants n'hi ha."""
    total = GrupsAmagatsRepository.set_all(db, grups)
    db.commit()
    # L'horari filtra els grups segons aquesta llista durant la càrrega;
    # cal invalidar-lo perquè es recarregui.
    invalidar_horari()
    return total


def configuracio_activitats_alliberables(db: Session, dia_calendari: Dia) -> dict:
    """Activitats sense grup que es poden alliberar (surten com a files a la
    taula de grups alliberats) i les que hi ha a l'horari vigent per triar-les."""
    disponibles = set()
    try:
        # És configuració, no un dia: els professors de l'XML fins a l'«últim
        # professor», també els que tenen una absència coberta aquell dia
        horari = dia_calendari.horari_amb_tothom
        for dia in horari.dies:
            for hora in horari.hores:
                for professor in horari.professors:
                    act = horari.get_activitat(dia, hora, professor) or {}
                    if act.get("assignatura") and not act.get("grup"):
                        disponibles.add(act["assignatura"])
    except MissingXmlError:
        pass

    return {
        "activitats": activitats_alliberables(db),
        "per_defecte": GrupsAlliberatsRepository.activitats_per_defecte(db),
        "disponibles": sorted(disponibles),
    }


def desa_activitats_alliberables(db: Session, activitats: List[str], per_defecte: List[str]) -> dict:
    """Les activitats alliberables i, d'aquestes, les alliberades fins que
    tenen alumnes (p.ex. Reforç)."""
    activitats = sorted({a.strip() for a in activitats if a and a.strip()})
    per_defecte = sorted({a.strip() for a in per_defecte if a and a.strip() in activitats})
    ConfiguracioRepository.set(db, CLAU_ACTIVITATS_ALLIBERABLES, json.dumps(activitats, ensure_ascii=False), "json")
    ConfiguracioRepository.set(db, CLAU_ACTIVITATS_PER_DEFECTE, json.dumps(per_defecte, ensure_ascii=False), "json")
    return {"activitats": activitats, "per_defecte": per_defecte}
