"""«Mateixa data» i «dates diferents» obligatòries (pes >= 100) es comparen per
data: dos dilluns de setmanes diferents són dues dates."""

import pytest

from planificador.motor.regles import viola_preferencia_dia_obligatoria

A = {"nom": "A (1-BAT)", "curs": "1-BAT"}
B = {"nom": "B (1-BAT)", "curs": "1-BAT"}
DILLUNS_1, DILLUNS_2 = "2027-03-01", "2027-03-08"


def _restriccions(clau, pes=100):
    return {"preferencies": {clau: [{"assignatures": [A["nom"], B["nom"]], "pes": pes}]}}


@pytest.mark.parametrize(
    ("clau", "data_de_b", "viola"),
    [
        ("dies_diferents", DILLUNS_1, True),
        ("dies_diferents", DILLUNS_2, False),
        ("mateix_dia", DILLUNS_1, False),
        ("mateix_dia", DILLUNS_2, True),
    ],
)
def test_preferencia_obligatoria_per_data(clau, data_de_b, viola):
    assert viola_preferencia_dia_obligatoria(B, data_de_b, {DILLUNS_1: [A]}, _restriccions(clau)) is viola


@pytest.mark.parametrize(("clau", "viola"), [("dies_diferents", True), ("mateix_dia", False)])
def test_sense_dates_es_compara_pel_nom_del_dia(clau, viola):
    assert viola_preferencia_dia_obligatoria(B, "Dilluns", {"dilluns": [A]}, _restriccions(clau)) is viola


def test_per_sota_de_100_no_es_obligatoria():
    assert not viola_preferencia_dia_obligatoria(B, DILLUNS_1, {DILLUNS_1: [A]}, _restriccions("dies_diferents", 90))
