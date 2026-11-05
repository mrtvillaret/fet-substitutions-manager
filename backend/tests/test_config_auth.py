"""Configuració d'auth explícita i validada, sense apedaçar constants consumidores."""

import ast
from dataclasses import FrozenInstanceError, is_dataclass
from pathlib import Path

import pytest

from config.auth import ConfigAuth, carrega_config_auth

ENV = {"SECRET_KEY": "clau-inventada-config-auth"}


def test_config_auth_te_defaults_i_no_modifica_l_entorn():
    env = dict(ENV)
    config = carrega_config_auth(env)
    assert isinstance(config, ConfigAuth) and is_dataclass(config)
    assert env == ENV
    assert config.environment == "production"
    assert config.is_development is False
    assert config.algorithm == "HS256"
    assert config.cookie_name == "gestor_token"
    assert config.cookie_secure is True
    assert config.sessio_inactivitat_minuts == 60
    assert config.sessio_maxima_hores == 24
    assert config.sessio_renovacio_minuts == 5
    assert config.usuaris_protegits == frozenset()
    assert config.login_delegacio_usuaris == frozenset()
    assert config.admin_username == "super_admin"
    assert config.admin_password is None
    assert config.admin_password_recuperacio is None
    with pytest.raises(FrozenInstanceError):
        config.cookie_name = "altre"
    assert ENV["SECRET_KEY"] not in repr(config)


def test_config_auth_llegeix_nomes_l_entorn_rebut():
    config = carrega_config_auth(
        {
            **ENV,
            "ENVIRONMENT": " Development ",
            "SECRET_KEY": "admin123",
            "COOKIE_NAME": " demo_token ",
            "COOKIE_SECURE": "FALSE",
            "LOGIN_DELEGACIO_USUARIS": " user_demo, admin_demo, user_demo, ,",
            "LOGIN_DELEGACIO_URL": " /demo/ ",
            "USUARIS_PROTEGITS": " user_demo, ,user_demo ",
            "SESSIO_INACTIVITAT_MINUTS": "42",
            "SESSIO_MAXIMA_HORES": "8",
            "ADMIN_PASSWORD_RECUPERACIO": "",
        }
    )
    assert config.is_development is True
    assert config.cookie_name == "demo_token"
    assert config.cookie_secure is False
    assert config.login_delegacio_usuaris == frozenset({"user_demo", "admin_demo"})
    assert config.login_delegacio_url == "/demo/"
    assert config.usuaris_protegits == frozenset({"user_demo"})
    assert config.sessio_inactivitat_minuts == 42
    assert config.sessio_maxima_hores == 8
    assert config.admin_password_recuperacio is None
    assert carrega_config_auth({**ENV, "COOKIE_NAME": "  "}).cookie_name == "gestor_token"


@pytest.mark.parametrize(
    "nom",
    ["SECRET_KEY", "ADMIN_PASSWORD", "ADMIN_PASSWORD_RECUPERACIO", "ADMIN_CENTRE1_PASSWORD", "USER_CENTRE1_PASSWORD"],
)
def test_config_auth_conserva_el_rebuig_dels_valors_publics(nom):
    with pytest.raises(SystemExit, match="valor de mostra"):
        carrega_config_auth({**ENV, nom: "admin123"})


def test_config_auth_conserva_error_de_clau_absent_i_enters_invalids():
    with pytest.raises(SystemExit, match="SECRET_KEY no està definida"):
        carrega_config_auth({})
    with pytest.raises(ValueError):
        carrega_config_auth({**ENV, "SESSIO_MAXIMA_HORES": "x"})


@pytest.mark.parametrize("url", ["//altre/", "http://altre/", "demo/", "https://"])
def test_config_auth_valida_la_delegacio(url):
    with pytest.raises(SystemExit, match="LOGIN_DELEGACIO_URL"):
        carrega_config_auth({**ENV, "LOGIN_DELEGACIO_USUARIS": "demo", "LOGIN_DELEGACIO_URL": url})


def test_prioritats_te_porta_publica_sense_imports_locals_a_auth():
    backend = Path(__file__).resolve().parents[1]
    for fitxer in ["auth/dependencies.py", "main.py"]:
        tree = ast.parse((backend / fitxer).read_text())
        imports = [
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.ImportFrom)
            and n.module
            and n.module.startswith("prioritats.")
            and any(a.name == "carrega_prioritats" for a in n.names)
        ]
        assert imports
        assert all(n.module == "prioritats.memoria" and n in tree.body for n in imports)


def test_main_llegeix_la_mateixa_galeta_que_auth(config_auth_de_prova, monkeypatch):
    from starlette.requests import Request
    from suport_main import app_sencera

    app_sencera()
    import main

    config_auth_de_prova(COOKIE_NAME="galeta_inventada")
    rebuts = []
    monkeypatch.setattr(main, "decode_access_token", lambda token: rebuts.append(token) or {})
    monkeypatch.setattr(main.access_logger, "info", lambda *_args: None)
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/prova",
            "query_string": b"",
            "headers": [(b"cookie", b"galeta_inventada=testimoni")],
            "client": ("testclient", 0),
        }
    )
    main._log_request(request, 1, 200)
    assert rebuts == ["testimoni"]


@pytest.mark.parametrize(
    "primer", ["auth.dependencies", "prioritats.memoria", "prioritats.services", "config.settings"]
)
def test_imports_en_fred_sense_cicle(primer):
    import os
    import subprocess
    import sys

    resultat = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import {primer}; import auth.dependencies; import prioritats.memoria; import prioritats.services; import config.settings",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHON_DOTENV_DISABLED": "1"},
        capture_output=True,
        text=True,
    )
    assert resultat.returncode == 0, resultat.stderr
