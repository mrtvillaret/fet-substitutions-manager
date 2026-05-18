"""
Funcions d'ajuda generals
"""
import re
from typing import List, Set

def compactar_grups(grups_text: str) -> str:
    """Compacta noms de grups: '1ESO-A, 1ESO-B' -> '1ESO-AB'"""
    if not grups_text:
        return grups_text
    
    grups = [g.strip() for g in grups_text.split(",") if g.strip()]
    if not grups:
        return grups_text
    
    # Agrupa per base
    bases = {}
    for grup in grups:
        match = re.match(r"(.+-)([A-Z])$", grup)
        if match:
            base, lletra = match.groups()
            if base not in bases:
                bases[base] = []
            bases[base].append(lletra)
        else:
            bases[grup] = []
    
    # Construeix resultat
    resultat = []
    for base, lletres in bases.items():
        if lletres:
            resultat.append(f"{base}{''.join(sorted(lletres))}")
        else:
            resultat.append(base.rstrip("-"))
    
    return ", ".join(sorted(resultat))

def validar_nom_fitxer(nom: str) -> str:
    """Neteja nom de fitxer eliminant caràcters no vàlids"""
    nom_net = re.sub(r'[<>:"/\\|?*]', '_', nom)
    nom_net = nom_net.strip('. ')
    return nom_net or "fitxer_sense_nom"

def set_to_list_sorted(s: Set[str]) -> List[str]:
    """Converteix set a llista ordenada"""
    return sorted(list(s))
