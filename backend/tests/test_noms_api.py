"""
Regla dels noms en rebre dades de l'API: tot camp o paràmetre que porta un nom
de professor, assignatura (activitat) o aula arriba net (noms.NomNet).
"""

import importlib
import re
import typing
import uuid
from pathlib import Path

import pytest
from fastapi import APIRouter, Depends
from fastapi.routing import APIRoute
from pydantic import BaseModel
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio

from absencia_coberta.router import router as absencia_coberta_router
from auth.dependencies import require_admin
from prioritats.router import router as prioritats_router
from rate_limit import limiter

BACKEND = Path(__file__).resolve().parent.parent

# Noms de camps i paràmetres que són noms de professor, assignatura o aula
ES_NOM = re.compile(
    r"^(professors?|substitut|vigilant|titular|assignatur(a|es)|aula|activitats?|per_defecte|ocupats|ultim_professor_subs|ordre_categories|pesos)$"
)

# Cossos de l'API sense model (un dict, un fitxer, un formulari), revisats un
# per un: o no porten noms, o els netegen en entrar (noms.neteja_noms / nom_net)
COSSOS_REVISATS = {
    # sense noms (grups, nivells, abreviatures, ids, configuració)
    ("POST", "/api/config/nivells"),
    ("PUT", "/api/config/nivells/ordre"),
    ("POST", "/api/config/grups/{nivell}"),
    ("PUT", "/api/config/grups/{nivell}/ordre"),
    ("DELETE", "/api/config/assignacions"),
    ("POST", "/api/config/abreviatures"),
    ("PUT", "/api/config/abreviatures/{abreviatura_id}"),
    ("PUT", "/api/config/afinitats"),
    ("POST", "/api/pdf/disponibles-tots-dies"),
    ("POST", "/api/files/upload-xml"),
    ("POST", "/api/files/upload-logo"),
    # els noms surten de les llistes de la mateixa aplicació (ja nets); pendent
    # de schema quan es migri el mòdul del planificador
    ("PUT", "/api/scheduler/config"),
    ("PUT", "/api/scheduler/costos-professors/{professor}"),
    # netegen els noms en entrar
    ("POST", "/api/config/assignatures/{nivell}"),
    ("PUT", "/api/config/assignatures/{nivell}/ordre"),
    ("POST", "/api/config/aules"),
    ("POST", "/api/config/assignacions"),
    ("PUT", "/api/config/assignacions/{assignacio_id}"),
    ("POST", "/api/config/importar-assignacions/dry-run"),
    ("POST", "/api/config/importar-assignacions"),
    ("POST", "/api/config/importar-assignacions-csv/dry-run"),
    ("POST", "/api/config/importar-assignacions-csv"),
    ("PUT", "/api/scheduler/costos-professors"),
}


def _routers():
    moduls = [f"routes.{p.stem}" for p in (BACKEND / "routes").glob("*.py") if p.stem != "__init__"]
    moduls += [f"{p.parent.name}.router" for p in BACKEND.glob("*/router.py")]
    for nom in sorted(moduls):
        modul = importlib.import_module(nom)
        # router, i també router_admin (dos routers al mateix fitxer)
        for atribut in ("router", "router_admin"):
            router = getattr(modul, atribut, None)
            if isinstance(router, APIRouter):
                yield nom, router


def _rutes():
    for nom, router in _routers():
        for ruta in router.routes:
            if isinstance(ruta, APIRoute):
                for metode in ruta.methods:
                    yield nom, metode, ruta


def _es_nom_net(camp) -> bool:
    # Pydantic deixa el validador a l'anotació (Optional[NomNet], List[NomNet]...)
    # o, si el camp és un NomNet sol, a metadata
    return "_nom_net_validador" in repr(camp.annotation) + repr(camp.metadata)


def _camps(model, prefix=""):
    for nom, camp in model.model_fields.items():
        yield prefix + nom, camp
        for arg in typing.get_args(camp.annotation) or [camp.annotation]:
            for sub in typing.get_args(arg) or [arg]:
                if isinstance(sub, type) and issubclass(sub, BaseModel):
                    yield from _camps(sub, f"{prefix}{nom}.")


def test_tot_nom_que_arriba_per_l_api_es_nom_net():
    errors = []
    for modul, metode, ruta in _rutes():
        lloc = f"{metode} {ruta.path} ({modul})"
        for param in ruta.dependant.path_params + ruta.dependant.query_params:
            if ES_NOM.match(param.name) and not _es_nom_net(param.field_info):
                errors.append(f"{lloc}: paràmetre {param.name}")
        for cos in ruta.dependant.body_params:
            tipus = cos.field_info.annotation
            if isinstance(tipus, type) and issubclass(tipus, BaseModel):
                for nom, camp in _camps(tipus):
                    if ES_NOM.match(nom.split(".")[-1]) and not _es_nom_net(camp):
                        errors.append(f"{lloc}: camp {nom} de {tipus.__name__}")
            elif (metode, ruta.path) not in COSSOS_REVISATS:
                errors.append(f"{lloc}: cos sense model ({cos.name}): porta noms? revisar i afegir a COSSOS_REVISATS")
    assert errors == []


# ----------------------------------------------- de debò, per una petició

APP = crea_app()
APP.include_router(prioritats_router, dependencies=[Depends(require_admin)])
APP.include_router(absencia_coberta_router, dependencies=[Depends(require_admin)])


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


@pytest.fixture
def client():
    centre = nova_institucio()
    nom = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, centre, "admin")
    return entra(client_per(APP), nom)


def test_un_nom_amb_espais_es_desa_net_i_es_la_mateixa_entrada(client):
    url = "/api/prioritats/no-substituir"
    assert client.post(url, json={"assignatura": " Guàrdia "}).status_code == 200
    assert client.get(url).json() == {"assignatures": ["Guàrdia"]}
    assert client.post(url, json={"assignatura": "Guàrdia"}).status_code == 409  # la mateixa
    assert client.post(url, json={"assignatura": "   "}).status_code == 200  # només espais: el buit
    assert client.post(url, json={"assignatura": ""}).status_code == 409
    assert client.delete(f"{url}/%20Guàrdia").status_code == 200  # també a la ruta
    assert client.get(url).json() == {"assignatures": [""]}
