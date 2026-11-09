"""Nivell derivat d’un codi de grup, sense consultes ni propostes d’importació."""

import re

_GRUP_LLETRES_PATTERN = re.compile(r"^(.*?)-?([A-D]{1,4})$")


def deriva_nivell(grup: str) -> str:
    """Nivell d'un codi de grup: '1-ESO-A' -> '1-ESO'; '1-BATX' -> '1-BATX'.

    Una classe amb alumnes de diversos grups sense abreviatura definida
    ('1-BAT-A,1-BAT-B') té el nivell comú dels grups ('1-BAT'); si no en
    tenen cap de comú, es deixa tal qual.
    """
    if "," in grup:
        nivells = {deriva_nivell(part.strip()) for part in grup.split(",") if part.strip()}
        return nivells.pop() if len(nivells) == 1 else grup
    m = _GRUP_LLETRES_PATTERN.match(grup)
    if m:
        return m.group(1)
    return grup
