"""
Punts de les restriccions al cost d'un horari d'exàmens.

Una sola font per als pesos i per a la fórmula: el cost final
(`estadistiques.recalcular_cost_i_breakdown`), les penalitzacions de les
restriccions (`scoring.calcular_cost_slot`, `constraints.calcular_penalitzacio_*`)
i les incidències del validador (`validacio.ValidadorHorari`) en treuen els
punts d'aquí. Abans el validador tenia uns pesos per defecte propis (1000 en
lloc de 10000) i el límit per professor hi valia 600 on el cost en comptava 6000.
"""

from typing import NamedTuple

from scheduler_engine.defaults import DEFAULT_PES_RESTRICCIO_DURA, DEFAULT_PES_RESTRICCIO_VIOLADA


def _percent(percent) -> int:
    """La força d'una restricció, de 0 a 100 (un text o un buit valen 0)."""
    try:
        valor = int(float(percent or 0))
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, valor))


def pes_restriccio_dura(restriccions: dict) -> int:
    """Els punts d'una restricció al 100% que no és obligatòria (la base dels percentatges)."""
    return (restriccions.get("pesos_optimitzacio") or {}).get("restriccio_dura", DEFAULT_PES_RESTRICCIO_DURA)


def pes_restriccio_violada(restriccions: dict) -> int:
    """Els punts d'una restricció obligatòria (força 100) que no es compleix."""
    return (restriccions.get("pesos_optimitzacio") or {}).get("restriccio_dura_violada", DEFAULT_PES_RESTRICCIO_VIOLADA)


def punts_percentatge(base: int, percent) -> int:
    """El `percent` (0–100) de `base`, arrodonit."""
    pct = _percent(percent)
    if pct <= 0:
        return 0
    return int(round(base * (pct / 100.0)))


def punts_restriccio(restriccions: dict, percent) -> int:
    """Una restricció incomplerta amb força `percent`: si és obligatòria
    (100), `restriccio_dura_violada`; si no, el percentatge de `restriccio_dura`."""
    if _percent(percent) >= 100:
        return pes_restriccio_violada(restriccions)
    return punts_percentatge(pes_restriccio_dura(restriccions), percent)


def punts_limit_professor(restriccions: dict, pes, excedent: int) -> int:
    """Límit d'exàmens per professor: els punts de la restricció per cada
    examen de més."""
    return punts_restriccio(restriccions, pes) * excedent if excedent else 0


class IncidenciaCost(NamedTuple):
    """Una part del cost d'un horari: el concepte, els punts que hi suma i on
    és. La suma dels punts de totes les incidències és el cost total.

    concepte: clau fina del desglossament (CONCEPTES); les preferències i el
    «no el mateix dia» van a les claus antigues de `cost_breakdown`
    (CLAU_BREAKDOWN)."""

    concepte: str
    punts: int
    nom: str = ""  # l'examen (sessió)
    curs: str = ""
    dia: str = ""  # el nom del dia, com a l'horari
    hora: str = ""
    data: str = ""  # la data ISO del dia, si l'horari la porta
    amb: tuple[str, ...] = ()  # els altres exàmens que la provoquen
    professor: str = ""
    detall: str = ""


# L'ordre en què es presenten els conceptes (desglossament i pantalla)
CONCEPTES = (
    "substitucio",
    "abans_jornada",
    "despres_jornada",
    "no_treballa_dia",
    "preferencia_mateix_dia",
    "preferencia_dies_diferents",
    "preferencia_mateix_slot",
    "no_mateix_slot",
    "no_mateix_dia",
    "combinacio_no_permesa",
    "dia_hora_fix",
    "assignatures_dies_exclosos",
    "limit_dies_professor",
    "professor_estricte",
)

# Concepte → clau de `cost_breakdown` (la resposta de sempre)
CLAU_BREAKDOWN = {
    "preferencia_mateix_dia": "preferencies",
    "preferencia_dies_diferents": "preferencies",
    "preferencia_mateix_slot": "preferencies",
    "no_mateix_dia": "restriccio_dura",
}


def desglossament(incidencies) -> list[dict]:
    """El cost per concepte i per valor: [{concepte, quantitat, pes, punts}],
    només dels conceptes amb punts, en l'ordre de CONCEPTES (i de més a menys
    pes). quantitat × pes = punts; la suma de punts és el cost total."""
    grups: dict[tuple[str, int], int] = {}
    for inc in incidencies:
        if inc.punts:
            grups[(inc.concepte, inc.punts)] = grups.get((inc.concepte, inc.punts), 0) + 1
    ordre = {c: i for i, c in enumerate(CONCEPTES)}
    return [
        {"concepte": concepte, "quantitat": n, "pes": pes, "punts": n * pes}
        for (concepte, pes), n in sorted(grups.items(), key=lambda g: (ordre.get(g[0][0], len(ordre)), -g[0][1]))
    ]
