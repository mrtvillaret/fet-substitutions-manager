"""
Quan un canvi del dia fa que un substitut ja no pugui fer la substitució
(perd la condició d'alliberat, passa a ser absent...), se'l treu i la fila
queda pendent. Després d'un canvi no s'assigna cap substitut automàticament:
només ho fan «Genera pendents», «Regenera tot» i «Reassignar problemàtics».

Dilluns 19/10/2026 a les 10:00: Prof 15 fa Anglès a 3-ESO-A, Prof 1 té classe
amb 3-ESO-C i Prof 3 fa guàrdia.
"""

import uuid

import pytest
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio

from rate_limit import limiter
from routes import grups
from substitucions import router as substitucions
from vigilancies.router import router as vigilancies_router

APP = crea_app(substitucions.router, grups.router, vigilancies_router)
DATA = "2026-10-19"
HORA = "10:00"


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


@pytest.fixture
def client():
    centre = nova_institucio(amb_xml=True)
    nom = f"user_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, centre, "user")
    return entra(client_per(APP), nom)


def _desa_grups(client, per_hora, professors=None):
    resp = client.put(
        f"/api/grups/{DATA}",
        json={
            "grups": per_hora,
            "professors": professors or {},
            "activitats": {},
            "ocupats": {},
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _absencia(client, professor, hores=(HORA,)):
    resp = client.put(
        f"/api/substitucions/{DATA}/absencies/{professor}", json={"hores_absencia": list(hores), "updated_at_map": {}}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _fila(client, professor="Prof 15"):
    return next(
        s
        for s in client.get(f"/api/substitucions/{DATA}", params={"include_all": True}).json()
        if s["hora"] == HORA and s["professor_absent"] == professor
    )


def _assigna(client, substitut, professor="Prof 15"):
    resp = client.put(
        f"/api/substitucions/{DATA}/{HORA}/{professor}",
        json={"substitut": substitut, "updated_at": _fila(client, professor)["updated_at"]},
    )
    assert resp.status_code == 200, resp.text


def test_qui_perd_la_condicio_d_alliberat_deixa_de_ser_substitut(client):
    _desa_grups(client, {HORA: ["3-ESO-C"]})
    _absencia(client, "Prof 15")
    _assigna(client, "Prof 1")

    resp = _desa_grups(client, {"12:30": ["3-ESO-C"]})  # a les 10:00 torna a tenir classe

    assert _fila(client)["substitut"] == ""
    [tret] = resp["substituts_trets"]
    assert (tret["hora"], tret["professor_absent"], tret["substitut"], tret["motiu"]) == (
        HORA,
        "Prof 15",
        "Prof 1",
        "classe",
    )
    assert tret["classe_grup"] == "3-ESO-C"


def test_el_professor_alliberat_que_deixa_de_ser_ho_deixa_de_ser_substitut(client):
    _desa_grups(client, {}, professors={HORA: ["Prof 1"]})
    _absencia(client, "Prof 15")
    _assigna(client, "Prof 1")

    resp = _desa_grups(client, {})

    assert _fila(client)["substitut"] == ""
    assert [t["substitut"] for t in resp["substituts_trets"]] == ["Prof 1"]


def test_qui_passa_a_ser_absent_deixa_de_ser_substitut(client):
    _absencia(client, "Prof 15")
    _assigna(client, "Prof 3")

    resp = _absencia(client, "Prof 3")

    assert _fila(client)["substitut"] == ""
    [tret] = resp["substituts_trets"]
    assert (tret["substitut"], tret["motiu"]) == ("Prof 3", "absent")


def test_un_canvi_del_dia_no_assigna_cap_substitut(client):
    _absencia(client, "Prof 15")
    assert _fila(client)["substitut"] == ""

    resp = _desa_grups(client, {HORA: ["3-ESO-C"]})

    assert _fila(client)["substitut"] == ""
    assert resp["substituts_trets"] == []


def test_els_substituts_valids_no_es_toquen(client):
    _absencia(client, "Prof 15")
    _assigna(client, "Prof 3")

    resp = _desa_grups(client, {"12:30": ["3-ESO-C"]})

    assert _fila(client)["substitut"] == "Prof 3"
    assert resp["substituts_trets"] == []


def test_genera_pendents_si_que_omple_les_files_buides(client):
    _absencia(client, "Prof 15")
    _desa_grups(client, {"12:30": ["3-ESO-C"]})
    assert client.post(f"/api/substitucions/{DATA}/generar").status_code == 200
    assert _fila(client)["substitut"] != ""


def _vigilancia_absent(client):
    """Fila de vigilant absent: Prof 21 vigila a les 10:00 i és absent."""
    resp = client.post(
        f"/api/vigilancies/{DATA}",
        json={
            "hora": HORA,
            "tipus": "Anglès",
            "grups": "2-BAT-A",
            "aula": "A1",
            "vigilant": "Prof 21",
            "comentaris": "",
            "nivell": "2-BAT",
        },
    )
    assert resp.status_code == 200, resp.text
    _absencia(client, "Prof 21")
    return next(
        s
        for s in client.get(f"/api/substitucions/{DATA}", params={"include_all": True}).json()
        if s["tipus_absencia"] == "VIGILANCIA_ABSENT"
    )


def test_un_canvi_del_dia_tampoc_assigna_la_vigilancia_d_un_vigilant_absent(client):
    assert _vigilancia_absent(client)["substitut"] == ""

    _desa_grups(client, {"12:30": ["3-ESO-C"]})

    fila = next(
        s
        for s in client.get(f"/api/substitucions/{DATA}", params={"include_all": True}).json()
        if s["tipus_absencia"] == "VIGILANCIA_ABSENT"
    )
    assert fila["substitut"] == ""
