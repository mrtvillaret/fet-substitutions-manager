"""Absències, alliberaments i categories per assignar vigilants."""

from datetime import date

from sqlalchemy.orm import Session

from config import constants
from grups.lectures import AlliberatsDelDia
from horari.context import _get_institucio_actual
from prioritats.memoria import categoria_de_prioritat
from substitucions.repositories import SubstitucioRepository


class VigilanciaCore:
    def __init__(
        self,
        *,
        absents_actuals: dict[str, list[str]] | None = None,
        grups_sense_classe: dict[str, list[str]] | None = None,
    ):
        self.absents_actuals = absents_actuals or {}
        self.grups_sense_classe = grups_sense_classe or {}

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

        categoria = categoria_de_prioritat(tipus_activitat)
        if categoria >= len(constants.ORDRE_PRIORITATS):
            return False

        if categoria < len(constants.CATEGORIES_ACTIVES) and not constants.CATEGORIES_ACTIVES[categoria]:
            return False

        return True


def get_vigilancia_core(data: date, db: Session, institucio: str | None = None) -> VigilanciaCore:
    """Carrega les absències i els alliberaments del dia."""
    if not institucio:
        _get_institucio_actual()

    absents: dict[str, list[str]] = {}
    for sub in SubstitucioRepository.get_by_date(db, data):
        if not (sub.professor_absent and sub.hora) or sub.tipus_absencia in ("VIGILANCIA", "ENCADENADA"):
            continue
        hores = absents.setdefault(sub.professor_absent, [])
        if sub.hora not in hores:
            hores.append(sub.hora)

    return VigilanciaCore(
        absents_actuals=absents,
        grups_sense_classe=AlliberatsDelDia.get_by_date(db, data),
    )
