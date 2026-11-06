"""
Una data i les maneres de mostrar-la (en l'idioma actiu) que fan servir els PDF
i el motor.
"""

from datetime import date, datetime

from babel.dates import format_date

import i18n_setup


def data_completa(data: date | datetime) -> str:
    """Data amb el dia de la setmana, en l'idioma actiu i amb majúscula inicial."""
    text = format_date(data, format="full", locale=i18n_setup.CURRENT_LANGUAGE)
    return text[:1].upper() + text[1:] if text else text


def data_compacta(data: date | datetime) -> str:
    """Data AAMMDD per als noms de fitxer dels PDF."""
    return data.strftime("%y%m%d")


def parse_date(date_str: str) -> date:
    """Converteix string YYYY-MM-DD a objecte date de Python"""
    if isinstance(date_str, date):
        return date_str
    return datetime.strptime(date_str, "%Y-%m-%d").date()
