"""Dades resoltes immutables i horari editable per ocurrència del JSON."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from planificador.compartit.franja import Franja
from planificador.compartit.nivells import NivellsDelsGrups
from planificador.motor.immutables import congela as congela
from planificador.motor.immutables import descongela as descongela
from planificador.motor.regles import Regles


@dataclass(frozen=True, slots=True)
class DataAmbOrigen:
    original: str
    normalitzada: str | None
    origen: str

    @classmethod
    def de_text(cls, text: str, origen: str):
        try:
            normalitzada = datetime.strptime(text, "%Y-%m-%d").strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            normalitzada = None
        return cls(text, normalitzada, origen)


@dataclass(frozen=True, slots=True)
class Examen:
    """Una sessió d'assignatura i nivell, amb totes les assignacions i extres."""

    id: str
    nom: str
    nom_base: str
    curs: str
    hores_vigilancia: int
    hores_examen: int
    dades: Mapping[str, Any]

    def a_diccionari(self) -> dict:
        return descongela(self.dades)


@dataclass(frozen=True, slots=True)
class Item:
    id: str | None
    nom: str
    examens: tuple[Examen, ...]
    dades: Mapping[str, Any]


type Assignacio = Mapping[str, Franja]


@dataclass(frozen=True, slots=True)
class Problema:
    examens: tuple[Examen, ...]
    franges: tuple[Franja, ...]
    graella: tuple[str, ...]
    hores_inici: tuple[str, ...]
    horaris_professors: Mapping
    nivells: tuple[str, ...]
    dies: tuple[str, ...]
    dates: tuple[DataAmbOrigen, ...]
    mapa_dies: Mapping
    regles: Regles
    alliberaments: Mapping
    durades_vigilancia: Mapping
    durades_examen: Mapping
    durada_titular: int
    durada_examen: int
    no_substituir: frozenset[str]
    taules_grups: Mapping

    def nivells_dels_grups(self) -> NivellsDelsGrups:
        return NivellsDelsGrups.de_config(descongela(self.taules_grups))


class HorariEditable:
    """Còpia editable del document, sense convertir-lo en una assignació d'ítems.

    Els recorreguts del cost i del validador comparteixen els mateixos objectes
    de sessió: el límit per professor deduplica per identitat en memòria.
    """

    def __init__(self, document: dict):
        self.document = deepcopy(document)

    def a_diccionari(self) -> dict:
        return deepcopy(self.document)
