"""Les consultes dels recomptes."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from models import Substitucio, Vigilancia
from repositories import parse_date


def _fila_substitucio(sub: Substitucio) -> dict[str, Any]:
    """Una substitució sencera, amb els valors tal com són a la taula: les
    dates en text ISO i els moments de creació i de modificació com els desa
    SQLAlchemy (els recomptes treballen amb diccionaris de text)."""
    fila = {}
    for columna in Substitucio.__table__.columns:
        valor = getattr(sub, columna.key)
        if isinstance(valor, datetime):
            valor = valor.strftime("%Y-%m-%d %H:%M:%S.%f")
        elif isinstance(valor, date):
            valor = valor.isoformat()
        fila[columna.name] = valor
    return fila


class RecomptesRepository:
    @staticmethod
    def substitucions_entre(db: Session, data_inici: str, data_final: str) -> list[dict[str, Any]]:
        """Totes les substitucions de l'interval (els dos dies inclosos), per
        data i, dins de cada dia, en l'ordre en què es van crear (l'ordre
        decideix els empats dels rànquings de l'informe)."""
        files = (
            db.query(Substitucio)
            .filter(Substitucio.data >= parse_date(data_inici), Substitucio.data <= parse_date(data_final))
            .order_by(Substitucio.data, Substitucio.id)
            .all()
        )
        return [_fila_substitucio(sub) for sub in files]

    @staticmethod
    def _amb_substitut(db: Session, data_inici: str | None, data_final: str | None, *columnes):
        """Les files amb substitut de l'interval (sense una de les dates, no hi
        té límit), en el mateix ordre que substitucions_entre."""
        query = db.query(*columnes).filter(func.trim(func.coalesce(Substitucio.substitut, "")) != "")
        if data_inici:
            query = query.filter(Substitucio.data >= parse_date(data_inici))
        if data_final:
            query = query.filter(Substitucio.data <= parse_date(data_final))
        return query.order_by(Substitucio.data, Substitucio.id)

    @staticmethod
    def amb_substitut_entre(db: Session, data_inici: str | None, data_final: str | None) -> list[dict[str, Any]]:
        """Les files amb substitut de l'interval, senceres."""
        return [
            _fila_substitucio(sub)
            for sub in RecomptesRepository._amb_substitut(db, data_inici, data_final, Substitucio)
        ]

    @staticmethod
    def franges_amb_substitut_entre(
        db: Session, data_inici: str | None, data_final: str | None
    ) -> list[dict[str, Any]]:
        """Les mateixes files, només amb el substitut, la data (text ISO) i
        l'hora: el que cal per comptar-les per franja, sense llegir-les
        senceres."""
        files = RecomptesRepository._amb_substitut(
            db, data_inici, data_final, Substitucio.substitut, Substitucio.data, Substitucio.hora
        )
        return [{"substitut": s, "data": d.isoformat(), "hora": h} for s, d, h in files]

    @staticmethod
    def vigilancies_entre(db: Session, data_inici: str, data_final: str) -> list[dict[str, Any]]:
        """Les vigilàncies d'examen de l'interval: data (text ISO), hora i
        vigilant, per data, hora i ordre."""
        files = (
            db.query(Vigilancia)
            .filter(Vigilancia.data >= parse_date(data_inici), Vigilancia.data <= parse_date(data_final))
            .order_by(Vigilancia.data, Vigilancia.hora, Vigilancia.ordre, Vigilancia.id)
            .all()
        )
        return [{"data": v.data.isoformat(), "hora": v.hora, "vigilant": v.vigilant} for v in files]
