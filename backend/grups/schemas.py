"""Schemas de les rutes de grups (entrades i respostes)."""

from typing import Dict, List, Optional

from pydantic import BaseModel

from noms import NomNet
from substitucions.schemas import SubstitutTretResponse

# ===== Entrades =====


class AlliberatsDia(BaseModel):
    grups: Dict[str, List[str]] = {}  # {hora: [grups sense classe]}
    professors: Dict[str, List[NomNet]] = {}  # {hora: [professors alliberats]}
    activitats: Dict[str, List[NomNet]] = {}  # {hora: [activitats alliberades]}
    ocupats: Dict[str, List[NomNet]] = {}  # {hora: [reforços sense alumnes que aquell dia sí en tenen]}


class CanviPeriode(BaseModel):
    tipus: str  # professor (l'únic tipus que hi ha)
    clau: str  # nom del professor
    hores: List[str]
    data: str  # a partir d'aquest dia
    alliberat: bool = True
    dia_setmana: str = ""  # el dia de la setmana (per defecte, el de `data`)


class GrupsAmagatsRequest(BaseModel):
    grups: List[NomNet]  # la llista sencera (reemplaça l'anterior)


class ActivitatsAlliberables(BaseModel):
    activitats: List[NomNet]
    per_defecte: List[NomNet] = []  # alliberades fins que tenen alumnes (p.ex. Reforç)


# ===== Respostes =====


class CanviPeriodeResponse(BaseModel):
    success: bool
    dia_setmana: str
    substituts_trets: List[SubstitutTretResponse]


class CanviDeFranja(BaseModel):
    des_de: str
    amb_alumnes: bool


class FranjaReforc(BaseModel):
    dia: str
    hora: str
    amb_alumnes: bool
    des_de: Optional[str]
    historial: List[CanviDeFranja]


class ReforcResponse(BaseModel):
    dies: List[str]
    hores: List[str]
    professors: Dict[str, List[FranjaReforc]]  # {professor: franges de la setmana}


class AlliberatPerPeriode(BaseModel):
    tipus: str
    clau: str
    des_de: str


class ProfessorDeReforc(BaseModel):
    professor: str
    amb_alumnes: bool


class DiaResponse(BaseModel):
    hores: List[str]
    grups_disponibles: List[str]
    grups_seleccionats_per_hora: Dict[str, List[str]]
    professors_per_grup_hora: Dict[str, Dict[str, List[str]]]  # {hora: {grup: [professors]}}
    professors_alliberats_per_hora: Dict[str, List[str]]
    activitats_per_hora: Dict[str, Dict[str, List[str]]]  # {activitat: {hora: [professors]}}
    activitats_seleccionades_per_hora: Dict[str, List[str]]
    periode: Dict[str, List[AlliberatPerPeriode]]  # {hora: alliberats per període}
    dia_setmana: str
    activitats_per_defecte: List[str]
    reforcs_per_hora: Dict[str, Dict[str, List[ProfessorDeReforc]]]  # {activitat: {hora: [...]}}
    ocupats_per_hora: Dict[str, List[str]]


class DiaDesatResponse(BaseModel):
    success: bool
    substituts_trets: List[SubstitutTretResponse]
    message: str
    total_hores: int
    total_grups: int
    total_professors: int


class GrupsAmagatsResponse(BaseModel):
    grups: List[str]


class GrupsAmagatsDesatsResponse(BaseModel):
    success: bool
    total: int


class ActivitatsAlliberablesResponse(BaseModel):
    activitats: List[str]
    per_defecte: List[str]
    disponibles: List[str]


class ActivitatsAlliberablesDesadesResponse(BaseModel):
    success: bool
    activitats: List[str]
    per_defecte: List[str]
