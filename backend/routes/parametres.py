"""Validació dels paràmetres comuns de les rutes."""

from datetime import date, datetime
from typing import Annotated, List, Optional

from fastapi import Depends, HTTPException, Query
from pydantic import AfterValidator

from utils.hores import normalitzar_hora


def data_iso(valor: str) -> date:
    """La data AAAA-MM-DD d'una petició; si no té aquest format, error 400."""
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Format de data invàlid. Usa YYYY-MM-DD") from None


def _comprova_data_iso(valor):
    if valor is not None:
        data_iso(valor)
    return valor


# Tipus per als paràmetres de data de les rutes: es validen sols (400 si no
# són AAAA-MM-DD o no existeixen) i arriben com a text.
#   def ruta(data: DataISO) / def ruta(data_inici: Optional[DataISO] = None)
DataISO = Annotated[str, AfterValidator(_comprova_data_iso)]


def hores_triades(
    hores: Optional[List[str]] = Query(None),
    hores_bracket: Optional[List[str]] = Query(None, alias="hores[]"),
) -> Optional[frozenset[str]]:
    """El filtre per hores d'Estadístiques i dels informes: les franges de
    l'horari triades (`hores=08:00&hores=PATI`, o `hores[]=` com les envia
    axios). Sense cap, totes."""
    triades = {normalitzar_hora(h.strip()) for h in [*(hores or []), *(hores_bracket or [])] if h and h.strip()}
    return frozenset(triades) or None


#   def ruta(hores: HoresTriades) -> frozenset de franges, o None (totes)
HoresTriades = Annotated[Optional[frozenset[str]], Depends(hores_triades)]
