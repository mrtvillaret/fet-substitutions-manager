"""
Context object per gestió unificada de dates
Elimina duplicació de format_data_* i get_dia_setmana calls
"""
from datetime import datetime
from typing import Union, Optional
from babel.dates import format_date
import i18n_setup

# QDate is optional (only needed for desktop GUI)
try:
    from PySide6.QtCore import QDate
    QDATE_AVAILABLE = True
except ImportError:
    QDATE_AVAILABLE = False
    QDate = None


class DateContext:
    """Context object per operacions de data consolidades"""
    
    def __init__(self, date_obj: Union[datetime, 'QDate', None] = None):
        """
        Crea context de data a partir de datetime, QDate o data actual
        """
        if date_obj is None:
            self._date = datetime.now()
            self._qdate = QDate.currentDate() if QDATE_AVAILABLE else None
        elif hasattr(date_obj, 'toPython'):  # QDate
            self._qdate = date_obj if QDATE_AVAILABLE else None
            self._date = date_obj.toPython()
        elif hasattr(date_obj, 'dayOfWeek'):  # QDate sense toPython
            self._qdate = date_obj if QDATE_AVAILABLE else None
            self._date = datetime(date_obj.year(), date_obj.month(), date_obj.day())
        else:  # datetime
            self._date = date_obj
            self._qdate = QDate(date_obj.year, date_obj.month, date_obj.day) if QDATE_AVAILABLE else None
    
    @property
    def iso_format(self) -> str:
        """Data en format ISO: 'YYYY-MM-DD'"""
        return self._date.strftime("%Y-%m-%d")
    
    @property
    def catalan_format(self) -> str:
        """
        Data formatada internacionalitzada amb Babel.
        Ex: '15 de gener de 2024' (CA) / '15 de enero de 2024' (ES) / 'January 15, 2024' (EN)

        Utilitza Babel per formatar dates segons l'idioma actiu al sistema i18n.
        NOTA: No inclou dia de la setmana perquè depèn de l'idioma de l'XML
        """
        # Obtenir idioma actual del sistema i18n
        # L'idioma s'estableix via setup_translation() i es guarda a CURRENT_LANGUAGE
        idioma = i18n_setup.CURRENT_LANGUAGE

        # Babel format_date amb format 'long': "15 de gener de 2024"
        # Aquest format s'adapta automàticament a cada locale
        return format_date(self._date, format='long', locale=idioma)

    @property
    def full_format(self) -> str:
        """
        Data formatada amb dia de la setmana i en l'idioma actiu.
        Ex: 'Dimarts, 6 de gener de 2026' (CA) / 'Martes, 6 de enero de 2026' (ES)
        """
        idioma = i18n_setup.CURRENT_LANGUAGE
        text = format_date(self._date, format='full', locale=idioma)
        # Capitalitza la primera lletra per mantenir estil dels PDFs
        return text[:1].upper() + text[1:] if text else text

    @property
    def weekday_index(self) -> int:
        """
        Índex del dia de la setmana (0-6)
        0=Monday, 1=Tuesday, ..., 6=Sunday
        """
        return self._date.weekday()

    @property
    def dia_setmana(self) -> str:
        """
        DEPRECATED: Utilitza weekday_index i horari.get_dia_name() per obtenir el nom del dia de l'XML
        Retorna string buit.
        """
        return ""

    @property
    def qdate(self) -> Optional['QDate']:
        """QDate object per widgets Qt (None si PySide6 no està disponible)"""
        return self._qdate

    @property
    def datetime(self) -> datetime:
        """datetime object per càlculs"""
        return self._date

    @property
    def date(self):
        """Retorna datetime.date object (sempre un date, no datetime)"""
        if hasattr(self._date, 'date'):
            # És un datetime.datetime, retorna la part date
            return self._date.date()
        # Ja és un datetime.date
        return self._date
    
    def to_dict(self) -> dict:
        """Retorna diccionari amb tots els formats"""
        return {
            'iso': self.iso_format,
            'catalan': self.catalan_format,
            'dia_setmana': self.dia_setmana,
            'year': self._date.year,
            'month': self._date.month,
            'day': self._date.day
        }
    
    @classmethod
    def from_iso(cls, iso_date: str) -> 'DateContext':
        """Crea DateContext des de string ISO 'YYYY-MM-DD'"""
        try:
            date_obj = datetime.strptime(iso_date, "%Y-%m-%d")
            return cls(date_obj)
        except ValueError:
            return cls()  # Fallback a data actual
    
    def __str__(self) -> str:
        return self.catalan_format
    
    def __repr__(self) -> str:
        return f"DateContext({self.iso_format})"
