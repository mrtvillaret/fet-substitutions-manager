"""Schemas d'entrada i de sortida de les rutes de vigilàncies."""

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel

from noms import NomNet


class VigilanciaRequest(BaseModel):
    hora: str
    tipus: str
    grups: str
    aula: NomNet
    vigilant: Optional[NomNet] = ""
    comentaris: Optional[str] = ""
    nivell: Optional[str] = None
    # L'id d'una fila de la mateixa hora: la nova va just a sota (el «+» de
    # cada fila, que la copia). Sense, va al final del bloc de la seva hora.
    despres_de: Optional[str] = None


class EdicioVigilanciaRequest(BaseModel):
    """Només els camps que es canvien. Sense `force`, cal l'`updated_at` que es
    va llegir (409 si algú l'ha modificat mentrestant)."""

    hora: Optional[str] = None
    tipus: Optional[str] = None
    grups: Optional[str] = None
    aula: Optional[NomNet] = None
    vigilant: Optional[NomNet] = None
    comentaris: Optional[str] = None
    nivell: Optional[str] = None
    updated_at: Optional[str] = None
    force: Optional[bool] = False


class ConsultaDisponibles(BaseModel):
    vigilancia_id: str | None = None
    hora: str
    tipus: Optional[str] = None
    grups: Optional[str] = None
    aula: Optional[NomNet] = None


class DisponiblesEnBlocRequest(BaseModel):
    queries: List[ConsultaDisponibles]


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
    titulars_hora_lliure: List[TitularHoraLliure] = []
    vigilancies_sense_titular: List[VigilanciaSenseTitular] = []


class OrdreRequest(BaseModel):
    """L'ordre de les files d'una hora: els ids, de la primera a l'última."""

    hora: str
    ids: List[str]


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
    activitat: Optional[ActivitatHora] = None
    tipus_absencia: Optional[str] = None
    substitucions: List[SubstitucioHora]
    vigilancies_hora: List[VigilanciaHora]
    vigilancies_dia: int


class Afinitat(BaseModel):
    base: str  # un nivell
    ordre: List[str]  # els nivells més propers, per ordre


class AfinitatsResponse(BaseModel):
    afinitats: List[Afinitat]


class AfinitatsDesadesResponse(BaseModel):
    success: bool
    afinitats: List[Afinitat]
    message: str


class AfinitatRequest(BaseModel):
    base: str
    ordre: List[str] = []


class AfinitatsRequest(BaseModel):
    afinitats: List[AfinitatRequest] = []


# ----------------------------------------------------------------- respostes


class ConfigVigilanciesResponse(BaseModel):
    """Nivells, grups, aules i assignatures de la configuració d'exàmens;
    professors i hores de l'horari del dia; tipus d'examen ja usats."""

    nivells: List[str]
    professors: List[str]
    hores: List[str]
    grups_per_nivell: Dict[str, List[str]]
    aules: List[str]
    tipus_examens: List[str]
    tipus_per_nivell: Dict[str, List[str]]


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

    results: Dict[str, List[ProfessorDisponible]]


class VigilanciaDelDia(BaseModel):
    id: str
    db_id: int
    hora: str
    tipus: str
    grups: str
    aula: str
    vigilant: str
    comentaris: str
    nivell: str
    ordre: Optional[int]
    updated_at: Optional[str]


class VigilanciaCreada(BaseModel):
    id: str
    hora: str
    tipus: str
    grups: str
    aula: str
    vigilant: str
    comentaris: str
    nivell: str
    updated_at: Optional[str]


class VigilanciaCreadaResponse(BaseModel):
    success: bool
    message: str
    vigilancia: VigilanciaCreada


class VigilanciaEditadaResponse(BaseModel):
    success: bool
    message: str
    updated_at: Optional[str]


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
