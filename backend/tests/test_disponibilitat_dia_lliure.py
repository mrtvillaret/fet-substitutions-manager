"""
Planificador (planificador/motor/disponibilitat.py): un professor que un
dia no té cap activitat «no treballa aquell dia», encara que el dia surti a
l'XML amb les franges buides (FET hi posa tots els dies). Amb horari
estricte, aquell dia queda bloquejat per als seus exàmens.
"""

import pytest

from planificador.compartit.franja import franja
from planificador.compartit.normalitzacio import normalitzar_dia
from planificador.motor.avaluador import causa_dura
from planificador.motor.compatibilitat import DIAGNOSTIC
from planificador.motor.disponibilitat import analitzar_disponibilitat_sessio

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
    # Prefix «1-ESO» (no és una data), com abans; comprovació dura de l'horari estricte
    ubicacio = franja("1-ESO_10:00")
    ubicacio = type(ubicacio)(ubicacio.clau, ubicacio.prefix, "Dimarts", None, ubicacio.hora)
    violacio = causa_dura(
        SESSIO,
        ubicacio,
        None,
        ["1-ESO"],
        analisi=_analisi("Dimarts", True),
        politiques=DIAGNOSTIC,
        restriccions=restriccions,
    )
    assert violacio is not None and violacio.clau == "professors_estrictes"
