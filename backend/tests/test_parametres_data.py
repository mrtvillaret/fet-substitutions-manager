"""
Els paràmetres de data de les rutes (data, data_inici, data_final, data_fi)
són DataISO: es validen sols i una data mal escrita o impossible dona 400,
en lloc d'una consulta que no troba res o d'un error intern.
"""

import ast
import uuid
from pathlib import Path

import pytest
from fastapi import Depends
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio

from auth.dependencies import get_current_user, require_admin
from pdf import router as pdf
from rate_limit import limiter
from routes import estadistiques
from substitucions import router as substitucions
from vigilancies.router import router as vigilancies_router

ROUTES = Path(__file__).resolve().parent.parent / "routes"
NOMS_DATA = {"data", "data_inici", "data_final", "data_fi"}

APP = crea_app()
for _router, _dep in (
    (substitucions.router, get_current_user),
    (vigilancies_router, get_current_user),
    (pdf.router, get_current_user),
    (estadistiques.router, require_admin),
):
    APP.include_router(_router, dependencies=[Depends(_dep)])  # com a main.py


def test_cap_parametre_de_data_d_una_ruta_es_text_sense_validar():
    sense_validar = []
    for fitxer in sorted(ROUTES.glob("*.py")):
        for fn in ast.walk(ast.parse(fitxer.read_text(encoding="utf-8"))):
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
                getattr(getattr(d, "func", None), "attr", "") in ("get", "post", "put", "delete")
                for d in fn.decorator_list
            ):
                for arg in fn.args.args + fn.args.kwonlyargs:
                    if (
                        arg.arg in NOMS_DATA
                        and arg.annotation is not None
                        and ast.unparse(arg.annotation) in ("str", "Optional[str]")
                    ):
                        sense_validar.append(f"{fitxer.name}:{fn.lineno} {fn.name}({arg.arg})")
    assert sense_validar == []


@pytest.fixture
def client():
    limiter.reset()
    nom = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, nova_institucio(amb_xml=True), "admin")
    return entra(client_per(APP), nom)


@pytest.mark.parametrize(
    "url",
    [
        "/api/vigilancies/20-04-2026",
        "/api/vigilancies/2026-02-31",
        "/api/substitucions/2026-13-01",
        "/api/estadistiques/resum?data_inici=ahir",
        "/api/pdf/vigilancies/interval?data_inici=2026-04-20&data_final=dema",
    ],
)
def test_una_data_mal_escrita_o_impossible_dona_400(client, url):
    resp = client.get(url)
    assert resp.status_code == 400, (resp.status_code, resp.text[:200])


@pytest.mark.parametrize(
    "ruta, params",
    [
        ("/api/estadistiques/resum", {}),
        ("/api/estadistiques/professors", {}),
        ("/api/estadistiques/temporal", {}),
        ("/api/estadistiques/classes", {}),
        ("/api/estadistiques/classes/detall", {"grups": "1-ESO-A"}),
        ("/api/estadistiques/taula", {}),
        ("/api/estadistiques/professor/Prof 1", {}),
        ("/api/estadistiques/franges", {"dia": "Dilluns", "hora": "08:00"}),
    ],
)
def test_estadistiques_rebutgen_un_interval_invertit(client, ruta, params):
    # Com els informes: abans responien buit i el PDF donava «error inesperat»
    resp = client.get(ruta, params={"data_inici": "2026-04-21", "data_final": "2026-04-20", **params})

    assert resp.status_code == 400, (resp.status_code, resp.text[:200])
    assert resp.json()["detail"] == "La data inicial ha de ser anterior o igual a la final"
