"""
Desactivar una institució (o esborrar-la en mode «soft») no en toca els
usuaris; l'esborrat definitiu no es fa des de la web.
"""

import pytest
from fastapi import Depends
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio
from suport_noms import unic

from auth.dependencies import require_admin
from auth.repositories import UserRepository
from centres import router as centres
from config.settings import config
from database import DATA_BASE_DIR, AuthSessionLocal
from rate_limit import limiter

APP = crea_app()
APP.include_router(centres.router, dependencies=[Depends(require_admin)])  # com a main.py


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


@pytest.fixture
def escenari():
    centre = nova_institucio()
    sufix = unic()
    noms = {"super": f"super_{sufix}", "admin": f"admin_{sufix}", "user": f"user_{sufix}"}
    crea_usuari(noms["super"], centre, "super_admin")
    crea_usuari(noms["admin"], centre, "admin")
    crea_usuari(noms["user"], centre, "user")
    return centre, noms, entra(client_per(APP), noms["super"])


def _usuari(nom):
    with AuthSessionLocal() as db:
        user = UserRepository.get_by_username(db, nom)
        return None if user is None else user.active


def test_desactivar_la_institucio_no_toca_els_usuaris(escenari):
    # No hi poden entrar perquè el centre és inactiu (test_centres_api.py)
    centre, noms, client = escenari
    assert client.put(f"/api/settings/institucions/{centre}/status", json={"active": False}).status_code == 200
    assert (_usuari(noms["admin"]), _usuari(noms["user"]), _usuari(noms["super"])) == (True, True, True)


def test_esborrar_la_institucio_suau_la_desactiva_sense_tocar_els_usuaris(escenari):
    # Com desactivar-la: abans en desactivava tots els usuaris
    centre, noms, client = escenari
    resp = client.request("DELETE", f"/api/settings/institucions/{centre}", json={"mode": "soft", "confirm": centre})
    assert resp.status_code == 200
    assert not config.is_institucio_activa(centre)
    assert (_usuari(noms["admin"]), _usuari(noms["user"]), _usuari(noms["super"])) == (True, True, True)


def test_l_esborrat_definitiu_no_es_fa_des_de_la_web(escenari):
    # Abans n'esborrava la carpeta i els usuaris; ara es fa des del servidor,
    # amb còpia (scripts/esborra_centre.py, test_esborra_centre.py)
    centre, noms, client = escenari
    resp = client.request(
        "DELETE", f"/api/settings/institucions/{centre}", json={"mode": "hard", "confirm": f"ELIMINA {centre}"}
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "L'esborrat definitiu d'un centre es fa des del servidor"
    assert (DATA_BASE_DIR / centre / "gestor.db").is_file()
    assert config.is_institucio_activa(centre)
    assert (_usuari(noms["admin"]), _usuari(noms["user"]), _usuari(noms["super"])) == (True, True, True)
