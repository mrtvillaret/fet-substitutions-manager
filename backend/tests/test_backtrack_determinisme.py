"""La mateixa llavor dona el mateix horari del backtracking, sigui quin
sigui `PYTHONHASHSEED`: els empats de cost es resolen a l'atzar amb el rng de
la llavor, no per l'ordre d'un `set`.

Cada execució es fa en un subprocés, perquè `PYTHONHASHSEED` només es pot
triar en arrencar l'intèrpret. El motor és el real (el nou); només se'n
substitueixen la partició i l'anàlisi de cada franja (tot val 0: tot són empats)."""

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
    ha anat cadascun ([(ítem, franja)], ordenat)."""
    from test_planificador_backtracking_nou import horari_amb_empats as amb_motor_nou

    return [list(parella) for parella in amb_motor_nou(random_seed, shuffle_top_n)]


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
    assert len(horaris[0]) == 4


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
    franges = [{franja for _, franja in horari_amb_empats(llavor)} for llavor in range(1, 6)]
    assert any(f != set(primeres) for f in franges)
