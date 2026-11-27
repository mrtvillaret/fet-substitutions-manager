"""
Quin horari (XML) es fa servir quan n'hi ha un de pujat amb data futura.
Sense data, el vigent avui: no l'últim pujat, que encara no ha començat.
"""

import pytest
from suport_xml import amb_horari_futur, amb_versions, dia, professor_que_plega

import rellotge
from database import get_data_db_session
from horari.context import horaris_per_dates
from horari.domain import Dia
from horari.repositories import XMLVersionRepository
from horari.sincronitzacio import sincronitza_un_cop_al_dia
from models import AbsenciaCoberta, Professor


@pytest.fixture
def amb_futur():
    return amb_horari_futur()


def test_sense_data_es_fa_servir_l_horari_vigent_avui(amb_futur):
    assert Dia.avui(amb_futur).xml_path.endswith("actual.xml")


def test_amb_data_es_fa_servir_el_d_aquella_data(amb_futur):
    assert Dia(dia(10), amb_futur).xml_path.endswith("futur.xml")
    assert Dia(dia(1), amb_futur).xml_path.endswith("actual.xml")


def test_un_professor_que_plega_amb_l_horari_futur_continua_actiu_fins_aleshores(amb_futur):
    sincronitza_un_cop_al_dia(amb_futur)  # explícit, com a la primera petició del dia
    with get_data_db_session(amb_futur) as db:
        prof = db.query(Professor).filter(Professor.nom == professor_que_plega()).one()
        assert prof.actiu


def test_si_nomes_hi_ha_un_horari_futur_es_fa_servir_aquest():
    centre = amb_versions(("futur.xml", dia(5), None))
    assert Dia.avui(centre).xml_path.endswith("futur.xml")


def test_entre_dos_horaris_es_fa_servir_el_seguent():
    # Cap versió cobreix avui (un buit): la que comença després
    centre = amb_versions(("actual.xml", dia(-30), dia(-5)), ("futur.xml", dia(5), None))
    with get_data_db_session(centre) as db:
        assert XMLVersionRepository.vigent(db).path == "futur.xml"


def test_si_tots_els_horaris_son_passats_es_fa_servir_el_darrer():
    centre = amb_versions(("futur.xml", dia(-60), dia(-31)), ("actual.xml", dia(-30), dia(-5)))
    with get_data_db_session(centre) as db:
        assert XMLVersionRepository.vigent(db).path == "actual.xml"


def test_horaris_d_interval_trien_versio_als_extrems_i_apliquen_les_absencies_de_cada_dia():
    centre = amb_versions(("actual.xml", dia(-30), dia(0)), ("futur.xml", dia(3), None))
    professor = professor_que_plega()
    with get_data_db_session(centre) as db:
        db.add(AbsenciaCoberta(professor=professor, data_inici=dia(0), data_final=dia(0)))
        db.commit()
        horari_de = horaris_per_dates(db)

        darrer = horari_de(dia(0))
        assert darrer.xml_path.endswith("actual.xml")
        assert professor not in darrer.professors

        primer = horari_de(dia(-30))
        assert primer is darrer.sencer
        assert professor in primer.professors

        forat = horari_de(dia(1))
        assert forat.xml_path.endswith("futur.xml")
        assert forat is horari_de(dia(3))


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
