"""Una franja del planificador: el lloc on pot començar un examen.

La clau d'una franja és «<prefix>_<hora>», on el prefix és la data ISO o, sense
dates, el nom del dia («2026-04-20_09:00», «Dilluns_09:00»). Abans cada motor
i cada diagnòstic la desfeia pel seu compte (`_parse_prefix` ×4).
"""

from dataclasses import dataclass
from datetime import datetime

from scheduler_engine.core.date_mapping import DIES_CAT


def dia_de_prefix(prefix: str) -> tuple[str, str | None]:
    """(nom del dia, data ISO) d'un prefix: si és una data, el seu dia de la
    setmana i la data; si no, el prefix tal qual (ja és un nom de dia) i None."""
    try:
        return DIES_CAT[datetime.strptime(prefix, "%Y-%m-%d").weekday()], prefix
    except (TypeError, ValueError):
        return prefix, None


@dataclass(frozen=True)
class Franja:
    """Un lloc on pot començar un examen: un dia (o una data) i una hora."""

    clau: str  # «2026-04-20_09:00» o «Dilluns_09:00»: la clau de les solucions
    prefix: str  # la data ISO o, sense dates, el nom del dia
    dia: str  # nom del dia, per a les restriccions
    data_iso: str | None
    hora: str


def franja(clau: str) -> Franja:
    """La franja d'una clau «<prefix>_<hora>» (l'hora és després de l'últim «_»)."""
    idx = clau.rfind("_")
    prefix, hora = clau[:idx], clau[idx + 1 :]
    dia, data_iso = dia_de_prefix(prefix)
    return Franja(clau, prefix, dia, data_iso, hora)
