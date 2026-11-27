"""La publicació i les cobertures derivades es confirmen alhora."""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from suport_api import crea_app, crea_usuari, entra, nova_institucio
from suport_noms import unic

from absencia_coberta.router import router as absencia_coberta_router
from database import get_data_db_session
from models import GrupAlliberat, Vigilancia
from planificador import router as scheduler
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
    nom = f"admin_{unic()}"
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
            "substitucions": sorted(
                SubstitucioRepository.get_by_date(db, date.fromisoformat(DATA)), key=lambda fila: fila.id
            ),
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

    # Un error controlat (abans un 500), amb referència, i no es desa res
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["success"] is False
    [error] = resposta.json()["errors"]
    assert "cobertures" in error and "ref " in error
    assert _bolcat(centre) == abans


def test_una_sessio_repetida_a_la_peticio_crea_una_sola_vigilancia(client, centre):
    """La mateixa (hora, nivell, grup, aula) dues vegades a la petició (un horari editat amb
    una sessió duplicada) feia dues files."""
    horari = _horari("1-BAT-A")
    franja = horari["dies"][0]["sessions"][0]
    franja["sessions_simultanees"] *= 2
    resposta = client.post(
        URL,
        json={
            "horari": horari,
            "setmanes": [{"Dilluns": DATA}],
            "opcions": {"auto_assign_titulars": False, "netejar_existents": False},
        },
    )
    assert resposta.status_code == 200 and resposta.json()["success"], resposta.text
    assert resposta.json()["vigilancies_creades"] == 1
    assert len(_bolcat(centre)["vigilancies"]) == 1


def test_dos_examens_a_la_mateixa_aula_i_hora_en_fan_una_i_avisen(client, centre):
    """Dos exàmens diferents del mateix grup a la mateixa aula i hora (un conflicte publicat
    igualment): una sola vigilància, la del primer, i un avís amb tots dos."""
    horari = _horari("1-BAT-A")
    sessions = horari["dies"][0]["sessions"][0]["sessions_simultanees"]
    sessions.append(
        {**sessions[0], "nom": "Història", "examens": [{**sessions[0]["examens"][0], "assignatura": "Història"}]}
    )
    resposta = client.post(
        URL,
        json={
            "horari": horari,
            "setmanes": [{"Dilluns": DATA}],
            "opcions": {"auto_assign_titulars": False, "netejar_existents": False},
        },
    )
    assert resposta.status_code == 200 and resposta.json()["success"], resposta.text
    assert [v[2] for v in _bolcat(centre)["vigilancies"]] == ["Filosofia"]
    assert resposta.json()["avisos"] == [
        {
            "codi": "examens_mateixa_aula_i_hora",
            "params": {
                "data": DATA,
                "hora": "10:00",
                "grups": "1-BAT-A",
                "aula": "A01",
                "assignatura": "Filosofia",
                "altra": "Història",
            },
        }
    ]
