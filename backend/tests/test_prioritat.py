"""
substitucions/prioritat.py: si per a un substitut assignat hi ha un disponible de
més prioritat, el PDF n'avisa i «Reassignar problemàtics» el canvia.

Dilluns 20/04/2026 a les 10:00: Prof 15 fa Anglès (3-ESO-A), Prof 3 fa guàrdia,
Prof 1 té classe amb 3-ESO-C i Prof 30 amb 1-ESO-A. Prioritats de suport_api:
primer els alliberats, després les guàrdies. Quan Prof 3 substitueix, la seva
guàrdia queda per cobrir (fila encadenada) i en generar s'hi posa un alliberat.
"""

import uuid

import pytest
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio, text_pdf

from rate_limit import limiter
from routes import grups, pdf
from substitucions import router as substitucions

APP = crea_app(substitucions.router, grups.router, pdf.router)
DATA = "2026-04-20"


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


@pytest.fixture
def client():
    centre = nova_institucio(amb_xml=True)
    nom = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, centre, "admin")
    return entra(client_per(APP), nom)


def _fila(client):
    return next(
        s
        for s in client.get(f"/api/substitucions/{DATA}", params={"include_all": True}).json()
        if s["hora"] == "10:00" and s["professor_absent"] == "Prof 15"
    )


def _guardia_amb_alliberats(client):
    """Prof 3 (guàrdia) substitueix Prof 15 i, després, Prof 1 i Prof 30 queden alliberats."""
    client.put(f"/api/substitucions/{DATA}/absencies/Prof 15", json={"hores_absencia": ["10:00"], "updated_at_map": {}})
    resp = client.put(
        f"/api/substitucions/{DATA}/10:00/Prof 15",
        json={"substitut": "Prof 3", "updated_at": _fila(client)["updated_at"]},
    )
    assert resp.status_code == 200, resp.text
    resp = client.put(
        f"/api/grups/{DATA}",
        json={"grups": {"10:00": ["3-ESO-C", "1-ESO-A"]}, "professors": {}, "activitats": {}, "ocupats": {}},
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.parametrize("format", ["hores", "dia"])
def test_el_pdf_complet_porta_l_avis_del_substitut_de_mes_prioritat(client, format):
    # El PDF fa la mateixa validació que la ruta de validacions (abans hi
    # faltava el Dia i l'avís no hi sortia)
    _guardia_amb_alliberats(client)
    resp = client.get(f"/api/pdf/complete/{DATA}", params={"format": format})
    assert resp.status_code == 200, resp.text
    text = " ".join(text_pdf(resp.content))
    assert "disponible en lloc de Prof 3" in text, text[-600:]


def test_un_alliberat_te_mes_prioritat_que_una_guardia(client):
    client.put(f"/api/substitucions/{DATA}/absencies/Prof 15", json={"hores_absencia": ["10:00"], "updated_at_map": {}})
    resp = client.put(
        f"/api/substitucions/{DATA}/10:00/Prof 15",
        json={"substitut": "Prof 3", "updated_at": _fila(client)["updated_at"]},
    )
    assert resp.status_code == 200, resp.text
    # Ara els grups de Prof 1 i Prof 30 no tenen classe: tots dos queden alliberats
    resp = client.put(
        f"/api/grups/{DATA}",
        json={"grups": {"10:00": ["3-ESO-C", "1-ESO-A"]}, "professors": {}, "activitats": {}, "ocupats": {}},
    )
    assert resp.status_code == 200, resp.text
    assert _fila(client)["substitut"] == "Prof 3"  # continua sent vàlid

    avisos = client.get(f"/api/pdf/{DATA}/validacions").json()["warnings"]
    assert any("(alliberat) disponible en lloc de Prof 3 (Guàrdia)" in a for a in avisos), avisos

    resp = client.post(f"/api/substitucions/{DATA}/reassign-problematics")
    assert resp.status_code == 200, resp.text
    fila = _fila(client)
    assert fila["substitut"] in ("Prof 1", "Prof 30")
