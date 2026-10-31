"""Accés a dades necessari per generar PDF i informes."""

import json
from typing import Any

from sqlalchemy.orm import Session

from models import AbsenciaCoberta
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


class InformesRepository:
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
