"""Greedy: límits, cost, atzar i rellotge exactes, sense temps real."""

import json
import random
from copy import deepcopy
from dataclasses import replace

import pytest
from suport_motor_nou import config_inventada as config_inventada
from suport_motor_nou import xml_inventat as xml_inventat

from planificador.motor.compatibilitat import GREEDY
from planificador.motor.construccio import construeix_problema
from planificador.motor.cost_cerca import CostCercaGreedy
from planificador.motor.estrategies.base import Pressupost
from planificador.motor.estrategies.greedy import Greedy
from planificador.motor.regles import construeix_regles
from planificador.motor.sortida import horari_greedy


class Rellotge:
    def __init__(self, tic=0):
        self.tic, self.consultes = tic, 0

    def __call__(self):
        valor = self.consultes * self.tic
        self.consultes += 1
        return valor


def problema_de(cfg, xml, hores=("09:00", "PATI", "11:00")):
    return construeix_problema(
        cfg,
        xml,
        cfg.nivells_configurats,
        ["Dilluns"],
        ["2027-03-01"],
        {"dilluns": ["2027-03-01"]},
        list(hores),
        GREEDY,
        restriccions_resoltes=cfg.restriccions,
    )


def executa_nou(problema, tic=0, segons=20, **parametres):
    rellotge = Rellotge(tic)
    resultat = Greedy().cerca(
        problema, GREEDY, CostCercaGreedy(problema), parametres, Pressupost(segons, rellotge), random
    )
    return horari_greedy(resultat, segons, parametres.get("track_intents", False)), resultat, rellotge


def bytes_de(dades):
    return json.dumps(dades, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


@pytest.mark.parametrize(
    "complet,durada,segons,maxim,esperats",
    [
        (True, 7, 20, 100, 3),
        (True, 40, 20, 100, 1),
        (False, 7, 20, 100, 3),
        (True, 7, 60, 100, 9),
        (True, 0, 20, 40, 40),
        (False, 0, 20, 5000, 5000),
    ],
)
def test_limits_millor_i_ultim_intent_sense_temps_real(
    monkeypatch, config_inventada, xml_inventat, complet, durada, segons, maxim, esperats
):
    from planificador.motor.estrategies import greedy  # noqa: PLC0415

    problema = problema_de(config_inventada, xml_inventat)
    ara, fetes = [0], []
    monkeypatch.setattr(Greedy, "_intent", lambda *a: {})

    def intent(*args):
        fetes.append(1)
        ara[0] += durada
        return {
            "dies": [],
            "metadata": {"total_sessions": len(problema.examens) if complet else 1, "numero": len(fetes)},
        }

    monkeypatch.setattr(greedy, "horari_intent_greedy", intent)
    monkeypatch.setattr(greedy, "estadistiques_generacio", lambda *_: {})
    # Cada intent millora; els incomplets, encara que siguin més barats, no guanyen.
    monkeypatch.setattr(CostCercaGreedy, "intent", lambda *_: {"cost_total": 6000 - len(fetes)})
    resultat = Greedy().cerca(
        problema,
        GREEDY,
        CostCercaGreedy(problema),
        {"max_intents_validacio": maxim, "track_intents": True},
        Pressupost(segons, lambda: ara[0]),
        random,
    )
    horari = horari_greedy(resultat, segons, True)
    assert len(fetes) == esperats
    assert horari["metadata"]["numero"] == esperats
    assert horari["metadata"]["cost_total"] == 6000 - esperats
    assert len(resultat.traça) == esperats
    assert resultat.complet is complet
    assert resultat.motiu_aturada == ("temps" if durada else None)
    if not complet and durada:
        assert horari["metadata"]["viable"] is False
        assert horari["metadata"]["error"]["codi"] == "cerca_tallada_temps"


def test_cost_zero_no_s_apunta_i_els_empats_no_substitueixen_el_primer(monkeypatch, config_inventada, xml_inventat):
    problema = problema_de(config_inventada, xml_inventat)
    # Sense cap cost: es para al primer intent, però no s'apunta a la traça.
    problema = replace(
        problema,
        durada_examen=1,  # exàmens d'una hora: hi caben a totes les franges
        regles=construeix_regles(
            {
                "costos_professors": {
                    "globals": {
                        "substitucio": 0,
                        "abans_jornada": 0,
                        "despres_jornada": 0,
                        "no_treballa_dia": 0,
                    }
                }
            }
        ),
    )
    horari, resultat, rellotge = executa_nou(problema, max_intents_validacio=40, track_intents=True)
    assert resultat.complet and horari["metadata"]["cost_total"] == 0
    assert resultat.traça == [] and rellotge.consultes == 1
    monkeypatch.setattr(CostCercaGreedy, "intent", lambda *_: {"cost_total": 10})
    random.seed(1)
    primer = executa_nou(problema, max_intents_validacio=1)[0]
    random.seed(1)
    molts = executa_nou(problema, max_intents_validacio=10)[0]
    assert bytes_de(primer) == bytes_de(molts)


def test_la_zona_examen_no_costa_res(monkeypatch, config_inventada, xml_inventat):
    """El greedy col·loca amb el cost de la sessió, sense el +5 per professor
    en zona d'examen (que el cost mostrat no compta)."""
    from planificador.motor import cost_cerca  # noqa: PLC0415

    problema = problema_de(config_inventada, xml_inventat)
    zona = [{"professor": "Prof 01", "hora": h} for h in ("09:00", "09:00", "11:00")]
    monkeypatch.setattr(cost_cerca, "analitza_motor", lambda *_, **__: {"zona_examen": zona})
    comptats = set()
    assert (
        CostCercaGreedy(problema).sessio(problema.examens[0].a_diccionari(), problema.franges[0], [], [], comptats) == 0
    )
    assert comptats == set()


def test_barreja_acumulada_i_seqüencia_exacta_de_crides(monkeypatch, config_inventada, xml_inventat):
    problema = problema_de(config_inventada, xml_inventat)
    original = random.shuffle
    crides = []

    def barreja(valors):
        abans = deepcopy(valors)
        original(valors)
        crides.append((abans, deepcopy(valors)))

    monkeypatch.setattr(random, "shuffle", barreja)
    random.seed(12345)
    executa_nou(problema, max_intents_validacio=4)
    assert len(crides) == 4 * (1 + len(problema.examens))
    for i in range(1, 4):
        assert crides[4 * i][0] == crides[4 * (i - 1)][1]


def test_regressio_nou_sessions_cost_330(monkeypatch, config_inventada):
    from test_scheduler_regression import (  # noqa: PLC0415
        DATES,
        DURADA_TITULAR,
        NIVELL,
        XML_PATH,
        _alliberaments,
        _config_examens,
        _dies_utilitzar,
        _restriccions,
    )

    from planificador.alliberaments import extreure_hores_examen_des_alliberaments  # noqa: PLC0415
    from planificador.compartit.dates import construir_mapa_dia_data_iso  # noqa: PLC0415
    from planificador.compartit.nivells import NivellsDelsGrups  # noqa: PLC0415

    cfg = config_inventada
    cfg.config, cfg.restriccions = _config_examens(), _restriccions()
    cfg.alliberaments = _alliberaments()
    cfg.nivells_dels_grups = NivellsDelsGrups.de_config(cfg.config)
    cfg.durada_titular = DURADA_TITULAR
    cfg.no_substituir = frozenset({"Guàrdia"})
    hores, _ = extreure_hores_examen_des_alliberaments(cfg.alliberaments)
    dies = _dies_utilitzar(DATES)
    mapa = construir_mapa_dia_data_iso(dies, DATES, min(DATES))
    problema = construeix_problema(
        cfg, XML_PATH, [NIVELL], dies, [], mapa, hores, GREEDY, restriccions_resoltes=cfg.restriccions
    )
    random.seed(12345)
    obtingut, _, _ = executa_nou(problema, max_intents_validacio=40, track_intents=True)
    assert obtingut["metadata"]["total_sessions"] == 9
    assert obtingut["metadata"]["cost_total"] == 330


@pytest.mark.parametrize(
    "complets,costos,guanyador",
    [
        ([False, False, False], [10, 30, 40], 3),
        ([True, True, True], [30, 10, 40], 2),
        ([True, False, False], [30, 10, 0], 1),
        ([True, True, True], [10, 10, 10], 1),
    ],
)
def test_tria_del_millor_complet_o_ultim_fallit(
    monkeypatch, config_inventada, xml_inventat, complets, costos, guanyador
):
    from planificador.motor.estrategies import greedy  # noqa: PLC0415

    problema = problema_de(config_inventada, xml_inventat)
    fetes = []
    monkeypatch.setattr(Greedy, "_intent", lambda *a: {})

    def document(*args):
        i = len(fetes)
        fetes.append(i)
        return {"dies": [], "metadata": {"numero": i + 1, "total_sessions": 3 if complets[i] else 1}}

    monkeypatch.setattr(greedy, "horari_intent_greedy", document)
    monkeypatch.setattr(greedy, "estadistiques_generacio", lambda *_: {})
    monkeypatch.setattr(CostCercaGreedy, "intent", lambda *_: {"cost_total": costos[fetes[-1]]})
    horari, resultat, _ = executa_nou(problema, max_intents_validacio=3, track_intents=True)
    assert horari["metadata"]["numero"] == guanyador
    assert len(resultat.traça) == 3
    assert resultat.complet == any(complets)


def test_el_termini_comenca_despres_de_preparar_i_nomes_es_mira_entre_intents(
    monkeypatch, config_inventada, xml_inventat
):
    from planificador.motor.estrategies import greedy  # noqa: PLC0415

    problema = problema_de(config_inventada, xml_inventat)
    ara, consultes, intents = [0], [], []
    particio_original = greedy.particio

    def prepara(*args):
        resultat = particio_original(*args)
        ara[0] = 100  # La preparació queda fora dels 20 segons del greedy.
        return resultat

    def rellotge():
        consultes.append(ara[0])
        return ara[0]

    def intent(*args):
        intents.append(ara[0])
        ara[0] += 7
        return {}

    monkeypatch.setattr(greedy, "particio", prepara)
    monkeypatch.setattr(Greedy, "_intent", intent)
    monkeypatch.setattr(CostCercaGreedy, "intent", lambda *_: {"cost_total": 10})
    resultat = Greedy().cerca(
        problema,
        GREEDY,
        CostCercaGreedy(problema),
        {"max_intents_validacio": 10},
        Pressupost(20, rellotge),
        random,
    )
    assert intents == [100, 107, 114]
    assert consultes == [100, 107, 114, 121]
    assert resultat.motiu_aturada == "temps"
    assert resultat.registre == ["⏱️ Límit de temps (20 s): s'han fet 3 intents dels 10 demanats"]


def test_mateix_moment_tou_sense_punts_amagats(config_inventada, xml_inventat):
    """El greedy col·loca amb el cost de la sessió (el mostrat). Una «mateixa data i hora» tova
    amb la companya en un altre moment ja hi és com a preferència; abans s'hi sumava, a més,
    10000 × % (7500 a 75 %) que no sortia enlloc. Al 100 %, la franja queda descartada."""
    for pes in (75, 100):
        cfg = config_inventada
        cfg.restriccions = {"preferencies": {"mateix_slot": [{"assignatures": ["A (N1)", "B (N1)"], "pes": pes}]}}
        problema = problema_de(cfg, xml_inventat)
        a, b = (e.a_diccionari() for e in problema.examens[:2])
        cerca = CostCercaGreedy(problema)
        franja_b = problema.franges[-1]
        ubicacions = [(b, franja_b.clau)]
        resultat = cerca.item({"sessions": [a]}, problema.franges[0], [], [], {}, ubicacions, set(), GREEDY)
        if pes == 100:
            assert resultat is None
        else:
            sol = cerca.sessio(a, problema.franges[0], [], [], set())
            assert resultat[0] == sol < 7500
