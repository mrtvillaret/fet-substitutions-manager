"""
Avisos de conflicte del PDF (export/pdf/engine.py): un substitut o vigilant que
és absent a aquella hora surt com a «absent» o, si l'absència és per servei,
com a «absent (servei)». El tipus surt de les seves pròpies files de substitució.
"""

import pytest

from export.pdf.engine import PDFCompletExporter
from export.pdf.taula import taula_del_dia


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
    taula = taula_del_dia(exporter, dades, espai_a_ma=False, combinada=True)[0]
    assert taula._cellvalues[1][1].style.fontSize == pytest.approx(cos)  # cel·la «Absent»
    assert taula._cellStyles[1][1].topPadding == marge


def test_a_la_llista_de_conflictes_l_hora_surt_un_sol_cop(tmp_path):
    # L'hora ja és al títol del grup («HORA 09:00:»): les línies no la repeteixen
    exporter = PDFCompletExporter(hores=["09:00"], export_dir=str(tmp_path))
    taula = exporter._crear_taula_conflictes(["• 09:00: Prof 12 té dues substitucions", "09:00: Prof 3 és absent"])
    textos = [str(fila[0].text) for fila in taula._cellvalues]
    assert sum("09:00" in t for t in textos) == 1, textos
    assert any("Prof 12 té dues substitucions" in t for t in textos)
    assert any(t.startswith("Prof 3 és absent") for t in textos), textos


# ------------------------------------------------ vigilàncies sense vigilant o sense aula


@pytest.fixture
def castella():
    import i18n_setup

    i18n_setup.setup_translation("es")
    yield
    i18n_setup.setup_translation("ca")


def test_el_nom_de_l_assignatura_no_es_tradueix_als_conflictes(tmp_path, castella):
    # «Dilluns» té traducció al castellà («Lunes»), però aquí és el nom d'una
    # assignatura (una dada del centre): ha de sortir tal com és
    exporter = PDFCompletExporter(hores=["10:00"], export_dir=str(tmp_path))
    vigilancies = [{"hora": "10:00", "tipus": "Dilluns", "vigilant": "", "aula": ""}]
    conflictes = exporter._validar_conflictes_complets([], vigilancies, absents={})
    assert any("Dilluns" in c and "vigilant" in c for c in conflictes), conflictes
    assert any("Dilluns" in c and "aula" in c for c in conflictes), conflictes
    assert not any("Lunes" in c for c in conflictes), conflictes


def test_el_valor_fix_vigilancia_si_que_es_tradueix(tmp_path, castella):
    exporter = PDFCompletExporter(hores=["10:00"], export_dir=str(tmp_path))
    vigilancies = [{"hora": "10:00", "tipus": "VIGILÀNCIA", "vigilant": "", "aula": ""}]
    conflictes = exporter._validar_conflictes_complets([], vigilancies, absents={})
    assert sum("VIGILANCIA" in c for c in conflictes) == 2, conflictes
    assert not any("VIGILÀNCIA" in c for c in conflictes), conflictes
