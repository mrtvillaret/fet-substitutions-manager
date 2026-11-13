"""Les tres causes de «dia_hora_fix» per separat: el pin de l'examen,
la franja prohibida i l'hora que el nivell no té
marcada com a inici. Quines franges són vàlides no canvia: la composició
(`percent_dia_hora_fix_violation`, la del cost) dona el mateix que abans."""

from collections import Counter

import pytest

from scheduler_engine.core.constraints import causa_dia_hora_fix, percent_dia_hora_fix_violation
from scheduler_engine.core.restriction_engine import RestrictionEngine, causa_principal

SESSIO = {"nom": "Fil (1-BAT)", "curs": "1-BAT", "examens": []}
INICIS = {"1-BAT": {"Dilluns": ["09:00"], "Dimarts": ["09:00", "11:30"]}}


def _restriccions(**dures):
    return {"restriccions_dures": dures}


def _check(dia, hora, prefix, **dures):
    violacio = RestrictionEngine(_restriccions(**dures), ["1-BAT"]).check_hard(SESSIO, dia, hora, prefix, [], [], None)
    return violacio.restriction if violacio else None


@pytest.mark.parametrize(
    "dures, franja, esperat",
    [
        ({"assignatures_dia_fix": {"Fil (1-BAT)": "Dimarts"}}, ("Dilluns", "09:00", "2026-04-20"), "examen_fixat"),
        ({"assignatures_dia_fix": {"Fil (1-BAT)": "2026-04-21"}}, ("Dimarts", "09:00", "2026-04-28"), "examen_fixat"),
        ({"assignatures_hora_fix": {"Fil (1-BAT)": "11:30"}}, ("Dilluns", "09:00", "2026-04-20"), "examen_fixat"),
        (
            {"assignatures_slot_prohibit": [{"assignatures": ["Fil (1-BAT)"], "dia": "Dilluns", "hora": "09:00"}]},
            ("Dilluns", "09:00", "2026-04-20"),
            "franja_prohibida",
        ),
        ({"slots_valids_per_nivell": INICIS}, ("Dilluns", "11:30", "2026-04-20"), "nivell_sense_inici"),
        ({"slots_valids_per_nivell": INICIS}, ("Dimarts", "11:30", "2026-04-21"), None),
        # Ordre: el pin primer, després la franja prohibida, i l'inici al final
        (
            {
                "assignatures_dia_fix": {"Fil (1-BAT)": "Dimarts"},
                "assignatures_slot_prohibit": [{"assignatures": ["Fil (1-BAT)"]}],
                "slots_valids_per_nivell": INICIS,
            },
            ("Dilluns", "11:30", "2026-04-20"),
            "examen_fixat",
        ),
        (
            {"assignatures_slot_prohibit": [{"assignatures": ["Fil (1-BAT)"]}], "slots_valids_per_nivell": INICIS},
            ("Dilluns", "11:30", "2026-04-20"),
            "franja_prohibida",
        ),
    ],
)
def test_cada_causa_te_el_seu_nom(dures, franja, esperat):
    assert _check(*franja, **dures) == esperat


def test_pin_no_obligatori_no_amaga_les_altres_causes():
    """Un pin al 50% no bloqueja la franja, però a les
    altres franges es continua mirant si són prohibides o si el nivell hi té
    inici. Abans el pin tou ho amagava (donava 50 i l'examen hi podia anar)."""
    dures = {
        "assignatures_dia_fix": {"Fil (1-BAT)": "Dimarts", "_pes_Fil (1-BAT)": 50},
        "slots_valids_per_nivell": INICIS,
    }
    r = _restriccions(**dures)
    # Dilluns 11:30: el nivell no hi té inici → dura, encara que hi hagi el pin tou
    assert causa_dia_hora_fix(SESSIO, "Dilluns", "11:30", r, ["1-BAT"], "2026-04-20") == ("nivell_sense_inici", 100)
    assert percent_dia_hora_fix_violation(SESSIO, "Dilluns", "11:30", r, ["1-BAT"]) == 100
    assert _check("Dilluns", "11:30", "2026-04-20", **dures) == "nivell_sense_inici"
    # Dilluns 9:00: hi ha inici i no és prohibida → només el pin tou (no bloqueja)
    assert causa_dia_hora_fix(SESSIO, "Dilluns", "09:00", r, ["1-BAT"], "2026-04-20") == ("examen_fixat", 50)
    assert _check("Dilluns", "09:00", "2026-04-20", **dures) is None
    # Franja prohibida: també mana sobre el pin tou
    prohibida = [{"assignatures": ["Fil (1-BAT)"], "dia": "Dilluns", "hora": "09:00"}]
    dures_p = {**dures, "assignatures_slot_prohibit": prohibida}
    assert causa_dia_hora_fix(SESSIO, "Dilluns", "09:00", _restriccions(**dures_p), ["1-BAT"], "2026-04-20") == (
        "franja_prohibida",
        100,
    )
    # A la franja fixada, com sempre
    assert causa_dia_hora_fix(SESSIO, "Dimarts", "09:00", r, ["1-BAT"], "2026-04-21") == (None, 0)


def test_la_composicio_dona_el_percentatge_de_la_primera_causa():
    r = _restriccions(slots_valids_per_nivell=INICIS)
    assert percent_dia_hora_fix_violation(SESSIO, "Dilluns", "11:30", r, ["1-BAT"], "2026-04-20") == 100
    assert percent_dia_hora_fix_violation(SESSIO, "Dilluns", "09:00", r, ["1-BAT"], "2026-04-20") == 0


def test_causa_principal_deixa_examen_fixat_per_a_l_ultim():
    assert causa_principal(Counter({"examen_fixat": 7, "nivell_sense_inici": 1})) == "nivell_sense_inici"
    assert causa_principal(Counter({"examen_fixat": 8})) == "examen_fixat"
    assert causa_principal(Counter({"no_mateix_dia": 2, "franja_prohibida": 3})) == "franja_prohibida"
    assert causa_principal(Counter()) is None
