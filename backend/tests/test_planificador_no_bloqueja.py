"""
Generar un horari d'exàmens tarda uns segons. Mentrestant, el backend ha de
continuar atenent la resta de peticions (d'aquest centre o d'un altre).
Amb un servidor uvicorn de veritat, com a test_concurrencia_institucions.

La generació queda aturada (un Event) fins que l'altra petició ha respost:
no depèn de quant tarda el motor ni de la velocitat de la màquina.
"""

import threading

import pytest
from suport_api import CONTRASENYA, crea_app, crea_usuari
from suport_planificador import (
    DATES,
    DIES,
    alliberaments,
    centre_amb_examens,
    configura,
)
from suport_servidor import peticio, servidor_uvicorn

from configuracio_examens import router as config_examens
from planificador import generacio_nova
from planificador import router as scheduler

ESPERA = 30  # segons, com a molt, per a cada senyal


@pytest.fixture(scope="module")
def servidor():
    institucio, client = centre_amb_examens(nivells=("1-BAT", "2-BAT"))
    configura(
        client, nivells_actius=["1-BAT", "2-BAT"], alliberaments_per_nivell=alliberaments(nivells=("1-BAT", "2-BAT"))
    )
    with servidor_uvicorn(crea_app(scheduler.router, config_examens.router)) as port:
        crea_usuari("admin_no_bloqueja", institucio, "admin")
        _, _, galeta = peticio(port, "POST", "/api/login", {"username": "admin_no_bloqueja", "password": CONTRASENYA})
        yield port, galeta.split(";")[0]


def test_mentre_es_genera_un_horari_les_altres_peticions_responen(servidor, monkeypatch):
    port, galeta = servidor
    comencada, allibera = threading.Event(), threading.Event()
    original = generacio_nova.genera

    def genera_aturada(*args, **kwargs):
        comencada.set()
        assert allibera.wait(ESPERA), "la prova no ha alliberat la generació"
        return original(*args, **kwargs)

    monkeypatch.setattr(generacio_nova, "genera", genera_aturada)
    generacio = {}

    def genera():
        estat, cos, _ = peticio(
            port,
            "POST",
            "/api/scheduler/generate",
            {"data_inici": DATES[0], "data_final": DATES[-1], "selected_dates": DATES, "dies_utilitzar": DIES},
            galeta=galeta,
        )
        generacio.update(estat=estat, cos=cos)

    fil = threading.Thread(target=genera)
    fil.start()
    try:
        assert comencada.wait(ESPERA), "la generació no ha començat"
        # La generació és en marxa (i aturada): aquesta petició ha de respondre igualment
        estat, _, _ = peticio(port, "GET", "/api/scheduler/config", galeta=galeta)
        assert estat == 200
        assert fil.is_alive(), "la generació ha acabat abans que la prova la deixés continuar"
    finally:
        allibera.set()
        fil.join(timeout=120)

    assert generacio["estat"] == 200, generacio.get("cos", b"")[:300]
