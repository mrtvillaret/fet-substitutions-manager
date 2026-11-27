"""
Marcar o treure les absències d'un professor un dia: les files d'absència i
de servei, les cobertures de les seves classes si vigila i les de vigilant
absent. Després es treuen els substituts que ja no poden ser-ho.
"""

from datetime import date

from substitucions.cobertures import refresca_cobertures
from substitucions.files import fila_de_proposta, fila_sense_substitut
from substitucions.reconciliacio import treu_substituts_no_valids
from substitucions.repositories import SubstitucioRepository
from substitucions.vigilancia_absent import sincronitzar_vigilancies_absents
from vigilancies.repositories import VigilanciaRepository


def canvia_tipus_cobertures(db, data: date, professor: str, hores, de: str, a: str) -> set:
    """Canvia el tipus de les files d'un professor a unes hores (de → a) i
    retorna les (hora, assignatura, grup) canviades. És la mateixa classe i
    el mateix substitut: només canvia si la cobreix una VIGILANCIA (el
    professor vigila un examen) o una ABSENCIA (el professor és absent)."""
    canviades = set()
    for sub in SubstitucioRepository.get_by_date(db, data):
        if sub.professor_absent == professor and sub.hora in hores and sub.tipus_absencia == de:
            SubstitucioRepository.update(db, int(sub.id), {"tipus_absencia": a})
            canviades.add((sub.hora, sub.assignatura, sub.grup))
    return canviades


def _treu_hores(db, data: date, professor: str, tipus: str, hores: set, files: list, gestors_cobertures) -> None:
    """Treu les `hores` del `tipus` (les files del dia, `files`, llegides abans
    de cap canvi). Si a alguna el professor vigila un examen, la seva classe
    torna a cobrir-la una VIGILANCIA (la mateixa fila, amb el mateix
    substitut); refresca_cobertures deixa després l'hora com toca."""
    hores_vigilant = {h for h in hores if professor in VigilanciaRepository.get_vigilants_per_hora(db, data, h)}
    canvia_tipus_cobertures(db, data, professor, hores_vigilant, tipus, "VIGILANCIA")
    for sub in files:
        if sub.professor_absent == professor and sub.tipus_absencia == tipus and sub.hora in hores - hores_vigilant:
            SubstitucioRepository.delete(db, int(sub.id))
    for hora_vigilant in hores_vigilant:
        refresca_cobertures(data, hora_vigilant, db, gestors=gestors_cobertures)


def _afegeix_hores(db, data: date, professor: str, tipus: str, hores: set, gestors) -> int:
    """Afegeix les `hores` del `tipus`: les substitucions que calen i, a les
    hores que no en generen cap, una fila sense substitut. Retorna quantes
    vigilàncies del professor han quedat sense vigilant (VIGILANCIA_ABSENT)."""
    horari, absencies = gestors
    dia_name = horari.get_dia_name(data.weekday())
    # Si vigila un examen a alguna d'aquestes hores, la seva classe ja
    # la cobria una VIGILANCIA: ara que és absent, aquella mateixa
    # fila (amb el seu substitut) passa a ser l'absència.
    ja_cobertes = canvia_tipus_cobertures(db, data, professor, hores, "VIGILANCIA", tipus)

    absents_nous = {professor: list(hores)}
    absents_nous_tipus = {(professor, hora): tipus for hora in hores}
    subs_generades = absencies.get_substitucions_necessaries(dia_name, absents_nous, absents_nous_tipus)

    for proposta in subs_generades:
        if (proposta.hora, proposta.assignatura, proposta.grup) in ja_cobertes:
            continue
        SubstitucioRepository.create(db, fila_de_proposta(data, proposta))

    hores_amb_substitucio = {proposta.hora for proposta in subs_generades} | {h for h, _, _ in ja_cobertes}
    for hora in hores:
        if hora not in hores_amb_substitucio:
            activitat = horari.get_activitat(dia_name, hora, professor)
            SubstitucioRepository.create(db, fila_sense_substitut(data, hora, professor, activitat, tipus))

    # Sincronitzar Tipus A VIGILANCIA_ABSENT per les hores noves
    subs_actuals = SubstitucioRepository.get_by_date(db, data)
    return sincronitzar_vigilancies_absents(db, data, professor, subs_actuals, hores)


def desa_absencies(
    db,
    data: date,
    professor: str,
    hores_absencia,
    hores_servei,
    gestors,
    gestors_cobertures=None,
    dia=None,
) -> dict:
    """Deixa el professor absent (ABSENCIA) i de servei (SERVEI) exactament a
    les hores donades; None vol dir que aquell tipus no es toca. `gestors`:
    (horari, absencies) del dia."""
    substitucions_list = SubstitucioRepository.get_by_date(db, data)

    types_a_processar = []
    if hores_absencia is not None:
        types_a_processar.append(("ABSENCIA", set(hores_absencia)))
    if hores_servei is not None:
        types_a_processar.append(("SERVEI", set(hores_servei)))

    total_afegides = 0
    total_eliminades = 0
    total_tipus_a_creades = 0

    for tipus, hores_noves_tipus in types_a_processar:
        # Hores antigues FILTRADES per aquest tipus concret (evita interferències entre tipus)
        hores_antigues_tipus = set(
            sub.hora for sub in substitucions_list if sub.professor_absent == professor and sub.tipus_absencia == tipus
        )

        hores_a_eliminar_tipus = hores_antigues_tipus - hores_noves_tipus
        hores_a_afegir_tipus = hores_noves_tipus - hores_antigues_tipus

        _treu_hores(db, data, professor, tipus, hores_a_eliminar_tipus, substitucions_list, gestors_cobertures)
        if hores_a_afegir_tipus:
            total_tipus_a_creades += _afegeix_hores(db, data, professor, tipus, hores_a_afegir_tipus, gestors)

        total_afegides += len(hores_a_afegir_tipus)
        total_eliminades += len(hores_a_eliminar_tipus)

    # Sincronitzar Tipus A VIGILANCIA_ABSENT: eliminar obsolets i crear nous si cal
    totes_hores_noves = set()
    for _, hores_noves in types_a_processar:
        totes_hores_noves |= hores_noves
    subs_finals = SubstitucioRepository.get_by_date(db, data)
    sincronitzar_vigilancies_absents(db, data, professor, subs_finals, totes_hores_noves)

    # Qui ara és absent no pot continuar fent de substitut a aquelles hores.
    trets = [{**fila, "data": data} for fila in treu_substituts_no_valids(db, data, dia)]

    return {
        "substituts_trets": trets,
        "hores_afegides": total_afegides,
        "hores_eliminades": total_eliminades,
        "hores_totals": sum(len(h) for _, h in types_a_processar),
        "vigilancies_desassignades": total_tipus_a_creades,
    }
