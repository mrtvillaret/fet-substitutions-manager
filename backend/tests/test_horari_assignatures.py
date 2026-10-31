"""
Les activitats de l'horari vigent per a la configuració: a Prioritats, en
afegir a «No substituir» una activitat que té grup, la pantalla avisa que
aquell grup quedarà sense professor quan qui la fa falti (l'hora no surt a
Substitucions).
"""

import uuid

from fastapi import Depends
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio

from auth.dependencies import get_current_user
from rate_limit import limiter
from routes import horari

APP = crea_app()
APP.include_router(horari.router, dependencies=[Depends(get_current_user)])


def test_detectar_diu_quines_activitats_tenen_grup_a_l_horari_vigent():
    limiter.reset()
    centre = nova_institucio(amb_xml=True)
    usuari = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(usuari, centre, "admin")
    client = entra(client_per(APP), usuari)

    resposta = client.get("/api/horari/assignatures/detectar", params={"data": "2026-04-20"})

    assert resposta.status_code == 200, resposta.text
    dades = resposta.json()
    assert "Català" in dades["amb_grup"]
    assert "Guàrdia" in dades["assignatures"] and "Guàrdia" not in dades["amb_grup"]
    assert set(dades["amb_grup"]) <= set(dades["assignatures"]) | {""}
    assert dades["amb_grup"] == sorted(dades["amb_grup"])
