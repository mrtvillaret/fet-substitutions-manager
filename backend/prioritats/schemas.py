"""Entrades i sortides de les rutes de prioritats, baixes i activitats alliberables."""

from pydantic import BaseModel

from noms import NomNet
from parametres import DataISO


class PrioritatsRequest(BaseModel):
    """Totes les prioritats d'una vegada («Desar tot»)"""

    ordre_categories: list[list[NomNet]]  # [["Reforç", "alliberat"], ["Guàrdia", ...], ...]
    pesos: dict[NomNet, int]  # {"Reforç": 1, "Guàrdia": 6, ...}
    categories_actives: list[bool] = []  # [True, True, False, ...] - estat activa per cada categoria


class NoSubstituirRequest(BaseModel):
    # Opcional perquè sense, la resposta sigui el 400 «Assignatura requerida»
    # de sempre (prioritats.services) i no un 422. El text buit s'accepta.
    assignatura: NomNet | None = None
    # Des de quan val (AAAA-MM-DD); sense, avui. Els dies d'abans no canvien.
    data: DataISO | None = None


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


class EntradaNoSubstituirResponse(BaseModel):
    assignatura: str
    vigent_des_de: str | None = None  # nul: des de sempre
    vigent_fins_a: str | None = None  # nul: sense final (inclòs)


class NoSubstituirResponse(BaseModel):
    assignatures: list[str]  # les vigents avui
    entrades: list[EntradaNoSubstituirResponse] = []  # les que valen avui o més endavant


class CreacioResponse(BaseModel):
    success: bool
    id: int
    message: str


class MissatgeResponse(BaseModel):
    success: bool
    message: str
