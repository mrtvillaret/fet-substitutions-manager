"""
Context unificat per als motors i l'anàlisi de l'scheduler.
"""

from dataclasses import dataclass, field


@dataclass
class SchedulerContext:
    sessions_per_nivell: dict[str, list[dict]]
    restriccions: dict
    horaris_professors: dict
    hores_examen: list[str]
    durada_titular: int
    no_substituir_norm: set[str]
    totes_hores: list[str]
    nivells_actius: list[str]
    dies_utilitzar: list[str]
    dia_a_data_iso: dict[str, list[str]] | None = field(default=None)
    # Alliberaments per nivell: { nivell: { dates: [], durada: int, config: { "YYYY-MM-DD": { "HH:MM": { a: bool, i: bool } } } } }
    # On 'a' indica si el nivell està alliberat a aquella data/hora (🟩)
    # i 'i' indica si és hora d'inici d'examen (🟦)
    alliberaments_per_nivell: dict | None = field(default=None)
    # Durades específiques per sessió: { "Nom (NIVELL)": hores }
    durades_per_sessio: dict | None = field(default=None)
