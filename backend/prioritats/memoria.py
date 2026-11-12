"""Càrrega pública de prioritats a memòria, sense dependències d'HTTP ni auth."""

from sqlalchemy.orm import Session

import config.constants as constants
from config.context import institucio_peticio
from prioritats.files import VigenciaNoSubstituir
from prioritats.repositories import AssignaturaPrioritatRepository, CategoriaPrioritatRepository, NoSubstituirRepository


def carrega_prioritats(db: Session) -> None:
    """Llegeix de la BD les prioritats i «No substituir» de la
    institució de la petició en curs (config.context) i les deixa a memòria
    (config.constants: ORDRE_PRIORITATS, CATEGORIES_ACTIVES, PRIORITATS i
    NO_SUBSTITUIR, amb la vigència per dates). Cal tornar-la a cridar
    després de qualsevol canvi."""
    categories = CategoriaPrioritatRepository.ordenades(db)
    assignatures = AssignaturaPrioritatRepository.totes(db)

    # Per categoria, en el seu ordre: les seves assignatures i si està activa
    ordre_prioritats = [[a.assignatura for a in assignatures if a.categoria_id == cat.id] for cat in categories]
    categories_actives = [cat.activa for cat in categories]
    prioritats = {a.assignatura: a.pes for a in assignatures}

    constants.desa_prioritats(
        institucio_peticio(),
        ORDRE_PRIORITATS=ordre_prioritats,
        CATEGORIES_ACTIVES=categories_actives,
        PRIORITATS=prioritats,
        NO_SUBSTITUIR=NoSubstituirRepository.vigencia(db),
    )


def no_substituir_a(data: str) -> frozenset[str]:
    """«No substituir» de la institució de la petició a `data` (de memòria,
    per al motor, que no té sessió de BD). La regla és la de
    `VigenciaNoSubstituir.a`, la mateixa que llegeix la BD."""
    return constants.dada_actual("NO_SUBSTITUIR", VigenciaNoSubstituir()).a(data)
