"""
Validacions d'un dia abans de generar el PDF: conflictes (cal resoldre'ls) i
avisos. Cada comprovació és una funció que afegeix els seus missatges; l'ordre
importa, perquè dins de cada hora surten en l'ordre en què s'afegeixen.
"""

import logging
from collections import defaultdict

from core.alliberats import sense_classe
from i18n_setup import translate
from serveis.dia_escolar import DiaEscolar

log = logging.getLogger(__name__)


def _per_hora(vigilancies: list) -> dict:
    per_hora = defaultdict(list)
    for v in vigilancies:
        if v.get("hora", ""):
            per_hora[v["hora"]].append(v)
    return per_hora


def _vigilancies_incompletes(dia: DiaEscolar, conflicts: list) -> None:
    for v in dia.vigilancies:
        hora, tipus = v.get("hora", ""), v.get("tipus", "")
        if not hora:
            continue
        if not (v.get("vigilant") or "").strip():
            conflicts.append(translate("❌ {hora}: {tipus} sense vigilant assignat").format(hora=hora, tipus=tipus))
        if not (v.get("aula") or "").strip():
            conflicts.append(translate("🏫 {hora}: {tipus} sense aula assignada").format(hora=hora, tipus=tipus))


def _vigilancies_duplicades(vigilancies_per_hora: dict, warnings: list) -> None:
    for hora, vigs in vigilancies_per_hora.items():
        vigilants = [v.get("vigilant") for v in vigs if v.get("vigilant")]
        for vigilant in set(vigilants):
            count = vigilants.count(vigilant)
            if count > 1:
                warnings.append(
                    translate("🔄 {hora}: {vigilant} assignat {count} vegades com a vigilant").format(
                        hora=hora, vigilant=vigilant, count=count
                    )
                )

    for hora, vigs in vigilancies_per_hora.items():
        aules = [v.get("aula") for v in vigs if v.get("aula") and v.get("aula") != "ENLLAÇ"]
        for aula in set(aules):
            if aules.count(aula) > 1:
                warnings.append(translate("🏫 {hora}: Aula {aula} duplicada").format(hora=hora, aula=aula))


class _Cobertures:
    """Qui no és a la seva hora i com està cobert, segons les files del dia."""

    def __init__(self, dia: DiaEscolar, warnings: list):
        # Absents a una hora (també els vigilants absents) i en tot el dia
        self.absents_per_hora = defaultdict(set)
        self.absents_del_dia = set()
        # {hora: {professor: substitut}}: classes de vigilants cobertes (VIGILANCIA)
        self.classes_de_vigilants = defaultdict(dict)
        # {(professor, hora): substitut}: vigilants absents coberts (VIGILANCIA_ABSENT)
        self.vigilants_absents_coberts = {}

        for sub in dia.files:
            hora = sub.get("hora", "")
            professor = sub.get("professor_absent", "")
            tipus = (sub.get("tipus_absencia") or "").upper().strip()

            if tipus == "VIGILANCIA":
                if hora and professor:
                    self.classes_de_vigilants[hora][professor] = sub.get("substitut", "").strip()
                continue
            if tipus == "VIGILANCIA_ABSENT":
                if hora and professor:
                    self.absents_per_hora[hora].add(professor)
                    self.absents_del_dia.add(professor)
                    substitut = sub.get("substitut", "").strip()
                    if substitut:
                        self.vigilants_absents_coberts[(professor, hora)] = substitut
                    else:
                        warnings.append(
                            translate("❌ {hora}: {prof} - VIGILÀNCIA sense substitut assignat").format(
                                hora=hora, prof=professor
                            )
                        )
                continue
            if tipus in ("VIGILÀNCIA", "ENCADENADA"):
                continue
            if hora and professor:
                self.absents_per_hora[hora].add(professor)
                self.absents_del_dia.add(professor)


def _vigilants(dia: DiaEscolar, vigilancies_per_hora: dict, cob: _Cobertures, warnings: list) -> None:
    """Vigilants absents (coberts o no) i vigilants que tenen classe. Per a
    vigilàncies, el grup que fa l'examen sí que allibera el professor."""
    if dia.horari is None:
        for hora, vigs in vigilancies_per_hora.items():
            for vig in vigs:
                vigilant = vig.get("vigilant", "")
                if (
                    vigilant
                    and vigilant in cob.absents_del_dia
                    and (vigilant, hora) not in cob.vigilants_absents_coberts
                ):
                    warnings.append(
                        translate("⚠️ {hora}: Vigilant {vigilant} absent sense cobertura").format(
                            hora=hora, vigilant=vigilant
                        )
                    )
        return

    for hora, vigs in vigilancies_per_hora.items():
        lliures = {v.get("grups", "") for v in vigs if v.get("grups", "")} | set(dia.alliberats.get(hora, []))
        for vig in vigs:
            vigilant = vig.get("vigilant", "")
            if not vigilant:
                continue
            if vigilant in cob.absents_per_hora.get(hora, set()):
                substitut = cob.vigilants_absents_coberts.get((vigilant, hora))
                if substitut:
                    warnings.append(
                        translate("ℹ️ {hora}: Vigilant {vigilant} absent (cobert per {substitut})").format(
                            hora=hora, vigilant=vigilant, substitut=substitut
                        )
                    )
                else:
                    warnings.append(
                        translate("⚠️ {hora}: Vigilant {vigilant} absent sense cobertura").format(
                            hora=hora, vigilant=vigilant
                        )
                    )
                continue

            activitat = dia.activitat(vigilant, hora)
            assignatura, grup = activitat.get("assignatura", ""), activitat.get("grup", "")
            if not grup.strip() or not assignatura.strip():
                continue  # guàrdia, reforç... o cap activitat: lliure
            # Només si no està lliure i la seva classe no té ja una cobertura
            if not sense_classe(vigilant, grup, lliures) and vigilant not in cob.classes_de_vigilants.get(hora, {}):
                warnings.append(
                    translate("⚠️ {hora}: Vigilant {vigilant} té classe ({assignatura}, {grup})").format(
                        hora=hora, vigilant=vigilant, assignatura=assignatura, grup=grup
                    )
                )


def _substituts_repetits(dia: DiaEscolar, vigilancies_per_hora: dict, warnings: list) -> None:
    substituts_per_hora = defaultdict(list)
    for sub in dia.files:
        if sub.get("hora", "") and sub.get("substitut", ""):
            substituts_per_hora[sub["hora"]].append(sub["substitut"])
    for hora, substituts in substituts_per_hora.items():
        for substitut in set(substituts):
            count = substituts.count(substitut)
            if count > 1:
                warnings.append(
                    translate("🔄 {hora}: {substitut} assignat {count} vegades com a substitut").format(
                        hora=hora, substitut=substitut, count=count
                    )
                )

    for hora, vigs in vigilancies_per_hora.items():
        vigilants = {v.get("vigilant", "").strip() for v in vigs if (v.get("vigilant") or "").strip()}
        substituts = {
            s.get("substitut", "").strip()
            for s in dia.files
            if s.get("hora") == hora and (s.get("substitut") or "").strip()
        }
        for professor in sorted(vigilants & substituts):
            warnings.append(
                translate("⚠️ {hora}: {professor} és vigilant i substitut alhora").format(hora=hora, professor=professor)
            )


def _absencies_sense_substitut(dia: DiaEscolar, conflicts: list) -> None:
    """Només les que cal cobrir: amb grup i que el grup no estigui sense classe."""
    for sub in dia.files:
        hora, grup = sub.get("hora", ""), sub.get("grup", "")
        prof_absent = sub.get("professor_absent", "")
        if (sub.get("substitut") or "").strip() or not grup.strip():
            continue
        if not sense_classe(prof_absent, grup, dia.alliberats.get(hora, [])):
            conflicts.append(
                translate("❌ {hora}: {prof_absent} ({assignatura}, {grup}) sense substitut").format(
                    hora=hora, prof_absent=prof_absent, assignatura=sub.get("assignatura", ""), grup=grup
                )
            )


def _baixes_i_substituts_no_valids(
    dia: DiaEscolar, vigilancies_per_hora: dict, conflicts: list, warnings: list
) -> None:
    for hora, vigs in vigilancies_per_hora.items():
        for vig in vigs:
            vigilant = vig.get("vigilant", "")
            if vigilant and vigilant in dia.baixes:
                warnings.append(
                    translate("🔄 {hora}: {vigilant} té una absència coberta però és assignat com a vigilant").format(
                        hora=hora, vigilant=vigilant
                    )
                )

    # Substituts que ja no poden fer la substitució (la mateixa regla que
    # «Reassignar problemàtics»). Ser vigilant ja s'ha avisat a _substituts_repetits.
    motius = [
        (sub, dia.motius_substitut(sub["substitut"].strip(), sub.get("hora", "")))
        for sub in dia.files
        if (sub.get("substitut") or "").strip()
    ]
    for sub, mots in motius:
        if any(m["motiu"] == "baixa" for m in mots):
            warnings.append(
                translate("🔄 {hora}: {substitut} té una absència coberta però és assignat com a substitut").format(
                    hora=sub.get("hora", ""), substitut=sub["substitut"]
                )
            )
    for sub, mots in motius:
        for m in mots:
            if m["motiu"] == "absent":
                conflicts.append(
                    translate("❌ {hora}: Substitut {substitut} està absent!").format(
                        hora=sub.get("hora", ""), substitut=sub["substitut"]
                    )
                )
            elif m["motiu"] == "classe":
                warnings.append(
                    translate("⚠️ {hora}: Substitut {substitut} té classe ({assignatura_sub}, {grup_sub})").format(
                        hora=sub.get("hora", ""),
                        substitut=sub["substitut"],
                        assignatura_sub=m["classe_assignatura"],
                        grup_sub=m["classe_grup"],
                    )
                )


def _resum_cobertures(cob: _Cobertures, warnings: list) -> None:
    cobertes = sum(1 for profs in cob.classes_de_vigilants.values() for s in profs.values() if s)
    pendents = sum(1 for profs in cob.classes_de_vigilants.values() for s in profs.values() if not s)
    if cobertes > 0:
        warnings.append(f"ℹ️ {cobertes} vigilàncies cobertes automàticament (substitució tècnica)")
    if pendents > 0:
        warnings.append(f"❌ {pendents} vigilàncies cobertes automàticament sense substitut assignat")


def _clau_hora(text: str):
    """L'hora d'un missatge, per ordenar-los (els que no en tenen, al final)."""
    try:
        parts = text.split(":")
        if len(parts) >= 2:
            return (int(parts[0].split()[-1]), int(parts[1].split()[0]))
    except (ValueError, IndexError):
        pass
    return (99, 99)


def valida_dia(db, data: str, institucio: str, avisos_prioritat) -> dict:
    """`avisos_prioritat(dia, vigilancies_per_hora)`: els avisos de substituts
    que es podrien canviar per un altre de més prioritat."""
    dia = DiaEscolar(db, data, institucio)
    vigilancies_per_hora = _per_hora(dia.vigilancies)
    conflicts, warnings = [], []

    _vigilancies_incompletes(dia, conflicts)
    _vigilancies_duplicades(vigilancies_per_hora, warnings)
    cob = _Cobertures(dia, warnings)
    _vigilants(dia, vigilancies_per_hora, cob, warnings)
    _substituts_repetits(dia, vigilancies_per_hora, warnings)
    _absencies_sense_substitut(dia, conflicts)
    _baixes_i_substituts_no_valids(dia, vigilancies_per_hora, conflicts, warnings)
    warnings.extend(avisos_prioritat(dia, vigilancies_per_hora))
    _resum_cobertures(cob, warnings)

    conflicts.sort(key=_clau_hora)
    warnings.sort(key=_clau_hora)
    return {
        "conflicts": conflicts,
        "warnings": warnings,
        "total": len(conflicts) + len(warnings),
        "has_critical": len(conflicts) > 0,
    }
