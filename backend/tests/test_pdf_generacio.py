"""
Les peces dels PDF que es poden provar sense BD ni PDF (pdf/generacio.py i
pdf/disponibles.py).
"""

import pytest

from pdf import disponibles, generacio
from pdf.domain import IntervalNoValid


def test_les_substitucions_que_surten_al_pdf_del_dia():
    alliberats = {"08:00": ["1-ESO-B", "professor:Prof 9"]}
    no_substituir = ["Guàrdia"]

    def surt(**camps):
        sub = {"hora": "08:00", "professor_absent": "Prof 1", "grup": "1-ESO-A", "assignatura": "Català", **camps}
        return generacio.es_substitucio_del_pdf(sub, alliberats, no_substituir)

    assert surt()
    assert not surt(grup="1-ESO-B")  # el grup no tenia classe
    assert not surt(professor_absent="Prof 9")  # alliberat
    assert surt(grup="1-ESO-B", tipus_absencia="VIGILANCIA_ABSENT")  # sempre
    assert surt(grup="", assignatura="Reforç")
    assert not surt(grup="", assignatura="Guàrdia")
    assert not surt(grup=" ", assignatura="Reforç", professor_absent="Prof 9")


def test_dates_de_l_interval():
    assert generacio.dates_de_l_interval("2026-03-06", "2026-03-09", False) == ["2026-03-06", "2026-03-09"]
    assert generacio.dates_de_l_interval("2026-03-06", "2026-03-08", True) == [
        "2026-03-06",
        "2026-03-07",
        "2026-03-08",
    ]
    with pytest.raises(IntervalNoValid):
        generacio.dates_de_l_interval("2026-03-09", "2026-03-06", True)


def test_titol_de_l_interval():
    assert generacio.titol_de_l_interval("2026-03-02", "2026-03-06", []) == "02/03/2026 - 06/03/2026"
    assert (
        generacio.titol_de_l_interval("2026-03-02", "2026-03-06", ["1-ESO", "2-BAT"])
        == "02/03/2026 - 06/03/2026 (1-ESO - 2-BAT)"
    )


def test_vigilancies_dels_nivells_en_l_ordre_de_la_pantalla():
    per_nivell = {
        "2-BAT": [{"hora": "10:00", "ordre": 1, "grups": "2-BAT-A"}],
        "1-ESO": [{"hora": "08:00", "ordre": 0, "grups": "1-ESO-A"}],
    }

    assert [v["grups"] for v in generacio.vigilancies_dels_nivells(per_nivell, [])] == ["1-ESO-A", "2-BAT-A"]
    assert [v["grups"] for v in generacio.vigilancies_dels_nivells(per_nivell, ["2-BAT"])] == ["2-BAT-A"]


def test_linies_dels_disponibles_amb_els_absents_i_els_ocupats_ratllats():
    linies = disponibles.linies_de_l_hora(
        [("Prof 3", "Guàrdia", ""), ("Prof 1", "Guàrdia", ""), ("Prof 2", "Guàrdia", "")],
        absents={"Prof 2"},
        ocupats={"Prof 3"},
    )

    assert len(linies) == 1
    assert "Prof 1, " in linies[0]
    assert '<strike><font color="#d97706">Prof 2</font></strike>' in linies[0]
    assert '<strike><font color="#9ca3af">Prof 3</font></strike>' in linies[0]
