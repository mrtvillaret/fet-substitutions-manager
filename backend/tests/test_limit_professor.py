"""Límit d'exàmens per professor als dies restringits.

La regla ha de comptar igual a la versió dura (pes 100), a la tova (pes < 100)
i al cost final: els exàmens ja posats als dies restringits més el candidat.
"""

import pytest

from planificador.cost import excessos_limit_dies
from scheduler_engine.core.constraints import (
    calcular_penalitzacio_professors_dies,
    calcular_penalitzacio_professors_dies_item,
    calcular_penalitzacio_total_professors,
    viola_limit_dies_professor_obligatori,
)

PROF = "Prof 1"
PENALITZACIO_60 = 6000  # 60 % de 10000


def _sessio(n: int, professor: str = PROF) -> dict:
    nom = f"Matèria {n} (1-BAT)"
    return {"nom": nom, "nom_base": f"Matèria {n}", "curs": "1-BAT", "examens": [{"titular": professor}]}


def _restriccions(max_examens: int, pes: int, dies=("Dilluns",), n_materies: int = 6) -> dict:
    return {
        "restriccions_dures": {
            "professors_limit_dies_especifics": {
                PROF: {
                    "assignatures": [f"Matèria {n}" for n in range(n_materies)],
                    "dies_restringits": list(dies),
                    "max_examens": max_examens,
                    "pes_penalitzacio": pes,
                }
            }
        }
    }


def _horari(dia: str, sessions: list) -> dict:
    return {"dies": [{"dia": dia, "sessions": [{"hora": "08:00", "sessions_simultanees": sessions}]}]}


# --- A1: el cost final ha de trobar els dies encara que canviïn les majúscules ---


@pytest.mark.parametrize("clau_dia", ["dilluns", "Dilluns", "2026-11-09"])
@pytest.mark.parametrize("dia_config", ["Dilluns", "dilluns"])
def test_cost_final_compta_el_limit_amb_qualsevol_forma_del_dia(clau_dia, dia_config):
    sessions = {clau_dia: [_sessio(0), _sessio(1)]}
    restr = _restriccions(0, 60, dies=(dia_config,))
    assert calcular_penalitzacio_total_professors(sessions, restr) == 2 * PENALITZACIO_60


def test_cost_final_no_compta_els_dies_no_restringits():
    sessions = {"dimarts": [_sessio(0), _sessio(1)]}
    assert calcular_penalitzacio_total_professors(sessions, _restriccions(0, 60)) == 0


@pytest.mark.parametrize("dia_horari", ["Dilluns", "dilluns"])
@pytest.mark.parametrize("dia_config", ["Dilluns", "dilluns"])
def test_excessos_de_la_pantalla_amb_qualsevol_forma_del_dia(dia_horari, dia_config):
    horari = _horari(dia_horari, [_sessio(0), _sessio(1)])
    assert excessos_limit_dies(horari, _restriccions(1, 60, dies=(dia_config,))) == [f"{PROF} +1"]


# --- A2: la versió tova compta el candidat, com la dura ---


def test_amb_limit_zero_el_primer_examen_ja_penalitza():
    restr = _restriccions(0, 60)
    assert calcular_penalitzacio_professors_dies(_sessio(0), "Dilluns", {}, restr) == PENALITZACIO_60
    item = {"sessions": [_sessio(0)]}
    assert calcular_penalitzacio_professors_dies_item(item, "Dilluns", {}, restr) == PENALITZACIO_60


@pytest.mark.parametrize("max_examens", [0, 1, 2])
@pytest.mark.parametrize("ja_posats", [0, 1, 2, 3])
def test_dura_i_tova_compten_el_mateix(max_examens, ja_posats):
    posades = {"Dilluns": [_sessio(n) for n in range(ja_posats)]}
    candidata = _sessio(5)
    excedent = max(0, ja_posats + 1 - max_examens)

    dura = viola_limit_dies_professor_obligatori(candidata, "Dilluns", posades, _restriccions(max_examens, 100))
    assert dura is (excedent > 0)

    tova = _restriccions(max_examens, 60)
    assert calcular_penalitzacio_professors_dies(candidata, "Dilluns", posades, tova) == excedent * PENALITZACIO_60
    item = {"sessions": [candidata]}
    assert calcular_penalitzacio_professors_dies_item(item, "Dilluns", posades, tova) == excedent * PENALITZACIO_60


def test_el_candidat_no_es_compta_dos_cops_si_ja_es_al_mapa():
    """La matriu de costos del greedy passa l'ítem mateix com a sessions del dia."""
    candidata = _sessio(0)
    restr = _restriccions(0, 60)
    item = {"sessions": [candidata]}
    assert calcular_penalitzacio_professors_dies_item(item, "Dilluns", {"Dilluns": [candidata]}, restr) == (
        PENALITZACIO_60
    )
    assert calcular_penalitzacio_professors_dies(candidata, "Dilluns", {"Dilluns": [candidata]}, restr) == (
        PENALITZACIO_60
    )


def test_el_candidat_en_un_dia_no_restringit_no_penalitza():
    posades = {"Dilluns": [_sessio(0), _sessio(1)]}
    restr = _restriccions(0, 60)
    assert calcular_penalitzacio_professors_dies(_sessio(5), "Dimarts", posades, restr) == 0
    assert not viola_limit_dies_professor_obligatori(_sessio(5), "Dimarts", posades, _restriccions(0, 100))


def test_examens_d_altres_professors_o_materies_no_compten():
    posades = {"Dilluns": [_sessio(0, professor="Prof 2"), _sessio(9)]}
    restr = _restriccions(1, 60)
    assert calcular_penalitzacio_professors_dies(_sessio(5), "Dilluns", posades, restr) == 0
