"""
Quin horari (XML) es fa servir quan n'hi ha un de pujat amb data futura.
Sense data, el vigent avui: no l'últim pujat, que encara no ha començat.
"""

import pytest
from suport_xml import amb_horari_futur, amb_versions, dia, professor_que_plega

from database import get_data_db_session
from helpers import avui, get_horari, get_xml_path_for_date
from horari.repositories import XMLVersionRepository
from models import Professor


@pytest.fixture
def amb_futur():
    return amb_horari_futur()


def test_sense_data_es_fa_servir_l_horari_vigent_avui(amb_futur):
    assert get_xml_path_for_date(amb_futur, avui()).endswith("actual.xml")


def test_amb_data_es_fa_servir_el_d_aquella_data(amb_futur):
    assert get_xml_path_for_date(amb_futur, dia(10).isoformat()).endswith("futur.xml")
    assert get_xml_path_for_date(amb_futur, dia(1).isoformat()).endswith("actual.xml")


def test_un_professor_que_plega_amb_l_horari_futur_continua_actiu_fins_aleshores(amb_futur):
    get_horari(amb_futur, data_iso=avui())  # sincronitza els professors amb l'horari sense data
    with get_data_db_session(amb_futur) as db:
        prof = db.query(Professor).filter(Professor.nom == professor_que_plega()).one()
        assert prof.actiu


def test_si_nomes_hi_ha_un_horari_futur_es_fa_servir_aquest():
    centre = amb_versions(("futur.xml", dia(5), None))
    assert get_xml_path_for_date(centre, avui()).endswith("futur.xml")


def test_entre_dos_horaris_es_fa_servir_el_seguent():
    # Cap versió cobreix avui (un buit): la que comença després
    centre = amb_versions(("actual.xml", dia(-30), dia(-5)), ("futur.xml", dia(5), None))
    with get_data_db_session(centre) as db:
        assert XMLVersionRepository.vigent(db).path == "futur.xml"


def test_si_tots_els_horaris_son_passats_es_fa_servir_el_darrer():
    centre = amb_versions(("futur.xml", dia(-60), dia(-31)), ("actual.xml", dia(-30), dia(-5)))
    with get_data_db_session(centre) as db:
        assert XMLVersionRepository.vigent(db).path == "actual.xml"
