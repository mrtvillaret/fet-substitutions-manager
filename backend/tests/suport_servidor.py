"""Un servidor uvicorn de veritat (fils i bucle d'esdeveniments reals) per als
tests de concurrència, i les peticions HTTP que s'hi fan."""

import http.client
import json
import socket
import threading
import time
from contextlib import contextmanager

import uvicorn

ARRENCADA_MAXIMA = 20  # segons


def _port_lliure():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextmanager
def servidor_uvicorn(app):
    """Arrenca `app` en un fil i en dona el port. Si no arrenca en
    ARRENCADA_MAXIMA segons (o el fil s'atura), falla en lloc d'esperar per
    sempre; en sortir, l'atura."""
    port = _port_lliure()
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    errors = []

    def executa():
        try:
            srv.run()
        except BaseException as error:  # també SystemExit: uvicorn en surt així si no arrenca
            errors.append(error)

    fil = threading.Thread(target=executa, daemon=True)
    fil.start()
    limit = time.monotonic() + ARRENCADA_MAXIMA
    while not srv.started:
        if not fil.is_alive():
            raise RuntimeError("uvicorn s'ha aturat abans d'arrencar") from (errors[0] if errors else None)
        if time.monotonic() > limit:
            srv.should_exit = True
            raise TimeoutError(f"uvicorn no ha arrencat en {ARRENCADA_MAXIMA} s")
        time.sleep(0.05)
    try:
        yield port
    finally:
        srv.should_exit = True
        fil.join(timeout=10)


def peticio(port, metode, ruta, cos=None, galeta=None):
    """(status, cos, set-cookie) d'una petició JSON al servidor."""
    connexio = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    capcaleres = {"Content-Type": "application/json"}
    if galeta:
        capcaleres["Cookie"] = galeta
    connexio.request(metode, ruta, body=json.dumps(cos) if cos else None, headers=capcaleres)
    resposta = connexio.getresponse()
    dades, set_cookie = resposta.read(), resposta.getheader("set-cookie")
    connexio.close()
    return resposta.status, dades, set_cookie
