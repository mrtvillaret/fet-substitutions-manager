"""Consultes de la configuració general del centre."""

from sqlalchemy.orm import Session

from models import Configuracio


class ConfiguracioRepository:
    """Operacions per configuració general"""

    @staticmethod
    def get_all_as_dict(db: Session) -> dict[str, str]:
        """Retorna tota la configuració com a diccionari"""
        configs = db.query(Configuracio).all()
        return {c.clau: c.valor for c in configs}

    @staticmethod
    def get(db: Session, clau: str) -> str | None:
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
        """Estableix un valor de configuració, sense tancar la transacció."""
        ConfiguracioRepository.desa(db, clau, valor, tipus=tipus, descripcio=descripcio)

    @staticmethod
    def desa(db: Session, clau: str, valor: str, tipus: str = "string", descripcio: str = ""):
        """Desa un valor amb flush; el servei decideix quan fer commit."""
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
