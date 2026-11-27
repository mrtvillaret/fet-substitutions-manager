"""
Les rutes de fitxers (XML de l'horari) són sempre dins la
carpeta del centre. Abans un admin podia escriure des de la configuració la
ruta d'un altre centre i llegir-ne l'horari o llistar-ne i esborrar-ne PDF.
"""

import pytest
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio
from suport_noms import unic

from configuracio import router as configuracio
from configuracio.repositories import ConfiguracioRepository
from database import (
    get_data_db_session,
    get_data_dir_for_institucio,
)
from horari.domain import Dia
from rate_limit import limiter

APP = crea_app(configuracio.router)


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


def _config(centre, clau):
    with get_data_db_session(centre) as db:
        return ConfiguracioRepository.get(db, clau)


def test_la_configuracio_no_deixa_canviar_les_rutes():
    centre, altre = nova_institucio(amb_xml=True), nova_institucio(amb_xml=True)
    nom = f"admin_{unic()}"
    crea_usuari(nom, centre, "admin")
    client = entra(client_per(APP), nom)

    resp = client.put(
        "/api/settings",
        json={
            "xml_horari_path": str(get_data_dir_for_institucio(altre) / "teachers.xml"),
            "export_dir": str(get_data_dir_for_institucio(altre)),
            "idioma": "ca",
        },
    )
    assert resp.status_code == 200, resp.text
    assert _config(centre, "xml_horari_path") == "teachers.xml"
    assert _config(centre, "export_dir") is None


@pytest.mark.parametrize(
    "cami",
    [lambda altre: str(get_data_dir_for_institucio(altre) / "teachers.xml"), lambda altre: f"../{altre}/teachers.xml"],
    ids=["absolut", "amb punts"],
)
def test_un_xml_desat_fora_de_la_carpeta_del_centre_no_es_llegeix(cami):
    centre, altre = nova_institucio(amb_xml=True), nova_institucio(amb_xml=True)
    with get_data_db_session(centre) as db:
        ConfiguracioRepository.set(db, "xml_horari_path", cami(altre))
        db.commit()
    assert Dia.avui(centre).xml_path is None


def test_un_xml_dins_la_carpeta_es_llegeix_igual_amb_ruta_absoluta_o_relativa():
    centre = nova_institucio(amb_xml=True)
    esperat = str(get_data_dir_for_institucio(centre).resolve() / "teachers.xml")
    assert Dia.avui(centre).xml_path == esperat
    with get_data_db_session(centre) as db:
        ConfiguracioRepository.set(db, "xml_horari_path", esperat)
        db.commit()
    assert Dia.avui(centre).xml_path == esperat


@pytest.mark.parametrize("nom", [".", "..", "...", ".amagat", "a..b", "-x", "_x", "a/b", "A", ""])
def test_noms_d_institucio_no_valids(nom):
    with pytest.raises(ValueError):
        get_data_dir_for_institucio(nom)


@pytest.mark.parametrize("nom", ["exemple", "demo", "centre_1", "centre_v2.5.5", "9x"])
def test_noms_d_institucio_valids(nom):
    assert get_data_dir_for_institucio(nom).name == nom
