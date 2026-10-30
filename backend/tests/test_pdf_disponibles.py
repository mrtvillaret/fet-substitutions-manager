"""Regles pròpies del PDF de professors disponibles."""

from datetime import date
from types import SimpleNamespace

from pdf.disponibles import nom_dia_xml


def test_el_dia_xml_es_busca_pel_nom_i_no_per_la_posicio():
    horari = SimpleNamespace(dies=["Dimarts", "Dilluns", "Dimecres"])

    assert nom_dia_xml(horari, date(2026, 4, 20)) == "Dilluns"
    assert nom_dia_xml(horari, date(2026, 4, 21)) == "Dimarts"
