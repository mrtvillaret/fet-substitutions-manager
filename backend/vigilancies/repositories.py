"""Consultes de les vigilàncies d'examen.

Els repositoris no fan commit (el fa el servei, un cop per operació): només
flush, perquè les sessions no en fan soles (autoflush=False) i el que ve
després (refresca_cobertures) ha de veure el canvi."""

from datetime import datetime

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from dates import parse_date
from models import Vigilancia
from vigilancies.files import FilaVigilancia


class VigilanciaRepository:
    """Operacions CRUD per vigilàncies"""

    @staticmethod
    def get_by_date(db: Session, data: str) -> dict[str, list[FilaVigilancia]]:
        """Retorna totes les vigilàncies d'una data agrupades per nivell"""
        vigilancies = db.query(Vigilancia).filter(Vigilancia.data == parse_date(data)).order_by(Vigilancia.id).all()

        # Agrupar per nivell
        result = {}
        for vig in vigilancies:
            if vig.nivell not in result:
                result[vig.nivell] = []

            result[vig.nivell].append(
                FilaVigilancia(
                    id=str(vig.id),
                    hora=vig.hora,
                    tipus=vig.tipus,
                    grups=vig.grups,
                    aula=vig.aula,
                    vigilant=vig.vigilant or "",
                    comentaris=vig.comentaris or "",
                    nivell=vig.nivell,
                    ordre=vig.ordre,
                    updated_at=vig.updated_at.isoformat() if vig.updated_at else None,
                )
            )

        return result

    @staticmethod
    def compta_sense_nivell(db: Session, data_inici: str, data_final: str) -> int:
        """Vigilàncies antigues sense nivell dins d'un interval, inclosos els extrems."""
        return (
            db.query(Vigilancia)
            .filter(
                Vigilancia.data >= parse_date(data_inici),
                Vigilancia.data <= parse_date(data_final),
                func.trim(Vigilancia.nivell) == "",
            )
            .count()
        )

    @staticmethod
    def create(db: Session, data: str, vigilancia_data: dict) -> Vigilancia:
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
    def update_by_id(
        db: Session, data: str, vig_id: str, updates: dict, *, updated_at_esperat: str = None
    ) -> Vigilancia | None:
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

        if updated_at_esperat is not None:
            valors = {
                k: v
                for k, v in updates.items()
                if k in {"hora", "tipus", "grups", "aula", "vigilant", "comentaris", "nivell"}
            }
            if "vigilant" in valors:
                valors["vigilant"] = valors["vigilant"] or None
            if "hora" in valors and valors["hora"] != vig.hora:
                valors["ordre"] = VigilanciaRepository.seguent_ordre(db, data, valors["hora"])
            valors = {k: v for k, v in valors.items() if getattr(vig, k) != v}
            valors = valors or {"updated_at": vig.updated_at}
            afectades = (
                db.query(Vigilancia)
                .filter(
                    Vigilancia.id == vig.id,
                    Vigilancia.data == parse_date(data),
                    Vigilancia.updated_at == datetime.fromisoformat(updated_at_esperat),
                )
                .update(valors, synchronize_session=False)
            )
            if afectades != 1:
                return None
            db.refresh(vig)
            return vig

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
    def get_by_id(db: Session, data: str, vig_id: str) -> Vigilancia | None:
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
    def delete_by_id(db: Session, data: str, vig_id: str, *, updated_at_esperat: str = None) -> bool:
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

        if updated_at_esperat is not None:
            return (
                db.query(Vigilancia)
                .filter(
                    Vigilancia.id == vig.id,
                    Vigilancia.data == parse_date(data),
                    Vigilancia.updated_at == datetime.fromisoformat(updated_at_esperat),
                )
                .delete(synchronize_session="fetch")
                == 1
            )

        db.delete(vig)
        db.flush()
        return True

    @staticmethod
    def get_vigilants_per_hora(db: Session, data: str, hora: str) -> list[str]:
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
    def dates_entre(db: Session, inici: str, final: str) -> set:
        """Les dates (date) entre `inici` i `final`, incloses, que tenen alguna vigilància."""
        files = db.query(Vigilancia.data).filter(
            Vigilancia.data >= parse_date(inici), Vigilancia.data <= parse_date(final)
        )
        return {d for (d,) in files.distinct()}

    @staticmethod
    def grups_usats(db: Session) -> set:
        """Els grups (tal com estan desats, p. ex. «1-BAT-A,1-BAT-B») de totes les vigilàncies."""
        files = db.query(Vigilancia.grups).filter(Vigilancia.grups.isnot(None), Vigilancia.grups != "")
        return {g for (g,) in files.distinct()}

    @staticmethod
    def get_unique_tipus(db: Session) -> list[str]:
        """Retorna tots els tipus d'examen únics de totes les vigilàncies"""
        result = db.query(Vigilancia.tipus).distinct().all()
        tipus_list = [r[0] for r in result if r[0] and r[0].strip()]
        return sorted(tipus_list)

    @staticmethod
    def amb_vigilant(db: Session, data: str) -> list[Vigilancia]:
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
    def del_dia(db: Session, data: str) -> list[Vigilancia]:
        return db.query(Vigilancia).filter(Vigilancia.data == parse_date(data)).all()

    @staticmethod
    def hores_del_dia(db: Session, data: str) -> list[str]:
        """Les hores que tenen alguna vigilància aquell dia."""
        return [hora for (hora,) in db.query(Vigilancia.hora).filter(Vigilancia.data == parse_date(data)).distinct()]

    @staticmethod
    def esborra_del_dia(db: Session, data: str) -> int:
        return db.query(Vigilancia).filter(Vigilancia.data == parse_date(data)).delete(synchronize_session=False)

    @staticmethod
    def del_dia_dels_nivells(db: Session, data: str, nivells) -> list[Vigilancia]:
        """Les vigilàncies del dia d'aquests nivells (cap, sense nivells)."""
        filtre = Vigilancia.nivell.in_(list(nivells)) if nivells else False
        return db.query(Vigilancia).filter(Vigilancia.data == parse_date(data), filtre).all()

    @staticmethod
    def afegeix(db: Session, **camps) -> None:
        """Una vigilància nova tal com ve (l'ordre el posa qui crida)."""
        db.add(Vigilancia(**camps))

    @staticmethod
    def esborra(db: Session, vigilancia: Vigilancia) -> None:
        db.delete(vigilancia)

    @staticmethod
    def per_id(db: Session, vig_id: int) -> Vigilancia | None:
        return db.query(Vigilancia).filter(Vigilancia.id == vig_id).first()
