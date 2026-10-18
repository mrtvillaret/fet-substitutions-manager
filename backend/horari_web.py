"""
Gestor d'horaris XML per al backend web - Llegeix configuració de SQLite
"""
import logging
import xml.etree.ElementTree as ET
from typing import Dict, Optional, Set

log = logging.getLogger(__name__)

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
        self.grups = set()  # Grups visibles (tots menys els amagats; amb abreviatures)
        self.tots_grups = set()  # TOTS els grups detectats a l'XML (per al selector)
        self.tots_grups_raw = set()  # TOTS els grups detectats, versió RAW
        self.hores = []  # Hores extretes del XML en ordre cronològic
        self.dies = []   # Dies extrets del XML
        self._abreviatures_cache = None  # Cache d'abreviatures de la BD
        self._grups_amagats = None  # Grups amagats (llista d'exclusió; buit = cap)
        self.carregar()

    def _carregar_grups_amagats_bd(self) -> set:
        """Carrega la llista de grups amagats des de la BD (buit = no s'amaga cap)."""
        if self._grups_amagats is not None:
            return self._grups_amagats

        from database import get_db_session
        from repositories import GrupsAmagatsRepository

        try:
            with get_db_session() as db:
                self._grups_amagats = set(GrupsAmagatsRepository.get_all(db))
                return self._grups_amagats
        except Exception as e:
            log.warning(f"⚠️  Error carregant grups amagats de BD: {e}")
            self._grups_amagats = set()
            return self._grups_amagats

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
                log.debug(f"✅ Carregades {len(self._abreviatures_cache)} abreviatures de grups des de BD")
                return self._abreviatures_cache
        except Exception as e:
            log.warning(f"⚠️  Error carregant abreviatures de BD: {e}")
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
            self.tots_grups = set()
            self.tots_grups_raw = set()
            self.hores = []
            self.dies = []

            # Grups amagats (llista d'exclusió; buit = no s'amaga cap)
            grups_amagats = self._carregar_grups_amagats_bd()

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
                    log.debug(_("Aplicat límit de professor: fins '{professor}' ({count} professors)").format(professor=ultim_prof, count=index_limit))
                except ValueError:
                    log.debug(_("Professor límit '{professor}' no trobat, en carregar tots").format(professor=ultim_prof))
                    self.professors = tots_professors
            else:
                log.debug(_("Sense límit de professor o '{professor}' no trobat").format(professor=ultim_prof))
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

                        # Consolida múltiples Students d'una mateixa hora.
                        # `tots_grups` recull tot el que apareix a l'XML (per al
                        # selector de configuració). `grups` són els VISIBLES: tots
                        # menys els amagats. Cap filtre per nom (res d'ESO/BATX
                        # hardcodejat); l'amagat es fa sobre la versió RAW (estable
                        # davant canvis d'abreviatures).
                        students_consolidat = self._consolidar_students(hour)
                        if students_consolidat:
                            students_raw = self._consolidar_students_raw(hour)
                            if students_raw:
                                self.tots_grups_raw.add(students_raw)
                            self.tots_grups.add(students_consolidat)

                            clau = students_raw or students_consolidat
                            if clau not in grups_amagats:
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

            log.debug(_("Horari carregat: {prof_count} professors, {grup_count} grups").format(prof_count=len(self.professors), grup_count=len(self.grups)))

        except Exception as e:
            log.warning(_("Error en carregar horari: {error}").format(error=e))
            raise
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

