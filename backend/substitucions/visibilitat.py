"""Quines files es veuen a la pantalla Substitucions: una sola regla, que fan
servir la pantalla (substitucions/_consultes.py) i les absències i la
cobertura (recomptes/). FUNCIONAMENT.md, apartat 5."""

from collections.abc import Collection

from core.alliberats import sense_classe
from noms import nom_net
from substitucions.vigilancia_absent import es_vigilancia_absent


def es_visible_a_substitucions(fila: dict, no_substituir: Collection[str], alliberats_hora: Collection[str]) -> bool:
    """Si la fila es veu a la pantalla Substitucions:
    - la vigilància d'un vigilant absent, sempre: no és una hora de l'horari
      del professor, sinó un tipus de fila que crea el programa quan falta un
      vigilant d'examen («VIGILÀNCIA» a l'assignatura n'és només l'etiqueta),
      i «No substituir» decideix quines hores de l'horari cal cobrir;
    - les altres, no si l'activitat és a «No substituir» (tingui grup o no;
      el nom buit, el de les hores sense activitat, és un nom més) ni si el
      professor està alliberat aquella hora (`alliberats_hora`, els
      alliberats efectius de la data a aquella hora)."""
    if es_vigilancia_absent(fila):
        return True
    if nom_net(fila.get("assignatura") or "") in no_substituir:
        return False
    return not sense_classe(fila.get("professor_absent") or "", (fila.get("grup") or "").strip(), alliberats_hora)
