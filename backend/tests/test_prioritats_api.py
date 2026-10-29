"""
Prioritats per l'API (com la pantalla): l'entrada de «No substituir» i el
text buit, que representa les hores de l'XML sense assignatura.
"""

import uuid

import pytest
from fastapi import Depends
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio

from absencia_coberta.router import router as absencia_coberta_router
from auth.dependencies import get_current_user, require_admin
from prioritats.router import router as prioritats_router
from rate_limit import limiter
from substitucions import router as substitucions

APP = crea_app()
APP.include_router(prioritats_router, dependencies=[Depends(require_admin)])  # com a main.py
APP.include_router(absencia_coberta_router, dependencies=[Depends(require_admin)])
APP.include_router(substitucions.router, dependencies=[Depends(get_current_user)])
URL = "/api/prioritats/no-substituir"


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


@pytest.fixture
def client():
    centre = nova_institucio(amb_xml=True)
    nom = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, centre, "admin")
    return entra(client_per(APP), nom)


def test_sense_assignatura_dona_400(client):
    resp = client.post(URL, json={})
    assert resp.status_code == 400 and resp.json() == {"detail": "Assignatura requerida"}


def test_el_text_buit_s_accepta(client):
    # «No substituir» amb text buit: les hores sense assignatura no se substitueixen
    assert client.post(URL, json={"assignatura": ""}).status_code == 200
    assert client.get(URL).json() == {"assignatures": [""]}


def test_una_assignatura_que_ja_hi_es_dona_409(client):
    assert client.post(URL, json={"assignatura": "Tutoria"}).status_code == 200
    resp = client.post(URL, json={"assignatura": "Tutoria"})
    assert resp.status_code == 409 and resp.json() == {"detail": "L'assignatura ja és a «No substituir»"}
    assert client.get(URL).json() == {"assignatures": ["Tutoria"]}


def test_el_text_buit_tampoc_es_pot_repetir(client):
    assert client.post(URL, json={"assignatura": ""}).status_code == 200
    assert client.post(URL, json={"assignatura": ""}).status_code == 409


def test_una_assignatura_que_no_es_text_dona_422(client):
    assert client.post(URL, json={"assignatura": 5}).status_code == 422
    assert client.get(URL).json() == {"assignatures": []}


# Prof 15 (horari d'exemple), dilluns: a les 08:00 no té assignatura, a les 10:00 fa Anglès
DATA = "2026-04-20"


def _absent_i_genera(client):
    resp = client.put(
        f"/api/substitucions/{DATA}/absencies/Prof 15",
        json={"hores_absencia": ["08:00", "10:00"], "updated_at_map": {}},
    )
    assert resp.status_code == 200
    assert client.post(f"/api/substitucions/{DATA}/generar", params={"regenerar_tot": True}).status_code == 200
    files = client.get(f"/api/substitucions/{DATA}", params={"include_all": True}).json()
    pendents = {s["hora"] for s in client.get(f"/api/substitucions/{DATA}").json()}
    return {s["hora"]: s for s in files}, pendents


def test_amb_el_text_buit_les_hores_sense_assignatura_no_se_substitueixen(client):
    assert client.post(URL, json={"assignatura": ""}).status_code == 200
    files, pendents = _absent_i_genera(client)
    assert files["08:00"]["assignatura"] == "" and not files["08:00"]["substitut"]
    assert "08:00" not in pendents  # no surt com a substitució per fer
    assert files["10:00"]["substitut"]  # la classe sí que se substitueix


def test_sense_el_text_buit_l_hora_sense_assignatura_queda_com_a_pendent(client):
    files, pendents = _absent_i_genera(client)
    assert not files["08:00"]["substitut"]
    assert "08:00" in pendents


# ------------------------------------------------ baixes amb una data mal escrita

BAIXES = "/api/absencies-cobertes"
FORMAT_INVALID = {"detail": "Format de data invàlid. Usa YYYY-MM-DD"}


def test_crear_una_baixa_amb_una_data_mal_escrita_dona_400(client):
    for dates in (
        {"data_inici": "dilluns", "data_final": "2026-04-24"},
        {"data_inici": "2026-04-20", "data_final": "24/04/2026"},
    ):
        resp = client.post(BAIXES, json={"professor": "Prof 15", **dates})
        assert resp.status_code == 400 and resp.json() == FORMAT_INVALID
    assert client.get(BAIXES).json() == {"absencies_cobertes": []}


def test_editar_una_baixa_amb_una_data_mal_escrita_dona_400(client):
    baixa = client.post(BAIXES, json={"professor": "Prof 15", "data_inici": "2026-04-20", "data_final": "2026-04-24"})
    baixa_id = baixa.json()["id"]
    resp = client.put(f"{BAIXES}/{baixa_id}", json={"data_final": "divendres"})
    assert resp.status_code == 400 and resp.json() == FORMAT_INVALID
    assert client.get(BAIXES).json()["absencies_cobertes"][0]["data_final"] == "2026-04-24"
