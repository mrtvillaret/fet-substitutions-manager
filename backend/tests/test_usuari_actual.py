"""
Les rutes reben un UsuariActual immutable, no l'objecte de la BD: no es pot
modificar ni desar per error (abans, per al superadmin, l'objecte de la BD
duia la institució activa i calia desvincular-lo de la sessió).
"""

import dataclasses
import uuid

import pytest
from fastapi import APIRouter, Depends
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio

from auth.dependencies import get_current_user
from auth.domain import Rol, UsuariActual
from rate_limit import limiter

rebut = {}
_router = APIRouter()


@_router.get("/prova/usuari")
def _prova(current_user=Depends(get_current_user)):
    rebut["usuari"] = current_user
    return {}


APP = crea_app(_router)


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


def test_la_ruta_rep_un_usuari_actual_immutable():
    centre = nova_institucio()
    nom = f"u_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, centre, "admin")
    assert entra(client_per(APP), nom).get("/prova/usuari").status_code == 200
    usuari = rebut["usuari"]
    assert isinstance(usuari, UsuariActual)
    assert (usuari.username, usuari.role, usuari.institucio) == (nom, "admin", centre)
    with pytest.raises(dataclasses.FrozenInstanceError):
        usuari.institucio = "una_altra"


@pytest.mark.parametrize(
    "rol, es_admin, es_super_admin",
    [(Rol.USER, False, False), (Rol.ADMIN, True, False), (Rol.SUPER_ADMIN, True, True), ("desconegut", False, False)],
)
def test_els_permisos_surten_del_rol(rol, es_admin, es_super_admin):
    usuari = UsuariActual(id=1, username="u", role=rol, institucio="c", versio_sessio=0)
    assert (usuari.es_admin, usuari.es_super_admin) == (es_admin, es_super_admin)
