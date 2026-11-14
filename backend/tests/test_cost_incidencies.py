"""Cada punt del cost total és en una incidència.

La pantalla mostra el cost total i les incidències amb «(cost: N)». Abans les
restriccions toves (preferències, mateixa franja, no el mateix dia, dies
exclosos...) costaven punts però la seva línia no deia quant (o no sortia), i
el «no treballa aquest dia» no tenia línia. Ara el validador escriu les
mateixes incidències que suma el cost final (estadistiques.incidencies_restriccions
i el cost de cada professor): la suma dels punts del registre és el cost total,
i el desglossament (quantitat × pes = punts) també hi quadra.
"""

import copy
import random
import re

import pytest
from suport_planificador import DATES, DIES, alliberaments, centre_amb_examens, configura

from rate_limit import limiter
from scheduler_engine.core.punts import CONCEPTES
from scheduler_engine.core.scoring import calcular_cost_slot

PETICIO = {"data_inici": DATES[0], "data_final": DATES[-1], "selected_dates": DATES, "dies_utilitzar": DIES}
DOS = ("1-BAT", "2-BAT")


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


def _punts(logs):
    return sum(int(m.group(1)) for linia in logs if (m := re.search(r"\(punt: *(-?\d+)\)$", linia)))


@pytest.fixture
def amb_restriccions():
    _, client = centre_amb_examens(nivells=DOS)
    configura(client, nivells_actius=list(DOS), alliberaments_per_nivell=alliberaments(nivells=DOS))
    restr = client.get("/api/scheduler/restriccions").json()["restriccions"]
    dures = restr.setdefault("restriccions_dures", {})
    dures["professors_limit_dies_especifics"] = {
        "Prof 48": {
            "assignatures": ["Filosofia (1-BAT)", "Filosofia (2-BAT)"],
            "dies_restringits": ["Dilluns"],
            "max_examens": 0,
            "pes_penalitzacio": 60,
        }
    }
    dures["no_mateix_slot"] = {"G": ["Anglès (1-BAT)", "Anglès (2-BAT)"], "_pes_G": 30}
    dures["no_mateix_dia"] = [["Català (1-BAT)", "Anglès (1-BAT)"]]
    restr["preferencies"] = {
        "dies_diferents": [{"assignatures": ["Català (2-BAT)", "Filosofia (2-BAT)"], "pes": 50}],
        "mateix_dia": [{"assignatures": ["Català (1-BAT)", "Filosofia (1-BAT)"], "pes": 40}],
        # Tres exàmens en dues franges del mateix dia: almenys un queda separat
        "mateix_slot": [{"assignatures": ["Català (1-BAT)", "Català (2-BAT)", "Anglès (2-BAT)"], "pes": 10}],
    }
    restr["pesos_optimitzacio"] = {
        "restriccio_dura": 1000,
        "preferencia_dies_diferents": 500,
        "preferencia_mateix_dia": -300,
    }
    assert client.put("/api/scheduler/restriccions", json={"restriccions": restr}).status_code == 200
    assert (
        client.put(
            "/api/scheduler/costos-professors",
            json={"globals": {"substitucio": 70, "abans_jornada": 40, "despres_jornada": 30, "no_treballa_dia": 90}},
        ).status_code
        == 200
    )
    return client


def _variants(horari):
    yield "original", horari
    # Tot a la primera franja: conflictes, mateix moment i mateix dia segurs
    h = copy.deepcopy(horari)
    franges = [slot for dia in h["dies"] for slot in dia["sessions"]]
    totes = [s for slot in franges for s in slot["sessions_simultanees"]]
    for slot in franges:
        slot["sessions_simultanees"] = []
    franges[0]["sessions_simultanees"] = totes
    yield "amuntegada", h
    # Tot el primer dia, repartit entre les franges
    h = copy.deepcopy(horari)
    sessions = [s for dia in h["dies"] for slot in dia["sessions"] for s in slot["sessions_simultanees"]]
    for dia in h["dies"]:
        for slot in dia["sessions"]:
            slot["sessions_simultanees"] = []
    franges_dia = [{"hora": hora, "sessions_simultanees": []} for hora in ("09:00", "11:30")]
    h["dies"][0]["sessions"] = franges_dia
    for i, sessio in enumerate(sessions):
        franges_dia[i % 2]["sessions_simultanees"].append(sessio)
    yield "un_dia", h


@pytest.mark.parametrize("motor", ["v3", "v2-backtrack"])
def test_la_suma_de_les_incidencies_es_el_cost_total(amb_restriccions, motor):
    resp = amb_restriccions.post("/api/scheduler/generate", json=dict(PETICIO, motor=motor))
    assert resp.status_code == 200, resp.text
    horari = resp.json()["horari"]
    conceptes_vistos = set()
    for nom, h in _variants(horari):
        r = amb_restriccions.post(
            "/api/scheduler/recalcular-cost",
            json={"horari": h, "data_referencia": DATES[0], "selected_dates": DATES},
        ).json()
        assert _punts(r["logs"]) == r["cost_total"], nom
        desglossament = r["cost_desglossament"]
        assert sum(fila["punts"] for fila in desglossament) == r["cost_total"], nom
        for fila in desglossament:
            assert fila["quantitat"] * fila["pes"] == fila["punts"] != 0
            assert fila["concepte"] in CONCEPTES
            conceptes_vistos.add(fila["concepte"])
        # L'últim horari desat porta el mateix desglossament (la pantalla el torna a obrir)
        desat = amb_restriccions.get("/api/scheduler/ultim-resultat").json()["resultat"]["horari"]["metadata"]
        assert desat["cost_desglossament"] == desglossament
    # Les variants passen per totes les restriccions toves de l'escenari
    assert {
        "limit_dies_professor",
        "no_mateix_slot",
        "no_mateix_dia",
        "preferencia_dies_diferents",
        "preferencia_mateix_dia",
        "preferencia_mateix_slot",
    } <= conceptes_vistos


def _recalculat(client, horari):
    return client.post(
        "/api/scheduler/recalcular-cost", json={"horari": horari, "data_referencia": DATES[0], "selected_dates": DATES}
    ).json()["cost_total"]


@pytest.fixture
def amb_durades():
    """Dos nivells, Filosofia de dues hores i cinc hores d'inici."""
    _, client = centre_amb_examens(nivells=DOS)
    hores = ("08:00", "09:00", "10:00", "11:30", "12:30")
    configura(
        client,
        nivells_actius=list(DOS),
        alliberaments_per_nivell=alliberaments(nivells=DOS, hores_inici=hores),
        durades_grups=[{"assignatures": ["Filosofia (1-BAT)", "Filosofia (2-BAT)"], "durada": 2, "durada_examen": 2}],
    )
    return client


@pytest.mark.parametrize("escenari", ["amb_restriccions", "amb_durades"])
@pytest.mark.parametrize("motor", ["v2", "v3", "v2-backtrack"])
def test_el_cost_de_la_resposta_de_generar_es_el_del_recalcul(request, escenari, motor):
    """La pantalla recalcula el cost tot seguit de generar; si el recàlcul
    fallés, mostraria el de la resposta: han de ser el mateix. Abans el recuit
    i el backtracking hi posaven el seu cost intern (1140 i 1110 punts on el
    recàlcul en deia 140 i 350)."""
    client = request.getfixturevalue(escenari)
    random.seed(1)
    resposta = client.post("/api/scheduler/generate", json=dict(PETICIO, motor=motor, random_seed=1))
    horari = resposta.json()["horari"]
    assert horari["metadata"].get("viable", True)
    assert horari["metadata"]["cost_total"] == _recalculat(client, horari)


@pytest.mark.parametrize("escenari", ["amb_restriccions", "amb_durades"])
def test_el_cost_que_porta_la_cerca_del_backtracking_es_el_validat(request, monkeypatch, escenari):
    """El cost que la cerca minimitza (sumat pas a pas) és el mateix número
    que el cost validat de l'horari que retorna."""
    from scheduler_engine.generators import v2_backtrack as bt

    client = request.getfixturevalue(escenari)
    de_la_cerca = []
    desa = bt.GeneradorV2Backtrack._desa_solucio
    monkeypatch.setattr(
        bt.GeneradorV2Backtrack,
        "_desa_solucio",
        lambda gen, cerca, cost: de_la_cerca.append(cost) or desa(gen, cerca, cost),
    )
    peticio = dict(PETICIO, motor="v2-backtrack", random_seed=1)
    horari = client.post("/api/scheduler/generate", json=peticio).json()["horari"]
    assert de_la_cerca[-1] == horari["metadata"]["cost_total"] == _recalculat(client, horari)


def test_el_backtracking_sense_tall_no_dona_un_horari_mes_car_que_el_greedy(amb_restriccions):
    """La cerca exhaustiva minimitza el cost que es mostra. Abans en sumava un
    de propi (sense les preferències de dia ni el «no el mateix dia» no
    obligatori, i amb el límit per professor acumulat) i en aquest escenari
    acabava sense tall amb un horari de 350 punts; el greedy en troba un de 140."""
    random.seed(1)
    greedy = amb_restriccions.post("/api/scheduler/generate", json=dict(PETICIO, motor="v2")).json()["horari"]
    for llavor in (1, 2, 3):
        limiter.reset()
        peticio = dict(PETICIO, motor="v2-backtrack", random_seed=llavor)
        horari = amb_restriccions.post("/api/scheduler/generate", json=peticio).json()["horari"]
        assert "motiu_aturada" not in horari["metadata"]
        cost = _recalculat(amb_restriccions, horari)
        assert cost == 140
        assert cost <= _recalculat(amb_restriccions, greedy)


def test_cada_restriccio_tova_te_la_seva_linia_amb_punts(amb_restriccions):
    horari = amb_restriccions.post("/api/scheduler/generate", json=dict(PETICIO, motor="v2-backtrack")).json()["horari"]
    _, amuntegada, un_dia = (h for _, h in _variants(horari))
    logs = []
    for h in (amuntegada, un_dia):
        logs += amb_restriccions.post(
            "/api/scheduler/recalcular-cost",
            json={"horari": h, "data_referencia": DATES[0], "selected_dates": DATES},
        ).json()["logs"]
    for marca in (
        "NO AL MATEIX MOMENT",
        "DIES DISTINTS",
        "DIES DIFERENTS",
        "MATEIX DIA",
        "MATEIXA FRANJA",
        "LÍMIT DIES",
    ):
        linies = [linia for linia in logs if marca in linia]
        assert linies, marca
        # Visibles a la pantalla (porten «→») i amb els punts
        assert all("→" in linia and re.search(r"\(punt: -?\d+\)$", linia) for linia in linies), linies


def test_la_preferencia_mateix_dia_amb_pes_negatiu_va_amb_signe(amb_restriccions):
    # pes base -300: el cost hi suma +120 (40 %) per cada companya el mateix dia
    horari = amb_restriccions.post("/api/scheduler/generate", json=dict(PETICIO, motor="v2-backtrack")).json()["horari"]
    _, amuntegada, _ = (h for _, h in _variants(horari))
    logs = amb_restriccions.post(
        "/api/scheduler/recalcular-cost",
        json={"horari": amuntegada, "data_referencia": DATES[0], "selected_dates": DATES},
    ).json()["logs"]
    assert [linia for linia in logs if "MATEIX DIA" in linia and linia.endswith("(punt: 120)")]


def test_el_professor_que_no_treballa_aquell_dia_te_linia_amb_punts():
    # Sense cap classe a l'XML el dia de l'examen: «no treballa aquest dia»
    from scheduler_engine.validacio import ValidadorHorari

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
                                "nom": "Física (1-BAT)",
                                "curs": "1-BAT",
                                "examens": [{"titular": "Prof 1"}],
                                "analisi": {"no_treballa_dia": [{"professor": "Prof 1", "hora": "09:00"}]},
                            }
                        ],
                    }
                ],
            }
        ]
    }
    restr = {"costos_professors": {"globals": {"no_treballa_dia": 90}}}
    logs = ValidadorHorari(horari, restr, set()).validar()["logs"]
    assert "🚫 Prof 1 (Física (1-BAT))->1-BAT → no treballa aquest dia a les 09:00 el Dilluns 20/04 (punt: 90)" in logs


@pytest.mark.parametrize("pes_base", [500, -500])
def test_les_incidencies_d_una_franja_sumen_el_seu_cost(pes_base):
    def s(nom, curs="1-BAT", prof="Prof 1"):
        return {"nom": f"{nom} ({curs})", "nom_base": nom, "curs": curs, "examens": [{"titular": prof}]}

    a, b, c = s("Física"), s("Química", prof="Prof 2"), s("Física", "2-BAT", "Prof 3")
    restr = {
        "restriccions_dures": {
            "no_mateix_slot": {"G": ["Física (1-BAT)", "Química (1-BAT)"], "_pes_G": 100},
            "no_mateix_dia": [{"assignatures": ["Física (1-BAT)", "Física (2-BAT)"], "pes": 70}],
            "combinacions_permeses": [["Física", "Biologia"]],
            "assignatures_dies_exclosos": [{"assignatures": ["Física (1-BAT)"], "dies": ["Dilluns"], "pes": 30}],
        },
        "preferencies": {
            "dies_diferents": [{"assignatures": ["Física (1-BAT)", "Física (2-BAT)"], "pes": 60}],
            "mateix_dia": [{"assignatures": ["Física (1-BAT)", "Química (1-BAT)"], "pes": 50}],
        },
        "pesos_optimitzacio": {"preferencia_dies_diferents": pes_base, "preferencia_mateix_dia": pes_base},
    }
    analisi = {
        "substitucions": [{"professor": "Prof 1", "hora": "09:00"}],
        "abans_jornada": [],
        "despres_jornada": [],
        "no_treballa_dia": [],
    }
    incidencies = []
    cost = calcular_cost_slot(
        a, "Dilluns", "09:00", analisi, restr, sessions_dia=[a, b, c], sessions_slot=[a, b], incidencies=incidencies
    )
    assert sum(inc.punts for inc in incidencies) == cost["cost_total"]
    assert {inc.concepte for inc in incidencies} == {
        "substitucio",
        "no_mateix_slot",
        "no_mateix_dia",
        "combinacio_no_permesa",
        "assignatures_dies_exclosos",
        "preferencia_dies_diferents",
        "preferencia_mateix_dia",
    }
