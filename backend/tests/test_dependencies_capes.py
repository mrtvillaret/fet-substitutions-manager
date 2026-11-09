"""Guardià AST de dependències: capes, cicles i imports interiors justificats.

No importa l’aplicació: analitza només fonts, també imports condicionals,
relatius, amb àlies i dins de funcions. Les excepcions són exactes i han de
portar el mateix motiu al costat del noqa de PLC0415.
"""

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
BASE = {
    "database",
    "models",
    "noms",
    "parametres",
    "rellotge",
    "errors_domini",
    "errors_servidor",
    "i18n_setup",
    "dates",
    "ordre_curs",
    "nivells",
    "textos",
}
# Casos d’ús que conserven el nom del seu concepte en lloc de services.py.
CASOS_D_US = {
    "pdf.generacio",
    "pdf.disponibles",
    "pdf.informe_direccio",
    "pdf.informe_professors",
    "configuracio_examens.importacio",
    "planificador.cost",
    "planificador.generacio",
    "planificador.publicacio",
    "planificador.config",
    "recomptes.services",
}
# (fitxer, funció qualificada, import) -> motiu exacte escrit al costat.
# Les proves queden fora d’aquest inventari de producció: imports locals per
# fixtures, monkeypatch i recàrrega sota entorns aïllats (pyproject.toml).
EXCEPCIONS = {
    (
        "pdf/informe_direccio.py",
        "_header_block",
        "from PIL import Image as PILImage",
    ): "Pillow només es carrega quan l’informe té logo.",
    (
        "pdf/engine.py",
        "PDFCompletExporter.__init__",
        "import pyphen",
    ): "Dependència opcional: ImportError conserva el PDF sense partició.",
    (
        "pdf/engine.py",
        "PDFCompletExporter._add_logo_to_page",
        "from PIL import Image",
    ): "El try del logo conserva la resta del PDF si falla la importació.",
    (
        "scripts/esborra_centre.py",
        "main",
        "from auth.repositories import UserRepository",
    ): "El CLI valida arguments abans d’inicialitzar l’aplicació.",
    (
        "scripts/esborra_centre.py",
        "main",
        "from centres import services",
    ): "El CLI valida arguments abans d’inicialitzar l’aplicació.",
    (
        "scripts/esborra_centre.py",
        "main",
        "from database import DATA_BASE_DIR, AuthSessionLocal, get_data_dir_for_institucio",
    ): "El CLI valida arguments abans d’inicialitzar l’aplicació.",
    (
        "scripts/esborra_centre.py",
        "main",
        "from errors_domini import ErrorDeDomini",
    ): "El CLI valida arguments abans d’inicialitzar l’aplicació.",
    (
        "scripts/esborra_centre.py",
        "main",
        "from models import User",
    ): "El CLI valida arguments abans d’inicialitzar l’aplicació.",
}


def _fonts():
    resultat = {}
    for carpeta, dirs, files in os.walk(BACKEND):
        dirs[:] = sorted(
            d for d in dirs if not d.startswith(("venv", "data", ".")) and d not in {"tests", "exports", "__pycache__"}
        )
        for nom in sorted(files):
            if nom.endswith(".py"):
                path = Path(carpeta) / nom
                resultat[path.relative_to(BACKEND).as_posix()] = path.read_text(encoding="utf-8")
    return resultat


def _modul(path):
    return path.removesuffix(".py").replace("/", ".").removesuffix(".__init__")


def _imports(node, scope=(), dins_funcio=False):
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        yield node, ".".join(scope), dins_funcio
    if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
        scope = (*scope, node.name)
    dins_funcio = dins_funcio or isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    for child in ast.iter_child_nodes(node):
        yield from _imports(child, scope, dins_funcio)


def _destins(node, modul, paquet, moduls):
    if isinstance(node, ast.Import):
        return [a.name for a in node.names]
    prefix = node.module or ""
    if node.level:
        parts = modul.split(".") if paquet else modul.split(".")[:-1]
        prefix = ".".join(parts[: len(parts) - node.level + 1] + ([prefix] if prefix else []))
    return [f"{prefix}.{a.name}" if f"{prefix}.{a.name}" in moduls else prefix for a in node.names]


def _es_base(modul):
    return modul in BASE or modul == "config" or modul.startswith("config.")


def _cicles(graf):
    """DFS: una aresta de retorn és prou per rebutjar un graf cíclic."""
    vistos, actius, errors = set(), set(), []

    def visita(modul, cami):
        if modul in actius:
            errors.append("cicle: " + " → ".join([*cami[cami.index(modul) :], modul]))
            return
        if modul in vistos:
            return
        actius.add(modul)
        for desti in sorted(graf[modul]):
            visita(desti, [*cami, modul])
        actius.remove(modul)
        vistos.add(modul)

    for modul in sorted(graf):
        visita(modul, [])
    return errors


def _violacions(fonts, excepcions=None, comprova_excepcions=True):
    excepcions = EXCEPCIONS if excepcions is None else excepcions
    moduls = {_modul(path) for path in fonts}
    arrels = {m.split(".")[0] for m in moduls}
    graf = {m: set() for m in moduls}
    trobades, errors = set(), []
    for path, text in sorted(fonts.items()):
        modul = _modul(path)
        tree = ast.parse(text, filename=path)
        # El registre tancat de la factory també afegeix arestes al graf.
        if modul == "scheduler_engine.factory":
            for node in ast.walk(tree):
                if not isinstance(node, ast.Dict):
                    continue
                for clau, valor in zip(node.keys, node.values, strict=True):
                    if isinstance(clau, ast.Constant) and clau.value == "module" and isinstance(valor, ast.Constant):
                        if valor.value in moduls:
                            graf[modul].add(valor.value)
                        if not valor.value.startswith("scheduler_engine.generators."):
                            errors.append(f"{path}:{valor.lineno}: motor depèn de l’aplicació web pel registre")
        ruta = path.endswith("/router.py") or any(
            isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "APIRouter"
            for n in ast.walk(tree)
        )
        for node, scope, local in _imports(tree):
            lloc = f"{path}:{node.lineno}"
            if local:
                clau = (path, scope, ast.unparse(node))
                motiu = excepcions.get(clau)
                if motiu:
                    trobades.add(clau)
                    linia = text.splitlines()[node.lineno - 1]
                    if "noqa: PLC0415" not in linia or motiu not in linia:
                        errors.append(f"{lloc}: falta noqa amb el motiu de l’excepció")
                else:
                    errors.append(f"{lloc}: import interior no justificat: {ast.unparse(node)}")
            for desti in _destins(node, modul, path.endswith("/__init__.py"), moduls):
                if desti in moduls:
                    graf[modul].add(desti)
                intern = desti.split(".")[0] in arrels
                if (_es_base(modul) or modul.startswith("schema_migrations.")) and intern and not _es_base(desti):
                    if not (
                        (modul == "database" or modul.startswith("schema_migrations."))
                        and desti.startswith("schema_migrations.")
                    ):
                        errors.append(f"{lloc}: base depèn del domini: {desti}")
                if path.endswith("/repositories.py") and intern:
                    if not (_es_base(desti) or desti.endswith((".repositories", ".files"))):
                        errors.append(f"{lloc}: repositori depèn d’una capa superior: {desti}")
                    if desti == "config.context":
                        errors.append(f"{lloc}: repositori llegeix context de petició")
                if not ruta and (desti.endswith(".router") or desti == "pdf.informes") and modul != "main":
                    errors.append(f"{lloc}: codi no HTTP importa rutes: {desti}")
                if path.endswith("/repositories.py") and desti.split(".")[0] in {"fastapi", "starlette"}:
                    errors.append(f"{lloc}: repositori importa context HTTP: {desti}")
                if path.endswith("/domain.py") and desti.endswith(".services"):
                    errors.append(f"{lloc}: domini importa serveis: {desti}")
                if ruta and intern:
                    perm = (
                        _es_base(desti)
                        or desti == "dependencies"
                        or desti == "rate_limit"
                        or desti.endswith((".services", ".schemas", ".dependencies", ".domain", ".security"))
                        or desti in CASOS_D_US
                    )
                    if not perm:
                        errors.append(f"{lloc}: ruta importa una capa no HTTP: {desti}")
                if modul.startswith("scheduler_engine."):
                    if (intern and not (desti.startswith("scheduler_engine.") or desti == "textos")) or desti.split(
                        "."
                    )[0] in {"fastapi", "starlette", "sqlalchemy", "pydantic"}:
                        errors.append(f"{lloc}: motor depèn de l’aplicació web: {desti}")
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            dinamic = (
                isinstance(node.func, ast.Name)
                and node.func.id == "__import__"
                or isinstance(node.func, ast.Attribute)
                and node.func.attr == "import_module"
            )
            if dinamic:
                permes = (
                    modul == "scheduler_engine.factory"
                    and ast.unparse(node) == "importlib.import_module(motor_info['module'])"
                )
                if not permes:
                    errors.append(f"{path}:{node.lineno}: import dinàmic fora del registre justificat")
        if ruta:
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr in {"query", "execute", "exec", "scalar", "scalars"}
                    or isinstance(node.func, ast.Name)
                    and node.func.id == "select"
                ):
                    errors.append(f"{path}:{node.lineno}: consulta dins d’una ruta")
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id in {"db", "session", "sessio"}
                    and node.func.attr
                    in {
                        "get",
                        "add",
                        "add_all",
                        "delete",
                        "flush",
                        "commit",
                        "rollback",
                        "connection",
                        "exec_driver_sql",
                    }
                ):
                    errors.append(f"{path}:{node.lineno}: consulta o escriptura dins d’una ruta")
    if comprova_excepcions:
        for clau in excepcions.keys() - trobades:
            errors.append(f"excepció caducada: {clau}")
    for modul in sorted(graf):
        if not modul.endswith(".repositories"):
            continue
        pendents, vistos = list(graf[modul]), set()
        while pendents:
            desti = pendents.pop()
            if desti in vistos:
                continue
            vistos.add(desti)
            if desti == "config.context":
                errors.append(f"{modul}: repositori depèn transitivament del context de petició")
            pendents.extend(graf[desti] - vistos)
    return errors + _cicles(graf)


def test_dependències_del_backend_respecten_les_capes():
    assert _violacions(_fonts()) == []


@pytest.mark.parametrize(
    ("path", "text", "esperat"),
    [
        ("models.py", "from grups.services import llista", "base depèn del domini"),
        ("schema_migrations/runner.py", "from grups.services import llista", "base depèn del domini"),
        ("grups/repositories.py", "from horari.context import get_horari", "repositori depèn"),
        ("grups/repositories.py", "from config.context import institucio_peticio", "context de petició"),
        ("grups/repositories.py", "from . import services", "repositori depèn"),
        ("grups/domain.py", "from grups import router", "importa rutes"),
        ("grups/domain.py", "from grups.services import llista", "domini importa serveis"),
        ("grups/services.py", "from grups.router import router as r", "importa rutes"),
        ("grups/router.py", "from grups.repositories import GrupRepository", "ruta importa"),
        ("grups/router.py", "db.query(Model)", "consulta dins"),
        ("grups/router.py", "db.get(Model, 1)", "consulta o escriptura"),
        ("grups/router.py", "db.add(model)", "consulta o escriptura"),
        ("grups/repositories.py", "from fastapi import Request", "context HTTP"),
        ("grups/services.py", "def f():\n    __import__('grups.router')", "import dinàmic"),
        ("grups/router.py", "db.execute(sql)", "consulta dins"),
        ("grups/router.py", "select(Model)", "consulta dins"),
        ("grups/services.py", "def f():\n    from models import Grup", "import interior"),
        ("grups/services.py", "async def f():\n    import models", "import interior"),
        ("grups/services.py", "def f():\n    def g():\n        import models", "import interior"),
        ("scheduler_engine/factory.py", "from grups.abreviatures import aplicar_abreviatura", "motor depèn"),
        ("scheduler_engine/factory.py", "from fastapi import Request", "motor depèn"),
        ("scheduler_engine/factory.py", "from noms import NomNet", "motor depèn"),
    ],
)
def test_el_guardia_rebutja_violacions_introduïdes(path, text, esperat):
    fonts = dict.fromkeys(
        [
            "models.py",
            "grups/repositories.py",
            "grups/services.py",
            "grups/router.py",
            "horari/context.py",
            "config/context.py",
            "grups/abreviatures.py",
            "noms.py",
        ],
        "",
    )
    fonts[path] = text
    assert any(esperat in e for e in _violacions(fonts, {}, False))


def test_el_guardia_rebutja_un_cicle_tambe_amb_import_interior():
    fonts = {"a.py": "from b import f", "b.py": "def f():\n    import a"}
    assert any("cicle:" in e for e in _violacions(fonts, {}, False))


def test_el_guardia_rebutja_excepcions_sense_motiu_i_caducades():
    clau = ("a.py", "f", "import os")
    assert any("falta noqa" in e for e in _violacions({"a.py": "def f():\n    import os"}, {clau: "motiu"}))
    assert any("caducada" in e for e in _violacions({"a.py": ""}, {clau: "motiu"}))
    assert _violacions({"a.py": "def f():\n    import os  # noqa: PLC0415 — motiu"}, {clau: "motiu"}) == []


def test_el_guardia_admet_repositoris_i_base_sense_importar_la_web():
    fonts = {
        "grups/repositories.py": "from models import Grup\nfrom configuracio.repositories import ConfiguracioRepository",
        "models.py": "",
        "configuracio/repositories.py": "",
    }
    assert _violacions(fonts, {}, False) == []


def test_repositori_tampoc_no_pot_llegir_context_a_traves_de_constants():
    fonts = {
        "grups/repositories.py": "from config.constants import PRIORITATS",
        "config/constants.py": "from config.context import institucio_peticio",
        "config/context.py": "",
    }
    assert any("transitivament del context" in e for e in _violacions(fonts, {}, False))


def test_registre_d_importacions_dinamiques_del_motor_es_tancat():
    arbre = ast.parse((BACKEND / "scheduler_engine/factory.py").read_text())
    destins = [
        valor.value
        for node in ast.walk(arbre)
        if isinstance(node, ast.Dict)
        for clau, valor in zip(node.keys, node.values, strict=True)
        if isinstance(clau, ast.Constant) and clau.value == "module" and isinstance(valor, ast.Constant)
    ]
    assert destins and all(d.startswith("scheduler_engine.generators.") for d in destins)


def test_el_guardia_rebutja_una_importacio_web_al_registre_del_motor():
    fonts = {"scheduler_engine/factory.py": 'MOTORS = {"x": {"module": "grups.services"}}', "grups/services.py": ""}
    assert any("pel registre" in e for e in _violacions(fonts, {}, False))


def test_el_guardia_detecta_cicles_amb_el_registre_dinamic():
    fonts = {
        "scheduler_engine/factory.py": 'MOTORS = {"x": {"module": "scheduler_engine.generators.x"}}',
        "scheduler_engine/generators/x.py": "import scheduler_engine.factory",
    }
    assert any("cicle:" in e for e in _violacions(fonts, {}, False))


def test_motor_es_pot_importar_sense_carregar_l_aplicacio_web(tmp_path):
    codi = """
import sys
import scheduler_engine.factory
import scheduler_engine.generators.v2_intents
import scheduler_engine.generators.v2_backtrack
import scheduler_engine.generators.v3_sa
prohibits = {"fastapi", "starlette", "sqlalchemy", "pydantic", "database", "models", "config", "horari", "grups", "noms"}
assert not prohibits.intersection(m.split(".")[0] for m in sys.modules)
"""
    env = {
        **os.environ,
        "DATA_DIR": str(tmp_path),
        "AUTH_DB_PATH": str(tmp_path / "auth.db"),
        "PYTHON_DOTENV_DISABLED": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    resultat = subprocess.run(
        [sys.executable, "-c", codi], cwd=BACKEND, env=env, capture_output=True, text=True, timeout=30
    )
    assert resultat.returncode == 0, resultat.stderr
    assert list(tmp_path.iterdir()) == []
