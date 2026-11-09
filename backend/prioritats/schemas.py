"""Entrades i sortides de les rutes de prioritats, baixes i activitats alliberables."""

from pydantic import BaseModel

from noms import NomNet


class PrioritatsRequest(BaseModel):
    """Totes les prioritats d'una vegada («Desar tot»)"""

    ordre_categories: list[list[NomNet]]  # [["Reforç", "alliberat"], ["Guàrdia", ...], ...]
    pesos: dict[NomNet, int]  # {"Reforç": 1, "Guàrdia": 6, ...}
    categories_actives: list[bool] = []  # [True, True, False, ...] - estat activa per cada categoria


class NoSubstituirRequest(BaseModel):
    # Opcional perquè sense, la resposta sigui el 400 «Assignatura requerida»
    # de sempre (prioritats.services) i no un 422. El text buit s'accepta.
    assignatura: NomNet | None = None


# Sortides


class CategoriaResponse(BaseModel):
    id: int
    nom: str
    ordre: int
    activa: bool | None = None


class CategoriesResponse(BaseModel):
    categories: list[CategoriaResponse]


class AssignaturaPrioritatResponse(BaseModel):
    id: int
    assignatura: str
    categoria_id: int
    pes: int | None = None
    ordre: int | None = None
    auto_assignada: bool | None = None


class AssignaturesPrioritatResponse(BaseModel):
    assignatures: list[AssignaturaPrioritatResponse]


class NoSubstituirResponse(BaseModel):
    assignatures: list[str]


class CreacioResponse(BaseModel):
    success: bool
    id: int
    message: str


class MissatgeResponse(BaseModel):
    success: bool
    message: str
