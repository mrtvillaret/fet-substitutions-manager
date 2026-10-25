"""
Una funció de ruta no es crida mai directament des del codi: els seus
paràmetres amb Depends (la sessió, l'usuari, el Dia...) només els resol
FastAPI. Cridada a mà, rep l'objecte Depends i falla, sovint en silenci (el PDF
complet va perdre així els avisos de prioritat). La feina comuna va en una
funció normal que criden totes dues rutes.
"""

import ast
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
# Pendent de decidir (treure-la o arreglar-la): GET /api/disponibles/{data}/resum
# crida get_disponibles_dia sense el Dia (respon 404) i no la fa servir res.
PERMESES = {"get_disponibles_dia"}


def _fitxers():
    return sorted([*(BACKEND / "routes").glob("*.py"), *BACKEND.glob("*/router.py")])


def _rutes(arbre) -> set:
    noms = set()
    for node in ast.walk(arbre):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                f = dec.func if isinstance(dec, ast.Call) else dec
                if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "router":
                    noms.add(node.name)
    return noms


def test_cap_funcio_de_ruta_no_es_crida_directament():
    arbres = {f: ast.parse(f.read_text(encoding="utf-8")) for f in _fitxers()}
    rutes = set().union(*(_rutes(a) for a in arbres.values())) - PERMESES
    crides = []
    for fitxer, arbre in arbres.items():
        for node in ast.walk(arbre):
            # La funció de ruta pel seu nom (importada o del mateix fitxer); un
            # mètode d'un altre objecte amb el mateix nom no compta
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                nom = node.func.id
                if nom in rutes:
                    crides.append(f"{fitxer.relative_to(BACKEND)}:{node.lineno}  {nom}()")
    assert crides == []
