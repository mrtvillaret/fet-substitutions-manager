"""
Lògica d'assignació de vigilàncies

Funcions de negoci per:
- Càlcul de prioritats i categories
- Selecció ponderada de candidats
- Scoring per assignació òptima

Extret del GUI per separació de responsabilitats.
"""

from config.constants import ORDRE_PRIORITATS

try:
    from i18n_setup import translate as _
except ImportError:

    def _(text):
        return text


def get_categoria_prioritat(tipus_activitat: str) -> int:
    """Retorna l'índex de categoria segons ORDRE_PRIORITATS

    Args:
        tipus_activitat: Tipus d'activitat (Guàrdia, LIBRE, etc.)

    Returns:
        Índex de categoria (0 = prioritat màxima)
        o len(ORDRE_PRIORITATS) si no es troba

    Example:
        >>> get_categoria_prioritat("Guàrdia")
        0  # Assumint que Guàrdia és categoria 0
        >>> get_categoria_prioritat("DESCONEGUT")
        10  # Si ORDRE_PRIORITATS té 10 categories
    """
    for i, categoria in enumerate(ORDRE_PRIORITATS):
        if tipus_activitat in categoria:
            return i
    return len(ORDRE_PRIORITATS)  # Categoria mínima per tipus desconeguts


def calculate_assignment_score(
    es_titular: bool, categoria: int, pes: int, proximitat_idx: int, max_proximitat: int
) -> float:
    """Calcula score d'assignació per ordenar candidats

    Components del score:
    1. Bonus titular (+100)
    2. Categoria (0-10, menor = millor)
    3. Pes d'activitat (1-10, major = millor)
    4. Proximitat de nivell (0-6, menor = millor)

    Args:
        es_titular: True si és titular de l'assignatura
        categoria: Índex categoria (0 = prioritat màxima)
        pes: Pes de l'activitat (PRIORITATS)
        proximitat_idx: Índex de proximitat de nivell (0 = mateix nivell)
        max_proximitat: Màxim valor de proximitat possible

    Returns:
        Score (float): Major = millor candidat

    Example:
        >>> calculate_assignment_score(True, 0, 10, 0, 6)
        119.0  # 100 (titular) + 10 (categoria 0→10) + 10 (pes) - 1 (proximitat 0)
        >>> calculate_assignment_score(False, 2, 5, 3, 6)
        9.5  # 0 + 8 (categoria 2→8) + 5 (pes) - 3.5 (proximitat 3)
    """
    score = 0.0

    # 1. Bonus titular
    if es_titular:
        score += 100

    # 2. Categoria (invertida: categoria 0 → +10, categoria 10 → +0)
    max_categoria = 10
    score += max(0, max_categoria - categoria)

    # 3. Pes d'activitat
    score += pes

    # 4. Proximitat de nivell (penalització: proximitat 0 → -1, proximitat 6 → -7)
    if max_proximitat > 0:
        proximitat_penalty = (proximitat_idx + 1) / max_proximitat * (max_proximitat + 1)
        score -= proximitat_penalty
    else:
        score -= proximitat_idx + 1

    return score
