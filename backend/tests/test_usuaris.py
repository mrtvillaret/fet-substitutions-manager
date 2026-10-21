"""
Gestió d'usuaris (usuaris/): les regles que no cobreixen test_auth.py ni
test_usuaris_protegits.py.
"""

import uuid

import pytest
from suport_api import CONTRASENYA, client_per, crea_app, crea_usuari, entra, nova_institucio

from auth.repositories import UserRepository
from database import AuthSessionLocal
from rate_limit import limiter
from usuaris.router import router as usuaris_router

APP = crea_app(usuaris_router)


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


@pytest.fixture
def centre():
    """Un centre amb dos admins i un usuari; els noms són únics per test."""
    nom = nova_institucio()
    sufix = uuid.uuid4().hex[:8]
    noms = {"admin": f"admin_{sufix}", "admin2": f"admin2_{sufix}", "user": f"user_{sufix}"}
    ids = {
        "admin": crea_usuari(noms["admin"], nom, "admin"),
        "admin2": crea_usuari(noms["admin2"], nom, "admin"),
        "user": crea_usuari(noms["user"], nom, "user"),
    }
    return {"nom": nom, "noms": noms, "ids": ids}


def _usuari(user_id):
    with AuthSessionLocal() as db:
        return UserRepository.get_by_id(db, user_id)


# ------------------------------------------------------------ reanomenar


def test_reanomenar_amb_un_nom_que_ja_existeix_dona_409(centre):
    client = entra(client_per(APP), centre["noms"]["admin"])
    resp = client.put(f"/api/users/{centre['ids']['user']}", json={"username": centre["noms"]["admin2"]})
    assert resp.status_code == 409
    assert resp.json() == {"detail": "Ja existeix un usuari amb aquest nom"}
    assert _usuari(centre["ids"]["user"]).username == centre["noms"]["user"]


def test_reanomenar_amb_el_mateix_nom_no_es_un_conflicte(centre):
    client = entra(client_per(APP), centre["noms"]["admin"])
    resp = client.put(f"/api/users/{centre['ids']['user']}", json={"username": centre["noms"]["user"]})
    assert resp.status_code == 200


def test_l_admin_que_es_canvia_el_nom_i_la_contrasenya_alhora_conserva_la_sessio(centre):
    client = entra(client_per(APP), centre["noms"]["admin"])
    altra = entra(client_per(APP), centre["noms"]["admin"])
    nou = centre["noms"]["admin"] + "_nou"
    resp = client.put(f"/api/users/{centre['ids']['admin']}", json={"username": nou, "password": "nova-contrasenya-1"})
    assert resp.status_code == 200
    assert client.get("/api/users/profile").json()["username"] == nou
    # La contrasenya nova tanca les altres sessions
    assert altra.get("/api/users/profile").status_code == 401
    assert entra(client_per(APP), nou, "nova-contrasenya-1")
    assert client_per(APP).post("/api/login", json={"username": nou, "password": CONTRASENYA}).status_code == 401


# ------------------------------------------------- ningú no es treu a si mateix


def test_un_admin_no_es_pot_desactivar_a_si_mateix(centre):
    client = entra(client_per(APP), centre["noms"]["admin"])
    resp = client.delete(f"/api/users/{centre['ids']['admin']}")
    assert resp.status_code == 403 and resp.json() == {"detail": "No et pots desactivar a tu mateix"}
    assert _usuari(centre["ids"]["admin"]).active


def test_un_admin_no_es_pot_desactivar_a_si_mateix_editant_se(centre):
    client = entra(client_per(APP), centre["noms"]["admin"])
    resp = client.put(f"/api/users/{centre['ids']['admin']}", json={"active": False})
    assert resp.status_code == 403 and resp.json() == {"detail": "No et pots desactivar a tu mateix"}
    assert _usuari(centre["ids"]["admin"]).active


# --------------------------------------- cap centre es queda sense admin actiu


@pytest.fixture
def super_client():
    nom = f"super_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, nova_institucio(), "super_admin")
    return entra(client_per(APP), nom)


@pytest.fixture
def un_sol_admin(centre):
    """El centre, amb admin2 desactivat: admin és l'únic admin actiu."""
    with AuthSessionLocal() as db:
        UserRepository.update(db, UserRepository.get_by_id(db, centre["ids"]["admin2"]), active=False)
        db.commit()
    return centre


SENSE_ADMIN = {"detail": "El centre es quedaria sense cap admin actiu"}


def test_no_es_pot_desactivar_l_ultim_admin_actiu(un_sol_admin, super_client):
    resp = super_client.delete(f"/api/users/{un_sol_admin['ids']['admin']}")
    assert resp.status_code == 403 and resp.json() == SENSE_ADMIN
    assert _usuari(un_sol_admin["ids"]["admin"]).active


def test_no_es_pot_desactivar_l_ultim_admin_actiu_editant_lo(un_sol_admin, super_client):
    resp = super_client.put(f"/api/users/{un_sol_admin['ids']['admin']}", json={"active": False})
    assert resp.status_code == 403 and resp.json() == SENSE_ADMIN


def test_no_es_pot_esborrar_l_ultim_admin_actiu(un_sol_admin, super_client):
    resp = super_client.delete(f"/api/users/{un_sol_admin['ids']['admin']}/hard")
    assert resp.status_code == 403 and resp.json() == SENSE_ADMIN
    assert _usuari(un_sol_admin["ids"]["admin"]) is not None


def test_no_es_pot_treure_el_rol_a_l_ultim_admin_actiu(un_sol_admin, super_client):
    resp = super_client.put(f"/api/users/{un_sol_admin['ids']['admin']}", json={"role": "user"})
    assert resp.status_code == 403 and resp.json() == SENSE_ADMIN
    assert _usuari(un_sol_admin["ids"]["admin"]).role == "admin"


def test_l_ultim_admin_actiu_no_es_pot_treure_el_rol_ell_mateix(un_sol_admin):
    client = entra(client_per(APP), un_sol_admin["noms"]["admin"])
    resp = client.put(f"/api/users/{un_sol_admin['ids']['admin']}", json={"role": "user"})
    assert resp.status_code == 403 and resp.json() == SENSE_ADMIN


def test_no_es_pot_canviar_de_centre_l_ultim_admin_actiu(un_sol_admin, super_client):
    altre = nova_institucio()
    resp = super_client.put(f"/api/users/{un_sol_admin['ids']['admin']}", json={"institucio": altre})
    assert resp.status_code == 403 and resp.json() == SENSE_ADMIN
    assert _usuari(un_sol_admin["ids"]["admin"]).institucio == un_sol_admin["nom"]


def test_amb_un_altre_admin_actiu_si_que_es_pot(centre, super_client):
    # admin2 continua actiu: admin es pot desactivar, treure el rol o canviar de centre
    assert super_client.put(f"/api/users/{centre['ids']['admin']}", json={"role": "user"}).status_code == 200
    assert super_client.delete(f"/api/users/{centre['ids']['user']}").status_code == 200
    # i ara admin2 és l'últim
    assert super_client.delete(f"/api/users/{centre['ids']['admin2']}").json() == SENSE_ADMIN


def test_un_usuari_normal_no_compta_per_a_la_regla(un_sol_admin, super_client):
    assert super_client.delete(f"/api/users/{un_sol_admin['ids']['user']}/hard").status_code == 200
