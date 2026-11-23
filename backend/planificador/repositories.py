"""Consultes del planificador: les restriccions i els costos dels professors
(taules exam_*) i la seva configuració (claus scheduler_* de la taula
`configuracio`, a través de ConfiguracioRepository).

Els repositoris no fan commit: el fa el servei, un cop per operació."""

import json

from sqlalchemy.orm import Session

from configuracio.repositories import ConfiguracioRepository
from models import ExamCostProfessor, ExamRestriccio
from textos import nom_net

# Claus de la configuració del planificador (taula configuracio)
SCHEDULER_DATES_KEY = "scheduler_selected_dates"
SCHEDULER_NIVELLS_KEY = "scheduler_selected_nivells"
SCHEDULER_ALLIBERAMENTS_KEY = "scheduler_alliberaments_per_nivell"
SCHEDULER_DURADA_KEY = "scheduler_durada_titular"
SCHEDULER_DURADA_EXAMEN_KEY = "scheduler_durada_examen"
SCHEDULER_DURADES_GRUPS_KEY = "scheduler_durades_grups"
# L'últim horari generat (o editat a mà): el planificador el recorda en tornar
# a la pantalla, des de qualsevol ordinador. Es desa en generar i en recalcular
# el cost després d'una edició.
SCHEDULER_ULTIM_RESULTAT_KEY = "scheduler_ultim_resultat"

# Els exàmens fixats a un dia i una hora (editor de l'horari)
TIPUS_FIXATS = ("assignatures_dia_fix", "assignatures_hora_fix")


def carrega_json(text: str, default):
    if not text:
        return default
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return default


def llegeix_json(db: Session, clau: str, default):
    """El valor JSON d'una clau de la configuració, o `default`."""
    return carrega_json(ConfiguracioRepository.get(db, clau), default)


class RestriccioRepository:
    """Les restriccions i preferències del planificador (exam_restriccions)."""

    @staticmethod
    def actives(db: Session) -> list:
        return db.query(ExamRestriccio).filter(ExamRestriccio.activa.is_(True)).all()

    @staticmethod
    def esborra_totes(db: Session) -> None:
        db.query(ExamRestriccio).delete()

    @staticmethod
    def afegeix(db: Session, **camps) -> None:
        db.add(ExamRestriccio(**camps))

    @staticmethod
    def desfixa(db: Session, nom: str) -> None:
        """Treu el dia i l'hora fixats d'un examen."""
        db.query(ExamRestriccio).filter(ExamRestriccio.tipus.in_(TIPUS_FIXATS), ExamRestriccio.clau == nom).delete(
            synchronize_session=False
        )

    @staticmethod
    def fixa(db: Session, tipus: str, nom: str, valor) -> None:
        """Fixa el dia o l'hora (`tipus`) d'un examen: actualitza la que ja hi
        és o en crea una de nova."""
        configuracio = json.dumps(valor, ensure_ascii=False)
        existent = db.query(ExamRestriccio).filter(ExamRestriccio.tipus == tipus, ExamRestriccio.clau == nom).first()
        if existent:
            existent.configuracio = configuracio
            existent.pes = 100
            existent.activa = True
        else:
            db.add(ExamRestriccio(tipus=tipus, clau=nom, configuracio=configuracio, pes=100, activa=True))


class CostProfessorRepository:
    """El cost de fer venir o substituir un professor (exam_costos_professors):
    els globals (professor buit) i els individuals."""

    @staticmethod
    def costos(db: Session) -> dict:
        """Els desats: {"globals": {"substitucio": 80, ...}, "individuals":
        {"Prof A": {"substitucio": 100}}}."""
        costos = {"globals": {}, "individuals": {}}
        for cp in db.query(ExamCostProfessor).all():
            if cp.professor is None:
                costos["globals"][cp.tipus] = cp.pes
            else:
                costos["individuals"].setdefault(cp.professor, {})[cp.tipus] = cp.pes
        return costos

    @staticmethod
    def substitueix(db: Session, costos: dict) -> None:
        """Substitueix tots els costos pels de `costos` (sense commit)."""
        db.query(ExamCostProfessor).delete()
        for tipus, pes in costos.get("globals", {}).items():
            db.add(ExamCostProfessor(professor=None, tipus=tipus, pes=int(pes)))
        for professor, per_tipus in costos.get("individuals", {}).items():
            for tipus, pes in per_tipus.items():
                db.add(ExamCostProfessor(professor=nom_net(professor), tipus=tipus, pes=int(pes)))
