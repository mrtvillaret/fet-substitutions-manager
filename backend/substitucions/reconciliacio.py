"""Reconciliació de substituts i encadenades després d’un canvi del dia."""

from substitucions.domain import DiaEscolar, substituts_no_valids
from substitucions.encadenades import reconcilia_encadenades
from substitucions.repositories import SubstitucioRepository


def treu_substituts_no_valids(db, data: str, dia: DiaEscolar = None) -> list:
    """Buida el substitut de les files de substituts_no_valids() i les retorna.
    No n'hi posa cap altre: les files queden pendents. Les encadenades, d'acord
    amb els substituts que queden (substitucions/encadenades.py): hi passen tots els
    canvis d'absències i d'alliberaments."""

    trets = substituts_no_valids(db, data, dia)
    for fila in trets:
        SubstitucioRepository.update(db, int(fila["id"]), {"substitut": "", "tipus_substitut": ""})
    reconcilia_encadenades(db, data)
    return trets
