"""
professors_de_baixa (core/baixes.py): la funció única que diu qui és de baixa
en una data. Abans era copiada a deu llocs, i una sola baixa amb dates mal
escrites aturava el bucle: els professors que venien després no comptaven.
"""
from datetime import date, datetime

from core.baixes import professors_de_baixa

BAIXES = [
    {"professor": "Prof 1", "data_inici": "2026-04-01", "data_final": "2026-04-30"},
    {"professor": "Prof 2", "data_inici": "2026-04-20", "data_final": "2026-04-20"},
    {"professor": "Prof 3", "data_inici": "2026-05-01", "data_final": "2026-05-31"},
]


def test_dins_del_periode_inclosos_el_primer_i_el_darrer_dia():
    assert professors_de_baixa(BAIXES, "2026-04-20") == {"Prof 1", "Prof 2"}
    assert professors_de_baixa(BAIXES, "2026-04-01") == {"Prof 1"}
    assert professors_de_baixa(BAIXES, "2026-04-30") == {"Prof 1"}
    assert professors_de_baixa(BAIXES, "2026-06-01") == set()


def test_accepta_date_datetime_i_text():
    assert professors_de_baixa(BAIXES, date(2026, 5, 2)) == {"Prof 3"}
    assert professors_de_baixa(BAIXES, datetime(2026, 5, 2, 9, 30)) == {"Prof 3"}


def test_una_baixa_mal_escrita_no_atura_les_altres():
    baixes = [{"professor": "Prof 9", "data_inici": "01/04/2026", "data_final": "2026-04-30"},
              {"professor": "Prof 8"}] + BAIXES
    assert professors_de_baixa(baixes, "2026-04-20") == {"Prof 1", "Prof 2"}
