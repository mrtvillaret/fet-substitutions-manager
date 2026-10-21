"""
Els errors del domini: cada categoria surt amb el seu status i la mateixa
resposta que una HTTPException, {"detail": "..."}. El codi i els paràmetres
(pensats per a l'i18n) no surten a la resposta.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from errors_domini import Conflicte, ErrorDeDomini, NoPermes, NoTrobat, NoValid
from errors_servidor import registra_gestors_errors


def _client_que_llanca(error):
    app = FastAPI()
    registra_gestors_errors(app)

    @app.get("/prova")
    def prova():
        raise error

    return TestClient(app)


@pytest.mark.parametrize("classe, status", [(NoTrobat, 404), (NoPermes, 403), (NoValid, 400), (Conflicte, 409)])
def test_cada_categoria_respon_amb_el_seu_status_i_el_missatge(classe, status):
    resp = _client_que_llanca(classe("Un missatge", codi="prova")).get("/prova")
    assert resp.status_code == status
    assert resp.json() == {"detail": "Un missatge"}


def test_el_codi_i_els_parametres_no_surten_a_la_resposta():
    error = NoValid("Massa curta", codi="contrasenya_curta", params={"minim": 8})
    assert (error.codi, error.params) == ("contrasenya_curta", {"minim": 8})
    assert _client_que_llanca(error).get("/prova").json() == {"detail": "Massa curta"}


def test_una_subclasse_fa_servir_el_status_de_la_seva_categoria():
    class ContrasenyaCurta(NoValid):
        pass

    assert _client_que_llanca(ContrasenyaCurta("Curta", codi="curta")).get("/prova").status_code == 400


def test_cal_triar_una_categoria():
    with pytest.raises(TypeError, match="categoria"):
        ErrorDeDomini("Sense categoria", codi="prova")


def test_el_codi_es_obligatori():
    with pytest.raises(TypeError):
        NoValid("Sense codi")


def test_una_categoria_sense_status_es_un_error_intern():
    class Nova(ErrorDeDomini):
        pass

    resp = _client_que_llanca(Nova("Detall intern", codi="nova")).get("/prova")
    assert resp.status_code == 500 and set(resp.json()) == {"error_ref"}
