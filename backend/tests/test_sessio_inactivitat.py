"""
Durada de les sessions (auth/security.py): caduquen al cap de SESSIO_INACTIVITAT_MINUTS
sense peticions, es renoven mentre s'hi treballa i no passen de
SESSIO_MAXIMA_HORES des de l'entrada.
"""

import uuid
from datetime import timedelta

import jwt
import pytest
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio
from suport_rellotge import ARA

from auth.security import decode_access_token
from config.auth import get_config_auth
from rate_limit import limiter
from usuaris.router import router as usuaris_router

APP = crea_app(usuaris_router)


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


@pytest.fixture
def client():
    centre = nova_institucio(amb_xml=True)
    nom = f"user_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, centre, "user")
    return entra(client_per(APP), nom)


def _payload(client):
    return decode_access_token(client.cookies[get_config_auth().cookie_name])


def _amb_testimoni(client, emes, inici, caduca):
    """Substitueix la cookie per una de la mateixa sessió amb altres hores."""
    p = _payload(client)
    p.update({"iat": int(emes.timestamp()), "ini": inici.timestamp(), "exp": int(caduca.timestamp())})
    client.cookies.set(
        get_config_auth().cookie_name,
        jwt.encode(p, get_config_auth().secret_key, algorithm=get_config_auth().algorithm),
        domain="testserver.local",
    )
    return client


def _perfil(client):
    return client.get("/api/users/profile")


def test_en_entrar_caduca_al_cap_de_la_inactivitat_maxima(client):
    p = _payload(client)
    assert p["exp"] - p["iat"] == get_config_auth().sessio_inactivitat_minuts * 60
    assert abs(p["ini"] - ARA.timestamp()) < 60


def test_una_peticio_al_cap_d_una_estona_renova_la_sessio(client):
    _amb_testimoni(client, ARA - timedelta(minutes=30), ARA - timedelta(hours=2), ARA + timedelta(minutes=30))
    resp = _perfil(client)
    assert resp.status_code == 200, resp.text
    assert get_config_auth().cookie_name in resp.headers.get("set-cookie", "")
    p = _payload(client)
    assert p["exp"] >= int(ARA.timestamp()) + get_config_auth().sessio_inactivitat_minuts * 60 - 5
    assert p["ini"] == pytest.approx((ARA - timedelta(hours=2)).timestamp())  # l'entrada no canvia


def test_si_s_acaba_de_renovar_no_es_torna_a_renovar(client):
    resp = _perfil(client)
    assert resp.status_code == 200
    assert get_config_auth().cookie_name not in resp.headers.get("set-cookie", "")


def test_la_renovacio_no_passa_del_maxim_des_de_l_entrada(client):
    inici = ARA - timedelta(hours=get_config_auth().sessio_maxima_hores) + timedelta(minutes=10)
    _amb_testimoni(client, ARA - timedelta(minutes=20), inici, ARA + timedelta(minutes=10))
    assert _perfil(client).status_code == 200
    limit = (inici + timedelta(hours=get_config_auth().sessio_maxima_hores)).timestamp()
    assert _payload(client)["exp"] <= int(limit) + 1


def test_sense_activitat_la_sessio_caduca(client):
    _amb_testimoni(
        client,
        ARA - timedelta(minutes=get_config_auth().sessio_inactivitat_minuts + 5),
        ARA - timedelta(hours=3),
        ARA - timedelta(minutes=5),
    )
    resp = _perfil(client)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Sessió caducada"


def test_una_peticio_que_falla_no_renova(client):
    _amb_testimoni(client, ARA - timedelta(minutes=30), ARA - timedelta(hours=2), ARA + timedelta(minutes=30))
    resp = client.get("/api/users/no-existeix-aquesta-ruta")
    assert resp.status_code >= 400
    assert get_config_auth().cookie_name not in resp.headers.get("set-cookie", "")


def test_la_mateixa_sessio_caduca_avancant_nomes_el_rellotge(client, rellotge_fix):
    assert _perfil(client).status_code == 200
    rellotge_fix.avanca(minutes=get_config_auth().sessio_inactivitat_minuts)
    resposta = _perfil(client)
    assert resposta.status_code == 401
    assert resposta.json()["detail"] == "Sessió caducada"
