"""Entrades acotades i temps del recuit comprovat dins de les iteracions."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from suport_api import crea_app, nova_institucio

from auth.dependencies import get_current_user
from planificador import generacio
from planificador.router import router
from planificador.schemas import HorariRecalcularRequest, SchedulerGenerateRequest, SchedulerPublicarRequest
from scheduler_engine.defaults import DEFAULT_SA_PARAMS
from scheduler_engine.generators import v3_sa


@pytest.fixture
def client(monkeypatch):
    centre = nova_institucio(amb_xml=True)
    app = crea_app(router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(institucio=centre, es_admin=True)
    # Una entrada acceptada no ha d'executar mai un motor amb paràmetres dolents.
    monkeypatch.setattr(generacio, "genera", lambda *_: {"horari": {"dies": []}})
    return TestClient(app, base_url="https://testserver", raise_server_exceptions=False)


@pytest.mark.parametrize(
    "camps",
    [
        {"max_dies": 0},
        {"epsilon": -0.1},
        {"epsilon": 1.1},
        {"max_intents_validacio": 0},
        {"iteracions_per_temperatura": 0, "factor_refredament": 1},
        {"iteracions_per_temperatura": -1},
        {"temperatura_final": -1},
        {"temperatura_inicial": -1},
        {"factor_refredament": -1},
        {"max_iteracions": -1},
        {"max_nodes": -1},
        {"temperatura_inicial": "Infinity"},
    ],
)
def test_parametres_invalids_son_422_abans_de_cridar_el_motor(client, camps):
    resp = client.post("/api/scheduler/generate", json={"data_inici": "2026-04-20", **camps})
    assert resp.status_code == 422, resp.text


def test_valors_per_defecte_actuals_valids():
    valors = {k: v for k, v in DEFAULT_SA_PARAMS.items() if k != "intents_solucio_inicial"}
    assert SchedulerGenerateRequest(data_inici="2026-04-20", **valors)
    assert SchedulerGenerateRequest(data_inici="2026-04-20")


@pytest.mark.parametrize("durada_inicial, veins_esperats", [(0, 20), (25, 0)])
def test_el_termini_atura_un_reinici_en_curs(monkeypatch, durada_inicial, veins_esperats):
    gen = object.__new__(v3_sa.GeneradorV3SA)
    gen.items_congelats_ids = set()
    gen.items_mobils = [object(), object(), object()]
    gen.iteracions_per_temperatura = 50
    gen.max_iteracions = 100
    gen.temperatura_inicial = 100
    gen.temperatura_final = 0.01
    gen.factor_refredament = 0.9
    ara = [0]
    veins = [0]

    def inicial():
        ara[0] += durada_inicial
        return v3_sa.Solucio(assignacions={}, cost=5)

    def vei(solucio):
        veins[0] += 1
        ara[0] += 1
        return solucio

    monkeypatch.setattr(v3_sa.time, "monotonic", lambda: ara[0])
    monkeypatch.setattr(gen, "_detectar_items_congelats", lambda: None)
    monkeypatch.setattr(gen, "_precalcular_slots_candidats", lambda: None)
    monkeypatch.setattr(gen, "_generar_solucio_inicial", inicial)
    monkeypatch.setattr(gen, "_generar_veí", vei)
    millor = gen.executar_simulated_annealing(verbose=False, reinicis=1)
    assert veins[0] == veins_esperats
    assert millor.cost == 5


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
        assert peticio.model_dump(exclude_unset=True, by_alias=True)["horari"] == horari


@pytest.mark.parametrize(
    "ruta, cos",
    [
        ("config", {"durada_titular": 0}),
        ("config", {"durada_examen": -1}),
        ("config", {"alliberaments_per_nivell": {"1-BAT": {"durada": 0}}}),
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
