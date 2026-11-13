"""El validador i el cost donen els mateixos punts a cada incidència.

Abans el validador tenia uns pesos per defecte propis (restricció dura 1000 en
lloc de 10000, violada = dura en lloc de 20000, dies diferents 500 en lloc de 0)
i el límit per professor hi valia 600 on el cost en comptava 6000. Ara tots dos
treuen els punts de `scheduler_engine/core/punts.py`.
"""

import re

import pytest

from scheduler_engine.core.constraints import calcular_penalitzacio_total_professors
from scheduler_engine.core.punts import punts_limit_professor, punts_restriccio
from scheduler_engine.core.scoring import calcular_cost_slot
from scheduler_engine.validacio import ValidadorHorari

PROF = "Prof 1"


def _sessio(nom: str, curs: str = "1-BAT", professor: str = PROF) -> dict:
    return {"nom": f"{nom} ({curs})", "nom_base": nom, "curs": curs, "examens": [{"titular": professor}]}


def _horari(*franges) -> dict:
    """franges: (dia, hora, [sessions])"""
    dies = {}
    for dia, hora, sessions in franges:
        dies.setdefault(dia, []).append({"hora": hora, "sessions_simultanees": sessions})
    return {"dies": [{"dia": dia, "sessions": sessions} for dia, sessions in dies.items()], "metadata": {}}


def _punts(linia: str) -> int:
    return int(re.search(r"\(punt: (-?\d+)\)$", linia).group(1))


def _linies(restriccions: dict, horari: dict, marca: str) -> list[str]:
    return [linia for linia in ValidadorHorari(horari, restriccions, set()).validar()["logs"] if marca in linia]


def _limit(pes, max_examens=0, **pesos) -> dict:
    restr = {
        "restriccions_dures": {
            "professors_limit_dies_especifics": {
                PROF: {
                    "assignatures": ["Filosofia", "Història"],
                    "dies_restringits": ["Dilluns"],
                    "max_examens": max_examens,
                    "pes_penalitzacio": pes,
                }
            }
        }
    }
    if pesos:
        restr["pesos_optimitzacio"] = pesos
    return restr


@pytest.mark.parametrize("pes", [60, 100])
@pytest.mark.parametrize("pesos", [{}, {"restriccio_dura": 1000, "restriccio_dura_violada": 3000}])
@pytest.mark.parametrize("examens", [1, 2])
def test_limit_per_professor_val_el_mateix_al_validador_i_al_cost(pes, pesos, examens):
    sessions = [_sessio("Filosofia"), _sessio("Història")][:examens]
    horari = _horari(*[("Dilluns", hora, [s]) for hora, s in zip(("08:00", "09:00"), sessions, strict=False)])
    restr = _limit(pes, **pesos)
    [linia] = _linies(restr, horari, "LÍMIT DIES")
    cost = calcular_penalitzacio_total_professors({"Dilluns": sessions}, restr)
    assert _punts(linia) == cost == punts_limit_professor(restr, pes, examens)


def test_el_cas_conegut_600_contra_6000():
    # Pes 60 %, sense pesos desats: abans el validador hi posava 600
    horari = _horari(("Dilluns", "08:00", [_sessio("Filosofia")]))
    [linia] = _linies(_limit(60), horari, "LÍMIT DIES")
    assert _punts(linia) == 6000


def test_pesos_per_defecte_iguals_que_al_cost():
    assert punts_restriccio({}, 50) == 5000
    assert punts_restriccio({}, 100) == 20000
    assert punts_restriccio({"pesos_optimitzacio": {"restriccio_dura": 1000}}, 100) == 20000
    assert punts_restriccio({"pesos_optimitzacio": {"restriccio_dura_violada": 7}}, 100) == 7


@pytest.mark.parametrize("pes", [40, 100])
def test_no_mateix_slot_val_el_mateix_que_cada_sessio_al_cost(pes):
    a, b = _sessio("Física"), _sessio("Química", curs="2-BAT", professor="Prof 2")
    restr = {"restriccions_dures": {"no_mateix_slot": {"G": ["Física", "Química"], "_pes_G": pes}}}
    horari = _horari(("Dilluns", "08:00", [a, b]))
    # Una línia per examen, com el cost (cada examen del grup en suma)
    linia, _ = _linies(restr, horari, "NO AL MATEIX MOMENT")
    buida = {"substitucions": [], "abans_jornada": [], "despres_jornada": [], "no_treballa_dia": []}
    cost = calcular_cost_slot(a, "Dilluns", "08:00", buida, restr, sessions_dia=[a, b], sessions_slot=[a, b])
    assert _punts(linia) == cost["breakdown"]["no_mateix_slot"] == punts_restriccio(restr, pes)


@pytest.mark.parametrize("pes", [30, 100])
def test_no_mateix_dia_val_el_mateix_que_cada_sessio_al_cost(pes):
    a, b = _sessio("Física"), _sessio("Química")
    restr = {"restriccions_dures": {"no_mateix_dia": [{"assignatures": ["Física", "Química"], "pes": pes}]}}
    horari = _horari(("Dilluns", "08:00", [a]), ("Dilluns", "09:00", [b]))
    linia, _ = _linies(restr, horari, "DIES DISTINTS")
    buida = {"substitucions": [], "abans_jornada": [], "despres_jornada": [], "no_treballa_dia": []}
    cost = calcular_cost_slot(a, "Dilluns", "08:00", buida, restr, sessions_dia=[a, b], sessions_slot=[a])
    assert _punts(linia) == cost["breakdown"]["restriccio_dura"] == punts_restriccio(restr, pes)
