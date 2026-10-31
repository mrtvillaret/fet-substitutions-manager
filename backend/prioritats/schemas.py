"""Entrades i sortides de les rutes de prioritats, baixes i activitats alliberables."""

from typing import Dict, List, Optional

from pydantic import BaseModel

from noms import NomNet


class PrioritatsRequest(BaseModel):
    """Totes les prioritats d'una vegada («Desar tot»)"""

    ordre_categories: List[List[NomNet]]  # [["Reforç", "alliberat"], ["Guàrdia", ...], ...]
    pesos: Dict[NomNet, int]  # {"Reforç": 1, "Guàrdia": 6, ...}
    categories_actives: List[bool] = []  # [True, True, False, ...] - estat activa per cada categoria


class NoSubstituirRequest(BaseModel):
    # Opcional perquè sense, la resposta sigui el 400 «Assignatura requerida»
    # de sempre (prioritats.services) i no un 422. El text buit s'accepta.
    assignatura: Optional[NomNet] = None


# Sortides


class CategoriaResponse(BaseModel):
    id: int
    nom: str
    ordre: int
    activa: Optional[bool] = None


class CategoriesResponse(BaseModel):
    categories: List[CategoriaResponse]


class AssignaturaPrioritatResponse(BaseModel):
    id: int
    assignatura: str
    categoria_id: int
    pes: Optional[int] = None
    ordre: Optional[int] = None
    auto_assignada: Optional[bool] = None


class AssignaturesPrioritatResponse(BaseModel):
    assignatures: List[AssignaturaPrioritatResponse]


class NoSubstituirResponse(BaseModel):
    assignatures: List[str]


class CreacioResponse(BaseModel):
    success: bool
    id: int
    message: str


class MissatgeResponse(BaseModel):
    success: bool
    message: str
