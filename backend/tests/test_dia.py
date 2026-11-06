"""
horari.domain.Dia: un dia per a un centre i l'horari (XML) vigent aquell dia.
"""

from datetime import date

import pytest
from suport_rellotge import AVUI
from suport_xml import amb_horari_futur, dia, professor_que_plega

from horari.domain import Dia


@pytest.fixture
def centre():
    return amb_horari_futur()


def test_cada_dia_te_l_horari_vigent_aquell_dia(centre):
    abans, despres = Dia(dia(1), centre), Dia(dia(10), centre)
    assert professor_que_plega() in abans.horari.professors
    assert professor_que_plega() not in despres.horari.professors
    assert abans.xml_path.endswith("actual.xml") and despres.xml_path.endswith("futur.xml")


def test_la_versio_de_l_horari_i_des_de_quan_es_vigent(centre):
    assert Dia(dia(10), centre).versio_des_de == dia(3).isoformat()
    assert Dia(dia(1), centre).versio_des_de == dia(-30).isoformat()


def test_avui_i_de_text(centre):
    assert Dia.avui(centre) == Dia(AVUI, centre)
    assert Dia.de_text("2026-04-20", centre) == Dia(date(2026, 4, 20), centre)
    assert Dia.de_text("2026-04-20", centre).iso == "2026-04-20"


def test_els_gestors_son_nous_a_cada_crida(centre):
    # Cada petició hi fixa el seu estat: no s'han de compartir
    d = Dia(dia(1), centre)
    assert d.gestors()[0] is not d.gestors()[0]
    assert d.gestors()[1] is d.horari  # l'horari sí (memòria cau)


def test_una_sola_lectura_de_versio_i_horari_per_dia(centre, monkeypatch):
    from horari import domain as modul
    from horari.repositories import XMLVersionRepository

    lectures = {"versio": 0, "horari": 0}
    vigent, get_horari = XMLVersionRepository.vigent, modul.get_horari

    def versio(*args, **kwargs):
        lectures["versio"] += 1
        return vigent(*args, **kwargs)

    def horari(*args, data_iso, **kwargs):
        lectures["horari"] += 1
        return get_horari(*args, data_iso=data_iso, **kwargs)

    monkeypatch.setattr(XMLVersionRepository, "vigent", versio)
    monkeypatch.setattr(modul, "get_horari", horari)
    d = Dia(dia(1), centre)
    assert d.gestors()[1] is d.horari
    assert d.xml_path and d.versio_des_de
    assert lectures == {"versio": 1, "horari": 1}
