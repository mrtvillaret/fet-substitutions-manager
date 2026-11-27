"""
Absència coberta: un professor absent que té un substitut extern a l'XML.
Durant el període, l'absent queda fora de tot. La regla es resol en un sol
punt: l'horari d'una data (horari.context.get_horari, per on passa Dia) ja no el
té (absencia_coberta.domain.sense_absents_coberts). Qui té una absència coberta
en una data ho diu una sola funció, absents_coberts_en: abans era copiada a deu
llocs, i una sola baixa amb dates mal escrites aturava el bucle (els professors
que venien després no comptaven).
"""

import re
from datetime import date
from pathlib import Path

import pytest

from absencia_coberta.domain import absents_coberts_en

BACKEND = Path(__file__).resolve().parent.parent

# Peces per saber qui té una absència coberta: només les pot fer servir el
# mòdul (i el punt únic de horari.context.get_horari, que crida les seves funcions)
PROHIBIT = re.compile(
    r"\b(AbsenciaCobertaRepository|absents_coberts_en|PROFESSORS_BAIXA|professors_de_baixa|esta_de_baixa|GestorBaixes)\b"
)
# La taula, fora del mòdul: el model i la migració dels noms
TAULA = re.compile(r"\bprofessors_baixa\b")
TAULA_PERMESA = {"models.py", "migracions/noms_nets.py"}
# (el model, AbsenciaCoberta, també el fan servir la purga de dades,
# dades/services.py, i l'informe de direcció, que en compta els registres:
# pdf/repositories.py)


def test_cap_codi_fora_del_modul_comprova_qui_te_una_absencia_coberta():
    errors = []
    for fitxer in BACKEND.rglob("*.py"):
        parts = fitxer.relative_to(BACKEND).parts
        if parts[0].startswith("venv") or "tests" in parts or parts[0] == "absencia_coberta":
            continue
        relatiu = "/".join(parts)
        for n, linia in enumerate(fitxer.read_text(encoding="utf-8").splitlines(), 1):
            if PROHIBIT.search(linia):
                errors.append(f"{relatiu}:{n}: {linia.strip()}")
            elif TAULA.search(linia) and relatiu not in TAULA_PERMESA:
                errors.append(f"{relatiu}:{n}: (taula) {linia.strip()}")
    assert errors == []


# --------------- absents_coberts_en: qui té una absència coberta en una data


BAIXES = [
    {"professor": "Prof 1", "data_inici": "2026-04-01", "data_final": "2026-04-30"},
    {"professor": "Prof 2", "data_inici": "2026-04-20", "data_final": "2026-04-20"},
    {"professor": "Prof 3", "data_inici": "2026-05-01", "data_final": "2026-05-31"},
]


@pytest.mark.parametrize(
    "data, absents",
    [
        (date(2026, 4, 20), {"Prof 1", "Prof 2"}),
        (date(2026, 4, 1), {"Prof 1"}),  # el primer dia
        (date(2026, 4, 30), {"Prof 1"}),  # el darrer dia
        (date(2026, 6, 1), set()),
        (date(2026, 5, 2), {"Prof 3"}),
    ],
)
def test_dins_del_periode_inclosos_el_primer_i_el_darrer_dia(data, absents):
    assert absents_coberts_en(BAIXES, data) == absents


def test_una_baixa_mal_escrita_no_atura_les_altres():
    baixes = [
        {"professor": "Prof 9", "data_inici": "01/04/2026", "data_final": "2026-04-30"},
        {"professor": "Prof 8"},
    ] + BAIXES
    assert absents_coberts_en(baixes, date(2026, 4, 20)) == {"Prof 1", "Prof 2"}
