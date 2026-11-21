"""Força d'una fixació (pin) d'examen a una altra franja: el seu pes; sense pes,
obligatòria (100); amb pes 0, cap efecte."""

import pytest

from planificador.motor.regles import percent_examen_fixat


@pytest.mark.parametrize(("pes", "esperat"), [(None, 100), (100, 100), (50, 50), (0, 0)])
def test_forca_del_pin_fora_de_la_franja_fixada(pes, esperat):
    dures = {"assignatures_hora_fix": {"A": "09:00"}}
    if pes is not None:
        dures["assignatures_hora_fix"]["_pes_A"] = pes
    restriccions = {"restriccions_dures": dures}
    assert percent_examen_fixat({"nom": "A"}, "Dilluns", "10:00", restriccions) == esperat
    assert percent_examen_fixat({"nom": "A"}, "Dilluns", "09:00", restriccions) == 0
