"""
Helpers per gestionar la durada d'examen per nivell i per sessió.
"""

from typing import Dict, Optional, Any

from scheduler_engine.core.constraints import detectar_nivell_grup


def get_durada_per_nivell(nivell: Optional[str],
                          alliberaments_per_nivell: Optional[Dict[str, Any]],
                          default: int) -> int:
    """Retorna la durada per nivell si existeix, o el default."""
    if not nivell or not alliberaments_per_nivell:
        return default

    data = alliberaments_per_nivell.get(nivell)
    if not isinstance(data, dict):
        return default

    durada = data.get('durada')
    if durada is None:
        return default

    try:
        durada_int = int(durada)
    except Exception:
        return default

    return durada_int if durada_int > 0 else default


def get_durada_per_sessio_key(sessio_nom: Optional[str],
                               nivell: Optional[str],
                               durades_per_sessio: Optional[Dict[str, int]],
                               alliberaments_per_nivell: Optional[Dict[str, Any]],
                               default: int) -> int:
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


def detectar_nivell_sessio(sessio: Any, nivells_actius: list[str]) -> Optional[str]:
    """Detecta el nivell d'una sessio a partir del camp curs o dels grups."""
    if not sessio:
        return None

    if isinstance(sessio, dict):
        curs = sessio.get('curs') or sessio.get('nivell')
        examens = sessio.get('examens', [])
    else:
        curs = getattr(sessio, 'curs', None) or getattr(sessio, 'nivell', None)
        examens = getattr(sessio, 'examens', []) or []

    if curs and (not nivells_actius or curs in nivells_actius):
        return curs

    for ex in examens:
        grup = ex.get('grup') if isinstance(ex, dict) else getattr(ex, 'grup', None)
        nivell = detectar_nivell_grup(grup or '', nivells_actius)
        if nivell:
            return nivell

    return curs
