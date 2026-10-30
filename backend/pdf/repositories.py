"""Accés a dades necessari per generar PDF i informes."""

import json
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from models import AbsenciaCoberta, Substitucio
from repositories import ConfiguracioRepository, parse_date


class PreferenciesPdfRepository:
    CLAUS = {
        "substitucions": "pdf_prefs_substitucions",
        "vigilancies": "pdf_prefs_vigilancies",
        "vigilancies_interval": "pdf_prefs_vigilancies_interval",
    }
    DESCRIPCIONS = {
        "substitucions": "Preferències PDF de substitucions",
        "vigilancies": "Preferències PDF de vigilàncies",
        "vigilancies_interval": "Preferències PDF interval de vigilàncies",
    }

    @classmethod
    def get_all(cls, db: Session) -> dict[str, dict[str, Any] | None]:
        resultat = {}
        for nom, clau in cls.CLAUS.items():
            valor = ConfiguracioRepository.get(db, clau)
            resultat[nom] = json.loads(valor) if valor else None
        return resultat

    @classmethod
    def update(cls, db: Session, preferencies: dict[str, dict[str, Any] | None]) -> None:
        for nom, valor in preferencies.items():
            if valor is None:
                continue
            ConfiguracioRepository.set(
                db,
                cls.CLAUS[nom],
                json.dumps(valor),
                tipus="json",
                descripcio=cls.DESCRIPCIONS[nom],
            )


def _fila_substitucio(sub: Substitucio) -> dict[str, Any]:
    """Una substitució sencera, amb els valors tal com són a la taula: les
    dates en text ISO i els moments de creació i de modificació com els desa
    SQLAlchemy (els informes treballen amb diccionaris de text)."""
    fila = {}
    for columna in Substitucio.__table__.columns:
        valor = getattr(sub, columna.key)
        if isinstance(valor, datetime):
            valor = valor.strftime("%Y-%m-%d %H:%M:%S.%f")
        elif isinstance(valor, date):
            valor = valor.isoformat()
        fila[columna.name] = valor
    return fila


class InformesRepository:
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
    def compta_absencies_cobertes(db: Session, data_inici: str, data_final: str) -> int:
        """Absències cobertes que toquen l'interval (n'hi ha prou amb un dia)."""
        return (
            db.query(AbsenciaCoberta)
            .filter(
                AbsenciaCoberta.data_inici <= parse_date(data_final),
                AbsenciaCoberta.data_final >= parse_date(data_inici),
            )
            .count()
        )
