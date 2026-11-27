"""Valida els paràmetres comuns de les rutes.

`Data` i `DataTextual` converteixen les dates de l’API en `date`, amb el 400
històric per als textos invàlids. `DataTextual` conserva el 422 quan el cos
no porta text. `DataResposta` conserva l’esquema de sortida de tipus string.
"""

from datetime import date, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Query
from pydantic import BeforeValidator, WithJsonSchema
from pydantic_core import PydanticCustomError

from textos import normalitzar_hora


def data_iso(valor: object) -> date:
    """La data AAAA-MM-DD d'una petició; si no té aquest format, error 400."""
    try:
        if isinstance(valor, str):
            return datetime.strptime(valor, "%Y-%m-%d").date()
    except ValueError:
        pass
    raise HTTPException(status_code=400, detail="Format de data invàlid. Usa YYYY-MM-DD")


def _comprova_data(valor: object) -> date | None:
    # El nul obligatori el valida Pydantic. Un datetime ha de passar pel
    # mateix rebuig que un text amb hora.
    if valor is None or type(valor) is date:
        return valor
    return data_iso(valor)


Data = Annotated[date, BeforeValidator(_comprova_data, json_schema_input_type=str)]


def _exigeix_text_de_data(valor: object) -> object:
    if not isinstance(valor, str) and type(valor) is not date:
        raise PydanticCustomError("string_type", "Input should be a valid string")
    return valor


# Cossos JSON que tenen un 422 de camp textual per a valors d'altres tipus.
DataTextual = Annotated[Data, BeforeValidator(_exigeix_text_de_data, json_schema_input_type=str)]

# Dates de respostes que ja es declaraven com a cadenes a l'OpenAPI.
DataResposta = Annotated[date, WithJsonSchema({"type": "string"}, mode="serialization")]


# Sostre de les llistes de dates d'una petició: un any sencer. Cap pantalla
# n'envia tantes; sense sostre, una llista enorme ocuparia el servidor.
MAX_DATES = 366


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
