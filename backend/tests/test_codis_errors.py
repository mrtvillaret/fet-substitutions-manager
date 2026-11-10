"""
Els codis dels errors de domini (errors_domini.py) són estables i el frontend
els tradueix (frontend/src/locales/*.json, `errors.<codi>`) amb els paràmetres
de l'error. Perquè la traducció digui el mateix que el text del servidor:

- un codi, un sol text: dos llocs amb el mateix codi diuen el mateix;
- el text català de cada `errors.<codi>` és exactament el del servidor, amb
  cada valor interpolat com a `{paràmetre}` (els paràmetres de l'error porten
  els mateixos valors que el text). Així, en català la pantalla no canvia.

El test llegeix el codi (AST): cada `raise` amb `codi="..."` literal.
"""

import ast
import json
from collections import defaultdict
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
CA = BACKEND.parent / "frontend" / "src" / "locales" / "ca.json"


def _fitxers():
    for fitxer in sorted(BACKEND.rglob("*.py")):
        parts = fitxer.relative_to(BACKEND).parts
        if not any(p.startswith("venv") or p in {"tests", "__pycache__"} for p in parts):
            yield fitxer


def _kw(call, nom):
    return next((k.value for k in call.keywords if k.arg == nom), None)


def _plantilla(missatge, params):
    """El text de l'error amb {paràmetre} on hi ha cada valor, o None si no es
    pot deduir (text calculat, o un valor interpolat que no és a params)."""
    valors = {}
    if isinstance(params, ast.Dict):
        valors = {ast.unparse(v): k.value for k, v in zip(params.keys, params.values, strict=True)}
    if isinstance(missatge, ast.Constant) and isinstance(missatge.value, str):
        return missatge.value
    if isinstance(missatge, ast.Call) and getattr(missatge.func, "id", None) == "_":
        return _plantilla(missatge.args[0], params)
    if isinstance(missatge, ast.Call) and getattr(missatge.func, "attr", None) == "format":
        # _("... {x} ...").format(x=valor): el paràmetre x ha de portar el mateix valor
        base = _plantilla(missatge.func.value, None)
        if base is None or any(valors.get(ast.unparse(k.value)) != k.arg for k in missatge.keywords):
            return None
        return base
    if isinstance(missatge, ast.JoinedStr):
        trossos = []
        for part in missatge.values:
            if isinstance(part, ast.Constant):
                trossos.append(part.value)
            elif part.conversion == -1 and part.format_spec is None and ast.unparse(part.value) in valors:
                trossos.append("{" + valors[ast.unparse(part.value)] + "}")
            else:
                return None
        return "".join(trossos)
    return None


def _errors_del_codi():
    """{codi: {plantilla o None: [llocs]}} de totes les crides amb codi literal."""
    per_codi = defaultdict(lambda: defaultdict(list))
    for fitxer in _fitxers():
        for node in ast.walk(ast.parse(fitxer.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            codi = _kw(node, "codi")
            if isinstance(codi, ast.Constant) and isinstance(codi.value, str):
                lloc = f"{fitxer.relative_to(BACKEND)}:{node.lineno}"
                per_codi[codi.value][_plantilla(node.args[0], _kw(node, "params"))].append(lloc)
    return per_codi


ERRORS = _errors_del_codi()
TRADUCCIONS = json.loads(CA.read_text(encoding="utf-8")).get("errors", {})


def test_un_codi_un_sol_text():
    repetits = {codi: dict(textos) for codi, textos in ERRORS.items() if len(textos) > 1}
    assert repetits == {}


def test_cada_traduccio_correspon_a_un_codi_amb_el_mateix_text_catala():
    diferents = {}
    for codi, text in TRADUCCIONS.items():
        plantilles = list(ERRORS.get(codi, {}))
        if plantilles != [text]:
            diferents[codi] = {"ca.json": text, "servidor": plantilles or "codi inexistent"}
    assert diferents == {}


def test_la_plantilla_entén_els_textos_amb_parametres():
    arbre = ast.parse(
        'NoValid(f"❌ {nom} a les {h}!", codi="c", params={"substitut": nom, "hora": h})\n'
        'NoValid(f"{x.isoformat()}", codi="c", params={"data": x})\n'
        'NoValid(_("❌ {substitut} fora").format(substitut=s), codi="c", params={"substitut": s})\n'
        'NoValid(_("❌ {substitut} fora").format(substitut=s), codi="c")',
    )
    crides = [n.value for n in arbre.body]
    assert [_plantilla(c.args[0], _kw(c, "params")) for c in crides] == [
        "❌ {substitut} a les {hora}!",
        None,
        "❌ {substitut} fora",
        None,
    ]
