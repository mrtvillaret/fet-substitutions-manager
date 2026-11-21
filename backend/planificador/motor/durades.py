"""Durades: hores de vigilància i hores d'examen de cada examen."""

from functools import lru_cache

from textos import normalitzar_hora


def _positiu(valor) -> int | None:
    try:
        return int(valor) if valor is not None and int(valor) > 0 else None
    except (TypeError, ValueError):
        return None


def vigilancia(nom: str | None, propies, general: int) -> int:
    return (_positiu(propies.get(nom)) if nom and propies else None) or general


def examen(nom, propies, vigilancies, general_examen, general_titular) -> int:
    """Hores que dura l'examen (una sola regla a tot arreu): la pròpia o la
    general d'examen, i mai menys que les hores de vigilància."""
    return max(vigilancia(nom, propies, general_examen), vigilancia(nom, vigilancies, general_titular))


def examen_del_problema(nom, problema) -> int:
    return examen(
        nom, problema.durades_examen, problema.durades_vigilancia, problema.durada_examen, problema.durada_titular
    )


def examen_hi_cap(nom, hora: str, problema) -> bool:
    """Un examen només pot començar a `hora` si totes les seves hores hi caben
    abans que s'acabi la graella (la jornada). Una hora fora de la graella només
    val per a exàmens d'una hora."""
    durada = examen_del_problema(nom, problema)
    return len(hores_ocupades(hora, problema.graella, durada)) >= durada


@lru_cache(maxsize=64)
def _graella_normalitzada(graella: tuple) -> tuple[str, ...]:
    return tuple(normalitzar_hora(h) for h in graella)


def hores_ocupades(hora: str, graella, durada: int) -> list[str]:
    """Les hores (normalitzades, HH:MM) que ocupa un examen de `durada` hores que comença a
    `hora`. La graella dels motors és el text cru de l'XML («9:00»), i les hores d'inici
    arriben normalitzades («09:00»): es comparen normalitzades totes dues."""
    normalitzada = _graella_normalitzada(tuple(graella))
    hora = normalitzar_hora(hora)
    if hora not in normalitzada:
        return [hora]
    inici = normalitzada.index(hora)
    return list(normalitzada[inici : min(inici + max(1, durada), len(normalitzada))])


def encavalca_amb_el_nivell(sessions, clau: str, col_locades, problema) -> bool:
    """Un examen ocupa, per al seu nivell, totes les hores que dura. Cert si
    algun examen de `sessions` començant a la franja `clau` comparteix alguna hora,
    la mateixa data, amb un examen ja col·locat del mateix nivell (`col_locades`:
    [(sessió, clau de franja)]). Les sessions d'un mateix ítem (agrupació) no
    compten entre elles."""
    if not col_locades:
        return False
    # Només calen el prefix (data) i l'hora de cada clau: partir-la és molt més
    # barat que `compartit.franja.franja`, que llegeix la data (es crida a cada node de la cerca).
    prefix, _, hora = clau.rpartition("_")
    propies = {id(s) for s in sessions}
    for sessio in sessions:
        curs = sessio.get("curs")
        hores = None
        for altra, clau_altra in col_locades:
            if id(altra) in propies or altra.get("curs") != curs:
                continue
            prefix_altra, _, hora_altra = clau_altra.rpartition("_")
            if prefix_altra != prefix:
                continue
            if hores is None:
                hores = set(hores_ocupades(hora, problema.graella, examen_del_problema(sessio.get("nom"), problema)))
            durada = examen_del_problema(altra.get("nom"), problema)
            if hores & set(hores_ocupades(hora_altra, problema.graella, durada)):
                return True
    return False
