"""Consultes de les prioritats (categories i assignatures) i de «No substituir».

Els repositoris no fan commit: el fa el servei, un cop per operació (com a
auth/repositories.py)."""

from typing import Dict, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from models import AssignaturaPrioritat, CategoriaPrioritat, NoSubstituir


class CategoriaPrioritatRepository:
    """Categories de prioritat"""

    @staticmethod
    def ordenades(db: Session) -> List[CategoriaPrioritat]:
        return db.query(CategoriaPrioritat).order_by(CategoriaPrioritat.ordre).all()

    @staticmethod
    def get_all(db: Session) -> List[Dict]:
        """Totes les categories ordenades per ordre"""
        return [
            {"id": c.id, "nom": c.nom, "ordre": c.ordre, "activa": c.activa}
            for c in CategoriaPrioritatRepository.ordenades(db)
        ]

    @staticmethod
    def create(db: Session, nom: str, ordre: int = None, activa: bool = True) -> int:
        """Crea una categoria (sense ordre, al final: l'ordre és únic, i comptar
        les que hi ha podia donar el d'una que ja existeix)"""
        if ordre is None:
            ordre = (db.query(func.max(CategoriaPrioritat.ordre)).scalar() or 0) + 1
        nova_cat = CategoriaPrioritat(nom=nom, ordre=ordre, activa=activa)
        db.add(nova_cat)
        db.flush()
        return nova_cat.id

    @staticmethod
    def esborra_totes(db: Session) -> None:
        """Esborra totes les categories i les seves assignatures."""
        db.query(AssignaturaPrioritat).delete()
        db.query(CategoriaPrioritat).delete()
        db.flush()


class AssignaturaPrioritatRepository:
    """Assignatures dins de les categories de prioritat"""

    @staticmethod
    def totes(db: Session) -> List[AssignaturaPrioritat]:
        return db.query(AssignaturaPrioritat).all()

    @staticmethod
    def get_all(db: Session) -> List[Dict]:
        """Totes les assignatures, en l'ordre de la categoria i el seu"""
        assignatures = (
            db.query(AssignaturaPrioritat)
            .join(CategoriaPrioritat)
            .order_by(CategoriaPrioritat.ordre, AssignaturaPrioritat.ordre)
            .all()
        )
        return [
            {
                "id": a.id,
                "assignatura": a.assignatura,
                "categoria_id": a.categoria_id,
                "pes": a.pes,
                "ordre": a.ordre,
                "auto_assignada": a.auto_assignada if hasattr(a, "auto_assignada") else False,
            }
            for a in assignatures
        ]

    @staticmethod
    def create(
        db: Session, assignatura: str, categoria_id: int, pes: int = 1, ordre: int = None, auto_assignada: bool = False
    ) -> int:
        """Crea una assignatura dins d'una categoria (sense ordre, al final)"""
        if ordre is None:
            darrer = (
                db.query(func.max(AssignaturaPrioritat.ordre))
                .filter(AssignaturaPrioritat.categoria_id == categoria_id)
                .scalar()
            )
            ordre = 0 if darrer is None else darrer + 1
        nova_assig = AssignaturaPrioritat(
            assignatura=assignatura, categoria_id=categoria_id, pes=pes, ordre=ordre, auto_assignada=auto_assignada
        )
        db.add(nova_assig)
        db.flush()
        return nova_assig.id


class NoSubstituirRepository:
    """Activitats que no se substitueixen"""

    @staticmethod
    def get_all(db: Session) -> List[str]:
        return [a.assignatura for a in db.query(NoSubstituir).all()]

    @staticmethod
    def create(db: Session, assignatura: str) -> int:
        nova = NoSubstituir(assignatura=assignatura)
        db.add(nova)
        db.flush()
        return nova.id

    @staticmethod
    def delete(db: Session, assignatura: str) -> bool:
        """False si no hi era."""
        assig = db.query(NoSubstituir).filter(NoSubstituir.assignatura == assignatura).first()
        if not assig:
            return False
        db.delete(assig)
        db.flush()
        return True
