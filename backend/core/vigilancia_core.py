"""
Core business logic for vigilance management.
Contains all non-UI logic for exam vigilance assignment.
"""

import logging

log = logging.getLogger(__name__)

try:
    from i18n_setup import translate as _
except ImportError:

    def _(text):
        return text


class VigilanciaCore:
    """Core business logic for vigilance management"""

    def __init__(self):
        self.assignatures_config = None
        self.professors = []
        self.absents_actuals = {}
        self.horari_gestor = None
        self.alliberats_gestor = None
        self.grups_sense_classe = set()
        self.dia_actual = ""

    def set_config(
        self,
        assignatures_config,
        professors,
        absents_actuals,
        horari_gestor,
        alliberats_gestor,
        grups_sense_classe,
        dia_actual,
    ):
        """Set configuration data"""
        self.assignatures_config = assignatures_config
        self.professors = professors
        self.absents_actuals = absents_actuals
        self.horari_gestor = horari_gestor
        self.alliberats_gestor = alliberats_gestor
        self.grups_sense_classe = grups_sense_classe
        self.dia_actual = dia_actual

    def get_categoria_prioritat(self, tipus_activitat: str) -> int:
        """Retorna l'índex de categoria segons ORDRE_PRIORITATS."""
        from config.constants import ORDRE_PRIORITATS

        for i, categoria in enumerate(ORDRE_PRIORITATS):
            if tipus_activitat in categoria:
                return i
        return len(ORDRE_PRIORITATS)

    def is_activitat_auto_assignable(self, tipus_activitat: str) -> bool:
        """
        Retorna si un tipus d'activitat és assignable automàticament
        segons categories configurades i categories actives.
        """
        if not tipus_activitat:
            return False

        from config.constants import CATEGORIES_ACTIVES, ORDRE_PRIORITATS, PRIORITATS

        # Fallback defensiu si encara no s'han carregat categories des de BD.
        if not ORDRE_PRIORITATS:
            return tipus_activitat == "alliberat" or tipus_activitat in PRIORITATS

        categoria = self.get_categoria_prioritat(tipus_activitat)
        if categoria >= len(ORDRE_PRIORITATS):
            return False

        if categoria < len(CATEGORIES_ACTIVES) and not CATEGORIES_ACTIVES[categoria]:
            return False

        return True
