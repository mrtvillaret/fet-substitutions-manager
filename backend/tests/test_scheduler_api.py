"""
API del planificador d'exàmens (routes/scheduler.py).

La configuració desada (nivells seleccionats i alliberaments per nivell) pot
ser d'un horari anterior: si els nivells han canviat de nom o ja no hi són,
no s'han de tornar, perquè el selector de nivells els mostraria com a `null`
i sortirien pestanyes de nivells que no existeixen.
"""
import json
import uuid

import pytest

from database import get_data_db_session
from models import Nivell
from rate_limit import limiter
from repositories import ConfiguracioRepository
from routes import scheduler
from routes.scheduler_service import SCHEDULER_ALLIBERAMENTS_KEY, SCHEDULER_NIVELLS_KEY
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio

APP = crea_app(scheduler.router)
URL = "/api/scheduler/config"

ALLIBERAMENT = {"durada": 1, "dates": ["2026-06-01"], "config": {"2026-06-01": {"09:00": {"a": True, "i": True}}}}


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


@pytest.fixture
def centre():
    institucio = nova_institucio(amb_xml=True)
    with get_data_db_session(institucio) as db:
        for ordre, codi in enumerate(("1r BATX", "2n BATX")):
            db.add(Nivell(codi=codi, nom=codi, ordre=ordre))
        db.commit()
    return institucio


@pytest.fixture
def client(centre):
    nom = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, centre, "admin")
    return entra(client_per(APP), nom)


def _desa(centre, nivells, alliberaments):
    with get_data_db_session(centre) as db:
        ConfiguracioRepository.set(db, SCHEDULER_NIVELLS_KEY, json.dumps(nivells), tipus="json")
        ConfiguracioRepository.set(db, SCHEDULER_ALLIBERAMENTS_KEY, json.dumps(alliberaments), tipus="json")


def test_la_configuracio_torna_els_nivells_seleccionats(client, centre):
    _desa(centre, ["2n BATX"], {"2n BATX": ALLIBERAMENT})
    config = client.get(URL).json()
    assert config["nivells"] == ["1r BATX", "2n BATX"]
    assert config["nivells_seleccionats"] == ["2n BATX"]
    assert list(config["alliberaments_per_nivell"]) == ["2n BATX"]
    assert list(config["hores_per_nivell"]) == ["2n BATX"]


def test_no_es_tornen_nivells_desats_que_ja_no_existeixen(client, centre):
    # Configuració desada amb un horari anterior, amb nivells d'altres noms.
    _desa(centre, ["1º BACH", "2º BACH", "1r BATX"], {"1º BACH": ALLIBERAMENT, "1r BATX": ALLIBERAMENT})
    config = client.get(URL).json()
    assert config["nivells_seleccionats"] == ["1r BATX"]
    assert list(config["alliberaments_per_nivell"]) == ["1r BATX"]
    assert list(config["hores_per_nivell"]) == ["1r BATX"]


def test_nomes_els_admins_veuen_la_configuracio(centre):
    nom = f"user_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, centre, "user")
    assert entra(client_per(APP), nom).get(URL).status_code == 403
