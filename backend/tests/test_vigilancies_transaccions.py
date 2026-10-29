"""Atomicitat entre vigilàncies i les substitucions que en deriven."""

import uuid

import pytest
from fastapi.testclient import TestClient
from suport_api import crea_app, crea_usuari, entra, nova_institucio

from database import get_data_db_session
from substitucions import router as substitucions_router
from substitucions.repositories import SubstitucioRepository
from vigilancies import services
from vigilancies.repositories import VigilanciaRepository
from vigilancies.router import router as vigilancies_router

DATA = "2026-04-20"
URL = f"/api/vigilancies/{DATA}"
APP = crea_app(vigilancies_router, substitucions_router.router)


@pytest.fixture
def centre():
    return nova_institucio(amb_xml=True)


@pytest.fixture
def client(centre):
    nom = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, centre, "admin")
    client_sense_excepcions = TestClient(APP, base_url="https://testserver", raise_server_exceptions=False)
    return entra(client_sense_excepcions, nom)


def _crea(client, hora="10:00", grups="2-BAT-A"):
    resposta = client.post(
        URL,
        json={
            "hora": hora,
            "tipus": "Anglès",
            "grups": grups,
            "aula": "A1",
            "vigilant": "Prof 15",
            "comentaris": "",
            "nivell": "2-BAT",
        },
    )
    assert resposta.status_code == 200, resposta.text
    return resposta.json()["vigilancia"]


def _bolcat(centre):
    with get_data_db_session(centre) as db:
        vigilancies = [v for files in VigilanciaRepository.get_by_date(db, DATA).values() for v in files]
        substitucions = SubstitucioRepository.get_by_date(db, DATA)
        return {
            "vigilancies": sorted(vigilancies, key=lambda fila: fila["id"]),
            "substitucions": sorted(substitucions, key=lambda fila: fila["id"]),
        }


def test_editar_desfa_vigilancia_i_cobertures_si_falla_la_reconciliacio(client, centre, monkeypatch):
    vigilancia = _crea(client)
    abans = _bolcat(centre)
    refresca_real = services.refresca_cobertures

    def refresca_i_falla(*args, **kwargs):
        refresca_real(*args, **kwargs)
        raise RuntimeError("error simulat després de refrescar cobertures")

    monkeypatch.setattr(services, "refresca_cobertures", refresca_i_falla)

    resposta = client.put(
        f"{URL}/{vigilancia['id']}",
        json={"vigilant": "", "updated_at": vigilancia["updated_at"]},
    )

    assert resposta.status_code == 500
    assert _bolcat(centre) == abans


def test_buidar_desfa_tots_els_vigilants_si_falla_una_de_les_hores(client, centre, monkeypatch):
    _crea(client, hora="10:00", grups="2-BAT-A")
    _crea(client, hora="11:30", grups="2-BAT-B")
    abans = _bolcat(centre)
    refresca_real = services.refresca_cobertures

    def refresca_i_falla(*args, **kwargs):
        refresca_real(*args, **kwargs)
        raise RuntimeError("error simulat a la primera hora")

    monkeypatch.setattr(services, "refresca_cobertures", refresca_i_falla)

    assert client.post(f"{URL}/clear").status_code == 500
    assert _bolcat(centre) == abans
