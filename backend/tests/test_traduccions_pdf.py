"""
Tots els textos dels PDF i dels informes es tradueixen a les tres llengües
(es, en, it). Abans, un text nou sortia en català al PDF castellà sense que
ningú se n'adonés, i algunes traduccions tenien uns altres camps ({hora},
{num}...) que el text original, o en faltaven.

El test revisa el codi: cada text literal passat a _() o translate() als
fitxers dels PDF, més les etiquetes de les columnes i la nota de les
vigilàncies (que es tradueixen amb una variable), ha de tenir una traducció
activa al .mo de cada llengua, amb els mateixos camps, i el .mo ha de
coincidir amb el .po (que no s'hagi oblidat de compilar).
"""

import ast
import gettext
import re
from pathlib import Path

import pytest

from pdf.taula import NOTA_VIGILANCIES, SUBSTITUCIONS, VIGILANCIES

BACKEND = Path(__file__).resolve().parent.parent
LOCALES = BACKEND / "locales"
LLENGUES = ("es", "en", "it")
FITXERS_PDF = ()
FUNCIONS = {"_", "translate"}


def _fitxers_pdf():
    yield from sorted((BACKEND / "pdf").rglob("*.py"))
    for nom in FITXERS_PDF:
        yield BACKEND / nom


def _textos_pdf():
    textos = set()
    for fitxer in _fitxers_pdf():
        for node in ast.walk(ast.parse(fitxer.read_text(encoding="utf-8"))):
            nom = getattr(node, "func", None)
            nom = getattr(nom, "id", None) or getattr(nom, "attr", None)
            if (
                isinstance(node, ast.Call)
                and nom in FUNCIONS
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                textos.add(node.args[0].value)
    textos |= set(SUBSTITUCIONS.etiquetes.values()) | set(VIGILANCIES.etiquetes.values())
    textos.add(NOTA_VIGILANCIES)
    textos.discard("")
    return textos


TEXTOS = _textos_pdf()


def _cataleg(llengua):
    with open(LOCALES / llengua / "LC_MESSAGES" / "messages.mo", "rb") as f:
        return gettext.GNUTranslations(f)._catalog


def _desescapa(cometes):
    text = "".join(re.findall(r'"((?:[^"\\]|\\.)*)"', cometes))
    escapes = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}
    return re.sub(r"\\(.)", lambda m: escapes.get(m.group(1), m.group(0)), text)


def _po_actiu(llengua):
    """{msgid: msgstr} de les entrades actives del .po (sense obsoletes ni fuzzy)."""
    text = (LOCALES / llengua / "LC_MESSAGES" / "messages.po").read_text(encoding="utf-8")
    entrades = {}
    for bloc in re.split(r"\n\s*\n", text):
        if "#, fuzzy" in bloc or re.search(r"^#~", bloc, re.M):
            continue
        msgid = re.search(r'^msgid ((?:"(?:[^"\\]|\\.)*"\s*)+)', bloc, re.M)
        msgstr = re.search(r'^msgstr ((?:"(?:[^"\\]|\\.)*"\s*)+)', bloc, re.M)
        if msgid and msgstr:
            entrades[_desescapa(msgid.group(1))] = _desescapa(msgstr.group(1))
    return entrades


def _camps(text):
    return sorted(re.findall(r"\{[^{}]*\}", text))


def test_es_troben_els_textos_dels_pdf():
    # Si el recorregut deixés de trobar-los, el test passaria sense revisar res
    assert len(TEXTOS) > 100
    assert "Absències cobertes" in TEXTOS and "Dl." in TEXTOS


@pytest.mark.parametrize("llengua", LLENGUES)
def test_cada_text_dels_pdf_te_traduccio(llengua):
    cataleg = _cataleg(llengua)
    assert sorted(t for t in TEXTOS if not cataleg.get(t)) == []


@pytest.mark.parametrize("llengua", LLENGUES)
def test_les_traduccions_tenen_els_mateixos_camps(llengua):
    cataleg = _cataleg(llengua)
    diferents = [
        (text, cataleg[text]) for text in sorted(TEXTOS) if text in cataleg and _camps(text) != _camps(cataleg[text])
    ]
    assert diferents == []


@pytest.mark.parametrize("llengua", LLENGUES)
def test_el_mo_esta_compilat_del_po(llengua):
    cataleg = _cataleg(llengua)
    po = _po_actiu(llengua)
    diferents = sorted(t for t in TEXTOS if po.get(t) != cataleg.get(t))
    assert diferents == []


def test_en_angles_sempre_invigilation():
    """Vigilància d'examen és «invigilation» (i vigilant, «invigilator»), mai «supervision»."""
    cataleg = _cataleg("en")
    assert sorted(t for t in TEXTOS if "supervis" in cataleg.get(t, "").lower()) == []
