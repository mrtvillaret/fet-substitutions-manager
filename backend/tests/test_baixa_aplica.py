"""
En desar una baixa (absencia_coberta/services.py), d'avui endavant: s'esborren les
absències del professor, se'l treu de vigilant i de substitut, i les files
queden pendents. Els dies passats no es toquen.

Dilluns, horari d'exemple: Prof 3 fa guàrdia a les 10:00 i té classe (ViP,
1-ESO-C) a les 11:30; Prof 15 fa Anglès a les 10:00.
"""

import uuid
from datetime import date, timedelta

import pytest
from fastapi import Depends
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio

from absencia_coberta.router import router as absencia_coberta_router
from auth.dependencies import get_current_user
from prioritats.router import router as prioritats_router
from rate_limit import limiter
from routes import horari, substitucions
from vigilancies.router import router as vigilancies_router

APP = crea_app(substitucions.router, vigilancies_router, prioritats_router, absencia_coberta_router)
# Com a main.py: el router de l'horari agafa el centre de la sessió
APP.include_router(horari.router, dependencies=[Depends(get_current_user)])
_avui = date.today()
FUTUR = (_avui + timedelta(days=7 - _avui.weekday())).isoformat()  # dilluns vinent
PASSAT = (_avui - timedelta(days=_avui.weekday() + 7)).isoformat()  # dilluns de fa una setmana


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


def _files(client, data):
    return client.get(f"/api/substitucions/{data}", params={"include_all": True}).json()


def _absencia(client, data, professor, hores):
    resp = client.put(
        f"/api/substitucions/{data}/absencies/{professor}", json={"hores_absencia": hores, "updated_at_map": {}}
    )
    assert resp.status_code == 200, resp.text


def _substitut_de_prof_15(client, data, substitut=None):
    fila = next(s for s in _files(client, data) if s["hora"] == "10:00" and s["professor_absent"] == "Prof 15")
    if substitut is not None:
        resp = client.put(
            f"/api/substitucions/{data}/10:00/Prof 15", json={"substitut": substitut, "updated_at": fila["updated_at"]}
        )
        assert resp.status_code == 200, resp.text
        return substitut
    return fila["substitut"]


def _prepara(client, data):
    _absencia(client, data, "Prof 15", ["10:00"])
    _substitut_de_prof_15(client, data, "Prof 3")
    _absencia(client, data, "Prof 3", ["12:30"])
    resp = client.post(
        f"/api/vigilancies/{data}",
        json={
            "hora": "11:30",
            "tipus": "Anglès",
            "grups": "2-BAT-A",
            "aula": "A1",
            "vigilant": "Prof 3",
            "comentaris": "",
            "nivell": "2-BAT",
        },
    )
    assert resp.status_code == 200, resp.text


def _vigilant(client, data):
    return client.get(f"/api/vigilancies/{data}").json()[0]["vigilant"]


def _baixa(client, inici, final):
    resp = client.post(
        "/api/absencies-cobertes",
        json={"professor": "Prof 3", "data_inici": inici, "data_final": final, "motiu": ""},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_la_baixa_treu_absencies_vigilancies_i_substitucions_d_avui_endavant(client):
    _prepara(client, FUTUR)
    assert any(s["professor_absent"] == "Prof 3" for s in _files(client, FUTUR))

    canvis = _baixa(client, PASSAT, FUTUR)["canvis"]

    files = _files(client, FUTUR)
    assert not any(s["professor_absent"] == "Prof 3" for s in files)  # absència i cobertura de la seva classe
    assert _substitut_de_prof_15(client, FUTUR) == ""
    assert _vigilant(client, FUTUR) == ""
    assert canvis["absencies_esborrades"] == [{"data": FUTUR, "hora": "12:30"}]
    assert [(v["data"], v["hora"]) for v in canvis["vigilancies_buidades"]] == [(FUTUR, "11:30")]
    assert [(t["data"], t["substitut"], t["motiu"]) for t in canvis["substituts_trets"]] == [(FUTUR, "Prof 3", "baixa")]


def test_els_dies_passats_no_es_toquen(client):
    _prepara(client, PASSAT)

    canvis = _baixa(client, PASSAT, FUTUR)["canvis"]

    assert _substitut_de_prof_15(client, PASSAT) == "Prof 3"
    assert _vigilant(client, PASSAT) == "Prof 3"
    assert any(s["professor_absent"] == "Prof 3" and s["hora"] == "12:30" for s in _files(client, PASSAT))
    assert canvis == {"absencies_esborrades": [], "vigilancies_buidades": [], "substituts_trets": []}


def test_allargar_la_baixa_tambe_s_aplica(client):
    _prepara(client, FUTUR)
    baixa = _baixa(client, PASSAT, PASSAT)  # acabada: no toca res
    assert _substitut_de_prof_15(client, FUTUR) == "Prof 3"

    resp = client.put(
        f"/api/absencies-cobertes/{baixa['id']}",
        json={"professor": "Prof 3", "data_inici": PASSAT, "data_final": FUTUR, "motiu": ""},
    )
    assert resp.status_code == 200, resp.text

    assert _substitut_de_prof_15(client, FUTUR) == ""
    assert _vigilant(client, FUTUR) == ""
    assert resp.json()["canvis"]["absencies_esborrades"] == [{"data": FUTUR, "hora": "12:30"}]


def test_no_es_pot_marcar_absent_un_professor_de_baixa(client):
    _absencia(client, FUTUR, "Prof 15", ["10:00"])
    resp = client.post(
        "/api/absencies-cobertes",
        json={"professor": "Prof 15", "data_inici": PASSAT, "data_final": FUTUR, "motiu": ""},
    )
    assert resp.status_code == 200, resp.text
    assert not any(s["professor_absent"] == "Prof 15" for s in _files(client, FUTUR))  # la baixa les ha tretes

    resp = client.put(
        f"/api/substitucions/{FUTUR}/absencies/Prof 15", json={"hores_absencia": ["10:00"], "updated_at_map": {}}
    )
    assert resp.status_code == 400 and "té una absència coberta" in resp.json()["detail"]
    resp = client.post(
        f"/api/substitucions/{FUTUR}/nova",
        json={"professor": "Prof 15", "hores": ["10:00"], "tipus_absencia": "ABSENCIA"},
    )
    assert resp.status_code == 400 and "té una absència coberta" in resp.json()["detail"]
    assert not any(s["professor_absent"] == "Prof 15" for s in _files(client, FUTUR))

    # Treure-li absències sí que es pot
    resp = client.put(
        f"/api/substitucions/{FUTUR}/absencies/Prof 15", json={"hores_absencia": [], "updated_at_map": {}}
    )
    assert resp.status_code == 200, resp.text


def test_la_llista_de_professors_dona_a_part_qui_te_una_absencia_coberta_aquell_dia(client):
    resp = client.post(
        "/api/absencies-cobertes",
        json={"professor": "Prof 15", "data_inici": FUTUR, "data_final": FUTUR, "motiu": ""},
    )
    assert resp.status_code == 200, resp.text

    llista = client.get("/api/horari/professors", params={"data": FUTUR}).json()
    assert llista["absencies_cobertes"] == [{"professor": "Prof 15", "data_final": FUTUR}]
    assert "Prof 15" not in llista["professors"]  # no es pot triar: la pantalla el mostra a part
    passat = client.get("/api/horari/professors", params={"data": PASSAT}).json()
    assert passat["absencies_cobertes"] == [] and "Prof 15" in passat["professors"]
    assert "absencies_cobertes" not in client.get("/api/horari/professors").json()
    assert client.get("/api/horari/professors", params={"data": "x"}).status_code == 400
