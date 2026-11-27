"""
Les peces dels PDF que es poden provar sense BD ni PDF (pdf/generacio.py i
pdf/disponibles.py).
"""

from datetime import date

import pytest

from pdf import disponibles, generacio
from pdf.domain import IntervalNoValid
from pdf.engine import PDFCompletExporter
from pdf.files import VigilanciaPdf
from vigilancies.files import FilaVigilancia


def test_dates_de_l_interval():
    assert generacio.dates_de_l_interval(date(2026, 3, 6), date(2026, 3, 9), False) == [
        date(2026, 3, 6),
        date(2026, 3, 9),
    ]
    assert generacio.dates_de_l_interval(date(2026, 3, 6), date(2026, 3, 8), True) == [
        date(2026, 3, 6),
        date(2026, 3, 7),
        date(2026, 3, 8),
    ]
    with pytest.raises(IntervalNoValid):
        generacio.dates_de_l_interval(date(2026, 3, 9), date(2026, 3, 6), True)


def test_titol_de_l_interval():
    assert generacio.titol_de_l_interval(date(2026, 3, 2), date(2026, 3, 6), []) == "02/03/2026 - 06/03/2026"
    assert (
        generacio.titol_de_l_interval(date(2026, 3, 2), date(2026, 3, 6), ["1-ESO", "2-BAT"])
        == "02/03/2026 - 06/03/2026 (1-ESO - 2-BAT)"
    )


def test_els_dies_sense_data_queden_al_final_en_l_ordre_d_entrada(tmp_path):
    exportador = PDFCompletExporter(export_dir=str(tmp_path), institucio="prova")
    vigilancies = [
        VigilanciaPdf(hora="08:00", dia_interval="Sense data"),
        VigilanciaPdf(dia_interval="Dia buit", data=date(2026, 4, 1), dia_buit=True),
        VigilanciaPdf(hora="08:00", dia_interval="Dia anterior", data=date(2026, 3, 31)),
        VigilanciaPdf(hora="08:00", dia_interval="Tampoc té data"),
    ]
    per_dia, ordre = exportador._sort_vigilancies_by_date(vigilancies)
    assert ordre == ["Dia anterior", "Dia buit", "Sense data", "Tampoc té data"]
    assert per_dia["Dia buit"] == {}


def test_vigilancies_dels_nivells_en_l_ordre_de_la_pantalla():
    per_nivell = {
        "2-BAT": [{"hora": "10:00", "ordre": 1, "grups": "2-BAT-A"}],
        "1-ESO": [{"hora": "08:00", "ordre": 0, "grups": "1-ESO-A"}],
        "": [{"hora": "09:00", "ordre": 0, "grups": "Antic"}],
    }

    per_nivell = {nivell: [FilaVigilancia(**v) for v in files] for nivell, files in per_nivell.items()}

    assert [v.grups for v in generacio.vigilancies_dels_nivells(per_nivell, [])] == [
        "1-ESO-A",
        "Antic",
        "2-BAT-A",
    ]
    assert [v.grups for v in generacio.vigilancies_dels_nivells(per_nivell, ["2-BAT"])] == ["2-BAT-A"]
    assert [v.grups for v in generacio.vigilancies_dels_nivells(per_nivell, ["2-BAT"], inclou_sense_nivell=True)] == [
        "Antic",
        "2-BAT-A",
    ]
    assert [v.grups for v in generacio.vigilancies_dels_nivells(per_nivell, ["2-BAT"], inclou_sense_nivell=False)] == [
        "2-BAT-A"
    ]


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
