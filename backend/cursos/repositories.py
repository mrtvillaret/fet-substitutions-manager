"""Consultes dels cursos acadèmics.

Els repositoris no fan commit: el fa qui crida, un cop per operació."""

from datetime import date, timedelta
from typing import List, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from models import Curs
from repositories import parse_date


class CursRepository:
    """Cursos acadèmics: seqüència CONTÍGUA de períodes (mateix patró que xml_versions).

    Només es defineix `data_inici`. `data_fi` es deriva sempre: el curs acaba el dia
    abans que comenci el següent, i l'últim queda obert (`data_fi = NULL`). Així tota
    data pertany exactament a un curs i no cal cap flag d'"actiu".
    """

    @staticmethod
    def _rechain(db: Session) -> None:
        """Recalcula data_fi de tots els cursos perquè la seqüència sigui contígua."""
        cursos = db.query(Curs).order_by(Curs.data_inici.asc()).all()
        for i, curs in enumerate(cursos):
            seguent = cursos[i + 1] if i + 1 < len(cursos) else None
            nova_fi = (seguent.data_inici - timedelta(days=1)) if seguent else None
            if curs.data_fi != nova_fi:
                curs.data_fi = nova_fi
        db.flush()

    @staticmethod
    def list_all(db: Session) -> List[Curs]:
        return db.query(Curs).order_by(Curs.data_inici.desc()).all()

    @staticmethod
    def get(db: Session, curs_id: int) -> Optional[Curs]:
        return db.query(Curs).filter(Curs.id == curs_id).first()

    @staticmethod
    def comenca_el(db: Session, data_inici: date, excepte: int = None) -> bool:
        """Si algun curs (que no sigui `excepte`) comença aquest dia."""
        q = db.query(Curs).filter(Curs.data_inici == data_inici)
        if excepte is not None:
            q = q.filter(Curs.id != excepte)
        return q.first() is not None

    @staticmethod
    def get_for_date(db: Session, data: str) -> Optional[Curs]:
        """Curs al qual pertany una data. Cap si la data és anterior al primer curs."""
        data_obj = parse_date(data)
        return (
            db.query(Curs)
            .filter(and_(Curs.data_inici <= data_obj, or_(Curs.data_fi.is_(None), Curs.data_fi >= data_obj)))
            .order_by(Curs.data_inici.desc())
            .first()
        )

    @staticmethod
    def create(db: Session, nom: str, data_inici: date) -> Curs:
        nou = Curs(nom=nom, data_inici=data_inici, data_fi=None)
        db.add(nou)
        db.flush()
        CursRepository._rechain(db)
        return nou

    @staticmethod
    def update(db: Session, curs_id: int, nom: str, data_inici: date) -> Optional[Curs]:
        curs = CursRepository.get(db, curs_id)
        if not curs:
            return None
        curs.nom = nom
        curs.data_inici = data_inici
        db.flush()
        CursRepository._rechain(db)
        return curs

    @staticmethod
    def delete(db: Session, curs_id: int) -> bool:
        curs = CursRepository.get(db, curs_id)
        if not curs:
            return False
        db.delete(curs)
        db.flush()
        CursRepository._rechain(db)
        return True
