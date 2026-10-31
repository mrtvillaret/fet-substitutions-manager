"""
Les pantalles d'un dia (Substitucions, Vigilàncies) fan servir l'horari
vigent aquell dia: amb un horari futur ja pujat, un dia d'abans del canvi
mostra els professors de l'horari actual i un dia de després, els del nou.
"""

import uuid

import pytest
from fastapi import Depends
from suport_api import client_per, crea_app, crea_usuari, entra
from suport_xml import amb_horari_futur, dia, professor_que_plega

from auth.dependencies import get_current_user
from grups.router import router_admin as grups_admin_router
from prioritats.router import router as prioritats_router
from rate_limit import limiter
from routes import general, horari
from vigilancies.router import router as vigilancies_router

APP = crea_app()
for _router in (
    general.router,
    horari.router,
    prioritats_router,
    grups_admin_router,
    vigilancies_router,
):  # com a main.py
    APP.include_router(_router, dependencies=[Depends(get_current_user)])
ABANS, DESPRES = dia(1).isoformat(), dia(10).isoformat()


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


@pytest.fixture
def client():
    centre = amb_horari_futur()
    nom = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, centre, "admin")
    return entra(client_per(APP), nom)


def _professors(client, url, **params):
    resp = client.get(url, params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()["professors"]


@pytest.mark.parametrize("url", ["/api/horari/professors", "/api/vigilancies/config", "/api/horari/professors/all"])
def test_els_professors_son_els_de_l_horari_d_aquell_dia(client, url):
    assert professor_que_plega() in _professors(client, url, data=ABANS)
    assert professor_que_plega() not in _professors(client, url, data=DESPRES)


@pytest.mark.parametrize(
    "url", ["/api/horari/professors", "/api/vigilancies/config", "/api/professors", "/api/horari/professors/all"]
)
def test_sense_data_els_professors_son_els_de_l_horari_vigent_avui(client, url):
    assert professor_que_plega() in _professors(client, url)


@pytest.mark.parametrize("url", ["/api/hores", "/api/vigilancies/config"])
def test_les_hores_es_poden_demanar_per_a_un_dia(client, url):
    resp = client.get(url, params={"data": DESPRES})
    assert resp.status_code == 200 and resp.json()["hores"]


@pytest.mark.parametrize(
    "url",
    [
        "/api/hores",
        "/api/vigilancies/config",
        "/api/horari/professors",
        "/api/horari/professors/all",
        "/api/config",
        "/api/prioritats/activitats-alliberables",
    ],
)
def test_una_data_mal_escrita_dona_400(client, url):
    assert client.get(url, params={"data": "17/10/2026"}).status_code == 400


def test_la_capcalera_compta_els_professors_de_l_horari_d_aquell_dia(client):
    abans = client.get("/api/config", params={"data": ABANS}).json()["num_professors"]
    despres = client.get("/api/config", params={"data": DESPRES}).json()["num_professors"]
    assert despres == abans - 1
