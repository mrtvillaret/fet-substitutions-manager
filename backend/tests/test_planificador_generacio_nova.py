"""Servei de generació: una sola preparació del problema per petició."""

import json
import random
from copy import deepcopy
from datetime import date
from types import SimpleNamespace

import pytest
from suport_motor import config_inventada as config_inventada
from suport_motor import xml_inventat as xml_inventat

from planificador import generacio_nova as nou
from planificador.compartit.dates import construir_mapa_dia_data
from planificador.compartit.preparacio import Preparacio
from planificador.documents import document_iso
from planificador.motor.estrategies import base
from planificador.schemas import SchedulerGenerateRequest

DATA = date(2027, 3, 1)


def _bytes(dades):
    return json.dumps(document_iso(dades), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


@pytest.mark.parametrize("motor", ["v2-backtrack", "v2", "v3", "V3"])
@pytest.mark.parametrize(
    "variant", ["viable", "precheck", "nodes", "temps", "parcial", "sense_sessions", "pin_zero", "combinacio", "durada"]
)
def test_un_sol_problema_per_a_diagnostic_cost_i_projeccio(monkeypatch, config_inventada, xml_inventat, variant, motor):
    cfg = config_inventada
    cfg.config.update(cfg.nivells_dels_grups.a_config())
    cfg.alliberaments = {
        "N1": {
            "dates": [DATA],
            "config": {DATA: {hora: {"i": True, "a": False} for hora in ("09:00", "PATI", "11:00")}},
        }
    }
    cfg.restriccions = {"pesos_optimitzacio": {"restriccio_dura": 1000}}
    if variant == "precheck":
        cfg.alliberaments["N1"]["config"][DATA] = {"09:00": {"i": True, "a": False}}
    elif variant == "parcial":
        cfg.restriccions["costos_professors"] = {"individuals": {"Prof 01": {"substitucio": 10000}}}
    elif variant == "sense_sessions":
        cfg.config["assignatures"] = {}
    elif variant == "pin_zero":
        cfg.restriccions["restriccions_dures"] = {"assignatures_hora_fix": {"A": "11:00", "_pes_A": 0}}
    elif variant == "combinacio":
        cfg.restriccions["restriccions_dures"] = {"combinacions_permeses": [["A", "B"]]}
    elif variant == "durada":
        cfg.durades_per_sessio = {"A (N1)": 2}
        cfg.durades_examen_per_sessio = {"A (N1)": 1}
    captura = []

    def prepara(*args):
        from planificador.config import deriva_restriccions  # noqa: PLC0415

        dades = deepcopy(cfg)
        hores = list(dades.alliberaments["N1"]["config"][DATA])
        mapa = construir_mapa_dia_data(["Dilluns"], [DATA])
        deriva_restriccions(
            dades.restriccions, dades.alliberaments, ["N1"], ["Dilluns"], mapa, ["09:00", "PATI", "11:00"]
        )
        return Preparacio(
            dades, dades.restriccions, xml_inventat, ["Dilluns"], ["N1"], [DATA], mapa, hores, {"N1": hores}
        )

    monkeypatch.setattr(nou, "prepara_planificacio", prepara)
    monkeypatch.setattr(nou, "desa_horari", lambda _, h, dies: captura.append(deepcopy(h)))
    rellotge = SimpleNamespace(monotonic=lambda: 0)
    monkeypatch.setattr(nou, "time", rellotge)
    monkeypatch.setattr(base, "time", rellotge)
    if variant == "temps":

        def rellotge_que_talla():
            crides = [0]

            def ara():
                crides[0] += 1
                return crides[0] * 25

            return SimpleNamespace(monotonic=ara)

        monkeypatch.setattr(base, "time", rellotge_que_talla())
    payload = SchedulerGenerateRequest(
        data_inici=DATA,
        motor=motor.lower(),
        dies_utilitzar=["Dilluns"],
        random_seed=7,
        seeds_count=3,
        shuffle_top_n=3,
        max_nodes=0 if variant == "nodes" else 100000,
    ).model_copy(update={"motor": motor})
    random.seed(7)
    problemes, diagnostics, costos, projeccions = [], [], [], []
    construeix_original = nou.construeix_problema
    diagnostic_original = nou.Diagnostic
    nom_cost = "CostCercaRecuit" if motor.lower() == "v3" else "CostCercaGreedy"
    cost_original = getattr(nou, nom_cost)
    projeccio_original = nou._problema_cost_mostrat

    def construeix(*args, **kwargs):
        problema = construeix_original(*args, **kwargs)
        problemes.append(problema)
        return problema

    def diagnostic(problema, politiques):
        diagnostics.append(problema)
        return diagnostic_original(problema, politiques)

    def cost_greedy(problema, *args):
        costos.append(problema)
        return cost_original(problema, *args)

    def projeccio(problema):
        projeccions.append(problema)
        return projeccio_original(problema)

    monkeypatch.setattr(nou, "construeix_problema", construeix)
    monkeypatch.setattr(nou, "Diagnostic", diagnostic)
    monkeypatch.setattr(nou, nom_cost, cost_greedy)
    monkeypatch.setattr(nou, "_problema_cost_mostrat", projeccio)
    obtingut = nou.genera(payload, "inventat")
    assert len(problemes) == len(diagnostics) == 1
    assert diagnostics[0] is problemes[0]
    assert all(p is problemes[0] for p in costos + projeccions)
    assert len(costos) == (1 if motor.lower() in ("v2", "v3") and variant != "precheck" else 0)
    viable = obtingut["horari"]["metadata"].get("viable", True)
    assert len(captura) == (1 if viable else 0)
    if viable:
        assert _bytes(captura[0]) == _bytes(obtingut["horari"])


@pytest.mark.parametrize("motor", ["v3", "V3"])
def test_el_recuit_prepara_el_context_nou_sense_delegar(monkeypatch, motor):
    class ContextNou(Exception):
        pass

    crides = []

    def prepara(*args):
        crides.append(motor)
        raise ContextNou

    monkeypatch.setattr(nou, "prepara_planificacio", prepara)
    with pytest.raises(ContextNou):
        nou.genera(SimpleNamespace(motor=motor), "inventat")
    assert crides == [motor]


def test_precheck_del_recuit_conserva_la_particio_nova_de_la_base(config_inventada, xml_inventat):
    from test_planificador_recuit import problema_de  # noqa: PLC0415

    from planificador.motor.compatibilitat import RECUIT  # noqa: PLC0415
    from planificador.motor.construccio import particio  # noqa: PLC0415
    from planificador.motor.diagnostic import Diagnostic  # noqa: PLC0415

    # Agrupacions superposades: la partició antiga del recuit i la nova del
    # diagnòstic hi fan ítems diferents.
    config_inventada.restriccions = {
        "restriccions_dures": {
            "mateix_slot": [
                {"nom": "G1", "assignatures": ["B (N1)", "C (N1)"]},
                {"nom": "G2", "assignatures": ["A (N1)", "B (N1)"]},
            ]
        }
    }
    problema = problema_de(config_inventada, xml_inventat)
    assert [e.nom_base for e in particio(problema, RECUIT)[0].examens] == ["A", "B"]
    items = Diagnostic(problema, RECUIT).preparar_particio_nivells()
    assert [s["nom_base"] for s in items[0]["sessions"]] == ["B", "C"]
