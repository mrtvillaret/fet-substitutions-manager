"""
Helpers per construir mapes dia -> data ISO (YYYY-MM-DD).
"""

from collections.abc import Iterable
from datetime import date, datetime, timedelta

from planificador.compartit.normalitzacio import normalitzar_dia

DIES_CAT = ["Dilluns", "Dimarts", "Dimecres", "Dijous", "Divendres", "Dissabte", "Diumenge"]


def data_calendari(valor: object) -> date | None:
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        try:
            return datetime.strptime(valor, "%Y-%m-%d").date()
        except ValueError:
            pass
    return None


def _normalitza_dies(dies: Iterable[str] | None) -> list[str]:
    out: list[str] = []
    if not dies:
        return out
    seen = set()
    for dia in dies:
        dia_norm = normalitzar_dia(dia)
        if dia_norm and dia_norm not in seen:
            seen.add(dia_norm)
            out.append(dia_norm)
    return out


def construir_mapa_dia_data(
    dies_utilitzar: Iterable[str] | None = None,
    selected_dates: Iterable[date] | None = None,
    data_inici: date | None = None,
) -> dict[str, list[date]]:
    """Mapa de dies a dates, amb duplicats i fallback seqüencial des de l’inici."""
    dies_norm = _normalitza_dies(dies_utilitzar)
    allowed = set(dies_norm)
    mapa: dict[str, list[date]] = {}
    for data in sorted(selected_dates or ()):
        dia = normalitzar_dia(DIES_CAT[data.weekday()])
        if not allowed or dia in allowed:
            mapa.setdefault(dia, []).append(data)

    if not mapa and data_inici:
        for idx, dia in enumerate(dies_norm):
            mapa.setdefault(dia, []).append(data_inici + timedelta(days=idx))
    return mapa


def mapa_per_al_motor(mapa: dict[str, list[date]]) -> dict[str, list[str]]:
    return {dia: [data.strftime("%Y-%m-%d") for data in dates] for dia, dates in mapa.items()}


def construir_mapa_dia_data_iso(
    dies_utilitzar: Iterable[str] | None = None,
    selected_dates: Iterable[str] | None = None,
    data_inici_iso: str | None = None,
) -> dict[str, list[str]]:
    """Entrada i sortida textuals que fa servir el motor."""
    dates = [data for valor in selected_dates or () if (data := data_calendari(valor))]
    return mapa_per_al_motor(construir_mapa_dia_data(dies_utilitzar, dates, data_calendari(data_inici_iso)))
