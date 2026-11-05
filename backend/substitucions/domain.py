"""
L'estat d'un dia tal com és a la BD (substitucions, vigilàncies, alliberats,
baixes i horari), llegit un sol cop, i les regles que en depenen: per què un
substitut ja no pot fer la substitució.
"""

import logging
from collections import defaultdict
from datetime import datetime
from functools import cached_property

from core.alliberats import sense_classe
from grups.repositories import GrupsAlliberatsRepository
from helpers import get_horari
from substitucions.repositories import SubstitucioRepository
from vigilancies.repositories import VigilanciaRepository

log = logging.getLogger(__name__)

# Files que es gestionen a part de les absències del motor.
TIPUS_NO_ABSENCIA = ("VIGILANCIA", "ENCADENADA", "VIGILANCIA_ABSENT")
TIPUS_ABSENCIA_REAL = ("ABSENCIA", "SERVEI")


class DiaEscolar:
    def __init__(self, db, data: str, institucio: str = None, horari=None, *, carregador_horari=None):
        self.data = data
        self.institucio = institucio
        self.files = SubstitucioRepository.get_by_date(db, data)
        self.vigilancies = [v for vigs in VigilanciaRepository.get_by_date(db, data).values() for v in vigs]
        # Alliberats efectius per hora (grups sense classe, professors, activitats)
        self.alliberats = GrupsAlliberatsRepository.get_by_date(db, data)

        self.vigilants_per_hora = defaultdict(set)
        for vig in self.vigilancies:
            hora = (vig.get("hora") or "").strip()
            vigilant = (vig.get("vigilant") or "").strip()
            if hora and vigilant:
                self.vigilants_per_hora[hora].add(vigilant)

        # Absents de veritat (absència o servei): no les cobertures de vigilància
        self.absents_per_hora = defaultdict(set)
        for sub in self.files:
            hora = (sub.get("hora") or "").strip()
            professor = (sub.get("professor_absent") or "").strip()
            if hora and professor and sub.get("tipus_absencia") in TIPUS_ABSENCIA_REAL:
                self.absents_per_hora[hora].add(professor)

        self._carregador_horari = carregador_horari
        self._horari = horari
        self._horari_carregat = horari is not None

    @property
    def horari(self):
        """L'horari vigent aquell dia, o None si no es pot carregar."""
        if not self._horari_carregat:
            if self._carregador_horari is not None:
                # La tria manual conserva els errors del Dia que ha rebut.
                self._horari = self._carregador_horari()
                self._horari_carregat = True
                return self._horari
            self._horari_carregat = True
            try:
                self._horari = get_horari(self.institucio, data_iso=self.data)
            except Exception:
                log.warning("No s'ha pogut carregar l'horari del dia", exc_info=True)
        return self._horari

    @property
    def baixes(self) -> frozenset:
        """Els professors amb una absència coberta aquell dia (els que l'horari
        del dia ja no té)."""
        return self.horari.absents_coberts if self.horari is not None else frozenset()

    @cached_property
    def dia(self) -> str:
        """El nom del dia a l'XML (p. ex. «Dilluns»)."""
        horari = self.horari
        if horari is None:
            return ""
        return horari.get_dia_name(datetime.strptime(self.data, "%Y-%m-%d").weekday())

    def activitat(self, professor: str, hora: str) -> dict:
        if self.horari is None:
            return {}
        return self.horari.get_activitat(self.dia, hora, professor) or {}

    @cached_property
    def _absencies_motor(self) -> tuple[dict, dict, dict]:
        """Absències del motor: primer tipus i activitat per professor/hora.

        Es conserva el filtre històric de generació, diferent de les
        absències reals que valida absents_per_hora.
        """
        absents, absents_tipus, activitats_fallback = {}, {}, {}
        for sub in self.files:
            professor = sub.get("professor_absent", "")
            hora = sub.get("hora", "")
            tipus = sub.get("tipus_absencia", "") or "ABSENCIA"
            if tipus in TIPUS_NO_ABSENCIA or not professor or not hora:
                continue
            if professor not in absents:
                absents[professor] = []
                absents_tipus[professor] = tipus
            if hora not in absents[professor]:
                absents[professor].append(hora)
            activitats_fallback.setdefault(
                (professor, hora),
                {
                    "assignatura": sub.get("assignatura", ""),
                    "grup": sub.get("grup", ""),
                    "aula": sub.get("aula", ""),
                },
            )
        return absents, absents_tipus, activitats_fallback

    @property
    def absents(self) -> dict:
        return self._absencies_motor[0]

    @property
    def absents_tipus(self) -> dict:
        return self._absencies_motor[1]

    @property
    def activitats_fallback(self) -> dict:
        return self._absencies_motor[2]

    @cached_property
    def grups(self) -> dict:
        """Alliberats amb el format de conjunts que espera el motor."""
        return {hora: set(valors) if isinstance(valors, list) else valors for hora, valors in self.alliberats.items()}

    @cached_property
    def vigilants(self) -> dict:
        """Vigilants del motor amb els valors originals, com a la generació."""
        resultat = {}
        for vig in self.vigilancies:
            if vig.get("hora") and vig.get("vigilant"):
                resultat.setdefault(vig["hora"], set()).add(vig["vigilant"])
        return resultat

    def motius_substitut(
        self, substitut: str, hora: str, *, nomes=None, classe_sense_assignatura: bool = False
    ) -> list:
        """Per què `substitut` no pot fer una substitució a `hora` (llista buida
        si pot). Cada motiu: {"motiu": "vigilancia" | "baixa" | "absent"} o
        {"motiu": "classe", "classe_assignatura", "classe_grup"}: té classe i el
        seu grup no està sense classe ni ell alliberat (un examen no l'allibera)."""
        # La tria manual valida per fases per conservar la precedència dels errors.
        # Històricament també rebutja classes amb grup però sense assignatura.
        nomes = {"vigilancia", "baixa", "absent", "classe"} if nomes is None else nomes
        motius = []
        if "vigilancia" in nomes and substitut in self.vigilants_per_hora.get(hora, set()):
            motius.append({"motiu": "vigilancia"})
        if "baixa" in nomes and substitut in self.baixes:
            motius.append({"motiu": "baixa"})
        if "absent" in nomes and substitut in self.absents_per_hora.get(hora, set()):
            motius.append({"motiu": "absent"})
        if "classe" not in nomes:
            return motius
        activitat = self.activitat(substitut, hora)
        grup, assignatura = activitat.get("grup", ""), activitat.get("assignatura", "")
        if (
            (grup.strip() if classe_sense_assignatura else grup)
            and (assignatura or classe_sense_assignatura)
            and not sense_classe(substitut, grup, self.alliberats.get(hora, []))
        ):
            motius.append({"motiu": "classe", "classe_assignatura": assignatura, "classe_grup": grup})
        return motius


def substituts_no_valids(db, data: str, dia: DiaEscolar = None) -> list:
    """Les files d'un dia amb un substitut que ja no pot fer la substitució
    (DiaEscolar.motius_substitut: vigila un examen, té una absència coberta, és absent o
    hi té classe). Són canvis posteriors a l'assignació: des de la pantalla no
    es pot desar un substitut que no sigui vàlid. Cada element: {id, hora,
    professor_absent, assignatura, grup, substitut} més el primer motiu."""
    dia = dia or DiaEscolar(db, data)
    resultat = []
    for sub in dia.files:
        hora = (sub.get("hora") or "").strip()
        substitut = (sub.get("substitut") or "").strip()
        if not sub.get("id") or not substitut or not hora:
            continue
        motius = dia.motius_substitut(substitut, hora)
        if motius:
            resultat.append(
                {
                    "id": sub["id"],
                    "hora": hora,
                    "professor_absent": sub.get("professor_absent", ""),
                    "assignatura": sub.get("assignatura", ""),
                    "grup": sub.get("grup", ""),
                    "substitut": substitut,
                    **motius[0],
                }
            )
    return resultat


def treu_substituts_no_valids(db, data: str, dia: DiaEscolar = None) -> list:
    """Buida el substitut de les files de substituts_no_valids() i les retorna.
    No n'hi posa cap altre: les files queden pendents. Les encadenades, d'acord
    amb els substituts que queden (substitucions/encadenades.py): hi passen tots els
    canvis d'absències i d'alliberaments."""
    from substitucions.encadenades import reconcilia_encadenades

    trets = substituts_no_valids(db, data, dia)
    for fila in trets:
        SubstitucioRepository.update(db, int(fila["id"]), {"substitut": "", "tipus_substitut": ""})
    reconcilia_encadenades(db, data)
    return trets
