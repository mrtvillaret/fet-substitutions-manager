"""
Vigilàncies d'examen d'un dia: configuració de la pantalla, crear, editar,
esborrar, els professors disponibles per vigilar, l'assignació automàtica,
netejar i ordenar. Cada canvi de vigilants refresca les cobertures de l'hora
(serveis/cobertures.py): un vigilant que tenia classe deixa una substitució.
"""

import random
from collections import defaultdict
from datetime import datetime

from sqlalchemy.orm import Session

from core.alliberats import sense_classe
from errors_domini import Conflicte, NoTrobat, NoValid
from repositories import (
    ConfiguracioExamenRepository,
    GrupsAlliberatsRepository,
    MasterConfigRepository,
    SubstitucioRepository,
)
from serveis.cobertures import refresca_cobertures
from serveis.dia import Dia
from vigilancies.assignacio import (
    Candidat,
    Fila,
    assigna_hora,
    es_enllac,
    get_vigilancies_afinitats,
    grups_de,
    titulars_de,
)
from vigilancies.repositories import VigilanciaRepository

PLACEHOLDER_VIGILANT = "-- selecciona vigilant --"


class ConflicteVigilancia(Conflicte):
    """Algú ha modificat la vigilància des que es va llegir: porta la versió
    actual perquè la pantalla la pugui mostrar."""

    def __init__(self, vigilancia: dict):
        super().__init__("Aquest registre ha estat modificat per un altre usuari", codi="vigilancia_modificada")
        self.vigilancia = vigilancia


def vigilants_per_hora(vigilancies_dict: dict) -> dict:
    """{hora: {vigilants}} de les vigilàncies d'un dia ({nivell: [vigilàncies]})."""
    resultat = defaultdict(set)
    for vigilancies_list in vigilancies_dict.values():
        for vig in vigilancies_list:
            hora = (vig.get("hora") or "").strip()
            vigilant = (vig.get("vigilant") or "").strip()
            if hora and vigilant and vigilant != PLACEHOLDER_VIGILANT:
                resultat[hora].add(vigilant)
    return resultat


def _payload(vig) -> dict:
    return {
        "id": str(vig.id),
        "hora": vig.hora,
        "tipus": vig.tipus,
        "grups": vig.grups,
        "aula": vig.aula,
        "vigilant": vig.vigilant or "",
        "comentaris": vig.comentaris or "",
        "nivell": vig.nivell,
        "updated_at": vig.updated_at.isoformat() if vig.updated_at else None,
    }


def _sense_placeholder(vigilant):
    """El text del desplegable («-- ... --») no és un vigilant: es desa buit."""
    return vigilant if vigilant and not vigilant.startswith("--") else ""


# ------------------------------------------------------------ configuració i llistat


def config(db: Session, dia: Dia) -> dict:
    """El que necessita la pantalla: nivells, professors i hores de l'horari
    del dia, grups i aules, i els tipus d'examen ja usats."""
    horari = dia.horari

    master_config = MasterConfigRepository.get_master_config(db)

    nivells_data = master_config.get("nivells", {})
    nivells = list(nivells_data.keys())
    grups_per_nivell = {nivell: dades.get("grups", []) for nivell, dades in nivells_data.items()}
    aules = master_config.get("aules", [])

    # Si no hi ha nivells, usar defaults
    if not nivells:
        nivells = ["GENERAL", "1-ESO", "2-ESO", "3-ESO", "4-ESO", "1-BATX", "2-BATX"]

    tipus_examens_list = VigilanciaRepository.get_unique_tipus(db)

    # Assegurar que VIGILÀNCIA estigui sempre al principi
    if "VIGILÀNCIA" in tipus_examens_list:
        tipus_examens_list.remove("VIGILÀNCIA")
    tipus_examens_list.insert(0, "VIGILÀNCIA")

    return {
        "nivells": nivells,
        "professors": sorted(horari.professors),
        "hores": horari.hores,
        "grups_per_nivell": grups_per_nivell,
        "aules": [a for a in aules if a and a.strip()],
        "tipus_examens": tipus_examens_list,
        "tipus_per_nivell": {nivell: dades.get("assignatures", []) for nivell, dades in nivells_data.items()},
    }


def en_ordre(vigs: list) -> list:
    """Les vigilàncies (dicts) en l'ordre desat dins de cada hora (les hores,
    com estiguin: les ordena qui les mostra). La pantalla i el PDF."""
    return sorted(vigs, key=lambda v: (v.get("ordre") is None, v.get("ordre") or 0, int(v.get("id") or 0)))


def llista(db: Session, data: str) -> list:
    """Les vigilàncies del dia en una llista plana: per hora i, dins de cada
    hora, en l'ordre desat."""
    vigilancies_dict = VigilanciaRepository.get_by_date(db, data)
    result = [v for vigs in vigilancies_dict.values() for v in vigs]
    return sorted(en_ordre(result), key=lambda x: x["hora"])


# ------------------------------------------------------------ ordre de les files


def clau_automatica(vig) -> tuple:
    """L'ordre automàtic dins d'una hora: nivell, grup, aula (i, si empaten,
    l'ordre de creació). `vig`: una Vigilancia o el seu dict."""
    camp = (lambda k: vig.get(k)) if isinstance(vig, dict) else (lambda k: getattr(vig, k))
    return (camp("nivell") or "", camp("grups") or "", camp("aula") or "", int(camp("id") or 0))


def _per_hora(vigs) -> dict:
    blocs = defaultdict(list)
    for v in vigs:
        blocs[(v.hora or "").strip()].append(v)
    return blocs


def te_ordre_manual(vigs) -> bool:
    """Si l'ordre desat d'un dia no és l'automàtic en alguna hora (s'hi ha
    retocat a mà). Una fila sense ordre compta com al final."""
    for files in _per_hora(vigs).values():
        desat = sorted(files, key=lambda v: (v.ordre is None, v.ordre or 0, v.id))
        if [v.id for v in desat] != [v.id for v in sorted(files, key=clau_automatica)]:
            return True
    return False


def ordena_automaticament(vigs) -> None:
    """Desa l'ordre automàtic a totes les files (no fa commit)."""
    for files in _per_hora(vigs).values():
        for i, v in enumerate(sorted(files, key=clau_automatica)):
            v.ordre = i


def completa_ordre(vigs) -> None:
    """Les files sense ordre van al final del bloc de la seva hora, per ordre
    automàtic entre elles; les altres no es mouen (no fa commit)."""
    for files in _per_hora(vigs).values():
        seguent = max((v.ordre for v in files if v.ordre is not None), default=-1) + 1
        for v in sorted((v for v in files if v.ordre is None), key=clau_automatica):
            v.ordre = seguent
            seguent += 1


# ------------------------------------------------------------ disponibles


def _normalitza_param(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _clau_consulta(hora: str, tipus: str | None, grups: str | None, aula: str | None) -> str:
    if tipus:
        return f"{hora}|{tipus}|{grups or ''}|{aula or ''}"
    return hora


def _categoria_prioritat(tipus_activitat: str, ordre_prioritats: list) -> int:
    for i, categoria in enumerate(ordre_prioritats):
        if tipus_activitat in categoria:
            return i
    return len(ordre_prioritats)


def _context_disponibles(dia: Dia, db: Session, hores_consulta: set[str], necessita_titulars: bool) -> dict:
    from config.constants import ORDRE_PRIORITATS, PRIORITATS

    data = dia.iso
    horari = dia.horari
    date_obj = datetime.strptime(data, "%Y-%m-%d")
    dia_name = horari.get_dia_name(date_obj.weekday())

    vigilancies_dict = VigilanciaRepository.get_by_date(db, data)
    vigilants_hora = vigilants_per_hora(vigilancies_dict)

    substitucions_data = SubstitucioRepository.get_by_date(db, data)
    absents_per_professor = defaultdict(set)
    absents_tipus = {}
    substituts_ocupats_per_hora = defaultdict(set)
    for sub in substitucions_data:
        professor = (sub.get("professor_absent") or "").strip()
        hora_sub = (sub.get("hora") or "").strip()
        tipus_abs = (sub.get("tipus_absencia") or "ABSENCIA").strip()
        substitut = (sub.get("substitut") or "").strip()

        if hora_sub and substitut:
            substituts_ocupats_per_hora[hora_sub].add(substitut)

        if tipus_abs in ["VIGILANCIA", "ENCADENADA"]:
            continue

        if professor and hora_sub:
            if professor not in absents_tipus:
                absents_tipus[professor] = tipus_abs
            absents_per_professor[professor].add(hora_sub)

    grups_sense_classe_raw = GrupsAlliberatsRepository.get_by_date(db, data)
    grups_sense_classe_per_hora = {hora: set(grups or []) for hora, grups in grups_sense_classe_raw.items()}

    absents_coberts = dia.horari.absents_coberts  # ja no hi són: no sortiran com a disponibles

    activitats_per_hora = {}
    for hora in hores_consulta:
        activitats_per_hora[hora] = {}
        for professor in horari.professors:
            activitat = horari.get_activitat(dia_name, hora, professor) or {}
            activitats_per_hora[hora][professor] = (activitat.get("assignatura", ""), activitat.get("grup", ""))

    config_examens = files_configuracio(db) if necessita_titulars else None
    _, abreviatures, nivells = taules_de_grups(db) if necessita_titulars else (None, None, None)

    return {
        "ordre_prioritats": ORDRE_PRIORITATS,
        "prioritats": set(PRIORITATS),
        "vigilants_per_hora": vigilants_hora,
        "absents_per_professor": absents_per_professor,
        "absents_tipus": absents_tipus,
        "substituts_ocupats_per_hora": substituts_ocupats_per_hora,
        "grups_sense_classe_per_hora": grups_sense_classe_per_hora,
        "absents_coberts": absents_coberts,
        "activitats_per_hora": activitats_per_hora,
        "config_examens": config_examens,
        "abreviatures": abreviatures,
        "nivells": nivells,
        "professors_ordenats": sorted(horari.professors),
    }


def estat_a_l_hora(context: dict, hora: str, professor: str) -> dict:
    """Què fa un professor a una hora, per vigilar-hi: l'estat (DE BAIXA,
    ABSENT, ALLIBERAT, DISPONIBLE, CLASSE o LLIURE), l'activitat de l'horari i,
    si és absent, el tipus d'absència. La regla és només aquí: la fan servir els
    disponibles i l'ajuda del vigilant. `context`: el de `_context_disponibles`
    amb `hora` entre les consultades."""
    assignatura, grup = context["activitats_per_hora"].get(hora, {}).get(professor, ("", ""))
    tipus_absencia = None
    if professor in context["absents_coberts"]:
        estat = "DE BAIXA"
    elif hora in context["absents_per_professor"].get(professor, set()):
        estat = "ABSENT"
        tipus_absencia = context["absents_tipus"].get(professor, "ABSENCIA")
    elif assignatura and sense_classe(professor, grup, context["grups_sense_classe_per_hora"].get(hora, set())):
        estat = "ALLIBERAT"
    elif assignatura and not grup:
        # Una activitat sense grup: disponible si és de les prioritats (p.ex. una guàrdia)
        estat = "DISPONIBLE" if assignatura in context["prioritats"] else "LLIURE"
    elif assignatura and grup:
        estat = "CLASSE"
    else:
        estat = "LLIURE"
    return {"estat": estat, "assignatura": assignatura, "grup": grup, "tipus_absencia": tipus_absencia}


def _disponibles_de(context: dict, hora: str, tipus: str | None, grups: str | None, aula: str | None) -> list[dict]:
    ordre_prioritats = context["ordre_prioritats"]
    vigilants_assignats = context["vigilants_per_hora"].get(hora, set())
    substituts_ocupats_hora = context["substituts_ocupats_per_hora"].get(hora, set())
    config_examens = context["config_examens"]

    professors_info = []
    for professor in context["professors_ordenats"]:
        es_titular = bool(
            config_examens is not None
            and tipus
            and tipus != "VIGILÀNCIA"
            and professor
            in titulars_de(config_examens, tipus, grups or "", aula or "", context["abreviatures"], context["nivells"])[
                0
            ]
        )

        estat_hora = estat_a_l_hora(context, hora, professor)
        estat = estat_hora["estat"]
        assignatura, grup = estat_hora["assignatura"], estat_hora["grup"]
        es_substituint = professor in substituts_ocupats_hora

        base_icon = "👨‍🏫 " if es_titular else ""
        titular_text = f" (TITULAR {tipus})" if es_titular else ""

        if estat in ("DE BAIXA", "ABSENT"):
            if estat == "DE BAIXA":
                emoji, info, ordre_tipus, color = "🏥", "DE BAIXA", 6, "rgba(255, 160, 122, 0.5)"
            else:
                emoji, ordre_tipus, color = "⚠️", 5, "#FFFF00"
                info = f"absent ({estat_hora['tipus_absencia']})"
            if assignatura:
                info += f" - tenia {assignatura}"
                if grup:
                    info += f" - {grup}"
        elif estat == "ALLIBERAT":
            emoji, ordre_tipus, color = "✅", 1, "#90EE90"
            info = f"alliberat (tenia {assignatura} - {grup})"
        elif estat == "DISPONIBLE":
            emoji, info, ordre_tipus, color = "🟢", assignatura, 2, "#AFEEEE"
        elif estat == "CLASSE":
            emoji, info, ordre_tipus, color = "🔴", f"{assignatura} - {grup}", 3, "#FFDCB4"
        else:  # LLIURE
            emoji, info, ordre_tipus, color = "⚪", assignatura or "lliure", 4, "#F5F5F5"

        ja_assignat = professor in vigilants_assignats
        if ja_assignat:
            info += " [JA ASSIGNAT]"
        if es_substituint:
            info += " [SUBSTITUCIÓ]"

        if es_titular:
            color = "#ADD8E6"
            ordre_tipus = 0
        elif ja_assignat:
            color = "#A9A9A9"
        elif es_substituint:
            color = "#8B8B8B"

        categoria = _categoria_prioritat(assignatura, ordre_prioritats) if assignatura else len(ordre_prioritats)
        label = f"{base_icon}{emoji} {professor}{titular_text} ({info})"
        professors_info.append(
            {
                "value": professor,
                "label": label,
                "emoji": emoji,
                "estat": estat,
                "info": info,
                "ordre_tipus": ordre_tipus,
                "categoria": categoria,
                "color": color,
                "ja_assignat": ja_assignat,
                "es_titular": es_titular,
            }
        )

    professors_info.sort(key=lambda x: (x["ordre_tipus"], x["value"]))
    return professors_info


def disponibles(db: Session, dia: Dia, hora: str, tipus=None, grups=None, aula=None) -> list[dict]:
    """Tots els professors per a una vigilància, amb el que fan a l'hora i
    ordenats per idoneïtat (titular, alliberats, disponibles...). Amb `tipus`,
    `grups` i `aula` es marca el titular de l'examen."""
    hora_norm = (hora or "").strip()
    tipus_norm = _normalitza_param(tipus)
    grups_norm = _normalitza_param(grups)
    aula_norm = _normalitza_param(aula)

    context = _context_disponibles(
        dia=dia, db=db, hores_consulta={hora_norm}, necessita_titulars=bool(tipus_norm and tipus_norm != "VIGILÀNCIA")
    )
    return _disponibles_de(context=context, hora=hora_norm, tipus=tipus_norm, grups=grups_norm, aula=aula_norm)


def disponibles_en_bloc(db: Session, dia: Dia, consultes) -> dict:
    """El mateix que `disponibles` per a moltes consultes alhora:
    {clau de la consulta: [professors]}. Les repetides es responen un cop."""
    queries = []
    keys_seen = set()
    for query in consultes:
        hora_norm = (query.hora or "").strip()
        if not hora_norm:
            continue
        tipus_norm = _normalitza_param(query.tipus)
        grups_norm = _normalitza_param(query.grups)
        aula_norm = _normalitza_param(query.aula)
        cache_key = _clau_consulta(hora_norm, tipus_norm, grups_norm, aula_norm)
        if cache_key in keys_seen:
            continue
        keys_seen.add(cache_key)
        queries.append(
            {"hora": hora_norm, "tipus": tipus_norm, "grups": grups_norm, "aula": aula_norm, "cache_key": cache_key}
        )

    if not queries:
        return {}

    hores_consulta = {q["hora"] for q in queries}
    necessita_titulars = any(q["tipus"] and q["tipus"] != "VIGILÀNCIA" for q in queries)
    context = _context_disponibles(dia=dia, db=db, hores_consulta=hores_consulta, necessita_titulars=necessita_titulars)

    results = {}
    for query in queries:
        results[query["cache_key"]] = _disponibles_de(
            context=context, hora=query["hora"], tipus=query["tipus"], grups=query["grups"], aula=query["aula"]
        )
    return results


# Els estats de la regla, com els retorna l'ajuda del vigilant (la pantalla els tradueix)
CODI_ESTAT = {
    "DE BAIXA": "absencia_coberta",
    "ABSENT": "absent",
    "ALLIBERAT": "alliberat",
    "DISPONIBLE": "disponible",
    "CLASSE": "classe",
    "LLIURE": "lliure",
}


def ajuda_vigilant(db: Session, dia: Dia, hora: str, professor: str) -> dict:
    """Tot el que té un professor a una hora del dia, per a l'ajuda de la
    pantalla en passar per damunt del vigilant: l'activitat de l'horari, l'estat
    per vigilar (la mateixa regla que els disponibles), les substitucions que fa
    i les vigilàncies d'aquella hora, i quantes vigilàncies porta el dia."""
    hora = (hora or "").strip()
    context = _context_disponibles(dia=dia, db=db, hores_consulta={hora}, necessita_titulars=False)
    estat_hora = estat_a_l_hora(context, hora, professor)
    estat = CODI_ESTAT[estat_hora["estat"]]
    if estat == "lliure" and professor not in dia.horari.professors:
        estat = "fora_de_l_horari"

    activitat = None
    if estat_hora["assignatura"]:
        dia_name = dia.horari.get_dia_name(dia.data.weekday())
        aula = (dia.horari.get_activitat(dia_name, hora, professor) or {}).get("aula") or ""
        activitat = {"assignatura": estat_hora["assignatura"], "grup": estat_hora["grup"], "aula": aula}

    substitucions = [
        {
            "professor_absent": sub["professor_absent"] or "",
            "assignatura": sub["assignatura"],
            "grup": sub["grup"],
            "aula": sub["aula"],
        }
        for sub in SubstitucioRepository.get_by_date(db, dia.iso)
        if (sub.get("hora") or "").strip() == hora and (sub.get("substitut") or "").strip() == professor
    ]

    del_professor = [
        vig
        for vigs in VigilanciaRepository.get_by_date(db, dia.iso).values()
        for vig in vigs
        if (vig.get("vigilant") or "").strip() == professor
    ]
    vigilancies_hora = [
        {"id": vig["id"], "tipus": vig["tipus"] or "", "grups": vig["grups"] or "", "aula": vig["aula"] or ""}
        for vig in en_ordre(del_professor)
        if (vig.get("hora") or "").strip() == hora
    ]

    return {
        "professor": professor,
        "hora": hora,
        "estat": estat,
        "activitat": activitat,
        "tipus_absencia": estat_hora["tipus_absencia"],
        "substitucions": substitucions,
        "vigilancies_hora": vigilancies_hora,
        "vigilancies_dia": len(del_professor),
    }


# ------------------------------------------------------------ crear, editar i esborrar


def crea(db: Session, data: str, vigilancia) -> dict:
    """Desa una vigilància nova i retorna com ha quedat (amb l'id de la BD)."""
    vigilancia_data = {
        "hora": vigilancia.hora,
        "tipus": vigilancia.tipus,
        "grups": vigilancia.grups,
        "aula": vigilancia.aula,
        "vigilant": _sense_placeholder(vigilancia.vigilant),
        "comentaris": vigilancia.comentaris,
        "nivell": vigilancia.nivell,
    }

    nova_vig = VigilanciaRepository.create(db, data, vigilancia_data)
    if vigilancia.despres_de:
        _posa_despres_de(db, data, nova_vig, vigilancia.despres_de)
    refresca_cobertures(data, vigilancia.hora, db)
    db.commit()

    # ID real de la BD, el mateix que retorna el llistat. L'antic ID compost
    # "hora|nivell|posició" deixava de ser vàlid si s'afegia o s'esborrava
    # una altra vigilància de la mateixa hora (i, amb vigilants buits,
    # podia apuntar a una altra vigilància des del principi).
    return _payload(nova_vig)


def _posa_despres_de(db: Session, data: str, nova, referencia: str) -> None:
    """Mou la fila `nova` (que acaba de crear-se al final del bloc) just a sota
    de la fila `referencia`, que ha de ser de la mateixa hora (no fa commit).
    Només canvia l'ordre de les files que es mouen."""
    de_lhora = sorted(
        (v for v in VigilanciaRepository.del_dia(db, data) if v.hora == nova.hora and v.id != nova.id),
        key=lambda v: (v.ordre is None, v.ordre or 0, v.id),
    )
    posicio = next((i for i, v in enumerate(de_lhora) if str(v.id) == str(referencia)), None)
    if posicio is None:
        raise NoValid("La fila de referència no és d'aquesta hora", codi="fila_referencia_no_valida")
    de_lhora.insert(posicio + 1, nova)
    for i, v in enumerate(de_lhora):
        if v.ordre != i:
            v.ordre = i


def _comprova_versio(vig_abans, updated_at, falta: str) -> None:
    if not updated_at:
        raise NoValid(falta, codi="falta_updated_at")
    if not vig_abans:
        raise NoTrobat("Vigilància no trobada", codi="vigilancia_no_trobada")
    current_ts = vig_abans.updated_at.isoformat() if vig_abans.updated_at else None
    if updated_at != current_ts:
        raise ConflicteVigilancia(_payload(vig_abans))


def edita(db: Session, data: str, vig_id: str, edicio) -> str | None:
    """Canvia els camps que porta `edicio` i retorna el nou updated_at. Sense
    `force`, l'updated_at ha de ser el que es va llegir."""
    updates = {}
    for camp in ("hora", "tipus", "grups", "aula", "vigilant", "comentaris", "nivell"):
        valor = getattr(edicio, camp)
        if valor is not None:
            updates[camp] = _sense_placeholder(valor) if camp == "vigilant" else valor

    vig_abans = VigilanciaRepository.get_by_id(db, data, vig_id)
    # L'hora d'abans s'ha de llegir ara: update_by_id modifica aquest mateix
    # objecte, i després ja tindria l'hora nova (i la cobertura de l'hora
    # antiga no es recalculava mai)
    hora_abans = vig_abans.hora if vig_abans else None

    if not edicio.force:
        _comprova_versio(vig_abans, edicio.updated_at, "Falta el camp updated_at per comprovar conflictes")

    vig_updated = VigilanciaRepository.update_by_id(db, data, vig_id, updates)

    if not vig_updated:
        raise NoTrobat("Vigilància no trobada", codi="vigilancia_no_trobada")

    hores_refresc = set()
    if hora_abans:
        hores_refresc.add(hora_abans)
    if "hora" in updates and updates.get("hora"):
        hores_refresc.add(updates["hora"])
    for hora in hores_refresc:
        refresca_cobertures(data, hora, db)
    db.commit()

    return vig_updated.updated_at.isoformat() if vig_updated.updated_at else None


def esborra(db: Session, data: str, vig_id: str, updated_at: str = None, force: bool = False) -> None:
    vig_abans = VigilanciaRepository.get_by_id(db, data, vig_id)

    if not force:
        _comprova_versio(vig_abans, updated_at, "Falta el paràmetre updated_at per comprovar conflictes")

    if not VigilanciaRepository.delete_by_id(db, data, vig_id):
        raise NoTrobat("Vigilància no trobada", codi="vigilancia_no_trobada")

    if vig_abans and vig_abans.hora:
        refresca_cobertures(data, vig_abans.hora, db)
    db.commit()


# ------------------------------------------------------------ assignació automàtica


def _atzar() -> random.Random:
    """L'atzar que desfà els empats. Els tests el substitueixen per un amb
    llavor fixa."""
    return random.Random()


def files_configuracio(db: Session) -> list:
    """Les files de la configuració d'exàmens: [{assignatura, grup, aula, titular}]."""
    return ConfiguracioExamenRepository.get_all(db)


def taules_de_grups(db: Session):
    """De la configuració d'exàmens: {grup: nivell}, {abreviatura: [grups]} i
    {nivell: [grups]}."""
    master = MasterConfigRepository.get_master_config(db)
    nivells = {codi: list(dades.get("grups", [])) for codi, dades in master.get("nivells", {}).items()}
    nivell_de = {g: codi for codi, grups in nivells.items() for g in grups}
    abreviatures = {
        abreviatura: [g.strip() for g in originals.split(",") if g.strip()]
        for originals, abreviatura in master.get("abreviatures", {}).items()
    }
    return nivell_de, abreviatures, nivells


def calcula_assignacio(db: Session, dia: Dia, data: str, amb_guardia: bool, rng=None) -> dict:
    """L'assignació sencera del dia, hora per hora, sense desar res:
    {"vigilants": {id de la fila: professor}, "titulars": {id: titulars
    possibles}, "hora_lliure": [titulars que no s'hi han posat perquè tenien
    l'hora lliure], "sense_titular": [files sense un titular configurat, amb
    el motiu]}. Les files que ja tenen vigilant no es toquen."""
    from config.constants import ORDRE_PRIORITATS, PRIORITATS

    rng = rng or _atzar()
    core = dia.vigilancia_core(db)
    horari = dia.horari
    nom_dia = horari.get_dia_name(datetime.strptime(data, "%Y-%m-%d").weekday())
    nivell_de, abreviatures, nivells = taules_de_grups(db)
    propers = {fila["base"]: fila["ordre"] for fila in get_vigilancies_afinitats(db)}
    config = files_configuracio(db)
    n_categories = len(ORDRE_PRIORITATS) + 1

    per_hora = defaultdict(list)
    for vig in llista(db, data):
        per_hora[(vig.get("hora") or "").strip()].append(vig)

    vigilants, titulars, hora_lliure, sense_titular = {}, {}, [], []
    for hora in sorted(per_hora):
        files_hora = per_hora[hora]
        for v in files_hora:
            if v.get("tipus") == "VIGILÀNCIA":
                continue
            possibles, motiu = titulars_de(
                config, v.get("tipus", ""), v.get("grups", ""), v.get("aula", ""), abreviatures, nivells
            )
            titulars[v["id"]] = possibles
            if motiu:
                sense_titular.append(
                    {
                        "vigilancia_id": v["id"],
                        "hora": hora,
                        "grups": v.get("grups", ""),
                        "tipus": v.get("tipus", ""),
                        "motiu": motiu,
                    }
                )
        ocupats = {
            (v.get("vigilant") or "").strip()
            for v in files_hora
            if _sense_placeholder((v.get("vigilant") or "").strip())
        }
        lliures = [v for v in files_hora if not _sense_placeholder((v.get("vigilant") or "").strip())]
        if not lliures:
            continue
        grups_hora = core.grups_sense_classe.get(hora, []) if isinstance(core.grups_sense_classe, dict) else []

        candidats, sense_activitat = [], set()
        for professor in sorted(horari.professors):
            if professor in ocupats or hora in core.absents_actuals.get(professor, []):
                continue
            activitat = horari.get_activitat(nom_dia, hora, professor) or {}
            assignatura, grup = activitat.get("assignatura", ""), activitat.get("grup", "")
            if (grup or assignatura) and sense_classe(professor, grup, grups_hora):
                alliberat, tipus = True, "alliberat"
            elif assignatura in PRIORITATS and not grup:
                alliberat, tipus = False, assignatura
            else:
                if not assignatura and not grup:
                    sense_activitat.add(professor)
                continue
            grups_classe = grups_de(grup, abreviatures)
            candidats.append(
                Candidat(
                    nom=professor,
                    alliberat=alliberat,
                    grups_classe=grups_classe,
                    nivells={nivell_de[g] for g in grups_classe if g in nivell_de},
                    preferencia_guardia=(n_categories - core.get_categoria_prioritat(tipus)) * 1000
                    + PRIORITATS.get(tipus, 1),
                    autoassignable=core.is_activitat_auto_assignable(tipus),
                )
            )

        files = [
            Fila(
                id=v["id"],
                grups=grups_de(v.get("grups", ""), abreviatures, nivells),
                nivell=v.get("nivell", ""),
                titulars=titulars.get(v["id"], frozenset()),
                enllac=es_enllac(v.get("aula", "")),
            )
            for v in lliures
        ]
        triats = assigna_hora(files, candidats, propers, amb_guardia, rng)
        vigilants.update(triats)
        # Les files sense cap titular posat, amb un titular que tenia l'hora lliure
        for v in lliures:
            possibles = titulars.get(v["id"], frozenset())
            if triats.get(v["id"]) in possibles:
                continue
            for titular in sorted(possibles & sense_activitat):
                hora_lliure.append(
                    {
                        "vigilancia_id": v["id"],
                        "hora": hora,
                        "grups": v.get("grups", ""),
                        "tipus": v.get("tipus", ""),
                        "titular": titular,
                    }
                )
    return {"vigilants": vigilants, "titulars": titulars, "hora_lliure": hora_lliure, "sense_titular": sense_titular}


def _desa(db: Session, data: str, posar: dict) -> None:
    """Desa els vigilants {id: professor} i refresca les cobertures de les
    hores que han canviat."""
    hores = set()
    for vig_id, professor in posar.items():
        vig = VigilanciaRepository.update_by_id(db, data, vig_id, {"vigilant": professor})
        if vig and vig.hora:
            hores.add(vig.hora)
    for hora in sorted(hores):
        refresca_cobertures(data, hora, db)
    db.commit()


def _pendents(db: Session, data: str) -> int:
    return sum(1 for v in llista(db, data) if not _sense_placeholder((v.get("vigilant") or "").strip()))


def assigna_titulars(db: Session, dia: Dia, data: str, rng=None) -> dict:
    """Posa NOMÉS els titulars, a la fila que els toca segons l'assignació
    sencera de cada hora (un titular de diversos grups va on deixa més
    professors al seu grup). Els titulars amb l'hora lliure no s'hi posen:
    surten a `titulars_hora_lliure` perquè ho decideixi qui fa les vigilàncies.
    `vigilancies_sense_titular`: les files que la configuració d'exàmens no
    deixa definides (cap fila per al grup, o diversos titulars possibles)."""
    if not VigilanciaRepository.get_by_date(db, data):
        return {"assigned_count": 0, "remaining_count": 0, "message": f"No hi ha vigilàncies per {data}"}

    calcul = calcula_assignacio(db, dia, data, amb_guardia=False, rng=rng)
    posar = {i: p for i, p in calcul["vigilants"].items() if p in calcul["titulars"].get(i, ())}
    _desa(db, data, posar)
    assigned_count, remaining_count = len(posar), _pendents(db, data)
    return {
        "assigned_count": assigned_count,
        "remaining_count": remaining_count,
        "message": f"✅ S'han assignat {assigned_count} titulars. Queden {remaining_count} vigilàncies pendents.",
        "titulars_hora_lliure": calcul["hora_lliure"],
        "vigilancies_sense_titular": calcul["sense_titular"],
    }


def assigna_pendents(db: Session, dia: Dia, data: str, disponibles: bool = False, rng=None) -> dict:
    """Omple les vigilàncies pendents (veure vigilancies/assignacio.py): amb
    `disponibles`, també amb professors de guàrdia i altres activitats de les
    prioritats; si no, només amb alliberats (i els titulars)."""
    if not VigilanciaRepository.get_by_date(db, data):
        return {"assigned_count": 0, "remaining_count": 0, "message": f"No hi ha vigilàncies per {data}"}

    posar = calcula_assignacio(db, dia, data, amb_guardia=disponibles, rng=rng)["vigilants"]
    _desa(db, data, posar)
    assigned_count, remaining_count = len(posar), _pendents(db, data)
    tipus_text = "alliberats + disponibles" if disponibles else "alliberats"
    return {
        "assigned_count": assigned_count,
        "remaining_count": remaining_count,
        "message": f"✅ S'han assignat {assigned_count} vigilants ({tipus_text}). Queden {remaining_count} pendents.",
    }


# ------------------------------------------------------------ netejar i ordenar


def buida_vigilants(db: Session, data: str) -> int:
    """Treu tots els vigilants del dia (es queden tipus, grups i aules) i
    retorna quants n'ha tret."""
    vigilancies = VigilanciaRepository.amb_vigilant(db, data)

    hores_cleared = set()
    for vig in vigilancies:
        if vig.hora:
            hores_cleared.add(vig.hora)
        vig.vigilant = ""

    db.commit()

    for hora in sorted(hores_cleared):
        refresca_cobertures(data, hora, db)

    return len(vigilancies)


def ordena(db: Session, data: str) -> int:
    """«Ordena»: desa l'ordre automàtic (dins de cada hora, nivell, grup i
    aula) i retorna quantes files hi ha. Els retocs fets a mà es perden: la
    pantalla ho ha de confirmar abans si `ordre_manual`."""
    vigs = VigilanciaRepository.del_dia(db, data)
    if not vigs:
        raise NoTrobat(f"No hi ha vigilàncies per {data}", codi="sense_vigilancies", params={"data": data})
    ordena_automaticament(vigs)
    db.commit()
    return len(vigs)


def ordre_manual(db: Session, data: str) -> bool:
    """Si l'ordre desat del dia té retocs fets a mà (no és l'automàtic)."""
    return te_ordre_manual(VigilanciaRepository.del_dia(db, data))


def desa_ordre(db: Session, data: str, hora: str, ids: list) -> None:
    """L'ordre de les files d'una hora, tal com ve (`ids`, de la primera a
    l'última). Han de ser exactament les files d'aquella hora: una fila d'una
    altra hora és un error (400); si en falta o en sobra alguna, algú ha
    canviat el dia mentrestant (409) i cal tornar-lo a carregar."""
    hora = (hora or "").strip()
    ids = [str(i) for i in ids]
    if len(set(ids)) != len(ids):
        raise NoValid("Hi ha files repetides", codi="ordre_files_repetides")
    del_dia = {str(v.id): v for v in VigilanciaRepository.del_dia(db, data)}
    if any(i in del_dia and (del_dia[i].hora or "").strip() != hora for i in ids):
        raise NoValid("Només es poden ordenar les files d'una mateixa hora", codi="ordre_altra_hora")
    de_lhora = {i for i, v in del_dia.items() if (v.hora or "").strip() == hora}
    if set(ids) != de_lhora:
        raise Conflicte(
            "Les files d'aquesta hora han canviat: torna a carregar les vigilàncies", codi="ordre_desactualitzat"
        )
    for posicio, i in enumerate(ids):
        del_dia[i].ordre = posicio
    db.commit()
