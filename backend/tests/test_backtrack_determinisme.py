"""La mateixa llavor dona el mateix horari del backtracking, sigui quin
sigui `PYTHONHASHSEED`: els empats de cost es resolen a l'atzar amb el rng de
la llavor, no per l'ordre d'un `set`.

Cada execució es fa en un subprocés, perquè `PYTHONHASHSEED` només es pot
triar en arrencar l'intèrpret. El motor és el real; només se'n substitueixen
el cost i l'anàlisi de cada franja (tot val 0: tot són empats)."""

import json
import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
HORES = ["08:00", "09:00", "10:00", "11:30", "12:30", "13:30"]
DIES = ["Dilluns", "Dimarts", "Dimecres"]


def horari_amb_empats(random_seed: int, shuffle_top_n: int = 0) -> list:
    """Quatre exàmens del mateix nivell, cost 0 a les 18 franges: retorna on
    ha anat cadascun (franja → exàmens)."""
    from scheduler_engine.generators import v2_backtrack as bt

    gen = object.__new__(bt.GeneradorV2Backtrack)
    gen.restriccions = {}
    gen.nivells_actius = ["1-ESO"]
    gen.hores_examen = list(HORES)
    items = [{"nom": f"Examen {n}", "sessions": [{"nom": f"Examen {n}", "curs": "1-ESO"}]} for n in "ABCD"]
    gen.preparar_particio_nivells = lambda **_: items
    gen.get_durada_per_sessio_key = lambda *_: 1
    gen._get_hores_ocupades = lambda hora, *_: [hora]
    gen.analitzar_disponibilitat_sessio = lambda *_, **__: {}
    gen._calcular_penalitzacio_professors_dies = lambda *_: 0

    def construeix(slots_occ, *_):
        franges = sorted((sk, sorted(it["label"] for it in its)) for sk, its in slots_occ.items())
        return {"metadata": {}, "dies": franges}

    gen._construir_horari_desde_slots = construeix
    cost_real = bt.calcular_cost_slot
    bt.calcular_cost_slot = lambda **_: {"cost_total": 0}
    try:
        resultat = gen.generar_totes_solucions_optimes(
            random_seed=random_seed, seeds_count=1, dies_utilitzar=list(DIES), shuffle_top_n=shuffle_top_n
        )
    finally:
        bt.calcular_cost_slot = cost_real
    return resultat[0]["dies"]


def _en_subproces(hashseed: int, random_seed: int, shuffle_top_n: int = 0) -> list:
    codi = (
        "import json, sys\n"
        f"sys.path[:0] = [{str(BACKEND)!r}, {str(BACKEND / 'tests')!r}]\n"
        "from test_backtrack_determinisme import horari_amb_empats\n"
        f"print(json.dumps(horari_amb_empats({random_seed}, {shuffle_top_n})))\n"
    )
    entorn = dict(os.environ, PYTHONHASHSEED=str(hashseed), PYTHON_DOTENV_DISABLED="1")
    sortida = subprocess.run(
        [sys.executable, "-c", codi], cwd=BACKEND, env=entorn, capture_output=True, text=True, check=True
    )
    return json.loads(sortida.stdout.strip().splitlines()[-1])


def test_mateixa_llavor_mateix_horari_amb_qualsevol_pythonhashseed():
    horaris = [_en_subproces(hashseed, random_seed=1) for hashseed in (0, 1, 2)]
    assert horaris[0] == horaris[1] == horaris[2]
    assert sum(len(examens) for _, examens in horaris[0]) == 4


def test_mateixa_llavor_amb_barreja_mateix_horari_amb_qualsevol_pythonhashseed():
    horaris = [_en_subproces(hashseed, random_seed=7, shuffle_top_n=5) for hashseed in (0, 1, 2)]
    assert horaris[0] == horaris[1] == horaris[2]


def test_llavors_diferents_poden_donar_horaris_diferents():
    # Amb shuffle_top_n la llavor barreja les franges empatades: la varietat
    # entre llavors es conserva.
    horaris = {json.dumps(horari_amb_empats(llavor, shuffle_top_n=5)) for llavor in range(1, 6)}
    assert len(horaris) > 1


def test_sense_barreja_llavors_diferents_desfan_els_empats_diferent():
    # Els empats de cost es desfan a l'atzar amb el rng de la llavor (abans,
    # per data i hora: totes les llavors donaven el mateix horari)
    horaris = {json.dumps(horari_amb_empats(llavor)) for llavor in range(1, 6)}
    assert len(horaris) > 1


def test_sense_barreja_la_mateixa_llavor_repeteix_l_horari():
    assert horari_amb_empats(3) == horari_amb_empats(3)


def test_els_empats_ja_no_van_a_les_primeres_franges_per_data_i_hora():
    # Amb data i hora, tots quatre anaven a les quatre primeres franges del dilluns
    primeres = [f"{DIES[0]}_{hora}" for hora in HORES[:4]]
    franges = [{franja for franja, _ in horari_amb_empats(llavor)} for llavor in range(1, 6)]
    assert any(f != set(primeres) for f in franges)
