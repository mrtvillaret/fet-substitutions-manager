"""Backend e2e real amb dades temporals i només les credencials de prova rebudes."""

import json
import os
import sys
import tempfile
from pathlib import Path

backend = Path(__file__).resolve().parents[2] / "backend"
carpeta = Path(tempfile.mkdtemp(prefix="gestor-e2e-"))
# Entorn propi: cap .env, registre, recuperació ni camí de dades heretat.
variables = {
    clau: os.environ[clau]
    for clau in ("PATH", "LANG", "SYSTEMROOT")
    if clau in os.environ
}
variables.update(json.loads(sys.argv[1]))
variables.update(
    DATA_DIR=str(carpeta),
    AUTH_DB_PATH=str(carpeta / "auth.db"),
    APP_CONFIG_PATH=str(carpeta / "config.json"),
    ACCESS_LOG_PATH=str(carpeta / "access.log"),
    PYTHON_DOTENV_DISABLED="1",
    ENVIRONMENT="development",
    COOKIE_SECURE="false",
    APP_INSTITUCIO="centre_e2e",
    SECRET_KEY="clau-publica-exclusiva-del-backend-temporal-e2e",
)
(carpeta / "config.json").write_text('{"idioma":"ca","institucio":"centre_e2e"}')
print(f"Dades temporals e2e: {carpeta}", flush=True)
os.chdir(backend)
os.execve(
    sys.executable,
    [
        sys.executable,
        "-m",
        "uvicorn",
        "main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8765",
    ],
    variables,
)
