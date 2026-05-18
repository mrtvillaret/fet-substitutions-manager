"""
Emmagatzematge local simple amb JSON i estadístiques
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

from .json_helpers import JSONHelpers
from .models import Substitucio, ConfiguracioDia
from utils.exception_chain import safe_data_operation

try:
    from i18n_setup import translate as _
except ImportError:
    def _(text):
        return text

class Storage:
    """Gestiona l'emmagatzematge local amb estadístiques"""

    def __init__(self, data_dir: str = "data"):
        if data_dir == "data":
            try:
                from config.settings import config
                data_dir = config.data_dir
            except Exception:
                pass
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

        self.substitucions_file = self.data_dir / "substitucions.json"
        self.configuracions_file = self.data_dir / "configuracions.json"
        self.horari_gestor = None  # Will be set by main_window

    def set_horari_gestor(self, horari_gestor):
        """Set horari gestor for day name conversion"""
        self.horari_gestor = horari_gestor

    def _parse_data_limit(self, data_inici: str = None, default: str = "2024-07-01") -> datetime:
        """Helper per parsejar i validar data límit amb fallback"""
        if data_inici is None:
            from config.settings import config
            data_inici = getattr(config, 'data_inici_estadistiques', default)

        try:
            return datetime.strptime(data_inici, "%Y-%m-%d")
        except ValueError:
            print(f"Data d'inici invàlida: {data_inici}, usant {default}")
            return datetime.strptime(default, "%Y-%m-%d")

    def _load_substitutions_data(self) -> Dict:
        """Helper per carregar dades de substitucions amb gestió d'errors"""
        return JSONHelpers.safe_load(self.substitucions_file, {})

    def _filter_valid_dates(self, all_data: Dict, data_limit: datetime) -> Dict:
        """Helper per filtrar dates vàlides dins el període especificat"""
        filtered_data = {}
        for data_str, substitucions in all_data.items():
            try:
                data_obj = datetime.strptime(data_str, "%Y-%m-%d")
                if data_obj >= data_limit:
                    filtered_data[data_str] = substitucions
            except (ValueError, TypeError):
                continue  # Skip invalid dates
        return filtered_data

    
    def desar_substitucions(self, data: str, substitucions: List[Dict], absents: Dict[str, List[str]] = None, absents_tipus: Dict[str, str] = None) -> bool:
        """Desa substitucions per una data (sobreescriu si existeix)

        Args:
            data: Data en format ISO
            substitucions: Llista de substitucions generades
            absents: Diccionari d'absents {professor: [hores]} per desar totes les absències
            absents_tipus: Diccionari de tipus d'absència {professor: tipus_absencia} per preservar consistència
        """
        try:
            # Carrega existents
            all_data = JSONHelpers.safe_load(self.substitucions_file, {})
            
            # Processa substitucions reals i absències sense substitució
            substitucions_reals = []
            
            # 1. Afegeix totes les substitucions (amb o sense substitut) 
            for sub in substitucions:
                if not sub.get("separador"):
                    
                    # Converteix a format estàndard
                    sub_clean = {
                        "data": data,
                        "hora": sub.get("hora", ""),
                        "professor_absent": sub.get("professor_absent", sub.get("professor", "")),
                        "assignatura": sub.get("assignatura", ""),
                        "grup": sub.get("grup", ""),
                        "substitut": sub.get("substitut", ""),
                        "tipus_substitut": sub.get("tipus_substitut", ""),
                        "tipus_absencia": sub.get("tipus_absencia"),  # Preserva el nou camp
                        "comentaris": sub.get("comentaris", ""),
                    }
                    substitucions_reals.append(sub_clean)
            
            # 2. Afegeix absències sense substitució només si no estan a la taula
            if absents:
                # Obté hores que ja estan a la taula de substitucions
                hores_amb_entrada = set()
                for sub in substitucions_reals:
                    clau_hora = f"{sub['professor_absent']}|{sub['hora']}"
                    hores_amb_entrada.add(clau_hora)
                
                # Afegeix només absències que no tenen entrada a la taula
                for professor, hores_absent in absents.items():
                    # Obté el tipus d'absència d'aquest professor
                    tipus_professor = (absents_tipus or {}).get(professor, "ABSENCIA")

                    for hora in hores_absent:
                        clau_hora = f"{professor}|{hora}"
                        if clau_hora not in hores_amb_entrada:
                            # Crea entrada d'absència sense substitució preservant el tipus
                            absencia_clean = {
                                "data": data,
                                "hora": hora,
                                "professor_absent": professor,
                                "assignatura": "",  # Buit perquè és professor de guàrdia
                                "grup": "",         # Buit perquè és professor de guàrdia
                                "substitut": "",    # Buit perquè no cal substitut
                                "tipus_substitut": "",
                                "tipus_absencia": tipus_professor,  # Preserva el tipus del professor
                                "comentaris": "",
                            }
                            substitucions_reals.append(absencia_clean)
            
            # SOBREESCRIU data específica (no suma)
            if substitucions_reals:
                all_data[data] = substitucions_reals
                print(f"Sobreescrites {len(substitucions_reals)} substitucions per {data}")
            else:
                # Si no hi ha substitucions reals, elimina l'entrada del dia
                if data in all_data:
                    del all_data[data]
                    print(f"Eliminades substitucions per {data} (cap substitució real)")
            
            # Desa
            return JSONHelpers.safe_save(self.substitucions_file, all_data)
        except Exception as e:
            print(f"Error desant substitucions: {e}")
            return False
    
    def carregar_substitucions(self, data: str) -> List[Dict]:
        """Carrega substitucions per una data"""
        return JSONHelpers.get_nested(self.substitucions_file, data, [])

    def carregar_absents(self, data: str) -> tuple[Dict[str, List[str]], Dict[str, str]]:
        """Carrega absents i tipus d'absència per una data

        Returns:
            tuple: (absents, absents_tipus)
                - absents: {professor: [hores]}
                - absents_tipus: {professor: tipus_absencia}
        """
        substitucions = self.carregar_substitucions(data)
        absents = {}
        absents_tipus = {}

        for sub in substitucions:
            professor = sub.get("professor_absent", "")
            hora = sub.get("hora", "")
            tipus = sub.get("tipus_absencia", "ABSENCIA")

            # Skip if it's a vigilance or chained substitution (teacher not really absent)
            if tipus in ["VIGILANCIA", "ENCADENADA"]:
                continue

            if professor and hora:
                if professor not in absents:
                    absents[professor] = []
                    absents_tipus[professor] = tipus
                if hora not in absents[professor]:
                    absents[professor].append(hora)

        return absents, absents_tipus
    
    def calcular_estadistiques_substitucions(self, data_inici: str = None) -> Dict[str, int]:
        """
        Calcula estadístiques de professors que fan substitucions desde una data específica
        data_inici: "2024-09-01" format YYYY-MM-DD (si None, usa config)
        
        Cada entrada JSON amb substitut representa una substitució.
        Compta vegades que cada professor ha fet substitucions per hora.
        
        Retorna estadístiques amb claus en múltiples formats:
        - "Professor|Hour": format original (per compatibilitat)
        - "Professor|Day|Hour": format detallat per dia i hora 
        - "Professor|TOTAL": total per professor
        """
        try:
            all_data = self._load_substitutions_data()
            data_limit = self._parse_data_limit(data_inici, "2024-07-01")
            
            estadistiques = {}
            total_substitucions = 0
            
            # Import date context utility
            from utils.date_context import DateContext
            
            filtered_data = self._filter_valid_dates(all_data, data_limit)
            for data_str, substitucions in filtered_data.items():

                # Get day of week for this date (use XML day name)
                weekday_idx = DateContext.from_iso(data_str).weekday_index
                dia_setmana = self.horari_gestor.get_dia_name(weekday_idx) if self.horari_gestor else f"Dia_{weekday_idx}"

                # Compta substitucions (cada entrada JSON representa una substitució)
                for sub in substitucions:
                    if not isinstance(sub, dict):
                        continue
                    
                    hora = sub.get("hora", "").strip()
                    substitut = sub.get("substitut", "").strip()
                    professor_absent = sub.get("professor_absent", "").strip()
                    
                    # Només compta entrades amb substitut (una substitució real)
                    if substitut and hora and professor_absent:
                        # SUBSTITUT: comptabilitza per al professor que fa la substitució
                        key_substitut = f"{substitut}|{hora}"
                        estadistiques[key_substitut] = estadistiques.get(key_substitut, 0) + 1
                        
                        key_substitut_dia = f"{substitut}|{dia_setmana}|{hora}"
                        estadistiques[key_substitut_dia] = estadistiques.get(key_substitut_dia, 0) + 1
                        
                        key_substitut_total = f"{substitut}|TOTAL"
                        estadistiques[key_substitut_total] = estadistiques.get(key_substitut_total, 0) + 1
                        
                        total_substitucions += 1
            
            
            return estadistiques
            
        except Exception as e:
            print(f"Error calculant estadístiques: {e}")
            return {}
    
    def get_resum_professor(self, professor: str, data_inici: str = None) -> Dict[str, int]:
        """Retorna resum de substitucions per professor per hora (format original)"""
        estadistiques = self.calcular_estadistiques_substitucions(data_inici)
        
        resum = {}
        for key, count in estadistiques.items():
            # Only return original format keys (Professor|Hour), skip day+hour and TOTAL keys
            parts = key.split('|')
            if len(parts) == 2 and parts[0] == professor and parts[1] != 'TOTAL':
                prof, hora = parts
                resum[hora] = count
        
        return resum
    
    def get_estadistiques_hora(self, hora: str, data_inici: str = None) -> Dict[str, int]:
        """Retorna tots els professors que han fet substitucions a una hora específica (format original)"""
        estadistiques = self.calcular_estadistiques_substitucions(data_inici)
        
        professors_hora = {}
        for key, count in estadistiques.items():
            # Only use original format keys (Professor|Hour)
            parts = key.split('|')
            if len(parts) == 2 and parts[1] == hora and parts[1] != 'TOTAL':
                prof, h = parts
                professors_hora[prof] = count
        
        return professors_hora
    
    @safe_data_operation("desament configuració")
    def desar_configuracio_dia(self, config: ConfiguracioDia) -> bool:
        """Desa configuració d'un dia"""
        if self.configuracions_file.exists():
            with open(self.configuracions_file, 'r', encoding='utf-8') as f:
                all_configs = json.load(f)
        else:
            all_configs = {}
        
        all_configs[config.data] = config.to_dict()
        
        with open(self.configuracions_file, 'w', encoding='utf-8') as f:
            json.dump(all_configs, f, indent=2, ensure_ascii=False)
        
        return True
    
    def carregar_configuracio_dia(self, data: str) -> Optional[ConfiguracioDia]:
        """Carrega configuració d'un dia"""
        config_data = JSONHelpers.get_nested(self.configuracions_file, data)
        if config_data:
            return ConfiguracioDia.from_dict(config_data)
        return None
    
    def calcular_estadistiques_absencies(self, data_inici: str = None) -> Dict[str, int]:
        """
        Calcula estadístiques de professors absents desde una data específica
        data_inici: "2024-09-01" format YYYY-MM-DD (si None, usa config)

        Compta absències de classes reals (amb assignatura i grup) independentment
        de si tenen substitut assignat o no. Inclou cases de batxillerat sense cobrir.
        """
        try:
            all_data = self._load_substitutions_data()
            data_limit = self._parse_data_limit(data_inici, "2024-09-01")
            
            estadistiques = {}
            total_absencies = 0
            
            filtered_data = self._filter_valid_dates(all_data, data_limit)
            for data_str, substitucions in filtered_data.items():
                
                # Compta absències diferenciades per tipus (reals vs altres activitats)
                for sub in substitucions:
                    if not isinstance(sub, dict):
                        continue

                    professor_absent = sub.get("professor_absent", "").strip()
                    hora = sub.get("hora", "").strip()
                    assignatura = sub.get("assignatura", "").strip()
                    grup = sub.get("grup", "").strip()
                    substitut = sub.get("substitut", "").strip()

                    # Utilitza tipus_absencia per millor categorització
                    tipus_absencia = sub.get("tipus_absencia", "ABSENCIA")

                    # Nova lògica: compta absències de classes reals (amb o sense substitut assignat)
                    if professor_absent and hora and assignatura and grup:
                        # Categoritza segons tipus_absencia
                        if tipus_absencia in ["SERVEI", "VIGILANCIA"]:
                            # Altres activitats (vigilàncies, reunions, servei, etc.)
                            key = f"{professor_absent}|{hora}|ALTRES"
                        else:
                            # Absències reals (malaltia, permisos, etc.)
                            key = f"{professor_absent}|{hora}"

                        estadistiques[key] = estadistiques.get(key, 0) + 1
                        total_absencies += 1
            
            print(f"Estadístiques d'absències: {total_absencies} absències des de {data_limit.strftime('%Y-%m-%d')}")
            
            return estadistiques

        except Exception as e:
            print(f"Error calculant estadístiques d'absències: {e}")
            return {}

    def calcular_distribucio_per_hora_dia(self, data_inici: str = None) -> Dict[str, Dict]:
        """
        Calcula distribució de substitucions per dia de setmana + hora
        per analitzar justícia distributiva del sistema de ponderació.

        Retorna: {
            "DILLUNS|08:00": {
                "1_substitució": {"Professor_A": 3, "Professor_B": 1},
                "2_substitucions": {"Professor_A": 2, "Professor_B": 2, "Professor_C": 2},
                "3_substitucions": {"Professor_A": 1, "Professor_B": 1, "Professor_C": 1}
            }
        }
        """
        try:
            from utils.date_context import DateContext

            all_data = self._load_substitutions_data()
            data_limit = self._parse_data_limit(data_inici, "2024-09-01")

            distribucio = {}

            filtered_data = self._filter_valid_dates(all_data, data_limit)
            for data_str, substitucions in filtered_data.items():

                # Obté dia de la setmana (use XML day name)
                weekday_idx = DateContext.from_iso(data_str).weekday_index
                dia_setmana = self.horari_gestor.get_dia_name(weekday_idx) if self.horari_gestor else f"Dia_{weekday_idx}"

                # Agrupa substitucions per hora per aquest dia
                subs_per_hora = {}
                for sub in substitucions:
                    if not isinstance(sub, dict):
                        continue

                    hora = sub.get("hora", "").strip()
                    substitut = sub.get("substitut", "").strip()

                    # Només compta substitucions reals (amb substitut)
                    if hora and substitut:
                        if hora not in subs_per_hora:
                            subs_per_hora[hora] = []

                        # Extreu tipus de substitució
                        tipus_substitut = sub.get("tipus_substitut", "").strip()
                        # Extreu només el tipus base (abans del parèntesi)
                        if " (" in tipus_substitut:
                            tipus_base = tipus_substitut.split(" (")[0]
                        else:
                            tipus_base = tipus_substitut if tipus_substitut else "Desconegut"

                        subs_per_hora[hora].append({
                            'substitut': substitut,
                            'tipus': tipus_base
                        })

                # Processa cada hora d'aquest dia
                for hora, substituts_data in subs_per_hora.items():
                    clau_hora = f"{dia_setmana}|{hora}"

                    if clau_hora not in distribucio:
                        distribucio[clau_hora] = {}

                    # Determina el nombre de substitucions simultànies
                    num_subs = len(substituts_data)
                    clau_num = f"{num_subs}_substitució{'s' if num_subs > 1 else ''}"

                    if clau_num not in distribucio[clau_hora]:
                        distribucio[clau_hora][clau_num] = {}

                    # Compta cada substitut amb el seu tipus
                    for data_substitut in substituts_data:
                        substitut = data_substitut['substitut']
                        tipus = data_substitut['tipus']

                        if substitut not in distribucio[clau_hora][clau_num]:
                            distribucio[clau_hora][clau_num][substitut] = {
                                'count': 0,
                                'tipus': set()  # Utilitzem set per tipus únics
                            }

                        distribucio[clau_hora][clau_num][substitut]['count'] += 1
                        distribucio[clau_hora][clau_num][substitut]['tipus'].add(tipus)

            # Converteix sets a llistes per facilitar serialització
            for franja in distribucio.values():
                for tipus_num in franja.values():
                    for substitut in tipus_num.values():
                        if isinstance(substitut, dict) and 'tipus' in substitut:
                            substitut['tipus'] = list(substitut['tipus'])

            return distribucio

        except Exception as e:
            print(f"Error calculant distribució per hora/dia: {e}")
            return {}

# Instància global (lazy initialization amb config.data_dir)
_storage = None

def get_storage():
    """
    Retorna la instància global de storage (lazy initialization).
    Usa config.data_dir per inicialitzar amb el directori correcte.
    """
    global _storage
    if _storage is None:
        from config.settings import config
        try:
            from .google_storage import GoogleSheetsStorage
            _storage = GoogleSheetsStorage(data_dir=config.data_dir)
            print(f"✅ Storage amb Google Sheets activat (data_dir: {config.data_dir})")
        except ImportError:
            _storage = Storage(data_dir=config.data_dir)
            print(f"⚠️ Google Sheets no disponible, usant storage local (data_dir: {config.data_dir})")
    return _storage

# Mantenir compatibilitat amb codi existent: storage com a propietat lazy
class _StorageProxy:
    """Proxy per accedir a storage amb lazy initialization"""
    def __getattr__(self, name):
        return getattr(get_storage(), name)

storage = _StorageProxy()
