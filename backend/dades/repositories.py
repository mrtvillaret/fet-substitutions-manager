"""Consultes de la governança de dades: el que hi ha i s'esborra d'un interval
de dates, i els noms dels professors a totes les taules on surten.

Els repositoris no fan commit: el fa qui crida, un cop per operació."""

from datetime import date
from typing import Dict, Iterable, List, Optional, Set

from sqlalchemy.orm import Session

from models import (
    AbsenciaCoberta,
    Configuracio,
    ExamCostProfessor,
    GrupAlliberat,
    Professor,
    Substitucio,
    Vigilancia,
    XMLVersion,
)


class PurgaRepository:
    """Les files d'un interval [data_inici, data_final] (inclòs)."""

    @staticmethod
    def _per_interval(db: Session, data_inici: date, data_final: date) -> Dict:
        # Substitucions, vigilàncies i grups alliberats, per la columna `data`;
        # les absències cobertes que se solapen amb l'interval
        return {
            "substitucions": db.query(Substitucio).filter(
                Substitucio.data >= data_inici, Substitucio.data <= data_final
            ),
            "vigilancies": db.query(Vigilancia).filter(Vigilancia.data >= data_inici, Vigilancia.data <= data_final),
            "grups_alliberats": db.query(GrupAlliberat).filter(
                GrupAlliberat.data >= data_inici, GrupAlliberat.data <= data_final
            ),
            "baixes": db.query(AbsenciaCoberta).filter(
                AbsenciaCoberta.data_inici <= data_final, AbsenciaCoberta.data_final >= data_inici
            ),
        }

    @staticmethod
    def compta(db: Session, data_inici: date, data_final: date) -> Dict[str, int]:
        return {nom: q.count() for nom, q in PurgaRepository._per_interval(db, data_inici, data_final).items()}

    @staticmethod
    def esborra(db: Session, data_inici: date, data_final: date) -> Dict[str, int]:
        return {
            nom: q.delete(synchronize_session=False)
            for nom, q in PurgaRepository._per_interval(db, data_inici, data_final).items()
        }

    @staticmethod
    def absencies_cobertes(db: Session, data_inici: date, data_final: date) -> List[AbsenciaCoberta]:
        """Les que toquen alguna data de l'interval, per data d'inici."""
        return (
            db.query(AbsenciaCoberta)
            .filter(AbsenciaCoberta.data_inici <= data_final, AbsenciaCoberta.data_final >= data_inici)
            .order_by(AbsenciaCoberta.data_inici)
            .all()
        )

    @staticmethod
    def versions_xml(db: Session, ids: Iterable[int]) -> List[XMLVersion]:
        return db.query(XMLVersion).filter(XMLVersion.id.in_(list(ids))).all()

    @staticmethod
    def paths_xml_excepte(db: Session, ids: Iterable[int]) -> Set[str]:
        """Els fitxers de les versions que es queden."""
        return {v.path for v in db.query(XMLVersion).filter(~XMLVersion.id.in_(list(ids))).all()}

    @staticmethod
    def canvia_configuracio(db: Session, clau: str, valor: str) -> None:
        # Sense ConfiguracioRepository.set, que fa commit: tot va en el commit de la purga
        db.query(Configuracio).filter(Configuracio.clau == clau).update(
            {Configuracio.valor: valor}, synchronize_session=False
        )

    @staticmethod
    def esborra_configuracio(db: Session, clau: str) -> None:
        db.query(Configuracio).filter(Configuracio.clau == clau).delete(synchronize_session=False)


class ProfessorsRepository:
    """Els professors de la BD (l'històric) i el seu nom a tots els registres."""

    @staticmethod
    def llista(db: Session) -> List[Professor]:
        """Actius primer, i per nom."""
        return db.query(Professor).order_by(Professor.actiu.desc(), Professor.nom).all()

    @staticmethod
    def get_by_nom(db: Session, nom: str) -> Optional[Professor]:
        return db.query(Professor).filter(Professor.nom == nom).first()

    @staticmethod
    def reanomena_registres(db: Session, nom_actual: str, nom_nou: str) -> Dict[str, int]:
        """Canvia el nom a totes les taules on surt; quantes files de cada."""
        return {
            "substitucions_absent": db.query(Substitucio)
            .filter(Substitucio.professor_absent == nom_actual)
            .update({Substitucio.professor_absent: nom_nou}, synchronize_session=False),
            "substitucions_substitut": db.query(Substitucio)
            .filter(Substitucio.substitut == nom_actual)
            .update({Substitucio.substitut: nom_nou}, synchronize_session=False),
            "vigilancies": db.query(Vigilancia)
            .filter(Vigilancia.vigilant == nom_actual)
            .update({Vigilancia.vigilant: nom_nou}, synchronize_session=False),
            "baixes": db.query(AbsenciaCoberta)
            .filter(AbsenciaCoberta.professor == nom_actual)
            .update({AbsenciaCoberta.professor: nom_nou}, synchronize_session=False),
            "costos_examens": db.query(ExamCostProfessor)
            .filter(ExamCostProfessor.professor == nom_actual)
            .update({ExamCostProfessor.professor: nom_nou}, synchronize_session=False),
        }
