"""Quines files es veuen a la pantalla Substitucions: una sola regla, que fan
servir la pantalla (substitucions/_consultes.py) i les absències i la
cobertura (recomptes/). FUNCIONAMENT.md, apartat 5."""

from collections.abc import Collection

from grups.disponibilitat import sense_classe
from substitucions.files import FilaSubstitucio
from substitucions.vigilancia_absent import es_vigilancia_absent
from textos import nom_net


def motiu_per_amagar(
    fila: FilaSubstitucio, no_substituir: Collection[str], alliberats_hora: Collection[str]
) -> str | None:
    """Motiu per amagar la fila, amb preferència per l'alliberament si coincideixen.

    «No substituir» s'avalua amb la llista vigent a la data de la fila.
    Les vigilàncies de vigilants absents es mostren sempre.
    """
    if es_vigilancia_absent(fila):
        return None
    if sense_classe(fila.professor_absent or "", (fila.grup or "").strip(), alliberats_hora):
        return "alliberament"
    if nom_net(fila.assignatura or "") in no_substituir:
        return "no_substituir"
    return None


def es_visible_a_substitucions(
    fila: FilaSubstitucio, no_substituir: Collection[str], alliberats_hora: Collection[str]
) -> bool:
    return motiu_per_amagar(fila, no_substituir, alliberats_hora) is None
