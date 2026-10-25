"""
Els PDF de substitucions i de vigilàncies fan servir els mateixos estils
(export/pdf/taula.py): les vigilàncies es distingeixen pel títol quan van
soles, i en gris i cursiva a la taula del dia, no per uns colors propis.
"""

import uuid

import pytest
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio, streams_pdf, text_pdf

from rate_limit import limiter
from routes import pdf, substitucions
from vigilancies.router import router as vigilancies_router

APP = crea_app(pdf.router, substitucions.router, vigilancies_router)
DATA = "2026-04-20"
# Colors en les ordres de dibuix del PDF (rgb de 0 a 1)
FONS_CAPCALERA = ".172549 .243137 .313725 rg"  # #2c3e50
TURQUESA = ".090196 .635294 .721569 rg"  # #17a2b8, el color propi d'abans


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


@pytest.fixture
def client():
    centre = nova_institucio(amb_xml=True)
    nom = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, centre, "admin")
    client = entra(client_per(APP), nom)
    body = {
        "hora": "10:00",
        "tipus": "Socials",
        "grups": "2-ESO-C",
        "aula": "A1",
        "vigilant": "Prof 3",
        "nivell": "2-ESO",
    }
    assert client.post(f"/api/vigilancies/{DATA}", json=body).status_code == 200
    return client


def _dibuix(client, ruta, **params):
    resp = client.get(ruta, params=params)
    assert resp.status_code == 200, resp.text
    return resp.content, "\n".join(streams_pdf(resp.content))


def test_el_pdf_de_vigilancies_te_els_colors_del_de_substitucions(client):
    contingut, dibuix = _dibuix(client, f"/api/pdf/vigilancies/{DATA}")
    assert "VIGIL\\300NCIES" in text_pdf(contingut)  # es distingeix pel títol
    assert FONS_CAPCALERA in dibuix
    assert TURQUESA not in dibuix


@pytest.mark.parametrize("format", ["hores", "dia"])
def test_les_vigilancies_del_pdf_complet_no_tenen_colors_propis(client, format):
    _, dibuix = _dibuix(client, f"/api/pdf/complete/{DATA}", format=format, include_substitutions=False)
    assert FONS_CAPCALERA in dibuix
    assert TURQUESA not in dibuix
