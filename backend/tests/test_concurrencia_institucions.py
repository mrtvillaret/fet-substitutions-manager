"""
Peticions simultànies d'usuaris de dues institucions al mateix backend: cap
resposta pot contenir dades de l'altra institució.

Abans, la institució de la petició es desava en una variable global
(la configuració global) i les prioritats es reescrivien globalment a cada
petició: amb només dues peticions alhora, prop de la meitat de les respostes
eren de l'altra institució. Aquí es fa amb un servidor uvicorn de veritat
(fils i bucle d'esdeveniments reals), no amb el client de test.
"""

import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import APIRouter, Depends
from suport_api import CONTRASENYA, XML_EXEMPLE, crea_app, crea_usuari, nova_institucio
from suport_noms import unic
from suport_servidor import peticio, servidor_uvicorn

import i18n_setup
import rellotge
from auth.dependencies import get_current_user
from configuracio.repositories import ConfiguracioRepository
from database import get_data_db_session, get_data_dir_for_institucio
from i18n_setup import _
from prioritats.memoria import no_substituir_a
from prioritats.repositories import NoSubstituirRepository
from vigilancies.router import router as vigilancies_router

PETICIONS = 400
FILS = 16

# Ruta de prova que retorna textos traduïts pel backend
_textos = APIRouter()


@_textos.get("/api/prova/no-substituir")
def no_substituir(_usuari=Depends(get_current_user)):
    return {"no_substituir": sorted(no_substituir_a(rellotge.avui().isoformat())), "institucio": _usuari.institucio}


@_textos.get("/api/prova/textos")
def textos(_usuari=Depends(get_current_user)):
    return {"dia": i18n_setup.translate("Dilluns"), "idioma": i18n_setup.idioma_actual(), "traduccio": _("Professor")}


@pytest.fixture(scope="module")
def servidor():
    # Institució A: horari d'exemple (Prof N). Institució B: el mateix horari
    # amb els professors renombrats (Docent N). Cadascuna amb una activitat
    # pròpia que no se substitueix.
    a, b = nova_institucio(amb_xml=True), nova_institucio(amb_xml=True)
    (get_data_dir_for_institucio(b) / "teachers.xml").write_bytes(
        XML_EXEMPLE.read_bytes().replace(b'name="Prof ', b'name="Docent ')
    )
    for inst, activitat, idioma in ((a, "Reunió A", "ca"), (b, "Reunió B", "es")):
        with get_data_db_session(inst) as db:
            NoSubstituirRepository.create(db, activitat)
            db.commit()
            ConfiguracioRepository.set(db, "idioma", idioma)
            db.commit()

    with servidor_uvicorn(crea_app(vigilancies_router, _textos)) as port:
        galetes = {}
        for inst in (a, b):
            nom = f"admin_{unic()}"
            crea_usuari(nom, inst, "admin")
            estat, _, galeta = peticio(port, "POST", "/api/login", {"username": nom, "password": CONTRASENYA})
            assert estat == 200
            galetes[inst] = galeta.split(";")[0]
        yield port, a, b, galetes


def _en_paral·lel(funcio, feines):
    with ThreadPoolExecutor(max_workers=FILS) as ex:
        return list(ex.map(funcio, feines))


def test_l_horari_no_es_barreja_entre_institucions(servidor):
    port, a, b, galetes = servidor

    def una(inst):
        estat, cos, _ = peticio(port, "GET", "/api/vigilancies/config", galeta=galetes[inst])
        assert estat == 200
        professors = json.loads(cos)["professors"]
        esperat, altre = ("Prof", "Docent") if inst == a else ("Docent", "Prof")
        return all(p.startswith(esperat) for p in professors) and not any(p.startswith(altre) for p in professors)

    resultats = _en_paral·lel(una, [a if i % 2 == 0 else b for i in range(PETICIONS)])
    assert resultats.count(False) == 0, (
        f"{resultats.count(False)} de {PETICIONS} respostes amb dades de l'altra institució"
    )


def test_les_prioritats_no_es_barregen_entre_institucions(servidor):
    port, a, b, galetes = servidor

    def una(inst):
        estat, cos, _ = peticio(port, "GET", "/api/prova/no-substituir", galeta=galetes[inst])
        assert estat == 200
        dades = json.loads(cos)
        esperat = ["Reunió A"] if inst == a else ["Reunió B"]
        return dades["no_substituir"] == esperat and dades["institucio"] == inst

    resultats = _en_paral·lel(una, [a if i % 2 == 0 else b for i in range(PETICIONS)])
    assert resultats.count(False) == 0, (
        f"{resultats.count(False)} de {PETICIONS} respostes amb dades de l'altra institució"
    )


def test_l_idioma_no_es_barreja_entre_institucions(servidor):
    port, a, b, galetes = servidor
    esperat = {
        a: {"dia": "Dilluns", "idioma": "ca", "traduccio": "Professor"},
        b: {"dia": "Lunes", "idioma": "es", "traduccio": "Profesor"},
    }

    def una(inst):
        estat, cos, _ = peticio(port, "GET", "/api/prova/textos", galeta=galetes[inst])
        assert estat == 200
        dades = json.loads(cos)
        assert dades == esperat[inst], {"rebut": dades, "esperat": esperat[inst]}
        return True

    resultats = _en_paral·lel(una, [a if i % 2 == 0 else b for i in range(PETICIONS)])
    assert resultats.count(False) == 0, (
        f"{resultats.count(False)} de {PETICIONS} respostes en l'idioma de l'altra institució"
    )
