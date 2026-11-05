"""
Configuració de bases de dades SQLite amb SQLAlchemy
- auth.db global per usuaris
- gestor.db per institució
"""

import os
import re
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from schema_migrations.runner import initialize_database

BASE_DIR = Path(__file__).resolve().parent
# DATA_DIR apunta a la carpeta data/ a l'arrel del projecte (dos nivells amunt)
# Això permet multi-institució: data/centre1, data/centre2, etc.
PROJECT_DATA_ROOT = BASE_DIR.parent / "data"
DATA_BASE_DIR = Path(os.getenv("DATA_DIR", PROJECT_DATA_ROOT))


def _create_engine(db_path: Path):
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}, poolclass=NullPool, echo=False
    )

    @event.listens_for(engine, "connect")
    def _activa_foreign_keys(dbapi_connection, connection_record):
        # SQLite ignora els ON DELETE CASCADE de l'esquema si no s'activa
        # explícitament per connexió; sense això els esborrats en cascada
        # (p.ex. nivell -> grups/assignatures) no fan res.
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def get_auth_db_path() -> Path:
    # auth.db està a l'arrel de data/ (global per totes les institucions)
    return Path(os.getenv("AUTH_DB_PATH", DATA_BASE_DIR / "auth.db"))


AUTH_ENGINE = _create_engine(get_auth_db_path())
AuthSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=AUTH_ENGINE)


def create_auth_tables():
    """Inicialitza o comprova la versió de l’esquema global."""
    initialize_database(AUTH_ENGINE, "auth")


def get_data_dir_for_institucio(institucio: str) -> Path:
    if not institucio:
        raise ValueError("Institucio buida")
    # Comença per lletra o xifra: ni "." ni ".." (la carpeta de dades o la de sobre)
    if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]*", institucio) or ".." in institucio:
        raise ValueError("Institucio invalida")
    return DATA_BASE_DIR / institucio


def get_export_dir_for_institucio(institucio: str) -> Path:
    """Carpeta dels PDF exportats d'abans (ara els PDF ja no es desen). Sempre
    dins la carpeta del centre: abans es podia triar des de la configuració, i
    un admin hi podia posar la d'un altre centre."""
    export_path = get_data_dir_for_institucio(institucio) / "exports"
    export_path.mkdir(parents=True, exist_ok=True)
    return export_path


def create_data_tables(engine):
    """Inicialitza o comprova la versió de les dades d’un centre."""
    initialize_database(engine, "data")


@lru_cache(maxsize=None)
def get_engine_for_institucio(institucio: str):
    data_dir = get_data_dir_for_institucio(institucio)
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "gestor.db"
    engine = _create_engine(db_path)
    create_data_tables(engine)
    return engine


def get_auth_db() -> Session:
    db = AuthSessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_data_db(institucio: str):
    engine = get_engine_for_institucio(institucio)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_auth_db_session():
    db = AuthSessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_data_db_session(institucio: str):
    engine = get_engine_for_institucio(institucio)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
