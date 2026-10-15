"""
Gestió de professors alliberats millorada amb estadístiques
"""
from typing import List, Set, Tuple
from datetime import date

import logging
log = logging.getLogger(__name__)

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
        self.professors_ocupats_examens = {}  # {hora: set(professors)}
        self.data_actual = None  # Data per filtrar baixes
    
    def set_data_actual(self, data: date):
        """Estableix la data actual per filtrar baixes"""
        self.data_actual = data


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
            log.warning(_("⚠️ Error en comprovar baixa de {professor}: {e}").format(professor=professor, e=e))
            return False
    
    def get_tots_disponibles(self, dia: str, hora: str, grups_sense_classe: Set[str]) -> List[Tuple[str, str, str]]:
        """
        Retorna tots els professors disponibles per substitucions
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

                # Detecta el tipus real segons l'assignatura
                tipus_real = self._detectar_tipus_activitat(assignatura)

                disponibles.append((professor, tipus_real, assignatura))

        return disponibles
    
