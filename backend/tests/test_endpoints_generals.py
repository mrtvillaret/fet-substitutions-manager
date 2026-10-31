"""
Endpoints generals que no tenen tests propis en cap altre lloc: les hores del
dia (/api/hores) i les comprovacions de salut (/ i /api/health), que són les
que es fan servir per veure si el servidor respon després d'un desplegament.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import Depends
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio

from auth.dependencies import get_current_user
from horari import router as horari
from rate_limit import limiter

BACKEND_DIR = Path(__file__).resolve().parent.parent

APP = crea_app()
APP.include_router(horari.router, dependencies=[Depends(get_current_user)])  # com a main.py


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


def _client(amb_xml):
    institucio = nova_institucio(amb_xml=amb_xml)
    crea_usuari(f"u_{institucio}", institucio)
    return entra(client_per(APP), f"u_{institucio}")


def test_les_hores_surten_en_l_ordre_de_l_xml_amb_el_pati():
    assert _client(amb_xml=True).get("/api/hores").json() == {
        "hores": ["08:00", "09:00", "10:00", "PATI", "11:30", "12:30", "13:30", "14:30", "15:00", "16:00", "17:00"]
    }


def test_sense_horari_les_hores_son_buides_i_ho_diu():
    assert _client(amb_xml=False).get("/api/hores").json() == {"hores": [], "xml_missing": True}


def test_les_hores_demanen_sessio():
    assert client_per(APP).get("/api/hores").status_code == 401


_SALUT = """
from fastapi.testclient import TestClient
import main
client = TestClient(main.app)
for ruta in ("/", "/api/health"):
    resp = client.get(ruta)
    print(ruta, resp.status_code, resp.json()["status"])
"""


def test_les_comprovacions_de_salut_responen_sense_sessio(tmp_path):
    # main.app en un procés a part: en importar-se crea els usuaris per
    # defecte i llegeix l'entorn, i no ha de tocar l'auth.db dels altres tests.
    entorn = dict(
        os.environ,
        DATA_DIR=str(tmp_path),
        AUTH_DB_PATH=str(tmp_path / "auth.db"),
        ADMIN_PASSWORD="contrasenya-del-test-de-salut",
    )
    sortida = subprocess.run(
        [sys.executable, "-c", _SALUT], cwd=BACKEND_DIR, env=entorn, capture_output=True, text=True, timeout=60
    )
    assert sortida.returncode == 0, sortida.stderr
    assert sortida.stdout.strip().splitlines()[-2:] == ["/ 200 ok", "/api/health 200 ok"]
