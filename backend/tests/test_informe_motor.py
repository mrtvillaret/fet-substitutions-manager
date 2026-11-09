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


def test_informe_no_canvia_stdout_i_conserva_text():
    from scheduler_engine.informe import captura_informe, log

    stdout = sys.stdout
    with captura_informe() as sortida:
        log.info("primera línia")
        log.info("\n   segona línia: %s", 3)
    assert sortida.getvalue() == "primera línia\n\n   segona línia: 3\n"
    assert sys.stdout is stdout


def test_informes_concurrents_no_es_barregen():
    from scheduler_engine.informe import captura_informe, log

    barrera = Barrier(4)

    def executa(n):
        with captura_informe() as sortida:
            for i in range(20):
                barrera.wait(timeout=10)
                log.info("execució %s, missatge %s", n, i)
        return sortida.getvalue().splitlines()

    with ThreadPoolExecutor(max_workers=4) as pool:
        informes = list(pool.map(executa, range(4)))
    for n, linies in enumerate(informes):
        assert linies == [f"execució {n}, missatge {i}" for i in range(20)]


def test_informe_imbricat_i_excepcio_restauren_el_context():
    from scheduler_engine.informe import captura_informe, log

    with captura_informe() as exterior:
        log.info("abans")
        with pytest.raises(RuntimeError), captura_informe() as interior:
            log.info("interior")
            raise RuntimeError("fallada simulada")
        log.info("després")
    log.info("fora")
    assert exterior.getvalue() == "abans\ndesprés\n"
    assert interior.getvalue() == "interior\n"
    with captura_informe() as nou:
        log.info("nou")
    assert nou.getvalue() == "nou\n"


def test_cap_print_al_motor_ni_captura_de_stdout():
    assert not (BACKEND / "captura_sortida.py").exists()
    for cami in (BACKEND / "scheduler_engine").rglob("*.py"):
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
