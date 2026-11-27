"""Consultes de les absències cobertes (taula professors_baixa).

Els repositoris no fan commit: el fa el servei, un cop per operació."""

from datetime import date
from typing import TypedDict, Unpack, cast

from sqlalchemy.orm import Session

from models import AbsenciaCoberta


class AbsenciaCobertaFitxa(TypedDict):
    id: int
    professor: str
    data_inici: date
    data_final: date
    motiu: str


class CanvisAbsenciaCoberta(TypedDict, total=False):
    professor: str | None
    data_inici: date | None
    data_final: date | None
    motiu: str | None


def _fitxa(a: AbsenciaCoberta) -> AbsenciaCobertaFitxa:
    return {
        "id": cast(int, a.id),
        "professor": cast(str, a.professor),
        "data_inici": a.data_inici,
        "data_final": a.data_final,
        "motiu": cast(str | None, a.motiu) or "",
    }


class AbsenciaCobertaRepository:
    @staticmethod
    def get_all(db: Session) -> list[AbsenciaCobertaFitxa]:
        """Totes, per data d'inici"""
        return [_fitxa(a) for a in db.query(AbsenciaCoberta).order_by(AbsenciaCoberta.data_inici).all()]

    @staticmethod
    def get_by_id(db: Session, absencia_id: int) -> AbsenciaCobertaFitxa | None:
        a = db.query(AbsenciaCoberta).filter(AbsenciaCoberta.id == absencia_id).first()
        return _fitxa(a) if a else None

    @staticmethod
    def create(db: Session, professor: str, data_inici: date, data_final: date, motiu: str = "") -> int:
        nova = AbsenciaCoberta(professor=professor, data_inici=data_inici, data_final=data_final, motiu=motiu)
        db.add(nova)
        db.flush()
        return cast(int, nova.id)

    @staticmethod
    def update(db: Session, absencia_id: int, **camps: Unpack[CanvisAbsenciaCoberta]) -> bool:
        """`camps`: professor, data_inici, data_final, motiu (els None no es toquen). False si no hi és."""
        a = db.query(AbsenciaCoberta).filter(AbsenciaCoberta.id == absencia_id).first()
        if not a:
            return False
        for camp, valor in camps.items():
            if valor is not None:
                setattr(a, camp, valor)
        db.flush()
        return True

    @staticmethod
    def delete(db: Session, absencia_id: int) -> bool:
        a = db.query(AbsenciaCoberta).filter(AbsenciaCoberta.id == absencia_id).first()
        if not a:
            return False
        db.delete(a)
        db.flush()
        return True
