"""
Utilitats compartides pels tests d'API: app mínima amb els routers que calguin,
institucions temporals (opcionalment amb l'XML d'exemple) i usuaris de prova.
Tot viu dins del DATA_DIR temporal que prepara el conftest.
"""
import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi.errors import RateLimitExceeded

from auth_utils import hash_password
from errors_servidor import registra_gestors_errors
from database import (
    AuthSessionLocal,
    create_auth_tables,
    get_data_db_session,
    get_data_dir_for_institucio,
)
from models import AssignaturaPrioritat, CategoriaPrioritat
from rate_limit import limit_superat, limiter
from repositories import ConfiguracioRepository, UserRepository
from routes import auth

CONTRASENYA = "contrasenya-de-prova"
XML_EXEMPLE = Path(__file__).resolve().parents[2] / "data" / "exemple" / "teachers.xml"


def crea_app(*routers):
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, limit_superat)
    registra_gestors_errors(app)
    app.include_router(auth.router)
    for router in routers:
        app.include_router(router)
    return app


def client_per(app):
    # https: la cookie de sessió es marca Secure i el client només la retorna per https.
    return TestClient(app, base_url="https://testserver")


# Categories de prioritat mínimes perquè hi hagi substituts disponibles: primer
# els professors amb el grup alliberat, després els que fan guàrdia.
PRIORITATS_PER_DEFECTE = [("Alliberats", ["alliberat"]), ("Guàrdies", ["Guàrdia"])]


def nova_institucio(amb_xml=False, prioritats=PRIORITATS_PER_DEFECTE):
    nom = f"centre_{uuid.uuid4().hex[:8]}"
    with get_data_db_session(nom) as db:  # crea la carpeta i el gestor.db
        if amb_xml:
            shutil.copy(XML_EXEMPLE, get_data_dir_for_institucio(nom) / "teachers.xml")
            ConfiguracioRepository.set(db, "xml_horari_path", "teachers.xml")
        for ordre, (categoria, assignatures) in enumerate(prioritats or [], start=1):
            cat = CategoriaPrioritat(nom=categoria, ordre=ordre, activa=True)
            db.add(cat)
            db.flush()
            for i, assignatura in enumerate(assignatures):
                # Cada assignatura pot ser un nom o un parell (nom, pes)
                nom_assig, pes = assignatura if isinstance(assignatura, tuple) else (assignatura, 1)
                db.add(AssignaturaPrioritat(assignatura=nom_assig, categoria_id=cat.id, pes=pes, ordre=i))
        db.commit()
    return nom


def crea_usuari(username, institucio, role="user", active=True):
    create_auth_tables()
    with AuthSessionLocal() as db:
        return UserRepository.create(
            db=db,
            username=username,
            password_hash=hash_password(CONTRASENYA),
            institucio=institucio,
            role=role,
            active=active,
        ).id


def entra(client, username, password=CONTRASENYA):
    resp = client.post("/api/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return client
