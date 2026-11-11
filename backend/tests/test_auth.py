"""
Tests d'autenticació i permisos: login/logout, validació del testimoni,
rols i gestió d'usuaris entre institucions.

No importa main.py (que carrega el .env i crea els usuaris inicials): munta
l'app mínima de suport_api amb els routers d'auth i d'usuaris i les
dependències reals de permisos. Tot passa sobre l'auth.db i les institucions
temporals que prepara el conftest.
"""

import uuid
from datetime import timedelta
from pathlib import Path

import jwt
import pytest
from fastapi import Depends
from suport_api import CONTRASENYA, client_per, crea_app, crea_usuari, entra, nova_institucio
from suport_rellotge import ARA

import auth.services as serveis_auth
from auth.dependencies import require_admin, require_super_admin, require_user
from auth.repositories import UserRepository
from auth.security import create_access_token, decode_access_token, hash_password, verify_password
from config.auth import get_config_auth
from config.settings import config
from database import AuthSessionLocal
from rate_limit import limiter
from usuaris.router import router as usuaris_router


def _app():
    app = crea_app(usuaris_router)

    @app.get("/prova/user")
    def nomes_user(u=Depends(require_user)):
        return {"username": u.username, "institucio": u.institucio}

    @app.get("/prova/admin")
    def nomes_admin(u=Depends(require_admin)):
        return {"username": u.username}

    @app.get("/prova/super")
    def nomes_super(u=Depends(require_super_admin)):
        return {"username": u.username}

    return app


APP = _app()


def _nova_institucio():
    # Sense prioritats: aquí només calen la carpeta i el gestor.db
    return nova_institucio(prioritats=None)


def _usuari_db(username):
    with AuthSessionLocal() as db:
        return UserRepository.get_by_username(db, username)


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def client():
    return client_per(APP)


@pytest.fixture
def escenari():
    """Dues institucions, cadascuna amb un admin i un usuari, i un superadmin."""
    sufix = uuid.uuid4().hex[:6]
    a, b = _nova_institucio(), _nova_institucio()
    noms = {
        "super": f"super_{sufix}",
        "admin_a": f"admin_a_{sufix}",
        "user_a": f"usuari_a_{sufix}",
        "admin_b": f"admin_b_{sufix}",
        "user_b": f"usuari_b_{sufix}",
    }
    ids = {
        "super": crea_usuari(noms["super"], a, "super_admin"),
        "admin_a": crea_usuari(noms["admin_a"], a, "admin"),
        "user_a": crea_usuari(noms["user_a"], a, "user"),
        "admin_b": crea_usuari(noms["admin_b"], b, "admin"),
        "user_b": crea_usuari(noms["user_b"], b, "user"),
    }
    return {"a": a, "b": b, "noms": noms, "ids": ids}


def _login(client, username, password=CONTRASENYA):
    return client.post("/api/login", json={"username": username, "password": password})


def _entra(client, escenari, qui):
    return entra(client, escenari["noms"][qui])


def _posa_token(client, payload, clau=get_config_auth().secret_key):
    client.cookies.set(get_config_auth().cookie_name, jwt.encode(payload, clau, algorithm=get_config_auth().algorithm))


# ---------------------------------------------------------------- contrasenyes


def test_hash_i_verificacio_de_contrasenya():
    h = hash_password("secret")
    assert h.startswith("$argon2")
    assert verify_password("secret", h)
    assert not verify_password("una-altra", h)


def test_hash_malmes_no_llanca_sino_que_retorna_false():
    assert verify_password("secret", "no-es-un-hash") is False


# ----------------------------------------------------------------------- login


def test_login_correcte_posa_cookie_httponly_amb_les_dades_del_usuari(client, escenari):
    resp = _login(client, escenari["noms"]["admin_a"])
    assert resp.status_code == 200
    cookie = resp.headers["set-cookie"]
    assert cookie.startswith(f"{get_config_auth().cookie_name}=")
    assert "HttpOnly" in cookie
    assert "samesite=lax" in cookie.lower()

    payload = decode_access_token(client.cookies[get_config_auth().cookie_name])
    assert payload["sub"] == escenari["noms"]["admin_a"]
    assert payload["institucio"] == escenari["a"]
    assert payload["role"] == "admin"
    assert "exp" in payload


def test_login_amb_contrasenya_incorrecta_o_usuari_inexistent_dona_el_mateix_error(client, escenari):
    dolenta = _login(client, escenari["noms"]["user_a"], "incorrecta")
    inexistent = _login(client, "no_existeix", "incorrecta")
    assert dolenta.status_code == inexistent.status_code == 401
    # Mateix missatge: no es pot saber si l'usuari existeix.
    assert dolenta.json() == inexistent.json()
    assert get_config_auth().cookie_name not in client.cookies


@pytest.mark.parametrize("cas", ["inexistent", "desactivat", "contrasenya dolenta"])
def test_el_login_sempre_comprova_una_contrasenya(client, escenari, monkeypatch, cas):
    # Sense rellotge: si el login d'un usuari inexistent o desactivat no
    # calculés cap Argon2, respondria abans i el temps diria qui existeix.
    comprovacions = []
    real = serveis_auth.verify_password
    monkeypatch.setattr(serveis_auth, "verify_password", lambda *a: comprovacions.append(a) or real(*a))
    nom = {"inexistent": "no_existeix", "contrasenya dolenta": escenari["noms"]["user_a"]}.get(cas)
    if cas == "desactivat":
        nom = "desactivat_" + escenari["a"]
        crea_usuari(nom, escenari["a"], active=False)
    assert _login(client, nom, "incorrecta").status_code == 401
    assert len(comprovacions) == 1


def test_login_d_usuari_desactivat_es_rebutja(client, escenari):
    crea_usuari("desactivat_" + escenari["a"], escenari["a"], active=False)
    assert _login(client, "desactivat_" + escenari["a"]).status_code == 401


def test_login_limitat_a_5_intents_per_minut_i_usuari(client, escenari):
    for _ in range(5):
        assert _login(client, escenari["noms"]["user_a"], "incorrecta").status_code == 401
    assert _login(client, escenari["noms"]["user_a"]).status_code == 429
    # Des de la mateixa IP, un altre usuari encara pot entrar
    assert _login(client, escenari["noms"]["admin_a"]).status_code == 200


def test_el_429_diu_quants_segons_cal_esperar(client, escenari):
    for _ in range(5):
        _login(client, escenari["noms"]["user_a"], "incorrecta")
    resp = _login(client, escenari["noms"]["user_a"])
    assert resp.status_code == 429
    assert 1 <= int(resp.headers["Retry-After"]) <= 60
    assert resp.json() == {"error": "Rate limit exceeded: 5 per 1 minute"}  # com el del decorador


def _prova_30_usuaris(client):
    for i in range(30):
        assert _login(client, f"no_existeix_{i}", "incorrecta").status_code == 401


def test_login_limitat_a_30_intents_per_minut_i_ip(client, escenari):
    # Qui prova molts usuaris des d'una IP topa amb el límit de la IP
    _prova_30_usuaris(client)
    resp = _login(client, escenari["noms"]["user_a"])
    assert resp.status_code == 429 and 1 <= int(resp.headers["Retry-After"]) <= 60


def test_canviar_x_forwarded_for_no_salta_el_limit_de_login(client, escenari):
    # Una connexió que no ve d'un proxy intern: la capçalera s'ignora.
    _prova_30_usuaris(client)
    resp = client.post(
        "/api/login",
        json={"username": escenari["noms"]["user_a"], "password": CONTRASENYA},
        headers={"X-Forwarded-For": "203.0.113.7"},
    )
    assert resp.status_code == 429


def _peticio(client_host, x_forwarded_for=None):
    from starlette.requests import Request

    capcaleres = [(b"x-forwarded-for", x_forwarded_for.encode())] if x_forwarded_for else []
    return Request({"type": "http", "headers": capcaleres, "client": (client_host, 1234)})


@pytest.mark.parametrize(
    "client_host, xff, esperat",
    [
        ("93.184.216.34", None, "93.184.216.34"),  # directe, sense proxy
        ("93.184.216.34", "1.2.3.4", "93.184.216.34"),  # directe: la capçalera no es creu
        ("172.18.0.5", "198.51.100.20", "198.51.100.20"),  # Caddy: un sol valor
        ("172.18.0.5", "1.2.3.4, 198.51.100.20", "198.51.100.20"),  # nginx: el client n'ha posat un de fals
        ("127.0.0.1", "198.51.100.20", "198.51.100.20"),  # proxy a la mateixa màquina
        ("172.18.0.5", None, "172.18.0.5"),  # proxy sense capçalera
    ],
)
def test_ip_del_client_per_al_limit(client_host, xff, esperat):
    from rate_limit import get_client_ip

    assert get_client_ip(_peticio(client_host, xff)) == esperat


def test_logout_esborra_la_cookie(client, escenari):
    _entra(client, escenari, "user_a")
    resp = client.post("/api/logout")
    assert resp.status_code == 200
    assert get_config_auth().cookie_name not in client.cookies
    assert client.get("/prova/user").status_code == 401


# --------------------------------------------------------- validació del token


def test_sense_cookie_dona_401(client, escenari):
    assert client.get("/prova/user").status_code == 401


def test_cada_401_diu_el_text_i_el_codi_i_sense_capcaleres_d_autenticacio(client, escenari):
    respostes = {("No autenticat", "no_autenticat"): client.get("/prova/user")}
    respostes["Credencials incorrectes", "credencials_incorrectes"] = _login(
        client, escenari["noms"]["user_a"], "incorrecta"
    )
    client.cookies.set(get_config_auth().cookie_name, "no-es-un-token")
    respostes["Token invàlid", "token_invalid"] = client.get("/prova/user")
    _posa_token(client, {"sub": escenari["noms"]["user_a"], "exp": ARA - timedelta(minutes=1)})
    respostes["Sessió caducada", "sessio_caducada"] = client.get("/prova/user")
    _posa_token(client, {"sub": "no_existeix", "uid": -1, "exp": ARA + timedelta(minutes=5)})
    respostes["Usuari inactiu o inexistent", "usuari_inactiu"] = client.get("/prova/user")
    for (detail, codi), resp in respostes.items():
        assert (resp.status_code, resp.json()) == (401, {"detail": detail, "codi": codi, "params": {}})
        assert "www-authenticate" not in resp.headers


def test_token_que_no_es_un_jwt_dona_401(client, escenari):
    client.cookies.set(get_config_auth().cookie_name, "no-es-un-token")
    assert client.get("/prova/user").status_code == 401


def test_token_signat_amb_una_altra_clau_dona_401(client, escenari):
    _posa_token(
        client,
        {"sub": escenari["noms"]["super"], "institucio": escenari["a"], "role": "super_admin"},
        clau="una-clau-que-no-es-la-del-servidor",
    )
    assert client.get("/prova/user").status_code == 401


def test_token_caducat_dona_401(client, escenari):
    _posa_token(
        client,
        {
            "sub": escenari["noms"]["user_a"],
            "institucio": escenari["a"],
            "role": "user",
            "exp": ARA - timedelta(minutes=1),
        },
    )
    assert client.get("/prova/user").status_code == 401


def test_token_sense_usuari_dona_401(client, escenari):
    _posa_token(client, {"institucio": escenari["a"], "role": "admin", "exp": ARA + timedelta(minutes=5)})
    resp = client.get("/prova/user")
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Token invàlid", "codi": "token_invalid", "params": {}}


def test_token_sense_caducitat_dona_401(client, escenari):
    # Signat amb la clau bona i d'un usuari actiu: sense "exp" valdria per sempre
    _posa_token(
        client, {"sub": escenari["noms"]["user_a"], "uid": escenari["ids"]["user_a"], "institucio": escenari["a"]}
    )
    resp = client.get("/prova/user")
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Token invàlid", "codi": "token_invalid", "params": {}}


@pytest.mark.parametrize("camp", ["exp", "sub"])
def test_decode_exigeix_caducitat_i_usuari(camp):
    payload = {"sub": "algu", "exp": ARA + timedelta(minutes=5)}
    del payload[camp]
    token = jwt.encode(payload, get_config_auth().secret_key, algorithm=get_config_auth().algorithm)
    with pytest.raises(jwt.MissingRequiredClaimError):
        decode_access_token(token)


def test_usuari_desactivat_despres_del_login_perd_l_acces(client, escenari):
    _entra(client, escenari, "user_a")
    with AuthSessionLocal() as db:
        u = UserRepository.get_by_username(db, escenari["noms"]["user_a"])
        UserRepository.update(db, u, active=False)
        db.commit()
    assert client.get("/prova/user").status_code == 401


def test_el_rol_surt_de_la_bd_i_no_del_token(client, escenari):
    # Un token vàlid d'un usuari normal que diu "admin" no dona permisos d'admin.
    client.cookies.set(
        get_config_auth().cookie_name,
        create_access_token(
            {
                "sub": escenari["noms"]["user_a"],
                "institucio": escenari["a"],
                "role": "super_admin",
            }
        ),
    )
    assert client.get("/prova/user").status_code == 200
    assert client.get("/prova/admin").status_code == 403
    assert client.get("/prova/super").status_code == 403


def test_usuari_normal_no_pot_canviar_d_institucio_amb_el_token(client, escenari):
    client.cookies.set(
        get_config_auth().cookie_name,
        create_access_token(
            {
                "sub": escenari["noms"]["user_a"],
                "institucio": escenari["b"],
                "role": "user",
            }
        ),
    )
    assert client.get("/prova/user").status_code == 401


# ------------------------------------------- la sessió identifica l'usuari per l'id


def test_la_sessio_d_un_usuari_esborrat_no_val_per_a_un_de_nou_amb_el_mateix_nom(client, escenari):
    _entra(client, escenari, "user_a")
    with AuthSessionLocal() as db:
        UserRepository.delete(db, UserRepository.get_by_id(db, escenari["ids"]["user_a"]))
        db.commit()
    crea_usuari(escenari["noms"]["user_a"], escenari["a"])  # el mateix nom, un altre usuari
    assert client.get("/prova/user").status_code == 401


def test_la_sessio_no_passa_a_qui_pren_el_nom_d_un_usuari_reanomenat(client, escenari):
    _entra(client, escenari, "user_a")
    nom = escenari["noms"]["user_a"]
    with AuthSessionLocal() as db:
        UserRepository.update(db, UserRepository.get_by_id(db, escenari["ids"]["user_a"]), username=nom + "_vell")
        db.commit()
    crea_usuari(nom, escenari["a"], "admin")
    resp = client.get("/prova/user")
    # La sessió continua sent del primer usuari (ara amb el nom nou), no de l'admin nou
    assert resp.status_code == 200 and resp.json()["username"] == nom + "_vell"
    assert client.get("/prova/admin").status_code == 403


def test_un_admin_que_es_reanomena_conserva_la_sessio(client, escenari):
    _entra(client, escenari, "admin_a")
    nou = escenari["noms"]["admin_a"] + "_nou"
    assert client.put(f"/api/users/{escenari['ids']['admin_a']}", json={"username": nou}).status_code == 200
    resp = client.get("/prova/admin")
    assert resp.status_code == 200 and resp.json()["username"] == nou


def test_institucio_inactiva_bloqueja_els_seus_usuaris(client, escenari):
    _entra(client, escenari, "user_a")
    config.set_institucio_activa(escenari["a"], False)
    try:
        assert client.get("/prova/user").status_code == 403
    finally:
        config.set_institucio_activa(escenari["a"], True)
    assert client.get("/prova/user").status_code == 200


# ------------------------------------------------------------------------ rols


@pytest.mark.parametrize(
    "qui, user, admin, super_",
    [
        ("user_a", 200, 403, 403),
        ("admin_a", 200, 200, 403),
        ("super", 200, 200, 200),
    ],
)
def test_permisos_per_rol(client, escenari, qui, user, admin, super_):
    _entra(client, escenari, qui)
    assert client.get("/prova/user").status_code == user
    assert client.get("/prova/admin").status_code == admin
    assert client.get("/prova/super").status_code == super_


# ------------------------------------------------------------ gestió d'usuaris


def test_usuari_normal_no_pot_llistar_usuaris(client, escenari):
    _entra(client, escenari, "user_a")
    assert client.get("/api/users").status_code == 403


def test_admin_nomes_veu_usuaris_de_la_seva_institucio_i_no_el_superadmin(client, escenari):
    _entra(client, escenari, "admin_a")
    resp = client.get("/api/users")
    assert resp.status_code == 200
    noms = {u["username"] for u in resp.json()}
    assert noms == {escenari["noms"]["admin_a"], escenari["noms"]["user_a"]}


def test_superadmin_veu_usuaris_de_totes_les_institucions(client, escenari):
    _entra(client, escenari, "super")
    noms = {u["username"] for u in client.get("/api/users").json()}
    assert set(escenari["noms"].values()) <= noms


def test_admin_crea_usuari_a_la_seva_institucio(client, escenari):
    _entra(client, escenari, "admin_a")
    nou = "nou_" + escenari["a"]
    resp = client.post("/api/users", json={"username": nou, "password": "prou-llarga"})
    assert resp.status_code == 200
    assert resp.json()["institucio"] == escenari["a"]
    assert resp.json()["role"] == "user"


@pytest.mark.parametrize(
    "canvis, esperat",
    [
        ({"institucio": "b"}, 403),
        ({"role": "super_admin"}, 403),
        ({"role": "rol_inventat"}, 400),
        ({"institucio": "no_existeix"}, 400),
    ],
)
def test_admin_no_pot_crear_usuaris_fora_del_seu_abast(client, escenari, canvis, esperat):
    _entra(client, escenari, "admin_a")
    if canvis.get("institucio") == "b":
        canvis = {**canvis, "institucio": escenari["b"]}
    body = {"username": "prova_" + uuid.uuid4().hex[:6], "password": "x", **canvis}
    assert client.post("/api/users", json=body).status_code == esperat


def test_no_es_poden_crear_dos_usuaris_amb_el_mateix_nom(client, escenari):
    _entra(client, escenari, "admin_a")
    body = {"username": escenari["noms"]["user_a"], "password": "x"}
    assert client.post("/api/users", json=body).status_code == 409


def test_admin_no_pot_editar_ni_desactivar_usuaris_d_una_altra_institucio(client, escenari):
    _entra(client, escenari, "admin_a")
    id_b = escenari["ids"]["user_b"]
    assert client.put(f"/api/users/{id_b}", json={"active": False}).status_code == 403
    assert client.delete(f"/api/users/{id_b}").status_code == 403
    assert _usuari_db(escenari["noms"]["user_b"]).active is True


def test_admin_no_pot_traslladar_usuaris_ni_fer_superadmins(client, escenari):
    _entra(client, escenari, "admin_a")
    id_a = escenari["ids"]["user_a"]
    assert client.put(f"/api/users/{id_a}", json={"institucio": escenari["b"]}).status_code == 403
    assert client.put(f"/api/users/{id_a}", json={"role": "super_admin"}).status_code == 403
    u = _usuari_db(escenari["noms"]["user_a"])
    assert (u.institucio, u.role) == (escenari["a"], "user")


def test_ningu_pot_editar_ni_desactivar_el_superadmin(client, escenari):
    _entra(client, escenari, "super")
    id_super = escenari["ids"]["super"]
    assert client.put(f"/api/users/{id_super}", json={"role": "user"}).status_code == 403
    assert client.delete(f"/api/users/{id_super}").status_code == 403
    assert client.delete(f"/api/users/{id_super}/hard").status_code == 403


def test_admin_desactiva_usuari_de_la_seva_institucio(client, escenari):
    _entra(client, escenari, "admin_a")
    assert client.delete(f"/api/users/{escenari['ids']['user_a']}").status_code == 200
    assert _usuari_db(escenari["noms"]["user_a"]).active is False


def test_nomes_el_superadmin_pot_esborrar_usuaris_definitivament(client, escenari):
    id_a = escenari["ids"]["user_a"]
    _entra(client, escenari, "admin_a")
    assert client.delete(f"/api/users/{id_a}/hard").status_code == 403
    _entra(client, escenari, "super")
    assert client.delete(f"/api/users/{id_a}/hard").status_code == 200
    assert _usuari_db(escenari["noms"]["user_a"]) is None


# ---------------------------------------------------------------------- perfil


def test_canvi_de_contrasenya_demana_la_contrasenya_actual(client, escenari):
    nom = escenari["noms"]["user_a"]
    _entra(client, escenari, "user_a")
    malament = {"current_password": "incorrecta", "new_password": "nova"}
    assert client.put("/api/users/profile/password", json=malament).status_code == 400

    be = {"current_password": CONTRASENYA, "new_password": "nova-contrasenya"}
    assert client.put("/api/users/profile/password", json=be).status_code == 200
    assert _login(client, nom, CONTRASENYA).status_code == 401
    assert _login(client, nom, "nova-contrasenya").status_code == 200


def test_nomes_el_superadmin_pot_canviar_d_institucio(client, escenari):
    _entra(client, escenari, "admin_a")
    body = {"institucio": escenari["b"]}
    assert client.post("/api/users/profile/institucio", json=body).status_code == 403

    _entra(client, escenari, "super")
    assert client.post("/api/users/profile/institucio", json=body).status_code == 200
    assert client.get("/prova/user").json()["institucio"] == escenari["b"]


def test_canviar_d_institucio_no_modifica_la_institucio_desada_del_superadmin(client, escenari):
    nom = escenari["noms"]["super"]
    _entra(client, escenari, "super")
    client.post("/api/users/profile/institucio", json={"institucio": escenari["b"]})
    body = {"current_password": CONTRASENYA, "new_password": CONTRASENYA}
    assert client.put("/api/users/profile/password", json=body).status_code == 200
    assert _usuari_db(nom).institucio == escenari["a"]


def test_superadmin_no_pot_canviar_a_una_institucio_inexistent(client, escenari):
    _entra(client, escenari, "super")
    body = {"institucio": "no_existeix"}
    assert client.post("/api/users/profile/institucio", json=body).status_code == 400


# ------------------------------------------------- delegació del login


@pytest.fixture
def delegacio(config_auth_de_prova):
    config_auth_de_prova(LOGIN_DELEGACIO_USUARIS="user_demo,admin_demo", LOGIN_DELEGACIO_URL="/demo/")


def test_login_d_un_usuari_delegat_indica_on_ha_d_anar_sense_obrir_sessio(client, escenari, delegacio):
    resp = client.post("/api/login", json={"username": "user_demo", "password": "qualsevol"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": False, "redirect": "/demo/"}
    assert get_config_auth().cookie_name not in client.cookies


def test_un_nom_delegat_queda_reservat_encara_que_existeixi_aqui(client, escenari, delegacio):
    crea = AuthSessionLocal()
    try:
        UserRepository.create(
            db=crea,
            username="admin_demo",
            password_hash=hash_password(CONTRASENYA),
            institucio=escenari["a"],
            role="admin",
            active=True,
        )
        crea.commit()
    finally:
        crea.close()
    resp = _login(client, "admin_demo")
    assert resp.json()["redirect"] == "/demo/"
    assert get_config_auth().cookie_name not in client.cookies


def test_la_resta_d_usuaris_entren_com_sempre_amb_delegacio_activa(client, escenari, delegacio):
    resp = _login(client, escenari["noms"]["user_a"])
    assert resp.json() == {"ok": True}
    assert client.get("/prova/user").status_code == 200


def test_sense_configuracio_no_hi_ha_delegacio(client, escenari):
    resp = client.post("/api/login", json={"username": "user_demo", "password": "x"})
    assert resp.status_code == 401


def _importa_config_amb_delegacio(url):
    import os
    import subprocess
    import sys

    entorn = {**os.environ, "LOGIN_DELEGACIO_USUARIS": "user_demo", "LOGIN_DELEGACIO_URL": url}
    return subprocess.run(
        [sys.executable, "-c", "import config.auth"],
        env=entorn,
        cwd=str(Path(__file__).resolve().parents[1]),
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize("url", ["http://demo.exemple", "//una-altra-web.exemple", "demo/", "javascript:alert(1)"])
def test_la_url_de_delegacio_ha_de_ser_una_ruta_o_una_adreca_https(url):
    res = _importa_config_amb_delegacio(url)
    assert res.returncode != 0
    assert "LOGIN_DELEGACIO_URL" in res.stderr


@pytest.mark.parametrize("url", ["/demo/", "https://demo.gestor.exemple/"])
def test_la_delegacio_pot_ser_al_mateix_domini_o_a_un_subdomini(url):
    assert _importa_config_amb_delegacio(url).returncode == 0


def test_la_delegacio_a_una_altra_adreca_indica_l_adreca(client, escenari, config_auth_de_prova):
    # Una demo en un subdomini: el frontend hi porta l'usuari sense enviar-hi la contrasenya
    config_auth_de_prova(LOGIN_DELEGACIO_USUARIS="user_demo", LOGIN_DELEGACIO_URL="https://demo.gestor.exemple/")
    resp = client.post("/api/login", json={"username": "user_demo", "password": "qualsevol"})
    assert resp.json() == {"ok": False, "redirect": "https://demo.gestor.exemple/"}
    assert get_config_auth().cookie_name not in client.cookies


# ------------------------------------------------------ nom de la galeta


def test_el_nom_de_la_galeta_es_configurable(client, escenari, config_auth_de_prova):
    config_auth_de_prova(COOKIE_NAME="gestor_token_demo")
    _entra(client, escenari, "user_a")
    assert "gestor_token_demo" in client.cookies
    assert "gestor_token" not in client.cookies
    assert client.get("/prova/user").status_code == 200
    token = client.cookies.get("gestor_token_demo")
    client.cookies.clear()
    client.cookies.set("gestor_token", token)  # mateix testimoni, nom antic: no val
    assert client.get("/prova/user").status_code == 401


# ------------------------------------------------- contrasenya mínima


def test_no_es_pot_crear_un_usuari_amb_una_contrasenya_curta(client, escenari):
    _entra(client, escenari, "admin_a")
    resp = client.post("/api/users", json={"username": "curta_" + escenari["a"], "password": "1234567"})
    assert resp.status_code == 400
    assert "8 caràcters" in resp.json()["detail"]
    assert _usuari_db("curta_" + escenari["a"]) is None


def test_no_es_pot_posar_una_contrasenya_curta_en_editar_un_usuari(client, escenari):
    _entra(client, escenari, "admin_a")
    resp = client.put(f"/api/users/{escenari['ids']['user_a']}", json={"password": "curta"})
    assert resp.status_code == 400
    assert _login(client, escenari["noms"]["user_a"]).status_code == 200  # no ha canviat


def test_no_es_pot_canviar_la_propia_contrasenya_per_una_de_curta(client, escenari):
    _entra(client, escenari, "user_a")
    body = {"current_password": CONTRASENYA, "new_password": "curta"}
    assert client.put("/api/users/profile/password", json=body).status_code == 400
    assert _login(client, escenari["noms"]["user_a"]).status_code == 200


def test_no_es_pot_endevinar_la_contrasenya_des_del_canvi_de_contrasenya(client, escenari):
    """Amb una sessió robada no s'hi poden provar contrasenyes sense límit."""
    _entra(client, escenari, "user_a")
    body = {"current_password": "incorrecta", "new_password": "nova-contrasenya"}
    codis = [client.put("/api/users/profile/password", json=body).status_code for _ in range(6)]
    assert codis == [400] * 5 + [429]


# ------------------------------------------- tancar sessions a distància


def _dispositiu(escenari, qui):
    """Un altre navegador (un altre dispositiu) amb sessió del mateix usuari."""
    return _entra(client_per(APP), escenari, qui)


def test_canviar_la_contrasenya_tanca_les_altres_sessions_pero_no_la_propia(client, escenari):
    escola = _dispositiu(escenari, "user_a")
    _entra(client, escenari, "user_a")  # "casa"
    body = {"current_password": CONTRASENYA, "new_password": "nova-contrasenya"}
    assert client.put("/api/users/profile/password", json=body).status_code == 200

    assert escola.get("/prova/user").status_code == 401  # la de l'escola queda tancada
    assert client.get("/prova/user").status_code == 200  # qui l'ha canviada continua dins


def test_si_un_admin_canvia_la_contrasenya_d_un_usuari_se_li_tanquen_les_sessions(client, escenari):
    usuari = _dispositiu(escenari, "user_a")
    _entra(client, escenari, "admin_a")
    resp = client.put(f"/api/users/{escenari['ids']['user_a']}", json={"password": "nova-contrasenya"})
    assert resp.status_code == 200
    assert usuari.get("/prova/user").status_code == 401
    assert client.get("/prova/admin").status_code == 200  # l'admin no es veu afectat


def test_un_admin_que_es_canvia_la_seva_contrasenya_des_d_usuaris_continua_dins(client, escenari):
    altre = _dispositiu(escenari, "admin_a")
    _entra(client, escenari, "admin_a")
    resp = client.put(f"/api/users/{escenari['ids']['admin_a']}", json={"password": "nova-contrasenya"})
    assert resp.status_code == 200
    assert client.get("/prova/admin").status_code == 200
    assert altre.get("/prova/admin").status_code == 401


def test_editar_un_usuari_sense_canviar_la_contrasenya_no_li_tanca_la_sessio(client, escenari):
    usuari = _dispositiu(escenari, "user_a")
    _entra(client, escenari, "admin_a")
    client.put(f"/api/users/{escenari['ids']['user_a']}", json={"role": "user"})
    assert usuari.get("/prova/user").status_code == 200


def test_tancar_les_altres_sessions(client, escenari):
    escola = _dispositiu(escenari, "user_a")
    _entra(client, escenari, "user_a")
    assert client.post("/api/users/profile/tancar-altres-sessions").status_code == 200
    assert escola.get("/prova/user").status_code == 401
    assert client.get("/prova/user").status_code == 200
    # Des de l'escola es pot tornar a entrar amb la contrasenya de sempre
    assert _login(escola, escenari["noms"]["user_a"]).status_code == 200
    assert escola.get("/prova/user").status_code == 200


def test_el_superadmin_conserva_la_institucio_activa_en_tancar_les_altres_sessions(client, escenari):
    _entra(client, escenari, "super")
    client.post("/api/users/profile/institucio", json={"institucio": escenari["b"]})
    assert client.post("/api/users/profile/tancar-altres-sessions").status_code == 200
    assert client.get("/prova/user").json()["institucio"] == escenari["b"]


def test_els_testimonis_d_abans_d_aquest_canvi_continuen_valent(client, escenari):
    # Testimoni sense "sv" (emès abans que existís la versió de sessió):
    # val mentre l'usuari no hagi tancat cap sessió, així que desplegar el
    # canvi no fa sortir ningú.
    client.cookies.set(
        get_config_auth().cookie_name,
        create_access_token(
            {
                "sub": escenari["noms"]["user_a"],
                "institucio": escenari["a"],
                "role": "user",
            }
        ),
    )
    assert client.get("/prova/user").status_code == 200


def test_una_auth_db_antiga_rep_la_columna_nova_sense_perdre_usuaris(tmp_path):
    import sqlite3

    from sqlalchemy import create_engine
    from suport_database_antic import _ensure_users_versio_sessio_column

    ruta = tmp_path / "auth_antiga.db"
    con = sqlite3.connect(ruta)
    con.execute(
        "CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR, password_hash VARCHAR, "
        "institucio VARCHAR, role VARCHAR, active BOOLEAN, created_at DATETIME, updated_at DATETIME)"
    )
    con.execute(
        "INSERT INTO users (username, password_hash, institucio, role, active) VALUES ('antic', 'h', 'c', 'user', 1)"
    )
    con.commit()
    con.close()

    _ensure_users_versio_sessio_column(create_engine(f"sqlite:///{ruta}"))
    _ensure_users_versio_sessio_column(create_engine(f"sqlite:///{ruta}"))  # dues vegades: no falla

    con = sqlite3.connect(ruta)
    assert con.execute("SELECT username, versio_sessio FROM users").fetchall() == [("antic", 0)]
    con.close()
