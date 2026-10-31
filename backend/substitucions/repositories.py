"""Repositori de substitucions."""

from typing import Dict, List, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from models import Substitucio
from ordre_curs import clau_curs, natural
from repositories import parse_date


class SubstitucioRepository:
    """Operacions CRUD per substitucions"""

    # L'ordre per mostrar-les (la pantalla i el PDF): per hores i, dins de cada
    # hora, segons el criteri triat a la pantalla (ORDRES): per curs
    # (ordre_curs.clau_curs: etapa, número, grup) i professor absent, o al
    # revés. Les files d'un mateix professor i grup, juntes (absència,
    # cobertura de vigilància...). Cada encadenada, just a sota de la
    # substitució que la provoca (la del seu professor com a substitut), s'ordeni
    # com s'ordeni: s'entén millor. No s'aplica a get_by_date: el motor
    # reparteix els substituts en l'ordre en què li arriben.
    _ORDRE_TIPUS = {"VIGILANCIA_ABSENT": 1, "VIGILANCIA": 2}
    ORDRES = ("curs", "professor")

    @staticmethod
    def ordena(files: list, hores: list, valor=lambda fila, camp: fila.get(camp), ordre: str = "curs") -> list:
        """Les files en l'ordre per mostrar-les. `hores`: l'ordre de l'horari
        (una hora que no hi és, al final). `valor(fila, camp)`: per a files que
        no són diccionaris (p.ex. models de Pydantic). `ordre`: un d'ORDRES."""
        if ordre not in SubstitucioRepository.ORDRES:
            raise ValueError(f"Ordre desconegut: {ordre}")

        def tipus(fila):
            return (valor(fila, "tipus_absencia") or "").upper()

        def clau(fila):
            curs = clau_curs(valor(fila, "grup"))
            professor = natural(valor(fila, "professor_absent"))
            primer, segon = (curs, professor) if ordre == "curs" else (professor, curs)
            return (
                primer,
                segon,
                SubstitucioRepository._ORDRE_TIPUS.get(tipus(fila), 0),
                natural(valor(fila, "assignatura")),
            )

        posicio = {hora: i for i, hora in enumerate(hores)}
        per_hora = {}
        for fila in files:
            per_hora.setdefault(valor(fila, "hora"), []).append(fila)

        ordenades = []
        for hora in sorted(per_hora, key=lambda h: (posicio.get(h, len(posicio)), h or "")):
            files_hora = per_hora[hora]
            encadenades = sorted(
                (f for f in files_hora if tipus(f) == "ENCADENADA"),
                key=lambda f: natural(valor(f, "professor_absent")),
            )
            pendents = list(encadenades)
            for fila in sorted((f for f in files_hora if tipus(f) != "ENCADENADA"), key=clau):
                ordenades.append(fila)
                substitut = (valor(fila, "substitut") or "").strip()
                for encadenada in [e for e in pendents if substitut and valor(e, "professor_absent") == substitut]:
                    ordenades.append(encadenada)
                    pendents.remove(encadenada)
            # Sense la substitució que la provoca (no hauria de passar): al final de l'hora
            ordenades.extend(pendents)
        return ordenades

    @staticmethod
    def get_by_date(db: Session, data: str) -> List[Dict]:
        """Retorna totes les substitucions d'una data"""
        subs = db.query(Substitucio).filter(Substitucio.data == parse_date(data)).all()

        return [
            {
                "id": str(sub.id),
                "data": str(sub.data),
                "hora": sub.hora,
                "professor_absent": sub.professor_absent,
                "assignatura": sub.assignatura or "",
                "grup": sub.grup or "",
                "aula": sub.aula or "",
                "substitut": sub.substitut or "",
                "tipus_substitut": sub.tipus_substitut or "",
                "tipus_absencia": sub.tipus_absencia or "",
                "comentaris": sub.comentaris or "",
                "updated_at": sub.updated_at.isoformat() if sub.updated_at else None,
            }
            for sub in subs
        ]

    @staticmethod
    def get_by_date_hour_and_type(db: Session, data: str, hora: str, tipus_absencia: str) -> List[Substitucio]:
        """Retorna les files d'una data i hora amb el tipus indicat."""
        return (
            db.query(Substitucio)
            .filter(
                and_(
                    Substitucio.data == parse_date(data),
                    Substitucio.hora == hora,
                    Substitucio.tipus_absencia == tipus_absencia,
                )
            )
            .all()
        )

    @staticmethod
    def get_absences_by_date_and_hour(db: Session, data: str, hora: str) -> List[Substitucio]:
        """Retorna absències i serveis, sense les files derivades."""
        return (
            db.query(Substitucio)
            .filter(
                and_(
                    Substitucio.data == parse_date(data),
                    Substitucio.hora == hora,
                    Substitucio.tipus_absencia.notin_(["VIGILANCIA", "ENCADENADA", "VIGILANCIA_ABSENT"]),
                )
            )
            .all()
        )

    @staticmethod
    def delete_by_ids(db: Session, sub_ids: List[int]) -> int:
        """Esborra en bloc sense fer commit; la transacció la conserva el servei."""
        return db.query(Substitucio).filter(Substitucio.id.in_(sub_ids)).delete(synchronize_session="fetch")

    @staticmethod
    def create(db: Session, sub_data: Dict) -> Substitucio:
        """Crea una nova substitució"""
        sub = Substitucio(
            data=parse_date(sub_data["data"]),
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
    def update(db: Session, sub_id: int, updates: Dict) -> Optional[Substitucio]:
        """Actualitza una substitució"""
        sub = db.query(Substitucio).filter(Substitucio.id == sub_id).first()
        if not sub:
            return None

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
