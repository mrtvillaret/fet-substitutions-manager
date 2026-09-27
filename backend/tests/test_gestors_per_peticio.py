"""
get_gestors: l'horari es reaprofita (memòria cau), però els gestors
d'alliberats, absències i substitucions són nous a cada crida. Cada petició
hi fixa el seu estat (data, vigilants...) i compartits entre peticions es
podrien trepitjar.
"""
from datetime import date

from helpers import get_gestors
from suport_api import nova_institucio


def test_cada_crida_te_gestors_propis_pero_el_mateix_horari():
    centre = nova_institucio(amb_xml=True)
    subs_1, horari_1, alliberats_1, absencies_1 = get_gestors(centre, "2026-04-20")
    subs_2, horari_2, alliberats_2, absencies_2 = get_gestors(centre, "2026-04-21")

    assert horari_1 is horari_2
    assert alliberats_1 is not alliberats_2
    assert absencies_1 is not absencies_2
    assert subs_1 is not subs_2
    assert subs_1.alliberats is alliberats_1 and subs_1.absencies is absencies_1


def test_la_data_d_una_crida_no_afecta_una_altra():
    centre = nova_institucio(amb_xml=True)
    _, _, alliberats_1, _ = get_gestors(centre, "2026-04-20")
    subs_2, _, alliberats_2, _ = get_gestors(centre, "2026-04-21")
    subs_2.professors_ocupats_examens = {"10:00": {"Prof 21"}}

    assert alliberats_1.data_actual == date(2026, 4, 20)
    assert alliberats_2.data_actual == date(2026, 4, 21)
    subs_3, _, _, _ = get_gestors(centre, "2026-04-20")
    assert subs_3.professors_ocupats_examens == {}
