"""
Marcar o treure les absències d'un professor un dia: les files d'absència i
de servei, les cobertures de les seves classes si vigila i les de vigilant
absent. Després es treuen els substituts que ja no poden ser-ho.
"""

from datetime import datetime

from helpers import get_gestors
from repositories import SubstitucioRepository, VigilanciaRepository
from serveis.cobertures import refresca_cobertures
from serveis.dia_escolar import treu_substituts_no_valids
from serveis.vigilancia_absent import sincronitzar_vigilancies_absents


def canvia_tipus_cobertures(db, data: str, professor: str, hores, de: str, a: str) -> set:
    """Canvia el tipus de les files d'un professor a unes hores (de → a) i
    retorna les (hora, assignatura, grup) canviades. És la mateixa classe i
    el mateix substitut: només canvia si la cobreix una VIGILANCIA (el
    professor vigila un examen) o una ABSENCIA (el professor és absent)."""
    canviades = set()
    for sub in SubstitucioRepository.get_by_date(db, data):
        if sub.get("professor_absent") == professor and sub.get("hora") in hores and sub.get("tipus_absencia") == de:
            SubstitucioRepository.update(db, int(sub["id"]), {"tipus_absencia": a})
            canviades.add((sub.get("hora"), sub.get("assignatura", ""), sub.get("grup", "")))
    return canviades


def desa_absencies(
    db, data: str, professor: str, hores_absencia=None, hores_servei=None, gestors=None, dia_name: str = None
) -> dict:
    """Deixa el professor absent (ABSENCIA) i de servei (SERVEI) exactament a
    les hores donades; None vol dir que aquell tipus no es toca. `gestors`:
    (horari, absencies) si ja es tenen."""
    if gestors is None:
        _, horari, _, absencies = get_gestors(data_iso=data)
    else:
        horari, absencies = gestors
    if dia_name is None:
        dia_name = horari.get_dia_name(datetime.strptime(data, "%Y-%m-%d").weekday())
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
            sub.get("hora")
            for sub in substitucions_list
            if sub.get("professor_absent") == professor and sub.get("tipus_absencia") == tipus
        )

        hores_a_eliminar_tipus = hores_antigues_tipus - hores_noves_tipus
        hores_a_afegir_tipus = hores_noves_tipus - hores_antigues_tipus

        # Hores que es treuen. Si a alguna el professor vigila un examen, la
        # seva classe torna a cobrir-la una VIGILANCIA (la mateixa fila, amb
        # el mateix substitut); refresca_cobertures deixa després l'hora com toca.
        hores_vigilant = {
            h for h in hores_a_eliminar_tipus if professor in VigilanciaRepository.get_vigilants_per_hora(db, data, h)
        }
        canvia_tipus_cobertures(db, data, professor, hores_vigilant, tipus, "VIGILANCIA")
        for sub in substitucions_list:
            if (
                sub.get("professor_absent") == professor
                and sub.get("tipus_absencia") == tipus
                and sub.get("hora") in hores_a_eliminar_tipus - hores_vigilant
            ):
                SubstitucioRepository.delete(db, int(sub["id"]))
        if hores_vigilant:
            for hora_vigilant in hores_vigilant:
                refresca_cobertures(data, hora_vigilant, db)

        # Afegir hores noves d'aquest tipus
        if hores_a_afegir_tipus:
            # Si vigila un examen a alguna d'aquestes hores, la seva classe ja
            # la cobria una VIGILANCIA: ara que és absent, aquella mateixa
            # fila (amb el seu substitut) passa a ser l'absència.
            ja_cobertes = canvia_tipus_cobertures(db, data, professor, hores_a_afegir_tipus, "VIGILANCIA", tipus)

            absents_nous = {professor: list(hores_a_afegir_tipus)}
            absents_nous_tipus = {professor: tipus}
            subs_generades = absencies.get_substitucions_necessaries(dia_name, absents_nous, absents_nous_tipus)

            for sub in subs_generades:
                if (sub.get("hora"), sub.get("assignatura", ""), sub.get("grup", "")) in ja_cobertes:
                    continue
                sub_data = {
                    "data": data,
                    "hora": sub.get("hora", ""),
                    "professor_absent": sub.get("professor_absent", ""),
                    "assignatura": sub.get("assignatura", ""),
                    "grup": sub.get("grup", ""),
                    "aula": sub.get("aula", ""),
                    "substitut": sub.get("substitut", ""),
                    "tipus_substitut": sub.get("tipus_substitut", ""),
                    "tipus_absencia": sub.get("tipus_absencia", ""),
                    "comentaris": sub.get("comentaris", ""),
                }
                SubstitucioRepository.create(db, sub_data)

            hores_amb_substitucio = {sub.get("hora") for sub in subs_generades} | {h for h, _, _ in ja_cobertes}
            for hora in hores_a_afegir_tipus:
                if hora not in hores_amb_substitucio:
                    activitat = horari.get_activitat(dia_name, hora, professor)
                    assignatura_absent = activitat.get("assignatura", "") if activitat else ""
                    grup_absent = activitat.get("grup", "") if activitat else ""
                    aula_absent = activitat.get("aula", "") if activitat else ""
                    sub_data = {
                        "data": data,
                        "hora": hora,
                        "professor_absent": professor,
                        "assignatura": assignatura_absent,
                        "grup": grup_absent,
                        "aula": aula_absent,
                        "substitut": "",
                        "tipus_substitut": "",
                        "tipus_absencia": tipus,
                        "comentaris": "",
                    }
                    SubstitucioRepository.create(db, sub_data)

            # Sincronitzar Tipus A VIGILANCIA_ABSENT per les hores noves
            subs_actuals = SubstitucioRepository.get_by_date(db, data)
            total_tipus_a_creades += sincronitzar_vigilancies_absents(
                db, data, professor, subs_actuals, hores_a_afegir_tipus
            )

        total_afegides += len(hores_a_afegir_tipus)
        total_eliminades += len(hores_a_eliminar_tipus)

    # Sincronitzar Tipus A VIGILANCIA_ABSENT: eliminar obsolets i crear nous si cal
    totes_hores_noves = set()
    for _, hores_noves in types_a_processar:
        totes_hores_noves |= hores_noves
    subs_finals = SubstitucioRepository.get_by_date(db, data)
    sincronitzar_vigilancies_absents(db, data, professor, subs_finals, totes_hores_noves)

    # Qui ara és absent no pot continuar fent de substitut a aquelles hores.
    trets = [{**fila, "data": data} for fila in treu_substituts_no_valids(db, data)]

    return {
        "substituts_trets": trets,
        "hores_afegides": total_afegides,
        "hores_eliminades": total_eliminades,
        "hores_totals": sum(len(h) for _, h in types_a_processar),
        "vigilancies_desassignades": total_tipus_a_creades,
    }
