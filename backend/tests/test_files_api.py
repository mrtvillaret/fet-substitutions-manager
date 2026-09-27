"""
Tests de la pujada de l'horari XML (routes/files.py, upload-xml): versionat,
i que el nom que envia el navegador no permet escriure fora de la carpeta de
la institució ni trepitjar l'XML vigent abans de desar-lo a l'històric.
"""
import uuid
from datetime import date, timedelta

import pytest

from database import DATA_BASE_DIR, get_data_db_session, get_data_dir_for_institucio
from rate_limit import limiter
from repositories import ConfiguracioRepository, XMLVersionRepository
from routes import files
from suport_api import XML_EXEMPLE, client_per, crea_app, crea_usuari, entra, nova_institucio

APP = crea_app(files.router)
URL = "/api/files/upload-xml"
XML = XML_EXEMPLE.read_bytes()


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


def _usuari_de(institucio, role="admin"):
    nom = f"{role}_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, institucio, role)
    return entra(client_per(APP), nom)


@pytest.fixture
def centre():
    return nova_institucio()


@pytest.fixture
def client(centre):
    return _usuari_de(centre)


def _puja(client, nom="horari.xml", contingut=XML, **form):
    return client.post(URL, files={"file": (nom, contingut, "text/xml")}, data=form)


def _xml_actual(centre):
    with get_data_db_session(centre) as db:
        return ConfiguracioRepository.get(db, "xml_horari_path")


def _versions(centre):
    with get_data_db_session(centre) as db:
        return [{"path": v.path, "data_inici": v.data_inici} for v in XMLVersionRepository.list_all(db)]


def _fitxers(centre):
    carpeta = get_data_dir_for_institucio(centre)
    return sorted(str(p.relative_to(carpeta)) for p in carpeta.rglob("*.xml"))


# ------------------------------------------------------------------ accés

def test_nomes_els_admins_poden_pujar_l_horari(centre):
    assert _puja(_usuari_de(centre, role="user")).status_code == 403


def test_nomes_s_accepten_fitxers_xml(client):
    assert _puja(client, nom="horari.txt").status_code == 400


# ---------------------------------------------------------------- versionat

def test_pujar_desa_l_horari_a_l_historic_i_el_fa_vigent(client, centre):
    resp = _puja(client, nom="Curs26-27_teachers.xml")
    assert resp.status_code == 200
    cos = resp.json()
    assert cos["filename"] == "Curs26-27_teachers.xml"
    assert cos["vigent_avui"] is True
    assert cos["path"].startswith("xml_history/horari_")
    assert _xml_actual(centre) == cos["path"]
    assert (get_data_dir_for_institucio(centre) / cos["path"]).read_bytes() == XML
    # Només queda la còpia de l'històric: ni el fitxer amb el nom original ni el temporal.
    assert _fitxers(centre) == [cos["path"]]


def test_pujar_el_mateix_horari_dues_vegades_no_crea_una_versio_nova(client, centre):
    _puja(client)
    resp = _puja(client, data_inici=(date.today() + timedelta(days=1)).isoformat())
    assert resp.status_code == 200
    assert "idèntic" in resp.json()["message"]
    assert len(_versions(centre)) == 1
    assert len(_fitxers(centre)) == 1


def test_un_horari_futur_no_passa_a_ser_vigent_fins_al_seu_dia(client, centre):
    primer = _puja(client).json()["path"]
    demà = (date.today() + timedelta(days=1)).isoformat()
    resp = _puja(client, contingut=XML.replace(b"Prof 1", b"Prof 1b"), data_inici=demà)
    assert resp.json()["vigent_avui"] is False
    assert _xml_actual(centre) == primer
    assert len(_versions(centre)) == 2


def test_una_versio_no_pot_comencar_abans_que_la_vigent(client):
    _puja(client)
    ahir = (date.today() - timedelta(days=1)).isoformat()
    resp = _puja(client, contingut=XML.replace(b"Prof 1", b"Prof 1b"), data_inici=ahir)
    assert resp.status_code == 400


# ------------------------------------------------ nom del fitxer segur

@pytest.mark.parametrize("nom_maliciós", [
    "../{altre}/teachers.xml",
    "../../{altre}/teachers.xml",
    "/tmp/{altre}.xml",
])
def test_el_nom_del_fitxer_no_permet_escriure_fora_de_la_institucio(client, centre, nom_maliciós):
    altre = nova_institucio(amb_xml=True)
    xml_altre = get_data_dir_for_institucio(altre) / "teachers.xml"
    abans = xml_altre.read_bytes()

    resp = _puja(client, nom=nom_maliciós.format(altre=altre), contingut=b"<fals/>")
    assert resp.status_code == 200
    assert resp.json()["filename"] == "teachers.xml" or resp.json()["filename"].endswith(".xml")

    assert xml_altre.read_bytes() == abans
    assert not (DATA_BASE_DIR.parent / f"{altre}.xml").exists()
    assert _fitxers(centre) == [resp.json()["path"]]


def test_pujar_un_fitxer_amb_el_mateix_nom_que_l_xml_vigent_no_perd_l_anterior(centre):
    # Institució que encara llegeix teachers.xml directament, sense versions.
    antiga = nova_institucio(amb_xml=True)
    client = _usuari_de(antiga)
    resp = _puja(client, nom="teachers.xml", contingut=XML.replace(b"Prof 1", b"Prof 1b"))
    assert resp.status_code == 200

    carpeta = get_data_dir_for_institucio(antiga)
    versions = sorted(_versions(antiga), key=lambda v: v["data_inici"])
    assert len(versions) == 2
    # La versió inicial conserva l'horari que hi havia abans de la pujada.
    assert (carpeta / versions[0]["path"]).read_bytes() == XML
    assert (carpeta / versions[1]["path"]).read_bytes() == XML.replace(b"Prof 1", b"Prof 1b")
