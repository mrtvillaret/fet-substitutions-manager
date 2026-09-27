"""
Peticions simultànies d'usuaris de dues institucions al mateix backend: cap
resposta pot contenir dades de l'altra institució.

Abans, la institució de la petició es desava en una variable global
(config.global_data) i les prioritats es reescrivien globalment a cada
petició: amb només dues peticions alhora, prop de la meitat de les respostes
eren de l'altra institució. Aquí es fa amb un servidor uvicorn de veritat
(fils i bucle d'esdeveniments reals), no amb el client de test.
"""
import http.client
import json
import socket
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
import uvicorn

from fastapi import APIRouter, Depends

import i18n_setup
from auth_utils import get_current_user
from database import get_data_db_session, get_data_dir_for_institucio
from repositories import ConfiguracioRepository, NoSubstituirRepository
from routes import settings, vigilancies
from suport_api import CONTRASENYA, XML_EXEMPLE, crea_app, crea_usuari, nova_institucio

PETICIONS = 400
FILS = 16

# Ruta de prova que retorna textos traduïts pel backend
_textos = APIRouter()


@_textos.get("/api/prova/textos")
def textos(_usuari=Depends(get_current_user)):
    return {"dia": i18n_setup.translate("Dilluns"), "idioma": i18n_setup.CURRENT_LANGUAGE,
            "builtins": _("Professor")}  # noqa: F821  (la `_` global que fan servir alguns mòduls)


def _port_lliure():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _peticio(port, metode, ruta, cos=None, galeta=None):
    connexio = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    capcaleres = {"Content-Type": "application/json"}
    if galeta:
        capcaleres["Cookie"] = galeta
    connexio.request(metode, ruta, body=json.dumps(cos) if cos else None, headers=capcaleres)
    resposta = connexio.getresponse()
    dades, set_cookie = resposta.read(), resposta.getheader("set-cookie")
    connexio.close()
    return resposta.status, dades, set_cookie


@pytest.fixture(scope="module")
def servidor():
    # Institució A: horari d'exemple (Prof N). Institució B: el mateix horari
    # amb els professors renombrats (Docent N). Cadascuna amb una activitat
    # pròpia que no se substitueix.
    a, b = nova_institucio(amb_xml=True), nova_institucio(amb_xml=True)
    (get_data_dir_for_institucio(b) / "teachers.xml").write_bytes(
        XML_EXEMPLE.read_bytes().replace(b'name="Prof ', b'name="Docent '))
    for inst, activitat, idioma in ((a, "Reunió A", "ca"), (b, "Reunió B", "es")):
        with get_data_db_session(inst) as db:
            NoSubstituirRepository.create(db, activitat)
            ConfiguracioRepository.set(db, "idioma", idioma)

    port = _port_lliure()
    srv = uvicorn.Server(uvicorn.Config(crea_app(vigilancies.router, settings.router, _textos),
                                        host="127.0.0.1", port=port, log_level="error"))
    fil = threading.Thread(target=srv.run, daemon=True)
    fil.start()
    while not srv.started:
        time.sleep(0.05)

    galetes = {}
    for inst in (a, b):
        nom = f"admin_{uuid.uuid4().hex[:8]}"
        crea_usuari(nom, inst, "admin")
        estat, _, galeta = _peticio(port, "POST", "/api/login", {"username": nom, "password": CONTRASENYA})
        assert estat == 200
        galetes[inst] = galeta.split(";")[0]
    yield port, a, b, galetes
    srv.should_exit = True
    fil.join(timeout=10)


def _en_paral·lel(funcio, feines):
    with ThreadPoolExecutor(max_workers=FILS) as ex:
        return list(ex.map(funcio, feines))


def test_l_horari_no_es_barreja_entre_institucions(servidor):
    port, a, b, galetes = servidor

    def una(inst):
        estat, cos, _ = _peticio(port, "GET", "/api/vigilancies/config", galeta=galetes[inst])
        assert estat == 200
        professors = json.loads(cos)["professors"]
        esperat, altre = ("Prof", "Docent") if inst == a else ("Docent", "Prof")
        return all(p.startswith(esperat) for p in professors) and not any(p.startswith(altre) for p in professors)

    resultats = _en_paral·lel(una, [a if i % 2 == 0 else b for i in range(PETICIONS)])
    assert resultats.count(False) == 0, f"{resultats.count(False)} de {PETICIONS} respostes amb dades de l'altra institució"


def test_les_prioritats_no_es_barregen_entre_institucions(servidor):
    port, a, b, galetes = servidor

    def una(inst):
        estat, cos, _ = _peticio(port, "GET", "/api/settings", galeta=galetes[inst])
        assert estat == 200
        dades = json.loads(cos)
        esperat = ["Reunió A"] if inst == a else ["Reunió B"]
        return dades["no_substituir"] == esperat and dades["institucio"] == inst

    resultats = _en_paral·lel(una, [a if i % 2 == 0 else b for i in range(PETICIONS)])
    assert resultats.count(False) == 0, f"{resultats.count(False)} de {PETICIONS} respostes amb dades de l'altra institució"


def test_l_idioma_no_es_barreja_entre_institucions(servidor):
    port, a, b, galetes = servidor
    esperat = {a: {"dia": "Dilluns", "idioma": "ca", "builtins": "Professor"},
               b: {"dia": "Lunes", "idioma": "es", "builtins": "Profesor"}}

    def una(inst):
        estat, cos, _ = _peticio(port, "GET", "/api/prova/textos", galeta=galetes[inst])
        assert estat == 200
        return json.loads(cos) == esperat[inst]

    resultats = _en_paral·lel(una, [a if i % 2 == 0 else b for i in range(PETICIONS)])
    assert resultats.count(False) == 0, f"{resultats.count(False)} de {PETICIONS} respostes en l'idioma de l'altra institució"
