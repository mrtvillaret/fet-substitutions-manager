"""
CORS: en producció el frontend i l'API són al mateix domini, i cap altre
origen pot fer crides amb la sessió de l'usuari. Els orígens de localhost
només s'accepten en desenvolupament (Vite en un altre port).
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent

_COMPROVA = """
from fastapi.testclient import TestClient
import main
resp = TestClient(main.app).options("/api/login", headers={
    "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
print(resp.headers.get("access-control-allow-origin", "-"))
"""


def _origen_permes(environment, tmp_path):
    # En un procés a part: ENVIRONMENT es llegeix en importar la configuració.
    entorn = dict(os.environ, ENVIRONMENT=environment, DATA_DIR=str(tmp_path),
                  AUTH_DB_PATH=str(tmp_path / "auth.db"),
                  ADMIN_PASSWORD="contrasenya-del-test-cors")
    sortida = subprocess.run([sys.executable, "-c", _COMPROVA], cwd=BACKEND_DIR, env=entorn,
                             capture_output=True, text=True, timeout=60)
    assert sortida.returncode == 0, sortida.stderr
    return sortida.stdout.strip().splitlines()[-1]


@pytest.mark.parametrize("environment, esperat", [
    ("production", "-"),
    ("development", "http://localhost:5173"),
])
def test_cors_nomes_accepta_localhost_en_desenvolupament(environment, esperat, tmp_path):
    assert _origen_permes(environment, tmp_path) == esperat
