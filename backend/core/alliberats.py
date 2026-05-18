"""
Gestió de professors alliberats millorada amb estadístiques
"""
from typing import List, Set, Dict, Tuple
from datetime import date
import os

try:
    from i18n_setup import translate as _
except ImportError:
    def _(text):
        return text



class GestorAlliberats:
    """Gestiona professors alliberats amb estadístiques i suport per exàmens"""

    def __init__(self, gestor_horari):
        self.horari = gestor_horari
        self.estadistiques_cache = {}  # Cache per estadístiques
        self.professors_ocupats_examens = {}  # NOVA: {hora: set(professors)}
        self.data_actual = None  # Data per filtrar baixes
    
    def set_data_actual(self, data: date):
        """Estableix la data actual per filtrar baixes"""
        self.data_actual = data

    def set_professors_ocupats_vigilancies(self, professors_ocupats: Dict[str, Set[str]]):
        """Estableix professors ocupats amb vigilàncies per hora"""
        self.professors_ocupats_examens = professors_ocupats
        # print(f"🔍 Professors ocupats amb vigilàncies: {professors_ocupats}")

    def _esta_de_baixa(self, professor: str) -> bool:
        """
        Comprova si un professor està de baixa en la data actual
        Retorna False si no hi ha data configurada
        """
        if self.data_actual is None:
            return False

        try:
            from core.baixes import gestor_baixes
            from config.settings import config
            instit = config.global_data.get("institucio") or os.getenv("APP_INSTITUCIO") or "exemple"

            return gestor_baixes.esta_de_baixa(professor, self.data_actual, instit)
        except Exception as e:
            print(_("⚠️ Error en comprovar baixa de {professor}: {e}").format(professor=professor, e=e))
            return False
    
    def get_tots_disponibles(self, dia: str, hora: str, grups_sense_classe: Set[str]) -> List[Tuple[str, str, str]]:
        """
        Retorna tots els professors disponibles per substitucions
        MODIFICAT: Mostra professors amb vigilàncies però marcats com a ocupats
        MODIFICAT: Filtra professors de baixa
        Returns: [(professor, tipus, detall), ...]
        """
        disponibles = []
        professors_ocupats_hora = self.professors_ocupats_examens.get(hora, set())

        # Professors alliberats (prioritat màxima)
        alliberats = self.get_alliberats(dia, hora, grups_sense_classe)

        for prof, tipus, detall in alliberats:
            # Filtra professors de baixa
            if self._esta_de_baixa(prof):
                continue

            if prof in professors_ocupats_hora:
                # Marca com a ocupat amb vigilància
                detall_amb_vigilancia = _("{detall} - VIGILÀNCIA").format(detall=detall)
                disponibles.append((prof, _("vigilància"), detall_amb_vigilancia))
            else:
                disponibles.append((prof, tipus, detall))

        # Professors amb forat (amb tipus correcte)
        amb_forat = self.get_disponibles_forat(dia, hora)

        for prof, tipus, detall in amb_forat:
            # Filtra professors de baixa
            if self._esta_de_baixa(prof):
                continue

            if prof in professors_ocupats_hora:
                # Marca com a ocupat amb vigilància
                detall_amb_vigilancia = _("{detall} - VIGILÀNCIA").format(detall=detall)
                disponibles.append((prof, _("vigilància"), detall_amb_vigilancia))
            else:
                disponibles.append((prof, tipus, detall))

        return disponibles
    
    def get_disponibles_amb_stats(self, dia: str, hora: str, grups_sense_classe: Set[str], 
                                 stats_substitucions: Dict[str, int] = None) -> List[Tuple[str, str, str]]:
        """
        Retorna disponibles amb estadístiques de substitucions
        MODIFICAT: Considera vigilàncies ja incorporades en get_tots_disponibles
        Returns: [(professor, tipus, detall_amb_stats), ...]
        """
        if stats_substitucions is None:
            stats_substitucions = {}
        
        disponibles = self.get_tots_disponibles(dia, hora, grups_sense_classe)
        disponibles_amb_stats = []
        
        for professor, tipus, detall in disponibles:
            # Afegeix estadístiques al detall
            num_subs = stats_substitucions.get(f"{professor}|{hora}", 0)

            if tipus == "vigilància":
                # Ja porta la informació de vigilància, només afegeix estadístiques
                detall_amb_stats = _("{detall} - {num_subs} subs").format(detall=detall, num_subs=num_subs)
            elif tipus == "alliberat":
                detall_amb_stats = _("{detall} - {num_subs} subs").format(detall=detall, num_subs=num_subs)
            else:
                detall_amb_stats = _("{detall} - {num_subs} subs").format(detall=detall, num_subs=num_subs)
            
            disponibles_amb_stats.append((professor, tipus, detall_amb_stats))
        
        return disponibles_amb_stats
    
    def is_professor_ocupat_vigilancia(self, professor: str, hora: str) -> bool:
        """Comprova si un professor està ocupat amb una vigilància"""
        professors_ocupats_hora = self.professors_ocupats_examens.get(hora, set())
        return professor in professors_ocupats_hora
    
    def debug_disponibles(self, dia: str, hora: str, grups_sense_classe: Set[str]):
        """Debug dels professors disponibles (ara mostra vigilàncies marcades)"""
        # print(f"Grups sense classe: {grups_sense_classe}")
        
        # Mostra professors ocupats amb vigilàncies
        professors_ocupats_hora = self.professors_ocupats_examens.get(hora, set())
        if professors_ocupats_hora:
            # print(f"Professors ocupats amb vigilàncies: {professors_ocupats_hora}")
            pass
        
        tots_disponibles = self.get_tots_disponibles(dia, hora, grups_sense_classe)
        # print(f"Tots disponibles: {len(tots_disponibles)}")

        for prof, tipus, detall in tots_disponibles:
            if tipus == "vigilància":
                # print(f"  - {prof} ({tipus}): {detall} ⚠️")
                pass
            else:
                # print(f"  - {prof} ({tipus}): {detall}")
                pass
        
        # print("=====================================\n")
    
    # Tots els altres mètodes romanen iguals...
    def _detectar_tipus_activitat(self, assignatura: str) -> str:
        """Retorna l'assignatura tal com és, sense mapeig"""
        return assignatura.strip()
    
    def get_alliberats(self, dia: str, hora: str, grups_sense_classe: Set[str]) -> List[Tuple[str, str, str]]:
        """
        Retorna professors alliberats per grups sense classe
        Returns: [(professor, "alliberat", "tenia Assignatura - Grup"), ...]
        """
        alliberats = []

        if not grups_sense_classe:
            return alliberats

        hora_data = self.horari.horari.get(dia, {}).get(hora, {})

        for professor, activitat in hora_data.items():
            grup = activitat.get("grup", "")
            if grup in grups_sense_classe:
                # Incloure l'assignatura original en el detall
                assignatura = activitat.get("assignatura", "")
                if assignatura:  # Assignatura no buida
                    detall = _("tenia {assignatura} - {grup}").format(assignatura=assignatura, grup=grup)
                else:
                    detall = _("Grup {grup}").format(grup=grup)
                alliberats.append((professor, "alliberat", detall))

        return alliberats
    
    def get_disponibles_forat(self, dia: str, hora: str) -> List[Tuple[str, str, str]]:
        """
        Retorna professors amb forat/guàrdia amb el tipus correcte
        Returns: [(professor, tipus_real, assignatura), ...]
        """
        from config.constants import PRIORITATS

        disponibles = []
        hora_data = self.horari.horari.get(dia, {}).get(hora, {})

        for professor, activitat in hora_data.items():
            assignatura = activitat.get("assignatura", "Forat")
            grup = activitat.get("grup", "")

            # Professor disponible si:
            # Té activitat de PRIORITATS (Guàrdia, WEB, Informàtica...) SENSE grup assignat
            es_prioritat_sense_grup = assignatura in PRIORITATS and not grup

            if es_prioritat_sense_grup:
                # print(f"Professor: {professor} | Assignatura: '{assignatura}' | Grup: '{grup}' | Tags: {activitat.get('tags', [])}")

                # Detecta el tipus real segons l'assignatura
                tipus_real = self._detectar_tipus_activitat(assignatura)
                # print(f"  -> Tipus detectat: '{tipus_real}'")

                disponibles.append((professor, tipus_real, assignatura))
        # print("=====================================\n")

        return disponibles
    
    def set_estadistiques_substitucions(self, stats: Dict[str, int]):
        """Estableix les estadístiques de substitucions per hora"""
        self.estadistiques_cache = stats
    
    def get_estadistiques_professor_hora(self, professor: str, hora: str) -> int:
        """Obté el número de substitucions d'un professor a una hora"""
        key = f"{professor}|{hora}"
        return self.estadistiques_cache.get(key, 0)
    
    def actualitza_estadistiques_substitucio(self, professor: str, hora: str):
        """Actualitza les estadístiques quan s'assigna una substitució"""
        key = f"{professor}|{hora}"
        self.estadistiques_cache[key] = self.estadistiques_cache.get(key, 0) + 1
    
    def reset_estadistiques(self):
        """Reseteja les estadístiques"""
        self.estadistiques_cache.clear()
        self.professors_ocupats_examens.clear()  # Reset també vigilàncies
