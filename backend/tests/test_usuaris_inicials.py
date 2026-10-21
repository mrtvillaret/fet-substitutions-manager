"""
Els usuaris inicials (crea_usuaris_inicials, en arrencar):
- es creen només si la taula d'usuaris és buida (instal·lació nova);
- després no es toquen mai sols: un usuari inicial desactivat o modificat des
  de la web es queda així en reiniciar;
- el superadmin només es recupera amb ADMIN_PASSWORD_RECUPERACIO, i sense
  aquesta variable mai no se li sobreescriu la contrasenya.

Cada arrencada és un procés a part: config/auth.py llegeix l'entorn en
importar-se. Les BD són temporals.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent

_ARRENCA = """
import json, sys
from auth.services import crea_usuaris_inicials
from auth.repositories import UserRepository
from auth.security import verify_password
from database import AuthSessionLocal, create_auth_tables
create_auth_tables()
for ordre in json.loads(sys.argv[1]):
    exec(ordre)
crea_usuaris_inicials()
with AuthSessionLocal() as db:
    usuaris = {
        u.username: {"role": u.role, "active": u.active, "institucio": u.institucio, "sv": u.versio_sessio,
                     "contrasenyes": [c for c in json.loads(sys.argv[2]) if verify_password(c, u.password_hash)]}
        for u in UserRepository.list_all(db)
    }
print("USUARIS=" + json.dumps(usuaris))
"""

# Abans d'arrencar: modificacions fetes «des de la web»
_DESACTIVA = (
    "with AuthSessionLocal() as db:\n"
    "    for u in UserRepository.list_all(db): UserRepository.update(db, u, active=False, role='user')\n"
    "    db.commit()"
)
_ESBORRA_SUPERADMIN = (
    "with AuthSessionLocal() as db:\n"
    "    UserRepository.delete(db, UserRepository.get_by_username(db, 'super_admin')); db.commit()"
)
CONTRASENYES = ["contrasenya-admin-1", "contrasenya-centre-1", "recuperacio-1234"]


def _arrenca(tmp_path, entorn=None, abans=()):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("ADMIN_", "USER_CENTRE1_"))}
    env.update(DATA_DIR=str(tmp_path), AUTH_DB_PATH=str(tmp_path / "auth.db"), **(entorn or {}))
    sortida = subprocess.run(
        [sys.executable, "-c", _ARRENCA, json.dumps(list(abans)), json.dumps(CONTRASENYES)],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    usuaris = None
    for linia in sortida.stdout.splitlines():
        if linia.startswith("USUARIS="):
            usuaris = json.loads(linia.removeprefix("USUARIS="))
    return sortida, usuaris


INICIALS = {"ADMIN_PASSWORD": "contrasenya-admin-1", "ADMIN_CENTRE1_PASSWORD": "contrasenya-centre-1"}


def test_una_instal_lacio_nova_crea_el_superadmin_i_els_usuaris_amb_contrasenya(tmp_path):
    sortida, usuaris = _arrenca(tmp_path, INICIALS)
    assert sortida.returncode == 0, sortida.stderr
    assert usuaris == {
        "super_admin": {
            "role": "super_admin",
            "active": True,
            "institucio": "exemple",
            "sv": 0,
            "contrasenyes": ["contrasenya-admin-1"],
        },
        "admin_centre1": {
            "role": "admin",
            "active": True,
            "institucio": "exemple",
            "sv": 0,
            "contrasenyes": ["contrasenya-centre-1"],
        },
    }  # user_centre1 no té contrasenya definida: no es crea


def test_una_instal_lacio_nova_sense_admin_password_no_arrenca(tmp_path):
    sortida, _ = _arrenca(tmp_path)
    assert sortida.returncode != 0 and "ADMIN_PASSWORD" in sortida.stderr


def test_en_reiniciar_no_es_reactiva_ni_es_modifica_cap_usuari_inicial(tmp_path):
    _arrenca(tmp_path, INICIALS)
    sortida, usuaris = _arrenca(tmp_path, INICIALS, abans=[_DESACTIVA])
    assert sortida.returncode == 0, sortida.stderr
    assert {nom: (u["role"], u["active"]) for nom, u in usuaris.items()} == {
        "super_admin": ("user", False),
        "admin_centre1": ("user", False),
    }


def test_amb_usuaris_arrenca_sense_admin_password_i_no_crea_el_superadmin(tmp_path):
    _arrenca(tmp_path, INICIALS)
    sortida, usuaris = _arrenca(tmp_path, abans=[_ESBORRA_SUPERADMIN])
    assert sortida.returncode == 0, sortida.stderr
    assert set(usuaris) == {"admin_centre1"}


def test_sense_recuperacio_no_se_sobreescriu_la_contrasenya_del_superadmin(tmp_path):
    _arrenca(tmp_path, INICIALS)
    _, usuaris = _arrenca(tmp_path, {"ADMIN_PASSWORD": "una-altra-contrasenya"})
    assert usuaris["super_admin"]["contrasenyes"] == ["contrasenya-admin-1"]


def test_la_recuperacio_reactiva_el_superadmin_amb_la_contrasenya_i_tanca_sessions(tmp_path):
    _arrenca(tmp_path, INICIALS)
    sortida, usuaris = _arrenca(tmp_path, {"ADMIN_PASSWORD_RECUPERACIO": "recuperacio-1234"}, abans=[_DESACTIVA])
    assert sortida.returncode == 0, sortida.stderr
    assert usuaris["super_admin"] == {
        "role": "super_admin",
        "active": True,
        "institucio": "exemple",
        "sv": 1,
        "contrasenyes": ["recuperacio-1234"],
    }
    assert (usuaris["admin_centre1"]["role"], usuaris["admin_centre1"]["active"]) == ("user", False)
    # L'avís diu explícitament que cal treure la variable de l'entorn
    assert "CAL TREURE LA VARIABLE ADMIN_PASSWORD_RECUPERACIO DE L'ENTORN" in sortida.stderr


def test_la_recuperacio_crea_el_superadmin_si_no_hi_es(tmp_path):
    _arrenca(tmp_path, INICIALS)
    sortida, usuaris = _arrenca(
        tmp_path, {"ADMIN_PASSWORD_RECUPERACIO": "recuperacio-1234"}, abans=[_ESBORRA_SUPERADMIN]
    )
    assert sortida.returncode == 0, sortida.stderr
    assert usuaris["super_admin"]["contrasenyes"] == ["recuperacio-1234"]
    assert usuaris["super_admin"]["role"] == "super_admin" and usuaris["super_admin"]["active"]


def test_una_contrasenya_de_recuperacio_curta_no_arrenca(tmp_path):
    _arrenca(tmp_path, INICIALS)
    sortida, _ = _arrenca(tmp_path, {"ADMIN_PASSWORD_RECUPERACIO": "curta"})
    assert sortida.returncode != 0 and "ADMIN_PASSWORD_RECUPERACIO" in sortida.stderr
