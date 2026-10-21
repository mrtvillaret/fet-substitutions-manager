"""
Planificador (scheduler_engine/core/availability.py): un professor que un
dia no té cap activitat «no treballa aquell dia», encara que el dia surti a
l'XML amb les franges buides (FET hi posa tots els dies). Amb horari
estricte, aquell dia queda bloquejat per als seus exàmens.
"""

import pytest

from scheduler_engine.core.availability import analitzar_disponibilitat_sessio
from scheduler_engine.core.normalitzacio import normalitzar_dia
from scheduler_engine.core.restriction_engine import RestrictionEngine

HORES = ["09:00", "10:00", "11:30"]
# Com ho llegeix el planificador de l'XML: el dimarts hi és, però buit
HORARIS = {
    "Prof X": {
        normalitzar_dia("Dilluns"): {"09:00": {"assignatura": "Mat", "grup": "1-ESO-A"}},
        normalitzar_dia("Dimarts"): {},
    }
}
SESSIO = {"nom": "Mat 1r", "examens": [{"titular": "Prof X"}]}


def _analisi(dia, normalitzat):
    kw = {"horaris_professors_norm": HORARIS} if normalitzat else {}
    return analitzar_disponibilitat_sessio(SESSIO, dia, "10:00", HORARIS, HORES, ["1-ESO"], 1, **kw)


@pytest.mark.parametrize("normalitzat", [False, True])
def test_un_dia_sense_cap_activitat_es_no_treballa(normalitzat):
    analisi = _analisi("Dimarts", normalitzat)
    assert [i["professor"] for i in analisi["no_treballa_dia"]] == ["Prof X"]
    assert analisi["lliures"] == []


@pytest.mark.parametrize("normalitzat", [False, True])
def test_un_dia_amb_activitat_no_es_no_treballa(normalitzat):
    assert _analisi("Dilluns", normalitzat)["no_treballa_dia"] == []


def test_amb_horari_estricte_el_dia_lliure_queda_bloquejat():
    restriccions = {"restriccions_dures": {"professors_horari_estricte": ["Prof X"]}}
    motor = RestrictionEngine(restriccions, ["1-ESO"])
    violacio = motor.check_hard(SESSIO, "Dimarts", "10:00", "1-ESO", [], [], analisi=_analisi("Dimarts", True))
    assert violacio is not None and violacio.restriction == "professors_estrictes"
