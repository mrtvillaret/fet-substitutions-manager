"""
Els grups que el centre amaga (/api/grups-amagats, configuració de grups):
els noms arriben nets (NomNet) i un element que no és text es rebutja (422)
sense desar res.
"""

import uuid

from fastapi import Depends
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio

from auth.dependencies import require_admin
from grups.router import router_admin
from rate_limit import limiter

APP = crea_app()
APP.include_router(router_admin, dependencies=[Depends(require_admin)])


def _client():
    limiter.reset()
    centre = nova_institucio(amb_xml=True)
    usuari = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(usuari, centre, "admin")
    return entra(client_per(APP), usuari)


def test_els_grups_amagats_es_desen_nets_i_sense_repetir():
    client = _client()

    resposta = client.put("/api/grups-amagats", json={"grups": ["1-ESO-A", " 2-ESO-B ", "", "1-ESO-A"]})

    assert resposta.json() == {"success": True, "total": 2}
    assert client.get("/api/grups-amagats").json() == {"grups": ["1-ESO-A", "2-ESO-B"]}


def test_un_element_que_no_es_text_es_rebutja_sense_desar_res():
    client = _client()
    client.put("/api/grups-amagats", json={"grups": ["1-ESO-A"]})

    resposta = client.put("/api/grups-amagats", json={"grups": [1, "2-ESO-B"]})

    assert resposta.status_code == 422
    assert client.get("/api/grups-amagats").json() == {"grups": ["1-ESO-A"]}
