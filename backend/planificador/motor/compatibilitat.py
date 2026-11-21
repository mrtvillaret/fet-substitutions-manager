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


class Particio(StrEnum):
    NOVA = "nova"
    ANTIGA = "antiga"


class Graella(StrEnum):
    MOTOR = "motor"
    COST = "cost"
    DERIVADA = "derivada"


class Estricte(StrEnum):
    DURA = "dura"  # els motors no el trenquen mai
    IGNORAT = "ignorat"  # configuració i recàlcul: el cost mostrat el compta a part


@dataclass(frozen=True, slots=True)
class Politiques:
    cami: Cami
    particio: Particio = Particio.NOVA
    graella: Graella = Graella.MOTOR
    estricte: Estricte = Estricte.DURA
    hora_normalitzada: bool = False
    clau_item_nom: bool = False


CONFIG = Politiques(Cami.CONFIG, estricte=Estricte.IGNORAT)
RECALCUL = Politiques(
    Cami.RECALCUL,
    graella=Graella.COST,
    estricte=Estricte.IGNORAT,
    hora_normalitzada=True,
)
COST_MOSTRAT = Politiques(
    Cami.COST_MOSTRAT,
    graella=Graella.COST,
    estricte=Estricte.IGNORAT,
    hora_normalitzada=True,
)
BACKTRACKING = Politiques(Cami.BACKTRACKING)
GREEDY = Politiques(Cami.GREEDY)
RECUIT = Politiques(
    Cami.RECUIT,
    particio=Particio.ANTIGA,
    estricte=Estricte.DURA,
    clau_item_nom=True,
)
ANALISI = Politiques(Cami.ANALISI, particio=Particio.ANTIGA)
PRECHECK = Politiques(Cami.PRECHECK, graella=Graella.DERIVADA)
DIAGNOSTIC = Politiques(Cami.DIAGNOSTIC, estricte=Estricte.DURA)
