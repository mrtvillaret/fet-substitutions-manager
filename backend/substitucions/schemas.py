"""Schemas d'entrada i de sortida de les rutes de substitucions."""

from typing import Annotated

from fastapi import HTTPException
from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from noms import NomNet
from substitucions.files import FilaSubstitucio
from substitucions.repositories import SubstitucioRepository


class SubstitucioResponse(BaseModel):
    id: str
    hora: str
    professor_absent: str
    assignatura: str
    grup: str
    aula: str | None = None
    substitut: str | None
    comentaris: str | None = None
    estat: str
    tipus_absencia: str | None = None
    updated_at: str | None = None


class SubstitucioUpdate(BaseModel):
    id: str | None = None
    substitut: NomNet | None = None
    comentaris: str | None = None
    updated_at: str | None = None
    force: bool | None = False
    # Si el substitut ja fa una altra substitució a la mateixa hora: treure'l
    # d'aquella (queda pendent) i posar-lo en aquesta
    moure: bool | None = False


class ActualitzarAbsenciesRequest(BaseModel):
    hores_absencia: list[str] | None = None
    hores_servei: list[str] | None = None
    updated_at_map: dict[str, str | None] | None = None
    force: bool | None = False


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
    pendents_detall: list[PendentSubstitucioResponse]
    regenerar_tot: bool
    avisos: list[str] = Field(default_factory=list)


class SubstitutTretResponse(BaseModel):
    id: str
    hora: str
    professor_absent: str
    assignatura: str
    grup: str
    substitut: str
    motiu: str
    data: str
    classe_assignatura: str | None = None
    classe_grup: str | None = None


class ActualitzacioAbsenciesResponse(BaseModel):
    success: bool
    message: str
    substituts_trets: list[SubstitutTretResponse]
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
    alliberades: list[FilaAlliberadaResponse]
    encadenades: EncadenadesResponse
    avisos: list[str] = Field(default_factory=list)


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
    changes: list[CanviSubstitutResponse]
    message: str
    avisos: list[str] = Field(default_factory=list)


class HoresProfessorResponse(BaseModel):
    hores_amb_classe: list[str]
    hores_al_centre: list[str]


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
    disponibles: list[ProfessorDisponibleResponse]


class DisponiblesEnBlocRequest(BaseModel):
    hores: list[str]


class DisponiblesEnBlocResponse(BaseModel):
    results: dict[str, DisponiblesResponse]


def resposta_substitucio(sub: FilaSubstitucio) -> SubstitucioResponse:
    return SubstitucioResponse(
        id=sub.id,
        hora=sub.hora,
        professor_absent=sub.professor_absent,
        assignatura=sub.assignatura,
        grup=sub.grup,
        aula=sub.aula,
        substitut=sub.substitut,
        comentaris=sub.comentaris,
        estat="assignada" if sub.substitut else "pendent",
        tipus_absencia=sub.tipus_absencia,
        updated_at=sub.updated_at,
    )


class FilaDesadaResponse(BaseModel):
    """La mateixa fila completa que es retornava en un conflicte optimista."""

    model_config = ConfigDict(from_attributes=True)
    id: str
    data: str
    hora: str
    professor_absent: str
    assignatura: str
    grup: str
    aula: str
    substitut: str
    tipus_substitut: str
    tipus_absencia: str
    comentaris: str
    updated_at: str | None


def resposta_conflicte(files: FilaSubstitucio | list[FilaSubstitucio]):
    if isinstance(files, list):
        return [FilaDesadaResponse.model_validate(f).model_dump() for f in files]
    return FilaDesadaResponse.model_validate(files).model_dump()
