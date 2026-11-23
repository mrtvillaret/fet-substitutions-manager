"""Contracte dels motors i pressupost amb rellotge injectable."""

import time
from dataclasses import dataclass, field
from typing import Literal

from planificador.motor.model import Assignacio, Item


class TempsEsgotat(Exception):
    """S'ha acabat el termini a mitja preparació."""


class Pressupost:
    """El motor decideix quan inicia i consulta el termini compartit.

    Cap consulta implícita en construir-lo ni en comptar nodes. Això conserva
    els punts exactes de consulta de cada estratègia.
    """

    def __init__(self, segons: float, rellotge=None):
        self.segons = segons
        self.rellotge = rellotge or (lambda: time.monotonic())
        self.termini = float("inf")

    def inicia(self):
        self.inici = self.rellotge()
        self.termini = self.inici + self.segons

    def temps_esgotat(self):
        return self.rellotge() >= self.termini

    def temps_transcorregut_esgotat(self):
        """El recuit resta l'inici abans de comparar; conserva l'aritmètica."""
        return self.rellotge() - self.inici >= self.segons

    def comprova_termini(self):
        if self.temps_esgotat():
            raise TempsEsgotat


@dataclass
class ResultatCerca:
    assignacio: Assignacio | None
    complet: bool
    motiu_aturada: Literal["temps", "nodes"] | None
    causes: list[dict] = field(default_factory=list)
    traça: list[dict] = field(default_factory=list)
    registre: list[str] = field(default_factory=list)
    cost: float | None = None
    items: tuple[Item, ...] = ()
