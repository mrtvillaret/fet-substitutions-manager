"""
L'horari (XML) sempre es demana per a una data, i les rutes hi arriben
només a través de serveis.dia.Dia (amb les dependències de dependencies.py). Quan la data era opcional,
una crida que se n'oblidava no fallava: agafava un altre horari en silenci i
l'error no es veia fins que hi havia un horari nou pujat amb data futura.
Ara la data és obligatòria (data_iso=...; per a avui, avui()) i aquest test
revisa el codi perquè cap crida la torni a deixar implícita.
"""

import ast
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
AMB_DATA_PER_NOM = {"get_horari", "get_gestors", "get_horari_fn"}


def _crides_sense_data():
    for fitxer in sorted(BACKEND.rglob("*.py")):
        if {"venv", "_legacy"} & set(fitxer.parts):
            continue
        for node in ast.walk(ast.parse(fitxer.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            nom = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if nom in AMB_DATA_PER_NOM and not any(k.arg == "data_iso" for k in node.keywords):
                yield f"{fitxer.relative_to(BACKEND)}:{node.lineno}  {ast.unparse(node)}"
            elif nom == "get_xml_path_for_date" and len(node.args) + len(node.keywords) < 2:
                yield f"{fitxer.relative_to(BACKEND)}:{node.lineno}  {ast.unparse(node)}"


def test_cap_crida_a_l_horari_sense_data():
    assert list(_crides_sense_data()) == []


PORTES_A_L_HORARI = {"get_horari", "get_gestors", "get_xml_path_for_date", "get_vigilancia_core", "get_horari_fn"}


def test_les_rutes_arriben_a_l_horari_nomes_a_traves_de_dia():
    """La regla de quin horari toca és a Dia i a les dependències; una ruta que
    cridés get_horari pel seu compte la podria saltar."""
    directes = []
    # routes/ i els router.py dels mòduls (auth/, prioritats/, vigilancies/...)
    for fitxer in sorted([*(BACKEND / "routes").glob("*.py"), *BACKEND.glob("*/router.py")]):
        for node in ast.walk(ast.parse(fitxer.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call):
                nom = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
                if nom in PORTES_A_L_HORARI:
                    directes.append(f"{fitxer.relative_to(BACKEND)}:{node.lineno}  {ast.unparse(node)}")
    assert directes == []
