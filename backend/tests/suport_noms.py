"""
Sufixos únics per als noms de prova (usuaris, centres): un comptador del
procés, no l'atzar. Abans eren els primers 6 o 8 caràcters d'un uuid4, que
es podien repetir dins de la mateixa auth.db i el test fallava per
`UNIQUE constraint failed: users.username`. Cada worker de xdist és un
procés amb la seva carpeta i la seva auth.db (conftest); el pid hi és per si
dos processos compartissin mai la mateixa base de dades.
"""

import itertools
import os

_COMPTADOR = itertools.count(1)


def unic() -> str:
    """Un sufix que no es repeteix mai dins del procés (ni entre processos)."""
    return f"{os.getpid()}_{next(_COMPTADOR)}"
