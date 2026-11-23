"""Per què s'atura la cerca: restriccions
incompatibles, límit de temps o límit de nodes. Si s'atura per un límit, el
resultat i el diagnòstic ho diuen en lloc de dir que no hi ha cap hora.
El rellotge és injectable (el del `Pressupost` o `time.monotonic` per l'API)."""

import random
import time
from types import SimpleNamespace

import pytest
from suport_motor import config_inventada as config_inventada
from suport_motor import xml_inventat as xml_inventat
from suport_planificador import DATES, DIES, centre_amb_examens, configura
from test_planificador_limits import client  # noqa: F401

from planificador.compartit.constants import SEGONS_MAXIMS_LIMIT, SEGONS_MAXIMS_PER_DEFECTE
from planificador.compartit.franja import franja
from planificador.compartit.missatges import missatge
from planificador.motor import diagnostic as modul_diagnostic
from planificador.motor.compatibilitat import BACKTRACKING, GREEDY
from planificador.motor.cost_cerca import CostCercaBacktracking
from planificador.motor.diagnostic import Diagnostic
from planificador.motor.estrategies import backtracking as bt
from planificador.motor.estrategies.base import Pressupost
from planificador.motor.model import Item, congela
from planificador.motor.regles import construeix_regles
from planificador.motor.sortida import horari_backtracking
from rate_limit import limiter

# ------------------------------------------------------------ backtracking


class MotorAmbCostZero:
    """El backtracking real (el nou) amb cost 0 a totes les franges: `n`
    exàmens del mateix nivell en `hores` franges d'un dia. `durant_preparacio`
    es crida a cada franja que es prepara (per fer avançar el rellotge)."""

    def __init__(self, monkeypatch, n, hores):
        items = tuple(
            Item(
                f"item_{i}",
                f"Examen {i}",
                (),
                congela(
                    {
                        "item_id": f"item_{i}",
                        "nom": f"Examen {i}",
                        "sessions": [{"nom": f"Examen {i}", "curs": "1-ESO"}],
                    }
                ),
            )
            for i in range(n)
        )
        self.problema = SimpleNamespace(
            franges=tuple(franja(f"Dilluns_{8 + h:02d}:00") for h in range(hores)),
            regles=construeix_regles({}),
            nivells=("1-ESO",),
            dies=("Dilluns",),
            # Exàmens d'una hora (se'n mira la durada)
            graella=tuple(f"{8 + h:02d}:00" for h in range(hores)),
            durades_examen={},
            durades_vigilancia={},
            durada_examen=1,
            durada_titular=1,
        )
        monkeypatch.setattr(bt, "particio", lambda *_: items)
        monkeypatch.setattr(bt, "Disponibilitat", lambda _: None)
        self.motor = bt.Backtracking()
        self.durant_preparacio = lambda: None

        def professors(*_):
            self.durant_preparacio()
            return {}

        self.motor._professors_item_a_franja = professors
        self.ara = [0]

    def genera(self, segons=SEGONS_MAXIMS_PER_DEFECTE, **parametres):
        """(resultat, metadata) com els dona la generació: el missatge de
        l'aturada o del no viable surt de `horari_backtracking`."""
        parametres = {"seeds_count": 1, **parametres}
        resultat = self.motor.cerca(
            self.problema,
            BACKTRACKING,
            CostCercaBacktracking(SimpleNamespace(regles=self.problema.regles, mapa_dies={})),
            parametres,
            Pressupost(segons, lambda: self.ara[0]),
            random.Random(1),
        )
        if resultat.assignacio is None:
            meta = horari_backtracking(resultat, self.problema, None, segons, parametres.get("max_nodes", 100000))[
                "metadata"
            ]
        else:
            meta = {"cost_total": resultat.cost}
            if resultat.motiu_aturada:
                meta["motiu_aturada"] = resultat.motiu_aturada
        return resultat, meta


@pytest.fixture
def backtrack(monkeypatch):
    return lambda n, hores: MotorAmbCostZero(monkeypatch, n, hores)


def test_backtracking_amb_restriccions_incompatibles_diu_la_causa(backtrack):
    resultat, meta = backtrack(n=4, hores=3).genera()  # quatre exàmens del mateix nivell, tres franges
    assert meta["viable"] is False
    assert meta["error"] == missatge("no_viable")
    assert "motiu_aturada" not in meta
    assert [m["codi"] for m in resultat.causes] == ["examen_sense_hora_causa"]


def test_backtracking_aturat_pel_limit_de_nodes_ho_diu(backtrack):
    resultat, meta = backtrack(n=3, hores=3).genera(max_nodes=0)  # hi ha solució, però zero nodes la talla a l'arrel
    assert meta["viable"] is False
    assert meta["motiu_aturada"] == "nodes"
    assert meta["error"] == missatge("cerca_tallada_nodes", nodes=0)
    assert resultat.causes == []  # cap «no té cap hora disponible»


def test_backtracking_aturat_pel_limit_de_nodes_sense_cap_causa_falsa(backtrack):
    # Sense solució i amb pocs nodes: abans deia «conflicte entre restriccions»
    resultat, meta = backtrack(n=4, hores=3).genera(max_nodes=2)
    assert meta["motiu_aturada"] == "nodes"
    assert meta["error"] == missatge("cerca_tallada_nodes", nodes=2)
    assert resultat.causes == []


def test_backtracking_aturat_pel_temps_ho_diu(backtrack):
    motor = backtrack(n=3, hores=3)

    def avanca():
        motor.ara[0] = SEGONS_MAXIMS_PER_DEFECTE + 1

    motor.durant_preparacio = avanca
    resultat, meta = motor.genera()
    assert meta["viable"] is False
    assert meta["motiu_aturada"] == "temps"
    assert meta["error"] == missatge("cerca_tallada_temps", segons=SEGONS_MAXIMS_PER_DEFECTE)
    assert resultat.causes == []


def test_backtracking_fa_servir_el_temps_maxim_triat(backtrack):
    motor = backtrack(n=3, hores=3)

    def avanca():
        motor.ara[0] = 6  # passat el termini de 5 s, però no el de 20 s per defecte

    motor.durant_preparacio = avanca
    _, meta = motor.genera(segons=5)
    assert meta["motiu_aturada"] == "temps"
    assert meta["error"] == missatge("cerca_tallada_temps", segons=5)


def test_backtracking_amb_solucio_no_marca_cap_aturada(backtrack):
    _, meta = backtrack(n=3, hores=3).genera()
    assert meta["cost_total"] == 0
    assert "motiu_aturada" not in meta


# ------------------------------------------------- diverses llavors


def _amb_llavors(motor, monkeypatch, nodes_de_cada_llavor, llavors):
    """Genera amb `llavors` llavors, cadascuna amb el seu límit de nodes (per
    tallar-ne unes i deixar acabar les altres). Retorna (resultat, metadata,
    quantes llavors s'han executat)."""
    fetes = []
    cerca_d_una_llavor = motor.motor._cerca_amb_llavor

    def amb_el_seu_limit(llavor, _max_nodes, *resta):
        fetes.append(llavor)
        return cerca_d_una_llavor(llavor, nodes_de_cada_llavor[len(fetes) - 1], *resta)

    monkeypatch.setattr(motor.motor, "_cerca_amb_llavor", amb_el_seu_limit)
    resultat, meta = motor.genera(seeds_count=llavors)
    return resultat, meta, len(fetes)


def test_despres_d_una_llavor_acabada_no_se_n_executen_mes(backtrack, monkeypatch):
    """Una cerca que acaba sense tall ja ha trobat el cost mínim: les altres
    llavors no el poden millorar (abans es feien totes)."""
    _, meta, fetes = _amb_llavors(backtrack(n=3, hores=3), monkeypatch, [100000] * 5, llavors=5)
    assert fetes == 1
    assert meta["cost_total"] == 0
    assert "motiu_aturada" not in meta


def test_una_llavor_tallada_no_marca_l_horari_d_una_altra_que_ha_acabat(backtrack, monkeypatch):
    """La primera llavor es talla pels nodes sense cap horari; la segona
    acaba. L'horari ve d'una cerca acabada: no porta `motiu_aturada` (abans hi
    quedava «nodes» i la pantalla avisava que la cerca no havia acabat)."""
    _, meta, fetes = _amb_llavors(backtrack(n=3, hores=3), monkeypatch, [3, 100000, 100000], llavors=3)
    assert fetes == 2
    assert meta["cost_total"] == 0
    assert "motiu_aturada" not in meta


def test_una_llavor_acabada_sense_horari_diu_que_no_n_hi_ha_encara_que_una_altra_s_hagi_tallat(backtrack, monkeypatch):
    motor = backtrack(n=4, hores=3)  # quatre exàmens del mateix nivell, tres franges
    resultat, meta, fetes = _amb_llavors(motor, monkeypatch, [2, 100000, 100000], llavors=3)
    assert fetes == 2
    assert meta["viable"] is False
    assert meta["error"] == missatge("no_viable")
    assert "motiu_aturada" not in meta
    assert [m["codi"] for m in resultat.causes] == ["examen_sense_hora_causa"]


def test_si_totes_les_llavors_es_tallen_l_horari_ho_diu(backtrack, monkeypatch):
    _, meta, fetes = _amb_llavors(backtrack(n=4, hores=3), monkeypatch, [2, 2, 2], llavors=3)
    assert fetes == 3
    assert meta["motiu_aturada"] == "nodes"
    assert meta["error"] == missatge("cerca_tallada_nodes", nodes=100000)


# Els cinc tests del bucle d'intents del greedy (termini, almenys un intent,
# sense cap intent complet, temps triat, dins del termini) són els casos de
# `test_planificador_greedy.py::test_limits_millor_i_ultim_intent_sense_temps_real`.


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
    from planificador.motor.estrategies.backtracking import Backtracking

    cerca_original = Backtracking.cerca

    def espia_nou(self, problema, politiques, cost_cerca, parametres, pressupost, rng):
        vistos.append(pressupost.segons)
        return cerca_original(self, problema, politiques, cost_cerca, parametres, pressupost, rng)

    monkeypatch.setattr(Backtracking, "cerca", espia_nou)
    from planificador.motor.estrategies.greedy import Greedy

    cerca_greedy_original = Greedy.cerca

    def espia_greedy(self, problema, politiques, cost_cerca, parametres, pressupost, rng):
        vistos.append(pressupost.segons)
        return cerca_greedy_original(self, problema, politiques, cost_cerca, parametres, pressupost, rng)

    monkeypatch.setattr(Greedy, "cerca", espia_greedy)
    from planificador.motor.estrategies.recuit import Recuit

    cerca_recuit_original = Recuit.cerca

    def espia_recuit(self, problema, politiques, cost_cerca, parametres, pressupost, rng):
        vistos.append(pressupost.segons)
        return cerca_recuit_original(self, problema, politiques, cost_cerca, parametres, pressupost, rng)

    monkeypatch.setattr(Recuit, "cerca", espia_recuit)
    limiter.reset()
    _, client_centre = centre_amb_examens()
    configura(client_centre)
    peticio = {"data_inici": DATES[0], "data_final": DATES[-1], "selected_dates": DATES, "dies_utilitzar": DIES}
    for segons in (None, 7):
        cos = dict(peticio, motor=motor, **({"segons_maxims": segons} if segons else {}))
        assert client_centre.post("/api/scheduler/generate", json=cos).status_code == 200
    assert vistos == [SEGONS_MAXIMS_PER_DEFECTE, 7]


# ------------------------------------------------ explicació no viable


def _diagnostic_amb(monkeypatch, config_inventada, xml_inventat, estructural, pendents):
    from test_planificador_greedy import problema_de

    diagnostic = Diagnostic(problema_de(config_inventada, xml_inventat), GREEDY)
    monkeypatch.setattr(diagnostic, "incompatibilitats", lambda _: [estructural])
    monkeypatch.setattr(modul_diagnostic, "identifica_sessions_no_collocades", lambda *_: pendents)
    pla = SimpleNamespace(cfg=SimpleNamespace(avisos=lambda nivells=None: []), nivells=[])
    return diagnostic, pla


def test_l_aturada_encapcala_el_diagnostic(monkeypatch, config_inventada, xml_inventat):
    tall = missatge("cerca_tallada_nodes", nodes=1000)
    estructural = missatge("examen_sense_hora", nom="A", nivell="N")
    pendents = missatge("nivell_cap_collocat", nivell="N", count=2)
    diagnostic, pla = _diagnostic_amb(monkeypatch, config_inventada, xml_inventat, estructural, [pendents])
    horari = {"dies": [], "metadata": {"viable": False, "error": tall, "motiu_aturada": "nodes"}}
    diagnostic.explica_no_viable(horari, pla, [])
    assert horari["metadata"]["incompatibilitats"] == [tall, estructural, pendents]


def test_sense_aturada_el_diagnostic_no_canvia(monkeypatch, config_inventada, xml_inventat):
    estructural = missatge("examen_sense_hora", nom="A", nivell="N")
    diagnostic, pla = _diagnostic_amb(monkeypatch, config_inventada, xml_inventat, estructural, [])
    horari = {"dies": [], "metadata": {"viable": False, "error": missatge("no_viable")}}
    diagnostic.explica_no_viable(horari, pla, [])
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


# ------------------------------------------------------------ el recuit, v3


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
