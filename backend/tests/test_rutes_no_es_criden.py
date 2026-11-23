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
FORA = {"tests", "__pycache__"}


def _crea_router(arbre) -> bool:
    return any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "APIRouter" for n in ast.walk(arbre)
    )


def _fitxers():
    """Els fitxers amb rutes: tots els que creen un APIRouter (router.py i, p.
    ex., pdf/informes.py), com el guardià de capes."""
    return {
        f: arbre
        for f in sorted(BACKEND.rglob("*.py"))
        if not FORA & set(parts := f.relative_to(BACKEND).parts)
        and not parts[0].startswith("venv")
        and _crea_router(arbre := ast.parse(f.read_text(encoding="utf-8")))
    }


def _rutes(arbre) -> set:
    noms = set()
    for node in ast.walk(arbre):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                f = dec.func if isinstance(dec, ast.Call) else dec
                # router, i també router_admin (dos routers al mateix fitxer)
                if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id.startswith("router"):
                    noms.add(node.name)
    return noms


def test_cap_funcio_de_ruta_no_es_crida_directament():
    arbres = _fitxers()
    rutes = set().union(*(_rutes(a) for a in arbres.values()))
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


def test_el_guardia_troba_tots_els_fitxers_de_rutes():
    fitxers = {str(f.relative_to(BACKEND)) for f in _fitxers()}
    assert {"pdf/router.py", "pdf/informes.py", "vigilancies/router.py"} <= fitxers
    assert not any(f.startswith("routes/") for f in fitxers)
