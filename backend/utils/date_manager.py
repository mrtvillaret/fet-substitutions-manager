"""
Gestor global de data singleton per calendari únic compartit
Assegura que totes les finestres/pestanyes comparteixen la mateixa data
"""
from PySide6.QtCore import QObject, Signal, QDate

try:
    from i18n_setup import translate as _
except ImportError:
    def _(text):
        return text


class DateManager(QObject):
    """
    Singleton que gestiona la data actual del sistema.
    Totes les finestres/pestanyes escolten els canvis de data.
    """

    # Señal emesa quan canvia la data
    date_changed = Signal(QDate)

    # Instància singleton
    _instance = None

    def __new__(cls):
        """Implementació del patró Singleton"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Inicialitza el gestor només un cop"""
        if self._initialized:
            return

        super().__init__()
        self._current_date = QDate.currentDate()
        self._initialized = True

    def set_date(self, date: QDate):
        """
        Canvia la data actual i notifica tots els listeners

        Args:
            date: Nova data a establir
        """
        if date != self._current_date and date.isValid():
            self._current_date = date
            self.date_changed.emit(date)

    def date(self) -> QDate:
        """
        Retorna la data actual

        Returns:
            QDate: Data actual del sistema
        """
        return self._current_date

    def reset_to_today(self):
        """Reseteja la data a avui"""
        self.set_date(QDate.currentDate())


# Instància global singleton
date_manager = DateManager()
