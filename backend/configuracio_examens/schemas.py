"""Esquemes de les rutes de la configuració d'exàmens. Els cossos d'entrada
són estrictes: un camp obligatori que falta o d'un tipus que no toca, 422.
Un text buit (o de només espais, en un nom) continua sent 400 als serveis."""

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
    nom: str | None = None  # sense nom: el codi


class NouGrupRequest(BaseModel):
    codi: str


class NovaAulaRequest(BaseModel):
    codi: NomNet


class AssignacioRequest(BaseModel):
    assignatura: NomNet
    grup: str
    titular: NomNet | None = None  # buit = sense titular
    aula: NomNet | None = None  # buit = sense aula
    ordre: int = 0


class EdicioAssignacioRequest(BaseModel):
    """Només el titular i l'aula (buits = cap)."""

    titular: NomNet | None = None
    aula: NomNet | None = None


class EsborrarAssignacionsRequest(BaseModel):
    ids: list[int] = []
    tot: bool = False  # totes


class PropostaRequest(BaseModel):
    """Una proposta d'importació. Si falta l'assignatura, el grup o el nivell,
    no s'importa i es diu als avisos."""

    assignatura: NomNet | None = None
    grup: str | None = None
    nivell: str | None = None
    titular: NomNet | None = None
    aula: NomNet | None = None


class PropostaDescartadaRequest(BaseModel):
    assignatura: NomNet | None = None
    grup: str | None = None
    titular: NomNet | None = None


class ImpacteRequest(BaseModel):
    propostes: list[PropostaRequest] = []
    overwrite: bool = False  # «Sobreescriu»


class ImportacioRequest(ImpacteRequest):
    descartades: list[PropostaDescartadaRequest] = []


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
    nivells: list[str]


class AssignaturesResponse(BaseModel):
    assignatures: list[str]


class GrupsResponse(BaseModel):
    grups: list[str]


class AulesResponse(BaseModel):
    aules: list[str]


class Assignacio(BaseModel):
    id: int
    assignatura: str
    grup: str
    titular: str  # "" = sense titular
    aula: str  # "" = sense aula
    ordre: int | str  # l'API encara accepta un ordre de text (E7)


class AssignacionsResponse(BaseModel):
    assignacions: list[Assignacio]


class AssignacioObsoleta(Assignacio):
    motius: list[str]  # "grup" i/o "titular"


class AssignacionsObsoletesResponse(BaseModel):
    assignacions: list[AssignacioObsoleta]


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
    propostes: list[Proposta]
    nivells_valids: list[str]


class ImpacteResponse(BaseModel):
    """El que crearia (resum previ) o ha creat una importació."""

    nivells_creats: list[str]
    grups_creats: list[str]
    assignatures_creades: list[str]
    aules_creades: list[str]
    assignacions_creades: list[str]
    ja_existien: int
    avisos: list[str]


class ImportacioResponse(ImpacteResponse):
    success: bool
