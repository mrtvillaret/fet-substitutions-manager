"""La manca d'XML conserva la resposta pública en moure l'error al domini."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from suport_main import app_sencera

from errors_domini import MissingXmlError


@pytest.mark.parametrize("xml_path", [None, "/fitxer/inexistent.xml"])
def test_missing_xml_conserva_la_resposta_http(xml_path):
    app = FastAPI(exception_handlers=app_sencera().exception_handlers)

    @app.get("/prova")
    def prova():
        raise MissingXmlError("centre_de_prova", xml_path)

    resposta = TestClient(app).get("/prova")
    assert resposta.status_code == 400
    assert resposta.json() == {
        "detail": "Cal pujar un fitxer XML d'horari per a la institució centre_de_prova.",
        "xml_missing": True,
        "institucio": "centre_de_prova",
    }


def test_missing_xml_es_un_error_de_domini_amb_context():
    from errors_domini import ErrorDeDomini, MissingXmlError

    error = MissingXmlError("centre_de_prova", None)
    assert isinstance(error, ErrorDeDomini)
    assert error.codi == "xml_missing"
    assert error.params == {"institucio": "centre_de_prova"}
    assert (error.institucio, error.xml_path) == ("centre_de_prova", None)
