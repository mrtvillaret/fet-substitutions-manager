"""
Gestor d'horaris XML per al backend web - Llegeix configuració de SQLite
"""
import xml.etree.ElementTree as ET
import re
from typing import Dict, List, Optional, Set, Union

try:
    from i18n_setup import translate as _
except ImportError:
    def _(text):
        return text

class GestorHorariWeb:
    """Gestor d'horaris amb límit de professor i consolidació de grups múltiples - Versió Web"""

    def __init__(self, xml_path: str, ultim_professor_subs: Optional[str] = None):
        """
        Args:
            xml_path: Path al fitxer XML de FET
            ultim_professor_subs: Últim professor a considerar (límit). Si None, carrega tots.
        """
        self.xml_path = xml_path
        self.ultim_professor_subs = ultim_professor_subs
        self.horari = {}  # {dia: {hora: {professor: dades}}}
        self.professors = []
        self.grups = set()  # Grups amb abreviatures aplicades
        self.grups_raw = set()  # Grups RAW del XML abans d'aplicar abreviatures
        self.hores = []  # Hores extretes del XML en ordre cronològic
        self.dies = []   # Dies extrets del XML
        self._abreviatures_cache = None  # Cache d'abreviatures de la BD
        self.carregar()

    def _carregar_abreviatures_bd(self) -> Dict[str, str]:
        """Carrega abreviatures des de la base de dades SQLite"""
        if self._abreviatures_cache is not None:
            return self._abreviatures_cache

        from database import get_db_session
        from repositories import AbreviaturaGrupRepository

        try:
            with get_db_session() as db:
                abreviatures_list = AbreviaturaGrupRepository.get_all(db)
                # Convertir a diccionari {grups_originals: abreviatura}
                self._abreviatures_cache = {
                    item['grups_originals']: item['abreviatura']
                    for item in abreviatures_list
                }
                print(f"✅ Carregades {len(self._abreviatures_cache)} abreviatures de grups des de BD")
                return self._abreviatures_cache
        except Exception as e:
            print(f"⚠️  Error carregant abreviatures de BD: {e}")
            return {}

    def _normalitzar_llista_grups(self, grups_string: str) -> str:
        """Normalitza una llista de grups separats per comes ordenant-los alfabèticament"""
        if not grups_string or ',' not in grups_string:
            return grups_string.strip()

        grups = [g.strip() for g in grups_string.split(',')]
        return ','.join(sorted(grups))

    def _aplicar_abreviatura(self, grups_string: str) -> str:
        """Aplica abreviatures llegint de la BD en lloc del JSON"""
        if not grups_string:
            return grups_string

        # Normalitza primer per assegurar ordre consistent
        normalitzat = self._normalitzar_llista_grups(grups_string)

        # Obté abreviatures de BD
        abreviatures = self._carregar_abreviatures_bd()

        # Busca abreviatura
        return abreviatures.get(normalitzat, normalitzat)

    def carregar(self):
        """Carrega l'horari des del XML amb consolidació de grups"""
        try:
            # Reinicialitza els atributs abans de carregar
            self.horari = {}
            self.professors = []
            self.grups = set()
            self.grups_raw = set()
            self.hores = []
            self.dies = []
            tree = ET.parse(self.xml_path)
            root = tree.getroot()

            # Primera passada: recull tots els professors
            tots_professors = []
            for teacher in root.findall("Teacher"):
                nom = teacher.get("name", "").strip()
                if not nom:
                    continue
                tots_professors.append(nom)

            # Aplica límit de professor
            ultim_prof = self.ultim_professor_subs
            if ultim_prof and ultim_prof in tots_professors:
                # Troba l'índex del professor límit
                try:
                    index_limit = tots_professors.index(ultim_prof) + 1
                    self.professors = tots_professors[:index_limit]
                    print(_("Aplicat límit de professor: fins '{professor}' ({count} professors)").format(professor=ultim_prof, count=index_limit))
                except ValueError:
                    print(_("Professor límit '{professor}' no trobat, en carregar tots").format(professor=ultim_prof))
                    self.professors = tots_professors
            else:
                print(_("Sense límit de professor o '{professor}' no trobat").format(professor=ultim_prof))
                self.professors = tots_professors

            # Segona passada: processa dades només dels professors seleccionats
            professors_set = set(self.professors)

            for teacher in root.findall("Teacher"):
                nom = teacher.get("name", "").strip()
                if not nom or nom not in professors_set:
                    continue

                for day in teacher.findall("Day"):
                    dia = day.get("name", "").strip()
                    if dia not in self.horari:
                        self.horari[dia] = {}

                    for hour in day.findall("Hour"):
                        hora = hour.get("name", "").strip()
                        if hora not in self.horari[dia]:
                            self.horari[dia][hora] = {}

                        # Processa activitat
                        # Si no hi ha Subject, cadena buida (professor no al centre o hora lliure)
                        subject_elem = hour.find("Subject")
                        subject = subject_elem.get("name", "") if subject_elem is not None else ""

                        # NOVA FUNCIONALITAT: Consolida múltiples Students (només ESO i BATX)
                        students_consolidat = self._consolidar_students(hour)
                        if students_consolidat and self._es_grup_valid(students_consolidat):
                            # Guarda versió RAW (abans d'abreviatures) i versió final
                            students_raw = self._consolidar_students_raw(hour)
                            if students_raw and self._es_grup_valid(students_raw):
                                self.grups_raw.add(students_raw)
                            self.grups.add(students_consolidat)

                        # Carrega l'aula (Room)
                        room_elem = hour.find("Room")
                        room = room_elem.get("name", "") if room_elem is not None else ""

                        tags = [tag.get("name", "") for tag in hour.findall("Activity_Tag")]

                        self.horari[dia][hora][nom] = {
                            "assignatura": subject,
                            "grup": students_consolidat,
                            "aula": room,
                            "tags": tags
                        }

            # Extreure dies i hores del horari processat (mantenint ordre del XML)
            self.dies = list(self.horari.keys())

            # Extreure hores úniques mantenint l'ordre del XML
            # Com que els dicts mantenen ordre d'inserció (Python 3.7+),
            # les hores ja estan en l'ordre correcte del XML
            hores_ordenades = []
            for dia_hores in self.horari.values():
                for hora in dia_hores.keys():
                    if hora not in hores_ordenades:
                        hores_ordenades.append(hora)
            self.hores = hores_ordenades

            # Manté self.grups com a set per compatibilitat
            # L'ordenació només es fa quan es necessita mostrar els grups
            grups_ordenats = self._ordenar_grups_personalitzat(self.grups)

            print(_("Horari carregat: {prof_count} professors, {grup_count} grups").format(prof_count=len(self.professors), grup_count=len(self.grups)))
            print(_("Dies: {dies}").format(dies=self.dies))
            print(_("Hores: {hores}").format(hores=self.hores))
            print(_("Primers 10 grups: {grups}").format(grups=grups_ordenats[:10]))

        except Exception as e:
            print(_("Error en carregar horari: {error}").format(error=e))
            raise
    def _ordenar_grups_personalitzat(self, grups):
        """Ordena grups segons ORDRE_GRUPS definit a constants"""
        from config.constants import ORDRE_GRUPS

        grups_list = list(grups)
        grups_ordenats = []
        grups_restants = grups_list.copy()

        # Primer: afegeix grups segons l'ordre predefinit
        for grup_ordre in ORDRE_GRUPS:
            if grup_ordre in grups_restants:
                grups_ordenats.append(grup_ordre)
                grups_restants.remove(grup_ordre)

        # Després: afegeix grups restants ordenats alfabèticament
        grups_restants_ordenats = sorted(grups_restants)
        grups_ordenats.extend(grups_restants_ordenats)

        return grups_ordenats

    def _es_grup_valid(self, grup: str) -> bool:
        """
        Comprova si un grup és vàlid (conté ESO o BAC/BATX)
        Exemples:
        - "BAC1A" → True
        - "ESO4A" → True
        - "1-BATX-AB" → True
        - "Professors" → False
        - "Tutoria-X" → False
        """
        if not grup:
            return False

        # Comprova si conté ESO, BAC o BATX (case-insensitive)
        grup_upper = grup.upper()
        return "ESO" in grup_upper or "BAC" in grup_upper or "BATX" in grup_upper

    def _consolidar_students_raw(self, hour_elem) -> str:
        """
        Retorna els grups RAW combinats per comes, SENSE aplicar abreviatures.
        Aquesta és la versió original abans del mapping.

        Exemples:
        - <Students name="1-BATX-A"/> + <Students name="1-BATX-B"/> → "1-BATX-A,1-BATX-B"
        - <Students name="4-ESO-A"/> + <Students name="4-ESO-B"/> + <Students name="4-ESO-C"/> → "4-ESO-A,4-ESO-B,4-ESO-C"
        """
        students_elements = hour_elem.findall("Students")

        if not students_elements:
            return ""

        if len(students_elements) == 1:
            # Un sol element, retorna tal com és
            return students_elements[0].get("name", "")

        # Múltiples elements: retorna separats per comes sense espais
        students_names = []
        for elem in students_elements:
            name = elem.get("name", "").strip()
            if name:  # Només noms no buits
                students_names.append(name)

        if not students_names:
            return ""

        if len(students_names) == 1:
            return students_names[0]

        # Retorna combinació RAW sense abreviatures, normalitzada (sense espais, ordenada)
        grups_combinats = ",".join(students_names)
        return self._normalitzar_llista_grups(grups_combinats)

    def _consolidar_students(self, hour_elem) -> str:
        """
        Retorna els grups amb abreviatures aplicades (versió final).

        Exemples:
        - <Students name="1-BATX-A"/> + <Students name="1-BATX-B"/> → "1-BATX-AB" (si està a grups.json)
        - <Students name="4-ESO-A"/> + <Students name="4-ESO-B"/> + <Students name="4-ESO-C"/> → "4-ESO-ABC"
        """
        # Obté la versió RAW
        grups_raw = self._consolidar_students_raw(hour_elem)

        if not grups_raw:
            return grups_raw

        # Aplica abreviatures
        return self._aplicar_abreviatura(grups_raw)

    def get_dia_name(self, weekday_index: int) -> str:
        """
        Converteix índex de dia de la setmana a nom del dia de l'XML
        Args:
            weekday_index: 0=Monday, 1=Tuesday, ..., 6=Sunday (independent d'idioma)
        Returns:
            Nom del dia segons l'idioma de l'XML (detectat automàticament)
        """
        # Dies laborables (0-4): retorna del XML
        if 0 <= weekday_index < len(self.dies):
            return self.dies[weekday_index]

        # Caps de setmana (5-6): detecta idioma de l'XML i retorna nom adequat
        idioma = self._detectar_idioma_xml()

        caps_setmana = {
            'ca': [_('Dissabte'), _('Diumenge')],
            'es': [_('Sábado'), _('Domingo')],
            'en': [_('Saturday'), _('Sunday')],
            'fr': [_('Samedi'), _('Dimanche')],
        }

        noms = caps_setmana.get(idioma, caps_setmana['ca'])  # Fallback a català

        if weekday_index == 5:
            return noms[0]  # Dissabte/Sábado/Saturday
        elif weekday_index == 6:
            return noms[1]  # Diumenge/Domingo/Sunday
        else:
            raise ValueError(_("Índex de dia invàlid: {index} (rang vàlid: 0-6)").format(index=weekday_index))

    def _detectar_idioma_xml(self) -> str:
        """
        Detecta l'idioma de l'XML basant-se en els noms dels dies
        Returns: 'ca', 'es', 'en', 'fr' o 'ca' (per defecte)
        """
        if not self.dies:
            return 'ca'

        primer_dia = self.dies[0].lower()

        # Detecta per primer dia (dilluns/lunes/monday/lundi)
        if 'dilluns' in primer_dia or 'dimarts' in (self.dies[1].lower() if len(self.dies) > 1 else ''):
            return 'ca'
        elif 'lunes' in primer_dia or 'martes' in (self.dies[1].lower() if len(self.dies) > 1 else ''):
            return 'es'
        elif 'monday' in primer_dia or 'tuesday' in (self.dies[1].lower() if len(self.dies) > 1 else ''):
            return 'en'
        elif 'lundi' in primer_dia or 'mardi' in (self.dies[1].lower() if len(self.dies) > 1 else ''):
            return 'fr'

        return 'ca'  # Fallback a català

    def get_activitat(self, dia: str, hora: str, professor: str) -> Optional[Dict]:
        """Obté l'activitat d'un professor"""
        return self.horari.get(dia, {}).get(hora, {}).get(professor)

    def get_jornada_professor(self, dia: str, professor: str) -> tuple:
        """Retorna (primera_hora, ultima_hora) amb activitat real del professor al dia donat.
        Només compta hores amb assignatura no buida (ignora forats).
        Retorna (None, None) si no treballa aquell dia."""
        dia_data = self.horari.get(dia, {})
        primera = None
        ultima = None
        for hora in self.hores:
            activitat = dia_data.get(hora, {}).get(professor)
            if activitat and activitat.get('assignatura', ''):
                if primera is None:
                    primera = hora
                ultima = hora
        return (primera, ultima)

    def get_professors_limits(self) -> List[str]:
        """Retorna la llista de professors amb límit aplicat"""
        return self.professors.copy()

    def te_classe(self, dia: str, hora: str, professor: str) -> bool:
        """Comprova si un professor té classe (no forat ni activitat especial)"""
        activitat = self.get_activitat(dia, hora, professor)
        if not activitat:
            return False

        # No té classe si és activitat especial
        from config.constants import NO_SUBST
        assignatura = activitat.get("assignatura", "")
        if assignatura in NO_SUBST:
            return False

        return True

    def get_grups_individuals(self) -> Set[str]:
        """
        Retorna tots els grups individuals que formen part dels grups consolidats
        Només inclou grups que contenen ESO o BATX
        """
        grups_individuals = set()

        for grup_consolidat in self.grups:
            if "," in grup_consolidat:
                # Grup múltiple: "1-BATX-AB,2-ESO-C" → ["1-BATX-AB", "2-ESO-C"]
                parts = grup_consolidat.split(",")
                for part in parts:
                    part_clean = part.strip()
                    if self._es_grup_valid(part_clean):
                        grups_individuals.update(self._expandir_grup_consolidat(part_clean))
            else:
                # Grup simple
                if self._es_grup_valid(grup_consolidat):
                    grups_individuals.update(self._expandir_grup_consolidat(grup_consolidat))

        return grups_individuals

    def _expandir_grup_consolidat(self, grup: str) -> List[str]:
        """
        Expandeix un grup consolidat en grups individuals
        Exemples:
        - "1-BATX-AB" → ["1-BATX-A", "1-BATX-B"]
        - "4-ESO-ABC" → ["4-ESO-A", "4-ESO-B", "4-ESO-C"]
        - "Grup-Especial" → ["Grup-Especial"]
        """
        base, lletres_str = self._extreure_base_lletres_multiple(grup)

        if not lletres_str:
            # No té lletres múltiples
            return [grup]

        # Té lletres múltiples: expandeix
        grups_individuals = []
        for lletra in lletres_str:
            grups_individuals.append(f"{base}{lletra}")

        return grups_individuals

    def _extreure_base_lletres_multiple(self, grup: str) -> tuple:
        """
        Extreu base i lletres múltiples d'un grup consolidat
        Exemples:
        - "1-BATX-AB" → ("1-BATX-", "AB")
        - "4-ESO-ABC" → ("4-ESO-", "ABC")
        - "Grup-Especial" → ("Grup-Especial", "")
        """
        # Patró per detectar lletres múltiples al final
        pattern = r"^(.+-)([A-Z]{2,})$"
        match = re.match(pattern, grup)

        if match:
            base = match.group(1)
            lletres = match.group(2)
            return (base, lletres)
        else:
            return (grup, "")

    def get_all_groups(self) -> Set[str]:
        """
        Retorna tots els grups RAW tal com surten al XML (camp students)
        Inclou les combinacions originals amb comes ABANS d'aplicar abreviatures
        Exemple: {"1-BATX-A,1-BATX-B", "1-ESO-A,1-ESO-B,1-ESO-C", "2-BATX-A", ...}
        """
        return self.grups_raw

    def get_grups_ordenats(self) -> List[str]:
        """
        Retorna els grups (amb abreviatures) ordenats segons ORDRE_GRUPS
        """
        return self._ordenar_grups_personalitzat(self.grups)

    def get_all_subjects(self) -> Set[str]:
        """
        Retorna totes les assignatures úniques del XML
        Exclou '-' i valors buits
        NOTA: Només inclou assignatures de professors fins al límit configurat
              (self.horari ja està filtrat durant carregar())
        """
        assignatures = set()
        for dia_hores in self.horari.values():
            for hora_profs in dia_hores.values():
                for dades in hora_profs.values():
                    assignatura = dades.get("assignatura", "")
                    if assignatura:  # Només assignatures reals (no buides)
                        assignatures.add(assignatura)
        return assignatures

    def get_all_rooms(self):
        """
        Retorna totes les aules úniques del XML

        Returns:
            Set[str]: Conjunt d'aules úniques trobades a l'horari
        """
        aules = set()
        for dia_hores in self.horari.values():
            for hora_profs in dia_hores.values():
                for dades in hora_profs.values():
                    aula = dades.get("aula", "")
                    if aula and aula.strip():  # Només aules no buides
                        aules.add(aula.strip())
        return aules

    def debug_info(self):
        """Informació de debug millorada"""
        print(_("Fitxer XML: {path}").format(path=self.xml_path))
        print(_("Professor límit configurat: {professor}").format(professor=self.ultim_professor_subs))
        print(_("Professors carregats: {count}").format(count=len(self.professors)))
        print(_("Primers 5: {professors}").format(professors=self.professors[:5]))
        if len(self.professors) > 5:
            print(_("Últims 5: {professors}").format(professors=self.professors[-5:]))
        print(_("Grups consolidats (ESO/BATX): {count}").format(count=len(self.grups)))
        print(_("Primers 10 grups: {grups}").format(grups=list(self.grups)[:10]))

        # Debug de consolidació
        grups_individuals = self.get_grups_individuals()
        print(_("Grups individuals (ESO/BATX): {count}").format(count=len(grups_individuals)))
        print(_("Primers 10 individuals: {grups}").format(grups=sorted(list(grups_individuals))[:10]))
        print(_("===================="))
