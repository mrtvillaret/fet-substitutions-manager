"""La publicació i les cobertures derivades es confirmen alhora."""

import uuid

import pytest
from fastapi.testclient import TestClient
from suport_api import crea_app, crea_usuari, entra, nova_institucio

from absencia_coberta.router import router as absencia_coberta_router
from database import get_data_db_session
from models import GrupAlliberat, Vigilancia
from routes import scheduler
from substitucions import cobertures
from substitucions import router as substitucions_router
from substitucions.repositories import SubstitucioRepository
from vigilancies.router import router as vigilancies_router

DATA = "2026-04-20"
URL = "/api/scheduler/publicar"
APP = crea_app(scheduler.router, vigilancies_router, substitucions_router.router, absencia_coberta_router)


@pytest.fixture
def centre():
    return nova_institucio(amb_xml=True)


@pytest.fixture
def client(centre):
    nom = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, centre, "admin")
    client_sense_excepcions = TestClient(APP, base_url="https://testserver", raise_server_exceptions=False)
    return entra(client_sense_excepcions, nom)


def _horari(grup):
    return {
        "dies": [
            {
                "dia": "Dilluns",
                "data": DATA,
                "sessions": [
                    {
                        "hora": "10:00",
                        "sessions_simultanees": [
                            {
                                "curs": "1-BAT",
                                "nom": "Filosofia",
                                "examens": [{"grup": grup, "aula": "A01", "assignatura": "Filosofia"}],
                            }
                        ],
                    }
                ],
            }
        ]
    }


def _publica(client, grup):
    return client.post(
        URL,
        json={
            "horari": _horari(grup),
            "setmanes": [{"Dilluns": DATA}],
            "opcions": {"auto_assign_titulars": False, "netejar_existents": False},
        },
    )


def _bolcat(centre):
    with get_data_db_session(centre) as db:
        vigilancies = db.query(Vigilancia).filter(Vigilancia.data == DATA).order_by(Vigilancia.id).all()
        grups = db.query(GrupAlliberat).filter(GrupAlliberat.data == DATA).order_by(GrupAlliberat.id).all()
        return {
            "vigilancies": [
                (
                    fila.id,
                    fila.hora,
                    fila.tipus,
                    fila.grups,
                    fila.aula,
                    fila.vigilant,
                    fila.comentaris,
                    fila.nivell,
                    fila.ordre,
                )
                for fila in vigilancies
            ],
            "grups": [(fila.id, fila.hora, fila.grups) for fila in grups],
            "substitucions": sorted(SubstitucioRepository.get_by_date(db, DATA), key=lambda fila: fila["id"]),
        }


def test_publicar_desfa_vigilancies_grups_i_cobertures_si_falla_el_refresc(client, centre, monkeypatch):
    resposta = _publica(client, "1-BAT-A")
    assert resposta.status_code == 200 and resposta.json()["success"], resposta.text
    [vigilancia] = client.get(f"/api/vigilancies/{DATA}").json()
    resposta = client.put(
        f"/api/vigilancies/{DATA}/{vigilancia['id']}",
        json={"vigilant": "Prof 15", "updated_at": vigilancia["updated_at"]},
    )
    assert resposta.status_code == 200, resposta.text
    abans = _bolcat(centre)
    refresca_real = cobertures.refresca_cobertures

    def refresca_i_falla(*args, **kwargs):
        refresca_real(*args, **kwargs)
        raise RuntimeError("error simulat després de refrescar cobertures")

    monkeypatch.setattr(cobertures, "refresca_cobertures", refresca_i_falla)

    resposta = _publica(client, "1-BAT-B")

    assert resposta.status_code == 500
    assert "error_ref" in resposta.json()
    assert _bolcat(centre) == abans
