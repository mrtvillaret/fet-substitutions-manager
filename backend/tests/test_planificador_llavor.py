"""Amb `random_seed`, el greedy i el recuit fan servir un generador propi d'aquesta llavor
(proves reproduïbles, encara que el generador global canviï); sense, el global, com sempre."""

import random

import pytest
from suport_planificador import DATES, DIES, alliberaments, centre_amb_examens, configura

from rate_limit import limiter

DOS = ("1-BAT", "2-BAT")
PETICIO = {"data_inici": DATES[0], "data_final": DATES[-1], "selected_dates": DATES, "dies_utilitzar": DIES}
PARAMS = {"v2": {}, "v3": {"max_iteracions": 300, "segons_maxims": 60}}


@pytest.fixture
def client():
    limiter.reset()
    _, client = centre_amb_examens(nivells=DOS)
    configura(client, nivells_actius=list(DOS), alliberaments_per_nivell=alliberaments(nivells=DOS))
    return client


def _franges(client, motor, llavor_global, **cos):
    random.seed(llavor_global)
    horari = client.post("/api/scheduler/generate", json={**PETICIO, "motor": motor, **PARAMS[motor], **cos}).json()
    return sorted(
        (sessio["nom"], dia["data"], franja["hora"])
        for dia in horari["horari"]["dies"]
        for franja in dia["sessions"]
        for sessio in franja["sessions_simultanees"]
    )


@pytest.mark.parametrize("motor", ["v2", "v3"])
def test_amb_la_mateixa_llavor_el_mateix_horari(client, motor):
    primer = _franges(client, motor, 1, random_seed=7)
    assert primer
    assert _franges(client, motor, 2, random_seed=7) == primer
    # Sense llavor, el generador global (el de sempre): amb el mateix global, el mateix horari
    assert _franges(client, motor, 3) == _franges(client, motor, 3)
