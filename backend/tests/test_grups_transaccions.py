"""Els canvis d'alliberats i la reconciliació formen una sola transacció."""

import uuid

import pytest
from fastapi.testclient import TestClient
from suport_api import crea_app, crea_usuari, entra, nova_institucio

from database import get_data_db_session
from grups import router as grups
from grups import services as grups_services
from models import AlliberamentPeriode, GrupAlliberat
from substitucions import cobertures
from substitucions import router as substitucions_router
from substitucions.repositories import SubstitucioRepository

DATA = "2026-04-20"
APP = crea_app(grups.router, substitucions_router.router)


@pytest.fixture
def centre():
    return nova_institucio(amb_xml=True)


@pytest.fixture
def client(centre):
    nom = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, centre, "admin")
    client_sense_excepcions = TestClient(APP, base_url="https://testserver", raise_server_exceptions=False)
    return entra(client_sense_excepcions, nom)


def _prepara_dia_afectat(client):
    resposta = client.put(
        f"/api/substitucions/{DATA}/absencies/Prof 15",
        json={"hores_absencia": ["10:00"], "updated_at_map": {}},
    )
    assert resposta.status_code == 200, resposta.text


def _bolcat(centre):
    with get_data_db_session(centre) as db:
        alliberats = db.query(GrupAlliberat).order_by(GrupAlliberat.id).all()
        periode = db.query(AlliberamentPeriode).order_by(AlliberamentPeriode.id).all()
        return {
            "grups": [(fila.id, fila.data.isoformat(), fila.hora, fila.grups) for fila in alliberats],
            "periode": [
                (
                    fila.id,
                    fila.tipus,
                    fila.clau,
                    fila.dia_setmana,
                    fila.hora,
                    fila.des_de.isoformat(),
                    bool(fila.alliberat),
                )
                for fila in periode
            ],
            "substitucions": sorted(SubstitucioRepository.get_by_date(db, DATA), key=lambda fila: fila["id"]),
        }


def _reconciliacio_que_falla(monkeypatch):
    def genera_i_falla(*_args, **_kwargs):
        raise RuntimeError("error simulat reconciliant substitucions")

    monkeypatch.setattr(grups_services, "genera_substitucions_dia", genera_i_falla)


def test_desar_el_dia_desfa_alliberats_i_derivats_si_falla_la_reconciliacio(client, centre, monkeypatch):
    _prepara_dia_afectat(client)
    abans = _bolcat(centre)
    _reconciliacio_que_falla(monkeypatch)

    resposta = client.put(f"/api/grups/{DATA}", json={"grups": {"10:00": ["3-ESO-A"]}})

    assert resposta.status_code == 500
    assert "error_ref" in resposta.json()
    assert _bolcat(centre) == abans


def test_desar_el_dia_desfa_tot_si_falla_despres_de_refrescar_cobertures(client, centre, monkeypatch):
    _prepara_dia_afectat(client)
    abans = _bolcat(centre)
    refresca_real = cobertures.refresca_cobertures

    def refresca_i_falla(*args, **kwargs):
        refresca_real(*args, **kwargs)
        raise RuntimeError("error simulat després de refrescar cobertures")

    monkeypatch.setattr(grups_services, "refresca_cobertures", refresca_i_falla)

    resposta = client.put(f"/api/grups/{DATA}", json={"grups": {"10:00": ["3-ESO-A"]}})

    assert resposta.status_code == 500
    assert "error_ref" in resposta.json()
    assert _bolcat(centre) == abans


def test_afegir_periode_desfa_el_canvi_si_falla_la_reconciliacio(client, centre, monkeypatch):
    _prepara_dia_afectat(client)
    abans = _bolcat(centre)
    _reconciliacio_que_falla(monkeypatch)

    resposta = client.post(
        "/api/grups/periode",
        json={"tipus": "professor", "clau": "Prof 21", "hores": ["10:00"], "data": DATA},
    )

    assert resposta.status_code == 500
    assert "error_ref" in resposta.json()
    assert _bolcat(centre) == abans
