"""Els límits del servidor i el termini compartit de totes les llavors."""

import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from test_planificador_limits import client  # noqa: F401

from scheduler_engine.generators import v2_backtrack as bt


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
    gen = object.__new__(bt.GeneradorV2Backtrack)
    ara = [0]
    rng = Mock()
    rng.randrange.return_value = 123
    monkeypatch.setattr(bt.random, "Random", lambda *_: rng)
    monkeypatch.setattr(time, "monotonic", lambda: ara[0])
    calculs = []

    def cerca(*args):
        calculs.append(args)
        ara[0] += 25
        return [(7, {})]

    monkeypatch.setattr(gen, "_backtrack_with_seed", cerca)
    monkeypatch.setattr(gen, "_construir_horari_desde_slots", lambda *_: {"metadata": {}, "dies": []})
    resultat = gen.generar_totes_solucions_optimes(random_seed=1, seeds_count=50, dies_utilitzar=["Dilluns"])
    assert len(calculs) == 1
    assert rng.randrange.call_count == 1
    assert resultat[0]["metadata"]["cost_total"] == 7


@pytest.mark.parametrize("fase", ["preparacio", "cerca"])
def test_el_termini_talla_la_preparacio_i_la_cerca_d_una_llavor(monkeypatch, fase):
    gen = object.__new__(bt.GeneradorV2Backtrack)
    gen.restriccions = {}
    gen.nivells_actius = ["1-ESO"]
    gen.hores_examen = ["09:00", "10:00"]
    ara, analisis = [0], []
    monkeypatch.setattr(time, "monotonic", lambda: ara[0])
    item = {"nom": "Examen", "sessions": [{"nom": "Examen", "curs": "1-ESO"}]}
    monkeypatch.setattr(gen, "preparar_particio_nivells", lambda **_: [item])
    monkeypatch.setattr(gen, "get_durada_per_sessio_key", lambda *_: 1)
    monkeypatch.setattr(gen, "_get_hores_ocupades", lambda hora, *_: [hora])
    monkeypatch.setattr(bt, "calcular_cost_slot", lambda **_: {"cost_total": 0})
    monkeypatch.setattr(gen, "_calcular_penalitzacio_professors_dies", lambda *_: 0)
    monkeypatch.setattr(gen, "_construir_horari_desde_slots", lambda *_: {"metadata": {}, "dies": []})

    def analitza(*args, **kwargs):
        analisis.append(args)
        if fase == "preparacio":
            ara[0] = 25
        return {}

    monkeypatch.setattr(gen, "analitzar_disponibilitat_sessio", analitza)
    comprovacions = [0]
    if fase == "cerca":

        def comprova(*args):
            comprovacions[0] += 1
            if comprovacions[0] == 3:  # dues franges preparades; primera branca de cerca
                ara[0] = 25

        monkeypatch.setattr(bt, "RestrictionEngine", lambda *_: SimpleNamespace(check_hard=comprova))
    resultat = gen.generar_totes_solucions_optimes(random_seed=1, seeds_count=1, dies_utilitzar=["Dilluns"])
    assert len(analisis) == (1 if fase == "preparacio" else 2)
    if fase == "cerca":
        assert comprovacions[0] == 3
    assert resultat[0]["metadata"]["viable"] is False
