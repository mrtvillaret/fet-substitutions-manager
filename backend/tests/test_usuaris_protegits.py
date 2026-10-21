"""
USUARIS_PROTEGITS (els usuaris d'una demo pública, amb la contrasenya
coneguda): ni ells mateixos ni cap admin els poden canviar la contrasenya,
editar, desactivar o tancar-los les sessions. El superadmin sí.
"""

import uuid

import pytest
from suport_api import (
    CONTRASENYA,
    client_per,
    crea_app,
    crea_usuari,
    entra,
    nova_institucio,
)

import auth.services as serveis_auth
from rate_limit import limiter
from usuaris.router import router as usuaris_router

APP = crea_app(usuaris_router)


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


@pytest.fixture
def demo(monkeypatch):
    centre = nova_institucio()
    noms = {r: f"{r}_{uuid.uuid4().hex[:6]}" for r in ("user", "admin", "super_admin")}
    ids = {r: crea_usuari(nom, centre, r) for r, nom in noms.items()}
    monkeypatch.setattr(serveis_auth, "USUARIS_PROTEGITS", frozenset({noms["user"], noms["admin"]}))
    return noms, ids


def _com(demo, rol):
    return entra(client_per(APP), demo[0][rol])


def test_un_usuari_protegit_no_es_pot_canviar_la_contrasenya(demo):
    body = {"current_password": CONTRASENYA, "new_password": "una-altra-contrasenya"}
    for rol in ("user", "admin"):
        assert _com(demo, rol).put("/api/users/profile/password", json=body).status_code == 403
    entra(client_per(APP), demo[0]["admin"])  # la contrasenya continua sent la mateixa


def test_un_usuari_protegit_no_pot_tancar_les_sessions_dels_altres(demo):
    assert _com(demo, "user").post("/api/users/profile/tancar-altres-sessions").status_code == 403


def test_l_admin_no_pot_editar_ni_desactivar_un_usuari_protegit(demo):
    admin = _com(demo, "admin")
    for rol in ("user", "admin"):
        assert admin.put(f"/api/users/{demo[1][rol]}", json={"password": "una-altra-contrasenya"}).status_code == 403
        assert admin.put(f"/api/users/{demo[1][rol]}", json={"active": False}).status_code == 403
        assert admin.delete(f"/api/users/{demo[1][rol]}").status_code == 403
    entra(client_per(APP), demo[0]["user"])


def test_l_admin_si_que_pot_gestionar_els_usuaris_no_protegits(demo):
    altre = crea_usuari(
        f"prof_{uuid.uuid4().hex[:6]}", _com(demo, "admin").get("/api/users/profile").json()["institucio"]
    )
    assert _com(demo, "admin").put(f"/api/users/{altre}", json={"active": False}).status_code == 200


def test_el_superadmin_si_que_pot_modificar_un_usuari_protegit(demo):
    sa = _com(demo, "super_admin")
    assert sa.put(f"/api/users/{demo[1]['user']}", json={"active": False}).status_code == 200
