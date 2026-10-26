"""
L'ordre dels cursos dins de cada hora, el mateix a Substitucions, Vigilàncies
i els PDF: primer per l'etapa (les lletres del nivell, «1-BATX» → BATX) i
després pel número del nivell, de manera que surt 1-BATX, 2-BATX, 1-ESO,
2-ESO... Sense cap paraula fixa: serveix sigui com sigui que el centre
anomeni els nivells («1-ESO», «ESO1»). Després, pel grup.
"""

import re

from exam_import import deriva_nivell


def natural(text: str) -> list:
    """Ordre natural: «Prof 2» abans de «Prof 10», «2-ESO» abans de «10-ESO»."""
    return [(0, int(t), "") if t.isdigit() else (1, 0, t.lower()) for t in re.split(r"(\d+)", text or "") if t]


def clau_curs(grup: str, nivell: str = "") -> tuple:
    """La clau per ordenar per curs. `nivell`: el de la fila, si en té (les
    vigilàncies); si no, el del grup (exam_import.deriva_nivell: «4-ESO-A» i
    «4-ESO-AB» → 4-ESO; «1-BAT-A,1-BAT-B» → 1-BAT)."""
    grup = (grup or "").strip()
    nivell = (nivell or "").strip() or deriva_nivell(grup)
    etapa = "".join(c for c in nivell if c.isalpha()).casefold()
    numeros = re.findall(r"\d+", nivell)
    return (etapa, int(numeros[0]) if numeros else -1, natural(nivell), natural(grup))
