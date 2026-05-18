"""
Helpers per construir mapes dia -> data ISO (YYYY-MM-DD).
"""

from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Optional

from scheduler_engine.core.normalitzacio import normalitzar_dia


DIES_CAT = ["Dilluns", "Dimarts", "Dimecres", "Dijous", "Divendres", "Dissabte", "Diumenge"]
_DIES_CAT = DIES_CAT  # àlies privat per compatibilitat interna


def _parse_iso_date(date_str: str) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def _normalitza_dies(dies: Optional[Iterable[str]]) -> List[str]:
    out: List[str] = []
    if not dies:
        return out
    seen = set()
    for dia in dies:
        dia_norm = normalitzar_dia(dia)
        if dia_norm and dia_norm not in seen:
            seen.add(dia_norm)
            out.append(dia_norm)
    return out


def construir_mapa_dia_data_iso(
    dies_utilitzar: Optional[Iterable[str]] = None,
    selected_dates: Optional[Iterable[str]] = None,
    data_inici_iso: Optional[str] = None,
) -> Dict[str, List[str]]:
    """
    Construeix un mapa {dia_normalitzat: [YYYY-MM-DD, ...]}.

    Prioritat:
    1) Si hi ha selected_dates, es fa servir la data real de cada dia (suporta repetits).
    2) Si no hi ha selected_dates, es fa fallback seqencial des de data_inici_iso.
    """
    dies_norm = _normalitza_dies(dies_utilitzar)
    allowed = set(dies_norm) if dies_norm else None
    mapa: Dict[str, List[str]] = {}

    parsed_dates = []
    for raw in selected_dates or []:
        dt = _parse_iso_date(raw)
        if dt:
            parsed_dates.append((dt, dt.strftime("%Y-%m-%d")))
    parsed_dates.sort(key=lambda x: x[0])

    for dt, iso in parsed_dates:
        dia_norm = normalitzar_dia(_DIES_CAT[dt.weekday()])
        if allowed and dia_norm not in allowed:
            continue
        mapa.setdefault(dia_norm, []).append(iso)

    if mapa or not data_inici_iso:
        return mapa

    base = _parse_iso_date(data_inici_iso)
    if not base:
        return mapa

    for idx, dia_norm in enumerate(dies_norm):
        mapa.setdefault(dia_norm, []).append((base + timedelta(days=idx)).strftime("%Y-%m-%d"))
    return mapa

