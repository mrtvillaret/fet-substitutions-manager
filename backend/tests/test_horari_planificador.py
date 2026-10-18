"""
El planificador fa servir l'horari vigent a les dates que es planifiquen (la
primera); sense dates, el d'avui. Amb un horari futur ja pujat, planificar
uns exàmens d'aquí a deu dies ha d'importar assignacions i comprovar-les amb
l'horari nou, no amb el d'avui.
"""
import uuid

import pytest
from fastapi import Depends

from auth_utils import get_current_user, require_admin
from rate_limit import limiter
from routes import config_examens, general, scheduler
from suport_api import client_per, crea_app, crea_usuari, entra
from suport_xml import amb_horari_futur, dia, professor_que_plega

APP = crea_app()
APP.include_router(scheduler.router, dependencies=[Depends(require_admin)])        # com a main.py
APP.include_router(config_examens.router, dependencies=[Depends(require_admin)])
APP.include_router(general.router, dependencies=[Depends(get_current_user)])
FUTUR = [dia(10).isoformat(), dia(11).isoformat()]


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


def _planifica(client, dates):
    assert client.put("/api/scheduler/dates", json={"selected_dates": dates}).status_code == 200


def _horari(client, **params):
    resp = client.get("/api/scheduler/horari", params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_sense_dates_planificades_es_fa_servir_l_horari_d_avui(client):
    horari = _horari(client)
    assert horari["sense_dates"] and horari["data_referencia"] == dia(0).isoformat()
    assert horari["versio_des_de"] == dia(-30).isoformat() and horari["canvi_horari"] is None


def test_amb_dates_futures_es_fa_servir_l_horari_d_aquelles_dates(client):
    _planifica(client, FUTUR)
    horari = _horari(client)
    assert horari["data_referencia"] == FUTUR[0] and horari["versio_des_de"] == dia(3).isoformat()
    assert horari["canvi_horari"] is None


def test_si_les_dates_cauen_en_dos_horaris_es_diu_quan_canvia(client):
    horari = _horari(client, dates=f"{dia(1).isoformat()},{dia(10).isoformat()}")
    assert horari["data_referencia"] == dia(1).isoformat()
    assert horari["canvi_horari"] == dia(3).isoformat()


def test_una_data_mal_escrita_dona_400(client):
    assert client.get("/api/scheduler/horari", params={"dates": "17/10/2026"}).status_code == 400


def _titulars_proposats(client):
    resp = client.get("/api/config/importar-assignacions/preview")
    assert resp.status_code == 200, resp.text
    return {p.get("titular") for p in resp.json()["propostes"]}


def test_importar_assignacions_fa_servir_l_horari_de_les_dates_planificades(client):
    assert professor_que_plega() in _titulars_proposats(client)       # avui hi és
    _planifica(client, FUTUR)
    assert professor_que_plega() not in _titulars_proposats(client)   # a l'horari nou, no


def test_les_assignacions_obsoletes_es_comproven_amb_l_horari_planificat(client):
    # Importades de l'horari d'avui; després es planifiquen dates de l'horari nou
    propostes = client.get("/api/config/importar-assignacions/preview").json()["propostes"]
    assert client.post("/api/config/importar-assignacions",
                       json={"propostes": propostes, "overwrite": True}).status_code == 200
    assert client.get("/api/config/assignacions-obsoletes").json()["assignacions"] == []
    _planifica(client, FUTUR)
    obsoletes = client.get("/api/config/assignacions-obsoletes").json()["assignacions"]
    assert obsoletes and {a["titular"] for a in obsoletes} == {professor_que_plega()}


def test_els_professors_es_poden_demanar_per_a_una_data(client):
    futurs = client.get("/api/professors", params={"data": FUTUR[0]}).json()["professors"]
    assert professor_que_plega() not in futurs
    assert professor_que_plega() in client.get("/api/professors").json()["professors"]
