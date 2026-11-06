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
