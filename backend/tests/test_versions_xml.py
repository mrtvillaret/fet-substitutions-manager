"""
Versions de l'horari (XML): només es tria quan comença cadascuna. La data de
fi es calcula sempre (el dia abans que comenci la següent; l'última, oberta),
en una sola operació, com els cursos: no hi pot haver forats ni solapaments.
"""

import uuid

import pytest
from fastapi import Depends
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio
from suport_xml import amb_versions, dia

from auth.dependencies import require_admin
from database import get_data_db_session, get_data_dir_for_institucio
from horari import router as horari
from models import XMLVersion
from rate_limit import limiter
from repositories import ConfiguracioRepository

APP = crea_app()
APP.include_router(horari.router_admin, dependencies=[Depends(require_admin)])  # com a main.py
URL = "/api/settings/xml-versions"


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


def _client(centre):
    nom = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, centre, "admin")
    return entra(client_per(APP), nom)


def _cadena(centre):
    with get_data_db_session(centre) as db:
        return [(v.path, v.data_inici, v.data_fi) for v in db.query(XMLVersion).order_by(XMLVersion.data_inici)]


def _id(centre, path):
    with get_data_db_session(centre) as db:
        return db.query(XMLVersion).filter(XMLVersion.path == path).one().id


def _punter(centre):
    with get_data_db_session(centre) as db:
        return ConfiguracioRepository.get(db, "xml_horari_path")


@pytest.fixture
def centre():
    # Dues versions amb un forat entre elles (com podia quedar abans)
    return amb_versions(("actual.xml", dia(-30), dia(-10)), ("futur.xml", dia(3), None))


def test_canviar_l_inici_d_una_versio_recalcula_la_fi_de_l_anterior(centre):
    client = _client(centre)
    assert client.put(f"{URL}/{_id(centre, 'futur.xml')}", json={"data_inici": dia(5).isoformat()}).status_code == 200
    assert _cadena(centre) == [("actual.xml", dia(-30), dia(4)), ("futur.xml", dia(5), None)]


def test_la_data_de_fi_no_es_pot_posar_a_ma(centre):
    client = _client(centre)
    resp = client.put(
        f"{URL}/{_id(centre, 'actual.xml')}", json={"data_inici": dia(-30).isoformat(), "data_fi": dia(-20).isoformat()}
    )
    assert resp.status_code == 200
    assert _cadena(centre)[0] == ("actual.xml", dia(-30), dia(2))  # la que toca, no la demanada


def test_dues_versions_no_poden_comencar_el_mateix_dia(centre):
    client = _client(centre)
    resp = client.put(f"{URL}/{_id(centre, 'futur.xml')}", json={"data_inici": dia(-30).isoformat()})
    assert resp.status_code == 400


def test_una_data_mal_escrita_dona_400(centre):
    assert (
        _client(centre).put(f"{URL}/{_id(centre, 'futur.xml')}", json={"data_inici": "20/10/2026"}).status_code == 400
    )


def test_esborrar_la_darrera_reobre_l_anterior_i_mou_el_punter(centre):
    client = _client(centre)
    assert client.delete(f"{URL}/{_id(centre, 'futur.xml')}").status_code == 200
    assert _cadena(centre) == [("actual.xml", dia(-30), None)]
    assert _punter(centre) == "actual.xml"


def test_esborrar_una_versio_del_mig_no_deixa_cap_forat():
    centre = amb_versions(
        ("actual.xml", dia(-60), dia(-31)), ("futur.xml", dia(-30), dia(2)), ("teachers.xml", dia(3), None)
    )
    client = _client(centre)
    assert client.delete(f"{URL}/{_id(centre, 'futur.xml')}").status_code == 200
    assert _cadena(centre) == [("actual.xml", dia(-60), dia(2)), ("teachers.xml", dia(3), None)]


def test_el_punter_es_la_versio_vigent_avui(centre):
    client = _client(centre)
    client.put(f"{URL}/{_id(centre, 'futur.xml')}", json={"data_inici": dia(-1).isoformat()})
    assert _punter(centre) == "futur.xml"


def test_esborrar_una_versio_n_esborra_el_fitxer(centre):
    # Abans el fitxer es quedava a la carpeta (des de la web no es podia recuperar)
    carpeta = get_data_dir_for_institucio(centre)
    assert _client(centre).delete(f"{URL}/{_id(centre, 'futur.xml')}").status_code == 200
    assert not (carpeta / "futur.xml").exists()
    assert (carpeta / "actual.xml").exists()


def test_no_esborra_un_fitxer_que_fa_servir_una_altra_versio():
    centre = amb_versions(("actual.xml", dia(-30), dia(-1)), ("actual.xml", dia(0), None))
    with get_data_db_session(centre) as db:
        primera = db.query(XMLVersion).order_by(XMLVersion.data_inici).first().id
    assert _client(centre).delete(f"{URL}/{primera}").status_code == 200
    assert (get_data_dir_for_institucio(centre) / "actual.xml").exists()


def test_no_esborra_res_de_fora_de_la_carpeta_del_centre(centre):
    altre = nova_institucio(amb_xml=True)
    with get_data_db_session(centre) as db:
        db.query(XMLVersion).filter(XMLVersion.path == "futur.xml").update({"path": f"../{altre}/teachers.xml"})
        db.commit()
    assert _client(centre).delete(f"{URL}/{_id(centre, f'../{altre}/teachers.xml')}").status_code == 200
    assert (get_data_dir_for_institucio(altre) / "teachers.xml").exists()
