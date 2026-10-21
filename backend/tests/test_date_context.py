"""utils/date_context.DateContext: la data dels PDF i el dia de la setmana."""

from datetime import datetime

import i18n_setup
from utils.date_context import DateContext


def test_data_completa_en_l_idioma_actiu(monkeypatch):
    monkeypatch.setattr(i18n_setup, "CURRENT_LANGUAGE", "ca")
    assert DateContext.from_iso("2026-01-06").full_format == "Dimarts, 6 de gener del 2026"
    monkeypatch.setattr(i18n_setup, "CURRENT_LANGUAGE", "es")
    assert DateContext.from_iso("2026-01-06").full_format.startswith("Martes, 6 de enero")


def test_dia_de_la_setmana():
    assert DateContext.from_iso("2026-10-19").weekday_index == 0  # dilluns
    assert DateContext.from_iso("2026-10-18").weekday_index == 6  # diumenge


def test_una_data_no_valida_es_avui():
    assert DateContext.from_iso("no-és-una-data").datetime.date() == datetime.now().date()
