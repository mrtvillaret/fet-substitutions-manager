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


# Professors alliberats: un professor que es queda sense alumnes encara que el
# seu grup tingui classe (p.ex. en una optativa amb diversos professors, un
# altre es queda els alumnes per fer un taller). Es desen a la mateixa llista
# per hora que els grups sense classe, amb aquest prefix, perquè arribin a tots
# els llocs on ja es consulten els grups alliberats.
PREFIX_PROFESSOR = "professor:"
# Activitats sense grup (p.ex. Reforç, un equip docent) que es poden alliberar:
# alliberen tots els professors que la fan a aquella hora.
PREFIX_ACTIVITAT = "activitat:"
# Un professor que, per defecte, està alliberat (p.ex. un reforç sense alumnes)
# però que un dia concret no ho està (aquell dia el reforç sí té alumnes).
PREFIX_OCUPAT = "ocupat:"


def clau_professor(professor: str) -> str:
    return PREFIX_PROFESSOR + professor


def es_clau_professor(valor) -> bool:
    return isinstance(valor, str) and valor.startswith(PREFIX_PROFESSOR)


def clau_activitat(activitat: str) -> str:
    return PREFIX_ACTIVITAT + activitat


def es_clau_activitat(valor) -> bool:
    return isinstance(valor, str) and valor.startswith(PREFIX_ACTIVITAT)


def clau_ocupat(professor: str) -> str:
    return PREFIX_OCUPAT + professor


def es_clau_ocupat(valor) -> bool:
    return isinstance(valor, str) and valor.startswith(PREFIX_OCUPAT)


def ocupats_de(valors) -> list:
    """Els professors que aquell dia no estan alliberats (encara que per defecte ho estiguin)."""
    return [v[len(PREFIX_OCUPAT):] for v in (valors or []) if es_clau_ocupat(v)]


def nomes_grups(valors) -> list:
    """Els grups sense classe d'una hora, sense els professors ni les activitats alliberats."""
    return [v for v in (valors or [])
            if not es_clau_professor(v) and not es_clau_activitat(v) and not es_clau_ocupat(v)]


def activitats_de(valors) -> list:
    """Les activitats alliberades d'una hora."""
    return [v[len(PREFIX_ACTIVITAT):] for v in (valors or []) if es_clau_activitat(v)]


def professors_de(valors) -> list:
    """Els professors alliberats d'una hora."""
    return [v[len(PREFIX_PROFESSOR):] for v in (valors or []) if es_clau_professor(v)]


def sense_classe(professor: str, grup: str, grups_hora) -> bool:
    """Si un professor que tenia una activitat a aquella hora no la té: perquè
    el seu grup està sense classe o perquè ell està alliberat (directament o
    per una activitat alliberada: es resol a professors en llegir els
    alliberats del dia, veure GrupsAlliberatsRepository.get_by_date)."""
    if not grups_hora:
        return False
    if grup and grup in grups_hora:
        return True
    return clau_professor(professor or "") in grups_hora


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
            from helpers import _get_institucio_actual
            instit = _get_institucio_actual()

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
        ja_alliberats = {prof for prof, _tipus, _detall in alliberats}

        for prof, tipus, detall in amb_forat:
            # Una guàrdia alliberada ja surt com a alliberat
            if prof in ja_alliberats:
                continue
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
            assignatura = activitat.get("assignatura", "")
            # Sense grup, només compta si té alguna activitat (alliberada)
            if (grup or assignatura) and sense_classe(professor, grup, grups_sense_classe):
                # Incloure l'assignatura original en el detall
                if assignatura and grup:
                    detall = _("tenia {assignatura} - {grup}").format(assignatura=assignatura, grup=grup)
                elif assignatura:  # activitat sense grup (p.ex. Reforç)
                    detall = _("tenia {assignatura}").format(assignatura=assignatura)
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
