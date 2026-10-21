"""
Desactivar o esborrar una institució desactiva o esborra els seus usuaris,
llevat del superadmin.
"""

import uuid

import pytest
from fastapi import Depends
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio

from auth.dependencies import require_admin
from auth.repositories import UserRepository
from database import AuthSessionLocal
from rate_limit import limiter
from routes import settings

APP = crea_app()
APP.include_router(settings.router, dependencies=[Depends(require_admin)])  # com a main.py


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


@pytest.fixture
def escenari():
    centre = nova_institucio()
    sufix = uuid.uuid4().hex[:8]
    noms = {"super": f"super_{sufix}", "admin": f"admin_{sufix}", "user": f"user_{sufix}"}
    crea_usuari(noms["super"], centre, "super_admin")
    crea_usuari(noms["admin"], centre, "admin")
    crea_usuari(noms["user"], centre, "user")
    return centre, noms, entra(client_per(APP), noms["super"])


def _usuari(nom):
    with AuthSessionLocal() as db:
        user = UserRepository.get_by_username(db, nom)
        return None if user is None else user.active


def test_desactivar_la_institucio_desactiva_els_seus_usuaris_menys_el_superadmin(escenari):
    centre, noms, client = escenari
    assert client.put(f"/api/settings/institucions/{centre}/status", json={"active": False}).status_code == 200
    assert (_usuari(noms["admin"]), _usuari(noms["user"]), _usuari(noms["super"])) == (False, False, True)


def test_esborrar_la_institucio_suau_desactiva_els_usuaris(escenari):
    centre, noms, client = escenari
    resp = client.request("DELETE", f"/api/settings/institucions/{centre}", json={"mode": "soft", "confirm": centre})
    assert resp.status_code == 200
    assert (_usuari(noms["admin"]), _usuari(noms["user"]), _usuari(noms["super"])) == (False, False, True)


def test_esborrar_la_institucio_del_tot_n_esborra_els_usuaris(escenari):
    centre, noms, client = escenari
    resp = client.request(
        "DELETE", f"/api/settings/institucions/{centre}", json={"mode": "hard", "confirm": f"ELIMINA {centre}"}
    )
    assert resp.status_code == 200
    assert (_usuari(noms["admin"]), _usuari(noms["user"]), _usuari(noms["super"])) == (None, None, True)
