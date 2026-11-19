"""Decisions de compatibilitat per camí; cap correcció de regles implícita.

Les polítiques de cerca es consumiran en portar cada estratègia. El recàlcul
només consumeix RECALCUL i COST_MOSTRAT: no depèn del motor que va generar-lo.
"""

from dataclasses import dataclass
from enum import StrEnum


class Cami(StrEnum):
    CONFIG = "config"
    RECALCUL = "recalcul"
    COST_MOSTRAT = "cost_mostrat"
    BACKTRACKING = "backtracking"
    GREEDY = "greedy"
    RECUIT = "recuit"
    ANALISI = "analisi"
    PRECHECK = "precheck"
    DIAGNOSTIC = "diagnostic"


class Ambit(StrEnum):
    DATA = "data"
    NOM_DIA = "nom_dia"
    FRANJA = "franja"
    GLOBAL = "global"


class Particio(StrEnum):
    NOVA = "nova"
    ANTIGA = "antiga"


class DuradaExamen(StrEnum):
    CONFIG = "config"
    RECALCUL = "recalcul"
    MOTOR = "motor"


class Graella(StrEnum):
    MOTOR = "motor"
    COST = "cost"
    DERIVADA = "derivada"


class Estricte(StrEnum):
    DURA = "dura"
    PER_COST = "per_cost"
    IGNORAT = "ignorat"


# Constants numèriques que no depenen dels pesos desats.
COST_ZONA_EXAMEN = 5
TALL_COST_SESSIO = 10000
BASE_MATEIX_MOMENT = 10000
COST_PROHIBITIU = 10000000


@dataclass(frozen=True, slots=True)
class Politiques:
    cami: Cami
    particio: Particio = Particio.NOVA
    durada_examen: DuradaExamen = DuradaExamen.MOTOR
    graella: Graella = Graella.MOTOR
    estricte: Estricte = Estricte.PER_COST
    exigeix_que_hi_capiga: bool = False
    hora_normalitzada: bool = False
    clau_item_nom: bool = False
    item_id_sense_agrupacions_nom: bool = False
    dies_buits_a_la_sortida: bool = True
    analisi_amb_context_de_franja: bool = True
    mateix_moment_dur: bool = True
    ambit_preferencies: Ambit = Ambit.NOM_DIA
    comprova_dins_item: bool = False
    # El cost mostrat omet aquestes quatre comprovacions expressament.
    cost_mostrat_estricte: bool = False
    cost_mostrat_mateix_dia_separat: bool = False
    cost_mostrat_agrupacio_separada: bool = False
    cost_mostrat_regla_or: bool = False

    @property
    def fusiona_combinacions(self) -> bool:
        return self.particio == Particio.NOVA


CONFIG = Politiques(Cami.CONFIG, durada_examen=DuradaExamen.CONFIG, estricte=Estricte.IGNORAT)
RECALCUL = Politiques(
    Cami.RECALCUL,
    ambit_preferencies=Ambit.DATA,
    durada_examen=DuradaExamen.RECALCUL,
    graella=Graella.COST,
    estricte=Estricte.IGNORAT,
    hora_normalitzada=True,
)
COST_MOSTRAT = Politiques(
    Cami.COST_MOSTRAT,
    graella=Graella.COST,
    estricte=Estricte.IGNORAT,
    hora_normalitzada=True,
    ambit_preferencies=Ambit.DATA,
)
BACKTRACKING = Politiques(Cami.BACKTRACKING, exigeix_que_hi_capiga=True)
GREEDY = Politiques(Cami.GREEDY, dies_buits_a_la_sortida=False)
RECUIT = Politiques(
    Cami.RECUIT,
    particio=Particio.ANTIGA,
    estricte=Estricte.DURA,
    clau_item_nom=True,
    item_id_sense_agrupacions_nom=True,
    analisi_amb_context_de_franja=False,
    mateix_moment_dur=False,
)
ANALISI = Politiques(Cami.ANALISI, particio=Particio.ANTIGA)
PRECHECK = Politiques(Cami.PRECHECK, graella=Graella.DERIVADA)
DIAGNOSTIC = Politiques(Cami.DIAGNOSTIC, estricte=Estricte.DURA)


def ambit_regla(clau: str, politiques: Politiques) -> Ambit:
    """Les preferències obligatòries de cerca i el cost difereixen expressament."""
    if clau in ("mateix_dia", "dies_diferents"):
        return politiques.ambit_preferencies
    if clau in ("no_mateix_dia", "dates_per_nivell", "slots_valids_iso_per_nivell"):
        return Ambit.DATA
    if clau in (
        "assignatures_slot_prohibit",
        "assignatures_dies_exclosos",
        "slots_valids_per_nivell",
        "professors_limit_dies_especifics",
    ):
        return Ambit.NOM_DIA
    if clau in ("mateix_slot", "no_mateix_slot", "combinacions_permeses", "assignatures_hora_fix"):
        return Ambit.FRANJA
    return Ambit.GLOBAL


def forca_del_pin(percentatge: int) -> int:
    """Un pin de pes zero es tracta com a obligatori, també al camí nou."""
    return percentatge or 100
