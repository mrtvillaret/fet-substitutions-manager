"""Peticions i respostes de l'API del planificador d'exàmens."""

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from noms import NomNet
from parametres import DataISO

# ---------------------------------------------------------------- peticions
# Un camp d'un tipus que no toca, 422; una data que no és AAAA-MM-DD, 400
# (DataISO). Els camps que no hi són s'ignoren, com a la resta de l'API
# (la pantalla envia a generar tots els paràmetres dels motors).

TipusCost = Literal["substitucio", "abans_jornada", "despres_jornada", "no_treballa_dia"]


class SchedulerGenerateRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    data_inici: DataISO
    data_final: Optional[DataISO] = None
    selected_dates: Optional[List[DataISO]] = None
    dies_utilitzar: Optional[List[str]] = None
    nivells_actius: Optional[List[str]] = None
    max_dies: int = Field(default=5, gt=0)
    motor: str = "v3"
    estrategia: str = "ponderada"
    epsilon: float = Field(default=0.2, ge=0, le=1)
    max_intents_validacio: int = Field(default=250, gt=0)
    max_iteracions: Optional[int] = Field(default=None, ge=0)
    iteracions_per_temperatura: Optional[int] = Field(default=None, gt=0)
    temperatura_inicial: Optional[float] = Field(default=None, ge=0)
    temperatura_final: Optional[float] = Field(default=None, ge=0)
    factor_refredament: Optional[float] = Field(default=None, ge=0)
    random_seed: Optional[int] = None
    seeds_count: Optional[int] = Field(default=None, le=50)
    max_nodes: Optional[int] = Field(default=None, ge=0, le=10_000_000)
    shuffle_top_n: Optional[int] = None

    @model_validator(mode="after")
    def comprova_coherencia(self):
        if self.data_final and self.data_final < self.data_inici:
            raise ValueError("La data final no pot ser anterior a la inicial")
        return self


class MarquesHora(BaseModel):
    a: bool = False  # sense classe (alliberada)
    i: bool = False  # hi pot començar un examen


class AlliberamentsNivell(BaseModel):
    """Les hores sense classe d'un nivell marcades al calendari."""

    durada: Optional[int] = Field(default=None, gt=0)
    dates: List[DataISO] = []
    config: Dict[DataISO, Dict[str, MarquesHora]] = {}  # data → hora → marques


class DuradaGrup(BaseModel):
    """Uns exàmens amb una durada pròpia (hores del titular i de l'examen)."""

    nom: str = ""
    assignatures: List[NomNet] = []  # «Assignatura (nivell)»
    durada: int = Field(default=1, gt=0)
    durada_examen: Optional[int] = Field(default=None, gt=0)


class ConfigPlanificadorRequest(BaseModel):
    """Només es desen els camps que hi són."""

    durada_titular: int = Field(default=None, gt=0)
    durada_examen: int = Field(default=None, gt=0)
    nivells_actius: List[str] = None
    alliberaments_per_nivell: Dict[str, AlliberamentsNivell] = None
    durades_grups: List[DuradaGrup] = None


class PinItem(BaseModel):
    nom: NomNet  # Nom de la sessió (ex: "Matemàtiques (2-BATX)")
    dia: str  # Dia de la setmana (ex: "Dilluns")
    hora: str  # Hora lectiva (ex: "09:00")


class SchedulerPinRequest(BaseModel):
    pins: List[PinItem] = []  # Sessions a fixar
    unpins: List[NomNet] = []  # Noms de sessions a desfixar


class SchedulerDatesRequest(BaseModel):
    selected_dates: List[DataISO]


class CostosProfessorsRequest(BaseModel):
    globals: Dict[TipusCost, int] = {}
    individuals: Dict[NomNet, Dict[TipusCost, int]] = {}


class Preferencia(BaseModel):
    assignatures: List[NomNet] = []  # exàmens, «Assignatura (nivell)»
    pes: int = 75


class Preferencies(BaseModel):
    mateix_dia: List[Preferencia] = []
    dies_diferents: List[Preferencia] = []
    mateix_slot: List[Preferencia] = []


class _RestriccioInterna(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class AgrupacioRestriccio(_RestriccioInterna):
    nom: str = ""
    assignatures: List[NomNet]
    pes: int = 100


class SlotProhibit(_RestriccioInterna):
    assignatures: List[NomNet]
    dia: str = ""
    hora: str = ""


class LimitDiesProfessor(_RestriccioInterna):
    assignatures: List[NomNet]
    dies_restringits: List[str] = []
    max_examens: int = 0
    pes_penalitzacio: int = 0


class DiesExclosos(_RestriccioInterna):
    assignatures: List[NomNet]
    dies: List[str]
    pes: int = 100


class RestriccionsDures(_RestriccioInterna):
    # També s'admeten les llistes històriques que llegeixen els motors.
    no_mateix_dia: List[List[NomNet] | NomNet] = []
    no_mateix_slot: Dict[str, List[NomNet] | int] = {}
    mateix_slot: List[AgrupacioRestriccio | List[NomNet]] = []
    assignatures_dia_fix: Dict[NomNet, str | int] = {}
    assignatures_hora_fix: Dict[NomNet, str | int] = {}
    assignatures_slot_prohibit: List[SlotProhibit] = []
    professors_horari_estricte: List[NomNet] = []
    professors_limit_dies_especifics: Dict[NomNet, LimitDiesProfessor | int] = {}
    slots_valids_per_nivell: Dict[str, Dict[str, List[str]] | int] = {}
    combinacions_permeses: List[AgrupacioRestriccio | List[NomNet]] = []
    assignatures_dies_exclosos: List[DiesExclosos] = []

    @field_validator(
        "no_mateix_slot",
        "assignatures_dia_fix",
        "assignatures_hora_fix",
        "professors_limit_dies_especifics",
        "slots_valids_per_nivell",
        mode="before",
    )
    @classmethod
    def comprova_pesos_separats(cls, valor):
        # `_pes_<clau>` és un enter; la resta de claus tenen la forma del tipus.
        # Una unió sola acceptaria un enter on s'espera una llista o un dia.
        if isinstance(valor, dict):
            for clau, contingut in valor.items():
                if isinstance(clau, str) and clau.startswith("_pes_"):
                    if type(contingut) is not int:
                        raise ValueError("El pes separat ha de ser un enter")
                elif type(contingut) is int:
                    raise ValueError("Un enter només és vàlid en una clau de pes _pes_…")
        return valor


class Restriccions(BaseModel):
    """Només es desen els camps que hi són (desar-les les substitueix totes)."""

    restriccions_dures: RestriccionsDures = Field(default_factory=RestriccionsDures)
    preferencies: Preferencies = Preferencies()
    pesos_optimitzacio: Dict[str, int] = {}
    costos_professors: Optional[CostosProfessorsRequest] = None
    pesos_percentatge: Dict[str, int] = {}


class SchedulerRestriccionsRequest(BaseModel):
    restriccions: Restriccions


class SchedulerPublicarOpcions(BaseModel):
    netejar_existents: bool = False
    auto_assign_titulars: bool = True


class _ModelHorari(BaseModel):
    # La pantalla conserva metadades del motor, anàlisis i identificadors
    # d'edició (p. ex. _uid). No es perden en validar ni en tornar al domini.
    model_config = ConfigDict(extra="allow")


class ExamenHorari(_ModelHorari):
    professor: Optional[NomNet] = None
    grup: Optional[str] = None
    assignatura: Optional[NomNet] = None
    aula: Optional[NomNet] = None


class SessioHorari(_ModelHorari):
    id: Optional[str] = None
    nom: Optional[str] = None
    nom_base: Optional[str] = None
    curs: Optional[str] = None
    examens: List[ExamenHorari] = Field(default_factory=list)


class FranjaHorari(_ModelHorari):
    hora: str
    sessions_simultanees: List[SessioHorari] = Field(default_factory=list)


class DiaHorari(_ModelHorari):
    dia: str
    data: Optional[DataISO] = None
    sessions: List[FranjaHorari] = Field(default_factory=list)


class HorariPlanificat(_ModelHorari):
    dies: List[DiaHorari] = Field(default_factory=list)
    metadata: Optional[dict] = None


class SchedulerPublicarRequest(BaseModel):
    horari: HorariPlanificat  # Resultat del scheduler (result.horari)
    setmanes: List[Dict[str, DataISO]]  # [{"Dilluns": "2026-02-02", "Dimarts": "2026-02-03"}, ...]
    grups_sense_classe: List[str] = []  # Grups que no tenen classe (per crear GrupAlliberat)
    opcions: SchedulerPublicarOpcions = SchedulerPublicarOpcions()
    dry_run: bool = False  # Si True, calcula estadístiques sense escriure a la BD


class HorariRecalcularRequest(BaseModel):
    horari: HorariPlanificat  # Estructura completa de l'horari
    data_referencia: Optional[DataISO] = None  # Data per carregar l'XML d'horaris
    selected_dates: Optional[List[DataISO]] = None


# ---------------------------------------------------------------- respostes


class ExitResponse(BaseModel):
    success: bool


class MotorsResponse(BaseModel):
    motors: List[dict]  # id, etiqueta, paràmetres i valors per defecte de cada motor


class ConfigPlanificadorResponse(BaseModel):
    nivells: List[str]
    hores_examen: list
    durada_titular: int
    durada_examen: int
    nivells_seleccionats: list
    hores_per_nivell: dict
    alliberaments_per_nivell: dict
    durades_grups: list


class RestriccionsResponse(BaseModel):
    restriccions: dict
    assignatures_inexistents: List[str]


class AssignaturesTretesResponse(BaseModel):
    trets: List[str]
    restriccions: dict


class CostosProfessors(BaseModel):
    globals: Dict[str, int]
    individuals: Dict[str, Dict[str, int]]


class CostosProfessorsResponse(BaseModel):
    costos_professors: CostosProfessors


class DatesResponse(BaseModel):
    selected_dates: list


class HorariPlanificacioResponse(BaseModel):
    data_referencia: str
    sense_dates: bool
    versio_des_de: Optional[str]
    canvi_horari: Optional[str]  # data en què comença un altre horari dins les dates


class CursAnterior(BaseModel):
    cursos: List[str]
    curs_actual: str


class CursDatesResponse(BaseModel):
    curs_anterior: Optional[CursAnterior]


class GeneracioResponse(BaseModel):
    """Viable: dies_utilitzar i horari; no viable: status «ok» i l'horari amb
    el motiu a les metadades."""

    horari: Optional[dict]
    dies_utilitzar: Optional[list] = None
    status: Optional[str] = None


class AnalisiResponse(BaseModel):
    per_slots: str
    per_sessio: str
    professors_slot: str


class PublicacioResponse(BaseModel):
    success: bool
    dry_run: bool
    dates_processades: List[str]
    vigilancies_creades: int
    vigilancies_actualitzades: int
    vigilancies_sense_canvis: int
    vigilancies_eliminades: int
    grups_alliberats_creats: int
    titulars_assignats: int
    errors: Optional[List[str]]
    avisos: Optional[list]


class CostFranja(BaseModel):
    slot_key: str  # data (o dia) i hora: "2026-04-20_09:00"
    cost: int | float
    breakdown: dict
    conflicte_nivell: bool
    avisos: List[str]
    item_avisos: Dict[str, List[str]]  # els avisos de cada examen (per _uid i per item_id)


class RecalculResponse(BaseModel):
    cost_total: int | float
    cost_breakdown: dict
    cost_breakdown_details: dict
    slots: List[CostFranja]
    valid: bool  # False si hi ha conflictes de nivell
    logs: List[str]
    stats: dict
