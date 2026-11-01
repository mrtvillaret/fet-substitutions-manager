"""Esquemes de les rutes de la configuració d'exàmens. Els cossos d'entrada
són estrictes: un camp obligatori que falta o d'un tipus que no toca, 422.
Un text buit (o de només espais, en un nom) continua sent 400 als serveis."""

from typing import List, Optional, Union

from pydantic import BaseModel

from noms import NomNet


class RenameRequest(BaseModel):
    """El nou codi d'un grup (un codi, no un nom de la regla dels noms)."""

    nou_nom: str


class NouNomRequest(BaseModel):
    """El nou nom d'una assignatura o d'una aula (net: noms.py)."""

    nou_nom: NomNet


class NovaAssignaturaRequest(BaseModel):
    nom: NomNet  # buit (o només espais): 400


class NouNivellRequest(BaseModel):
    codi: str
    nom: Optional[str] = None  # sense nom: el codi


class NouGrupRequest(BaseModel):
    codi: str


class NovaAulaRequest(BaseModel):
    codi: NomNet


class AssignacioRequest(BaseModel):
    assignatura: NomNet
    grup: str
    titular: Optional[NomNet] = None  # buit = sense titular
    aula: Optional[NomNet] = None  # buit = sense aula
    ordre: int = 0


class EdicioAssignacioRequest(BaseModel):
    """Només el titular i l'aula (buits = cap)."""

    titular: Optional[NomNet] = None
    aula: Optional[NomNet] = None


class EsborrarAssignacionsRequest(BaseModel):
    ids: List[int] = []
    tot: bool = False  # totes


class PropostaRequest(BaseModel):
    """Una proposta d'importació. Si falta l'assignatura, el grup o el nivell,
    no s'importa i es diu als avisos."""

    assignatura: Optional[NomNet] = None
    grup: Optional[str] = None
    nivell: Optional[str] = None
    titular: Optional[NomNet] = None
    aula: Optional[NomNet] = None


class PropostaDescartadaRequest(BaseModel):
    assignatura: Optional[NomNet] = None
    grup: Optional[str] = None
    titular: Optional[NomNet] = None


class ImpacteRequest(BaseModel):
    propostes: List[PropostaRequest] = []
    overwrite: bool = False  # «Sobreescriu»


class ImportacioRequest(ImpacteRequest):
    descartades: List[PropostaDescartadaRequest] = []


class MissatgeResponse(BaseModel):
    success: bool
    message: str


class EsborratResponse(MissatgeResponse):
    assignacions: int  # quantes assignacions el fan servir (no es toquen)


class EsborratAmbAssignacionsResponse(EsborratResponse):
    assignacions_esborrades: bool  # si s'han esborrat també


class AssignacionsQueHoFanServirResponse(BaseModel):
    assignacions: int


class NivellsResponse(BaseModel):
    nivells: List[str]


class AssignaturesResponse(BaseModel):
    assignatures: List[str]


class GrupsResponse(BaseModel):
    grups: List[str]


class AulesResponse(BaseModel):
    aules: List[str]


class Assignacio(BaseModel):
    id: int
    assignatura: str
    grup: str
    titular: str  # "" = sense titular
    aula: str  # "" = sense aula
    ordre: Union[int, str]  # l'API encara accepta un ordre de text (E7)


class AssignacionsResponse(BaseModel):
    assignacions: List[Assignacio]


class AssignacioObsoleta(Assignacio):
    motius: List[str]  # "grup" i/o "titular"


class AssignacionsObsoletesResponse(BaseModel):
    assignacions: List[AssignacioObsoleta]


class CreacioResponse(BaseModel):
    success: bool
    id: int
    message: str


class EliminadesResponse(BaseModel):
    success: bool
    eliminades: int


class Proposta(BaseModel):
    assignatura: str
    grup: str
    titular: str
    aula: str
    nivell: str
    ja_existeix: bool
    descartada: bool


class PropostesResponse(BaseModel):
    propostes: List[Proposta]
    nivells_valids: List[str]


class ImpacteResponse(BaseModel):
    """El que crearia (resum previ) o ha creat una importació."""

    nivells_creats: List[str]
    grups_creats: List[str]
    assignatures_creades: List[str]
    aules_creades: List[str]
    assignacions_creades: List[str]
    ja_existien: int
    avisos: List[str]


class ImportacioResponse(ImpacteResponse):
    success: bool
