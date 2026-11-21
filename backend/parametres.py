"""Validació dels paràmetres comuns de les rutes."""

from datetime import date, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Query
from pydantic import AfterValidator

from textos import normalitzar_hora


def data_iso(valor: str) -> date:
    """La data AAAA-MM-DD d'una petició; si no té aquest format, error 400."""
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Format de data invàlid. Usa YYYY-MM-DD") from None


def _comprova_data_iso(valor):
    # Normalitzada (2027-3-1 → 2027-03-01): la resta del codi la compara com a
    # text i la llegeix amb date.fromisoformat, que no accepta dates sense zeros.
    return data_iso(valor).isoformat() if valor is not None else None


# Tipus per als paràmetres de data de les rutes: es validen sols (400 si no
# són AAAA-MM-DD o no existeixen) i arriben com a text AAAA-MM-DD amb zeros.
#   def ruta(data: DataISO) / def ruta(data_inici: Optional[DataISO] = None)
DataISO = Annotated[str, AfterValidator(_comprova_data_iso)]


def hores_triades(
    hores: list[str] | None = Query(None),
    hores_bracket: list[str] | None = Query(None, alias="hores[]"),
) -> frozenset[str] | None:
    """El filtre per hores d'Estadístiques i dels informes: les franges de
    l'horari triades (`hores=08:00&hores=PATI`, o `hores[]=` com les envia
    axios). Sense cap, totes."""
    triades = {normalitzar_hora(h.strip()) for h in [*(hores or []), *(hores_bracket or [])] if h and h.strip()}
    return frozenset(triades) or None


#   def ruta(hores: HoresTriades) -> frozenset de franges, o None (totes)
HoresTriades = Annotated[frozenset[str] | None, Depends(hores_triades)]
