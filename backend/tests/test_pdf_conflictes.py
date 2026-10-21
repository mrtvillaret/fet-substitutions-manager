"""
Avisos de conflicte del PDF (export/pdf/engine.py): un substitut o vigilant que
és absent a aquella hora surt com a «absent» o, si l'absència és per servei,
com a «absent (servei)». El tipus surt de les seves pròpies files de substitució.
"""

import pytest

from export.pdf.engine import PDFCompletExporter


def _conflictes(tmp_path, tipus):
    exporter = PDFCompletExporter(hores=["10:00"], export_dir=str(tmp_path))
    substitucions = [
        {
            "hora": "10:00",
            "professor_absent": "Prof 1",
            "assignatura": "Anglès",
            "substitut": "Prof 2",
            "tipus_absencia": "ABSENCIA",
        },
        {
            "hora": "10:00",
            "professor_absent": "Prof 2",
            "assignatura": "Física",
            "substitut": "Prof 3",
            "tipus_absencia": tipus,
        },
    ]
    vigilancies = [{"hora": "10:00", "vigilant": "Prof 2", "aula": "A01"}]
    return exporter._validar_conflictes_complets(substitucions, vigilancies, absents={"Prof 2": ["10:00"]})


def test_substitut_i_vigilant_absents(tmp_path):
    conflictes = _conflictes(tmp_path, "ABSENCIA")
    assert any("Substitut Prof 2 absent" in c for c in conflictes)
    assert any("Vigilant Prof 2 absent" in c for c in conflictes)


def test_absencia_per_servei(tmp_path):
    conflictes = _conflictes(tmp_path, "SERVEI")
    assert any("Substitut Prof 2 absent (servei)" in c for c in conflictes)
    assert any("Vigilant Prof 2 absent (servei)" in c for c in conflictes)


# ------------------------------------------------ mida de la lletra de la taula del dia


@pytest.mark.parametrize("mida, cos, marge", [(1.0, 10, 4), (1.2, 12, 4), (1.35, 13.5, 6)])
def test_la_taula_del_dia_fa_servir_la_mida_de_lletra(tmp_path, mida, cos, marge):
    exporter = PDFCompletExporter(hores=["10:00"], export_dir=str(tmp_path))
    exporter.mida_lletra = mida
    dades = {
        "10:00": {
            "substitucions": [
                {
                    "hora": "10:00",
                    "professor_absent": "Prof 1",
                    "grup": "1-ESO-A",
                    "assignatura": "Anglès",
                    "substitut": "Prof 2",
                }
            ],
            "vigilancies": [],
        }
    }
    taula = exporter._crear_taula_dia(dades, espai_a_ma=False)[0]
    assert taula._cellvalues[1][1].style.fontSize == pytest.approx(cos)  # cel·la «Absent»
    assert taula._cellStyles[1][1].topPadding == marge
