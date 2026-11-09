"""Schemas d'entrada i de sortida de les rutes de vigilàncies."""

from dataclasses import asdict
from typing import Literal

from pydantic import BaseModel, ConfigDict

from noms import NomNet
from vigilancies.files import FilaVigilancia


class VigilanciaRequest(BaseModel):
    hora: str
    tipus: str
    grups: str
    aula: NomNet
    vigilant: NomNet | None = ""
    comentaris: str | None = ""
    nivell: str | None = None
    # L'id d'una fila de la mateixa hora: la nova va just a sota (el «+» de
    # cada fila, que la copia). Sense, va al final del bloc de la seva hora.
    despres_de: str | None = None


class EdicioVigilanciaRequest(BaseModel):
    """Només els camps que es canvien. Sense `force`, cal l'`updated_at` que es
    va llegir (409 si algú l'ha modificat mentrestant)."""

    hora: str | None = None
    tipus: str | None = None
    grups: str | None = None
    aula: NomNet | None = None
    vigilant: NomNet | None = None
    comentaris: str | None = None
    nivell: str | None = None
    updated_at: str | None = None
    force: bool | None = False


class ConsultaDisponibles(BaseModel):
    vigilancia_id: str | None = None
    hora: str
    tipus: str | None = None
    grups: str | None = None
    aula: NomNet | None = None


class DisponiblesEnBlocRequest(BaseModel):
    queries: list[ConsultaDisponibles]


class TitularHoraLliure(BaseModel):
    """Un titular que no s'ha posat perquè tenia l'hora lliure: ho decideix
    qui fa les vigilàncies."""

    vigilancia_id: str
    hora: str
    grups: str
    tipus: str
    titular: str


class AssignacioResponse(BaseModel):
    assigned_count: int
    remaining_count: int
    message: str


class VigilanciaSenseTitular(BaseModel):
    """Una vigilància que la configuració d'exàmens no deixa definida.
    motiu: "cap_fila_grup" (l'assignatura té files, però cap per al grup) o
    "diversos_titulars" (s'ha assignat igualment; cal l'aula de cada professor
    a la configuració perquè quedi definit)."""

    vigilancia_id: str
    hora: str
    grups: str
    tipus: str
    motiu: str


class AssignacioTitularsResponse(AssignacioResponse):
    titulars_hora_lliure: list[TitularHoraLliure] = []
    vigilancies_sense_titular: list[VigilanciaSenseTitular] = []


class OrdreRequest(BaseModel):
    """L'ordre de les files d'una hora: els ids, de la primera a l'última."""

    hora: str
    ids: list[str]


class OrdreManualResponse(BaseModel):
    ordre_manual: bool


class ActivitatHora(BaseModel):
    """El que diu l'horari d'un professor a una hora."""

    assignatura: str
    grup: str
    aula: str


class SubstitucioHora(BaseModel):
    professor_absent: str
    assignatura: str
    grup: str
    aula: str


class VigilanciaHora(BaseModel):
    id: str
    tipus: str
    grups: str
    aula: str


class AjudaVigilantResponse(BaseModel):
    """Tot el que té un professor a una hora, per a l'ajuda en passar per
    damunt del vigilant. `estat`: absencia_coberta, absent, alliberat,
    disponible, classe, lliure o fora_de_l_horari (no és a l'horari del dia)."""

    professor: str
    hora: str
    estat: str
    activitat: ActivitatHora | None = None
    tipus_absencia: str | None = None
    substitucions: list[SubstitucioHora]
    vigilancies_hora: list[VigilanciaHora]
    vigilancies_dia: int


class Afinitat(BaseModel):
    base: str  # un nivell
    ordre: list[str]  # els nivells més propers, per ordre


class AfinitatsResponse(BaseModel):
    afinitats: list[Afinitat]


class AfinitatsDesadesResponse(BaseModel):
    success: bool
    afinitats: list[Afinitat]
    message: str


class AfinitatRequest(BaseModel):
    base: str
    ordre: list[str] = []


class AfinitatsRequest(BaseModel):
    afinitats: list[AfinitatRequest] = []


# ----------------------------------------------------------------- respostes


class ConfigVigilanciesResponse(BaseModel):
    """Nivells, grups, aules i assignatures de la configuració d'exàmens;
    professors i hores de l'horari del dia; tipus d'examen ja usats."""

    nivells: list[str]
    professors: list[str]
    hores: list[str]
    grups_per_nivell: dict[str, list[str]]
    aules: list[str]
    tipus_examens: list[str]
    tipus_per_nivell: dict[str, list[str]]


class ProfessorDisponible(BaseModel):
    """Un professor del desplegable de vigilants, amb el que fa a l'hora.
    `ordre_tipus`: 0 titular, 1 alliberat, 2 disponible, 3 classe, 4 lliure,
    5 absent, 6 de baixa."""

    value: str  # el nom
    label: str
    emoji: str
    estat: str
    info: str
    ordre_tipus: int
    categoria: int
    color: str
    ja_assignat: bool
    es_titular: bool


class DisponiblesEnBlocResponse(BaseModel):
    """{clau de la consulta («hora» o «hora|tipus|grups|aula»): professors}"""

    results: dict[str, list[ProfessorDisponible]]


class VigilanciaDelDia(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    db_id: int
    hora: str
    tipus: str
    grups: str
    aula: str
    vigilant: str
    comentaris: str
    nivell: str
    ordre: int | None
    updated_at: str | None


class VigilanciaCreada(BaseModel):
    id: str
    hora: str
    tipus: str
    grups: str
    aula: str
    vigilant: str
    comentaris: str
    nivell: str
    updated_at: str | None


class VigilanciaCreadaResponse(BaseModel):
    success: bool
    message: str
    vigilancia: VigilanciaCreada


class VigilanciaEditadaResponse(BaseModel):
    success: bool
    message: str
    updated_at: str | None


class MissatgeResponse(BaseModel):
    success: bool
    message: str


class SuccessResponse(BaseModel):
    success: bool


class NetejaResponse(BaseModel):
    success: bool
    cleared_count: int
    message: str


class OrdenacioResponse(BaseModel):
    success: bool
    sorted_count: int
    message: str


class ProblemaVigilancia(BaseModel):
    tipus: str
    gravetat: Literal["important", "avis", "informacio"]
    hora: str
    files: list[str]
    professor: str
    grup: str
    aula: str
    cobertura_efectiva: str | None
    missatge: str


def resposta_vigilancia(fila: FilaVigilancia) -> VigilanciaDelDia:
    """Un únic ID de BD al domini; dos camps històrics al contracte HTTP."""
    return VigilanciaDelDia(**{**asdict(fila), "id": str(fila.id), "db_id": int(fila.id)})
