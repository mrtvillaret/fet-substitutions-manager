"""L'informe és logging local a l'execució, sense globals de Python mutats."""

import ast
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

BACKEND = Path(__file__).resolve().parents[1]


def test_traduccio_no_altera_builtins():
    resultat = subprocess.run(
        [
            sys.executable,
            "-c",
            "import builtins; abans = dict(vars(builtins)); import i18n_setup; assert vars(builtins) == abans",
        ],
        cwd=BACKEND,
        env={**os.environ, "PYTHON_DOTENV_DISABLED": "1"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert resultat.returncode == 0, resultat.stderr


def test_cap_mutacio_de_builtins():
    trobats = []
    for cami in BACKEND.rglob("*.py"):
        rel = cami.relative_to(BACKEND)
        if rel.parts[0] in {"venv", "venv_old_py313_broken", "tests", "__pycache__"}:
            continue
        tree = ast.parse(cami.read_text())
        for n in ast.walk(tree):
            if isinstance(n, ast.Import) and any(a.name == "builtins" for a in n.names):
                trobats.append(f"{rel}:{n.lineno}")
            if isinstance(n, ast.ImportFrom) and n.module == "builtins":
                trobats.append(f"{rel}:{n.lineno}")
            if isinstance(n, ast.Name) and n.id == "__builtins__":
                trobats.append(f"{rel}:{n.lineno}")
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "install":
                trobats.append(f"{rel}:{n.lineno}")
    assert trobats == []


def _registre_de_la_cerca(monkeypatch, n):
    from test_planificador_aturada import MotorAmbCostZero

    resultat, _ = MotorAmbCostZero(monkeypatch, n=n, hores=n).genera()
    return resultat.registre


def test_el_registre_no_canvia_stdout_i_conserva_text(monkeypatch, capsys):
    stdout = sys.stdout
    registre = _registre_de_la_cerca(monkeypatch, 2)
    assert registre == [
        "🔍 Pre-calculant costos i compatibilitats per 2 items...",
        "   Calculant matriu de compatibilitat 2x2...",
        "   ✅ 2 items preparats",
        "   📊 Nodes explorats: 3, solucions trobades: 1",
    ]
    assert sys.stdout is stdout
    assert capsys.readouterr() == ("", "")


def test_registres_concurrents_no_es_barregen(monkeypatch):
    """Cada execució porta el seu registre (no hi ha cap destí global): quatre
    cerques alhora donen el mateix registre que cadascuna sola."""
    sols = [_registre_de_la_cerca(monkeypatch, n) for n in range(1, 5)]
    barrera = Barrier(4)

    def executa(n):
        barrera.wait(timeout=10)
        return _registre_de_la_cerca(monkeypatch, n)

    with ThreadPoolExecutor(max_workers=4) as pool:
        registres = list(pool.map(executa, range(1, 5)))
    assert registres == sols


def test_cap_print_al_motor_ni_captura_de_stdout():
    assert not (BACKEND / "captura_sortida.py").exists()
    for cami in (BACKEND / "planificador").rglob("*.py"):
        for n in ast.walk(ast.parse(cami.read_text())):
            assert not (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "print"), cami


@pytest.mark.parametrize(
    "tipus,emoji",
    [
        ("reforç", "⭐"),
        ("alliberat", "✅"),
        ("guàrdia", "🛡️"),
        ("guàrdia-r", "🛡️"),
        ("guàrdia-t", "🛡️"),
        ("guàrdia-p", "🛡️"),
        ("web", "💻"),
        ("informàtica", "🖥️"),
        ("correcció", "✏️"),
        ("bat dual", "🎓"),
        ("reforç-a", "⭐"),
        ("cd", "👨‍💼"),
        ("alumnes", "👥"),
        ("alumnes-batx", "👥"),
        ("orientació", "🧭"),
        ("gp", "🌳"),
        ("disponible", "🟢"),
        ("lliure", "⚪"),
        ("altre", "🟢"),
    ],
)
def test_emojis_visibles_conserven_el_resultat(tipus, emoji):
    from config.constants import get_professor_emoji

    assert get_professor_emoji(tipus) == emoji
    assert get_professor_emoji(f"Activitat {tipus.upper()} de prova") == emoji
