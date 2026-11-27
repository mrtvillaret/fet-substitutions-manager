"""
Les peces dels PDF que es poden provar sense BD ni PDF (pdf/generacio.py,
pdf/disponibles.py i pdf/icones.py).
"""

from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from horari.domain import Dia
from pdf import disponibles, generacio
from pdf.disponibles import nom_dia_xml
from pdf.domain import IntervalNoValid
from pdf.engine import PDFCompletExporter
from pdf.files import VigilanciaPdf
from pdf.icones import _ICONES, amb_icones
from substitucions import domain
from substitucions.files import FilaSubstitucio
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


def test_linies_dels_disponibles_amb_els_absents_i_els_ocupats_ratllats_i_el_motiu():
    linies = disponibles.linies_de_l_hora(
        [("Prof 3", "Guàrdia", ""), ("Prof 1", "Guàrdia", ""), ("Prof 2", "Guàrdia", ""), ("Prof 4", "Guàrdia", "")],
        motius={"Prof 2": ["absent"], "Prof 3": ["substitueix"], "Prof 4": ["substitueix", "vigila"]},
    )

    assert len(linies) == 1
    assert "Prof 1, " in linies[0]
    assert '<strike><font color="#d97706">Prof 2</font></strike> <font color="#d97706">(absent)</font>' in linies[0]
    assert (
        '<strike><font color="#9ca3af">Prof 3</font></strike> <font color="#9ca3af">(substitueix)</font>' in linies[0]
    )
    assert (
        '<strike><font color="#9ca3af">Prof 4</font></strike> <font color="#9ca3af">(substitueix, vigila)</font>'
        in (linies[0])
    )


def test_motius_del_dia_absents_substituts_i_vigilants(monkeypatch):
    files = [
        FilaSubstitucio(hora="10:00", professor_absent="Prof 1", substitut="Prof 5", tipus_absencia="ABSENCIA"),
        # Prof 2 vigila i Prof 6 li cobreix la classe; Prof 3 substitueix i Prof 7 li fa la guàrdia
        FilaSubstitucio(hora="10:00", professor_absent="Prof 2", substitut="Prof 6", tipus_absencia="VIGILANCIA"),
        FilaSubstitucio(hora="10:00", professor_absent="Prof 3", substitut="Prof 7", tipus_absencia="ENCADENADA"),
        FilaSubstitucio(hora="10:00", professor_absent="Prof 8", substitut="Prof 3", tipus_absencia="ABSENCIA"),
        FilaSubstitucio(hora="11:00", professor_absent="Prof 9", substitut="Prof 5", tipus_absencia="SERVEI"),
    ]
    vigilancies = {
        "1-ESO": [FilaVigilancia(hora="10:00", vigilant="Prof 2"), FilaVigilancia(hora="10:00", vigilant="Prof 5")]
    }
    monkeypatch.setattr(domain.SubstitucioRepository, "get_by_date", lambda *_: files)
    monkeypatch.setattr(domain.VigilanciaRepository, "get_by_date", lambda *_: vigilancies)
    monkeypatch.setattr(domain.AlliberatsDelDia, "get_by_date", lambda *_: {})

    motius = disponibles.motius_del_dia(domain.DiaEscolar(None, Dia(date(2026, 4, 20), "prova")))

    # Absents, només els de DiaEscolar.absents_per_hora (absència o servei): Prof 2,
    # que vigila, i Prof 3, que substitueix, no ho són.
    assert motius == {
        "10:00": {
            "Prof 1": ["absent"],
            "Prof 8": ["absent"],
            "Prof 5": ["substitueix", "vigila"],
            "Prof 6": ["substitueix"],
            "Prof 7": ["substitueix"],
            "Prof 3": ["substitueix"],
            "Prof 2": ["vigila"],
        },
        "11:00": {"Prof 9": ["absent"], "Prof 5": ["substitueix"]},
    }


# -------------------------------------------------------- PDF de disponibles


def test_el_dia_xml_es_busca_pel_nom_i_no_per_la_posicio():
    horari = SimpleNamespace(dies=["Dimarts", "Dilluns", "Dimecres"])

    assert nom_dia_xml(horari, date(2026, 4, 20)) == "Dilluns"
    assert nom_dia_xml(horari, date(2026, 4, 21)) == "Dimarts"


# ----------------------------- icones dels avisos (substitueixen els emojis)


def test_cada_icona_existeix():
    carpeta = Path(__file__).resolve().parents[1] / "pdf" / "icones"
    assert all((carpeta / fitxer).is_file() for fitxer in _ICONES.values())


def test_els_emojis_coneguts_es_canvien_per_la_imatge_i_la_resta_no():
    text = amb_icones("🕐 HORA 09:00: ⚠️ avís ❌ 🏫 aula 🙂")
    assert text.count("<img ") == 4
    assert "🙂" in text and "🕐" not in text
    assert amb_icones("sense cap emoji") == "sense cap emoji"
