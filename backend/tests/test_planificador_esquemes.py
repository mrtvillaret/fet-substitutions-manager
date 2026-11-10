"""
Entrades del planificador amb esquema: un camp d'un tipus que no toca, 422;
una data que no és AAAA-MM-DD, 400 (parametres.DataISO). Els noms d'examen
(fixats, preferències, grups de durada) i de professor arriben nets.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from suport_api import crea_app, crea_usuari, entra, nova_institucio

from database import get_data_db_session
from models import ExamRestriccio
from planificador.router import router
from rate_limit import limiter

APP = crea_app(router)
DIA_SENSE_SESSIONS = {"dies": [{"dia": "Dilluns", "sessions": []}]}


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


@pytest.fixture
def centre():
    return nova_institucio(amb_xml=True)


@pytest.fixture
def client(centre):
    nom = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, centre, "admin")
    return entra(TestClient(APP, base_url="https://testserver", raise_server_exceptions=False), nom)


@pytest.mark.parametrize(
    "metode, ruta, cos",
    [
        ("put", "/api/scheduler/config", {"durada_titular": "x"}),
        ("put", "/api/scheduler/config", {"durada_examen": None}),
        ("put", "/api/scheduler/config", {"nivells_actius": "1-BAT"}),
        (
            "put",
            "/api/scheduler/config",
            {"alliberaments_per_nivell": {"1-BAT": {"config": {"2026-04-20": {"09:00": {"a": "potser"}}}}}},
        ),
        ("put", "/api/scheduler/config", {"durades_grups": [{"assignatures": "Anglès (1-BAT)", "durada": 2}]}),
        ("put", "/api/scheduler/costos-professors", {"globals": {"substitucio": "x"}}),
        ("put", "/api/scheduler/costos-professors", {"globals": {"inventat": 5}}),
        ("put", "/api/scheduler/costos-professors", {"individuals": {"Prof 9": {"substitucio": "x"}}}),
        ("put", "/api/scheduler/restriccions", {"restriccions": {"pesos_optimitzacio": {"equilibri": "x"}}}),
        (
            "put",
            "/api/scheduler/restriccions",
            {"restriccions": {"preferencies": {"mateix_dia": [{"assignatures": "A"}]}}},
        ),
    ],
)
def test_un_camp_d_un_tipus_que_no_toca_dona_422(client, metode, ruta, cos):
    assert getattr(client, metode)(ruta, json=cos).status_code == 422


@pytest.mark.parametrize(
    "metode, ruta, cos",
    [
        ("put", "/api/scheduler/dates", {"selected_dates": ["2026-13-01"]}),
        ("post", "/api/scheduler/generate", {"data_inici": "2026-04-20", "data_final": "2026-04-99"}),
        ("post", "/api/scheduler/generate", {"data_inici": "2026-04-20", "selected_dates": ["20/04/2026"]}),
        ("post", "/api/scheduler/analisi", {"data_inici": "dilluns"}),
        ("post", "/api/scheduler/recalcular-cost", {"horari": DIA_SENSE_SESSIONS, "data_referencia": "abril"}),
        ("post", "/api/scheduler/recalcular-cost", {"horari": DIA_SENSE_SESSIONS, "selected_dates": ["2026-04-32"]}),
        ("post", "/api/scheduler/publicar", {"horari": DIA_SENSE_SESSIONS, "setmanes": [{"Dilluns": "2026-04-32"}]}),
    ],
)
def test_una_data_que_no_es_aaaa_mm_dd_dona_400(client, metode, ruta, cos):
    resp = getattr(client, metode)(ruta, json=cos)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Format de data invàlid. Usa YYYY-MM-DD"


def _restriccions(centre):
    with get_data_db_session(centre) as db:
        return {(r.tipus, r.clau, r.configuracio) for r in db.query(ExamRestriccio).all()}


def test_els_examens_fixats_tenen_el_nom_net(client, centre):
    client.post(
        "/api/scheduler/restriccions/pin",
        json={"pins": [{"nom": " Català (1-BAT) ", "dia": "Dilluns", "hora": "09:00"}]},
    )
    assert _restriccions(centre) == {
        ("assignatures_dia_fix", "Català (1-BAT)", '"Dilluns"'),
        ("assignatures_hora_fix", "Català (1-BAT)", '"09:00"'),
    }
    client.post("/api/scheduler/restriccions/pin", json={"unpins": [" Català (1-BAT) "]})
    assert _restriccions(centre) == set()


def test_les_preferencies_tenen_els_noms_nets(client, centre):
    cos = {"restriccions": {"preferencies": {"mateix_dia": [{"assignatures": [" Anglès (1-BAT) ", "Català (1-BAT)"]}]}}}
    assert client.put("/api/scheduler/restriccions", json=cos).status_code == 200
    assert _restriccions(centre) == {("mateix_dia", None, '["Anglès (1-BAT)", "Català (1-BAT)"]')}


def test_els_grups_de_durada_tenen_els_noms_nets(client):
    cos = {"durades_grups": [{"nom": "Llargs", "assignatures": [" Anglès (1-BAT) "], "durada": 2, "durada_examen": 2}]}
    assert client.put("/api/scheduler/config", json=cos).status_code == 200
    assert client.get("/api/scheduler/config").json()["durades_grups"][0]["assignatures"] == ["Anglès (1-BAT)"]
