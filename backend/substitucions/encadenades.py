"""
La regla de les substitucions encadenades, en un sol lloc: un substitut que a
aquella hora feia una activitat de les prioritats que no és a «No substituir»
(p.ex. Guàrdia) la deixa sense fer, i se'n crea una substitució (ENCADENADA).
La fan servir el motor (substitucions/assignacio.py) i, després de triar un
substitut a mà o de posar o treure absències, reconcilia_encadenades: cada
substitut que deixa una activitat que cal cobrir en té una (pendent: el
substitut no es posa sol) i la que ja no cal s'esborra.
"""

import logging
import re
from typing import Optional

from config import constants
from substitucions.repositories import SubstitucioRepository

log = logging.getLogger(__name__)


def activitat_encadenada(tipus_substitut: str) -> Optional[str]:
    """L'activitat que deixa un substitut, si cal una encadenada; si no, None.
    `tipus_substitut` és el text desat a la fila: l'activitat va entre
    parèntesis («disponible (Guàrdia)»); un alliberat («alliberat (tenia…)»)
    o una vigilància no en fan cap."""
    if not tipus_substitut:
        return None
    match = re.search(r"\(([^)]+)\)", tipus_substitut)
    if match:
        activitat = match.group(1)
    else:
        # Formats antics, sense parèntesis
        activitat = tipus_substitut.split(" (")[0]
    # Les de les prioritats que no són a «No substituir» (prioritats.services)
    return activitat if activitat in constants.GENERA_ENCADENADES else None


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
