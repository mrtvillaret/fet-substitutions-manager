"""
Classificador automàtic de grups per nivells educatius.
Detecta prefixos automàticament dels noms de grups del XML.
"""

import re
from typing import Dict, List, Set
from collections import defaultdict


def extreure_prefix(grup: str) -> str:
    """
    Extreu el prefix (nivell) d'un nom de grup automàticament.

    Estratègia:
    - Separa la part numèrica/alfanumèrica inicial del sufix de lletra
    - Exemples:
      - "BAC1A" → "BAC1"
      - "BAC2B" → "BAC2"
      - "ESO4A" → "ESO4"
      - "3-ESO-A" → "3-ESO"
      - "1-BATX-B" → "1-BATX"

    Args:
        grup: Nom del grup complet

    Returns:
        Prefix detectat (nivell educatiu)
    """
    if not grup or grup == "-" or not grup.strip():
        return ""

    grup = grup.strip()

    # Estratègia 1: Si té guions, agafar tot menys la darrera part
    if "-" in grup:
        parts = grup.split("-")
        # Si l'última part és una sola lletra (A, B, C...), és el sufix
        if len(parts[-1]) == 1 and parts[-1].isalpha():
            return "-".join(parts[:-1])
        # Sinó, retornar tot
        return grup

    # Estratègia 2: Sense guions, separar lletra final
    # Buscar patró: (text amb números)(lletra final opcional)
    match = re.match(r'^([A-Z]+\d+)([A-Z]?)$', grup.upper())
    if match:
        prefix = match.group(1)
        return prefix

    # Estratègia 3: Si no es detecta, retornar el grup sencer
    return grup


def classificar_grups_per_nivell(grups: Set[str]) -> Dict[str, List[str]]:
    """
    Classifica un conjunt de grups per nivells educatius detectats automàticament.

    Args:
        grups: Conjunt de noms de grups del XML

    Returns:
        Diccionari {prefix_nivell: [grups ordenats]}
        Exemple: {"BAC1": ["BAC1A", "BAC1B"], "BAC2": ["BAC2A"], "ESO4": ["ESO4A", "ESO4B"]}
    """
    grups_per_nivell = defaultdict(list)

    # Filtrar grups vàlids
    grups_valids = {g for g in grups if g and g != "-" and g.strip()}

    for grup in grups_valids:
        prefix = extreure_prefix(grup)
        if prefix:  # Només afegir si s'ha detectat un prefix vàlid
            grups_per_nivell[prefix].append(grup)

    # Ordenar grups dins de cada nivell
    for nivell in grups_per_nivell:
        grups_per_nivell[nivell].sort()

    # Convertir a dict normal i ordenar per clau de nivell
    return dict(sorted(grups_per_nivell.items()))


def generar_grups_json(grups: Set[str]) -> Dict[str, List[str]]:
    """
    Genera l'estructura completa per desar a grups.json.
    Detecció 100% automàtica sense hardcoding de nivells.

    Args:
        grups: Conjunt de grups del horari XML (pot incloure grups separats per comes)

    Returns:
        Diccionari llest per serialitzar a JSON
        Exemple: {"BAC1": ["BAC1A", "BAC1B"], "BAC2": ["BAC2A"], "ESO4": ["ESO4A"]}
    """
    # Expandir grups separats per comes en grups individuals
    grups_individuals = set()
    for grup in grups:
        if "," in grup:
            # Dividir per comes i afegir cada grup individualment
            parts = [part.strip() for part in grup.split(",")]
            grups_individuals.update(parts)
        else:
            grups_individuals.add(grup)

    return classificar_grups_per_nivell(grups_individuals)
