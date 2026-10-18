"""
Core business logic for vigilance management.
Contains all non-UI logic for exam vigilance assignment.
"""

import logging
from typing import Dict, List, Optional, Set

log = logging.getLogger(__name__)

try:
    from i18n_setup import translate as _
except ImportError:
    def _(text):
        return text

class VigilanciaCore:
    """Core business logic for vigilance management"""
    
    def __init__(self):
        self.assignatures_config = None
        self.professors = []
        self.absents_actuals = {}
        self.horari_gestor = None
        self.alliberats_gestor = None
        self.grups_sense_classe = set()
        self.dia_actual = ""
    
    def set_config(self, assignatures_config, professors, absents_actuals, horari_gestor, alliberats_gestor, grups_sense_classe, dia_actual):
        """Set configuration data"""
        self.assignatures_config = assignatures_config
        self.professors = professors
        self.absents_actuals = absents_actuals
        self.horari_gestor = horari_gestor
        self.alliberats_gestor = alliberats_gestor
        self.grups_sense_classe = grups_sense_classe
        self.dia_actual = dia_actual

    def get_categoria_prioritat(self, tipus_activitat: str) -> int:
        """Retorna l'índex de categoria segons ORDRE_PRIORITATS."""
        from config.constants import ORDRE_PRIORITATS

        for i, categoria in enumerate(ORDRE_PRIORITATS):
            if tipus_activitat in categoria:
                return i
        return len(ORDRE_PRIORITATS)

    def is_activitat_auto_assignable(self, tipus_activitat: str) -> bool:
        """
        Retorna si un tipus d'activitat és assignable automàticament
        segons categories configurades i categories actives.
        """
        if not tipus_activitat:
            return False

        from config.constants import CATEGORIES_ACTIVES, ORDRE_PRIORITATS, PRIORITATS

        # Fallback defensiu si encara no s'han carregat categories des de BD.
        if not ORDRE_PRIORITATS:
            return tipus_activitat == "alliberat" or tipus_activitat in PRIORITATS

        categoria = self.get_categoria_prioritat(tipus_activitat)
        if categoria >= len(ORDRE_PRIORITATS):
            return False

        if categoria < len(CATEGORIES_ACTIVES) and not CATEGORIES_ACTIVES[categoria]:
            return False

        return True

    def is_professor_assignable(self, professor: str, hora: str, tipus_activitat: str) -> bool:
        """
        Regla única de domini: professor assignable automàticament.
        """
        if professor in self.absents_actuals and hora in self.absents_actuals.get(professor, []):
            return False
        return self.is_activitat_auto_assignable(tipus_activitat)
    
    def buscar_professor_titular(self, tipus_examen: str, grups: str = "", aula: str = "") -> Optional[str]:
        """Find titular professor for specific exam type, groups and classroom"""
        if not self.assignatures_config:
            return None
        
        try:
            assignatures = self.assignatures_config.get("assignatures", {})
            if not assignatures:
                return None
            
            subject_config = assignatures.get(tipus_examen, {})
            if not subject_config:
                return None
            
            assignacions_list = subject_config.get("assignacions", [])
            
            # Priority 1: Exact match (group + classroom)
            if grups and aula:
                for assignacio in assignacions_list:
                    grup_config = assignacio.get("grup", "")
                    aula_config = assignacio.get("aula", "")
                    titular = assignacio.get("titular", "")
                    
                    if grup_config == grups and aula_config == aula and titular:
                        return titular
            
            # Priority 2: Exact group match (skip ENLLAÇ - they have lower priority)
            if grups:
                for assignacio in assignacions_list:
                    grup_config = assignacio.get("grup", "")
                    aula_config = assignacio.get("aula", "")
                    titular = assignacio.get("titular", "")

                    # Skip ENLLAÇ entries - they are handled in Priority 4
                    if grup_config == grups and titular and aula_config != "ENLLAÇ":
                        return titular
            
            # Priority 3: Exact classroom match (skip ENLLAÇ - they have lower priority)
            if aula:
                for assignacio in assignacions_list:
                    aula_config = assignacio.get("aula", "")
                    titular = assignacio.get("titular", "")

                    # Skip ENLLAÇ entries - they are handled in Priority 4
                    if aula_config == aula and titular and aula_config != "ENLLAÇ":
                        return titular
            
            # Priority 4: ENLLAÇ matches for combined groups
            if grups:
                for assignacio in assignacions_list:
                    grup_config = assignacio.get("grup", "")
                    aula_config = assignacio.get("aula", "")
                    titular = assignacio.get("titular", "")
                    
                    if aula_config == "ENLLAÇ" and titular:
                        # Check if group is compatible with ENLLAÇ
                        if any(part in grups for part in grup_config.split("-") if part):
                            return titular
            
            # Priority 5: First available as fallback
            if assignacions_list:
                titular = assignacions_list[0].get("titular", "")
                if titular:
                    return titular
                    
        except Exception:
            log.warning("No s'ha pogut buscar el titular", exc_info=True)
        
        return None
    
    def es_titular_per_assignatura(self, professor: str, tipus_examen: str, grups: str = "", aula: str = "") -> bool:
        """Check if a specific professor is titular for the given exam type, group and classroom"""
        try:
            titular = self.buscar_professor_titular(tipus_examen, grups, aula)
            return titular == professor
        except Exception:
            log.warning("No s'ha pogut comprovar el titular", exc_info=True)
            return False
    
    def get_titular_status(self, titular: str, hora: str) -> str:
        """Get titular's status: alliberat, disponible, lliure, classe, or absent"""
        # Check if absent
        if titular in self.absents_actuals and hora in self.absents_actuals[titular]:
            return "absent"
        
        # Check if in disponibles list (alliberat or disponible)
        current_data = {"hora": hora}
        disponibles = self.get_disponibles_for_vigilance(hora, current_data)
        
        for disponible in disponibles:
            if isinstance(disponible, tuple) and len(disponible) >= 3:
                nom, tipus_disp, detall = disponible[:3]
                if nom == titular:
                    # Map specific types to general categories
                    if tipus_disp == "alliberat":
                        return "alliberat"
                    else:
                        # All other types (Guàrdia-P, Guàrdia, CD, etc.) are considered "disponible"
                        return "disponible"
        
        # Check if titular's group is in grups_sense_classe (should be alliberat)
        if self.horari_gestor and hasattr(self, 'grups_sense_classe'):
            try:
                activitat = self.horari_gestor.get_activitat(self.dia_actual, hora, titular)
                if activitat:
                    grup_titular = activitat.get("grup", "")
                    assignatura = activitat.get("assignatura", "")
                    
                    # If titular's group is in grups_sense_classe, they are alliberat
                    if grup_titular and grup_titular in self.grups_sense_classe:
                        return "alliberat"
                    # If they have a real class, they have classe
                    elif assignatura:  # Assignatura no buida = té classe
                        return "classe"
                    else:
                        return "lliure"  # Free period
                else:
                    return "lliure"  # Free period
            except Exception:
                log.warning("No s'ha pogut consultar l'activitat del titular", exc_info=True)
                return "lliure"
        
        return "lliure"  # Default
    
    
    def get_disponibles_for_vigilance(self, hora: str, data: Dict) -> List[tuple]:
        """Get available professors for vigilance using same system as substitutions"""
        if not hasattr(self, 'alliberats_gestor') or not self.alliberats_gestor:
            return []
        
        try:
            # Use same method as substitutions
            # Agafar només els grups d'aquesta hora específica
            grups_sense_classe_all = getattr(self, 'grups_sense_classe', set())

            # Si és un diccionari (Dict[str, Set[str]]), agafa només grups d'aquesta hora
            if isinstance(grups_sense_classe_all, dict):
                grups_hora = grups_sense_classe_all.get(hora, set())
            else:
                # Si és un set pla (fallback), usa'l tal qual
                grups_hora = grups_sense_classe_all

            disponibles = self.alliberats_gestor.get_tots_disponibles(
                self.dia_actual, hora, grups_hora
            )

            # DON'T filter out absents for vigilance - we want to show them with warning colors
            # (Different from substitutions where we don't want absent professors)
            return disponibles
            
        except Exception:
            log.warning("No s'han pogut calcular els disponibles per a vigilància", exc_info=True)
            return []
    
    

    def get_vigilants_assignats_hora(self, hora: str) -> Set[str]:
        """Get set of professors already assigned as vigilants at specific hour - placeholder"""
        # This would be implemented by the UI layer
        return set()
