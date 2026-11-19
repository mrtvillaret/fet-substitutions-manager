"""Totes les rutes del planificador per l'API, el no viable i l'entropia del
backtracking sense llavor."""

from types import SimpleNamespace

import pytest
from suport_planificador import DATES, DIES, centre_amb_examens, configura

from planificador import generacio_nova
from planificador.motor.estrategies import base
from planificador.router import router


def test_totes_les_rutes_responen(monkeypatch):
    _, client = centre_amb_examens()
    configura(client)
    rellotge = SimpleNamespace(monotonic=lambda: 0)
    monkeypatch.setattr(base, "time", rellotge)
    monkeypatch.setattr(generacio_nova, "time", rellotge)
    peticio = {
        "data_inici": DATES[0],
        "dies_utilitzar": DIES,
        "selected_dates": DATES,
        "random_seed": 7,
        "max_iteracions": 0,
    }
    visitades = set()

    def demana(metode, ruta, **arguments):
        resposta = getattr(client, metode)("/api/scheduler" + ruta, **arguments)
        visitades.add((metode.upper(), "/api/scheduler" + ruta.split("?", 1)[0]))
        assert resposta.status_code == 200, (metode, ruta, resposta.text)
        return resposta.json()

    for ruta in (
        "/motors",
        "/config",
        "/restriccions",
        "/costos-professors",
        "/dates",
        "/sessions-info",
        "/assignatures-actives",
        "/horari",
        "/ultim-resultat",
        "/curs-dates",
    ):
        demana("get", ruta)
    demana("put", "/config", json={})
    demana("put", "/restriccions", json={"restriccions": {}})
    demana("post", "/restriccions/treure-inexistents")
    demana("post", "/restriccions/pin", json={"pins": [], "unpins": []})
    demana("put", "/costos-professors", json={"globals": {}, "individuals": {}})
    demana("put", "/dates", json={"selected_dates": DATES})
    for motor in ("v2-backtrack", "v2", "v3"):
        resultat = demana("post", "/generate", json={**peticio, "motor": motor})
        assert resultat["horari"]["metadata"].get("viable", True)
    demana("post", "/analisi", json=peticio)
    demana("post", "/recalcular-cost", json={"horari": resultat["horari"], "selected_dates": DATES})
    demana(
        "post",
        "/publicar",
        json={"horari": resultat["horari"], "dry_run": True, "setmanes": [dict(zip(DIES, DATES, strict=True))]},
    )
    esperades = {(metode, ruta.path) for ruta in router.routes for metode in ruta.methods}
    assert visitades == esperades


@pytest.mark.parametrize("motor", ["v2-backtrack", "v2", "v3"])
def test_precheck_i_diagnostic_no_viable(monkeypatch, motor):
    from suport_planificador import alliberaments

    _, client = centre_amb_examens()
    configura(client, alliberaments_per_nivell=alliberaments(hores_inici=("09:00",)))
    resposta = client.post(
        "/api/scheduler/generate",
        json={"data_inici": DATES[0], "dies_utilitzar": [DIES[0]], "selected_dates": [DATES[0]], "motor": motor},
    )
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["horari"]["metadata"]["viable"] is False
    assert resposta.json()["horari"]["metadata"]["incompatibilitats"]


def test_l_entropia_interceptada_arriba_al_backtracking(monkeypatch):
    import random

    class FontEntropia:
        def __init__(self):
            self.consultes = 0

        def SystemRandom(self):  # noqa: N802 — és la interfície del mòdul random
            self.consultes += 1
            return random.Random(7)

        def __getattr__(self, nom):
            return getattr(random, nom)

    _, client = centre_amb_examens()
    configura(client)
    font = FontEntropia()
    monkeypatch.setattr(generacio_nova, "random", font)
    rellotge = SimpleNamespace(monotonic=lambda: 0)
    monkeypatch.setattr(base, "time", rellotge)
    monkeypatch.setattr(generacio_nova, "time", rellotge)
    resposta = client.post(
        "/api/scheduler/generate",
        json={"data_inici": DATES[0], "dies_utilitzar": DIES, "selected_dates": DATES, "motor": "v2-backtrack"},
    )
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["horari"]["metadata"].get("viable", True) is True
    assert font.consultes == 1
