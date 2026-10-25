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

import copy
import logging
from datetime import date, datetime, timedelta

from absencia_coberta.repositories import AbsenciaCobertaRepository
from errors_domini import NoTrobat
from models import Substitucio, Vigilancia
from noms import nom_net
from repositories import SubstitucioRepository, parse_date
from serveis.absencies import desa_absencies
from serveis.cobertures import refresca_cobertures
from serveis.dia_escolar import treu_substituts_no_valids
from vigilancies.repositories import VigilanciaRepository

log = logging.getLogger(__name__)


def _dies_afectats(db, data_inici: str, data_final: str, avui: date) -> list:
    try:
        inici = datetime.strptime(data_inici, "%Y-%m-%d").date()
        final = datetime.strptime(data_final, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return []
    inici = max(inici, avui)
    if inici > final:
        return []
    dates = set()
    for model in (Substitucio, Vigilancia):
        for (d,) in (
            db.query(model.data)
            .filter(model.data >= parse_date(inici.isoformat()), model.data <= parse_date(final.isoformat()))
            .distinct()
        ):
            dates.add(d.isoformat())
    return sorted(dates)


def aplica_absencia_coberta(db, professor: str, data_inici: str, data_final: str, avui: date = None) -> dict:
    """Aplica la baixa (veure el docstring del mòdul) i retorna el que ha canviat.
    Cal cridar-la després de desar-la: l'horari de cada dia ja no la hi té."""

    professor = (professor or "").strip()
    canvis = {"absencies_esborrades": [], "vigilancies_buidades": [], "substituts_trets": []}
    if not professor:
        return canvis

    for d in _dies_afectats(db, data_inici, data_final, avui or date.today()):
        hores_absent = sorted(
            {
                s.get("hora", "")
                for s in SubstitucioRepository.get_by_date(db, d)
                if s.get("professor_absent") == professor and s.get("tipus_absencia") in ("ABSENCIA", "SERVEI")
            }
        )
        if hores_absent:
            # El mateix que esborrar-li totes les absències des de la pantalla
            # (també treu els substituts que ja no són vàlids, com ell mateix)
            resposta = desa_absencies(db, d, professor, hores_absencia=[], hores_servei=[])
            canvis["absencies_esborrades"] += [{"data": d, "hora": h} for h in hores_absent]
            canvis["substituts_trets"] += resposta.get("substituts_trets", [])

        hores_vigilancia = set()
        for vigs in VigilanciaRepository.get_by_date(db, d).values():
            for vig in vigs:
                if (vig.get("vigilant") or "").strip() == professor:
                    VigilanciaRepository.update_by_id(db, d, str(vig["id"]), {"vigilant": ""})
                    hores_vigilancia.add(vig.get("hora", ""))
                    canvis["vigilancies_buidades"].append(
                        {"data": d, "hora": vig.get("hora", ""), "tipus": vig.get("tipus", "")}
                    )
        db.commit()  # el repositori de vigilàncies no en fa
        for hora in sorted(hores_vigilancia):
            refresca_cobertures(d, hora, db)

        canvis["substituts_trets"] += [{**fila, "data": d} for fila in treu_substituts_no_valids(db, d)]

    return canvis


def absents_coberts_en(baixes, data) -> set:
    """Els professors amb una absència coberta en una data (inclosos el primer
    i el darrer dia). `baixes`: [{professor, data_inici, data_final}];
    `data`: date, datetime o text AAAA-MM-DD. Una baixa amb dates invàlides
    s'ignora (i se n'avisa) sense afectar les altres."""
    if isinstance(data, str):
        data = datetime.strptime(data, "%Y-%m-%d").date()
    elif isinstance(data, datetime):
        data = data.date()
    resultat = set()
    for baixa in baixes:
        professor = nom_net(baixa.get("professor") or "")
        try:
            inici = datetime.strptime(baixa["data_inici"], "%Y-%m-%d").date()
            final = datetime.strptime(baixa["data_final"], "%Y-%m-%d").date()
        except (KeyError, TypeError, ValueError):
            log.warning("Absència coberta amb dates invàlides: s'ignora")
            continue
        if professor and inici <= data <= final:
            resultat.add(professor)
    return resultat


def absents_coberts(db, data_iso: str) -> frozenset:
    """Els professors amb una absència coberta el dia `data_iso`."""
    return frozenset(absents_coberts_en(AbsenciaCobertaRepository.get_all(db), data_iso))


def sense_absents_coberts(horari, absents: frozenset):
    """L'horari d'un dia sense els professors amb una absència coberta: queden
    fora de tot (ni substitueixen, ni són substituïts, ni vigilen, ni surten
    com a disponibles). Les classes del grup continuen, perquè el substitut és
    a l'XML. És una vista: l'horari de memòria cau (el de totes les dates) no
    es toca. L'ordre i el límit de l'«últim professor» ja hi són aplicats."""
    presents = absents & set(horari.professors)
    if not presents:
        return horari
    vista = copy.copy(horari)
    vista.professors = [p for p in horari.professors if p not in presents]
    vista.horari = {
        dia: {hora: {p: a for p, a in profs.items() if p not in presents} for hora, profs in hores.items()}
        for dia, hores in horari.horari.items()
    }
    vista.absents_coberts = frozenset(presents)
    vista.sencer = horari  # l'horari de l'XML, amb tothom (per comprovar els substituts)
    return vista


def absencies_cobertes_del_dia(institucio: str, data_iso: str, professors) -> list:
    """Per mostrar-los (no per decidir res): dels `professors` (els que
    l'horari del dia ha tret), fins quan dura la seva absència coberta.
    [{professor, data_final}], per nom."""
    from database import get_data_db_session

    with get_data_db_session(institucio) as db:
        absencies = AbsenciaCobertaRepository.get_all(db)
    resultat = []
    for professor in sorted(professors):
        finals = [
            a.get("data_final")
            for a in absencies
            if nom_net(a.get("professor") or "") == professor and absents_coberts_en([a], data_iso)
        ]
        resultat.append({"professor": professor, "data_final": max(finals) if finals else None})
    return resultat


def classes_sense_substitut(institucio: str, professor: str, data_inici: str, data_final: str) -> list:
    """Les classes de `professor` durant el període que, a l'XML vigent cada
    dia, no tenen cap altre professor amb el mateix grup a la mateixa hora: si
    hi fos el substitut extern, n'hi hauria un. És un avís, no bloqueja res.
    Cada classe surt un cop per dia de la setmana i horari: {dia, hora, grup,
    assignatura}."""
    from helpers import MissingXmlError
    from serveis.dia import Dia

    professor = nom_net(professor or "")
    try:
        inici = datetime.strptime(data_inici, "%Y-%m-%d").date()
        final = datetime.strptime(data_final, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return []
    vistos, resultat = set(), []
    data = inici
    for _ in range(min((final - inici).days + 1, 400)):  # un curs, com a molt
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


def absencia_coberta_de(db, professor: str, data: str):
    """L'absència coberta que té `professor` el dia `data` ({professor,
    data_inici, data_final...}), o None."""
    professor = nom_net(professor or "")
    for baixa in AbsenciaCobertaRepository.get_all(db):
        if nom_net(baixa.get("professor") or "") == professor and absents_coberts_en([baixa], data):
            return baixa
    return None


def missatge_absencia_coberta(professor: str, baixa: dict) -> str:
    return (
        f"{professor} té una absència coberta ({baixa.get('data_inici')} – {baixa.get('data_final')}): "
        "no se li posen absències, perquè les seves classes ja estan cobertes a l'XML. "
        "Si cal, escurça-la o treu-la."
    )


# ------------------------------------------------------------ alta, edició i baixa


def llista(db) -> list:
    return AbsenciaCobertaRepository.get_all(db)


def _aplica_i_avisa(db, absencia_id: int, institucio: str) -> dict:
    absencia = AbsenciaCobertaRepository.get_by_id(db, absencia_id)
    canvis = aplica_absencia_coberta(db, absencia["professor"], absencia["data_inici"], absencia["data_final"])
    classes = classes_sense_substitut(institucio, absencia["professor"], absencia["data_inici"], absencia["data_final"])
    avisos = [{"codi": "classe_sense_substitut", "params": c} for c in classes] or None
    return {"canvis": canvis, "avisos": avisos}


def crea(db, institucio: str, professor: str, data_inici: str, data_final: str, motiu: str = "") -> dict:
    """Desa una absència coberta i l'aplica. Retorna {id, canvis, avisos}."""
    absencia_id = AbsenciaCobertaRepository.create(db, professor, data_inici, data_final, motiu)
    db.commit()
    return {"id": absencia_id, **_aplica_i_avisa(db, absencia_id, institucio)}


def edita(db, institucio: str, absencia_id: int, **camps) -> dict:
    """Canvia els camps donats (professor, data_inici, data_final, motiu) i
    l'aplica de nou. Retorna {canvis, avisos}."""
    if not AbsenciaCobertaRepository.update(db, absencia_id, **camps):
        raise NoTrobat("Absència coberta no trobada", codi="absencia_coberta_no_trobada")
    db.commit()
    return _aplica_i_avisa(db, absencia_id, institucio)


def esborra(db, absencia_id: int) -> None:
    if not AbsenciaCobertaRepository.delete(db, absencia_id):
        raise NoTrobat("Absència coberta no trobada", codi="absencia_coberta_no_trobada")
    db.commit()
