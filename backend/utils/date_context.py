"""
Una data i les maneres de mostrar-la (en l'idioma actiu) que fan servir els PDF
i el motor.
"""

from datetime import datetime

from babel.dates import format_date

import i18n_setup


class DateContext:
    def __init__(self, data: datetime = None):
        self._data = data or datetime.now()

    @classmethod
    def from_iso(cls, iso_date: str) -> "DateContext":
        """Des de 'YYYY-MM-DD' (si no és vàlida, avui)."""
        try:
            return cls(datetime.strptime(iso_date, "%Y-%m-%d"))
        except ValueError:
            return cls()

    @property
    def datetime(self) -> datetime:
        return self._data

    @property
    def full_format(self) -> str:
        """Amb el dia de la setmana, en l'idioma actiu i amb majúscula inicial.
        Ex.: 'Dimarts, 6 de gener de 2026' (ca) / 'Martes, 6 de enero de 2026' (es)."""
        text = format_date(self._data, format="full", locale=i18n_setup.CURRENT_LANGUAGE)
        return text[:1].upper() + text[1:] if text else text

    @property
    def weekday_index(self) -> int:
        """0 = dilluns ... 6 = diumenge."""
        return self._data.weekday()

    def __repr__(self) -> str:
        return f"DateContext({self._data:%Y-%m-%d})"
