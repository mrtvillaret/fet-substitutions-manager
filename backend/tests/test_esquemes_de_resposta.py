"""
Totes les rutes que responen JSON tenen esquema de resposta (`response_model`):
el que retornen és el que diu l'esquema i res més. Les úniques sense, les que
retornen fitxers i les dues comprovacions de salut, són aquí a la llista.
"""

from suport_main import app_sencera

SENSE_ESQUEMA = {
    # Fitxers (PDF, CSV i el logo)
    ("GET", "/api/config/exportar-assignacions-csv"),
    ("GET", "/api/pdf/complete/{data}"),
    ("GET", "/api/pdf/vigilancies/interval"),
    ("GET", "/api/pdf/vigilancies/{data}"),
    ("POST", "/api/pdf/disponibles-tots-dies"),
    ("GET", "/api/files/logo"),
    ("GET", "/api/informes/direccio"),
    ("GET", "/api/informes/professor"),
    # Comprovacions de salut (main.py)
    ("GET", "/"),
    ("GET", "/api/health"),
}


def _sense_esquema():
    for cami, operacions in app_sencera().openapi()["paths"].items():
        for metode, operacio in operacions.items():
            continguts = operacio["responses"].get("200", {}).get("content", {})
            if not any(c.get("schema") for c in continguts.values()):
                yield metode.upper(), cami


def test_totes_les_rutes_json_tenen_esquema_de_resposta():
    assert set(_sense_esquema()) == SENSE_ESQUEMA
