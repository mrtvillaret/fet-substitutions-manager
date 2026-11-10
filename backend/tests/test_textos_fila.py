"""Text del tipus de substitut i clau de fila: una sola funció per a cadascun."""

import ast
from pathlib import Path

import pytest

from substitucions.assignacio import text_tipus_substitut, tipus_real
from substitucions.files import clau_fila

SUBSTITUCIONS = Path(__file__).resolve().parents[1] / "substitucions"


@pytest.mark.parametrize(
    "tipus,detall,text",
    [
        ("Guàrdia", "Guàrdia", "disponible (Guàrdia)"),
        ("alliberat", "tenia Anglès - 3-ESO-A", "alliberat (tenia Anglès - 3-ESO-A)"),
        ("alliberat", "alliberat", "alliberat (alliberat)"),
        ("vigilància", "Guàrdia - VIGILÀNCIA", "vigilància (Guàrdia - VIGILÀNCIA)"),
    ],
)
def test_text_del_tipus_de_substitut(tipus, detall, text):
    assert text_tipus_substitut(tipus, detall) == text
    assert tipus_real(text) == tipus


def test_clau_de_fila():
    assert clau_fila("Prof 1", "10:00", "Anglès", "3-ESO-A") == "Prof 1|10:00|Anglès|3-ESO-A"
    assert clau_fila("Prof 1", "10:00", "Guàrdia", "") == "Prof 1|10:00|Guàrdia|"


def _textos_fixos(arbre):
    for node in ast.walk(arbre):
        if isinstance(node, ast.JoinedStr):
            yield "".join(v.value for v in node.values if isinstance(v, ast.Constant))


def test_cap_altre_lloc_no_construeix_el_text_ni_la_clau():
    """Guardià: els f-strings «disponible (…)» i «…|…|…|…» només surten de les dues funcions."""
    trobats = []
    for fitxer in sorted(SUBSTITUCIONS.glob("*.py")):
        for text in _textos_fixos(ast.parse(fitxer.read_text(encoding="utf-8"))):
            if text.startswith("disponible (") or text == "|||":
                trobats.append((fitxer.name, text))
    assert sorted(trobats) == [("assignacio.py", "disponible ()"), ("files.py", "|||")]
