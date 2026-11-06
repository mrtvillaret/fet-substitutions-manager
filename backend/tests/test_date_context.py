"""Formats dels PDF i lectura de dates sense un objecte intermedi."""

from contextvars import ContextVar
from datetime import date, datetime

import pytest

import i18n_setup
from dates import data_compacta, data_completa, parse_date


@pytest.mark.parametrize("data", [date(2026, 1, 6), datetime(2026, 1, 6, 23, 45)])
def test_data_completa_en_l_idioma_actiu(monkeypatch, data):
    # CURRENT_LANGUAGE és dinàmic (__getattr__): restaurar-lo amb setattr
    # deixaria un atribut fix que contaminaria els tests posteriors.
    monkeypatch.setattr(i18n_setup, "_idioma_peticio", ContextVar("idioma_de_prova", default="ca"))
    i18n_setup.setup_translation("ca")
    assert data_completa(data) == "Dimarts, 6 de gener del 2026"
    i18n_setup.setup_translation("es")
    assert data_completa(data).startswith("Martes, 6 de enero")
    assert "CURRENT_LANGUAGE" not in vars(i18n_setup)


@pytest.mark.parametrize("data", [date(2026, 1, 6), datetime(2026, 1, 6, 23, 45)])
def test_data_compacta_per_als_noms_dels_pdf(data):
    assert data_compacta(data) == "260106"


def test_dia_de_la_setmana():
    assert parse_date("2026-10-19").weekday() == 0  # dilluns
    assert parse_date("2026-10-18").weekday() == 6  # diumenge


def test_una_data_no_valida_es_un_error():
    with pytest.raises(ValueError):
        parse_date("no-és-una-data")
