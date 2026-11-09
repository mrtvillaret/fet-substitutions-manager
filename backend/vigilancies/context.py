"""
Core business logic for vigilance management.
Contains all non-UI logic for exam vigilance assignment.
"""

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from config import constants
from configuracio_examens.repositories import ConfiguracioExamenRepository
from grups.lectures import AlliberatsDelDia
from horari.context import _get_institucio_actual
from substitucions.context import get_gestors
from substitucions.repositories import SubstitucioRepository

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

        for i, categoria in enumerate(constants.ORDRE_PRIORITATS):
            if tipus_activitat in categoria:
                return i
        return len(constants.ORDRE_PRIORITATS)

    def is_activitat_auto_assignable(self, tipus_activitat: str) -> bool:
        """
        Retorna si un tipus d'activitat és assignable automàticament
        segons categories configurades i categories actives.
        """
        if not tipus_activitat:
            return False

        # Fallback defensiu si encara no s'han carregat categories des de BD.
        if not constants.ORDRE_PRIORITATS:
            return tipus_activitat == "alliberat" or tipus_activitat in constants.PRIORITATS

        categoria = self.get_categoria_prioritat(tipus_activitat)
        if categoria >= len(constants.ORDRE_PRIORITATS):
            return False

        if categoria < len(constants.CATEGORIES_ACTIVES) and not constants.CATEGORIES_ACTIVES[categoria]:
            return False

        return True


def get_vigilancia_core(data: str, db: Session = None, institucio: str = None, *, horari=None) -> VigilanciaCore:
    """Crea i configura VigilanciaCore per una data específica"""
    instit = institucio or _get_institucio_actual()

    core = VigilanciaCore()

    # Obtenir gestors
    _, horari, alliberats, _ = get_gestors(instit, data_iso=data, horari=horari)

    # Validar que tenim sessió de base de dades (obligatori)
    if not db:
        raise ValueError("get_vigilancia_core() requereix sessió de base de dades (db)")

    # Carregar configuració d'exàmens des de SQLite
    assignatures_config = ConfiguracioExamenRepository.get_all_as_dict(db)
    date_obj = datetime.strptime(data, "%Y-%m-%d")

    substitucions_data = SubstitucioRepository.get_by_date(db, data)
    absents = {}
    absents_tipus = {}

    for sub in substitucions_data:
        professor = sub.professor_absent
        hora = sub.hora
        tipus_abs = sub.tipus_absencia or "ABSENCIA"

        if tipus_abs in ["VIGILANCIA", "ENCADENADA"]:
            continue

        if professor and hora:
            if professor not in absents:
                absents[professor] = []
                absents_tipus[professor] = tipus_abs
            if hora not in absents[professor]:
                absents[professor].append(hora)

    # Grups sense classe (Des de SQLite)
    grups_sense_classe = AlliberatsDelDia.get_by_date(db, data)

    # Dia de la setmana
    weekday_idx = date_obj.weekday()
    dia_name = horari.get_dia_name(weekday_idx)

    # Configurar core
    core.set_config(
        assignatures_config=assignatures_config,
        professors=sorted(horari.professors),
        absents_actuals=absents,
        horari_gestor=horari,
        alliberats_gestor=alliberats,
        grups_sense_classe=grups_sense_classe,
        dia_actual=dia_name,
    )

    return core
