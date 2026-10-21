"""Validació dels paràmetres comuns de les rutes."""

from datetime import date, datetime
from typing import Annotated

from fastapi import HTTPException
from pydantic import AfterValidator


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
