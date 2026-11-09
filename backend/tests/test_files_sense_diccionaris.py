"""Guardià AST: les files tipades no es poden consumir com a diccionaris.

L'inventari identifica els paràmetres de fila dels consumidors. També segueix
àlies, lectures de repositori i contenidors locals, independentment del nom.
Els diccionaris de petició, activitats XML i resultats agregats continuen sent
estructures diferents de les files del domini.
"""

import ast
import os
from pathlib import Path

import pytest

from substitucions.files import FilaSubstitucio
from substitucions.repositories import SubstitucioRepository
from vigilancies.files import FilaVigilancia
from vigilancies.repositories import VigilanciaRepository

BACKEND = Path(__file__).resolve().parents[1]
# Variables de fila rebudes com a paràmetres o procedents de col·laboradors.
# '*' indica totes les funcions del fitxer; la resta, una funció concreta.
SUBSTITUCIONS = {
    "substitucions/domain.py": {"*": {"sub"}},
    "substitucions/assignacio.py": {"*": {"sub", "sub_encadenada", "sub_anterior", "dades"}},
    "substitucions/necessitats.py": {"*": {"sub"}},
    "substitucions/encadenades.py": {"*": {"fila"}},
    "substitucions/generacio.py": {"*": {"sub", "s"}},
    "substitucions/absencies.py": {"*": {"sub"}},
    "substitucions/cobertures.py": {"*": {"sub", "existent"}},
    "substitucions/vigilancia_absent.py": {"*": {"sub", "s", "pendent"}},
    "substitucions/prioritat.py": {"*": {"sub"}},
    "substitucions/visibilitat.py": {"*": {"fila"}},
    "substitucions/services.py": {"*": {"sub", "s", "fila", "substitucio_actual"}},
    "substitucions/_consultes.py": {"*": {"sub"}},
    "substitucions/schemas.py": {"*": {"sub"}},
    "vigilancies/analisi.py": {"*": {"sub", "s"}},
    "vigilancies/context.py": {"*": {"sub"}},
    "vigilancies/services.py": {"*": {"sub"}},
    "absencia_coberta/services.py": {"*": {"s"}},
    "recomptes/services.py": {"*": {"s"}},
    "estadistiques/services.py": {"*": {"s"}, "classes_detall": {"f"}},
    "pdf/informe_professors.py": {"*": {"s", "a", "x"}},
    "pdf/validacions.py": {"*": {"sub"}},
    "pdf/generacio.py": {"*": {"sub", "s"}, "_marca_substitucio": {"fila"}},
    "pdf/disponibles.py": {"*": {"sub"}},
    "pdf/taula.py": {"_valors_substitucio": {"sub"}},
    "pdf/engine.py": {"*": {"sub", "s"}},
}

VIGILANCIES = {
    "substitucions/domain.py": {"*": {"vig"}},
    "substitucions/_consultes.py": {"*": {"vigilancia"}},
    "substitucions/cobertures.py": {"*": {"vig"}},
    "substitucions/vigilancia_absent.py": {"*": {"vig"}},
    "vigilancies/analisi.py": {"*": {"v", "f"}},
    "vigilancies/services.py": {"*": {"vig", "v"}, "llista": {"x"}},
    "absencia_coberta/services.py": {"*": {"vig"}},
    "recomptes/services.py": {"vigilancies_per_resultat": {"v"}, "vigilancies_entre": {"v"}},
    "estadistiques/services.py": {"*": {"vig"}},
    "pdf/generacio.py": {"*": {"vig", "v"}, "_marca_dia": {"fila"}},
    "pdf/disponibles.py": {"*": {"vig"}},
    "pdf/taula.py": {"curs_vigilancia": {"vig"}, "_valors_vigilancia": {"vig"}},
    "pdf/engine.py": {"*": {"vig"}},
    "planificador/publicacio.py": {"_avisa_titulars_absents": {"v"}, "assigna_titulars": {"v"}},
    "grups/services.py": {"_reconcilia_dia": {"v"}},
}
for path, funcions in VIGILANCIES.items():
    for nom, variables in funcions.items():
        SUBSTITUCIONS.setdefault(path, {}).setdefault(nom, set()).update(variables)

# Categories internes: 1 fila, 2 llista de files, 3 mapa de llistes, 4 mapa de files.
LECTURES = {
    ("SubstitucioRepository", "get_by_date"): 2,
    ("VigilanciaRepository", "get_by_date"): 3,
    ("RecomptesRepository", "vigilancies_entre"): 2,
    ("RecomptesRepository", "substitucions_entre"): 2,
    ("RecomptesRepository", "amb_substitut_entre"): 2,
    ("RecomptesRepository", "franges_amb_substitut_entre"): 2,
}


def _fonts():
    for carpeta, dirs, files in os.walk(BACKEND):
        dirs[:] = [
            d for d in dirs if not d.startswith(("venv", "data", ".")) and d not in {"tests", "__pycache__", "exports"}
        ]
        for nom in files:
            if nom.endswith(".py"):
                p = Path(carpeta) / nom
                yield p.relative_to(BACKEND).as_posix(), p.read_text()


def _tipus(node, noms):
    if isinstance(node, ast.Name):
        return noms.get(node.id, 0)
    if isinstance(node, ast.Attribute) and node.attr == "files":
        return 2
    if isinstance(node, ast.Subscript):
        t = _tipus(node.value, noms)
        return (2 if isinstance(node.slice, ast.Slice) else 1) if t in {2, 4} else 2 if t == 3 else 0
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            if node.func.id in {"FilaSubstitucio", "PropostaSubstitucio", "FilaVigilancia"}:
                return 1
            if node.func.id in {"sorted", "list", "en_ordre"} and node.args:
                return _tipus(node.args[0], noms)
            if node.func.id == "next" and node.args:
                return 1 if _tipus(node.args[0], noms) == 2 else 0
        if isinstance(node.func, ast.Attribute):
            f = node.func
            if isinstance(f.value, ast.Name) and (t := LECTURES.get((f.value.id, f.attr))):
                return t
            t = _tipus(f.value, noms)
            if f.attr == "values":
                return 5 if t == 3 else 2 if t == 4 else 0
            if f.attr == "get":
                return 2 if t == 3 else 1 if t == 4 else 0
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
        locals_ = dict(noms)
        for g in node.generators:
            t = _tipus(g.iter, locals_)
            if isinstance(g.target, ast.Name):
                locals_[g.target.id] = 2 if t == 5 else 1 if t == 2 else 0
        value = node.value if isinstance(node, ast.DictComp) else node.elt
        return (4 if isinstance(node, ast.DictComp) else 2) if _tipus(value, locals_) == 1 else 0
    return 0


def _violacions(text, inventari=None):
    arbre = ast.parse(text)
    inventari = inventari or {}
    errors = []
    for funcio in (n for n in ast.walk(arbre) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))):
        noms = {n: 1 for n in inventari.get("*", set()) | inventari.get(funcio.name, set())}
        for arg in [*funcio.args.posonlyargs, *funcio.args.args, *funcio.args.kwonlyargs]:
            ann = ast.unparse(arg.annotation) if arg.annotation else ""
            if any(t in ann for t in ("FilaSubstitucio", "PropostaSubstitucio", "FilaVigilancia")):
                noms[arg.arg] = (
                    (3 if "list[" in ann else 4) if ann.startswith("dict[") else 2 if ann.startswith("list[") else 1
                )
        # Punt fix per als àlies i contenidors (també noms diferents dels de l'inventari).
        for _ in range(8):
            abans = dict(noms)
            for n in ast.walk(funcio):
                if isinstance(n, (ast.Assign, ast.AnnAssign)):
                    t = _tipus(n.value, noms) if n.value else 0
                    targets = n.targets if isinstance(n, ast.Assign) else [n.target]
                    for target in targets:
                        if isinstance(target, ast.Name) and t:
                            noms[target.id] = t
                elif isinstance(n, (ast.For, ast.comprehension)) and isinstance(n.target, ast.Name):
                    t = _tipus(n.iter, noms)
                    if t in {2, 5}:
                        noms[n.target.id] = 1 if t == 2 else 2
            if abans == noms:
                break
        for n in ast.walk(funcio):
            valor = None
            if isinstance(n, ast.Subscript):
                valor = n.value
            elif (
                isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)
                and n.func.attr in {"get", "keys", "items", "values", "update"}
            ):
                valor = n.func.value
            if valor is not None and _tipus(valor, noms) == 1:
                errors.append(f"{funcio.name}:{n.lineno}: {ast.unparse(n)}")
    return sorted(set(errors))


def test_les_files_no_es_llegeixen_ni_es_muten_com_diccionaris():
    errors = []
    for path, text in _fonts():
        errors.extend(f"{path}:{e}" for e in _violacions(text, SUBSTITUCIONS.get(path)))
    assert errors == []


def test_el_repositori_retorna_objectes_i_no_una_capa_de_compatibilitat(db_session):
    import typing

    assert typing.get_type_hints(SubstitucioRepository.get_by_date)["return"] == list[FilaSubstitucio]
    SubstitucioRepository.create(db_session, {"data": "2026-11-09", "hora": "10:00", "professor_absent": "Prof test"})
    fila = SubstitucioRepository.get_by_date(db_session, "2026-11-09")[0]
    assert isinstance(fila, FilaSubstitucio)
    assert not hasattr(fila, "get") and not hasattr(fila, "__getitem__")
    assert not hasattr(SubstitucioRepository, "get_files_by_date")


@pytest.mark.parametrize(
    "text",
    [
        'def f(sub): return sub.get("hora", "")',
        'def f(sub): return sub["hora"]',
        'def f(sub):\n alias = sub\n segon = alias\n return segon.get("substitut")',
        'def f():\n files = SubstitucioRepository.get_by_date(db, data)\n return files[0]["hora"]',
        'def f():\n for desconeguda in SubstitucioRepository.get_by_date(db, data):\n  desconeguda.get("hora")',
    ],
)
def test_el_guardia_rebutja_accessos_per_clau_i_alias(text):
    assert _violacions(text, {"*": {"sub"}})


def test_el_guardia_admet_diccionaris_que_no_son_files():
    assert _violacions('def f(config): return config.get("hora", "")') == []


def test_els_moduls_de_files_son_purs():
    permesos = {"dataclasses", "typing", "substitucions.files", "vigilancies.files"}
    for path, text in _fonts():
        if not path.endswith("/files.py"):
            continue
        for n in ast.walk(ast.parse(text)):
            if isinstance(n, ast.Import):
                assert all(a.name in permesos for a in n.names), path
            elif isinstance(n, ast.ImportFrom):
                assert n.module in permesos, path


def test_el_guardia_detecta_una_violacio_en_un_consumidor_real():
    text = (BACKEND / "substitucions/domain.py").read_text()
    modificat = text.replace("sub.hora", 'sub.get("hora")', 1)
    assert modificat != text
    assert _violacions(modificat, SUBSTITUCIONS["substitucions/domain.py"])


def test_les_vigilancies_tambe_surten_tipades_del_repositori(db_session):
    import typing

    assert typing.get_type_hints(VigilanciaRepository.get_by_date)["return"] == dict[str, list[FilaVigilancia]]
    assert not hasattr(FilaVigilancia(), "get") and not hasattr(FilaVigilancia(), "__getitem__")


@pytest.mark.parametrize(
    "text",
    [
        'def f():\n per_nivell = VigilanciaRepository.get_by_date(db, data)\n for files in per_nivell.values():\n  for alias in files:\n   alias.get("vigilant")',
        'def f():\n per_nivell = VigilanciaRepository.get_by_date(db, data)\n for files in per_nivell.values():\n  files[0]["hora"]',
    ],
)
def test_el_guardia_segueix_les_vigilancies_agrupades(text):
    assert _violacions(text)


def test_el_guardia_detecta_una_violacio_real_de_vigilancies():
    text = (BACKEND / "vigilancies/analisi.py").read_text()
    modificat = text.replace("v.hora", 'v.get("hora")', 1)
    assert modificat != text
    assert _violacions(modificat, SUBSTITUCIONS["vigilancies/analisi.py"])
