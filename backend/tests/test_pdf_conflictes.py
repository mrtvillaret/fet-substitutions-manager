"""
Avisos de conflicte del PDF (pdf/engine.py): un substitut o vigilant que
és absent a aquella hora surt com a «absent» o, si l'absència és per servei,
com a «absent (servei)». El tipus surt de les seves pròpies files de substitució.
"""

import pytest
from test_vigilancies_analisi import dia_fals

from pdf.engine import PDFCompletExporter
from pdf.taula import taula_del_dia
from vigilancies.analisi import analitza_vigilancies


def _conflictes(tmp_path, tipus):
    files = [{"hora": "10:00", "professor_absent": "Prof 2", "tipus_absencia": tipus}]
    dia = dia_fals([{"hora": "10:00", "vigilant": "Prof 2", "aula": "A01"}], files, absents={"10:00": {"Prof 2"}})
    return analitza_vigilancies(dia)


@pytest.mark.parametrize("tipus", ["ABSENCIA", "SERVEI"])
def test_vigilant_absent_te_un_sol_problema_important(tipus, tmp_path):
    problemes = _conflictes(tmp_path, tipus)
    assert [p["tipus"] for p in problemes] == ["vigilant_absent_sense_cobertura"]
    assert problemes[0]["gravetat"] == "important"


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
    vigilancies = [{"hora": "10:00", "tipus": "Dilluns", "vigilant": "", "aula": ""}]
    conflictes = [p["missatge"] for p in analitza_vigilancies(dia_fals(vigilancies))]
    assert any("Dilluns" in c and "vigilant" in c for c in conflictes), conflictes
    assert any("Dilluns" in c and "aula" in c for c in conflictes), conflictes
    assert not any("Lunes" in c for c in conflictes), conflictes


def test_el_valor_fix_vigilancia_si_que_es_tradueix(tmp_path, castella):
    vigilancies = [{"hora": "10:00", "tipus": "VIGILÀNCIA", "vigilant": "", "aula": ""}]
    conflictes = [p["missatge"] for p in analitza_vigilancies(dia_fals(vigilancies))]
    assert sum("VIGILANCIA" in c for c in conflictes) == 2, conflictes
    assert not any("VIGILÀNCIA" in c for c in conflictes), conflictes
