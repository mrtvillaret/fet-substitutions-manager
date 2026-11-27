"""
Validacions d'un dia abans de generar el PDF: conflictes (cal resoldre'ls) i
avisos. Cada comprovació és una funció que afegeix els seus missatges; l'ordre
importa, perquè dins de cada hora surten en l'ordre en què s'afegeixen.
"""

import logging
import re
from collections import defaultdict
from collections.abc import Callable, Sequence
from datetime import date
from typing import cast

from grups.disponibilitat import sense_classe
from horari.domain import Dia
from i18n_setup import translate
from prioritats.repositories import NoSubstituirRepository
from substitucions.domain import DiaEscolar
from substitucions.encadenades import avisos_encadenades
from substitucions.files import FilaSubstitucio
from textos import nom_net
from vigilancies.analisi import analitza_vigilancies

log = logging.getLogger(__name__)


# Què diu ja l'anàlisi de vigilàncies d'una fila de vigilància (VIGILANCIA: la
# classe que deixa el vigilant; VIGILANCIA_ABSENT: la vigilància del vigilant
# absent): els tipus de problema que fan innecessària cada comprovació de files.
# Les files que no són de vigilància, o que l'anàlisi no ha tractat (sense cap
# vigilància associada), es revisen sempre.
_SENSE_SUBSTITUT_JA_ANALITZAT: dict[str, tuple[str, ...]] = {
    "VIGILANCIA": ("classe_sense_cobertura", "classe_coberta"),
    "VIGILANCIA_ABSENT": ("vigilant_absent_sense_cobertura", "vigilant_absent_cobert"),
}
_SUBSTITUT_ABSENT_JA_ANALITZAT: dict[str, tuple[str, ...]] = {
    "VIGILANCIA": ("classe_sense_cobertura",),
    "VIGILANCIA_ABSENT": ("vigilant_absent_sense_cobertura",),
}


def _hi_ha_problema(problemes: list, tipus: tuple[str, ...], hora: str, professor: str) -> bool:
    return any(p["tipus"] in tipus and p["hora"] == hora and p["professor"] == professor for p in problemes)


def _es_vigilancia_del_substitut(sub: FilaSubstitucio, problemes: list) -> bool:
    """Una cobertura de vigilant absent que l'anàlisi dona per bona és la vigilància
    del substitut, no una substitució: les feines repetides del substitut ja les diu
    l'anàlisi (vigilant i substitut alhora, assignat N vegades com a vigilant)."""
    return sub.tipus_absencia == "VIGILANCIA_ABSENT" and any(
        p["tipus"] == "vigilant_absent_cobert"
        and p["hora"] == sub.hora
        and p["professor"] == sub.professor_absent
        and p["cobertura_efectiva"] == nom_net(sub.substitut)
        for p in problemes
    )


def _substituts_repetits(dia: DiaEscolar, warnings: list, problemes: list) -> None:
    substituts_per_hora = defaultdict(list)
    for sub in dia.files:
        if _es_vigilancia_del_substitut(sub, problemes):
            continue
        if sub.hora and sub.substitut:
            substituts_per_hora[sub.hora].append(sub.substitut)
    for hora, substituts in substituts_per_hora.items():
        for substitut in set(substituts):
            count = substituts.count(substitut)
            if count > 1:
                warnings.append(
                    translate("🔄 {hora}: {substitut} assignat {count} vegades com a substitut").format(
                        hora=hora, substitut=substitut, count=count
                    )
                )


def _absencies_sense_substitut(dia: DiaEscolar, conflicts: list, problemes: list) -> None:
    """Només les que cal cobrir: amb grup i que el grup no estigui sense classe."""
    for sub in dia.files:
        hora, grup = sub.hora, cast(str, sub.grup)
        prof_absent = sub.professor_absent
        if (sub.substitut or "").strip() or not grup.strip():
            continue
        if _hi_ha_problema(
            problemes, _SENSE_SUBSTITUT_JA_ANALITZAT.get(sub.tipus_absencia or "", ()), hora, prof_absent
        ):
            continue
        if not sense_classe(prof_absent, grup, dia.alliberats.get(hora, [])):
            conflicts.append(
                translate("❌ {hora}: {prof_absent} ({assignatura}, {grup}) sense substitut").format(
                    hora=hora, prof_absent=prof_absent, assignatura=sub.assignatura, grup=grup
                )
            )


def _motiu_ja_analitzat(sub: FilaSubstitucio, motiu: dict, problemes: list) -> bool:
    """Un substitut absent o de baixa fa que l'anàlisi doni la classe o la vigilància
    per no coberta; la classe del substitut d'un vigilant absent, l'anàlisi la
    comprova com la de qualsevol vigilant."""
    if motiu["motiu"] in ("absent", "baixa"):
        tipus = _SUBSTITUT_ABSENT_JA_ANALITZAT.get(sub.tipus_absencia or "", ())
        return _hi_ha_problema(problemes, tipus, sub.hora, sub.professor_absent)
    if motiu["motiu"] == "classe":
        if sub.tipus_absencia == "VIGILANCIA":
            return _hi_ha_problema(problemes, ("classe_sense_cobertura",), sub.hora, sub.professor_absent)
        if _es_vigilancia_del_substitut(sub, problemes):
            classe = ("classe_sense_cobertura", "classe_coberta")
            return _hi_ha_problema(problemes, classe, sub.hora, cast(str, nom_net(sub.substitut)))
    return False


def _baixes_i_substituts_no_valids(dia: DiaEscolar, conflicts: list, warnings: list, problemes: list) -> None:
    # Substituts que ja no poden fer la substitució (la mateixa regla que
    # «Reassignar problemàtics»), tret del que ja diu l'anàlisi de vigilàncies.
    motius = [
        (sub, [m for m in dia.motius_substitut(substitut, sub.hora) if not _motiu_ja_analitzat(sub, m, problemes)])
        for sub in dia.files
        if (substitut := (sub.substitut or "").strip())
    ]
    for sub, mots in motius:
        if any(m["motiu"] == "baixa" for m in mots):
            warnings.append(
                translate("🔄 {hora}: {substitut} té una absència coberta però és assignat com a substitut").format(
                    hora=sub.hora, substitut=sub.substitut
                )
            )
    for sub, mots in motius:
        for m in mots:
            if m["motiu"] == "absent":
                conflicts.append(
                    translate("❌ {hora}: Substitut {substitut} està absent!").format(
                        hora=sub.hora, substitut=sub.substitut
                    )
                )
            elif m["motiu"] == "classe":
                warnings.append(
                    translate("⚠️ {hora}: Substitut {substitut} té classe ({assignatura_sub}, {grup_sub})").format(
                        hora=sub.hora,
                        substitut=sub.substitut,
                        assignatura_sub=m["classe_assignatura"],
                        grup_sub=m["classe_grup"],
                    )
                )


def hora_de_l_avis(avis: str, hores: Sequence[str]) -> str | None:
    """L'hora de l'horari amb què comença un avís («❌ 10:00: …», «🔄 PATI: …»),
    o None si no en té cap."""
    trobades = [hora for hora in hores if re.match(rf"\W*{re.escape(hora)}:", avis)]
    return max(trobades, key=len) if trobades else None


def ordre_de_l_horari(hores: Sequence[str]) -> Callable[[str], int]:
    """Clau d'ordenació dels avisos: l'ordre de les hores de l'horari del dia (el
    PATI al seu lloc) i, amb `sorted`, dins de cada hora l'ordre en què arriben;
    els que no són d'una hora de l'horari, al final. És l'ordre de la revisió i
    de la llista d'avisos del PDF."""
    posicio = {hora: i for i, hora in enumerate(hores)}
    return lambda avis: posicio.get(hora_de_l_avis(avis, hores) or "", len(hores))


def valida_dia(
    db, data: date, institucio: str, avisos_prioritat, *, amb_substitucions: bool, amb_vigilancies: bool
) -> dict:
    """Els avisos de les seccions triades del PDF, en l'ordre de l'horari del dia.
    `avisos_prioritat(dia)`: els avisos de substituts que es podrien canviar per
    un altre de més prioritat."""
    dia = DiaEscolar(db, Dia.del_centre(data, institucio))
    conflicts: list[str] = []
    warnings: list[str] = []

    problemes = analitza_vigilancies(dia)
    conflicts.extend(p["missatge"] for p in problemes if p["gravetat"] == "important")
    warnings.extend(p["missatge"] for p in problemes if p["gravetat"] == "avis")
    # Els informatius només surten (plegats) a la revisió: el PDF no els imprimeix
    informatius = [p["missatge"] for p in problemes if p["gravetat"] == "informacio"]
    _substituts_repetits(dia, warnings, problemes)
    _absencies_sense_substitut(dia, conflicts, problemes)
    _baixes_i_substituts_no_valids(dia, conflicts, warnings, problemes)
    warnings.extend(avisos_prioritat(dia))
    encadenades = avisos_encadenades(dia.files, NoSubstituirRepository.vigents_a(db, data))
    warnings.extend(encadenades)

    # Cada PDF porta els avisos de les seves seccions: els de l'anàlisi de
    # vigilàncies, amb les vigilàncies, excepte els de la classe que deixa el
    # vigilant (classe_*), que és una fila de substitucions; la resta, amb les
    # substitucions.
    de_vigilancies = {p["missatge"] for p in problemes if not p["tipus"].startswith("classe_")}

    def de_la_tria(avis: str) -> bool:
        return amb_vigilancies if avis in de_vigilancies else amb_substitucions

    clau = ordre_de_l_horari(dia.horari.hores if dia.horari is not None else [])
    problemes = sorted((p for p in problemes if de_la_tria(p["missatge"])), key=lambda p: clau(p["missatge"]))
    conflicts = sorted(filter(de_la_tria, conflicts), key=clau)
    warnings = sorted(filter(de_la_tria, warnings), key=clau)
    informatius = sorted(filter(de_la_tria, informatius), key=clau)
    encadenades = [avis for avis in encadenades if de_la_tria(avis)]
    return {
        "problemes_vigilancies": problemes,
        "avisos_encadenades": encadenades,
        "conflicts": conflicts,
        "warnings": warnings,
        "informatius": informatius,
        "total": len(conflicts) + len(warnings) + len(informatius),
        "has_critical": len(conflicts) > 0,
    }
