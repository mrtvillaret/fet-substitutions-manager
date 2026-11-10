"""
L'estat d'un dia tal com és a la BD (substitucions, vigilàncies, alliberats,
baixes i horari), llegit un sol cop, i les regles que en depenen: per què un
substitut ja no pot fer la substitució.
"""

import logging
from collections import defaultdict
from functools import cached_property

from grups.disponibilitat import sense_classe
from grups.lectures import AlliberatsDelDia
from horari.domain import Dia
from substitucions.files import FilaSubstitucio
from substitucions.repositories import SubstitucioRepository
from vigilancies.files import FilaVigilancia
from vigilancies.repositories import VigilanciaRepository

log = logging.getLogger(__name__)

# Files que es gestionen a part de les absències del motor.
TIPUS_NO_ABSENCIA = ("VIGILANCIA", "ENCADENADA", "VIGILANCIA_ABSENT")
TIPUS_ABSENCIA_REAL = ("ABSENCIA", "SERVEI")


class DiaEscolar:
    def __init__(self, db, dia: Dia, *, estricte=False):
        self.dia = dia
        data = dia.iso
        self.data = data
        self.institucio = dia.institucio
        self.files: list[FilaSubstitucio] = SubstitucioRepository.get_by_date(db, data)
        self.vigilancies: list[FilaVigilancia] = [
            v for vigs in VigilanciaRepository.get_by_date(db, data).values() for v in vigs
        ]
        # Alliberats efectius per hora (grups sense classe, professors, activitats)
        self.alliberats = AlliberatsDelDia.get_by_date(db, data)

        self.vigilants_per_hora = defaultdict(set)
        for vig in self.vigilancies:
            hora = (vig.hora or "").strip()
            vigilant = (vig.vigilant or "").strip()
            if hora and vigilant:
                self.vigilants_per_hora[hora].add(vigilant)

        # Absents de veritat (absència o servei): no les cobertures de vigilància
        self.absents_per_hora = defaultdict(set)
        for sub in self.files:
            hora = (sub.hora or "").strip()
            professor = (sub.professor_absent or "").strip()
            if hora and professor and sub.tipus_absencia in TIPUS_ABSENCIA_REAL:
                self.absents_per_hora[hora].add(professor)

        self._estricte = estricte

    @property
    def horari(self):
        """L'horari del Dia; en mode estricte, propaga els errors de càrrega."""
        if hasattr(self, "_horari_carregat"):
            return self._horari_carregat
        try:
            self._horari_carregat = self.dia.horari
            return self._horari_carregat
        except Exception:
            if self._estricte:
                raise
            log.warning("No s'ha pogut carregar l'horari del dia", exc_info=True)
            return None

    @property
    def baixes(self) -> frozenset:
        """Els professors amb una absència coberta aquell dia (els que l'horari
        del dia ja no té)."""
        return self.horari.absents_coberts if self.horari is not None else frozenset()

    @property
    def nom_del_dia(self) -> str:
        """El nom del dia a l'XML (p. ex. «Dilluns»)."""
        horari = self.horari
        if horari is None:
            return ""
        return horari.get_dia_name(self.dia.data.weekday())

    def activitat(self, professor: str, hora: str) -> dict:
        if self.horari is None:
            return {}
        return self.horari.get_activitat(self.nom_del_dia, hora, professor) or {}

    def professor_a_horari(self, professor: str) -> bool | None:
        """Pertany a l'XML del dia, sense el límit dels candidats ni les baixes.

        Sense horari no es pot saber: no s'ha de declarar ningú fora de l'XML.
        Les absències cobertes tenen el seu motiu propi, «baixa».
        """
        horari = self.horari
        return professor in horari.tots_professors if horari is not None else None

    @cached_property
    def _absencies_motor(self) -> tuple[dict, dict]:
        """Absències del motor: hores i primer tipus per professor.

        Es conserva el filtre històric de generació, diferent de les
        absències reals que valida absents_per_hora.
        """
        absents, absents_tipus = {}, {}
        for sub in self.files:
            professor = sub.professor_absent
            hora = sub.hora
            tipus = sub.tipus_absencia or "ABSENCIA"
            if tipus in TIPUS_NO_ABSENCIA or not professor or not hora:
                continue
            if professor not in absents:
                absents[professor] = []
                absents_tipus[professor] = tipus
            if hora not in absents[professor]:
                absents[professor].append(hora)
        return absents, absents_tipus

    @property
    def absents(self) -> dict:
        return self._absencies_motor[0]

    @property
    def absents_tipus(self) -> dict:
        return self._absencies_motor[1]

    @cached_property
    def grups(self) -> dict:
        """Alliberats amb el format de conjunts que espera el motor."""
        return {hora: set(valors) if isinstance(valors, list) else valors for hora, valors in self.alliberats.items()}

    @cached_property
    def vigilants(self) -> dict:
        """Vigilants del motor amb els valors originals, com a la generació."""
        resultat = {}
        for vig in self.vigilancies:
            if vig.hora and vig.vigilant:
                resultat.setdefault(vig.hora, set()).add(vig.vigilant)
        return resultat

    def motius_substitut(
        self, substitut: str, hora: str, *, nomes=None, classe_sense_assignatura: bool = False
    ) -> list:
        """Per què `substitut` no pot fer una substitució a `hora` (llista buida
        si pot). Cada motiu: {"motiu": "vigilancia" | "baixa" | "absent" | "fora_horari"} o
        {"motiu": "classe", "classe_assignatura", "classe_grup"}: té classe i el
        seu grup no està sense classe ni ell alliberat (un examen no l'allibera)."""
        # La tria manual valida per fases per conservar la precedència dels errors.
        # Històricament també rebutja classes amb grup però sense assignatura.
        nomes = {"vigilancia", "baixa", "absent", "classe", "fora_horari"} if nomes is None else nomes
        motius = []
        if "vigilancia" in nomes and substitut in self.vigilants_per_hora.get(hora, set()):
            motius.append({"motiu": "vigilancia"})
        if "baixa" in nomes and substitut in self.baixes:
            motius.append({"motiu": "baixa"})
        if "absent" in nomes and substitut in self.absents_per_hora.get(hora, set()):
            motius.append({"motiu": "absent"})
        if "fora_horari" in nomes and self.professor_a_horari(substitut) is False:
            motius.append({"motiu": "fora_horari"})
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
    hi té classe o ja no és a l'XML vigent). Són canvis posteriors a l'assignació: des de la pantalla no
    es pot desar un substitut que no sigui vàlid. Cada element: {id, hora,
    professor_absent, assignatura, grup, substitut} més el primer motiu."""
    dia = dia or DiaEscolar(db, Dia.de_text(data, db.info.get("institucio")))
    resultat = []
    for sub in dia.files:
        hora = (sub.hora or "").strip()
        substitut = (sub.substitut or "").strip()
        if not sub.id or not substitut or not hora:
            continue
        motius = dia.motius_substitut(substitut, hora)
        if motius:
            resultat.append(
                {
                    "id": sub.id,
                    "hora": hora,
                    "professor_absent": sub.professor_absent,
                    "assignatura": sub.assignatura,
                    "grup": sub.grup,
                    "substitut": substitut,
                    **motius[0],
                }
            )
    return resultat
