"""
Helpers per gestionar la durada d'examen per nivell i per sessió.
"""

from typing import Any


def get_durada_per_nivell(nivell: str | None, alliberaments_per_nivell: dict[str, Any] | None, default: int) -> int:
    """Retorna la durada per nivell si existeix, o el default."""
    if not nivell or not alliberaments_per_nivell:
        return default

    data = alliberaments_per_nivell.get(nivell)
    if not isinstance(data, dict):
        return default

    durada = data.get("durada")
    if durada is None:
        return default

    try:
        durada_int = int(durada)
    except Exception:
        return default

    return durada_int if durada_int > 0 else default


def get_durada_per_sessio_key(
    sessio_nom: str | None,
    nivell: str | None,
    durades_per_sessio: dict[str, int] | None,
    alliberaments_per_nivell: dict[str, Any] | None,
    default: int,
) -> int:
    """Prioritat: durades_per_sessio > default global (durada_titular).

    Nota: el fallback per nivell s'ha eliminat deliberadament per evitar
    que configuracions antigues d'alliberaments influeixin en el cost de
    sessions no incloses a durades_per_sessio.
    """
    if sessio_nom and durades_per_sessio:
        d = durades_per_sessio.get(sessio_nom)
        if d is not None:
            try:
                d_int = int(d)
                if d_int > 0:
                    return d_int
            except (TypeError, ValueError):
                pass
    return default


def detectar_nivell_sessio(sessio: Any) -> str | None:
    """El nivell d'una sessió: el seu camp «curs» (o «nivell»). No es dedueix
    dels grups dels exàmens: cada sessió es crea ja amb el seu nivell."""
    if not sessio:
        return None
    if isinstance(sessio, dict):
        return sessio.get("curs") or sessio.get("nivell")
    return getattr(sessio, "curs", None) or getattr(sessio, "nivell", None)
