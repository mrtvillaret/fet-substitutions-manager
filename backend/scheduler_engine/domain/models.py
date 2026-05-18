"""
Models de domini compartits per als motors de generació d'horaris.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Any

@dataclass
class Slot:
    """Representa un slot temporal (dia + hora)"""
    dia: str   # nom del dia (Dilluns...) — per restriccions i display
    hora: str
    data: str = ""  # data ISO YYYY-MM-DD — identificació única quan hi ha dates repetides

    @property
    def key(self) -> str:
        primary = self.data if self.data else self.dia
        return f"{primary}_{self.hora}"

    def __hash__(self):
        return hash(self.key)

    def __eq__(self, other):
        if not isinstance(other, Slot):
            return False
        return self.key == other.key

@dataclass
class Sessio:
    """Representa una sessió d'examen (pot tenir múltiples grups/professors)"""
    id: str
    nom: str
    nom_base: str
    curs: str
    examens: List[Dict]

    def professors(self) -> Set[str]:
        return {e['titular'] for e in self.examens if e.get('titular')}

@dataclass
class Item:
    """Representa un conjunt de sessions que van juntes al mateix slot."""
    id: str
    sessions: List[Sessio]
    noms_base: Set[str] = field(default_factory=set)

    def __post_init__(self):
        self.noms_base = {s.nom_base for s in self.sessions}

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if not isinstance(other, Item):
            return False
        return self.id == other.id

    def fusionar(self, altre: 'Item') -> 'Item':
        return Item(
            id=f"{self.id}+{altre.id}",
            sessions=self.sessions + altre.sessions
        )
