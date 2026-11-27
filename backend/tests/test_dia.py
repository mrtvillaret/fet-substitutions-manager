"""
horari.domain.Dia: un dia per a un centre i l'horari (XML) vigent aquell dia.
"""

from datetime import date

import pytest
from suport_rellotge import AVUI
from suport_xml import amb_horari_futur, dia, professor_que_plega

from horari.domain import Dia
from substitucions.context import get_gestors


@pytest.fixture
def centre():
    return amb_horari_futur()


def test_cada_dia_te_l_horari_vigent_aquell_dia(centre):
    abans, despres = Dia(dia(1), centre), Dia(dia(10), centre)
    assert professor_que_plega() in abans.horari.professors
    assert professor_que_plega() not in despres.horari.professors
    assert abans.xml_path.endswith("actual.xml") and despres.xml_path.endswith("futur.xml")


def test_la_versio_de_l_horari_i_des_de_quan_es_vigent(centre):
    assert Dia(dia(10), centre).versio_des_de == dia(3)
    assert Dia(dia(1), centre).versio_des_de == dia(-30)


def test_versio_explicita_per_revisar_un_xml_encara_no_vigent(centre, monkeypatch):
    from horari.repositories import XMLVersionRepository

    versio_nova = Dia(dia(10), centre).versio

    def no_consultar(*args, **kwargs):
        pytest.fail("Amb versió explícita no s'ha de resoldre la vigent")

    monkeypatch.setattr(XMLVersionRepository, "vigent", no_consultar)
    d = Dia(dia(1), centre, versio_xml=versio_nova)
    assert d.versio is versio_nova
    assert d.versio_des_de == dia(3)
    assert d.xml_path.endswith("futur.xml")
    assert professor_que_plega() not in d.horari.professors


def test_avui_i_de_text(centre):
    assert Dia.avui(centre) == Dia(AVUI, centre)
    assert Dia.de_text("2026-04-20", centre) == Dia(date(2026, 4, 20), centre)
    assert Dia.de_text("2026-04-20", centre).iso == "2026-04-20"


def test_els_gestors_son_nous_a_cada_crida(centre):
    # L'horari es reaprofita (memòria cau), però els gestors d'alliberats, absències
    # i substitucions són nous a cada crida: cada petició hi fixa el seu estat
    # (data, vigilants...) i compartits entre peticions es podrien trepitjar
    d = Dia(dia(1), centre)
    assert d.gestors()[0] is not d.gestors()[0]
    assert d.gestors()[1] is d.horari  # l'horari sí (memòria cau)

    subs_1, horari_1, alliberats_1, absencies_1 = get_gestors(centre, data_iso=dia(1))
    subs_2, horari_2, alliberats_2, absencies_2 = get_gestors(centre, data_iso=dia(2))
    assert horari_1 is horari_2
    assert alliberats_1 is not alliberats_2
    assert absencies_1 is not absencies_2
    assert subs_1 is not subs_2
    assert subs_1.alliberats is alliberats_1 and subs_1.absencies is absencies_1

    # La data (i l'estat) d'una crida no afecta una altra
    subs_2.professors_ocupats_examens = {"10:00": {"Prof 21"}}
    subs_3, _, _, _ = get_gestors(centre, data_iso=dia(1))
    assert subs_3.professors_ocupats_examens == {}


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
