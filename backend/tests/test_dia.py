"""
serveis.dia.Dia: un dia per a un centre i l'horari (XML) vigent aquell dia.
"""
from datetime import date

import pytest
from suport_xml import amb_horari_futur, dia, professor_que_plega

from serveis.dia import Dia


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
    assert Dia.avui(centre) == Dia(date.today(), centre)
    assert Dia.de_text("2026-04-20", centre) == Dia(date(2026, 4, 20), centre)
    assert Dia.de_text("2026-04-20", centre).iso == "2026-04-20"


def test_els_gestors_son_nous_a_cada_crida(centre):
    # Cada petició hi fixa el seu estat: no s'han de compartir
    d = Dia(dia(1), centre)
    assert d.gestors()[0] is not d.gestors()[0]
    assert d.gestors()[1] is d.horari          # l'horari sí (memòria cau)
