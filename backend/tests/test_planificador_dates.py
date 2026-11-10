"""
El planificador fa servir la data de la petició (les dependències de
dependencies.py), no date.today(): el curs actual és el del dia d'avui de la
petició (dia_d_avui) i, sense cap data a l'horari editat, el recàlcul fa
servir la del planificador (dia_de_la_planificacio). Si no hi ha horari
(XML) per a la data, el missatge és en català i diu la data.
"""

import uuid
from dataclasses import dataclass
from datetime import date

import pytest
from fastapi.testclient import TestClient
from suport_api import crea_app, crea_usuari, entra, nova_institucio

from cursos.repositories import CursRepository
from database import get_data_db_session
from dependencies import dia_d_avui, dia_de_la_planificacio
from horari.domain import Dia
from planificador import planificacio
from planificador.router import router
from rate_limit import limiter

APP = crea_app(router)
DATA = "2026-04-20"  # dilluns, curs 2025-2026
SENSE_HORARI = "No hi ha cap horari (XML) per al 20/04/2026"


@dataclass(frozen=True)
class DiaSenseHorari:
    data: date
    institucio: str
    xml_path = None

    @property
    def iso(self):
        return self.data.isoformat()


@pytest.fixture(autouse=True)
def _net():
    limiter.reset()
    yield
    APP.dependency_overrides.clear()


@pytest.fixture
def centre():
    centre = nova_institucio(amb_xml=True)
    with get_data_db_session(centre) as db:
        CursRepository.create(db, "2025-2026", date(2025, 9, 1))
        CursRepository.create(db, "2026-2027", date(2026, 9, 1))
        db.commit()
    return centre


@pytest.fixture
def client(centre):
    nom = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, centre, "admin")
    return entra(TestClient(APP, base_url="https://testserver", raise_server_exceptions=False), nom)


def _avui_es(centre, data):
    APP.dependency_overrides[dia_d_avui] = lambda: Dia.de_text(data, centre)


def test_el_curs_actual_es_el_del_dia_de_la_peticio(client, centre):
    _avui_es(centre, "2026-05-04")  # encara és el curs 2025-2026
    assert client.get("/api/scheduler/curs-dates", params={"dates": DATA}).json() == {"curs_anterior": None}
    _avui_es(centre, "2026-10-05")
    assert client.get("/api/scheduler/curs-dates", params={"dates": DATA}).json() == {
        "curs_anterior": {"cursos": ["2025-2026"], "curs_actual": "2026-2027"}
    }


def test_publicar_compara_amb_el_curs_del_dia_de_la_peticio(client, centre):
    _avui_es(centre, "2026-05-04")
    resp = client.post(
        "/api/scheduler/publicar",
        json={"horari": {"dies": [{"dia": "Dilluns", "data": DATA, "sessions": []}]}, "setmanes": [{"Dilluns": DATA}]},
    )
    assert resp.status_code == 200, resp.text


def test_sense_data_el_recalcul_fa_servir_la_del_planificador(client, centre):
    APP.dependency_overrides[dia_de_la_planificacio] = lambda: DiaSenseHorari(date(2026, 4, 20), centre)
    resp = client.post(
        "/api/scheduler/recalcular-cost", json={"horari": {"dies": [{"dia": "Dilluns", "sessions": []}]}}
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == SENSE_HORARI


def test_generar_sense_horari_ho_diu_en_catala(client, centre, monkeypatch):
    monkeypatch.setattr(
        planificacio.Dia, "de_text", lambda data, institucio=None: DiaSenseHorari(date(2026, 4, 20), centre)
    )
    resp = client.post("/api/scheduler/generate", json={"data_inici": DATA, "selected_dates": [DATA]})
    assert resp.status_code == 400
    assert resp.json()["detail"] == SENSE_HORARI
