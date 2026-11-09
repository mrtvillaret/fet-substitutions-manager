"""Schemas de les rutes de grups (entrades i respostes)."""

from pydantic import BaseModel

from noms import NomNet
from substitucions.schemas import SubstitutTretResponse

# ===== Entrades =====


class AlliberatsDia(BaseModel):
    grups: dict[str, list[str]] = {}  # {hora: [grups sense classe]}
    professors: dict[str, list[NomNet]] = {}  # {hora: [professors alliberats]}
    activitats: dict[str, list[NomNet]] = {}  # {hora: [activitats alliberades]}
    ocupats: dict[str, list[NomNet]] = {}  # {hora: [reforços sense alumnes que aquell dia sí en tenen]}


class CanviPeriode(BaseModel):
    tipus: str  # professor (l'únic tipus que hi ha)
    clau: str  # nom del professor
    hores: list[str]
    data: str  # a partir d'aquest dia
    alliberat: bool = True
    dia_setmana: str = ""  # el dia de la setmana (per defecte, el de `data`)


class GrupsAmagatsRequest(BaseModel):
    grups: list[NomNet]  # la llista sencera (reemplaça l'anterior)


class ActivitatsAlliberables(BaseModel):
    activitats: list[NomNet]
    per_defecte: list[NomNet] = []  # alliberades fins que tenen alumnes (p.ex. Reforç)


# ===== Respostes =====


class CanviPeriodeResponse(BaseModel):
    success: bool
    dia_setmana: str
    substituts_trets: list[SubstitutTretResponse]


class CanviDeFranja(BaseModel):
    des_de: str
    amb_alumnes: bool


class FranjaReforc(BaseModel):
    dia: str
    hora: str
    amb_alumnes: bool
    des_de: str | None
    historial: list[CanviDeFranja]


class ReforcResponse(BaseModel):
    dies: list[str]
    hores: list[str]
    professors: dict[str, list[FranjaReforc]]  # {professor: franges de la setmana}


class AlliberatPerPeriode(BaseModel):
    tipus: str
    clau: str
    des_de: str


class ProfessorDeReforc(BaseModel):
    professor: str
    amb_alumnes: bool


class DiaResponse(BaseModel):
    hores: list[str]
    grups_disponibles: list[str]
    grups_seleccionats_per_hora: dict[str, list[str]]
    professors_per_grup_hora: dict[str, dict[str, list[str]]]  # {hora: {grup: [professors]}}
    professors_alliberats_per_hora: dict[str, list[str]]
    activitats_per_hora: dict[str, dict[str, list[str]]]  # {activitat: {hora: [professors]}}
    activitats_seleccionades_per_hora: dict[str, list[str]]
    periode: dict[str, list[AlliberatPerPeriode]]  # {hora: alliberats per període}
    dia_setmana: str
    activitats_per_defecte: list[str]
    reforcs_per_hora: dict[str, dict[str, list[ProfessorDeReforc]]]  # {activitat: {hora: [...]}}
    ocupats_per_hora: dict[str, list[str]]


class DiaDesatResponse(BaseModel):
    success: bool
    substituts_trets: list[SubstitutTretResponse]
    message: str
    total_hores: int
    total_grups: int
    total_professors: int


class GrupsAmagatsResponse(BaseModel):
    grups: list[str]


class GrupsAmagatsDesatsResponse(BaseModel):
    success: bool
    total: int


class ActivitatsAlliberablesResponse(BaseModel):
    activitats: list[str]
    per_defecte: list[str]
    disponibles: list[str]


class ActivitatsAlliberablesDesadesResponse(BaseModel):
    success: bool
    activitats: list[str]
    per_defecte: list[str]


class Abreviatura(BaseModel):
    id: int
    grups_originals: str
    abreviatura: str


class AbreviaturesResponse(BaseModel):
    abreviatures: list[Abreviatura]


class AbreviaturaCreadaResponse(BaseModel):
    success: bool
    id: int
    message: str


class AbreviaturaDesadaResponse(BaseModel):
    success: bool
    message: str


class NovaAbreviaturaRequest(BaseModel):
    grups_originals: str  # p. ex. "1-BAT-A,1-BAT-B"
    abreviatura: str  # p. ex. "1-BAT-AB"


class EdicioAbreviaturaRequest(BaseModel):
    """Els camps que no hi són es mantenen."""

    grups_originals: str | None = None
    abreviatura: str | None = None
