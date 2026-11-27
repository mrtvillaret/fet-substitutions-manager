"""
Absència coberta (abans «baixa»): un professor absent que té un substitut
extern a l'XML. Durant el període queda fora de tot: l'horari de cada data ja
no el té (sense_absents_coberts, el punt únic, per on passa Dia).

Què passa en desar-ne una, per a cada dia del període, d'avui endavant, que ja
tingui substitucions o vigilàncies:
- s'esborren les seves absències d'aquell dia;
- es treu com a vigilant (la vigilància queda pendent);
- es treu com a substitut (la fila queda pendent).
Els dies passats no es toquen: són historial (PDF ja repartits, informes).
"""

from collections.abc import Collection
from datetime import date, timedelta
from typing import Unpack

from sqlalchemy.orm import Session

import rellotge
from absencia_coberta.domain import absents_coberts, absents_coberts_en, sense_absents_coberts
from absencia_coberta.repositories import AbsenciaCobertaFitxa, AbsenciaCobertaRepository, CanvisAbsenciaCoberta
from database import get_data_db_session
from errors_domini import MissingXmlError, NoTrobat
from horari.domain import Dia
from substitucions.absencies import desa_absencies
from substitucions.cobertures import refresca_cobertures
from substitucions.domain import DiaEscolar
from substitucions.reconciliacio import treu_substituts_no_valids
from substitucions.repositories import SubstitucioRepository
from textos import nom_net
from vigilancies.repositories import VigilanciaRepository


def _dies_afectats(db: Session, data_inici: date, data_final: date, avui: date) -> list[date]:
    inici = max(data_inici, avui)
    if inici > data_final:
        return []
    dates = set()
    for repositori in (SubstitucioRepository, VigilanciaRepository):
        dates |= repositori.dates_entre(db, inici, data_final)
    return sorted(dates)


def _dia_amb_absencies_pendents(db: Session, institucio: str, data: date) -> Dia:
    """Dia amb l'horari que veu també la transacció actual."""
    dia = Dia(data, institucio)
    horari_sencer = dia.horari_amb_tothom
    # La mateixa memòria cau de Dia.horari, amb la vista dels canvis pendents.
    dia.__dict__["horari"] = sense_absents_coberts(horari_sencer, absents_coberts(db, data))
    return dia


def aplica_absencia_coberta(
    db: Session, professor: str, data_inici: date, data_final: date, *, institucio: str, avui: date | None = None
) -> dict:
    """Aplica la baixa (veure el docstring del mòdul) i retorna el que ha canviat.
    Cal cridar-la després de desar-la: l'horari de cada dia ja no la hi té."""

    professor = (professor or "").strip()
    canvis: dict[str, list[dict]] = {"absencies_esborrades": [], "vigilancies_buidades": [], "substituts_trets": []}
    if not professor:
        return canvis

    for data in _dies_afectats(db, data_inici, data_final, avui or rellotge.avui()):
        dia = _dia_amb_absencies_pendents(db, institucio, data)
        gestors = dia.gestors()
        _, horari, _, absencies = gestors
        hores_absent = sorted(
            {
                s.hora
                for s in SubstitucioRepository.get_by_date(db, data)
                if s.professor_absent == professor and s.tipus_absencia in ("ABSENCIA", "SERVEI")
            }
        )
        if hores_absent:
            # El mateix que esborrar-li totes les absències des de la pantalla
            # (també treu els substituts que ja no són vàlids, com ell mateix)
            resposta = desa_absencies(
                db,
                data,
                professor,
                hores_absencia=[],
                hores_servei=[],
                gestors=(horari, absencies),
                gestors_cobertures=gestors,
                dia_escolar=DiaEscolar(db, dia),
            )
            canvis["absencies_esborrades"] += [{"data": data, "hora": h} for h in hores_absent]
            canvis["substituts_trets"] += resposta.get("substituts_trets", [])

        hores_vigilancia = set()
        for vigs in VigilanciaRepository.get_by_date(db, data).values():
            for vig in vigs:
                if (vig.vigilant or "").strip() == professor:
                    assert vig.id is not None  # la fila ve de la BD
                    VigilanciaRepository.update_by_id(db, data, vig.id, {"vigilant": ""})
                    hores_vigilancia.add(vig.hora)
                    canvis["vigilancies_buidades"].append({"data": data, "hora": vig.hora, "tipus": vig.tipus})
        for hora in sorted(hores_vigilancia):
            refresca_cobertures(data, hora, db, gestors=gestors)

        dia_escolar = DiaEscolar(db, dia)
        canvis["substituts_trets"] += [
            {**fila, "data": data} for fila in treu_substituts_no_valids(db, data, dia_escolar)
        ]

    return canvis


def absencies_cobertes_del_dia(institucio: str, data: date, professors: Collection[str]) -> list[dict]:
    """Per mostrar-los (no per decidir res): dels `professors` (els que
    l'horari del dia ha tret), fins quan dura la seva absència coberta.
    [{professor, data_final}], per nom."""

    with get_data_db_session(institucio, lectura=True) as db:
        absencies = AbsenciaCobertaRepository.get_all(db)
    resultat = []
    for professor in sorted(professors):
        finals = [
            a["data_final"]
            for a in absencies
            if nom_net(a["professor"] or "") == professor and absents_coberts_en([a], data)
        ]
        resultat.append({"professor": professor, "data_final": max(finals) if finals else None})
    return resultat


def classes_sense_substitut(institucio: str, professor: str, data_inici: date, data_final: date) -> list[dict]:
    """Les classes de `professor` durant el període que, a l'XML vigent cada
    dia, no tenen cap altre professor amb el mateix grup a la mateixa hora: si
    hi fos el substitut extern, n'hi hauria un. És un avís, no bloqueja res.
    Cada classe surt un cop per dia de la setmana i horari: {dia, hora, grup,
    assignatura}."""

    professor = nom_net(professor) or ""
    vistos, resultat = set(), []
    data = data_inici
    for _ in range(min((data_final - data_inici).days + 1, 400)):  # un curs, com a molt
        try:
            vista = Dia(data, institucio).horari
        except MissingXmlError:
            data += timedelta(days=1)
            continue
        horari = getattr(vista, "sencer", vista)
        nom_dia = horari.get_dia_name(data.weekday())
        clau = (id(horari), nom_dia)
        if clau not in vistos:
            vistos.add(clau)
            for hora, profs in horari.horari.get(nom_dia, {}).items():
                classe = profs.get(professor) or {}
                grup = classe.get("grup")
                if grup and not any(p != professor and (a or {}).get("grup") == grup for p, a in profs.items()):
                    resultat.append(
                        {"dia": nom_dia, "hora": hora, "grup": grup, "assignatura": classe.get("assignatura", "")}
                    )
        data += timedelta(days=1)
    return resultat


# ------------------------------------------------------------ alta, edició i baixa


def llista(db: Session) -> list[AbsenciaCobertaFitxa]:
    return AbsenciaCobertaRepository.get_all(db)


def _aplica_i_avisa(db: Session, absencia_id: int, institucio: str) -> dict:
    absencia = AbsenciaCobertaRepository.get_by_id(db, absencia_id)
    assert absencia is not None  # la mateixa transacció l'acaba de desar
    canvis = aplica_absencia_coberta(
        db,
        absencia["professor"],
        absencia["data_inici"],
        absencia["data_final"],
        institucio=institucio,
    )
    classes = classes_sense_substitut(institucio, absencia["professor"], absencia["data_inici"], absencia["data_final"])
    avisos = [{"codi": "classe_sense_substitut", "params": c} for c in classes] or None
    return {"canvis": canvis, "avisos": avisos}


def crea(db: Session, institucio: str, professor: str, data_inici: date, data_final: date, motiu: str = "") -> dict:
    """Desa una absència coberta i l'aplica. Retorna {id, canvis, avisos}."""
    absencia_id = AbsenciaCobertaRepository.create(db, professor, data_inici, data_final, motiu)
    resultat = {"id": absencia_id, **_aplica_i_avisa(db, absencia_id, institucio)}
    db.commit()
    return resultat


def edita(db: Session, institucio: str, absencia_id: int, **camps: Unpack[CanvisAbsenciaCoberta]) -> dict:
    """Canvia els camps donats (professor, data_inici, data_final, motiu) i
    l'aplica de nou. Retorna {canvis, avisos}."""
    if not AbsenciaCobertaRepository.update(db, absencia_id, **camps):
        raise NoTrobat("Absència coberta no trobada", codi="absencia_coberta_no_trobada")
    resultat = _aplica_i_avisa(db, absencia_id, institucio)
    db.commit()
    return resultat


def esborra(db: Session, absencia_id: int) -> None:
    if not AbsenciaCobertaRepository.delete(db, absencia_id):
        raise NoTrobat("Absència coberta no trobada", codi="absencia_coberta_no_trobada")
    db.commit()
