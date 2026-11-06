"""Resums HTTP sense noms del camí, query ni IP, i retenció explícita."""

import logging
import re
import shlex
from datetime import datetime, timedelta, timezone
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from suport_main import app_sencera


@pytest.fixture
def main(monkeypatch, caplog):
    import importlib

    app_sencera()
    modul = importlib.import_module("main")
    logger = logging.getLogger("prova.access")
    caplog.set_level(logging.INFO, logger=logger.name)
    monkeypatch.setattr(modul, "access_logger", logger)
    monkeypatch.setattr(modul, "get_auth_token", lambda _: "test-token")
    monkeypatch.setattr(
        modul, "decode_access_token", lambda _: {"sub": "usuari", "role": "admin", "institucio": "centre_temporal"}
    )
    return modul


def _missatge(caplog):
    return next(r.getMessage() for r in reversed(caplog.records) if r.name == "prova.access")


def test_api_registra_la_plantilla_i_les_dades_operatives(main, caplog):
    client = TestClient(main.app, base_url="https://testserver", client=("198.51.100.23", 4321))
    resposta = client.put("/api/substitucions/2026-04-20/10:00/Professor%20inventat?nom=secret", json={})
    assert resposta.status_code == 401
    text = _missatge(caplog)
    assert "usuari (admin@centre_temporal)" in text
    assert "PUT /api/substitucions/{data}/{hora}/{professor} | 401 |" in text
    assert re.search(r"\| \d+ms$", text)
    assert all(valor not in text for valor in ("Professor", "inventat", "secret", "nom=", "198.51.100.23", "?"))


def test_sense_ruta_registra_el_cami_sense_query(main, caplog):
    resposta = TestClient(main.app).get("/no-existeix?nom=secret")
    assert resposta.status_code == 404
    text = _missatge(caplog)
    assert "GET /no-existeix | 404 |" in text
    assert "secret" not in text and "?" not in text


def test_error_500_tambe_registra_la_plantilla(main, caplog, monkeypatch):
    monkeypatch.setattr(main.app.router, "routes", list(main.app.router.routes))

    @main.app.get("/prova-registres/{nom}")
    def falla(nom: str):
        raise RuntimeError("fallada inventada")

    resposta = TestClient(main.app, raise_server_exceptions=False).get("/prova-registres/nom-inventat?x=secret")
    assert resposta.status_code == 500
    text = _missatge(caplog)
    assert "GET /prova-registres/{nom} | 500 |" in text
    assert "nom-inventat" not in text and "secret" not in text
    assert all(
        "nom-inventat" not in r.getMessage() for r in caplog.records if r.name in {"uvicorn.error", "prova.access"}
    )


def test_sense_fitxer_es_conserva_la_consola(monkeypatch):
    from config.access_log import configure_access_logger

    monkeypatch.delenv("ACCESS_LOG_PATH", raising=False)
    logger = configure_access_logger()
    assert logger.name == "uvicorn.error"
    assert logging.getLogger("uvicorn.access").disabled


def test_fitxer_diari_conserva_trenta_copies_temporals(tmp_path, monkeypatch):
    from config.access_log import configure_access_logger

    path = tmp_path / "access.log"
    monkeypatch.setenv("ACCESS_LOG_PATH", str(path))
    logger = configure_access_logger()
    handler = next(h for h in logger.handlers if isinstance(h, TimedRotatingFileHandler))
    assert handler.when == "MIDNIGHT"
    assert handler.interval == 86400
    assert handler.backupCount == 30
    assert not logger.propagate
    inici = datetime(2026, 1, 1, tzinfo=timezone.utc)
    ara = [inici.timestamp()]
    monkeypatch.setattr("logging.handlers.time.time", lambda: ara[0])
    try:
        for dia in range(35):
            handler.rolloverAt = int(inici.timestamp()) + (dia + 1) * 86400
            logger.info("registre inventat %s", dia)
            ara[0] = handler.rolloverAt
            handler.doRollover()
        esperats = {"access.log." + (inici + timedelta(days=dia)).strftime("%Y-%m-%d") for dia in range(5, 35)}
        assert {p.name for p in tmp_path.glob("access.log.*")} == esperats
    finally:
        logger.removeHandler(handler)
        handler.close()


CADDYFILE = Path(__file__).resolve().parents[2] / "Caddyfile.example"


def _uri_caddy(uri):
    for line in CADDYFILE.read_text().splitlines():
        if not line.strip().startswith("request>uri regexp "):
            continue
        tokens = shlex.split(line)
        if tokens[:2] != ["request>uri", "regexp"]:
            continue
        pattern, replacement = tokens[2:]
        uri = re.sub(
            pattern,
            lambda m, replacement=replacement: re.sub(r"\$\{(\d+)\}", lambda g: m.group(int(g[1])), replacement),
            uri,
        )
    return uri


def test_caddy_amaga_tots_els_segments_de_nom_dels_routers():
    parametres = {"data": "2026-04-20", "hora": "10:00", "nivell": "1-BAT"}
    noms = {"professor", "nom", "assignatura"}
    revisades = set()
    rutes = [
        r
        for inclosa in app_sencera().routes
        for r in (inclosa.original_router.routes if hasattr(inclosa, "original_router") else [inclosa])
    ]
    for ruta in rutes:
        if not isinstance(ruta, APIRoute):
            continue
        presents = set(re.findall(r"\{(\w+)\}", ruta.path_format))
        if not noms & presents:
            continue
        uri = ruta.path_format
        esperat = ruta.path_format
        for param in presents:
            uri = uri.replace("{" + param + "}", "Nom%20inventat%2Fnom" if param in noms else parametres[param])
            if param not in noms:
                esperat = esperat.replace("{" + param + "}", parametres[param])
        assert _uri_caddy(uri + "?nom=secret") == esperat, ruta.path_format
        revisades.add(ruta.path_format)
    assert revisades
    assert _uri_caddy("/api/health?nom=secret") == "/api/health"


def test_caddy_te_termini_de_trenta_dies():
    assert re.search(r"roll_keep_for\s+720h\b", CADDYFILE.read_text())
