"""
Assignar pendents: cada professor vigila el grup amb qui tenia classe a
aquella hora, també quan el titular d'un examen ja és en un altre grup.

Dilluns 20/04/2026 a les 10:00, horari d'exemple:
  2-ESO-A Prof 33 (Matemàtiques), 2-ESO-B Prof 38 (Castellà),
  2-ESO-C Prof 45 (Socials), 3-ESO-B Prof 41 (Castellà);
  guàrdia: Prof 3, 21, 28.
Els quatre grups fan examen (són sense classe), i el titular de l'examen de
2-ESO-A és un altre professor.
"""

import uuid

import pytest
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio

from database import get_data_db_session
from grups.repositories import GrupsAlliberatsRepository
from models import ConfiguracioExamen
from rate_limit import limiter
from vigilancies.router import router as vigilancies_router

APP = crea_app(vigilancies_router)
DATA = "2026-04-20"  # dilluns
URL = f"/api/vigilancies/{DATA}"
EXAMENS = [("Matemàtiques", "2-ESO-A"), ("Castellà", "2-ESO-B"), ("Socials", "2-ESO-C")]


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


def _assigna(titular, ordre=EXAMENS, alliberats=("2-ESO-A", "2-ESO-B", "2-ESO-C", "3-ESO-B")):
    centre = nova_institucio(amb_xml=True)
    with get_data_db_session(centre) as db:
        GrupsAlliberatsRepository.set_for_date(db, DATA, {"10:00": list(alliberats)})
        db.add(ConfiguracioExamen(assignatura="Matemàtiques", grup="2-ESO-A", titular=titular, aula=""))
        db.commit()
    nom = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, centre, "admin")
    client = entra(client_per(APP), nom)
    for tipus, grup in ordre:
        body = {"hora": "10:00", "tipus": tipus, "grups": grup, "aula": "A1", "vigilant": "", "nivell": "2-ESO"}
        assert client.post(URL, json=body).status_code == 200
    assert client.post(f"{URL}/assign/pendents").status_code == 200
    return {v["grups"]: v["vigilant"] for v in client.get(URL).json()}


@pytest.mark.parametrize("titular", ["Prof 41", "Prof 3"], ids=["titular alliberat", "titular de guàrdia"])
@pytest.mark.parametrize("ordre", [EXAMENS, EXAMENS[::-1]], ids=["A-B-C", "C-B-A"])
def test_cada_professor_vigila_el_seu_grup_despres_del_titular(titular, ordre):
    vigilants = _assigna(titular, ordre)
    assert vigilants["2-ESO-A"] == titular
    assert vigilants["2-ESO-B"] == "Prof 38"
    assert vigilants["2-ESO-C"] == "Prof 45"
