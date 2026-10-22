"""Consultes de les absències cobertes (taula professors_baixa).

Els repositoris no fan commit: el fa el servei, un cop per operació."""

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from models import AbsenciaCoberta


def _data(text: str):
    return datetime.strptime(text, "%Y-%m-%d").date()


def _fitxa(a: AbsenciaCoberta) -> Dict:
    return {
        "id": a.id,
        "professor": a.professor,
        "data_inici": a.data_inici.isoformat(),
        "data_final": a.data_final.isoformat(),
        "motiu": a.motiu or "",
    }


class AbsenciaCobertaRepository:
    @staticmethod
    def get_all(db: Session) -> List[Dict]:
        """Totes, per data d'inici"""
        return [_fitxa(a) for a in db.query(AbsenciaCoberta).order_by(AbsenciaCoberta.data_inici).all()]

    @staticmethod
    def get_by_id(db: Session, absencia_id: int) -> Optional[Dict]:
        a = db.query(AbsenciaCoberta).filter(AbsenciaCoberta.id == absencia_id).first()
        return _fitxa(a) if a else None

    @staticmethod
    def create(db: Session, professor: str, data_inici: str, data_final: str, motiu: str = "") -> int:
        nova = AbsenciaCoberta(
            professor=professor, data_inici=_data(data_inici), data_final=_data(data_final), motiu=motiu
        )
        db.add(nova)
        db.flush()
        return nova.id

    @staticmethod
    def update(db: Session, absencia_id: int, **camps) -> bool:
        """`camps`: professor, data_inici, data_final, motiu (els None no es toquen). False si no hi és."""
        a = db.query(AbsenciaCoberta).filter(AbsenciaCoberta.id == absencia_id).first()
        if not a:
            return False
        for camp, valor in camps.items():
            if valor is not None:
                setattr(a, camp, _data(valor) if camp in ("data_inici", "data_final") else valor)
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
