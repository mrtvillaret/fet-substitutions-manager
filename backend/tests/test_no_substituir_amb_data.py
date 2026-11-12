"""
«No substituir» té vigència per dates (migració 0004): la llista sempre es
demana per a una data, i l'única porta és `prioritats.files.VigenciaNoSubstituir.a`
(que s'obté de la BD amb `NoSubstituirRepository.vigencia`/`vigents_a` o de
memòria amb `prioritats.memoria.no_substituir_a`). Abans, una llista sense
data feia que afegir una activitat amagués files i canviés els recomptes dels
cursos passats. Aquest test revisa el codi perquè cap lectura no torni a ser
sense data.
"""

import ast
import os
from pathlib import Path

import pytest

from prioritats.files import EntradaNoSubstituir, VigenciaNoSubstituir

BACKEND = Path(__file__).resolve().parent.parent
# Noms de la llista sense data que ja no existeixen.
NOMS_RETIRATS = {"NO_SUBST", "GENERA_ENCADENADES"}
# La porta: qui pot tocar les files o les entrades directament.
PORTA = {"prioritats/repositories.py", "prioritats/memoria.py", "prioritats/services.py", "prioritats/files.py"}
# Lectures amb data: (nom, nombre mínim d'arguments posicionals o amb nom)
AMB_DATA = {"vigents_a": 2, "no_substituir_a": 1}


def _fonts():
    for arrel, directoris, fitxers in os.walk(BACKEND, topdown=True):
        directoris[:] = sorted(
            d
            for d in directoris
            if not d.startswith("venv") and d not in {".git", "__pycache__", "_legacy", "tests", "migracions"}
        )
        for nom in sorted(f for f in fitxers if f.endswith(".py")):
            fitxer = Path(arrel, nom)
            yield str(fitxer.relative_to(BACKEND)), fitxer.read_text(encoding="utf-8")


def _violacions(fonts):
    errors = []
    for path, text in fonts:
        for node in ast.walk(ast.parse(text)):
            lloc = f"{path}:{getattr(node, 'lineno', 0)}"
            if isinstance(node, ast.Name) and node.id in NOMS_RETIRATS:
                errors.append(f"{lloc}: llista sense data {node.id}")
            elif isinstance(node, ast.Attribute) and node.attr in NOMS_RETIRATS:
                errors.append(f"{lloc}: llista sense data {node.attr}")
            elif isinstance(node, ast.alias) and node.name in NOMS_RETIRATS:
                errors.append(f"{lloc}: llista sense data {node.name}")
            if path in PORTA or path.startswith("schema_migrations/"):
                continue
            if isinstance(node, ast.Name) and node.id == "NoSubstituir":
                errors.append(f"{lloc}: files de no_substituir fora de la porta")
            elif isinstance(node, ast.Attribute) and node.attr == "entrades":
                errors.append(f"{lloc}: entrades de «No substituir» fora de la porta")
            elif isinstance(node, ast.Call):
                func = node.func
                nom = getattr(func, "id", None) or getattr(func, "attr", None)
                rebuts = len(node.args) + len(node.keywords)
                if nom in AMB_DATA and rebuts < AMB_DATA[nom]:
                    errors.append(f"{lloc}: {ast.unparse(node)} sense data")
                if (
                    isinstance(func, ast.Attribute)
                    and ast.unparse(func.value) == "NoSubstituirRepository"
                    and func.attr not in {"vigencia", "vigents_a"}
                ):
                    errors.append(f"{lloc}: {ast.unparse(node)}: només vigencia/vigents_a fora de prioritats")
                if nom == "a" and isinstance(func, ast.Attribute) and not node.args and not node.keywords:
                    errors.append(f"{lloc}: {ast.unparse(node)} sense data")
    return errors


def test_cap_lectura_de_no_substituir_sense_data():
    assert _violacions(_fonts()) == []


@pytest.mark.parametrize(
    "text",
    [
        "from config.constants import NO_SUBST",
        "x = constants.GENERA_ENCADENADES",
        "NoSubstituirRepository.get_all(db)",
        "NoSubstituirRepository.vigents_a(db)",
        "no_substituir_a()",
        "db.query(NoSubstituir).all()",
        "[e.assignatura for e in vigencia.entrades]",
        "vigencia.a()",
    ],
)
def test_el_guardia_detecta_lectures_sense_data(text):
    assert _violacions([("substitucions/prova.py", text)])


def test_el_guardia_admet_les_lectures_amb_data():
    text = (
        "NoSubstituirRepository.vigents_a(db, data)\n"
        "v = NoSubstituirRepository.vigencia(db)\n"
        "v.a(fila.data)\n"
        "no_substituir_a(data_iso)\n"
    )
    assert _violacions([("recomptes/prova.py", text)]) == []


def test_la_vigencia_no_es_pot_fer_servir_com_una_llista():
    vigencia = VigenciaNoSubstituir((EntradaNoSubstituir(1, "Guàrdia"),))
    with pytest.raises(TypeError):
        "Guàrdia" in vigencia  # noqa: B015
    with pytest.raises(TypeError):
        list(vigencia)
    for sense_data in (None, "", "11/11/2026", "2026-11-1"):
        with pytest.raises(ValueError):
            vigencia.a(sense_data)


def test_cada_entrada_val_entre_les_seves_dates_incloses():
    vigencia = VigenciaNoSubstituir(
        (
            EntradaNoSubstituir(1, "Sempre"),
            EntradaNoSubstituir(2, "Tancada", vigent_fins_a="2026-11-10"),
            EntradaNoSubstituir(3, "Nova", vigent_des_de="2026-11-11"),
            EntradaNoSubstituir(4, "Període", vigent_des_de="2026-09-01", vigent_fins_a="2026-09-30"),
        )
    )
    assert vigencia.a("2026-08-31") == {"Sempre", "Tancada"}
    assert vigencia.a("2026-09-01") == {"Sempre", "Tancada", "Període"}
    assert vigencia.a("2026-09-30") == {"Sempre", "Tancada", "Període"}
    assert vigencia.a("2026-11-10") == {"Sempre", "Tancada"}
    assert vigencia.a("2026-11-11") == {"Sempre", "Nova"}
