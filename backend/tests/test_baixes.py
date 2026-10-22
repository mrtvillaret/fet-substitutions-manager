"""
absents_coberts_en (absencia_coberta/services.py): la funció única que diu qui té una absència coberta
en una data. Abans era copiada a deu llocs, i una sola baixa amb dates mal
escrites aturava el bucle: els professors que venien després no comptaven.
"""

from datetime import date, datetime

from absencia_coberta.services import absents_coberts_en

BAIXES = [
    {"professor": "Prof 1", "data_inici": "2026-04-01", "data_final": "2026-04-30"},
    {"professor": "Prof 2", "data_inici": "2026-04-20", "data_final": "2026-04-20"},
    {"professor": "Prof 3", "data_inici": "2026-05-01", "data_final": "2026-05-31"},
]


def test_dins_del_periode_inclosos_el_primer_i_el_darrer_dia():
    assert absents_coberts_en(BAIXES, "2026-04-20") == {"Prof 1", "Prof 2"}
    assert absents_coberts_en(BAIXES, "2026-04-01") == {"Prof 1"}
    assert absents_coberts_en(BAIXES, "2026-04-30") == {"Prof 1"}
    assert absents_coberts_en(BAIXES, "2026-06-01") == set()


def test_accepta_date_datetime_i_text():
    assert absents_coberts_en(BAIXES, date(2026, 5, 2)) == {"Prof 3"}
    assert absents_coberts_en(BAIXES, datetime(2026, 5, 2, 9, 30)) == {"Prof 3"}


def test_una_baixa_mal_escrita_no_atura_les_altres():
    baixes = [
        {"professor": "Prof 9", "data_inici": "01/04/2026", "data_final": "2026-04-30"},
        {"professor": "Prof 8"},
    ] + BAIXES
    assert absents_coberts_en(baixes, "2026-04-20") == {"Prof 1", "Prof 2"}
