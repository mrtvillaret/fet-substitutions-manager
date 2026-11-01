"""
Repositoris (DAOs) per accedir a les dades SQLite
Encapsula tota la lògica d'accés a dades
"""

import logging
from datetime import date, datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from models import Configuracio

log = logging.getLogger(__name__)


def parse_date(date_str: str) -> date:
    """Converteix string YYYY-MM-DD a objecte date de Python"""
    if isinstance(date_str, date):
        return date_str
    return datetime.strptime(date_str, "%Y-%m-%d").date()


class ConfiguracioRepository:
    """Operacions per configuració general"""

    @staticmethod
    def get_all_as_dict(db: Session) -> Dict[str, str]:
        """Retorna tota la configuració com a diccionari"""
        configs = db.query(Configuracio).all()
        return {c.clau: c.valor for c in configs}

    @staticmethod
    def get(db: Session, clau: str) -> Optional[str]:
        """Obté un valor de configuració"""
        config = db.query(Configuracio).filter(Configuracio.clau == clau).first()
        return config.valor if config else None

    @staticmethod
    def nom_visible_institucio(db: Session, institucio: str) -> str:
        """El nom de la institució que es mostra a la web: el configurat o, si
        no n'hi ha, l'identificador. `db` és la BD de la mateixa institució."""
        return ConfiguracioRepository.get(db, "institucio_display_name") or institucio

    @staticmethod
    def set(db: Session, clau: str, valor: str, tipus: str = "string", descripcio: str = ""):
        """Estableix un valor de configuració i en fa commit."""
        ConfiguracioRepository.desa(db, clau, valor, tipus=tipus, descripcio=descripcio)
        db.commit()

    @staticmethod
    def desa(db: Session, clau: str, valor: str, tipus: str = "string", descripcio: str = ""):
        """Com set, però sense commit: per desar diversos valors d'un cop."""
        config = db.query(Configuracio).filter(Configuracio.clau == clau).first()

        if config:
            config.valor = valor
            config.tipus = tipus
            if descripcio:
                config.descripcio = descripcio
        else:
            config = Configuracio(clau=clau, valor=valor, tipus=tipus, descripcio=descripcio)
            db.add(config)
        db.flush()


class ProfessorRepository:
    """Repositori per gestionar professors històrics"""

    @staticmethod
    def existeix(db: Session, nom: str) -> bool:
        from models import Professor

        return db.query(Professor).filter_by(nom=nom).first() is not None

    @staticmethod
    def sync_from_xml(db: Session, professors_xml: List[str], data_sync=None) -> Dict[str, int]:
        """Sincronitza professors amb l'XML (actiu/inactiu)"""
        from datetime import date

        from models import Professor

        data_avui = data_sync or date.today()
        professors_noms = {nom.strip() for nom in professors_xml if nom and nom.strip()}

        existing = {p.nom: p for p in db.query(Professor).all()}

        nous = 0
        reactivats = 0
        desactivats = 0

        # Afegir o reactivar professors presents a l'XML
        for nom in professors_noms:
            prof = existing.get(nom)
            if prof:
                if not prof.actiu:
                    prof.actiu = True
                    reactivats += 1
                if not prof.primera_aparicio:
                    prof.primera_aparicio = data_avui
                prof.ultima_aparicio = data_avui
            else:
                db.add(Professor(nom=nom, actiu=True, primera_aparicio=data_avui, ultima_aparicio=data_avui))
                nous += 1

        # Marcar inactius els que ja no hi són
        for nom, prof in existing.items():
            if nom not in professors_noms and prof.actiu:
                prof.actiu = False
                prof.ultima_aparicio = data_avui
                desactivats += 1

        db.commit()
        return {"nous": nous, "reactivats": reactivats, "desactivats": desactivats, "total_xml": len(professors_noms)}
