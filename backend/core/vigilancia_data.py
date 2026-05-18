"""
Data management for vigilance system.
Handles configuration loading, data persistence, and data validation.
"""

import json
import os
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
from utils.grups_classifier import generar_grups_json
from models import Vigilancia, converters

class VigilanciaDataManager:
    """Manages all data operations for vigilance system"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.vigilancies = {}
        self.assignatures_config = {}
        self.assignatures_per_nivell = {}
        self.grups_per_nivell = {}
        self.aules = []
        self.data_actual = ""
        self.grups_sense_classe = set()
        self._vigilancies_cache = None  # Cache del JSON complet per evitar rellegir
        
    def load_configuration(self):
        """Load exam configuration and classroom data"""
        try:
            # Load exam configuration (for titular assignments)
            config_path = os.path.join(self.data_dir, "configuracio_examens.json")
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    self.assignatures_config = json.load(f)
            else:
                self.assignatures_config = {}

            # Load subjects, groups and classrooms from master_configuracio.json
            master_path = os.path.join(self.data_dir, "master_configuracio.json")
            if os.path.exists(master_path):
                with open(master_path, 'r', encoding='utf-8') as f:
                    master_data = json.load(f)

                    # Llegir estructura jeràrquica
                    nivells_data = master_data.get("nivells", {})
                    self.assignatures_per_nivell = {}
                    self.grups_per_nivell = {}

                    for nivell, dades in nivells_data.items():
                        self.assignatures_per_nivell[nivell] = dades.get("assignatures", [])
                        self.grups_per_nivell[nivell] = dades.get("grups", [])

                    # Load classrooms
                    aules_data = master_data.get("aules", [])
                    self.aules = [a for a in aules_data if a and a.strip()]
            else:
                self.assignatures_per_nivell = {}
                self.grups_per_nivell = {}
                self.aules = []
                
        except Exception as e:
            # print(f"Error loading configuration: {e}")
            self.assignatures_config = {}
            self.assignatures_per_nivell = {}
            self.grups_per_nivell = {}
            self.aules = []
    
    def load_vigilancies(self, data: str) -> Dict[str, List[Vigilancia]]:
        """Load vigilance data for specific date as Vigilancia dataclasses

        Args:
            data: Date in ISO format (YYYY-MM-DD)

        Returns:
            Dict[nivell, List[Vigilancia]] - Vigilancies per nivell
        """
        try:
            vigilancies_path = os.path.join(self.data_dir, "vigilancies_examens.json")
            if os.path.exists(vigilancies_path):
                # 🚀 PERF: Usa cache per evitar rellegir el fitxer múltiples vegades
                if self._vigilancies_cache is None:
                    with open(vigilancies_path, 'r', encoding='utf-8') as f:
                        self._vigilancies_cache = json.load(f)

                vigilancies_dict = self._vigilancies_cache.get(data, {})

                # Convert Dict[str, List[Dict]] → Dict[str, List[Vigilancia]]
                result = {}
                for nivell, vigilancies_list in vigilancies_dict.items():
                    result[nivell] = converters.vigilancies_list_from_dicts(vigilancies_list)
                return result
            return {}
        except Exception as e:
            # print(f"Error loading vigilancies: {e}")
            return {}
    
    def save_vigilancies(self, data: str, vigilancies_data: Dict[str, List[Vigilancia]]):
        """Save vigilance data for specific date

        Args:
            data: Date in ISO format (YYYY-MM-DD)
            vigilancies_data: Dict[nivell, List[Vigilancia]]
        """
        try:
            vigilancies_path = os.path.join(self.data_dir, "vigilancies_examens.json")

            # Load existing data (use cache if available)
            if self._vigilancies_cache is not None:
                all_vigilancies = self._vigilancies_cache.copy()
            elif os.path.exists(vigilancies_path):
                with open(vigilancies_path, 'r', encoding='utf-8') as f:
                    all_vigilancies = json.load(f)
            else:
                all_vigilancies = {}

            # Convert Dict[str, List[Vigilancia]] → Dict[str, List[Dict]] for JSON
            vigilancies_dict = {}
            for nivell, vigilancies_list in vigilancies_data.items():
                vigilancies_dict[nivell] = converters.vigilancies_list_to_dicts(vigilancies_list)

            # Update data for this date
            all_vigilancies[data] = vigilancies_dict

            # Save back
            with open(vigilancies_path, 'w', encoding='utf-8') as f:
                json.dump(all_vigilancies, f, ensure_ascii=False, indent=2)

            # 🚀 PERF: Actualitza cache després de desar
            self._vigilancies_cache = all_vigilancies

        except Exception as e:
            # print(f"Error saving vigilancies: {e}")
            pass
    
    def load_configurations_data(self, data: str) -> Dict:
        """Load configuration data (groups without class) for specific date"""
        try:
            config_path = os.path.join(self.data_dir, "configuracions.json")
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    all_configs = json.load(f)
                    return all_configs.get(data, {})
            return {}
        except Exception as e:
            # print(f"Error loading configurations: {e}")
            return {}
    
    def get_assignatures_per_nivell(self, nivell: str) -> List[str]:
        """Get subjects for specific level"""
        # First try exact match
        if nivell in self.assignatures_per_nivell:
            return self.assignatures_per_nivell[nivell]
        
        # Try with spaces removed (e.g., "1rBATX")
        clean_nivell = nivell.replace(" ", "")
        if clean_nivell in self.assignatures_per_nivell:
            return self.assignatures_per_nivell[clean_nivell]
        
        # Fallback to generic level
        if "BATX" in nivell:
            return self.assignatures_per_nivell.get("BATX", [])
        elif "ESO" in nivell:
            return self.assignatures_per_nivell.get("ESO", [])
        
        return []
    
    def get_grups_per_nivell(self, nivell: str) -> List[str]:
        """Get groups for specific level"""
        # First try exact match
        if nivell in self.grups_per_nivell:
            return self.grups_per_nivell[nivell]
        
        return []
    
    def get_aules(self) -> List[str]:
        """Get available classrooms"""
        return self.aules
    
    def get_assignatures_config(self) -> Dict:
        """Get exam configuration"""
        return self.assignatures_config
    
    def set_grups_sense_classe(self, grups: Set[str]):
        """Set groups without class"""
        self.grups_sense_classe = grups
    
    def get_grups_sense_classe(self) -> Set[str]:
        """Get groups without class"""
        return self.grups_sense_classe

    def generar_i_desar_grups(self, grups_xml: Set[str]) -> bool:
        """
        Genera la secció "grups" de master_configuracio.json automàticament des dels grups del XML.
        Només s'executa si master_configuracio.json no existeix o no té grups.

        Args:
            grups_xml: Conjunt de grups extrets del XML (horari.grups)

        Returns:
            True si s'ha generat i desat, False si ja existia
        """
        master_path = os.path.join(self.data_dir, "master_configuracio.json")

        # Comprova si ja existeix i té nivells amb grups
        if os.path.exists(master_path):
            try:
                with open(master_path, 'r', encoding='utf-8') as f:
                    master_data = json.load(f)
                    # Comprovar si té l'estructura jeràrquica amb nivells
                    nivells = master_data.get("nivells", {})
                    if nivells:
                        print(_("📁 master_configuracio.json ja existeix, no es regenera (edita'l manualment)"))
                        return False
            except:
                pass  # Si hi ha error, es regenera

        try:
            # Generar estructura classificada automàticament
            self.grups_per_nivell = generar_grups_json(grups_xml)

            # Carregar master existent o crear nou amb estructura jeràrquica
            nivells_data = {}
            assignatures_existents = {}
            aules_existents = []
            abreviatures_existents = {}

            if os.path.exists(master_path):
                try:
                    with open(master_path, 'r', encoding='utf-8') as f:
                        master_data = json.load(f)

                        # Extreure assignatures existents
                        for nivell, dades in master_data.get("nivells", {}).items():
                            assignatures_existents[nivell] = dades.get("assignatures", [])

                        aules_existents = master_data.get("aules", [])
                        abreviatures_existents = master_data.get("abreviatures", {})
                except:
                    pass

            # Crear estructura jeràrquica combinant grups nous amb assignatures existents
            # IMPORTANT: Filtrar grups abreviats per NO crear-los com a nivells
            grups_abreviats = set(abreviatures_existents.values())

            tots_nivells = set(self.grups_per_nivell.keys()) | set(assignatures_existents.keys())
            # Eliminar grups abreviats de la llista de nivells
            nivells_reals = tots_nivells - grups_abreviats

            for nivell in nivells_reals:
                nivells_data[nivell] = {
                    "assignatures": assignatures_existents.get(nivell, []),
                    "grups": self.grups_per_nivell.get(nivell, [])
                }

            master_data = {
                "nivells": nivells_data,
                "aules": aules_existents,
                "abreviatures": abreviatures_existents
            }

            # Desar
            os.makedirs(os.path.dirname(master_path), exist_ok=True)
            with open(master_path, 'w', encoding='utf-8') as f:
                json.dump(master_data, f, ensure_ascii=False, indent=2)

            print(_("✅ Grups generats automàticament a master_configuracio.json amb {} nivells:").format(len(self.grups_per_nivell)))
            for nivell, grups in self.grups_per_nivell.items():
                print(_("   - {}: {} grups").format(nivell, len(grups)))

            return True

        except Exception as e:
            print(_("❌ Error en generar grups a master_configuracio.json: {}").format(e))
            return False

    def validate_vigilance_data(self, data: Dict) -> List[str]:
        """Validate vigilance data and return list of errors"""
        errors = []
        
        required_fields = ["hora", "tipus", "vigilant"]
        for field in required_fields:
            if not data.get(field):
                if field != "vigilant" or not data.get("tipus") in ["VIGILÀNCIA"]:
                    errors.append(_("Missing required field: {}").format(field))
        
        # Validate hour format
        hora = data.get("hora", "")
        if hora and not (hora.count(":") == 1 and len(hora.split(":")) == 2):
            errors.append(_("Invalid hour format: {}").format(hora))
        
        return errors
    
    def create_empty_vigilance(self) -> Vigilancia:
        """Create empty vigilance record with default values"""
        return Vigilancia(
            hora="",  # Will be set to first available hour from XML
            tipus="VIGILÀNCIA",
            grups="",
            aula="",
            vigilant="",
            comentaris="",
            nivell="GENERAL"  # Will be overridden by caller
        )
    
    def get_unique_hours(self, vigilancies_data: Dict) -> List[str]:
        """Get sorted list of unique hours from vigilance data"""
        hours = set()
        for nivell_data in vigilancies_data.values():
            for vigilance in nivell_data:
                if vigilance.get("hora"):
                    hours.add(vigilance["hora"])
        
        # Sort hours chronologically
        sorted_hours = sorted(list(hours), key=lambda h: (
            int(h.split(":")[0]) if h != "Pati" else 10,
            int(h.split(":")[1]) if h != "Pati" else 30
        ))
        
        return sorted_hours