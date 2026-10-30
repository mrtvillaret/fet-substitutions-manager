"""
La regla dels noms (noms.py): sense espais al principi i al final; el text
buit és vàlid, i un nom fet només d'espais queda buit.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from noms import NomNet, nom_net


@pytest.mark.parametrize(
    "cru, net",
    [
        ("Guàrdia", "Guàrdia"),
        (" Guàrdia", "Guàrdia"),
        ("Guàrdia ", "Guàrdia"),
        ("   Prof 3", "Prof 3"),  # els espais del davant de FET no formen part del nom
        ("Educació Física", "Educació Física"),  # els de dins, sí
        ("\tReunió\n", "Reunió"),
        ("", ""),  # el buit és vàlid
        ("   ", ""),  # només espais: buit
        (None, None),
    ],
)
def test_nom_net(cru, net):
    assert nom_net(cru) == net


class _Peticio(BaseModel):
    professor: NomNet
    aula: NomNet = ""


_app = FastAPI()


@_app.post("/prova/{assignatura}")
def _prova(assignatura: NomNet, peticio: _Peticio):
    return {"assignatura": assignatura, "professor": peticio.professor, "aula": peticio.aula}


def test_l_api_rep_els_noms_nets():
    resp = TestClient(_app).post("/prova/%20Pares%20", json={"professor": "  Prof 3 ", "aula": " A1"})
    assert resp.json() == {"assignatura": "Pares", "professor": "Prof 3", "aula": "A1"}


def test_un_nom_que_no_es_text_continua_sent_un_422():
    assert TestClient(_app).post("/prova/Pares", json={"professor": 5}).status_code == 422


def test_ordre_alfabetic_natural_i_en_catala():
    from noms import ordre_alfabetic

    # La mateixa llista que frontend/tests/ordreAlfabetic.test.js
    noms = ["Prof 10", "prof 2", "Èric", "Prof 6", "Zoe", "Esteve", "Àlex", "Andreu", "Prof 1"]
    noms += ["Mariana", "Mª Àngels", "Maria"]  # «ª» com «a», com Intl.Collator('ca')

    assert sorted(noms, key=ordre_alfabetic) == [
        "Àlex",
        "Andreu",
        "Èric",
        "Esteve",
        "Mª Àngels",
        "Maria",
        "Mariana",
        "Prof 1",
        "prof 2",
        "Prof 6",
        "Prof 10",
        "Zoe",
    ]
