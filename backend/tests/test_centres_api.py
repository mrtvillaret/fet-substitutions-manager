"""
Centres (/api/settings/institucions): els gestiona el superadmin.
"""

import uuid

import pytest
from fastapi import Depends
from suport_api import CONTRASENYA, client_per, crea_app, crea_usuari, entra, nova_institucio

from auth.dependencies import require_admin
from auth.repositories import UserRepository
from centres import router as centres
from config.settings import config
from database import DATA_BASE_DIR, AuthSessionLocal, get_data_db_session
from rate_limit import limiter
from repositories import ConfiguracioRepository

APP = crea_app()
APP.include_router(centres.router, dependencies=[Depends(require_admin)])  # com a main.py
URL = "/api/settings/institucions"


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


def _superadmin():
    nom = f"super_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, nova_institucio(), "super_admin")
    return entra(client_per(APP), nom)


@pytest.mark.parametrize("nom", ["../fora", "Centre E", ".amagat", "", "a/b"])
def test_un_nom_de_centre_no_valid_dona_400_i_no_crea_res(nom):
    # Abans: 500 (el ValueError de la carpeta no es controlava)
    superadmin = _superadmin()
    abans = sorted(DATA_BASE_DIR.iterdir())

    resposta = superadmin.post(URL, json={"nom": nom})

    assert resposta.status_code == 400, resposta.text
    assert resposta.json() == {"detail": "Nom de centre no vàlid"}
    assert sorted(DATA_BASE_DIR.iterdir()) == abans


def test_es_pot_canviar_el_nom_visible_d_un_centre_desactivat():
    # Abans donava 404: només el buscava entre els actius
    superadmin = _superadmin()
    centre = nova_institucio()
    config.set_institucio_activa(centre, False)

    resposta = superadmin.put(f"{URL}/{centre}", json={"display_name": "Nom nou"})

    assert resposta.status_code == 200, resposta.text
    with get_data_db_session(centre) as db:
        assert ConfiguracioRepository.nom_visible_institucio(db, centre) == "Nom nou"


def test_un_centre_que_no_existeix_continua_donant_404():
    assert _superadmin().put(f"{URL}/no_hi_es", json={"display_name": "X"}).status_code == 404


def _usuaris_actius(centre):
    with AuthSessionLocal() as db:
        return sorted((u.username, bool(u.active)) for u in UserRepository.list_by_institucio(db, centre))


def test_desactivar_un_centre_no_desactiva_els_usuaris_pero_no_hi_poden_entrar():
    # Abans es desactivaven tots (admins inclosos) i en reactivar el centre
    # s'havien de reactivar un per un. Ara n'hi ha prou amb el centre: cada
    # petició i l'entrada comproven que és actiu.
    superadmin = _superadmin()
    centre = nova_institucio()
    admin, usuari = f"admin_{uuid.uuid4().hex[:8]}", f"user_{uuid.uuid4().hex[:8]}"
    crea_usuari(admin, centre, "admin")
    crea_usuari(usuari, centre, "user")
    ja_dins = entra(client_per(APP), usuari)  # una sessió oberta abans de desactivar-lo
    abans = _usuaris_actius(centre)

    assert superadmin.put(f"{URL}/{centre}/status", json={"active": False}).status_code == 200

    assert _usuaris_actius(centre) == abans  # tots continuen actius
    for nom in (admin, usuari):
        resposta = client_per(APP).post("/api/login", json={"username": nom, "password": CONTRASENYA})
        assert resposta.status_code == 401, nom
    assert ja_dins.get("/api/users/profile").status_code == 403
    assert ja_dins.get(URL).status_code == 403

    assert superadmin.put(f"{URL}/{centre}/status", json={"active": True}).status_code == 200

    assert ja_dins.get("/api/users/profile").status_code == 200
    assert entra(client_per(APP), admin).get(URL).status_code == 200
