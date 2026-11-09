"""
Validacions d'un dia abans de generar el PDF: conflictes (cal resoldre'ls) i
avisos. Cada comprovació és una funció que afegeix els seus missatges; l'ordre
importa, perquè dins de cada hora surten en l'ordre en què s'afegeixen.
"""

import logging
from collections import defaultdict

from grups.disponibilitat import sense_classe
from horari.domain import Dia
from i18n_setup import translate
from substitucions.domain import DiaEscolar
from substitucions.encadenades import avisos_encadenades
from substitucions.files import FilaSubstitucio
from vigilancies.analisi import analitza_vigilancies

log = logging.getLogger(__name__)


def _cobertura_ja_analitzada(sub: FilaSubstitucio, problemes: list) -> bool:
    """Evita duplicar els problemes de classes/vigilants que ha revisat l'anàlisi comuna.
    Les files antigues sense cap vigilància associada es revisen com abans.
    """
    return sub.tipus_absencia in ("VIGILANCIA", "VIGILANCIA_ABSENT") and any(
        p["professor"] == sub.professor_absent and p["hora"] == sub.hora for p in problemes
    )


def _substituts_repetits(dia: DiaEscolar, warnings: list, problemes: list) -> None:
    substituts_per_hora = defaultdict(list)
    for sub in dia.files:
        if _cobertura_ja_analitzada(sub, problemes):
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
        if _cobertura_ja_analitzada(sub, problemes):
            continue
        hora, grup = sub.hora, sub.grup
        prof_absent = sub.professor_absent
        if (sub.substitut or "").strip() or not grup.strip():
            continue
        if not sense_classe(prof_absent, grup, dia.alliberats.get(hora, [])):
            conflicts.append(
                translate("❌ {hora}: {prof_absent} ({assignatura}, {grup}) sense substitut").format(
                    hora=hora, prof_absent=prof_absent, assignatura=sub.assignatura, grup=grup
                )
            )


def _baixes_i_substituts_no_valids(dia: DiaEscolar, conflicts: list, warnings: list, problemes: list) -> None:
    # Substituts que ja no poden fer la substitució (la mateixa regla que
    # «Reassignar problemàtics»). Les cobertures de vigilàncies ja les comprova analitza_vigilancies.
    motius = [
        (sub, dia.motius_substitut(sub.substitut.strip(), sub.hora))
        for sub in dia.files
        if (sub.substitut or "").strip() and not _cobertura_ja_analitzada(sub, problemes)
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
    """`avisos_prioritat(dia)`: els avisos de substituts
    que es podrien canviar per un altre de més prioritat."""
    dia = DiaEscolar(db, Dia.de_text(data, institucio))
    conflicts, warnings = [], []

    problemes = analitza_vigilancies(dia)
    conflicts.extend(p["missatge"] for p in problemes if p["gravetat"] == "important")
    warnings.extend(p["missatge"] for p in problemes if p["gravetat"] != "important")
    _substituts_repetits(dia, warnings, problemes)
    _absencies_sense_substitut(dia, conflicts, problemes)
    _baixes_i_substituts_no_valids(dia, conflicts, warnings, problemes)
    warnings.extend(avisos_prioritat(dia))
    encadenades = avisos_encadenades(dia.files)
    warnings.extend(encadenades)

    conflicts.sort(key=_clau_hora)
    warnings.sort(key=_clau_hora)
    return {
        "problemes_vigilancies": problemes,
        "avisos_encadenades": encadenades,
        "conflicts": conflicts,
        "warnings": warnings,
        "total": len(conflicts) + len(warnings),
        "has_critical": len(conflicts) > 0,
    }
