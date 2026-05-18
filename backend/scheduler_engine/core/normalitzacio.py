"""
Funcions de normalització de text i noms.
"""
from functools import lru_cache

# Mapejat de noms de dies entre idiomes (clau normalitzada → variants)
DIES_MAPEJAT = {
    'dilluns': ['dilluns', 'lunes', 'monday', 'dl'],
    'dimarts': ['dimarts', 'martes', 'tuesday', 'dm'],
    'dimecres': ['dimecres', 'miércoles', 'miercoles', 'wednesday', 'dx'],
    'dijous': ['dijous', 'jueves', 'thursday', 'dj'],
    'divendres': ['divendres', 'viernes', 'friday', 'dv'],
    'dissabte': ['dissabte', 'sábado', 'sabado', 'saturday', 'ds'],
    'diumenge': ['diumenge', 'domingo', 'sunday', 'dg'],
}

@lru_cache(maxsize=512)
def normalitzar_text(text: str) -> str:
    """
    Normalitza text: elimina espais extra i converteix a minúscules (casefold).
    Exemple: "  Text   Exemple  " -> "text exemple"
    """
    return " ".join(str(text).strip().split()).casefold()

@lru_cache(maxsize=64)
def normalitzar_dia(dia: str) -> str:
    """Converteix qualsevol nom de dia al format normalitzat (català minúscules)"""
    dia_lower = dia.lower().strip()
    for normalitzat, variants in DIES_MAPEJAT.items():
        if dia_lower in variants:
            return normalitzat
    return dia_lower

_DIES_CAT = ["Dilluns", "Dimarts", "Dimecres", "Dijous", "Divendres", "Dissabte", "Diumenge"]

def iso_a_dia_nom(data_iso: str) -> str:
    """Converteix data ISO (YYYY-MM-DD) a nom de dia en català."""
    from datetime import datetime as _dt
    try:
        return _DIES_CAT[_dt.strptime(data_iso, "%Y-%m-%d").weekday()]
    except (ValueError, IndexError):
        return data_iso

def format_dia_label(dia: str) -> str:
    """Formata dia per display: nom de dia o 'Dilluns (12/01)' si ISO."""
    import re as _re
    if _re.match(r'^\d{4}-\d{2}-\d{2}$', dia):
        from datetime import datetime as _dt
        try:
            dt = _dt.strptime(dia, "%Y-%m-%d")
            return f"{_DIES_CAT[dt.weekday()]} ({dt.strftime('%d/%m')})"
        except (ValueError, IndexError):
            return dia
    return dia

def dia_nom_per_horari(dia: str) -> str:
    """Retorna nom de dia per lookup en horaris (converteix ISO si cal)."""
    import re as _re
    if _re.match(r'^\d{4}-\d{2}-\d{2}$', dia):
        return normalitzar_dia(iso_a_dia_nom(dia))
    return normalitzar_dia(dia)

def nom_base_assignatura(nom: str) -> str:
    """
    Extreu el nom base d'una assignatura eliminant el sufix de grup/curs.
    Exemple: 'ANGLÈS (1-BATX)' -> 'ANGLÈS'
    Exemple: 'Matemàtiques' -> 'Matemàtiques'
    """
    if not nom:
        return ""
    if " (" in nom:
        return nom.split(" (")[0].strip()
    return nom.strip()
