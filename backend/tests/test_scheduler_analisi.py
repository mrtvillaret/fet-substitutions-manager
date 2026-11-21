"""
Anàlisi de possibilitats del planificador (POST /api/scheduler/analisi):
per a cada examen i franja, quins professors s'haurien de substituir. Els
informes són text.
"""

import pytest
from suport_planificador import (
    DATES,
    DIES,
    alliberaments,
    centre_amb_examens,
    configura,
)

from rate_limit import limiter

PETICIO = {"data_inici": DATES[0], "data_final": DATES[-1], "selected_dates": DATES, "dies_utilitzar": DIES}


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


@pytest.fixture
def client():
    _, client = centre_amb_examens()
    configura(client)
    return client


def test_l_analisi_dona_els_tres_informes_amb_els_examens_del_nivell(client):
    resp = client.post("/api/scheduler/analisi", json=PETICIO)
    assert resp.status_code == 200, resp.text
    informes = resp.json()
    assert set(informes) == {"per_slots", "per_sessio", "professors_slot", "avisos"}
    assert informes["avisos"] == []  # tots els grups són a un nivell
    sessions = {s["titol"]: s for s in informes["per_sessio"]}
    for examen in ("Anglès (1-BAT)", "Català (1-BAT)", "Filosofia (1-BAT)"):
        assert examen in sessions
    assert "Prof 25" in sessions["Anglès (1-BAT)"]["professors"]  # titular d'Anglès


# ---------------------------------------- examens més llargs que la durada general


def _files_de(informe, examen):
    """Files (una per dia i hora) de la secció d'un examen a l'informe per agrupacions."""
    return [fila for sessio in informe if sessio["titol"] == examen for fila in sessio["files"]]


def _analisi_filosofia(durades_grups=None):
    _, client = centre_amb_examens()
    camps = {"alliberaments_per_nivell": alliberaments(hores_inici=("09:00", "10:00", "11:30"))}
    if durades_grups:
        camps["durades_grups"] = durades_grups
    configura(client, **camps)
    return _files_de(client.post("/api/scheduler/analisi", json=PETICIO).json()["per_sessio"], "Filosofia (1-BAT)")


def test_un_examen_que_dura_mes_que_la_durada_general_s_analitza_sencer():
    # Durada general d'1 hora; Filosofia en dura 2: es miren les dues hores
    una_hora = _analisi_filosofia()
    dues_hores = _analisi_filosofia([{"assignatures": ["Filosofia (1-BAT)"], "durada": 2, "durada_examen": 2}])
    assert una_hora and len(dues_hores) > len(una_hora)
