"""Peticions de la pantalla: desat i relectura, incloses bonificacions."""

import pytest
from test_planificador_limits import client  # noqa: F401

PESOS_PANTALLA = {
    "restriccio_dura": 1000,
    "preferencia_mateix_dia": -500,
    "preferencia_mateix_slot": -2000,
    "preferencia_dies_diferents": 500,
}
COSTOS_PANTALLA = {"substitucio": 80, "abans_jornada": 30, "despres_jornada": 30, "no_treballa_dia": 60}


@pytest.mark.parametrize("preset", ["v3", "v2", "v2-backtrack"])
def test_defaults_i_presets_de_la_pantalla_es_desen_i_es_rellegeixen(client, preset):
    # genConfig incorpora els params etiquetats de GET motors (motors.js).
    motors = client.get("/api/scheduler/motors")
    assert motors.status_code == 200
    motor = next(m for m in motors.json()["motors"] if m["id"] == preset)
    params = {k: v for k, v in motor["params"].items() if k in motor["param_labels"]}
    config = {"durada_titular": 1, "durada_examen": 1, "durades_grups": [], "alliberaments_per_nivell": {}}
    assert client.put("/api/scheduler/config", json=config).status_code == 200
    lectura = client.get("/api/scheduler/config")
    assert lectura.status_code == 200
    for camp, valor in config.items():
        assert lectura.json()[camp] == valor
    restriccions = {"pesos_optimitzacio": PESOS_PANTALLA, "costos_professors": {"globals": COSTOS_PANTALLA}}
    resposta = client.put("/api/scheduler/restriccions", json={"restriccions": restriccions})
    assert resposta.status_code == 200, resposta.text
    lectura = client.get("/api/scheduler/restriccions")
    assert lectura.status_code == 200
    assert lectura.json()["restriccions"]["pesos_optimitzacio"] == PESOS_PANTALLA
    costos = client.get("/api/scheduler/costos-professors")
    assert costos.status_code == 200
    assert costos.json()["costos_professors"]["globals"] == COSTOS_PANTALLA
    # Els paràmetres del motor no tenen endpoint de persistència: s'envien
    # a generar després del desat comú. El motor està substituït al fixture.
    resposta = client.post(
        "/api/scheduler/generate", json={"data_inici": "2026-04-20", "motor": preset, "max_dies": 5, **params}
    )
    assert resposta.status_code == 200, resposta.text


@pytest.mark.parametrize("cost", [-50, 101, 500, 1000])
def test_costos_amb_signe_i_sense_sostre_es_conserven(client, cost):
    cos = {"globals": {"substitucio": cost}, "individuals": {"Prof 1": {"abans_jornada": cost}}}
    resposta = client.put("/api/scheduler/costos-professors", json=cos)
    assert resposta.status_code == 200, resposta.text
    lectura = client.get("/api/scheduler/costos-professors")
    assert lectura.status_code == 200
    assert lectura.json()["costos_professors"]["globals"]["substitucio"] == cost
    assert lectura.json()["costos_professors"]["individuals"] == cos["individuals"]


@pytest.mark.parametrize("pes", [-2000, -1, 101, 10000])
def test_pesos_anteriors_sense_restriccions_noves(client, pes):
    cos = {
        "pesos_optimitzacio": {"lliure": pes},
        "preferencies": {"mateix_dia": [{"assignatures": ["Prova"], "pes": pes}]},
        "pesos_percentatge": {"substitucio": pes},
    }
    resposta = client.put("/api/scheduler/restriccions", json={"restriccions": cos})
    assert resposta.status_code == 200, resposta.text
    lectura = client.get("/api/scheduler/restriccions").json()["restriccions"]
    for camp, valor in cos.items():
        if camp == "preferencies":
            assert lectura[camp]["mateix_dia"] == valor["mateix_dia"]
        else:
            assert lectura[camp][next(iter(valor))] == next(iter(valor.values()))


@pytest.mark.parametrize(
    "params",
    [
        {"max_iteracions": 0},
        {"temperatura_inicial": 0},
        {"temperatura_final": 0},
        {"temperatura_final": 101},
        {"temperatura_inicial": 1, "temperatura_final": 2},
        {"factor_refredament": 0},
        {"factor_refredament": 1},
        {"factor_refredament": 1.1},
        {"seeds_count": 0},
        {"seeds_count": -1},
        {"shuffle_top_n": -1},
        {"max_nodes": 0},
    ],
)
def test_modes_anteriors_finits_i_amb_significat_son_acceptats(client, params):
    resposta = client.post("/api/scheduler/generate", json={"data_inici": "2026-04-20", **params})
    assert resposta.status_code == 200, resposta.text
