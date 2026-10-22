"""
Absència coberta (abans «baixa»): en desar-ne una, si alguna classe de
l'absent no té cap altre professor amb el mateix grup a l'XML (el substitut
extern), la resposta en porta un avís. No bloqueja res.

Dilluns 20/04/2026, horari d'exemple: Prof 15 fa Anglès a les 10:00 (3-ESO-A).
"""

import copy
import uuid
import xml.etree.ElementTree as ET

import pytest
from fastapi import Depends
from suport_api import XML_EXEMPLE, client_per, crea_app, crea_usuari, entra, nova_institucio

from absencia_coberta.router import router as absencia_coberta_router
from auth.dependencies import require_admin
from database import get_data_dir_for_institucio
from rate_limit import limiter

APP = crea_app()
APP.include_router(absencia_coberta_router, dependencies=[Depends(require_admin)])  # com a main.py
URL = "/api/absencies-cobertes"
DILLUNS = "2026-04-20"


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


def _client(amb_substitut):
    centre = nova_institucio(amb_xml=True)
    if amb_substitut:
        # El substitut extern a l'XML: un professor nou amb les mateixes classes que Prof 15
        arbre = ET.parse(XML_EXEMPLE)
        arrel = arbre.getroot()
        substitut = copy.deepcopy(next(t for t in arrel.findall("Teacher") if t.get("name") == "Prof 15"))
        substitut.set("name", "Substitut 1")
        arrel.append(substitut)
        arbre.write(get_data_dir_for_institucio(centre) / "teachers.xml", encoding="utf-8")
    nom = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, centre, "admin")
    return entra(client_per(APP), nom)


def _desa(client):
    resp = client.post(URL, json={"professor": "Prof 15", "data_inici": DILLUNS, "data_final": DILLUNS, "motiu": ""})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_sense_substitut_a_l_xml_avisa_de_les_classes_que_queden_sense_ningu():
    avisos = _desa(_client(amb_substitut=False))["avisos"]
    assert avisos and all(a["codi"] == "classe_sense_substitut" for a in avisos)
    assert {"dia": "Dilluns", "hora": "10:00", "grup": "3-ESO-A", "assignatura": "Anglès"} in [
        a["params"] for a in avisos
    ]


def test_amb_el_substitut_a_l_xml_no_hi_ha_cap_avis():
    assert _desa(_client(amb_substitut=True))["avisos"] is None


def test_l_avis_tambe_surt_en_editar_la():
    client = _client(amb_substitut=False)
    baixa_id = _desa(client)["id"]
    resp = client.put(f"{URL}/{baixa_id}", json={"motiu": "Llarga"})
    assert resp.status_code == 200 and resp.json()["avisos"]


def test_una_absencia_coberta_creada_surt_a_la_llista():
    client = _client(amb_substitut=False)
    _desa(client)
    assert [a["professor"] for a in client.get(URL).json()["absencies_cobertes"]] == ["Prof 15"]


def test_editar_o_esborrar_una_absencia_coberta_que_no_hi_es_dona_404():
    client = _client(amb_substitut=False)
    assert client.put(f"{URL}/999999", json={"motiu": "x"}).status_code == 404
    assert client.delete(f"{URL}/999999").status_code == 404


def test_esborrar_una_absencia_coberta_la_treu_de_la_llista():
    client = _client(amb_substitut=False)
    absencia_id = _desa(client)["id"]
    assert client.delete(f"{URL}/{absencia_id}").status_code == 200
    assert client.get(URL).json() == {"absencies_cobertes": []}
