"""Reconciliació de substituts i encadenades després d’un canvi del dia."""

from horari.domain import Dia
from prioritats.repositories import NoSubstituirRepository
from substitucions.domain import DiaEscolar, substituts_no_valids
from substitucions.encadenades import reconcilia_encadenades
from substitucions.repositories import SubstitucioRepository
from substitucions.visibilitat import motiu_per_amagar


def treu_substituts_no_valids(db, data: str, dia: DiaEscolar = None) -> list:
    """Buida les assignacions invàlides i les de files amagades.
    Retorna els avisos de les assignacions invàlides de files visibles."""
    dia = dia or DiaEscolar(db, Dia.de_text(data, db.info.get("institucio")))
    no_substituir = NoSubstituirRepository.vigents_a(db, dia.data)
    amagades = {
        fila.id
        for fila in dia.files
        if (fila.substitut or fila.tipus_substitut)
        and motiu_per_amagar(fila, no_substituir, dia.alliberats.get(fila.hora, ()))
    }
    trets = substituts_no_valids(db, data, dia)
    for id_fila in sorted(amagades | {avis["id"] for avis in trets}):
        SubstitucioRepository.update(db, int(id_fila), {"substitut": "", "tipus_substitut": ""})
    reconcilia_encadenades(db, data)
    return [avis for avis in trets if avis["id"] not in amagades]
