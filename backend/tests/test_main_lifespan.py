"""Importar l'app és declaratiu; la inicialització passa en arrencar-la."""

import json
import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def _executa(tmp_path, codi):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("ADMIN_", "USER_CENTRE1_", "ACCESS_LOG_PATH"))}
    env.update(
        PYTHON_DOTENV_DISABLED="1",
        PYTHONDONTWRITEBYTECODE="1",
        DATA_DIR=str(tmp_path),
        AUTH_DB_PATH=str(tmp_path / "auth.db"),
        APP_CONFIG_PATH=str(tmp_path / "config.json"),
        APP_INSTITUCIO="centre_temporal",
        ADMIN_USERNAME="admin_inicial",
        ADMIN_PASSWORD="contrasenya-del-test-lifespan",
        ADMIN_INSTITUCIO="centre_temporal",
        ACCESS_LOG_PATH=str(tmp_path / "access.log"),
    )
    resultat = subprocess.run(
        [sys.executable, "-c", codi], cwd=BACKEND, env=env, capture_output=True, text=True, timeout=60
    )
    assert resultat.returncode == 0, resultat.stderr
    return json.loads(resultat.stdout.strip().splitlines()[-1])


def test_importar_main_no_crea_fitxers_ni_bd(tmp_path):
    resultat = _executa(
        tmp_path,
        """
import json, os
from pathlib import Path
import main
print(json.dumps(sorted(str(p.relative_to(os.environ['DATA_DIR'])) for p in Path(os.environ['DATA_DIR']).rglob('*'))))
""",
    )
    assert resultat == []


def test_arrencar_main_inicialitza_taules_usuaris_i_prioritats(tmp_path):
    resultat = _executa(
        tmp_path,
        """
import json, os
from pathlib import Path
from fastapi.testclient import TestClient
import main
from auth.repositories import UserRepository
from database import AuthSessionLocal
crides = []
carrega_real = main.carrega_prioritats

def carrega(db):
    crides.append(db.info['institucio'])
    return carrega_real(db)

main.carrega_prioritats = carrega
with TestClient(main.app) as client:
    assert client.get('/api/health').json() == {'status': 'ok'}
    with AuthSessionLocal() as db:
        usuaris = [u.username for u in UserRepository.list_all(db)]
print(json.dumps({'fitxers': sorted(str(p.relative_to(os.environ['DATA_DIR'])) for p in Path(os.environ['DATA_DIR']).rglob('*') if p.is_file()), 'usuaris': usuaris, 'prioritats': crides}))
""",
    )
    assert {"auth.db", "centre_temporal/gestor.db", "access.log"} <= set(resultat["fitxers"])
    assert "admin_inicial" in resultat["usuaris"]
    assert resultat["prioritats"] == ["centre_temporal"]
