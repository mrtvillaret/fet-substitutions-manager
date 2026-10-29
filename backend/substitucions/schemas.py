"""Schemas d'entrada i de sortida de les rutes de substitucions."""

from typing import Annotated, List, Optional

from fastapi import HTTPException
from pydantic import AfterValidator, BaseModel, Field

from noms import NomNet
from substitucions.repositories import SubstitucioRepository


class SubstitucioResponse(BaseModel):
    id: str
    hora: str
    professor_absent: str
    assignatura: str
    grup: str
    aula: Optional[str] = None
    substitut: Optional[str]
    comentaris: Optional[str] = None
    estat: str
    tipus_absencia: Optional[str] = None
    updated_at: Optional[str] = None


class SubstitucioUpdate(BaseModel):
    id: Optional[str] = None
    substitut: Optional[NomNet] = None
    comentaris: Optional[str] = None
    updated_at: Optional[str] = None
    force: Optional[bool] = False
    # Si el substitut ja fa una altra substitució a la mateixa hora: treure'l
    # d'aquella (queda pendent) i posar-lo en aquesta
    moure: Optional[bool] = False


class ActualitzarAbsenciesRequest(BaseModel):
    hores_absencia: Optional[List[str]] = None
    hores_servei: Optional[List[str]] = None
    updated_at_map: dict[str, str | None] | None = None
    force: Optional[bool] = False


def _comprova_ordre(valor):
    if valor not in SubstitucioRepository.ORDRES:
        raise HTTPException(status_code=400, detail="Ordre de les substitucions desconegut")
    return valor


# L'ordre de les substitucions dins de cada hora («curs» o «professor»),
# el mateix a la pantalla i al PDF; conserva l'error 400 actual.
OrdreSubstitucions = Annotated[str, AfterValidator(_comprova_ordre)]


# Sortides


class PendentSubstitucioResponse(BaseModel):
    professor: str
    hora: str
    assignatura: str
    grup: str
    tipus: str


class GeneracioSubstitucionsResponse(BaseModel):
    success: bool
    message: str
    total: int
    assignades: int
    pendents: int
    pendents_detall: List[PendentSubstitucioResponse]
    regenerar_tot: bool
    avisos: List[str] = Field(default_factory=list)


class SubstitutTretResponse(BaseModel):
    id: str
    hora: str
    professor_absent: str
    assignatura: str
    grup: str
    substitut: str
    motiu: str
    data: str
    classe_assignatura: Optional[str] = None
    classe_grup: Optional[str] = None


class ActualitzacioAbsenciesResponse(BaseModel):
    success: bool
    message: str
    substituts_trets: List[SubstitutTretResponse]
    hores_afegides: int
    hores_eliminades: int
    hores_totals: int
    vigilancies_desassignades: int


class FilaAlliberadaResponse(BaseModel):
    hora: str
    professor_absent: str
    assignatura: str
    grup: str


class EncadenadesResponse(BaseModel):
    creades: int
    esborrades: int


class ActualitzacioSubstitutResponse(BaseModel):
    success: bool
    message: str
    updated_at: str | None
    alliberades: List[FilaAlliberadaResponse]
    encadenades: EncadenadesResponse
    avisos: List[str] = Field(default_factory=list)


class CanviSubstitutResponse(BaseModel):
    hora: str
    professor_absent: str
    assignatura: str
    grup: str
    abans: str
    despres: str


class ReassignacioSubstitucionsResponse(BaseModel):
    success: bool
    cleared: int
    changes: List[CanviSubstitutResponse]
    message: str
    avisos: List[str] = Field(default_factory=list)


class HoresProfessorResponse(BaseModel):
    hores_amb_classe: List[str]
    hores_al_centre: List[str]


class ProfessorDisponibleResponse(BaseModel):
    professor: str
    tipus: str
    detall: str
    emoji: str
    text_display: str
    categoria: int
    color: str
    status: str
    ocupat: bool
    absent: bool
    de_baixa: bool
    ocupat_vigilancia: bool
    ja_assignat: bool


class DisponiblesResponse(BaseModel):
    disponibles: List[ProfessorDisponibleResponse]
