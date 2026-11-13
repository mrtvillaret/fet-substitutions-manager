"""Peticions i respostes de l'API del planificador d'exàmens."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from noms import NomNet
from parametres import DataISO
from scheduler_engine.defaults import SEGONS_MAXIMS_LIMIT, SEGONS_MAXIMS_PER_DEFECTE

# ---------------------------------------------------------------- peticions
# Un camp d'un tipus que no toca, 422; una data que no és AAAA-MM-DD, 400
# (DataISO). Els camps que no hi són s'ignoren, com a la resta de l'API
# (la pantalla envia a generar tots els paràmetres dels motors). Una petició
# antiga amb `epsilon` (tret: no feia res) tampoc no falla.

TipusCost = Literal["substitucio", "abans_jornada", "despres_jornada", "no_treballa_dia"]


class SchedulerGenerateRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    data_inici: DataISO
    data_final: DataISO | None = None
    selected_dates: list[DataISO] | None = None
    dies_utilitzar: list[str] | None = None
    nivells_actius: list[str] | None = None
    max_dies: int = Field(default=5, gt=0)
    motor: str = "v3"
    estrategia: str = "ponderada"
    # Sostre = el màxim de la pantalla; a més, el motor s'atura al temps màxim (segons_maxims)
    max_intents_validacio: int = Field(default=250, gt=0, le=5000)
    max_iteracions: int | None = Field(default=None, ge=0)
    iteracions_per_temperatura: int | None = Field(default=None, gt=0)
    temperatura_inicial: float | None = Field(default=None, ge=0)
    temperatura_final: float | None = Field(default=None, ge=0)
    factor_refredament: float | None = Field(default=None, ge=0)
    random_seed: int | None = None
    seeds_count: int | None = Field(default=None, le=50)
    max_nodes: int | None = Field(default=None, ge=0, le=10_000_000)
    shuffle_top_n: int | None = None
    # Temps màxim de la cerca (tots tres motors); el sostre el fixen els temps
    # límit de la cadena de producció (DESPLEGAMENT.md)
    segons_maxims: int = Field(default=SEGONS_MAXIMS_PER_DEFECTE, ge=1, le=SEGONS_MAXIMS_LIMIT)

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

    durada: int | None = Field(default=None, gt=0)
    dates: list[DataISO] = []
    config: dict[DataISO, dict[str, MarquesHora]] = {}  # data → hora → marques


class DuradaGrup(BaseModel):
    """Uns exàmens amb una durada pròpia (hores del titular i de l'examen)."""

    nom: str = ""
    assignatures: list[NomNet] = []  # «Assignatura (nivell)»
    durada: int = Field(default=1, gt=0)
    durada_examen: int | None = Field(default=None, gt=0)


class ConfigPlanificadorRequest(BaseModel):
    """Només es desen els camps que hi són."""

    durada_titular: int = Field(default=None, gt=0)
    durada_examen: int = Field(default=None, gt=0)
    nivells_actius: list[str] = None
    alliberaments_per_nivell: dict[str, AlliberamentsNivell] = None
    durades_grups: list[DuradaGrup] = None


class PinItem(BaseModel):
    nom: NomNet  # Nom de la sessió (ex: "Matemàtiques (2-BATX)")
    dia: str  # Dia de la setmana (ex: "Dilluns")
    hora: str  # Hora lectiva (ex: "09:00")


class SchedulerPinRequest(BaseModel):
    pins: list[PinItem] = []  # Sessions a fixar
    unpins: list[NomNet] = []  # Noms de sessions a desfixar


class SchedulerDatesRequest(BaseModel):
    selected_dates: list[DataISO]


class CostosProfessorsRequest(BaseModel):
    globals: dict[TipusCost, int] = {}
    individuals: dict[NomNet, dict[TipusCost, int]] = {}


class Preferencia(BaseModel):
    assignatures: list[NomNet] = []  # exàmens, «Assignatura (nivell)»
    pes: int = 75


class Preferencies(BaseModel):
    mateix_dia: list[Preferencia] = []
    dies_diferents: list[Preferencia] = []
    mateix_slot: list[Preferencia] = []


class _RestriccioInterna(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class AgrupacioRestriccio(_RestriccioInterna):
    nom: str = ""
    assignatures: list[NomNet]
    pes: int = 100


class SlotProhibit(_RestriccioInterna):
    assignatures: list[NomNet]
    dia: str = ""
    hora: str = ""


class LimitDiesProfessor(_RestriccioInterna):
    assignatures: list[NomNet]
    dies_restringits: list[str] = []
    max_examens: int = 0
    pes_penalitzacio: int = 0


class DiesExclosos(_RestriccioInterna):
    assignatures: list[NomNet]
    dies: list[str]
    pes: int = 100


class RestriccionsDures(_RestriccioInterna):
    # També s'admeten les llistes històriques que llegeixen els motors.
    no_mateix_dia: list[list[NomNet] | NomNet] = []
    no_mateix_slot: dict[str, list[NomNet] | int] = {}
    mateix_slot: list[AgrupacioRestriccio | list[NomNet]] = []
    assignatures_dia_fix: dict[NomNet, str | int] = {}
    assignatures_hora_fix: dict[NomNet, str | int] = {}
    assignatures_slot_prohibit: list[SlotProhibit] = []
    professors_horari_estricte: list[NomNet] = []
    professors_limit_dies_especifics: dict[NomNet, LimitDiesProfessor | int] = {}
    slots_valids_per_nivell: dict[str, dict[str, list[str]] | int] = {}
    combinacions_permeses: list[AgrupacioRestriccio | list[NomNet]] = []
    assignatures_dies_exclosos: list[DiesExclosos] = []

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
    pesos_optimitzacio: dict[str, int] = {}
    costos_professors: CostosProfessorsRequest | None = None
    pesos_percentatge: dict[str, int] = {}


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
    professor: NomNet | None = None
    grup: str | None = None
    assignatura: NomNet | None = None
    aula: NomNet | None = None


class SessioHorari(_ModelHorari):
    id: str | None = None
    nom: str | None = None
    nom_base: str | None = None
    curs: str | None = None
    examens: list[ExamenHorari] = Field(default_factory=list)


class FranjaHorari(_ModelHorari):
    hora: str
    sessions_simultanees: list[SessioHorari] = Field(default_factory=list)


class DiaHorari(_ModelHorari):
    dia: str
    data: DataISO | None = None
    sessions: list[FranjaHorari] = Field(default_factory=list)


class HorariPlanificat(_ModelHorari):
    dies: list[DiaHorari] = Field(default_factory=list)
    metadata: dict | None = None


class SchedulerPublicarRequest(BaseModel):
    horari: HorariPlanificat  # Resultat del scheduler (result.horari)
    setmanes: list[dict[str, DataISO]]  # [{"Dilluns": "2026-02-02", "Dimarts": "2026-02-03"}, ...]
    grups_sense_classe: list[str] = []  # Grups que no tenen classe (per crear GrupAlliberat)
    opcions: SchedulerPublicarOpcions = SchedulerPublicarOpcions()
    dry_run: bool = False  # Si True, calcula estadístiques sense escriure a la BD


class HorariRecalcularRequest(BaseModel):
    horari: HorariPlanificat  # Estructura completa de l'horari
    data_referencia: DataISO | None = None  # Data per carregar l'XML d'horaris
    selected_dates: list[DataISO] | None = None


# ---------------------------------------------------------------- respostes


class ExitResponse(BaseModel):
    success: bool


class MotorsResponse(BaseModel):
    motors: list[dict]  # id, etiqueta, paràmetres i valors per defecte de cada motor


class ConfigPlanificadorResponse(BaseModel):
    nivells: list[str]
    hores_examen: list
    durada_titular: int
    durada_examen: int
    nivells_seleccionats: list
    hores_per_nivell: dict
    alliberaments_per_nivell: dict
    durades_grups: list


class RestriccionsResponse(BaseModel):
    restriccions: dict
    assignatures_inexistents: list[str]


class AssignaturesTretesResponse(BaseModel):
    trets: list[str]
    restriccions: dict


class CostosProfessors(BaseModel):
    globals: dict[str, int]
    individuals: dict[str, dict[str, int]]


class CostosProfessorsResponse(BaseModel):
    costos_professors: CostosProfessors


class DatesResponse(BaseModel):
    selected_dates: list


class HorariPlanificacioResponse(BaseModel):
    data_referencia: str
    sense_dates: bool
    versio_des_de: str | None
    canvi_horari: str | None  # data en què comença un altre horari dins les dates


class CursAnterior(BaseModel):
    cursos: list[str]
    curs_actual: str


class CursDatesResponse(BaseModel):
    curs_anterior: CursAnterior | None


class GeneracioResponse(BaseModel):
    """Viable: dies_utilitzar i horari; no viable: status «ok» i l'horari amb
    el motiu a les metadades."""

    horari: dict | None
    dies_utilitzar: list | None = None
    status: str | None = None


class AnalisiResponse(BaseModel):
    per_slots: str
    per_sessio: str
    professors_slot: str
    avisos: list[dict] = []  # grups sense nivell ({codi, params})


class PublicacioResponse(BaseModel):
    success: bool
    dry_run: bool
    dates_processades: list[str]
    vigilancies_creades: int
    vigilancies_actualitzades: int
    vigilancies_sense_canvis: int
    vigilancies_eliminades: int
    grups_alliberats_creats: int
    titulars_assignats: int
    errors: list[str] | None
    avisos: list | None


class CostFranja(BaseModel):
    slot_key: str  # data (o dia) i hora: "2026-04-20_09:00"
    cost: int | float
    breakdown: dict
    conflicte_nivell: bool
    avisos: list[str]
    item_avisos: dict[str, list[str]]  # els avisos de cada examen (per _uid i per item_id)


class ConcepteCost(BaseModel):
    """Una fila del desglossament del cost: quantitat × pes = punts."""

    concepte: str  # scheduler_engine.core.punts.CONCEPTES
    quantitat: int
    pes: int
    punts: int


class RecalculResponse(BaseModel):
    cost_total: int | float
    cost_breakdown: dict
    cost_breakdown_details: dict
    # Només els conceptes amb punts; la suma de punts és cost_total
    cost_desglossament: list[ConcepteCost]
    slots: list[CostFranja]
    valid: bool  # False si hi ha conflictes de nivell
    # Text del validador i avisos de la configuració ({codi, params}), com a la generació
    logs: list[str | dict]
    stats: dict
