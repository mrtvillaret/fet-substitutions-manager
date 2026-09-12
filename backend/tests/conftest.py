"""
Configuració comuna per als tests: posa el directori del backend al
sys.path i prepara variables d'entorn mínimes (SECRET_KEY, DATA_DIR cap a
un directori temporal) perquè els mòduls de l'app es puguin importar sense
dependre de la configuració real de desenvolupament ni tocar cap dada real.
"""
import os
import sys
import tempfile
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("SECRET_KEY", "test-secret-key-nomes-per-als-tests")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="gestor_tests_data_")

import pytest


@pytest.fixture
def db_session():
    """Sessió de BD sobre una institució temporal i única per test, perquè
    els tests no comparteixin ni contaminin dades entre ells (ni toquin cap
    institució real)."""
    from database import get_data_db

    institucio = f"test_{uuid.uuid4().hex}"
    gen = get_data_db(institucio)
    session = next(gen)
    try:
        yield session
    finally:
        try:
            next(gen)
        except StopIteration:
            pass
