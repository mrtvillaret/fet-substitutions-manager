"""Força bruta, fites i trajectòria del motor nou, amb rellotge virtual.

Els escenaris (inventats), l'enumeració exhaustiva i els ajudants de la cerca
són a `test_backtrack_cost_final.py`.
"""

import json
import os
import random
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from suport_motor_nou import config_inventada as config_inventada
from suport_motor_nou import problema_inventat
from suport_motor_nou import xml_inventat as xml_inventat
from test_backtrack_cost_final import (
    cerca_nou,
    escenari_a_l_atzar,
    prepara_nou,
    problema_escenari,
)

from planificador.compartit.franja import franja
from planificador.motor.compatibilitat import BACKTRACKING
from planificador.motor.cost_cerca import CostCercaBacktracking
from planificador.motor.estrategies import backtracking as bt
from planificador.motor.estrategies.base import Pressupost
from planificador.motor.model import congela
from planificador.motor.regles import construeix_regles


@pytest.mark.parametrize("llavor", range(1, 25))
def test_forca_bruta_cost_final_fites_i_poda(monkeypatch, config_inventada, xml_inventat, llavor):
    escenari = escenari_a_l_atzar(llavor)
    problema = problema_escenari(problema_inventat(config_inventada, xml_inventat), escenari)
    prepara_nou(monkeypatch, escenari)
    minim = escenari.minim_per_forca_bruta()
    resultat, amb, _ = cerca_nou(problema, llavor)
    sense_resultat, sense, _ = cerca_nou(problema, llavor, poda=False)
    assert resultat.complet and resultat.motiu_aturada is None
    assert resultat.cost == sense_resultat.cost == minim
    assert amb.cerques[0].nodes <= sense.cerques[0].nodes
    assert len(sense.fulles) > 100
    for cost, ubicacions, fites, _ in sense.fulles:
        assert cost == escenari.cost(ubicacions)
        assert max(fites) <= cost
    assert cerca_nou(problema, llavor, shuffle_top_n=3)[0].cost == minim


@pytest.mark.parametrize("variant", ["dura", "violada", "professor", "preferencia"])
def test_les_tres_causes_de_no_podar_i_la_preferencia_negativa(monkeypatch, config_inventada, xml_inventat, variant):
    escenari = escenari_a_l_atzar(3)
    if variant == "professor":
        escenari.restriccions["costos_professors"] = {"individuals": {"Prof 1": {"substitucio": -1}}}
    else:
        clau = {
            "dura": "restriccio_dura",
            "violada": "restriccio_dura_violada",
            "preferencia": "preferencia_mateix_dia",
        }[variant]
        escenari.restriccions["pesos_optimitzacio"][clau] = -1000
    problema = problema_escenari(problema_inventat(config_inventada, xml_inventat), escenari)
    prepara_nou(monkeypatch, escenari)
    resultat, motor, _ = cerca_nou(problema)
    assert resultat.cost == escenari.minim_per_forca_bruta()
    assert motor.cerques[0].poda == (variant == "preferencia")
    if variant != "preferencia":
        assert motor.cerques[0].nodes == cerca_nou(problema, poda=False)[1].cerques[0].nodes


def test_els_escenaris_encara_fan_baixar_el_cost(monkeypatch, config_inventada, xml_inventat):
    baixades = 0
    for llavor in range(1, 25):
        escenari = escenari_a_l_atzar(llavor)
        problema = problema_escenari(problema_inventat(config_inventada, xml_inventat), escenari)
        prepara_nou(monkeypatch, escenari)
        _, motor, _ = cerca_nou(problema, poda=False)
        baixades += any(max(costos) > cost for cost, _, _, costos in motor.fulles)
    assert baixades >= 10


@pytest.mark.parametrize("nombre", [-1, 0, 1, 4])
def test_preparacio_unica_i_llavor_acabada_tanca_la_cerca(monkeypatch, config_inventada, xml_inventat, nombre):
    escenari = escenari_a_l_atzar(3)
    problema = problema_escenari(problema_inventat(config_inventada, xml_inventat), escenari)
    prepara_nou(monkeypatch, escenari)
    preparacions = []
    original = CostCercaBacktracking.prepara

    def apunta(self, *args):
        preparacions.append(args)
        return original(self, *args)

    monkeypatch.setattr(CostCercaBacktracking, "prepara", apunta)
    resultat, motor, _ = cerca_nou(problema, seeds_count=nombre)
    assert resultat.complet and resultat.motiu_aturada is None
    assert len(motor.cerques) == len(preparacions) == 1
    preparacions.clear()
    _, motor, _ = cerca_nou(problema, seeds_count=nombre, max_nodes=2)
    assert len(motor.cerques) == max(1, nombre)
    assert len(preparacions) == 1


def horari_amb_empats(llavor, barreja):
    """Sense XML ni temps real: quatre ítems i divuit franges empatades."""
    from types import SimpleNamespace  # noqa: PLC0415

    from planificador.motor.model import Item  # noqa: PLC0415
    from planificador.motor.regles import construeix_regles  # noqa: PLC0415

    items = tuple(
        Item(
            f"item_{i}",
            f"Examen {i}",
            (),
            congela(
                {
                    "item_id": f"item_{i}",
                    "nom": f"Examen {i}",
                    "sessions": [{"nom": f"Examen {i}", "curs": "N1"}],
                }
            ),
        )
        for i in range(4)
    )
    problema = SimpleNamespace(
        franges=tuple(
            franja(f"{d}_{h}")
            for d in ("Dilluns", "Dimarts", "Dimecres")
            for h in ("08:00", "09:00", "10:00", "11:30", "12:30", "13:30")
        ),
        regles=construeix_regles({}),
        nivells=("N1",),
        dies=("Dilluns", "Dimarts", "Dimecres"),
        # Exàmens d'una hora (se'n mira la durada)
        graella=("08:00", "09:00", "10:00", "11:30", "12:30", "13:30"),
        durades_examen={},
        durades_vigilancia={},
        durada_examen=1,
        durada_titular=1,
    )
    motor = bt.Backtracking()
    motor._professors_item_a_franja = lambda *_: {}
    # Només s'injecten les dades i l'anàlisi alienes a l'ordre de la cerca.
    original_particio, original_disponibilitat = bt.particio, bt.Disponibilitat
    bt.particio, bt.Disponibilitat = lambda *_: items, lambda _: None
    try:
        resultat = motor.cerca(
            problema,
            BACKTRACKING,
            CostCercaBacktracking(SimpleNamespace(regles=problema.regles, mapa_dies={})),
            {"shuffle_top_n": barreja},
            Pressupost(20, lambda: 0),
            random.Random(llavor),
        )
        return sorted((k, f.clau) for k, f in resultat.assignacio.items())
    finally:
        bt.particio, bt.Disponibilitat = original_particio, original_disponibilitat


@pytest.mark.parametrize("barreja", [0, 5])
def test_determinisme_entre_hashseeds_i_diversitat_de_llavors(barreja):
    arrel = Path(__file__).resolve().parents[1]
    codi = (
        "import json, sys\n"
        f"sys.path.insert(0, {str(arrel / 'tests')!r})\n"
        "from test_planificador_backtracking_nou import horari_amb_empats\n"
        f"print(json.dumps(horari_amb_empats(7, {barreja})))"
    )
    sortides = []
    for hashseed in (0, 1, 2):
        resultat = subprocess.run(
            [sys.executable, "-c", codi],
            cwd=arrel,
            capture_output=True,
            text=True,
            check=True,
            env=dict(os.environ, PYTHONHASHSEED=str(hashseed)),
        )
        sortides.append(resultat.stdout)
    assert sortides[0] == sortides[1] == sortides[2]
    assert len({json.dumps(horari_amb_empats(llavor, barreja)) for llavor in range(1, 6)}) > 1


@pytest.mark.parametrize(
    "prefix,esperat", [("2026-04-20", None), ("2026-4-20", "examen_fixat"), ("Dilluns", "examen_fixat")]
)
def test_comprovador_dur_conserva_el_filtre_iso(config_inventada, xml_inventat, prefix, esperat):
    """Només un prefix ISO amb zeros és una data per al comprovador dur (valors
    fixats amb el comprovador antic abans de retirar-lo)."""
    problema = problema_inventat(config_inventada, xml_inventat)
    regles = construeix_regles({"restriccions_dures": {"assignatures_dia_fix": {"A": "2026-04-20"}}})
    problema = replace(problema, regles=regles)
    sessio = problema.examens[0].a_diccionari()
    ubicacio = franja(f"{prefix}_09:00")
    nova = bt._Dures(problema, BACKTRACKING).comprova(sessio, ubicacio.dia, ubicacio.hora, prefix, [], [], {})
    assert (nova.clau if nova else None) == esperat
