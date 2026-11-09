"""Lectura i vista de les absències cobertes, sense orquestració de canvis."""

import copy
import logging
from datetime import datetime

from absencia_coberta.repositories import AbsenciaCobertaRepository
from textos import nom_net

# Conserva el nom del logger anterior al moviment.
log = logging.getLogger("absencia_coberta.services")


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


def vista_per_data(db):
    """Una lectura de períodes per a totes les vistes d'una petició."""
    baixes = AbsenciaCobertaRepository.get_all(db)

    def vista(horari, data):
        return sense_absents_coberts(horari, frozenset(absents_coberts_en(baixes, data)))

    return vista


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
