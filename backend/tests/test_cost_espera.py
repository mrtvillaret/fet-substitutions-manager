"""
Cost d'un titular que ha de vigilar un examen fora de la seva jornada: compta
cada hora que ha d'esperar, pati inclòs, des de l'examen fins a la primera
classe (arriba abans) o des de l'última classe fins a l'examen (es queda
després). Si ha de venir a les 9 i començava a les 11:30, amb el pati entremig,
són 3 hores.
"""
import pytest

from scheduler_engine.core.availability import analitzar_disponibilitat_sessio
from scheduler_engine.core.normalitzacio import normalitzar_dia
from scheduler_engine.core.scoring import costos_professors_analisi

HORES = ["08:00", "09:00", "10:00", "PATI", "11:30", "12:30", "13:30", "14:30"]
CLASSES = {normalitzar_dia("Dilluns"): {"11:30": {"assignatura": "Mat", "grup": "3-ESO-A"},
                                        "12:30": {"assignatura": "Mat", "grup": "3-ESO-B"}}}
SESSIO = {"nom": "Filosofia (1-BAT)", "curs": "1-BAT", "examens": [{"grup": "1-BAT-A", "titular": "Prof X"}]}


def _analisi(inici, durada=1):
    idx = HORES.index(inici)
    hores = HORES[idx:idx + durada]
    return analitzar_disponibilitat_sessio(SESSIO, "Dilluns", inici, {"Prof X": CLASSES}, HORES, ["1-BAT"],
                                           durada_titular=durada, hores_override=hores, hores_supervisio=hores)


@pytest.mark.parametrize("inici, durada, hores_abans", [
    ("10:00", 1, ["10:00", "PATI"]),
    ("09:00", 1, ["09:00", "10:00", "PATI"]),
    ("08:00", 1, ["08:00", "09:00", "10:00", "PATI"]),
    ("09:00", 2, ["09:00", "10:00", "PATI"]),          # cada hora compta un sol cop
])
def test_arribar_abans_compta_cada_hora_fins_a_la_primera_classe(inici, durada, hores_abans):
    analisi = _analisi(inici, durada)
    assert [i["hora"] for i in analisi["abans_jornada"]] == hores_abans
    assert sum(costos_professors_analisi(analisi, inici, {}).values()) == 30 * len(hores_abans)


@pytest.mark.parametrize("inici, hores_despres", [
    ("13:30", ["13:30"]),
    ("14:30", ["13:30", "14:30"]),
])
def test_quedar_se_despres_compta_cada_hora_des_de_l_ultima_classe(inici, hores_despres):
    analisi = _analisi(inici)
    assert [i["hora"] for i in analisi["despres_jornada"]] == hores_despres
    assert sum(costos_professors_analisi(analisi, inici, {}).values()) == 30 * len(hores_despres)


def test_dins_la_jornada_no_hi_ha_cost_d_espera():
    analisi = _analisi("12:30")         # té classe: és una substitució, no una espera
    assert analisi["abans_jornada"] == [] and analisi["despres_jornada"] == []
