"""
Comprovació de fum contra un backend ja engegat.

Aquest mòdul no arrenca res: si a BASE_URL no hi respon ningú, es salta
sencer. Les credencials surten de l'entorn, les mateixes que el .env del
backend, perquè els endpoints demanen sessió.

    pip install -r requirements-dev.txt
    uvicorn main:app &            # en una altra terminal
    pytest tests/test_api.py
"""
import os
from datetime import datetime

import pytest

requests = pytest.importorskip(
    "requests", reason="instal·la requirements-dev.txt per a les proves"
)

BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8000")
USERNAME = os.getenv("ADMIN_USERNAME", "super_admin")
PASSWORD = os.getenv("ADMIN_PASSWORD", "")


@pytest.fixture(scope="module")
def sessio():
    """Sessió autenticada, o skip si no hi ha backend a l'altra banda."""
    client = requests.Session()
    try:
        client.get(BASE_URL, timeout=2)
    except requests.exceptions.RequestException:
        pytest.skip(f"cap backend escoltant a {BASE_URL}")

    if not PASSWORD:
        pytest.skip("cal ADMIN_PASSWORD a l'entorn per poder entrar")

    resposta = client.post(
        f"{BASE_URL}/api/login",
        json={"username": USERNAME, "password": PASSWORD},
        timeout=5,
    )
    if resposta.status_code != 200:
        pytest.skip(f"login rebutjat per a {USERNAME}: {resposta.status_code}")
    return client


def test_health(sessio):
    assert sessio.get(f"{BASE_URL}/", timeout=5).status_code == 200


def test_config(sessio):
    resposta = sessio.get(f"{BASE_URL}/api/config", timeout=5)
    assert resposta.status_code == 200
    dades = resposta.json()
    assert dades["num_professors"] >= 0
    assert dades["num_hores"] >= 0


def test_professors(sessio):
    resposta = sessio.get(f"{BASE_URL}/api/professors", timeout=5)
    assert resposta.status_code == 200
    assert isinstance(resposta.json()["professors"], list)


def test_hores(sessio):
    resposta = sessio.get(f"{BASE_URL}/api/hores", timeout=5)
    assert resposta.status_code == 200
    assert isinstance(resposta.json()["hores"], list)


@pytest.fixture(scope="module")
def amb_horari(sessio):
    """Skip si la institució encara no té cap XML d'horari carregat."""
    dades = sessio.get(f"{BASE_URL}/api/professors", timeout=5).json()
    if dades.get("xml_missing"):
        pytest.skip("la institució no té cap XML d'horari carregat")
    return sessio


def test_substitucions(amb_horari):
    avui = datetime.now().strftime("%Y-%m-%d")
    resposta = amb_horari.get(f"{BASE_URL}/api/substitucions/{avui}", timeout=10)
    assert resposta.status_code == 200
    assert isinstance(resposta.json(), list)
