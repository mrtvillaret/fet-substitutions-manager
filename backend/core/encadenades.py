"""
La regla de les substitucions encadenades, en un sol lloc: un substitut que a
aquella hora feia una activitat de les prioritats que no és a «No substituir»
(p.ex. Guàrdia) la deixa sense fer, i se'n crea una substitució (ENCADENADA).
La fan servir el motor (core/substitucions.py) i la tria a mà
(serveis/encadenades.py).
"""

import re
from typing import Optional

from config import constants


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
