"""
Quin horari (XML) es fa servir quan n'hi ha un de pujat amb data futura.
Sense data, el vigent avui: no l'últim pujat, que encara no ha començat.
"""

import pytest
from suport_xml import amb_horari_futur, amb_versions, dia, professor_que_plega

import rellotge
from database import get_data_db_session
from horari.context import avui, get_xml_path_for_date
from horari.repositories import XMLVersionRepository
from horari.sincronitzacio import sincronitza_un_cop_al_dia
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
    sincronitza_un_cop_al_dia(amb_futur)  # explícit, com a la primera petició del dia
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


def test_un_error_de_sincronitzacio_no_bloqueja_el_centre(amb_futur, monkeypatch, caplog):
    """Un XML vigent il·legible no fa fallar les peticions: l'error queda al
    registre i es reintenta més tard, sense rellegir l'XML a cada petició."""
    from horari import sincronitzacio

    crides = []

    def falla(db, institucio):
        crides.append(institucio)
        raise ValueError("XML il·legible")

    rellotge_monotonic = [1000.0]
    monkeypatch.setattr(sincronitzacio, "sincronitza_professors", falla)
    monkeypatch.setattr(sincronitzacio.time, "monotonic", lambda: rellotge_monotonic[0])
    monkeypatch.setitem(sincronitzacio._ultim_dia, amb_futur, None)
    sincronitzacio._ultim_error.pop(amb_futur, None)

    sincronitza_un_cop_al_dia(amb_futur)  # no llança
    assert crides == [amb_futur]
    assert "No s'han pogut sincronitzar" in caplog.text
    assert sincronitzacio._ultim_dia[amb_futur] is None  # no es dona per fet

    rellotge_monotonic[0] += sincronitzacio.REINTENT_DESPRES_D_ERROR - 1
    sincronitza_un_cop_al_dia(amb_futur)  # dins l'espera: no ho torna a provar
    assert crides == [amb_futur]

    monkeypatch.undo()  # l'XML torna a ser llegible
    rellotge_monotonic[0] += 2
    monkeypatch.setattr(sincronitzacio.time, "monotonic", lambda: rellotge_monotonic[0])
    sincronitza_un_cop_al_dia(amb_futur)  # passada l'espera: ho torna a provar i ho aconsegueix
    assert sincronitzacio._ultim_dia[amb_futur] == rellotge.avui()
    assert amb_futur not in sincronitzacio._ultim_error
