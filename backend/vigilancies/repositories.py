"""Consultes de les vigilàncies d'examen.

Els repositoris no fan commit (el fa el servei, un cop per operació): només
flush, perquè les sessions no en fan soles (autoflush=False) i el que ve
després (refresca_cobertures) ha de veure el canvi."""

from datetime import date, datetime

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from models import Vigilancia
from vigilancies.files import FilaVigilancia

# Els camps que es poden editar d'una vigilància
CAMPS_EDITABLES = ("hora", "tipus", "grups", "aula", "vigilant", "comentaris", "nivell")


class VigilanciaRepository:
    """Operacions CRUD per vigilàncies"""

    @staticmethod
    def get_by_date(db: Session, data: date) -> dict[str, list[FilaVigilancia]]:
        """Retorna totes les vigilàncies d'una data agrupades per nivell"""
        vigilancies = db.query(Vigilancia).filter(Vigilancia.data == data).order_by(Vigilancia.id).all()

        # Agrupar per nivell
        result = {}
        for vig in vigilancies:
            if vig.nivell not in result:
                result[vig.nivell] = []

            result[vig.nivell].append(
                FilaVigilancia(
                    id=str(vig.id),
                    data=vig.data,
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
    def compta_sense_nivell(db: Session, data_inici: date, data_final: date) -> int:
        """Vigilàncies antigues sense nivell dins d'un interval, inclosos els extrems."""
        return (
            db.query(Vigilancia)
            .filter(
                Vigilancia.data >= data_inici,
                Vigilancia.data <= data_final,
                func.trim(Vigilancia.nivell) == "",
            )
            .count()
        )

    @staticmethod
    def create(db: Session, data: date, vigilancia_data: dict) -> Vigilancia:
        """Crea una nova vigilància"""
        vig = Vigilancia(
            data=data,
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
        db: Session, data: date, vig_id: int | str, updates: dict, *, updated_at_esperat: str = None
    ) -> Vigilancia | None:
        """Actualitza la vigilància `vig_id` del dia `data` amb els camps
        editables d'`updates` que canvien (vigilant buit: sense vigilant; una
        hora nova porta la fila al final del bloc de l'hora nova). Amb
        `updated_at_esperat`, només si la fila encara té aquesta versió (si no,
        None); sense canvis, la versió no es mou."""
        vig = VigilanciaRepository.get_by_id(db, data, vig_id)
        if not vig:
            return None

        valors = {k: v for k, v in updates.items() if k in CAMPS_EDITABLES}
        if "vigilant" in valors:
            valors["vigilant"] = valors["vigilant"] or None
        if "hora" in valors and valors["hora"] != vig.hora:
            valors["ordre"] = VigilanciaRepository.seguent_ordre(db, data, valors["hora"])
        valors = {k: v for k, v in valors.items() if getattr(vig, k) != v}

        if updated_at_esperat is None:
            for camp, valor in valors.items():
                setattr(vig, camp, valor)
            db.flush()
        else:
            afectades = (
                db.query(Vigilancia)
                .filter(
                    Vigilancia.id == vig.id,
                    Vigilancia.data == data,
                    Vigilancia.updated_at == datetime.fromisoformat(updated_at_esperat),
                )
                .update(valors or {"updated_at": vig.updated_at}, synchronize_session=False)
            )
            if afectades != 1:
                return None
        db.refresh(vig)
        return vig

    @staticmethod
    def get_by_id(db: Session, data: date, vig_id: int | str) -> Vigilancia | None:
        """La vigilància `vig_id`, si és del dia `data`."""
        return db.query(Vigilancia).filter(and_(Vigilancia.id == vig_id, Vigilancia.data == data)).first()

    @staticmethod
    def delete_by_id(db: Session, data: date, vig_id: int, *, updated_at_esperat: str = None) -> bool:
        """Esborra la vigilància `vig_id` del dia `data`."""
        vig = VigilanciaRepository.get_by_id(db, data, vig_id)
        if not vig:
            return False

        if updated_at_esperat is not None:
            return (
                db.query(Vigilancia)
                .filter(
                    Vigilancia.id == vig.id,
                    Vigilancia.data == data,
                    Vigilancia.updated_at == datetime.fromisoformat(updated_at_esperat),
                )
                .delete(synchronize_session="fetch")
                == 1
            )

        db.delete(vig)
        db.flush()
        return True

    @staticmethod
    def get_vigilants_per_hora(db: Session, data: date, hora: str) -> list[str]:
        """Retorna vigilants assignats a una hora concreta"""
        vigilancies = (
            db.query(Vigilancia)
            .filter(
                and_(
                    Vigilancia.data == data,
                    Vigilancia.hora == hora,
                    Vigilancia.vigilant.isnot(None),
                    Vigilancia.vigilant != "",
                )
            )
            .all()
        )

        return [v.vigilant for v in vigilancies]

    @staticmethod
    def dates_entre(db: Session, inici: date, final: date) -> set[date]:
        """Les dates (date) entre `inici` i `final`, incloses, que tenen alguna vigilància."""
        files = db.query(Vigilancia.data).filter(Vigilancia.data >= inici, Vigilancia.data <= final)
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
    def amb_vigilant(db: Session, data: date) -> list[Vigilancia]:
        """Les vigilàncies del dia que tenen vigilant."""
        return (
            db.query(Vigilancia)
            .filter(
                and_(
                    Vigilancia.data == data,
                    Vigilancia.vigilant.isnot(None),
                    Vigilancia.vigilant != "",
                )
            )
            .all()
        )

    @staticmethod
    def seguent_ordre(db: Session, data: date, hora: str) -> int:
        """L'ordre d'una fila que va al final del bloc d'una hora."""
        maxim = db.query(func.max(Vigilancia.ordre)).filter(Vigilancia.data == data, Vigilancia.hora == hora).scalar()
        return 0 if maxim is None else maxim + 1

    @staticmethod
    def del_dia(db: Session, data: date) -> list[Vigilancia]:
        return db.query(Vigilancia).filter(Vigilancia.data == data).all()

    @staticmethod
    def hores_del_dia(db: Session, data: date) -> list[str]:
        """Les hores que tenen alguna vigilància aquell dia."""
        return [hora for (hora,) in db.query(Vigilancia.hora).filter(Vigilancia.data == data).distinct()]

    @staticmethod
    def esborra_del_dia(db: Session, data: date) -> int:
        return db.query(Vigilancia).filter(Vigilancia.data == data).delete(synchronize_session=False)

    @staticmethod
    def del_dia_dels_nivells(db: Session, data: date, nivells) -> list[Vigilancia]:
        """Les vigilàncies del dia d'aquests nivells (cap, sense nivells)."""
        filtre = Vigilancia.nivell.in_(list(nivells)) if nivells else False
        return db.query(Vigilancia).filter(Vigilancia.data == data, filtre).all()

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
