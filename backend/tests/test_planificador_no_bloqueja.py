"""
Generar un horari d'exàmens tarda uns segons. Mentrestant, el backend ha de
continuar atenent la resta de peticions (d'aquest centre o d'un altre).
Amb un servidor uvicorn de veritat, com a test_concurrencia_institucions.
"""
import threading
import time

import pytest
import uvicorn

from routes import config_examens, scheduler
from suport_api import CONTRASENYA, crea_app, crea_usuari
from suport_planificador import DATES, DIES, alliberaments, centre_amb_examens, configura
from test_concurrencia_institucions import _peticio, _port_lliure


@pytest.fixture(scope="module")
def servidor():
    institucio, client = centre_amb_examens(nivells=("1-BAT", "2-BAT"))
    configura(client, nivells_actius=["1-BAT", "2-BAT"],
              alliberaments_per_nivell=alliberaments(nivells=("1-BAT", "2-BAT")))
    port = _port_lliure()
    srv = uvicorn.Server(uvicorn.Config(crea_app(scheduler.router, config_examens.router),
                                        host="127.0.0.1", port=port, log_level="error"))
    fil = threading.Thread(target=srv.run, daemon=True)
    fil.start()
    while not srv.started:
        time.sleep(0.05)
    crea_usuari("admin_no_bloqueja", institucio, "admin")
    _, _, galeta = _peticio(port, "POST", "/api/login", {"username": "admin_no_bloqueja", "password": CONTRASENYA})
    yield port, galeta.split(";")[0]
    srv.should_exit = True
    fil.join(timeout=10)


def test_mentre_es_genera_un_horari_les_altres_peticions_responen(servidor):
    port, galeta = servidor
    generacio = {}

    def genera():
        inici = time.monotonic()
        estat, cos, _ = _peticio(port, "POST", "/api/scheduler/generate", {
            "data_inici": DATES[0], "data_final": DATES[-1], "selected_dates": DATES, "dies_utilitzar": DIES,
        }, galeta=galeta)
        generacio.update(estat=estat, fi=time.monotonic(), durada=time.monotonic() - inici, cos=cos)

    fil = threading.Thread(target=genera)
    fil.start()
    time.sleep(0.5)  # la generació ja ha començat

    inici = time.monotonic()
    estat, _, _ = _peticio(port, "GET", "/api/scheduler/config", galeta=galeta)
    resposta = time.monotonic()
    fil.join(timeout=120)

    assert estat == 200 and generacio["estat"] == 200, generacio.get("cos", b"")[:300]
    assert generacio["durada"] > 1.5, "la generació ha de durar prou per a la prova"
    assert resposta < generacio["fi"], "la petició ha esperat que acabés la generació"
    assert resposta - inici < 1.0


def test_la_captura_de_missatges_no_barreja_peticions_simultanies():
    from concurrent.futures import ThreadPoolExecutor
    from captura_sortida import captura_stdout

    barrera = threading.Barrier(4)

    def peticio(n):
        with captura_stdout() as sortida:
            barrera.wait()  # totes quatre capturant alhora
            for i in range(50):
                print(f"peticio {n} linia {i}")
                time.sleep(0.001)
        return sortida.getvalue().splitlines()

    with ThreadPoolExecutor(max_workers=4) as ex:
        resultats = list(ex.map(peticio, range(4)))
    for n, linies in enumerate(resultats):
        assert linies == [f"peticio {n} linia {i}" for i in range(50)]
