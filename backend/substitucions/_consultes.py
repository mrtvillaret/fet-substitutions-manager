"""Consultes i presentació de les substitucions d'un dia."""

from collections import defaultdict

from sqlalchemy.orm import Session

from config import constants
from grups.lectures import AlliberatsDelDia
from horari.domain import Dia
from noms import ordre_alfabetic
from prioritats.memoria import categoria_de_prioritat
from prioritats.repositories import NoSubstituirRepository
from recomptes.services import fetes_del_curs_per_substitut
from substitucions.domain import DiaEscolar
from substitucions.files import ordena_per_mostrar
from substitucions.repositories import SubstitucioRepository
from substitucions.schemas import SubstitucioResponse, resposta_substitucio
from substitucions.visibilitat import es_visible_a_substitucions


def llista_substitucions(
    db: Session,
    dia: Dia,
    *,
    include_all: bool,
    ordre: str,
) -> list[SubstitucioResponse]:
    """Retorna les substitucions visibles o totes les absències editables."""
    data = dia.data
    horari = dia.horari
    substitucions_list = SubstitucioRepository.get_by_date(db, data)
    result = []

    if include_all:
        for sub in substitucions_list:
            if sub.tipus_absencia == "ENCADENADA":
                continue
            result.append(resposta_substitucio(sub))
    else:
        grups_sense_classe = AlliberatsDelDia.get_by_date(db, data)
        no_substituir = NoSubstituirRepository.vigents_a(db, data)

        for sub in substitucions_list:
            if es_visible_a_substitucions(sub, no_substituir, grups_sense_classe.get(sub.hora, [])):
                result.append(resposta_substitucio(sub))

    return ordena_per_mostrar(result, horari.hores, ordre=ordre)


def hores_professor(db: Session, dia: Dia, professor: str) -> dict:
    """Classifica les hores amb classe i les activitats no substituïbles."""
    horari = dia.horari
    dia_name = horari.get_dia_name(dia.data.weekday())
    no_substituir = NoSubstituirRepository.vigents_a(db, dia.data)

    hores_amb_classe = []
    hores_al_centre = []
    for hora in horari.hores:
        activitat = horari.get_activitat(dia_name, hora, professor)
        if not activitat:
            continue
        assignatura = activitat.get("assignatura", "")
        if not assignatura:
            continue
        if assignatura in no_substituir:
            hores_al_centre.append(hora)
        else:
            hores_amb_classe.append(hora)

    return {"hores_amb_classe": hores_amb_classe, "hores_al_centre": hores_al_centre}


def _context_disponibles(db: Session, dia: Dia) -> dict:
    """Prepara una vegada les dades comunes a totes les hores del dia."""
    estat = DiaEscolar(db, dia)
    substituts_per_hora = defaultdict(set)
    for sub in estat.files:
        if sub.hora and sub.substitut:
            substituts_per_hora[sub.hora].add(sub.substitut)

    _, horari, alliberats, _ = dia.gestors()
    dia_setmana = dia.data.weekday()
    # El «(n/total)» de cada professor: les seves substitucions fetes del curs
    # a aquesta franja de la setmana i en total, comptades a recomptes/
    fetes_per_franja, fetes_total = fetes_del_curs_per_substitut(db, dia.data)

    return {
        "get_professor_emoji": constants.get_professor_emoji,
        "vigilants_per_hora": estat.vigilants_per_hora,
        "substituts_per_hora": substituts_per_hora,
        # Absents de veritat (absència o servei): DiaEscolar.absents_per_hora
        "absents_per_hora": estat.absents_per_hora,
        "horari": horari,
        "alliberats": alliberats,
        "absents_coberts": horari.absents_coberts,
        "dia_setmana": dia_setmana,
        "dia_name": horari.get_dia_name(dia_setmana),
        "grups_sense_classe": estat.alliberats,
        "fetes_per_franja": fetes_per_franja,
        "fetes_total": fetes_total,
    }


def disponibles(db: Session, dia: Dia, hora: str, *, context: dict | None = None) -> dict:
    """Professors disponibles i ocupats, amb prioritat, estat i estadístiques.

    La ruta individual i la ruta en bloc passen sempre per aquesta funció. En
    bloc, ``context`` evita repetir la preparació comuna per cada hora.
    """
    context = context or _context_disponibles(db, dia)
    vigilants_ocupats = context["vigilants_per_hora"][hora]
    substituts_ocupats = context["substituts_per_hora"][hora]
    professors_absents = context["absents_per_hora"][hora]
    absents_coberts = context["absents_coberts"]
    disponibles_hora = context["alliberats"].get_tots_disponibles(
        context["dia_name"], hora, set(context["grups_sense_classe"].get(hora, []))
    )
    fetes_per_franja = context["fetes_per_franja"]
    fetes_total = context["fetes_total"]

    def color_i_estat(professor: str, tipus: str) -> tuple[str, str]:
        if professor in professors_absents:
            return "rgba(255, 255, 0, 0.4)", "ABSENT"
        if professor in absents_coberts:
            return "rgba(255, 160, 122, 0.5)", "DE BAIXA"
        if professor in vigilants_ocupats:
            return "rgba(138, 43, 226, 0.4)", "OCUPAT VIGILÀNCIA"
        if professor in substituts_ocupats:
            return "rgba(255, 0, 0, 0.4)", "JA ASSIGNAT"
        if tipus.lower() == "alliberat":
            return "rgba(0, 0, 255, 0.4)", "alliberat"
        return "rgba(0, 255, 0, 0.4)", "disponible"

    resultat = []
    for professor, tipus, detall in disponibles_hora:
        categoria_professor = categoria_de_prioritat(tipus)
        color, status = color_i_estat(professor, tipus)
        emoji = context["get_professor_emoji"](tipus)
        num_guardies_dia_hora = fetes_per_franja[(professor, context["dia_setmana"], hora.strip())]
        num_guardies_total = fetes_total[professor]
        stats_text = f" ({num_guardies_dia_hora}/{num_guardies_total})"

        es_absent = professor in professors_absents
        es_de_baixa = professor in absents_coberts
        es_vigilant = professor in vigilants_ocupats
        es_ja_assignat = professor in substituts_ocupats
        es_ocupat = es_absent or es_de_baixa or es_vigilant or es_ja_assignat

        indicador_alliberat = " [alliberat]" if tipus.lower() == "alliberat" else ""
        indicador_baixa = " 🏥 [DE BAIXA]" if es_de_baixa else ""
        indicador_vigilancia = " [VIGILÀNCIA]" if es_vigilant else ""
        text_display = (
            f"{emoji} {professor} ({detall}){stats_text}{indicador_alliberat}{indicador_baixa}{indicador_vigilancia}"
        )

        resultat.append(
            {
                "professor": professor,
                "tipus": tipus,
                "detall": detall,
                "emoji": emoji,
                "text_display": text_display,
                "categoria": categoria_professor,
                "color": color,
                "status": status,
                "ocupat": es_ocupat,
                "absent": es_absent,
                "de_baixa": es_de_baixa,
                "ocupat_vigilancia": es_vigilant,
                "ja_assignat": es_ja_assignat,
            }
        )

    # L'ordre del desplegable (la pantalla no el toca): a igualtat, per nom natural
    resultat.sort(key=lambda x: (x["de_baixa"], x["ocupat"], x["categoria"], ordre_alfabetic(x["professor"])))
    return {"disponibles": resultat}


def disponibles_en_bloc(db: Session, dia: Dia, hores: list[str]) -> dict:
    """El mateix resultat que :func:`disponibles` per a totes les hores."""
    context = _context_disponibles(db, dia)
    return {hora: disponibles(db, dia, hora, context=context) for hora in dict.fromkeys(hores)}
