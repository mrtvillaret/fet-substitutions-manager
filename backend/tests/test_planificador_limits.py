"""Entrades acotades de la petició i del contracte de la pantalla."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from suport_api import crea_app, nova_institucio

from auth.dependencies import get_current_user
from planificador import generacio_nova
from planificador.compartit.constants import DEFAULT_SA_PARAMS
from planificador.router import router
from planificador.schemas import HorariRecalcularRequest, SchedulerGenerateRequest, SchedulerPublicarRequest


@pytest.fixture
def client(monkeypatch):
    centre = nova_institucio(amb_xml=True)
    app = crea_app(router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(institucio=centre, es_admin=True)
    # Una entrada acceptada no ha d'executar mai un motor amb paràmetres dolents.
    monkeypatch.setattr(generacio_nova, "genera", lambda *_: {"horari": {"dies": []}})
    return TestClient(app, base_url="https://testserver", raise_server_exceptions=False)


@pytest.mark.parametrize(
    "camps",
    [
        {"max_intents_validacio": 0},
        {"iteracions_per_temperatura": 0, "factor_refredament": 1},
        {"iteracions_per_temperatura": -1},
        {"temperatura_final": -1},
        {"temperatura_inicial": -1},
        {"factor_refredament": -1},
        {"max_iteracions": -1},
        {"max_nodes": -1},
        {"temperatura_inicial": "Infinity"},
        {"motor": "no_existeix"},
    ],
)
def test_parametres_invalids_son_422_abans_de_cridar_el_motor(client, camps):
    resp = client.post("/api/scheduler/generate", json={"data_inici": "2026-04-20", **camps})
    assert resp.status_code == 422, resp.text


@pytest.mark.parametrize("camps", [{"epsilon": 0.2}, {"epsilon": -0.1}, {"estrategia": "epsilon_greedy"}])
def test_peticio_antiga_amb_epsilon_no_falla(client, camps):
    """`epsilon` (i l'estratègia «Epsilon Greedy») no feien res i s'han tret:
    una petició antiga que els envia s'accepta igual."""
    resp = client.post("/api/scheduler/generate", json={"data_inici": "2026-04-20", "motor": "v2", **camps})
    assert resp.status_code == 200, resp.text


def test_els_motors_ja_no_ofereixen_epsilon(client):
    v2 = next(m for m in client.get("/api/scheduler/motors").json()["motors"] if m["id"] == "v2")
    assert "epsilon" not in v2["params"] and "epsilon" not in v2["param_labels"]
    assert [o["value"] for o in v2["param_labels"]["estrategia"]["options"]] == ["ponderada", "greedy"]


def test_valors_per_defecte_actuals_valids():
    valors = {k: v for k, v in DEFAULT_SA_PARAMS.items() if k != "intents_solucio_inicial"}
    assert SchedulerGenerateRequest(data_inici="2026-04-20", **valors)
    assert SchedulerGenerateRequest(data_inici="2026-04-20")


# El termini que atura un reinici en curs del recuit (amb la solució inicial
# dins o fora del temps): test_planificador_recuit.py::
# test_solucio_inicial_dins_del_temps_sense_interrupcio.


@pytest.mark.parametrize("ruta", ["recalcular-cost", "publicar"])
@pytest.mark.parametrize(
    "horari",
    [
        {"dies": "x"},
        {"dies": [None]},
        {"dies": [{"dia": "Dilluns", "sessions": "x"}]},
        {"dies": [{"dia": "Dilluns", "sessions": [{"hora": "09:00", "sessions_simultanees": "x"}]}]},
        {"dies": [{"dia": "Dilluns", "sessions": [{"hora": "09:00", "sessions_simultanees": [{"examens": "x"}]}]}]},
        {
            "dies": [
                {
                    "dia": "Dilluns",
                    "sessions": [{"hora": "09:00", "sessions_simultanees": [{"examens": [{"professor": []}]}]}],
                }
            ]
        },
    ],
)
def test_estructura_de_dia_franja_sessio_i_examen_validada(client, ruta, horari):
    resposta = client.post(f"/api/scheduler/{ruta}", json={"horari": horari, "setmanes": []})
    assert resposta.status_code == 422, resposta.text


def test_el_contracte_de_la_pantalla_conserva_identificadors_i_analisi():
    horari = {
        "dies": [
            {
                "dia": "Dilluns",
                "data": "2026-04-20",
                "sessions": [
                    {
                        "hora": "09:00",
                        "sessions_simultanees": [
                            {
                                "id": "a",
                                "nom": "Examen",
                                "curs": "1-BAT",
                                "_uid": "uid",
                                "item_id": None,
                                "analisi": {"avisos": []},
                                "examens": [
                                    {"professor": "Prof 1", "grup": "G1", "assignatura": "Examen", "aula": "A1"}
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
        "metadata": {"cost_total": 0},
    }
    for model in (HorariRecalcularRequest, SchedulerPublicarRequest):
        peticio = model(horari=horari, setmanes=[])
        assert peticio.model_dump(mode="json", exclude_unset=True, by_alias=True)["horari"] == horari


@pytest.mark.parametrize(
    "ruta, cos",
    [
        ("config", {"durada_titular": 0}),
        ("config", {"durada_examen": -1}),
        ("config", {"durades_grups": [{"durada": 0}]}),
        ("config", {"durades_grups": [{"durada_examen": -1}]}),
    ],
)
def test_durades_i_pesos_fora_de_rang_son_422(client, ruta, cos):
    resposta = client.put(f"/api/scheduler/{ruta}", json=cos)
    assert resposta.status_code == 422, resposta.text


def test_tots_els_defaults_publicats_dels_motors_son_valids(client):
    resposta = client.get("/api/scheduler/motors")
    assert resposta.status_code == 200
    for motor in resposta.json()["motors"]:
        SchedulerGenerateRequest(data_inici="2026-04-20", motor=motor["id"], **motor["params"])


def test_dates_invertides_son_422(client):
    resposta = client.post("/api/scheduler/generate", json={"data_inici": "2026-04-20", "data_final": "2026-04-19"})
    assert resposta.status_code == 422


def test_els_motors_que_accepta_la_peticio_son_els_del_registre():
    from typing import get_args

    from planificador.motor.cataleg import MOTORS
    from planificador.schemas import SchedulerGenerateRequest

    assert set(get_args(SchedulerGenerateRequest.model_fields["motor"].annotation)) == set(MOTORS)
