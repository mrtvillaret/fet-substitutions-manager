"""
Les substitucions encadenades d'un dia, d'acord amb els substituts que hi ha
(la regla, a core/encadenades.py): després de triar un substitut a mà, o de
posar o treure absències, cada substitut que deixa una activitat que cal
cobrir en té una (pendent: el substitut no es posa sol) i la que ja no cal
s'esborra.
"""

import logging

from core.encadenades import activitat_encadenada
from repositories import SubstitucioRepository

log = logging.getLogger(__name__)


def reconcilia_encadenades(db, data: str) -> dict:
    """Crea les encadenades que falten (sense substitut) i esborra les que ja
    no calen. Només un nivell, com el motor: el substitut d'una encadenada no
    en fa cap altra. Retorna {"creades": n, "esborrades": n}."""
    files = SubstitucioRepository.get_by_date(db, data)
    cal = set()
    for fila in files:
        if fila.get("tipus_absencia") == "ENCADENADA":
            continue
        substitut = (fila.get("substitut") or "").strip()
        activitat = activitat_encadenada(fila.get("tipus_substitut") or "")
        if substitut and activitat:
            cal.add((fila.get("hora"), substitut, activitat))

    resum = {"creades": 0, "esborrades": 0}
    hi_son = set()
    for fila in files:
        if fila.get("tipus_absencia") != "ENCADENADA":
            continue
        clau = (fila.get("hora"), fila.get("professor_absent"), fila.get("assignatura"))
        if clau in cal and clau not in hi_son:
            hi_son.add(clau)
        else:
            SubstitucioRepository.delete(db, int(fila["id"]))
            resum["esborrades"] += 1

    for hora, professor, activitat in sorted(cal - hi_son):
        SubstitucioRepository.create(
            db,
            {
                "data": data,
                "hora": hora,
                "professor_absent": professor,
                "assignatura": activitat,
                "grup": "",
                "tipus_absencia": "ENCADENADA",
            },
        )
        resum["creades"] += 1

    if resum["creades"] or resum["esborrades"]:
        log.debug(f"🔗 Encadenades {data}: {resum}")
    return resum
