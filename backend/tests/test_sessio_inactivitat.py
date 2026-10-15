"""
Durada de les sessions (auth_utils): caduquen al cap de SESSIO_INACTIVITAT_MINUTS
sense peticions, es renoven mentre s'hi treballa i no passen de
SESSIO_MAXIMA_HORES des de l'entrada.
"""
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from auth_utils import COOKIE_NAME
from config.auth import ALGORITHM, SECRET_KEY, SESSIO_INACTIVITAT_MINUTS, SESSIO_MAXIMA_HORES
from rate_limit import limiter
from routes import users
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio

APP = crea_app(users.router)
ARA = None


@pytest.fixture(autouse=True)
def _limiter_net():
    global ARA
    ARA = datetime.now(timezone.utc)
    limiter.reset()
    yield


@pytest.fixture
def client():
    centre = nova_institucio(amb_xml=True)
    nom = f"user_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, centre, "user")
    return entra(client_per(APP), nom)


def _payload(client):
    return jwt.decode(client.cookies[COOKIE_NAME], SECRET_KEY, algorithms=[ALGORITHM])


def _amb_testimoni(client, emes, inici, caduca):
    """Substitueix la cookie per una de la mateixa sessió amb altres hores."""
    p = _payload(client)
    p.update({"iat": int(emes.timestamp()), "ini": inici.timestamp(), "exp": int(caduca.timestamp())})
    client.cookies.set(COOKIE_NAME, jwt.encode(p, SECRET_KEY, algorithm=ALGORITHM), domain="testserver.local")
    return client


def _perfil(client):
    return client.get("/api/users/profile")


def test_en_entrar_caduca_al_cap_de_la_inactivitat_maxima(client):
    p = _payload(client)
    assert p["exp"] - p["iat"] == SESSIO_INACTIVITAT_MINUTS * 60
    assert abs(p["ini"] - ARA.timestamp()) < 60


def test_una_peticio_al_cap_d_una_estona_renova_la_sessio(client):
    _amb_testimoni(client, ARA - timedelta(minutes=30), ARA - timedelta(hours=2), ARA + timedelta(minutes=30))
    resp = _perfil(client)
    assert resp.status_code == 200, resp.text
    assert COOKIE_NAME in resp.headers.get("set-cookie", "")
    p = _payload(client)
    assert p["exp"] >= int(ARA.timestamp()) + SESSIO_INACTIVITAT_MINUTS * 60 - 5
    assert p["ini"] == pytest.approx((ARA - timedelta(hours=2)).timestamp())   # l'entrada no canvia


def test_si_s_acaba_de_renovar_no_es_torna_a_renovar(client):
    resp = _perfil(client)
    assert resp.status_code == 200
    assert COOKIE_NAME not in resp.headers.get("set-cookie", "")


def test_la_renovacio_no_passa_del_maxim_des_de_l_entrada(client):
    inici = ARA - timedelta(hours=SESSIO_MAXIMA_HORES) + timedelta(minutes=10)
    _amb_testimoni(client, ARA - timedelta(minutes=20), inici, ARA + timedelta(minutes=10))
    assert _perfil(client).status_code == 200
    limit = (inici + timedelta(hours=SESSIO_MAXIMA_HORES)).timestamp()
    assert _payload(client)["exp"] <= int(limit) + 1


def test_sense_activitat_la_sessio_caduca(client):
    _amb_testimoni(client, ARA - timedelta(minutes=SESSIO_INACTIVITAT_MINUTS + 5),
                   ARA - timedelta(hours=3), ARA - timedelta(minutes=5))
    resp = _perfil(client)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Sessió caducada"


def test_una_peticio_que_falla_no_renova(client):
    _amb_testimoni(client, ARA - timedelta(minutes=30), ARA - timedelta(hours=2), ARA + timedelta(minutes=30))
    resp = client.get("/api/users/no-existeix-aquesta-ruta")
    assert resp.status_code >= 400
    assert COOKIE_NAME not in resp.headers.get("set-cookie", "")
