"""
Gestor d'errors 5xx (errors_servidor.py): l'usuari no rep mai el detall intern
(consultes SQL, rutes, missatges d'excepció), només una referència que
permet trobar-lo al registre del servidor. Els errors 4xx no canvien.
"""
from fastapi import APIRouter, HTTPException
from fastapi.testclient import TestClient

from suport_api import crea_app

router = APIRouter()


@router.get("/prova/500")
def error_500():
    raise HTTPException(status_code=500, detail="Error: (sqlite3.OperationalError) no such table: secreta")


@router.get("/prova/excepcio")
def excepcio():
    raise RuntimeError("detall intern de l'excepció")


@router.get("/prova/404")
def error_404():
    raise HTTPException(status_code=404, detail="Substitució no trobada")


@router.get("/prova/400")
def error_400():
    raise HTTPException(status_code=400, detail={"xml_missing": True, "message": "Falta l'XML"})


CLIENT = TestClient(crea_app(router), raise_server_exceptions=False)


def _referencia_al_registre(caplog, ref, text):
    return any(ref in r.getMessage() and text in r.getMessage() for r in caplog.records)


def test_un_500_no_retorna_el_detall_intern(caplog):
    resp = CLIENT.get("/prova/500")
    assert resp.status_code == 500
    assert set(resp.json()) == {"error_ref"}
    assert "sqlite3" not in resp.text
    assert _referencia_al_registre(caplog, resp.json()["error_ref"], "no such table")


def test_una_excepcio_no_controlada_tampoc(caplog):
    resp = CLIENT.get("/prova/excepcio")
    assert resp.status_code == 500
    assert set(resp.json()) == {"error_ref"}
    assert _referencia_al_registre(caplog, resp.json()["error_ref"], "detall intern")


def test_cada_error_te_una_referencia_diferent():
    assert CLIENT.get("/prova/500").json()["error_ref"] != CLIENT.get("/prova/500").json()["error_ref"]


def test_els_errors_4xx_no_canvien():
    assert CLIENT.get("/prova/404").json() == {"detail": "Substitució no trobada"}
    assert CLIENT.get("/prova/400").json() == {"detail": {"xml_missing": True, "message": "Falta l'XML"}}
