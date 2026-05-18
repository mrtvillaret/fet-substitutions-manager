# google_storage.py
# -*- coding: utf-8 -*-
"""
Storage amb Google Sheets, amb resolució mixta via Meld i ordenació consistent.
- Capçalera a Sheets sense "Aula" ni "Observacions".
- Ordenació estable per (hora, professor_absent, assignatura, grup) a TOTS els fluxos.
- Resolució mixta: obre Meld (local.json vs sheets_temp.json) i, en tancar, puja LOCAL → Sheets.
"""

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from .json_helpers import JSONHelpers

from .storage import Storage  # Storage local base (ha d’existir i gestionar substitucions_file, etc.)

try:
    from i18n_setup import translate as _
except ImportError:
    def _(text):
        return text

# Consolidated logger for this module
_logger = logging.getLogger(__name__)


class GoogleSheetsStorage(Storage):
    """Storage LOCAL amb capacitat de sincronitzar amb Google Sheets"""

    def __init__(self, data_dir: str = "data"):
        super().__init__(data_dir)
        self.sheets_client = None
        self.spreadsheet = None
        self.worksheet = None
        self.sheets_enabled = False
        self._last_connection_error = None

        # Fitxer local de substitucions (l'ha de definir Storage)
        # self.substitucions_file = Path(self.data_dir) / "substitucions.json"

    # -------------------------------------------------------------------------
    # Helpers d’ordenació i normalització
    # -------------------------------------------------------------------------

    def _convert_tipus_absencia_to_string(self, tipus_absencia) -> str:
        """Converteix tipus_absencia a string per Google Sheets"""
        return tipus_absencia or "ABSENCIA"

    def _normalize_entries(self, subs: List[Dict]) -> List[Dict]:
        """Ordena entrades per clau estable (hora, absent, assignatura, grup)."""
        def k(s):
            return (
                s.get("hora", ""),
                (s.get("professor_absent") or s.get("professor") or ""),
                s.get("assignatura", ""),
                s.get("grup", "")
            )
        return sorted(subs, key=k)

    def _normalize_dict_of_lists(self, data: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
        """Aplica ordenació estable a totes les dates."""
        out = {}
        for d, lst in (data or {}).items():
            out[d] = self._normalize_entries(lst or [])
        return out

    # -------------------------------------------------------------------------
    # API Local (sobre-escriu alguns mètodes per injectar ordenació)
    # -------------------------------------------------------------------------

    def desar_substitucions(self, data: str, substitucions: List[Dict], absents: Dict[str, List[str]] = None, absents_tipus: Dict[str, str] = None) -> bool:
        """Desa substitucions SEMPRE localment, opcionalment a Google Sheets només per al dia específic"""
        
        # 1. SEMPRE desa localment primer
        subs_ord = self._normalize_entries([dict(s) for s in substitucions if not s.get("separador")])
        
        
        local_success = super().desar_substitucions(data, subs_ord, absents, absents_tipus)
        
        # 2. Sincronitza amb Google Sheets sempre (dia buit o amb dades)
        self._last_sync_error = None  # Reset error info
        if local_success:
            # Carrega les dades que s'han desat realment al JSON (pot incluir més dades)
            dades_json = self.carregar_substitucions(data) or []
            sheets_success, error_info = self._desar_a_sheets_safe_with_error(data, dades_json)
            self._last_sync_error = error_info  # Store error details
            if sheets_success:
                if dades_json:
                    _logger.info(f"✅ Sincronitzat amb Google Sheets per al dia {data}")
                else:
                    _logger.info(f"✅ Dia buit sincronitzat amb Google Sheets per al dia {data}")
        
        return local_success
    
    def get_last_sync_error(self) -> tuple[bool, str, str]:
        """Retorna (success, error_type, error_message) de l'última sincronització"""
        if self._last_sync_error is None:
            return True, "", ""
        return self._last_sync_error

    def carregar_substitucions(self, data: Optional[str] = None) -> List[Dict]:
        """Carrega dades locals (com fa Storage)."""
        return super().carregar_substitucions(data)

    def calcular_estadistiques_substitucions(self, data_inici: str = None) -> Dict[str, int]:
        """Estadístiques locals (com fa Storage)."""
        return super().calcular_estadistiques_substitucions(data_inici)

    # -------------------------------------------------------------------------
    # Google Sheets (lazy connect)
    # -------------------------------------------------------------------------

    def _conectar_lazy(self) -> bool:
        """Connecta a Google Sheets només quan cal, amb timeout senzill."""
        if self.worksheet is not None:
            return True
        
        import socket
        
        try:
            import gspread
            from google.oauth2.service_account import Credentials
            
            # Configurar timeout de socket molt curt per evitar bloquejos UI
            socket.setdefaulttimeout(3)

            credentials_file = self.data_dir / "google_credentials.json"
            if not credentials_file.exists():
                _logger.warning("⚠️ No hi ha credencials Google Sheets")
                socket.setdefaulttimeout(None)
                self._last_connection_error = "CREDENTIALS"
                return False

            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            credentials = Credentials.from_service_account_file(str(credentials_file), scopes=scope)
            self.sheets_client = gspread.authorize(credentials)

            # Canvia l'ID si cal
            spreadsheet_id = "1GvqdYJz-hQu6BQVb9Jn9MDZx3YfukUwl0c-pUEUE66A"
            self.spreadsheet = self.sheets_client.open_by_key(spreadsheet_id)
            self.worksheet = self.spreadsheet.worksheet("Substitucions")

            socket.setdefaulttimeout(None)
            self.sheets_enabled = True
            self._last_connection_error = None
            import logging
            # Consolidated logger used
            _logger.info("🔗 Connectat a Google Sheets")
            return True

        except Exception as e:
            socket.setdefaulttimeout(None)
            import logging
            # Consolidated logger used
            
            # Capturar el tipus d'error per usar-lo després
            error_str = str(e).lower()
            if ("nameresolutionerror" in error_str or "failed to resolve" in error_str or 
                "el nom o servei no és conegut" in error_str or "name or service not known" in error_str):
                self._last_connection_error = "NO_INTERNET"
                _logger.warning("⏱️ Timeout connectant a Google Sheets (offline)")
            elif "timeout" in error_str:
                self._last_connection_error = "TIMEOUT"
                _logger.warning("⏱️ Timeout connectant a Google Sheets")
            else:
                self._last_connection_error = "CONNECTION"
                _logger.error(f"⚠️ No s'ha pogut connectar a Google Sheets: {e}")
            
            self.sheets_enabled = False
            return False

    # -------------------------------------------------------------------------
    # Lectura / escriptura Sheets
    # -------------------------------------------------------------------------

    def _download_sheets_data(self) -> Dict[str, List[Dict]]:
        """
        Baixa totes les dades de Sheets a un diccionari {data: [entrades]}.
        Format capçalera (índex):
          0 Data
          1 DiaSetmana
          2 Hora
          3 ProfessorAbsent
          4 Assignatura
          5 Grup
          6 Substitut
          7 TipusSubstitut
          8 EditatPer
          9 Timestamp
          10 Vigilancia
          11 Comentaris
        """
        if not self._conectar_lazy():
            return {}

        try:
            all_values = self.worksheet.get_all_values()
            if not all_values:
                return {}

            # Usa el mètode robust _to_local_json que ja gestiona Vigilancia
            return self._to_local_json(all_values)

        except Exception as e:
            import logging
            # Consolidated logger used
            _logger.error(f"❌ Error baixant dades de Sheets: {e}")
            return {}

    def _upload_local_to_sheets_full(self, local_data: Dict[str, List[Dict]]) -> bool:
        """Puja TOT el diccionari local a Sheets"""
        sheets_data = self._from_local_json(local_data)
        return self._write_sheet(sheets_data)

    def _read_sheet(self) -> List[List[str]]:
        """Lectura raw de Google Sheets"""
        if not self._conectar_lazy():
            return []
        try:
            return self.worksheet.get_all_values()
        except Exception as e:
            import logging
            # Consolidated logger used
            _logger.error(f"❌ Error llegint Sheets: {e}")
            return []
    
    def _to_local_json(self, raw_data: List[List[str]]) -> Dict[str, List[Dict]]:
        """Transformació Sheets → JSON local (robust: lectura per nom de columna)"""
        if not raw_data:
            return {}

        # Crear mapa de columnes per nom (robust contra canvis d'ordre)
        headers = raw_data[0] if raw_data else []
        col_map = {header.strip(): i for i, header in enumerate(headers)}

        # Verificar columnes essencials
        required_cols = ['Data', 'Hora', 'ProfessorAbsent']
        missing_cols = [col for col in required_cols if col not in col_map]
        if missing_cols:
            print(f"❌ Columnes essencials no trobades: {missing_cols}")
            return {}

        rows = raw_data[1:]  # Skip header
        out: Dict[str, List[Dict]] = {}

        for row in rows:
            if len(row) < len(required_cols):
                continue

            # Llegir per nom de columna (robust contra reordenació)
            def get_col(name: str, default: str = "") -> str:
                idx = col_map.get(name, -1)
                return row[idx].strip() if 0 <= idx < len(row) else default

            data = get_col("Data")
            if not data:
                continue

            # Gestió per tipus_absencia: preserva valor original de Sheets
            tipus_absencia_raw = get_col("TipusAbsencia")
            tipus_absencia_value = tipus_absencia_raw or "ABSENCIA"  # Default to ABSENCIA

            sub = {
                "data": data,
                "hora": get_col("Hora"),
                "professor_absent": get_col("ProfessorAbsent"),
                "assignatura": get_col("Assignatura"),
                "grup": get_col("Grup"),
                "substitut": get_col("Substitut"),
                "tipus_substitut": get_col("TipusSubstitut"),
                "tipus_absencia": tipus_absencia_value,
                "comentaris": get_col("Comentaris"),
            }
            out.setdefault(data, []).append(sub)

        return self._normalize_dict_of_lists(out)
    
    def _from_local_json(self, local_data: Dict[str, List[Dict]]) -> List[List[str]]:
        """Transformació JSON local → Sheets"""
        from datetime import datetime
        
        headers = ['Data', 'DiaSetmana', 'Hora', 'ProfessorAbsent', 'Assignatura',
                  'Grup', 'Substitut', 'TipusSubstitut', 'EditatPer', 'Timestamp',
                  'TipusAbsencia', 'Comentaris']
        rows = [headers]
        
        for data_str in sorted(local_data.keys()):
            dia_setmana = self._get_dia_setmana(data_str)
            for sub in self._normalize_entries(local_data[data_str]):
                # Converteix tipus_absencia a string per Google Sheets
                tipus_absencia_str = self._convert_tipus_absencia_to_string(sub.get("tipus_absencia"))

                rows.append([
                    data_str, dia_setmana, sub.get("hora", ""),
                    sub.get("professor_absent", sub.get("professor", "")),
                    sub.get("assignatura", ""), sub.get("grup", ""),
                    sub.get("substitut", ""), sub.get("tipus_substitut", ""),
                    "Sistema Auto", datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    tipus_absencia_str,  # TipusAbsencia
                    sub.get("comentaris", "")
                ])
        return rows
    
    def _write_sheet(self, sheet_data: List[List[str]]) -> bool:
        """Escriptura raw a Google Sheets"""
        if not self._conectar_lazy():
            return False
        try:
            import logging
            # Consolidated logger used
            _logger.info("🧹 Netejant Google Sheets...")
            self.worksheet.clear()
            
            if sheet_data:
                _logger.info(f"📤 Pujant {len(sheet_data)-1} substitucions...")
                self.worksheet.append_rows(sheet_data, value_input_option='RAW')
            
            _logger.info("✅ Dades pujades correctament")
            return True
        except Exception as e:
            import logging
            # Consolidated logger used
            _logger.error(f"❌ Error escrivint Sheets: {e}")
            return False

    # -------------------------------------------------------------------------
    # Utilitats
    # -------------------------------------------------------------------------

    def _get_dia_setmana(self, data_str: str) -> str:
        """Get day name from XML via horari_gestor, with fallback to Catalan"""
        try:
            d = datetime.strptime(data_str, "%Y-%m-%d")
            weekday_idx = d.weekday()
            # Use horari_gestor if available (inherited from Storage)
            if self.horari_gestor:
                return self.horari_gestor.get_dia_name(weekday_idx)
            else:
                # Fallback to Catalan day names
                dies = ["Dilluns", "Dimarts", "Dimecres", "Dijous", "Divendres", "Dissabte", "Diumenge"]
                return dies[weekday_idx]
        except Exception:
            return ""

    def _load_local_dict(self) -> Dict[str, List[Dict]]:
        """Carrega el JSON local complet com a dict {data: [subs]} (ordenant)."""
        if not self.substitucions_file.exists():
            return {}
        try:
            with open(self.substitucions_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return self._normalize_dict_of_lists(data)
        except Exception as e:
            import logging
            # Consolidated logger used
            _logger.error(f"❌ Error llegint local: {e}")
            return {}

    def _save_local_dict(self, data: Dict[str, List[Dict]]) -> bool:
        """Desa el JSON local complet (ordenant)."""
        try:
            norm = self._normalize_dict_of_lists(data)
            with open(self.substitucions_file, 'w', encoding='utf-8') as f:
                json.dump(norm, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            import logging
            # Consolidated logger used
            _logger.error(f"❌ Error desant local: {e}")
            return False

    # -------------------------------------------------------------------------
    # Operacions per dia específic (nova funcionalitat)
    # -------------------------------------------------------------------------

    def _eliminar_files_data_safe(self, data: str) -> bool:
        """Elimina files d'una data específica de Google Sheets - OPTIMITZAT per reduir crides API"""
        import logging
        # Consolidated logger used
        
        try:
            if not self._conectar_lazy():
                return False

            # Llegeix totes les dades d'una sola vegada
            all_values = self.worksheet.get_all_values()
            if not all_values or len(all_values) <= 1:
                return True  # No hi ha res per eliminar (només capçalera o buit)

            # Filtra les files que NO són de la data especificada
            headers = all_values[0]
            files_a_mantenir = [headers]  # Mantenir sempre la capçalera
            files_eliminades = 0
            
            for row in all_values[1:]:  # Skip capçalera
                if len(row) > 0 and row[0].strip() == data:
                    files_eliminades += 1
                    # No afegir aquesta fila (eliminar-la)
                else:
                    files_a_mantenir.append(row)

            # Si hi ha files a eliminar, reescriu tot el sheet d'una vegada
            if files_eliminades > 0:
                self.worksheet.clear()
                if files_a_mantenir:
                    self.worksheet.append_rows(files_a_mantenir, value_input_option='RAW')
                _logger.info(f"🗑️ Eliminades {files_eliminades} files de la data {data} de Google Sheets")
            
            return True

        except Exception as e:
            _logger.error(f"⚠️ Error eliminant files de la data {data}: {e}")
            return False

    def _desar_a_sheets_safe(self, data: str, substitucions: List[Dict]) -> bool:
        """Desa a Google Sheets de forma segura només les files del dia específic - OPTIMITZAT"""
        import logging
        # Consolidated logger used
        
        try:
            # Només connecta quan realment cal pujar dades
            if not self._conectar_lazy():
                return False
            
            # Filtra només separadors (inclou totes les substitucions, amb o sense substitut)
            subs_valides = [s for s in substitucions if not s.get("separador")]
            
            # OPTIMITZACIÓ: Operació combinada - llegeix totes les dades d'una vegada
            all_values = self.worksheet.get_all_values()
            headers = all_values[0] if all_values else [
                'Data', 'DiaSetmana', 'Hora', 'ProfessorAbsent', 'Assignatura',
                'Grup', 'Substitut', 'TipusSubstitut', 'EditatPer', 'Timestamp', 'TipusAbsencia', 'Comentaris'
            ]
            
            # Filtra totes les files que NO són d'aquesta data
            files_a_mantenir = [headers]
            files_eliminades = 0
            
            if all_values and len(all_values) > 1:
                for row in all_values[1:]:  # Skip capçalera
                    if len(row) > 0 and row[0].strip() == data:
                        files_eliminades += 1
                        # No afegir aquesta fila (eliminar-la)
                    else:
                        files_a_mantenir.append(row)
            
            # Afegeix les noves dades d'aquest dia
            if subs_valides:
                for sub in subs_valides:
                    professor_absent = (sub.get("professor_absent") or 
                                      sub.get("professor") or 
                                      "Professor desconegut")
                    
                    row = [
                        data,                                    # Data
                        self._get_dia_setmana(data),            # DiaSetmana  
                        sub.get("hora", ""),                    # Hora
                        professor_absent,                       # Absent
                        sub.get("assignatura", ""),            # Assignatura
                        sub.get("grup", ""),                   # Grup
                        sub.get("substitut", ""),              # Substitut (pot estar buit)
                        sub.get("tipus_substitut", ""),        # ActivitatSubstitut
                        "Sistema Auto",                         # EditatPer
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # Timestamp
                        self._convert_tipus_absencia_to_string(sub.get("tipus_absencia")),  # TipusAbsencia
                        sub.get("comentaris", "")              # Notes/Canvi
                    ]
                    files_a_mantenir.append(row)
            
            # Reescriu tot el sheet d'una sola vegada (optimització màxima)
            self.worksheet.clear()
            if len(files_a_mantenir) > 1:  # Més que només capçalera
                self.worksheet.append_rows(files_a_mantenir, value_input_option='RAW')
            elif len(files_a_mantenir) == 1:  # Només capçalera
                self.worksheet.append_row(headers, value_input_option='RAW')
            
            if files_eliminades > 0:
                _logger.info(f"🗑️ Eliminades {files_eliminades} files de la data {data} de Google Sheets")
            
            if subs_valides:
                _logger.info(f"📤 {len(subs_valides)} files (totes les substitucions del dia) pujades a Google Sheets per al dia {data}")
            else:
                _logger.info(f"📋 Dia buit - eliminades files del dia {data} de Google Sheets")
            
            return True
            
        except Exception as e:
            _logger.error(f"⚠️ No s'ha pogut pujar a Google Sheets el dia {data}: {e}")
            return False  # No és error crític, les dades locals estan bé

    def _desar_a_sheets_safe_with_error(self, data: str, substitucions: List[Dict]) -> tuple[bool, tuple[bool, str, str]]:
        """Desa a Google Sheets capturant informació d'error detallada"""
        try:
            success = self._desar_a_sheets_safe(data, substitucions)
            if success:
                return True, (True, "", "")
            else:
                # Si ha fallat però no ha llançat excepció, comprovar error de connexió
                if self._last_connection_error:
                    if self._last_connection_error == "NO_INTERNET":
                        return False, (False, "NO_INTERNET", _("Sense connexió a Internet"))
                    elif self._last_connection_error == "TIMEOUT":
                        return False, (False, "TIMEOUT", _("Temps d'espera esgotat connectant a Google Sheets"))
                    elif self._last_connection_error == "CREDENTIALS":
                        return False, (False, "CREDENTIALS", _("Error d'autenticació amb Google Sheets"))
                    elif self._last_connection_error == "CONNECTION":
                        return False, (False, "CONNECTION", _("Error de connexió amb Google Sheets"))

                return False, (False, "UNKNOWN", _("Error desconegut durant la sincronització"))
        except Exception as e:
            error_str = str(e).lower()
            
            # Classificar tipus d'error
            if ("nameresolutionerror" in error_str or "failed to resolve" in error_str or 
                "el nom o servei no és conegut" in error_str or "name or service not known" in error_str):
                return False, (False, "NO_INTERNET", _("Sense connexió a Internet"))
            elif "403" in error_str or "forbidden" in error_str:
                return False, (False, "NO_PERMISSION", _("Permisos insuficients per modificar Google Sheets"))
            elif "429" in error_str or "quota" in error_str:
                return False, (False, "QUOTA_EXCEEDED", _("Límit de peticions a Google Sheets exhaurit"))
            elif "timeout" in error_str:
                return False, (False, "TIMEOUT", _("Temps d'espera esgotat connectant a Google Sheets"))
            elif "credentials" in error_str or "auth" in error_str:
                return False, (False, "CREDENTIALS", _("Error d'autenticació amb Google Sheets"))
            elif "connectionerror" in error_str or "connection" in error_str:
                return False, (False, "CONNECTION", _("Error de connexió amb Google Sheets"))
            else:
                return False, (False, "UNKNOWN", _("Error: {error}").format(error=str(e)[:150]))

    # -------------------------------------------------------------------------
    # Operacions d'alt nivell: força pujar / baixar / detectar / meld
    # -------------------------------------------------------------------------

    def force_local_to_sheets(self) -> bool:
        """Força pujar TOT el local a Sheets (sobre-escriu)."""
        local_dict = self._load_local_dict()
        return self._upload_local_to_sheets_full(local_dict)

    def force_sheets_to_local(self) -> bool:
        """Força baixar TOT de Sheets i sobre-escriure local (ordenat)."""
        sheets_dict = self._download_sheets_data()
        if not sheets_dict and not self._conectar_lazy():
            return False
        ok = self._save_local_dict(sheets_dict)
        if ok:
            import logging
            # Consolidated logger used
            _logger.info("✅ Dades de Sheets desades localment")
        return ok

    def check_sync_direction(self) -> str:
        """
        Detecta estat: 'equal', 'local_to_sheets', 'sheets_to_local', 'mixed'
        """
        local = self._load_local_dict()
        sheets = self._download_sheets_data()

        if not sheets and not self.sheets_enabled:
            return "unknown"

        # Canonitza a text per comparar (ordre ja normalitzat)
        def to_lines(d: Dict[str, List[Dict]]) -> List[str]:
            lines = []
            for date in sorted(d.keys()):
                lines.append(f"=== {date} ===")
                for s in d[date]:
                    # Ordre fix dels camps per comparació consistent
                    fields = [
                        s.get('hora', ''),
                        s.get('professor_absent', ''),
                        s.get('assignatura', ''),
                        s.get('grup', ''),
                        s.get('substitut', ''),
                        s.get('tipus_substitut', ''),
                        s.get('tipus_absencia', 'ABSENCIA'),  # SERVEI o ABSENCIA
                        s.get('comentaris', '')
                    ]
                    lines.append('\t'.join(fields))
            return lines

        L = to_lines(local)
        S = to_lines(sheets)

        if L == S:
            return "equal"

        # Defineix que “direcció simple” si un és subconjunt exacte de l’altre
        setL, setS = set(L), set(S)
        if setL.issubset(setS) and setL != setS:
            return "sheets_to_local"
        if setS.issubset(setL) and setL != setS:
            return "local_to_sheets"
        return "mixed"



    def resolve_with_meld(self) -> bool:
        """Flux complet de resolució amb Meld"""
        temp_files = self._manage_temp_files()
        if not temp_files:
            return False
            
        return self._execute_meld_workflow(temp_files)
    
    def _manage_temp_files(self) -> Optional[dict]:
        """Gestiona creació de fitxers temporals per Meld"""
        import shutil
        from pathlib import Path
        
        # Comprovar Meld
        meld_path = shutil.which("meld")
        if not meld_path:
            import logging
            # Consolidated logger used
            _logger.warning("⚠️ Meld no està instal·lat. Intenta:")
            _logger.info("   Ubuntu/Debian: sudo apt install meld")
            _logger.info("   Fedora: sudo dnf install meld")
            _logger.info("   Arch: sudo pacman -S meld")
            _logger.info("   macOS (brew): brew install --cask meld")
            _logger.info("   Windows: https://meldmerge.org/")
            return None
            
        # Carregar dades d'origen
        local_dict = self._load_local_dict()
        sheets_dict = self._download_sheets_data()
        
        # Crear fitxers temporals
        tmp_local = Path(self.data_dir) / "substitucions_local_temp.json"
        tmp_sheets = Path(self.data_dir) / "substitucions_sheets_temp.json"
        
        try:
            self._dump_ordered_json(tmp_local, local_dict)
            self._dump_ordered_json(tmp_sheets, sheets_dict)
            import logging
            # Consolidated logger used
            _logger.info(f"📄 Temporals creats:\n  - {tmp_local}\n  - {tmp_sheets}")
            
            return {
                'meld_path': meld_path,
                'tmp_local': tmp_local,
                'tmp_sheets': tmp_sheets,
                'h_local_before': self._sha256(tmp_local),
                'h_sheets_before': self._sha256(tmp_sheets)
            }
            
        except Exception as e:
            import logging
            # Consolidated logger used
            _logger.error(f"❌ No s'han pogut crear temporals: {e}")
            return None
    
    def _execute_meld_workflow(self, temp_files: dict) -> bool:
        """Executa flux Meld i aplica canvis"""
        import subprocess
        
        meld_path = temp_files['meld_path']
        tmp_local = temp_files['tmp_local']
        tmp_sheets = temp_files['tmp_sheets']
        h_local_before = temp_files['h_local_before']
        h_sheets_before = temp_files['h_sheets_before']
        
        # Obrir Meld
        try:
            import logging
            # Consolidated logger used
            _logger.info("🟪 Obrint Meld… (pots editar qualsevol costat; desa abans de tancar)")
            subprocess.call([meld_path, str(tmp_local), str(tmp_sheets)])
        except Exception as e:
            import logging
            # Consolidated logger used
            _logger.error(f"❌ Error obrint Meld: {e}")
            return False
            
        # Detectar i aplicar canvis
        changed_local = (self._sha256(tmp_local) != h_local_before)
        changed_sheets = (self._sha256(tmp_sheets) != h_sheets_before)
        
        ok = self._apply_meld_changes(tmp_local, tmp_sheets, changed_local, changed_sheets)
        
        # Netejar temporals
        for p in (tmp_local, tmp_sheets):
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass
                
        return ok
    
    def _apply_meld_changes(self, tmp_local, tmp_sheets, changed_local: bool, changed_sheets: bool) -> bool:
        """Aplica canvis dels fitxers Meld"""
        import json
        
        if not changed_local and not changed_sheets:
            import logging
            # Consolidated logger used
            _logger.warning("⚠️ No s'han detectat canvis en cap fitxer!")
            _logger.info("ℹ️ Fitxers NO sincronitzats - no s'ha modificat res")
            return False
            
        ok = True
        
        if changed_local:
            try:
                with open(tmp_local, 'r', encoding='utf-8') as f:
                    resolved_local = json.load(f)
                self._save_local_dict(resolved_local)
                _logger.info("✅ Canvis aplicats al fitxer local real")
            except Exception as e:
                _logger.error(f"❌ Error aplicant al local: {e}")
                ok = False
                
        if changed_sheets:
            try:
                with open(tmp_sheets, 'r', encoding='utf-8') as f:
                    resolved_sheets = json.load(f)
                if not self._upload_dict_to_sheets_meld(resolved_sheets):
                    ok = False
                else:
                    _logger.info("✅ Canvis pujats a Google Sheets")
            except Exception as e:
                _logger.error(f"❌ Error aplicant a Sheets: {e}")
                ok = False
                
        return ok
    
    def _dump_ordered_json(self, path, data: dict):
        """Desa JSON amb ordenació consistent"""
        import json
        ordered_data = self._ordered_copy(data)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(ordered_data, f, indent=2, ensure_ascii=False)
    
    def _ordered_copy(self, d: dict) -> dict:
        """Retorna dict amb dates i llistes ordenades"""
        if not d:
            return {}
        out = {}
        for date in sorted(d.keys()):
            lst = d.get(date, []) or []
            lst_sorted = sorted(lst, key=lambda s: (
                self._norm_hora(s.get("hora", "")),
                (s.get("professor_absent") or s.get("professor") or ""),
                s.get("assignatura", ""),
                s.get("grup", "")
            ))
            out[date] = lst_sorted
        return out
    
    def _norm_hora(self, h: str) -> str:
        """Normalitza format hora"""
        try:
            hh, mm = (h or "").split(":")
            return f"{int(hh):02d}:{int(mm):02d}"
        except Exception:
            return (h or "").strip()
    
    def _sha256(self, path) -> str:
        """Calcula hash SHA256 del fitxer"""
        import hashlib
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    
    def _upload_dict_to_sheets_meld(self, data_dict: dict) -> bool:
        """Puja diccionari a Sheets des de Meld"""
        try:
            if not self._conectar_lazy():
                return False
                
            # Neteja i capçaleres
            self.worksheet.clear()
            headers = ['Data','DiaSetmana','Hora','ProfessorAbsent','Assignatura',
                      'Grup','Substitut','TipusSubstitut','EditatPer','Timestamp','TipusAbsencia','Comentaris']
            self.worksheet.append_row(headers)
            
            # Genera files
            from datetime import datetime
            rows = []
            for data_str in sorted(data_dict.keys()):
                dia_setmana = self._get_dia_setmana(data_str)
                for sub in data_dict[data_str]:
                    rows.append([
                        data_str, dia_setmana, self._norm_hora(sub.get("hora","")),
                        sub.get("professor_absent", sub.get("professor","")),
                        sub.get("assignatura",""), sub.get("grup",""),
                        sub.get("substitut",""), sub.get("tipus_substitut",""),
                        "Meld", datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        self._convert_tipus_absencia_to_string(sub.get("tipus_absencia")),  # TipusAbsencia
                        sub.get("comentaris","")
                    ])
                    
            if rows:
                self.worksheet.append_rows(rows, value_input_option='RAW')
            return True
        except Exception as e:
            import logging
            # Consolidated logger used
            _logger.error(f"❌ Error pujant a Sheets: {e}")
            return False




# -------------------------------------------------------------------------
# Utilitat per crear credencials
# -------------------------------------------------------------------------

def create_credentials_file(credentials_data: dict, data_dir: str = "data"):
    """Crea fitxer de credencials per Google API."""
    credentials_file = Path(data_dir) / "google_credentials.json"
    with open(credentials_file, 'w', encoding='utf-8') as f:
        json.dump(credentials_data, f, indent=2)
    import logging
    # Consolidated logger used
    _logger.info(f"✅ Credencials desades a {credentials_file}")
    return str(credentials_file)

