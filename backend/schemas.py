"""
Models Pydantic per validació de dades de l'API
"""
from pydantic import BaseModel
from typing import List, Optional


class SubstitucioResponse(BaseModel):
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
    substitut: Optional[str] = None
    comentaris: Optional[str] = None
    updated_at: Optional[str] = None
    force: Optional[bool] = False


class NovaSubstitucioRequest(BaseModel):
    professor: str
    hores: List[str]
    tipus_absencia: str


class ActualitzarAbsenciesRequest(BaseModel):
    hores_absencia: Optional[List[str]] = None
    hores_servei: Optional[List[str]] = None
    updated_at_map: Optional[dict] = None
    force: Optional[bool] = False


class ConfigResponse(BaseModel):
    data_actual: str
    horari_carregat: bool
    num_professors: int
    num_hores: int
    xml_missing: Optional[bool] = False


class VigilanciaCreate(BaseModel):
    hora: str
    tipus: str
    grups: str
    aula: str
    vigilant: Optional[str] = ""
    comentaris: Optional[str] = ""
    nivell: str


class VigilanciaUpdate(BaseModel):
    hora: Optional[str] = None
    tipus: Optional[str] = None
    grups: Optional[str] = None
    aula: Optional[str] = None
    vigilant: Optional[str] = None
    comentaris: Optional[str] = None
    nivell: Optional[str] = None
    updated_at: Optional[str] = None
    force: Optional[bool] = False


class AssignmentResponse(BaseModel):
    assigned_count: int
    remaining_count: int
    message: str


class VigilanciaDisponiblesQuery(BaseModel):
    hora: str
    tipus: Optional[str] = None
    grups: Optional[str] = None
    aula: Optional[str] = None


class VigilanciaDisponiblesBatchRequest(BaseModel):
    queries: List[VigilanciaDisponiblesQuery]


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


class RenameRequest(BaseModel):
    nou_nom: str


class RenameNivellRequest(BaseModel):
    nou_codi: str


class SchedulerGenerateRequest(BaseModel):
    data_inici: str
    data_final: Optional[str] = None
    selected_dates: Optional[List[str]] = None
    dies_utilitzar: Optional[List[str]] = None
    nivells_actius: Optional[List[str]] = None
    analisi_tab: Optional[str] = None
    max_dies: int = 5
    motor: str = "v3"
    estrategia: str = "ponderada"
    epsilon: float = 0.2
    max_intents_validacio: int = 250
    max_iteracions: Optional[int] = None
    iteracions_per_temperatura: Optional[int] = None
    temperatura_inicial: Optional[float] = None
    temperatura_final: Optional[float] = None
    factor_refredament: Optional[float] = None
    random_seed: Optional[int] = None
    seeds_count: Optional[int] = None
    max_nodes: Optional[int] = None
    shuffle_top_n: Optional[int] = None


class PinItem(BaseModel):
    nom: str       # Nom de la sessió (ex: "Matemàtiques (2-BATX)")
    dia: str       # Dia de la setmana (ex: "Dilluns")
    hora: str      # Hora lectiva (ex: "09:00")


class SchedulerPinRequest(BaseModel):
    pins: List[PinItem] = []     # Sessions a fixar
    unpins: List[str] = []       # Noms de sessions a desfixar


class SchedulerDatesRequest(BaseModel):
    selected_dates: List[str]


class SchedulerRestriccionsRequest(BaseModel):
    restriccions: dict


class SchedulerPublicarOpcions(BaseModel):
    netejar_existents: bool = False
    auto_assign_titulars: bool = True


class SchedulerPublicarRequest(BaseModel):
    horari: dict  # Resultat del scheduler (result.horari)
    setmanes: List[dict]  # [{"Dilluns": "2026-02-02", "Dimarts": "2026-02-03"}, ...]
    grups_sense_classe: List[str] = []  # Grups que no tenen classe (per crear GrupAlliberat)
    durada_examen: int = 1  # Nombre d'hores lectives que dura cada examen (per GrupAlliberat)
    opcions: SchedulerPublicarOpcions = SchedulerPublicarOpcions()
    dry_run: bool = False  # Si True, calcula estadístiques sense escriure a la BD


class HorariRecalcularRequest(BaseModel):
    horari: dict  # Estructura completa de l'horari (dies -> sessions -> ...)
    data_referencia: Optional[str] = None  # Data per carregar l'XML d'horaris
    selected_dates: Optional[List[str]] = None


class SlotCostInfo(BaseModel):
    slot_key: str  # "Dilluns_09:00"
    cost: int
    breakdown: dict
    conflicte_nivell: bool
    avisos: List[str]


class HorariRecalcularResponse(BaseModel):
    cost_total: int
    cost_breakdown: dict
    slots: List[SlotCostInfo]  # Cost desglossat per slot
    valid: bool  # False si hi ha conflictes de nivell
