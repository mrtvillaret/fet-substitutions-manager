"""
Tests dels PDF (routes/pdf.py i routes/informes.py): el text que escriuen els
usuaris (camps de vigilàncies, substitut, comentaris) ha d'arribar al PDF com
a text, no interpretat com a etiquetes de ReportLab. Abans, un simple
"Examen <font" feia fallar el PDF de tot el dia, i "<img src=...>" feia que el
generador llegís fitxers del servidor.
"""
import uuid

import pytest

from rate_limit import limiter
from routes import informes, pdf, substitucions, vigilancies
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio

APP = crea_app(vigilancies.router, substitucions.router, pdf.router, informes.router)
DATA = "2026-04-20"  # dilluns
TEXT_PERILLÓS = "Aula <font"                      # etiqueta sense tancar
IMATGE = "<img src='/etc/hostname' width='9' height='9'/>"
MARCATGE = "<b>negreta</b>"

PDFS = [
    f"/api/pdf/vigilancies/{DATA}",
    f"/api/pdf/complete/{DATA}",
    f"/api/pdf/vigilancies/interval?data_inici={DATA}&data_final={DATA}",
    f"/api/informes/direccio?data_inici={DATA}&data_final={DATA}",
    f"/api/informes/professor?data_inici={DATA}&data_final={DATA}&mostrar_taules=true",
]


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


def _prepara(client, valor):
    """Vigilància i substitució amb `valor` a tots els camps de text lliure."""
    resp = client.post(f"/api/vigilancies/{DATA}", json={
        "hora": "10:00", "tipus": valor, "grups": valor, "aula": valor,
        "vigilant": "Prof 21", "comentaris": valor, "nivell": valor,
    })
    assert resp.status_code == 200, resp.text
    client.put(f"/api/substitucions/{DATA}/absencies/Prof 15",
               json={"hores_absencia": ["11:30"], "updated_at_map": {}})
    fila = next(s for s in client.get(f"/api/substitucions/{DATA}", params={"include_all": True}).json()
                if s["hora"] == "11:30")
    resp = client.put(f"/api/substitucions/{DATA}/11:30/Prof 15",
                      json={"substitut": valor, "comentaris": valor, "force": True})
    assert resp.status_code == 200, resp.text


@pytest.mark.parametrize("ruta", PDFS)
@pytest.mark.parametrize("valor", [TEXT_PERILLÓS, IMATGE, MARCATGE])
def test_el_text_dels_usuaris_no_trenca_ni_s_interpreta_al_pdf(client, ruta, valor):
    _prepara(client, valor)
    resp = client.get(ruta)
    assert resp.status_code == 200, resp.text[:300]
    assert resp.headers["content-type"] == "application/pdf"
