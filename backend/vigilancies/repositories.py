"""Consultes de les vigilàncies d'examen.

Els repositoris no fan commit (el fa el servei, un cop per operació): només
flush, perquè les sessions no en fan soles (autoflush=False) i el que ve
després (refresca_cobertures) ha de veure el canvi."""

from typing import Dict, List, Optional

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from models import Vigilancia
from repositories import parse_date


class VigilanciaRepository:
    """Operacions CRUD per vigilàncies"""

    @staticmethod
    def get_by_date(db: Session, data: str) -> Dict[str, List[Dict]]:
        """Retorna totes les vigilàncies d'una data agrupades per nivell"""
        vigilancies = db.query(Vigilancia).filter(Vigilancia.data == parse_date(data)).order_by(Vigilancia.id).all()

        # Agrupar per nivell
        result = {}
        for vig in vigilancies:
            if vig.nivell not in result:
                result[vig.nivell] = []

            result[vig.nivell].append(
                {
                    "id": str(vig.id),  # Utilitzar ID real de la base de dades
                    "db_id": vig.id,  # També incloure per compatibilitat
                    "hora": vig.hora,
                    "tipus": vig.tipus,
                    "grups": vig.grups,
                    "aula": vig.aula,
                    "vigilant": vig.vigilant or "",
                    "comentaris": vig.comentaris or "",
                    "nivell": vig.nivell,
                    "ordre": vig.ordre,
                    "updated_at": vig.updated_at.isoformat() if vig.updated_at else None,
                }
            )

        return result

    @staticmethod
    def create(db: Session, data: str, vigilancia_data: Dict) -> Vigilancia:
        """Crea una nova vigilància"""
        vig = Vigilancia(
            data=parse_date(data),
            hora=vigilancia_data["hora"],
            tipus=vigilancia_data["tipus"],
            grups=vigilancia_data["grups"],
            aula=vigilancia_data["aula"],
            vigilant=vigilancia_data.get("vigilant") or None,
            comentaris=vigilancia_data.get("comentaris", ""),
            nivell=vigilancia_data["nivell"],
            # Una fila nova va al final del bloc de la seva hora
            ordre=VigilanciaRepository.seguent_ordre(db, data, vigilancia_data["hora"]),
        )
        db.add(vig)
        db.flush()
        db.refresh(vig)
        return vig

    @staticmethod
    def update_by_id(db: Session, data: str, vig_id: str, updates: Dict) -> Optional[Vigilancia]:
        """
        Actualitza una vigilància pel seu ID (pot ser integer o compost)

        Args:
            vig_id: Pot ser:
                - Integer (ID real de la BD): "123"
                - Compost (legacy): "08:00|1-BATX|0"
        """
        vig = None

        # Intentar parsejar com a integer primer (ID real de la BD)
        try:
            db_id = int(vig_id)
            vig = db.query(Vigilancia).filter(and_(Vigilancia.id == db_id, Vigilancia.data == parse_date(data))).first()
        except ValueError:
            # No és un integer, provar amb format compost
            parts = vig_id.split("|")
            if len(parts) != 3:
                return None

            hora, nivell, index_str = parts
            try:
                index = int(index_str)
            except ValueError:
                return None

            # Buscar vigilància amb index
            vigilancies = (
                db.query(Vigilancia)
                .filter(and_(Vigilancia.data == parse_date(data), Vigilancia.hora == hora, Vigilancia.nivell == nivell))
                .order_by(Vigilancia.id)
                .all()
            )

            if index >= len(vigilancies):
                return None

            vig = vigilancies[index]

        if not vig:
            return None

        # Actualitzar camps
        if "hora" in updates and updates["hora"] != vig.hora:
            # Canviar d'hora és canviar la dada: la fila va al final del bloc de l'hora nova
            vig.ordre = VigilanciaRepository.seguent_ordre(db, data, updates["hora"])
            vig.hora = updates["hora"]
        if "tipus" in updates:
            vig.tipus = updates["tipus"]
        if "grups" in updates:
            vig.grups = updates["grups"]
        if "aula" in updates:
            vig.aula = updates["aula"]
        if "vigilant" in updates:
            vig.vigilant = updates["vigilant"] or None
        if "comentaris" in updates:
            vig.comentaris = updates["comentaris"]
        if "nivell" in updates:
            vig.nivell = updates["nivell"]

        db.flush()
        db.refresh(vig)
        return vig

    @staticmethod
    def get_by_id(db: Session, data: str, vig_id: str) -> Optional[Vigilancia]:
        """Retorna una vigilància pel seu ID (integer o compost)."""
        vig = None

        try:
            db_id = int(vig_id)
            vig = db.query(Vigilancia).filter(and_(Vigilancia.id == db_id, Vigilancia.data == parse_date(data))).first()
        except ValueError:
            parts = vig_id.split("|")
            if len(parts) != 3:
                return None

            hora, nivell, index_str = parts
            try:
                index = int(index_str)
            except ValueError:
                return None

            vigilancies = (
                db.query(Vigilancia)
                .filter(and_(Vigilancia.data == parse_date(data), Vigilancia.hora == hora, Vigilancia.nivell == nivell))
                .order_by(Vigilancia.id)
                .all()
            )

            if index >= len(vigilancies):
                return None

            vig = vigilancies[index]

        return vig

    @staticmethod
    def delete_by_id(db: Session, data: str, vig_id: str) -> bool:
        """
        Elimina una vigilància pel seu ID (pot ser integer o compost)

        Args:
            vig_id: Pot ser:
                - Integer (ID real de la BD): "123"
                - Compost (legacy): "08:00|1-BATX|0"
        """
        vig = None

        # Intentar parsejar com a integer primer (ID real de la BD)
        try:
            db_id = int(vig_id)
            vig = db.query(Vigilancia).filter(and_(Vigilancia.id == db_id, Vigilancia.data == parse_date(data))).first()
        except ValueError:
            # No és un integer, provar amb format compost
            parts = vig_id.split("|")
            if len(parts) != 3:
                return False

            hora, nivell, index_str = parts
            try:
                index = int(index_str)
            except ValueError:
                return False

            # Buscar vigilància amb index
            vigilancies = (
                db.query(Vigilancia)
                .filter(and_(Vigilancia.data == parse_date(data), Vigilancia.hora == hora, Vigilancia.nivell == nivell))
                .order_by(Vigilancia.id)
                .all()
            )

            if index >= len(vigilancies):
                return False

            vig = vigilancies[index]

        if not vig:
            return False

        db.delete(vig)
        db.flush()
        return True

    @staticmethod
    def get_vigilants_per_hora(db: Session, data: str, hora: str) -> List[str]:
        """Retorna vigilants assignats a una hora concreta"""
        vigilancies = (
            db.query(Vigilancia)
            .filter(
                and_(
                    Vigilancia.data == parse_date(data),
                    Vigilancia.hora == hora,
                    Vigilancia.vigilant.isnot(None),
                    Vigilancia.vigilant != "",
                )
            )
            .all()
        )

        return [v.vigilant for v in vigilancies]

    @staticmethod
    def get_unique_tipus(db: Session) -> List[str]:
        """Retorna tots els tipus d'examen únics de totes les vigilàncies"""
        result = db.query(Vigilancia.tipus).distinct().all()
        tipus_list = [r[0] for r in result if r[0] and r[0].strip()]
        return sorted(tipus_list)

    @staticmethod
    def amb_vigilant(db: Session, data: str) -> List[Vigilancia]:
        """Les vigilàncies del dia que tenen vigilant (ni buit ni el text del desplegable)."""
        return (
            db.query(Vigilancia)
            .filter(
                and_(
                    Vigilancia.data == parse_date(data),
                    Vigilancia.vigilant.isnot(None),
                    Vigilancia.vigilant != "",
                    Vigilancia.vigilant != "-- selecciona vigilant --",
                )
            )
            .all()
        )

    @staticmethod
    def seguent_ordre(db: Session, data: str, hora: str) -> int:
        """L'ordre d'una fila que va al final del bloc d'una hora."""
        maxim = (
            db.query(func.max(Vigilancia.ordre))
            .filter(Vigilancia.data == parse_date(data), Vigilancia.hora == hora)
            .scalar()
        )
        return 0 if maxim is None else maxim + 1

    @staticmethod
    def del_dia(db: Session, data: str) -> List[Vigilancia]:
        return db.query(Vigilancia).filter(Vigilancia.data == parse_date(data)).all()
