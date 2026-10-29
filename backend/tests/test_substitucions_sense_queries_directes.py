"""Les rutes i els serveis de substitucions no consulten la BD directament."""

import ast
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]

MODUL_SUBSTITUCIONS = (
    "_consultes.py",
    "absencies.py",
    "cobertures.py",
    "domain.py",
    "encadenades.py",
    "generacio.py",
    "prioritat.py",
    "vigilancia_absent.py",
)


def _fitxers_vigilats():
    yield BACKEND / "substitucions" / "router.py"
    yield BACKEND / "substitucions" / "services.py"
    for nom in MODUL_SUBSTITUCIONS:
        yield BACKEND / "substitucions" / nom
    yield from sorted((BACKEND / "substitucions").glob("*services.py"))


def test_les_rutes_i_els_serveis_de_substitucions_no_fan_queries_directes():
    queries = []
    for fitxer in _fitxers_vigilats():
        arbre = ast.parse(fitxer.read_text(encoding="utf-8"))
        for node in ast.walk(arbre):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "query"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "db"
            ):
                queries.append(f"{fitxer.relative_to(BACKEND)}:{node.lineno}  {ast.unparse(node)}")

    assert queries == []
