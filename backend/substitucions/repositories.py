"""Repositori de substitucions."""

from datetime import date, datetime, timedelta

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from cursos.repositories import CursRepository
from models import Substitucio
from substitucions.files import FilaSubstitucio

# Sense cap curs definit, fins on mira enrere l'historial de la quota. Amb curs,
# només es compta el curs del dia (a cada curs nou la quota torna a començar).
HISTORIAL_QUOTA = timedelta(days=2 * 365)


class SubstitucioRepository:
    """Operacions CRUD per substitucions"""

    @staticmethod
    def get_by_date(db: Session, data: date) -> list[FilaSubstitucio]:
        """Totes les files del dia, en el mateix ordre i amb els mateixos buits."""
        subs = db.query(Substitucio).filter(Substitucio.data == data).all()
        return [
            FilaSubstitucio(
                id=str(sub.id),
                data=sub.data,
                hora=sub.hora,
                professor_absent=sub.professor_absent,
                assignatura=sub.assignatura or "",
                grup=sub.grup or "",
                aula=sub.aula or "",
                substitut=sub.substitut or "",
                tipus_substitut=sub.tipus_substitut or "",
                tipus_absencia=sub.tipus_absencia or "",
                comentaris=sub.comentaris or "",
                updated_at=sub.updated_at.isoformat() if sub.updated_at else None,
            )
            for sub in subs
        ]

    @staticmethod
    def historial_quota(db: Session, data: date) -> list[tuple[str, str, str]]:
        """Una lectura per centre/dia del mateix dia de la setmana, també dates
        futures; exclou el mateix dia. Només el curs del dia; sense curs definit,
        els dos últims anys (HISTORIAL_QUOTA).

        Projecció mínima en ordre cronològic amb ID com a desempat estable.
        El domini separa categories i reté només les deu últimes de cadascuna.
        """
        curs = CursRepository.get_for_date(db, data)
        consulta = db.query(Substitucio.hora, Substitucio.substitut, Substitucio.tipus_substitut)
        if curs:
            consulta = consulta.filter(Substitucio.data >= curs.data_inici)
            if curs.data_fi:
                consulta = consulta.filter(Substitucio.data <= curs.data_fi)
        else:
            consulta = consulta.filter(Substitucio.data >= data - HISTORIAL_QUOTA)
        files = (
            consulta.filter(
                Substitucio.data != data,
                func.strftime("%w", Substitucio.data) == data.strftime("%w"),
                Substitucio.substitut.isnot(None),
                Substitucio.substitut != "",
            )
            .order_by(Substitucio.data, Substitucio.id)
            .all()
        )
        return [(hora, professor, tipus or "") for hora, professor, tipus in files]

    @staticmethod
    def dates_entre(db: Session, inici: date, final: date) -> set[date]:
        """Les dates (date) entre `inici` i `final`, incloses, que tenen alguna fila."""
        files = db.query(Substitucio.data).filter(Substitucio.data >= inici, Substitucio.data <= final)
        return {d for (d,) in files.distinct()}

    @staticmethod
    def grups_usats(db: Session) -> set:
        """Els grups (tal com estan desats) de totes les files de l'historial."""
        files = db.query(Substitucio.grup).filter(Substitucio.grup.isnot(None), Substitucio.grup != "")
        return {g for (g,) in files.distinct()}

    @staticmethod
    def get_by_date_hour_and_type(db: Session, data: date, hora: str, tipus_absencia: str) -> list[Substitucio]:
        """Retorna les files d'una data i hora amb el tipus indicat."""
        return (
            db.query(Substitucio)
            .filter(
                and_(
                    Substitucio.data == data,
                    Substitucio.hora == hora,
                    Substitucio.tipus_absencia == tipus_absencia,
                )
            )
            .all()
        )

    @staticmethod
    def get_absences_by_date_and_hour(db: Session, data: date, hora: str) -> list[Substitucio]:
        """Retorna absències i serveis, sense les files derivades."""
        return (
            db.query(Substitucio)
            .filter(
                and_(
                    Substitucio.data == data,
                    Substitucio.hora == hora,
                    Substitucio.tipus_absencia.notin_(["VIGILANCIA", "ENCADENADA", "VIGILANCIA_ABSENT"]),
                )
            )
            .all()
        )

    @staticmethod
    def delete_by_ids(db: Session, sub_ids: list[int]) -> int:
        """Esborra en bloc sense fer commit; la transacció la conserva el servei."""
        return db.query(Substitucio).filter(Substitucio.id.in_(sub_ids)).delete(synchronize_session="fetch")

    @staticmethod
    def create(db: Session, sub_data: dict) -> Substitucio:
        """Crea una nova substitució"""
        sub = Substitucio(
            data=sub_data["data"],
            hora=sub_data["hora"],
            professor_absent=sub_data["professor_absent"],
            assignatura=sub_data.get("assignatura", ""),
            grup=sub_data.get("grup", ""),
            aula=sub_data.get("aula", ""),
            substitut=sub_data.get("substitut", ""),
            tipus_substitut=sub_data.get("tipus_substitut", ""),
            tipus_absencia=sub_data.get("tipus_absencia", ""),
            comentaris=sub_data.get("comentaris", ""),
        )
        db.add(sub)
        db.flush()
        db.refresh(sub)
        return sub

    @staticmethod
    def update(db: Session, sub_id: int, updates: dict, *, updated_at_esperat: str | None = None) -> Substitucio | None:
        """Actualitza una substitució"""
        sub = db.query(Substitucio).filter(Substitucio.id == sub_id).first()
        if not sub:
            return None

        if updated_at_esperat is not None:
            # El predicat i l'escriptura són una única operació de la BD.
            valors = {k: v for k, v in updates.items() if hasattr(sub, k) and getattr(sub, k) != v}
            # Un canvi buit també comprova la versió i conserva el timestamp.
            valors = valors or {"updated_at": sub.updated_at}
            afectades = (
                db.query(Substitucio)
                .filter(Substitucio.id == sub_id, Substitucio.updated_at == datetime.fromisoformat(updated_at_esperat))
                .update(valors, synchronize_session=False)
            )
            if afectades != 1:
                return None
            db.refresh(sub)
            return sub

        for key, value in updates.items():
            if hasattr(sub, key):
                setattr(sub, key, value)

        db.flush()
        db.refresh(sub)
        return sub

    @staticmethod
    def delete(db: Session, sub_id: int) -> bool:
        """Elimina una substitució"""
        sub = db.query(Substitucio).filter(Substitucio.id == sub_id).first()
        if not sub:
            return False

        db.delete(sub)
        db.flush()
        return True

    @staticmethod
    def esborra_vigilancies_del_dia(db: Session, data: date) -> None:
        """Les files de vigilant absent (tipus VIGILANCIA) d'un dia."""
        db.query(Substitucio).filter(Substitucio.data == data, Substitucio.tipus_absencia == "VIGILANCIA").delete(
            synchronize_session=False
        )
