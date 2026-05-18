"""
Gestor unificat de dades de substitucions
Consolida JSONDataLoader + funcions disperses de main_window
"""
import json
from pathlib import Path
from typing import Dict, List, Optional, Callable
from collections import defaultdict


class SubstitutionsDataManager:
    """Gestió centralitzada de totes les dades de substitucions"""

    def __init__(self, data_dir: Path):
        """
        Args:
            data_dir: Directori on es troben els fitxers JSON
        """
        self.data_dir = data_dir

    # ==================== VIGILÀNCIES ====================

    def load_vigilancies(self, data_iso: str, vigilancies_path: Path) -> List[Dict]:
        """
        Carrega vigilàncies del JSON per una data específica

        Args:
            data_iso: Data en format ISO (YYYY-MM-DD)
            vigilancies_path: Path al fitxer vigilancies_examens.json

        Returns:
            Llista de vigilàncies de tots els nivells per aquesta data
        """
        vigilancies = []
        try:
            if vigilancies_path.exists():
                with open(vigilancies_path, 'r', encoding='utf-8') as f:
                    all_data = json.load(f)

                vigilancies_dia = all_data.get(data_iso, {})

                for nivell, vigilancies_nivell in vigilancies_dia.items():
                    vigilancies.extend(vigilancies_nivell)
            else:
                print(_("⚠️ Fitxer vigilancies_examens.json no trobat"))

        except Exception as e:
            print(_("❌ Error en carregar vigilàncies del JSON: {}").format(e))

        return vigilancies

    # ==================== EXTRACCIÓ ABSENTS ====================

    def extract_absents_from_substitutions(self, substitucions_list: List[Dict]) -> Dict[str, Dict]:
        """
        Extreu TOTES les absències (amb i sense substitució) d'una llista de substitucions

        Args:
            substitucions_list: Llista de substitucions carregada del JSON

        Returns:
            Dict[professor, {'hores': [hores], 'tipus_absencia': str}]
        """
        absents_info = {}

        try:
            if not substitucions_list:
                return {}

            for sub in substitucions_list:
                professor = sub.get("professor_absent", "")
                hora = sub.get("hora", "")
                tipus_absencia = sub.get("tipus_absencia", "ABSENCIA")

                # Carrega tots els absents amb tipus ABSENCIA o SERVEI (excloent VIGILANCIA)
                if professor and hora and tipus_absencia in ["ABSENCIA", "SERVEI"]:
                    if professor not in absents_info:
                        absents_info[professor] = {'hores': [], 'tipus_absencia': tipus_absencia}

                    if hora not in absents_info[professor]['hores']:
                        absents_info[professor]['hores'].append(hora)

                    # Mantenir el tipus_absencia consistent
                    absents_info[professor]['tipus_absencia'] = tipus_absencia

            # Ordena les hores per cada professor
            for professor in absents_info:
                absents_info[professor]['hores'].sort()

            return absents_info

        except Exception as e:
            print(_("⚠️ Error extraient absents: {}").format(e))
            return {}

    def extract_absents_from_substitutions_json(self, data_iso: str, storage) -> Dict[str, Dict]:
        """
        Extreu TOTES les absències directament de substitucions.json per una data

        Args:
            data_iso: Data en format ISO
            storage: Objecte storage per accedir a dades

        Returns:
            Dict[professor, {'hores': [hores], 'tipus_absencia': str}]
        """
        substitucions_llista = storage.carregar_substitucions(data_iso)
        return self.extract_absents_from_substitutions(substitucions_llista)

    # ==================== FORMAT WIDGET ====================

    def format_substitutions_for_widget(
        self,
        substitucions_json: Dict[str, Dict],
        hores: List[str],
        disponibles_callback: Optional[Callable] = None
    ) -> List[Dict]:
        """
        Converteix les substitucions del JSON al format que espera el widget

        Args:
            substitucions_json: Dict de substitucions amb claus compostes
            hores: Llista d'hores del horari
            disponibles_callback: Funció per obtenir disponibles (opcional)

        Returns:
            Llista de substitucions formatades amb separadors per hora
        """
        substitucions_formatades = []

        try:
            # Agrupa per hora per crear separadors
            per_hora = {}
            for clau, sub_data in substitucions_json.items():
                parts = clau.split("|")
                if len(parts) >= 5:
                    # Nou format: professor|hora|assignatura|grup|tipus_absencia
                    professor, hora, assignatura, grup, tipus_absencia = parts[:5]
                elif len(parts) >= 4:
                    # Format antic (compatibilitat): professor|hora|assignatura|grup
                    professor, hora, assignatura, grup = parts[:4]
                    tipus_absencia = sub_data.get("tipus_absencia", "ABSENCIA")
                else:
                    continue

                if hora not in per_hora:
                    per_hora[hora] = []

                # Format que espera el widget
                sub_formatada = {
                    "professor": professor,
                    "professor_absent": professor,
                    "hora": hora,
                    "assignatura": assignatura,
                    "grup": grup,
                    "substitut": sub_data.get("substitut", ""),
                    "tipus_substitut": sub_data.get("tipus_substitut", ""),
                    "comentaris": sub_data.get("comentaris", ""),
                    "tipus_absencia": tipus_absencia,
                    "_conservat": True,  # Marca com conservat del JSON
                }

                # Afegeix disponibles si hi ha callback
                if disponibles_callback:
                    sub_formatada["disponibles"] = disponibles_callback(hora)

                per_hora[hora].append(sub_formatada)

            # Ordena hores i crea la llista amb separadors
            for hora in hores:
                if hora in per_hora:
                    # Afegeix separador
                    substitucions_formatades.append({
                        "separador": True,
                        "hora": hora
                    })

                    # Afegeix substitucions d'aquesta hora
                    substitucions_formatades.extend(per_hora[hora])

        except Exception as e:
            print(_("⚠️ Error en formatejar substitucions: {}").format(e))

        return substitucions_formatades

    # ==================== OBTENCIÓ SUBSTITUCIONS ====================

    def get_substitutions_from_json(self, data_iso: str, substitucions_mgr) -> Dict[str, Dict]:
        """
        Obté les substitucions del JSON publicat per conservar-les

        Args:
            data_iso: Data en format ISO
            substitucions_mgr: Gestor de substitucions per carregar

        Returns:
            Dict[clau_unica, substitucio_data]
        """
        try:
            return substitucions_mgr._carregar_substitucions_publicades(data_iso)
        except Exception as e:
            print(_("⚠️ Error en obtenir substitucions del JSON: {}").format(e))
            return {}

    def get_substitutions_from_widget(self, substitucions_widget) -> Dict[str, Dict]:
        """
        Obté les substitucions actuals de la taula (amb canvis manuals no desats)

        Args:
            substitucions_widget: Widget de substitucions

        Returns:
            Dict[clau_unica, substitucio_data]
        """
        substitucions_actuals = {}

        try:
            if hasattr(substitucions_widget, 'substitucions'):
                for sub in substitucions_widget.substitucions:
                    if not sub.get("separador") and sub.get("substitut"):
                        # Crea clau única semàntica (sense tipus_absencia per preservar en canvis SERVEI ↔ ABSENCIA)
                        tipus_absencia = sub.get('tipus_absencia', 'ABSENCIA')
                        clau = f"{sub.get('professor_absent', '')}|{sub.get('hora', '')}|{sub.get('assignatura', '')}|{sub.get('grup', '')}"

                        substitucions_actuals[clau] = {
                            "substitut": sub.get("substitut", ""),
                            "tipus_substitut": sub.get("tipus_substitut", ""),
                            "comentaris": sub.get("comentaris", ""),
                            "tipus_absencia": tipus_absencia
                        }
        except Exception as e:
            print(_("⚠️ Error en obtenir substitucions actuals: {}").format(e))

        return substitucions_actuals

    # ==================== DISPONIBLES PER JSON ====================

    def get_disponibles_for_json(self, data_iso: str, hora: str, alliberats_gestor, horari, grups_sense_classe) -> List:
        """
        Obté disponibles per una hora específica (per mostrar al JSON)

        Args:
            data_iso: Data en format ISO
            hora: Hora a consultar
            alliberats_gestor: Gestor d'alliberats
            horari: Gestor d'horari
            grups_sense_classe: Dict de grups sense classe per hora

        Returns:
            Llista de professors disponibles
        """
        try:
            from utils.date_context import DateContext

            date_ctx = DateContext.from_iso(data_iso)
            dia = horari.get_dia_name(date_ctx.weekday_index)

            grups_hora = grups_sense_classe.get(hora, set())
            disponibles = alliberats_gestor.get_tots_disponibles(dia, hora, grups_hora)

            return disponibles

        except Exception as e:
            print(_("⚠️ Error en obtenir disponibles per {} a {}: {}").format(data_iso, hora, e))
            return []

    # ==================== COMPARACIÓ AMB PDF ====================

    def count_changes_vs_published_pdf(self, substitucions_actuals: List[Dict],
                                       substitucions_mgr, data_iso: str) -> int:
        """
        Compta canvis respecte al PDF publicat

        Args:
            substitucions_actuals: Llista de substitucions actuals
            substitucions_mgr: Gestor de substitucions
            data_iso: Data en format ISO

        Returns:
            Nombre de canvis
        """
        try:
            substitucions_publicades = substitucions_mgr._carregar_substitucions_publicades(data_iso)
            canvis = 0

            for sub in substitucions_actuals:
                if sub.get("separador"):
                    continue

                tipus_absencia = sub.get('tipus_absencia', 'ABSENCIA')
                clau = f"{sub.get('professor_absent', '')}|{sub.get('hora', '')}|{sub.get('assignatura', '')}|{sub.get('grup', '')}|{tipus_absencia}"

                sub_publicada = substitucions_publicades.get(clau, {})
                if sub.get("substitut") != sub_publicada.get("substitut", ""):
                    canvis += 1

            return canvis

        except Exception as e:
            print(_("⚠️ Error en comptar canvis: {}").format(e))
            return 0