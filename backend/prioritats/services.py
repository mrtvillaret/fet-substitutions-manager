"""Regles de les prioritats: les categories i les assignatures (amb el seu pes)
que fan servir el motor de substitucions i el de vigilàncies per triar
substituts, «No substituir», i la seva càrrega a memòria (config.constants)."""

from typing import Optional

from sqlalchemy.orm import Session

import config.constants as constants
from config.context import institucio_peticio
from errors_domini import Conflicte, NoTrobat, NoValid
from prioritats.repositories import AssignaturaPrioritatRepository, CategoriaPrioritatRepository, NoSubstituirRepository


def carrega_prioritats(db: Session) -> None:
    """Llegeix de la BD les prioritats i «No substituir» de la
    institució de la petició en curs (config.context) i les deixa a memòria
    (config.constants: ORDRE_PRIORITATS, CATEGORIES_ACTIVES, PRIORITATS,
    NO_SUBST, GENERA_ENCADENADES). Cal tornar-la a cridar
    després de qualsevol canvi."""
    categories = CategoriaPrioritatRepository.ordenades(db)
    assignatures = AssignaturaPrioritatRepository.totes(db)

    # Per categoria, en el seu ordre: les seves assignatures i si està activa
    ordre_prioritats = [[a.assignatura for a in assignatures if a.categoria_id == cat.id] for cat in categories]
    categories_actives = [cat.activa for cat in categories]
    prioritats = {a.assignatura: a.pes for a in assignatures}
    no_subst = set(NoSubstituirRepository.get_all(db))

    constants.desa_prioritats(
        institucio_peticio(),
        ORDRE_PRIORITATS=ordre_prioritats,
        CATEGORIES_ACTIVES=categories_actives,
        PRIORITATS=prioritats,
        NO_SUBST=no_subst,
        GENERA_ENCADENADES=[tipus for tipus in prioritats if tipus not in no_subst],
    )


def llista_categories(db: Session) -> list[dict]:
    return CategoriaPrioritatRepository.get_all(db)


def llista_assignatures(db: Session) -> list[dict]:
    return AssignaturaPrioritatRepository.get_all(db)


def desa_totes(db: Session, ordre_categories: list[list[str]], pesos: dict, categories_actives: list[bool]) -> None:
    """Substitueix totes les categories i assignatures per les d'`ordre_categories`
    (una llista d'assignatures per categoria, en ordre de prioritat). Les
    llistes buides es salten. La categoria es diu com la seva assignatura o,
    si en té més, com les dues primeres; sense estat a `categories_actives`,
    és activa, i les assignatures d'una categoria activa s'assignen soles."""
    try:
        CategoriaPrioritatRepository.esborra_totes(db)
        for cat_ordre, assignatures in enumerate(ordre_categories):
            if not assignatures:
                continue
            nom = assignatures[0] if len(assignatures) == 1 else ", ".join(assignatures[:2])
            activa = categories_actives[cat_ordre] if cat_ordre < len(categories_actives) else True
            cat_id = CategoriaPrioritatRepository.create(db, nom, ordre=cat_ordre, activa=activa)
            for assig_ordre, assignatura in enumerate(assignatures):
                AssignaturaPrioritatRepository.create(
                    db, assignatura, cat_id, pes=pesos.get(assignatura, 1), ordre=assig_ordre, auto_assignada=activa
                )
        db.commit()
    except Exception:
        db.rollback()
        raise
    carrega_prioritats(db)


def llista_no_substituir(db: Session) -> list[str]:
    return NoSubstituirRepository.get_all(db)


def afegeix_no_substituir(db: Session, assignatura: Optional[str]) -> int:
    """El text buit s'accepta (hi ha activitats sense nom a l'XML)."""
    if not assignatura and assignatura != "":
        raise NoValid("Assignatura requerida", codi="assignatura_requerida")
    if assignatura in NoSubstituirRepository.get_all(db):
        raise Conflicte(
            "L'assignatura ja és a «No substituir»", codi="no_substituir_repetida", params={"assignatura": assignatura}
        )
    no_subst_id = NoSubstituirRepository.create(db, assignatura)
    db.commit()
    carrega_prioritats(db)
    return no_subst_id


def treu_no_substituir(db: Session, assignatura: str) -> None:
    if not NoSubstituirRepository.delete(db, assignatura):
        raise NoTrobat("Assignatura no trobada", codi="assignatura_no_trobada")
    db.commit()
    carrega_prioritats(db)
