"""
Classe per càrrega i processament de dades JSON
Extret de main_window.py per modularització
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict


class JSONDataLoader:
    """Gestió unificada de càrrega i processament de fitxers JSON"""

    def __init__(self, data_dir: Path):
        """
        Args:
            data_dir: Directori on es troben els fitxers JSON
        """
        self.data_dir = data_dir

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

    def extract_absents_from_preserved_format(self, substitucions_json: Dict[str, Dict]) -> Dict[str, List[str]]:
        """
        Extreu absents del format de preservació (només substitucions amb substitut)
        Format de clau: "Professor|Hora|Assignatura|Grup"

        OBSOLETA: Mantinguda per compatibilitat

        Args:
            substitucions_json: Dict de substitucions amb claus compostes

        Returns:
            Dict[professor, [hores]]
        """
        absents = {}

        for clau, sub_data in substitucions_json.items():
            # Clau format: "Professor|Hora|Assignatura|Grup"
            parts = clau.split("|")
            if len(parts) >= 2:
                professor = parts[0]
                hora = parts[1]

                if professor not in absents:
                    absents[professor] = []

                if hora not in absents[professor]:
                    absents[professor].append(hora)

        # Ordena les hores per cada professor
        for professor in absents:
            absents[professor].sort()

        return absents

    def format_substitutions_for_widget(
        self,
        substitucions_json: Dict[str, Dict],
        hores: List[str],
        disponibles_callback=None
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