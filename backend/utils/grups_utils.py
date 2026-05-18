"""
Utils per treballar amb grups i les seves abreviatures.

Aquest mòdul llegeix les abreviatures de grups configurades manualment
des de SQLite per institució i proporciona funcions per aplicar-les.
"""

from typing import Dict, Optional
import os
import i18n_setup

_ = i18n_setup._


# Cache global per evitar llegir el fitxer repetidament
_abreviatures_cache: Dict[str, Dict[str, str]] = {}


def _get_institucio_actual() -> str:
    from config.settings import config
    return config.global_data.get("institucio") or os.getenv("APP_INSTITUCIO") or "exemple"


def normalitzar_llista_grups(grups_string: str) -> str:
    """
    Normalitza una llista de grups separats per comes ordenant-los alfabèticament.

    Això assegura que "1-ESO-B,1-ESO-A" i "1-ESO-A,1-ESO-B" es tractin igual.

    Args:
        grups_string: String amb grups separats per comes, ex: "ESO1B,ESO1A"

    Returns:
        String normalitzat amb grups ordenats alfabèticament, ex: "ESO1A,ESO1B"

    Examples:
        >>> normalitzar_llista_grups("ESO1B,ESO1A")
        "ESO1A,ESO1B"
        >>> normalitzar_llista_grups("1-ESO-C,1-ESO-A,1-ESO-B")
        "1-ESO-A,1-ESO-B,1-ESO-C"
    """
    if not grups_string or ',' not in grups_string:
        return grups_string.strip()

    grups = [g.strip() for g in grups_string.split(',')]
    return ','.join(sorted(grups))


def carregar_abreviatures_grups() -> Dict[str, str]:
    """
    Llegeix les abreviatures de grups des de SQLite de la institució actual.

    Returns:
        Diccionari amb abreviatures: {"ESO1A,ESO1B": "ESO1AB", ...}
        Retorna diccionari buit si no hi ha abreviatures o error.
    """
    from database import get_data_db_session
    from repositories import AbreviaturaGrupRepository

    instit = _get_institucio_actual()
    try:
        with get_data_db_session(instit) as db:
            abreviatures_list = AbreviaturaGrupRepository.get_all(db)
            abreviatures = {a["grups_originals"]: a["abreviatura"] for a in abreviatures_list}
            print(_("✅ Carregades {} abreviatures de grups des de BD").format(len(abreviatures)))
            return abreviatures
    except Exception as e:
        print(_("⚠️ Error en carregar abreviatures de BD: {}").format(e))
        return {}


def get_abreviatures_cached() -> Dict[str, str]:
    """
    Obté les abreviatures amb cache per evitar lectures repetides del fitxer.

    Returns:
        Diccionari amb abreviatures cached
    """
    global _abreviatures_cache
    instit = _get_institucio_actual()

    if instit not in _abreviatures_cache:
        _abreviatures_cache[instit] = carregar_abreviatures_grups()

    return _abreviatures_cache[instit]


def invalidar_cache_abreviatures():
    """
    Invalida el cache d'abreviatures.

    Cridar aquesta funció quan es canviï d'institució o quan s'actualitzi
    la BD per forçar una nova lectura.
    """
    global _abreviatures_cache
    _abreviatures_cache = {}


def obtenir_abreviatura(grups_string: str, abreviatures: Optional[Dict[str, str]] = None) -> str:
    """
    Obté l'abreviatura per a una llista de grups si existeix.

    Normalitza la llista de grups abans de buscar l'abreviatura.
    Si no hi ha abreviatura configurada, retorna la llista normalitzada.

    Args:
        grups_string: String amb grups separats per comes
        abreviatures: Diccionari opcional d'abreviatures. Si és None, usa el cache.

    Returns:
        Abreviatura si existeix, sinó el string original (normalitzat)

    Examples:
        >>> obtenir_abreviatura("ESO1B,ESO1A", {"ESO1A,ESO1B": "ESO1AB"})
        "ESO1AB"
        >>> obtenir_abreviatura("ESO1A", {})
        "ESO1A"
    """
    if not grups_string:
        return grups_string

    # Normalitza primer per assegurar ordre consistent
    normalitzat = normalitzar_llista_grups(grups_string)

    # Usa cache si no es passa diccionari
    if abreviatures is None:
        abreviatures = get_abreviatures_cached()

    # Busca abreviatura
    return abreviatures.get(normalitzat, normalitzat)


def aplicar_abreviatura(grups_string: str) -> str:
    """
    Funció principal per aplicar abreviatures automàticament.

    Aquesta és la funció que s'ha d'usar en tot el codi per obtenir
    l'abreviatura d'una llista de grups.

    Args:
        grups_string: String amb grups separats per comes

    Returns:
        Abreviatura si existeix, sinó el string normalitzat

    Examples:
        >>> aplicar_abreviatura("ESO1B,ESO1A")
        "ESO1AB"  # Si està configurat a grups.json
        >>> aplicar_abreviatura("ESO1X")
        "ESO1X"  # Si no hi ha abreviatura
    """
    return obtenir_abreviatura(grups_string)


def aplicar_abreviatures_a_llista(llista_grups: list) -> list:
    """
    Aplica abreviatures a una llista de strings de grups.

    Args:
        llista_grups: Llista de strings amb grups (poden tenir comes)

    Returns:
        Llista amb abreviatures aplicades

    Examples:
        >>> aplicar_abreviatures_a_llista(["ESO1A,ESO1B", "ESO2A"])
        ["ESO1AB", "ESO2A"]
    """
    return [aplicar_abreviatura(grups) for grups in llista_grups]


def aplicar_abreviatura_grup(grup: str) -> str:
    """
    Aplica abreviatures també a un grup individual.

    Si el grup no és una combinació (sense comes) però forma part
    d'una abreviatura definida, retorna l'abreviatura.
    """
    if not grup:
        return grup

    abreujat = aplicar_abreviatura(grup)
    if abreujat != grup:
        return abreujat

    abreviatures = get_abreviatures_cached()
    for originals, abbr in abreviatures.items():
        parts = [g.strip() for g in originals.split(',') if g.strip()]
        if grup in parts:
            return abbr

    return grup
