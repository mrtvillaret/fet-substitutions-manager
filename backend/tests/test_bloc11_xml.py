"""Impacte dels canvis d'XML, sempre amb centres i fitxers de prova."""

import subprocess
import uuid
import xml.etree.ElementTree as ET

import pytest
from suport_api import XML_EXEMPLE, client_per, crea_app, crea_usuari, entra, nova_institucio

from configuracio.repositories import ConfiguracioRepository
from database import get_data_db_session, get_data_dir_for_institucio
from horari.context import invalidar_horari
from pdf.router import router as pdf_router
from substitucions.router import router as substitucions_router
from vigilancies.router import router as vigilancies_router

DATA = "2026-11-09"


@pytest.mark.parametrize(
    "idioma,text",
    [
        ("ca", "Prof 21 no és a l’horari d’aquell dia"),
        ("es", "Prof 21 no está en el horario de ese día"),
        ("en", "Prof 21 is not in that day's timetable"),
        ("it", "Prof 21 non è nell'orario di quel giorno"),
    ],
)
@pytest.mark.parametrize("absent", [False, True])
def test_vigilant_que_plega_es_important_a_pantalla_revisio_i_pdf(idioma, text, absent):
    centre = nova_institucio(amb_xml=True)
    with get_data_db_session(centre) as db:
        ConfiguracioRepository.set(db, "idioma", idioma)
        db.commit()
    nom = "bloc11_" + uuid.uuid4().hex[:8]
    crea_usuari(nom, centre, "admin")
    client = entra(client_per(crea_app(vigilancies_router, pdf_router, substitucions_router)), nom)
    r = client.post(
        f"/api/vigilancies/{DATA}",
        json={"hora": "10:00", "tipus": "Prova", "grups": "G1", "aula": "A1", "vigilant": "Prof 21", "nivell": "N1"},
    )
    assert r.status_code == 200, r.text
    if absent:
        r = client.put(
            f"/api/substitucions/{DATA}/absencies/Prof 21",
            json={"hores_absencia": ["10:00"], "updated_at_map": {}},
        )
        assert r.status_code == 200, r.text
    abans = client.get(f"/api/vigilancies/{DATA}").json()
    arbre = ET.parse(XML_EXEMPLE)
    arrel = arbre.getroot()
    for professor in arrel.findall("Teacher"):
        if professor.get("name", "").strip() == "Prof 21":
            arrel.remove(professor)
    arbre.write(get_data_dir_for_institucio(centre) / "teachers.xml", encoding="utf-8")
    invalidar_horari(centre)

    ps = client.get(f"/api/vigilancies/{DATA}/analisi").json()
    [problema] = [p for p in ps if p["tipus"] == "vigilant_fora_horari"]
    assert problema["gravetat"] == "important"
    assert problema["professor"] == "Prof 21"
    assert text in problema["missatge"]
    revisio = client.get(f"/api/pdf/{DATA}/validacions").json()
    assert revisio["problemes_vigilancies"] == ps
    assert problema["missatge"] in revisio["conflicts"]
    for ruta in [
        f"/api/pdf/vigilancies/{DATA}",
        f"/api/pdf/complete/{DATA}",
        f"/api/pdf/vigilancies/interval?data_inici={DATA}&data_final={DATA}",
    ]:
        r = client.get(ruta)
        assert r.status_code == 200, r.text[:200]
        contingut = subprocess.run(
            ["pdftotext", "-", "-"], input=r.content, capture_output=True, check=True
        ).stdout.decode()
        assert text in " ".join(contingut.split())
    assert client.get(f"/api/vigilancies/{DATA}").json() == abans
