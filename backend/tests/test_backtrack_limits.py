"""Els límits del servidor i el termini compartit de totes les llavors."""

import random
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from test_planificador_aturada import MotorAmbCostZero
from test_planificador_limits import client  # noqa: F401

from planificador.motor.estrategies import backtracking as bt


@pytest.mark.parametrize("params", [{"seeds_count": 51}, {"max_nodes": 10_000_001}])
def test_limits_backtrack_rebutjats_abans_del_motor(client, params):
    resposta = client.post(
        "/api/scheduler/generate", json={"data_inici": "2026-04-20", "motor": "v2-backtrack", **params}
    )
    assert resposta.status_code == 422, resposta.text


@pytest.mark.parametrize(
    "params",
    # 0 i negatius ja eren vàlids: el motor els tracta com una sola llavor.
    [
        {"seeds_count": -1},
        {"seeds_count": 0},
        {"seeds_count": 1},
        {"seeds_count": 50},
        {"max_nodes": 0},
        {"max_nodes": 10_000_000},
    ],
)
def test_extrems_backtrack_acceptats(client, params):
    resposta = client.post(
        "/api/scheduler/generate", json={"data_inici": "2026-04-20", "motor": "v2-backtrack", **params}
    )
    assert resposta.status_code == 200, resposta.text


def test_les_llavors_son_per_demanda_i_comparteixen_el_termini(monkeypatch):
    motor = MotorAmbCostZero(monkeypatch, n=1, hores=2)
    rng = Mock()
    rng.randrange.return_value = 123
    monkeypatch.setattr(random, "Random", lambda *_: rng)
    calculs = []

    def cerca(*args):
        calculs.append(args)
        motor.ara[0] += 25
        return [(7, {})]

    monkeypatch.setattr(motor.motor, "_cerca_amb_llavor", cerca)
    resultat, meta = motor.genera(seeds_count=50)
    assert len(calculs) == 1
    assert rng.randrange.call_count == 1
    assert meta["cost_total"] == 7


@pytest.mark.parametrize("fase", ["preparacio", "cerca"])
def test_el_termini_talla_la_preparacio_i_la_cerca_d_una_llavor(monkeypatch, fase):
    motor = MotorAmbCostZero(monkeypatch, n=1, hores=2)
    analisis = []

    def analitza():
        analisis.append(1)
        if fase == "preparacio":
            motor.ara[0] = 25

    motor.durant_preparacio = analitza
    comprovacions = [0]
    if fase == "cerca":

        def comprova(*args):
            comprovacions[0] += 1
            # Al motor nou la comprovació de la preparació és dins de
            # `_professors_item_a_franja` (aquí substituït): la primera és la
            # primera branca de la cerca.
            if comprovacions[0] == 1:
                motor.ara[0] = 25

        monkeypatch.setattr(bt, "_Dures", lambda *_: SimpleNamespace(comprova=comprova))
    _, meta = motor.genera()
    assert len(analisis) == (1 if fase == "preparacio" else 2)
    if fase == "cerca":
        assert comprovacions[0] == 1
    assert meta["viable"] is False
