"""Per què s'atura la cerca: restriccions
incompatibles, límit de temps o límit de nodes. Si s'atura per un límit, el
resultat i el diagnòstic ho diuen en lloc de dir que no hi ha cap hora.
El rellotge és injectable (`time.monotonic`), com als altres tests de límits."""

import time

import pytest
from suport_planificador import DATES, DIES, centre_amb_examens, configura
from test_planificador_limits import client  # noqa: F401

from planificador import generacio
from rate_limit import limiter
from scheduler_engine.core.missatges import missatge
from scheduler_engine.defaults import SEGONS_MAXIMS_LIMIT, SEGONS_MAXIMS_PER_DEFECTE
from scheduler_engine.generators import v2_backtrack as bt
from scheduler_engine.generators import v2_intents

# ------------------------------------------------------------ backtracking


@pytest.fixture
def backtrack(monkeypatch):
    """El motor real amb cost 0 a totes les franges: `n` exàmens del mateix
    nivell en `hores` franges d'un dia."""

    def crea(n, hores):
        gen = object.__new__(bt.GeneradorV2Backtrack)
        gen.restriccions = {}
        gen.nivells_actius = ["1-ESO"]
        gen.hores_examen = [f"{8 + h:02d}:00" for h in range(hores)]
        items = [{"nom": f"Examen {i}", "sessions": [{"nom": f"Examen {i}", "curs": "1-ESO"}]} for i in range(n)]
        monkeypatch.setattr(gen, "preparar_particio_nivells", lambda **_: items)
        monkeypatch.setattr(gen, "get_durada_per_sessio_key", lambda *_: 1)
        monkeypatch.setattr(gen, "_get_hores_ocupades", lambda hora, *_: [hora])
        monkeypatch.setattr(gen, "analitzar_disponibilitat_sessio", lambda *_, **__: {})
        monkeypatch.setattr(gen, "_calcular_penalitzacio_professors_dies", lambda *_: 0)
        monkeypatch.setattr(gen, "_construir_horari_desde_slots", lambda *_: {"metadata": {}, "dies": [{}]})
        monkeypatch.setattr(bt, "calcular_cost_slot", lambda **_: {"cost_total": 0})
        return gen

    return crea


def _genera_bt(gen, **params):
    return gen.generar_totes_solucions_optimes(random_seed=1, seeds_count=1, dies_utilitzar=["Dilluns"], **params)[0]


def test_backtracking_amb_restriccions_incompatibles_diu_la_causa(backtrack):
    gen = backtrack(n=4, hores=3)  # quatre exàmens del mateix nivell, tres franges
    meta = _genera_bt(gen)["metadata"]
    assert meta["viable"] is False
    assert meta["error"] == missatge("no_viable")
    assert "motiu_aturada" not in meta
    assert [m["codi"] for m in gen._incompatibilitats_bt] == ["examen_sense_hora_causa"]


def test_backtracking_aturat_pel_limit_de_nodes_ho_diu(backtrack):
    gen = backtrack(n=3, hores=3)  # hi ha solució, però zero nodes la talla a l'arrel
    meta = _genera_bt(gen, max_nodes=0)["metadata"]
    assert meta["viable"] is False
    assert meta["motiu_aturada"] == "nodes"
    assert meta["error"] == missatge("cerca_tallada_nodes", nodes=0)
    assert gen._incompatibilitats_bt == []  # cap «no té cap hora disponible»


def test_backtracking_aturat_pel_limit_de_nodes_sense_cap_causa_falsa(backtrack):
    # Sense solució i amb pocs nodes: abans deia «conflicte entre restriccions»
    gen = backtrack(n=4, hores=3)
    meta = _genera_bt(gen, max_nodes=2)["metadata"]
    assert meta["motiu_aturada"] == "nodes"
    assert meta["error"] == missatge("cerca_tallada_nodes", nodes=2)
    assert gen._incompatibilitats_bt == []


def test_backtracking_aturat_pel_temps_ho_diu(backtrack, monkeypatch):
    gen = backtrack(n=3, hores=3)
    ara = [0]
    monkeypatch.setattr(time, "monotonic", lambda: ara[0])

    def analitza(*_, **__):
        ara[0] = SEGONS_MAXIMS_PER_DEFECTE + 1
        return {}

    monkeypatch.setattr(gen, "analitzar_disponibilitat_sessio", analitza)
    meta = _genera_bt(gen)["metadata"]
    assert meta["viable"] is False
    assert meta["motiu_aturada"] == "temps"
    assert meta["error"] == missatge("cerca_tallada_temps", segons=SEGONS_MAXIMS_PER_DEFECTE)
    assert gen._incompatibilitats_bt == []


def test_backtracking_fa_servir_el_temps_maxim_triat(backtrack, monkeypatch):
    gen = backtrack(n=3, hores=3)
    gen.segons_maxims = 5
    ara = [0]
    monkeypatch.setattr(time, "monotonic", lambda: ara[0])

    def analitza(*_, **__):
        ara[0] = 6  # passat el termini de 5 s, però no el de 20 s per defecte
        return {}

    monkeypatch.setattr(gen, "analitzar_disponibilitat_sessio", analitza)
    meta = _genera_bt(gen)["metadata"]
    assert meta["motiu_aturada"] == "temps"
    assert meta["error"] == missatge("cerca_tallada_temps", segons=5)


def test_backtracking_amb_solucio_no_marca_cap_aturada(backtrack):
    meta = _genera_bt(backtrack(n=3, hores=3))["metadata"]
    assert meta["cost_total"] == 0
    assert "motiu_aturada" not in meta


# ------------------------------------------------------------ greedy (v2)


@pytest.fixture
def greedy(monkeypatch):
    """El bucle d'intents del motor v2 amb cada intent substituït: `durada`
    segons per intent i `complet` diu si l'intent col·loca tots els exàmens."""

    def crea(durada, complet=True):
        gen = object.__new__(v2_intents.GeneradorV2Intents)
        gen.hores_examen = ["09:00"]
        ara, intents = [0], []
        monkeypatch.setattr(time, "monotonic", lambda: ara[0])
        monkeypatch.setattr(gen, "_pre_normalitzar_horaris", lambda: {})
        monkeypatch.setattr(gen, "preparar_particio_nivells", lambda **_: [])
        monkeypatch.setattr(gen, "get_total_sessions_count", lambda: 2)
        monkeypatch.setattr(gen, "build_context", lambda *_: None)
        monkeypatch.setattr(v2_intents, "aplicar_estadistiques", lambda *_: None)
        monkeypatch.setattr(v2_intents, "recalcular_cost_i_breakdown", lambda *_: {"cost_total": 100 - len(intents)})

        def intent(*_):
            intents.append(1)
            ara[0] += durada
            return {"dies": [], "metadata": {"total_sessions": 2 if complet else 1}}

        monkeypatch.setattr(gen, "_generar_un_intent_horari", intent)
        return gen, intents

    return crea


def _genera_v2(gen, intents=100):
    return gen.generar_horari_optimitzat(dies_utilitzar=["Dilluns"], max_intents_validacio=intents)


def test_greedy_s_atura_al_termini_i_es_queda_el_millor_intent(greedy):
    gen, intents = greedy(durada=7)
    meta = _genera_v2(gen)["metadata"]
    # 0 → 7 → 14 → 21 s: el quart intent ja no comença
    assert len(intents) == 3
    assert meta["motiu_aturada"] == "temps"
    assert meta["cost_total"] == 97  # el millor dels tres (99, 98, 97)
    assert meta.get("viable", True) is True


def test_greedy_sempre_fa_almenys_un_intent(greedy):
    gen, intents = greedy(durada=SEGONS_MAXIMS_PER_DEFECTE * 2)
    _genera_v2(gen)
    assert len(intents) == 1


def test_greedy_sense_cap_intent_complet_abans_del_termini_ho_diu(greedy):
    gen, _ = greedy(durada=7, complet=False)
    meta = _genera_v2(gen)["metadata"]
    assert meta["viable"] is False
    assert meta["motiu_aturada"] == "temps"
    assert meta["error"] == missatge("cerca_tallada_temps", segons=SEGONS_MAXIMS_PER_DEFECTE)


def test_greedy_fa_servir_el_temps_maxim_triat(greedy):
    gen, intents = greedy(durada=7)
    gen.segons_maxims = 60
    meta = _genera_v2(gen)["metadata"]
    # 0 → 7 → … → 63 s: nou intents
    assert len(intents) == 9
    assert meta["motiu_aturada"] == "temps"


def test_greedy_dins_del_termini_fa_tots_els_intents(greedy):
    gen, intents = greedy(durada=0)
    meta = _genera_v2(gen, intents=40)["metadata"]
    assert len(intents) == 40
    assert "motiu_aturada" not in meta


# --------------------------------------------- límit d'intents a l'API


@pytest.mark.parametrize("intents, estat", [(5000, 200), (5001, 422)])
def test_max_intents_validacio_te_sostre(client, intents, estat):
    resposta = client.post(
        "/api/scheduler/generate",
        json={"data_inici": "2026-04-20", "motor": "v2", "max_intents_validacio": intents},
    )
    assert resposta.status_code == estat, resposta.text


@pytest.mark.parametrize(
    "segons, estat", [(1, 200), (SEGONS_MAXIMS_LIMIT, 200), (0, 422), (SEGONS_MAXIMS_LIMIT + 1, 422)]
)
def test_el_temps_maxim_te_sostre(client, segons, estat):
    resposta = client.post(
        "/api/scheduler/generate",
        json={"data_inici": "2026-04-20", "motor": "v2", "max_intents_validacio": 10, "segons_maxims": segons},
    )
    assert resposta.status_code == estat, resposta.text


@pytest.mark.parametrize("motor", ["v3", "v2", "v2-backtrack"])
def test_la_peticio_passa_el_temps_maxim_al_motor(monkeypatch, motor):
    # El que arriba al motor és el que demana la pantalla (per defecte, 20 s)
    vistos = []
    original = generacio._executa_motor

    def espia(gen, *args, **kwargs):
        vistos.append(gen.segons_maxims)
        return original(gen, *args, **kwargs)

    monkeypatch.setattr(generacio, "_executa_motor", espia)
    limiter.reset()
    _, client_centre = centre_amb_examens()
    configura(client_centre)
    peticio = {"data_inici": DATES[0], "data_final": DATES[-1], "selected_dates": DATES, "dies_utilitzar": DIES}
    for segons in (None, 7):
        cos = dict(peticio, motor=motor, **({"segons_maxims": segons} if segons else {}))
        assert client_centre.post("/api/scheduler/generate", json=cos).status_code == 200
    assert vistos == [SEGONS_MAXIMS_PER_DEFECTE, 7]


# ------------------------------------------------ explicació no viable


def test_l_aturada_encapcala_el_diagnostic(monkeypatch):
    tall = missatge("cerca_tallada_nodes", nodes=1000)
    estructural = missatge("examen_sense_hora", nom="A", nivell="N")
    pendents = missatge("nivell_cap_collocat", nivell="N", count=2)
    monkeypatch.setattr(generacio, "_diagnosticar_incompatibilitats", lambda **_: [estructural])
    monkeypatch.setattr(generacio, "_identificar_sessions_no_collocades", lambda *_: [pendents])
    horari = {"dies": [], "metadata": {"viable": False, "error": tall, "motiu_aturada": "nodes"}}
    gen = type("Gen", (), {"_incompatibilitats_bt": []})()
    pla = type("Pla", (), {"restriccions": {}, "dies": [], "dia_a_data_iso": {}, "nivells": [], "cfg": None})()
    pla.cfg = type("Cfg", (), {"alliberaments": {}, "avisos": lambda self, nivells=None: []})()
    generacio._explica_no_viable(horari, gen, pla)
    assert horari["metadata"]["incompatibilitats"] == [tall, estructural, pendents]


def test_sense_aturada_el_diagnostic_no_canvia(monkeypatch):
    estructural = missatge("examen_sense_hora", nom="A", nivell="N")
    monkeypatch.setattr(generacio, "_diagnosticar_incompatibilitats", lambda **_: [estructural])
    monkeypatch.setattr(generacio, "_identificar_sessions_no_collocades", lambda *_: [])
    horari = {"dies": [], "metadata": {"viable": False, "error": missatge("no_viable")}}
    gen = type("Gen", (), {"_incompatibilitats_bt": []})()
    pla = type("Pla", (), {"restriccions": {}, "dies": [], "dia_a_data_iso": {}, "nivells": []})()
    pla.cfg = type("Cfg", (), {"alliberaments": {}, "avisos": lambda self, nivells=None: []})()
    generacio._explica_no_viable(horari, gen, pla)
    assert horari["metadata"]["incompatibilitats"] == [estructural]


# ------------------------------------------------------------ per l'API


def test_per_l_api_el_limit_de_nodes_es_diu_al_resultat_i_al_diagnostic():
    limiter.reset()
    _, client_centre = centre_amb_examens()
    configura(client_centre)
    peticio = {"data_inici": DATES[0], "data_final": DATES[-1], "selected_dates": DATES, "dies_utilitzar": DIES}
    resposta = client_centre.post("/api/scheduler/generate", json=dict(peticio, motor="v2-backtrack", max_nodes=0))
    assert resposta.status_code == 200, resposta.text
    meta = resposta.json()["horari"]["metadata"]
    tall = missatge("cerca_tallada_nodes", nodes=0)
    assert meta["viable"] is False
    assert meta["motiu_aturada"] == "nodes"
    assert meta["error"] == tall
    assert meta["incompatibilitats"][0] == tall
    assert all(m.get("params", {}).get("causa") != "conflicte_restriccions" for m in meta["incompatibilitats"])


# ------------------------------------------------------------ recuit (v3)


def test_el_recuit_aturat_pel_temps_ho_diu_i_es_queda_la_millor_solucio(monkeypatch):
    # Rellotge que avança un segon a cada consulta: el recuit s'atura pel temps
    limiter.reset()
    _, client_centre = centre_amb_examens()
    configura(client_centre)
    peticio = {"data_inici": DATES[0], "data_final": DATES[-1], "selected_dates": DATES, "dies_utilitzar": DIES}
    ara = [0]

    def rellotge():
        ara[0] += 1
        return ara[0]

    monkeypatch.setattr(time, "monotonic", rellotge)
    meta = client_centre.post("/api/scheduler/generate", json=dict(peticio, motor="v3", segons_maxims=3)).json()[
        "horari"
    ]["metadata"]
    assert meta.get("viable", True) is True
    assert meta["motiu_aturada"] == "temps"


def test_el_recuit_dins_del_temps_no_marca_cap_aturada():
    limiter.reset()
    _, client_centre = centre_amb_examens()
    configura(client_centre)
    peticio = {"data_inici": DATES[0], "data_final": DATES[-1], "selected_dates": DATES, "dies_utilitzar": DIES}
    meta = client_centre.post("/api/scheduler/generate", json=dict(peticio, motor="v3")).json()["horari"]["metadata"]
    assert "motiu_aturada" not in meta
