"""
Context unificat per als motors i l'anàlisi de l'scheduler.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional


@dataclass
class SchedulerContext:
    sessions_per_nivell: Dict[str, List[Dict]]
    restriccions: Dict
    horaris_professors: Dict
    hores_examen: List[str]
    durada_titular: int
    no_substituir_norm: Set[str]
    totes_hores: List[str]
    nivells_actius: List[str]
    dies_utilitzar: List[str]
    dia_a_data_iso: Optional[Dict[str, List[str]]] = field(default=None)
    # Alliberaments per nivell: { nivell: { dates: [], durada: int, config: { "YYYY-MM-DD": { "HH:MM": { a: bool, i: bool } } } } }
    # On 'a' indica si el nivell està alliberat a aquella data/hora (🟩)
    # i 'i' indica si és hora d'inici d'examen (🟦)
    alliberaments_per_nivell: Optional[Dict] = field(default=None)
    # Durades específiques per sessió: { "Nom (NIVELL)": hores }
    durades_per_sessio: Optional[Dict] = field(default=None)
