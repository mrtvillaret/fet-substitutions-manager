"""Recuit nou: trajectòria, cost incremental, atzar i rellotge virtual."""

import random
from copy import deepcopy

import pytest
from suport_motor_nou import config_inventada as config_inventada
from suport_motor_nou import xml_inventat as xml_inventat
from test_planificador_greedy_nou import Rellotge

from planificador.motor.compatibilitat import RECUIT
from planificador.motor.construccio import construeix_problema, particio
from planificador.motor.cost_cerca import CostCercaRecuit, SolucioRecuit
from planificador.motor.disponibilitat import Disponibilitat
from planificador.motor.estrategies.base import Pressupost
from planificador.motor.estrategies.recuit import Recuit
from planificador.motor.sortida import horari_recuit

PARAMETRES = {
    "temperatura_inicial": 300.0,
    "temperatura_final": 0.1,
    "factor_refredament": 0.8,
    "iteracions_per_temperatura": 5,
    "max_iteracions": 35,
    "intents_solucio_inicial": 12,
}


def problema_de(cfg, xml, hores=("09:00", "PATI", "11:00"), dates=True):
    return construeix_problema(
        cfg,
        xml,
        cfg.nivells_configurats,
        ["Dilluns", "Dimarts"],
        ["2027-03-01", "2027-03-02"] if dates else [],
        {"dilluns": ["2027-03-01"], "dimarts": ["2027-03-02"]},
        list(hores),
        RECUIT,
        restriccions_resoltes=cfg.restriccions,
    )


def executa_nou(problema, tic=0, segons=20, parametres=None, rng=random):
    rellotge = Rellotge(tic)
    motor = Recuit()
    resultat = motor.cerca(
        problema, RECUIT, CostCercaRecuit(problema), parametres or PARAMETRES, Pressupost(segons, rellotge), rng
    )
    return horari_recuit(resultat, problema, Disponibilitat(problema)), resultat, rellotge, motor


class AtzarRegistrat:
    """Registra cada operació i el seu domini, a més de l'estat global final."""

    def __init__(self):
        self.crides = []

    @staticmethod
    def projeccio(valor):
        if isinstance(valor, list) or isinstance(valor, tuple):
            return [AtzarRegistrat.projeccio(v) for v in valor]
        if hasattr(valor, "clau"):
            return valor.clau
        if hasattr(valor, "key"):
            return valor.key
        return valor.id if hasattr(valor, "id") else valor

    def shuffle(self, valors):
        self.crides.append(("barreja", self.projeccio(valors)))
        random.shuffle(valors)

    def choice(self, valors):
        self.crides.append(("tria", self.projeccio(valors)))
        return random.choice(valors)

    def random(self):
        self.crides.append(("probabilitat",))
        return random.random()


def executa(problema, llavor=7, tic=0, segons=20, parametres=None):
    """El recuit amb llavor i rellotge virtual: (horari, resultat, motor)."""
    random.seed(llavor)
    obtingut, resultat, _, motor = executa_nou(problema, tic, segons, parametres, AtzarRegistrat())
    return obtingut, resultat, motor


@pytest.mark.parametrize("mobils", [0, 1, 2, 3, 5, 6])
def test_reinicis_i_limits_per_nombre_de_mobils(monkeypatch, config_inventada, xml_inventat, mobils):
    cfg = config_inventada
    cfg.config["assignatures"] = {str(i): deepcopy(cfg.config["assignatures"]["A"]) for i in range(max(mobils, 1))}
    if not mobils:
        cfg.restriccions = {
            "restriccions_dures": {"assignatures_dia_fix": {"0": "Dilluns"}, "assignatures_hora_fix": {"0": "09:00"}}
        }
    problema = problema_de(cfg, xml_inventat)
    _, resultat, motor = executa(problema)
    assert len(motor.items_mobils) == mobils
    reinicis = [linia for linia in resultat.registre if linia.strip().startswith("Reinici ")]
    assert len(reinicis) == (0 if mobils <= 1 else 1 if mobils == 2 else 12)


def test_delta_conserva_les_altres_franges_desfasades(config_inventada, xml_inventat):
    cfg = config_inventada
    cfg.restriccions = {
        "preferencies": {"dies_diferents": [{"assignatures": ["A (N1)", "B (N1)"], "pes": 50}]},
        "pesos_optimitzacio": {"preferencia_dies_diferents": 100},
    }
    problema = problema_de(cfg, xml_inventat)
    cost = CostCercaRecuit(problema)
    items = particio(problema, RECUIT)
    cost.prepara(items, RECUIT)
    antiga = SolucioRecuit({items[0].id: problema.franges[0], items[1].id: problema.franges[1]})
    antiga.cost, antiga.violacions = cost.total(antiga)
    nova = deepcopy(antiga)
    nova.assignacions[items[0].id] = problema.franges[3]
    afectades = {problema.franges[0].clau, problema.franges[3].clau}
    cost.delta(antiga, nova, afectades)
    sencer, _ = cost.total(deepcopy(nova))
    assert nova.cost_per_franja[problema.franges[1].clau] == antiga.cost_per_franja[problema.franges[1].clau]
    assert nova.cost != sencer
    assert nova.cost - sencer == 50


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
    from planificador.motor.avaluador import cost  # noqa: PLC0415
    from planificador.motor.model import HorariEditable  # noqa: PLC0415

    cfg = config_inventada
    cfg.config, cfg.restriccions, cfg.alliberaments = _config_examens(), _restriccions(), _alliberaments()
    cfg.nivells_dels_grups = NivellsDelsGrups.de_config(cfg.config)
    cfg.durada_titular = DURADA_TITULAR
    cfg.no_substituir = frozenset({"Guàrdia"})
    hores, _ = extreure_hores_examen_des_alliberaments(cfg.alliberaments)
    dies = _dies_utilitzar(DATES)
    mapa = construir_mapa_dia_data_iso(dies, DATES, min(DATES))
    problema = construeix_problema(
        cfg, XML_PATH, [NIVELL], dies, [], mapa, hores, RECUIT, restriccions_resoltes=cfg.restriccions
    )
    parametres = dict(
        PARAMETRES,
        temperatura_final=0.1,
        factor_refredament=0.95,
        iteracions_per_temperatura=25,
        max_iteracions=2500,
        intents_solucio_inicial=5,
    )
    horari, _, _ = executa(problema, llavor=12345, parametres=parametres)
    assert horari["metadata"]["total_sessions"] == 9
    assert cost(HorariEditable(horari), problema).total == 330


@pytest.mark.parametrize("durada_inicial,veins", [(0, 3), (3, 0)])
def test_solucio_inicial_dins_del_temps_sense_interrupcio(
    monkeypatch, config_inventada, xml_inventat, durada_inicial, veins
):
    problema = problema_de(config_inventada, xml_inventat)
    ara, consultes, moviments = [100], [], []
    original = Recuit._detecta_congelats

    def prepara(motor):
        original(motor)
        ara[0] += 100  # Preparació fora del termini.

    def rellotge():
        consultes.append(ara[0])
        return ara[0]

    def inicial(motor):
        ara[0] += durada_inicial
        return SolucioRecuit({}, cost=5)

    def vei(motor, solucio):
        moviments.append(1)
        ara[0] += 1
        return solucio

    monkeypatch.setattr(Recuit, "_detecta_congelats", prepara)
    monkeypatch.setattr(Recuit, "_solucio_inicial", inicial)
    monkeypatch.setattr(Recuit, "_vei", vei)
    resultat = Recuit().cerca(
        problema, RECUIT, CostCercaRecuit(problema), dict(PARAMETRES, reinicis=2), Pressupost(3, rellotge), random
    )
    assert consultes[0] == 200
    assert len(moviments) == veins
    assert resultat.cost == 5
    assert resultat.motiu_aturada == "temps"


@pytest.mark.parametrize("mobils,per_temperatura,sostre", [(2, 30, 8000), (5, 80, 30000), (6, 500, 300000)])
def test_sostres_d_iteracions_i_temperatura(
    monkeypatch, config_inventada, xml_inventat, mobils, per_temperatura, sostre
):
    problema = problema_de(config_inventada, xml_inventat)
    motor = Recuit()
    moviments = []

    def detecta(motor):
        motor.items_mobils = [problema.examens[0]] * mobils
        motor.items_congelats_ids = set()

    monkeypatch.setattr(Recuit, "_detecta_congelats", detecta)
    monkeypatch.setattr(Recuit, "_precalcula_candidates", lambda *_: None)
    monkeypatch.setattr(Recuit, "_solucio_inicial", lambda *_: SolucioRecuit({}, cost=100001))
    monkeypatch.setattr(Recuit, "_vei", lambda _, sol: moviments.append(1) or sol)
    parametres = dict(
        temperatura_inicial=300,
        temperatura_final=0.01,
        factor_refredament=0.999,
        max_iteracions=300000,
        iteracions_per_temperatura=500,
        reinicis=1,
    )
    resultat = motor.cerca(problema, RECUIT, CostCercaRecuit(problema), parametres, Pressupost(20, lambda: 0), random)
    # El límit només es comprova entre blocs de temperatura: es pot sobrepassar.
    esperats = ((sostre + per_temperatura - 1) // per_temperatura) * per_temperatura
    assert len(moviments) == esperats
    assert any(f": {esperats} iteracions" in linia for linia in resultat.registre)


def test_aturada_sense_solucio_perd_el_motiu(monkeypatch, config_inventada, xml_inventat):
    problema = problema_de(config_inventada, xml_inventat)
    monkeypatch.setattr(Recuit, "_solucio_inicial", lambda *_: None)
    horari, resultat, rellotge, _ = executa_nou(problema, tic=30)
    assert resultat.assignacio is None and resultat.motiu_aturada is None
    assert "motiu_aturada" not in horari["metadata"]
    assert rellotge.consultes == 2
    assert horari["metadata"]["error"]["codi"] == "sense_hora_compatible"


@pytest.mark.parametrize("pes,esperat", [(75, 7500), (100, 10000000)])
def test_mateix_moment_es_cost_global_i_no_dura(config_inventada, xml_inventat, pes, esperat):
    cfg = config_inventada
    cfg.restriccions = {"preferencies": {"mateix_slot": [{"assignatures": [" a ", "b"], "pes": pes}]}}
    problema = problema_de(cfg, xml_inventat)
    cost = CostCercaRecuit(problema)
    items = particio(problema, RECUIT)
    cost.prepara(items, RECUIT)
    solucio = SolucioRecuit({items[0].id: problema.franges[0], items[1].id: problema.franges[3]})
    assert cost.global_mateix_moment(solucio)[0] == esperat
    assert cost.compatible(SolucioRecuit({items[0].id: problema.franges[0]}), items[1], problema.franges[3])


def test_deu_solucions_inicials_viables_i_cinquanta_intents_fallits(monkeypatch, config_inventada, xml_inventat):
    problema = problema_de(config_inventada, xml_inventat)
    _, _, _, motor = executa_nou(problema)
    costos = []
    monkeypatch.setattr(motor, "calcular_cost", lambda *_: costos.append(100 - len(costos)) or (costos[-1], []))
    motor.intents_solucio_inicial = 50
    solucio = motor._solucio_inicial()
    assert len(costos) == 10 and solucio.cost == 91
    crides = []

    def compatible(solucio, item, franja):
        crides.append(1)
        # El recompte estàtic inicial accepta; el primer ítem també, el segon falla.
        return not solucio.assignacions

    monkeypatch.setattr(motor, "_compatible", compatible)
    assert motor._solucio_inicial() is None
    assert len(crides) == len(problema.franges) * (len(motor.items) + 50 * 2)


def test_limit_per_sessio_i_dia_no_es_el_limit_global(config_inventada, xml_inventat):
    cfg = config_inventada
    cfg.restriccions = {
        "restriccions_dures": {
            "professors_limit_dies_especifics": {
                "Prof 01": {
                    "dies_restringits": ["Dilluns"],
                    "max_examens": 1,
                    "pes_penalitzacio": 50,
                    "assignatures": ["A", "B", "C"],
                }
            }
        },
        "costos_professors": {
            "globals": {"substitucio": 0, "abans_jornada": 0, "despres_jornada": 0, "no_treballa_dia": 0}
        },
        "pesos_optimitzacio": {"restriccio_dura": 1000},
    }
    problema = problema_de(cfg, xml_inventat)
    cost = CostCercaRecuit(problema)
    items = particio(problema, RECUIT)
    cost.prepara(items, RECUIT)
    solucio = SolucioRecuit({it.id: problema.franges[i] for i, it in enumerate(items)})
    # 3 sessions × 2 exàmens de més × 50% de 1000; no pas un sol límit global.
    assert cost.total(solucio)[0] == 3000


def test_homonims_i_identificadors_publics(monkeypatch, config_inventada, xml_inventat):
    from planificador.compartit.nivells import NivellsDelsGrups  # noqa: PLC0415

    cfg = config_inventada
    cfg.nivells_configurats = ["N1", "N2"]
    cfg.nivells_dels_grups = NivellsDelsGrups({"N1": ["N1-A"], "N2": ["N2-A"]})
    for dades in cfg.config["assignatures"].values():
        dades["assignacions"].append({"grup": "N2-A", "titular": "Prof 02", "aula": ""})
    cfg.restriccions = {"restriccions_dures": {"mateix_slot": [{"nom": "Paquet", "assignatures": ["A", "B"]}]}}
    horari, resultat, _ = executa(problema_de(cfg, xml_inventat))
    assert len(resultat.items) == 4
    assert len(resultat.assignacio) == 3
    assert resultat.complet is False
    assert horari["metadata"]["total_sessions"] == 4  # se'n perden dues (com feia el motor antic).
    sessions = [s for d in horari["dies"] for f in d["sessions"] for s in f["sessions_simultanees"]]
    assert all(s["item_id"].startswith("item_") for s in sessions)
    assert {s["item_label"] for s in sessions if s["nom_base"] in ("A", "B")} == {"Paquet"}


def test_aturada_per_estancament_amb_temperatura_baixa(monkeypatch, config_inventada, xml_inventat):
    problema = problema_de(config_inventada, xml_inventat)
    moviments = []
    monkeypatch.setattr(Recuit, "_solucio_inicial", lambda *_: SolucioRecuit({}, cost=5))
    monkeypatch.setattr(Recuit, "_vei", lambda _, sol: moviments.append(1) or sol)
    parametres = dict(
        PARAMETRES,
        temperatura_inicial=300,
        temperatura_final=0.01,
        factor_refredament=0.9,
        iteracions_per_temperatura=500,
        max_iteracions=30000,
        reinicis=1,
    )
    _, resultat, _, _ = executa_nou(problema, parametres=parametres)
    assert 2000 < len(moviments) < 30000
    assert any("Early stopping:" in linia for linia in resultat.registre)


def test_rellotge_conserva_la_resta_abans_de_comparar():
    # A aquesta magnitud, inici + 1 arrodoneix a inici; restar primer dona 0.
    pressupost = Pressupost(1, lambda: 1e16)
    pressupost.inicia()
    assert pressupost.temps_transcorregut_esgotat() is False
