"""Càlculs dels informes de direcció i per professor, sense HTTP ni PDF.

Els informes compten només les substitucions «reals» de l'interval
(`es_substitucio_real`). Cada apartat de l'informe de direcció (resum, per
mes, per professor, per dia i hora, per grup i nivell) és una funció que rep
aquesta llista i es pot provar sense generar el PDF.
"""

import logging
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from core.alliberats import sense_classe
from noms import ordre_alfabetic
from pdf.domain import IntervalNoValid
from pdf.repositories import InformesRepository
from prioritats.repositories import NoSubstituirRepository
from repositories import ConfiguracioRepository, GrupsAlliberatsRepository, MasterConfigRepository
from routes.parametres import data_iso
from serveis.dia import Dia
from utils.hores import normalitzar_hora

log = logging.getLogger(__name__)

# Noms de mes per idioma. El render del PDF no re-tradueix: mostra aquestes etiquetes
# tal qual i n'abreuja els 3 primers caràcters (Novembre→Nov, Noviembre→Nov, November→Nov).
MESOS = {
    "ca": {
        1: "Gener",
        2: "Febrer",
        3: "Març",
        4: "Abril",
        5: "Maig",
        6: "Juny",
        7: "Juliol",
        8: "Agost",
        9: "Setembre",
        10: "Octubre",
        11: "Novembre",
        12: "Desembre",
    },
    "es": {
        1: "Enero",
        2: "Febrero",
        3: "Marzo",
        4: "Abril",
        5: "Mayo",
        6: "Junio",
        7: "Julio",
        8: "Agosto",
        9: "Septiembre",
        10: "Octubre",
        11: "Noviembre",
        12: "Diciembre",
    },
    "en": {
        1: "January",
        2: "February",
        3: "March",
        4: "April",
        5: "May",
        6: "June",
        7: "July",
        8: "August",
        9: "September",
        10: "October",
        11: "November",
        12: "December",
    },
}

# Nivell dels grups que no són de cap nivell de la configuració d'exàmens, i
# nivells de la configuració que no compten com a nivell propi
ALTRES = "Altres"
NIVELLS_EXCLOSOS = {"GENERAL", "RECERCA"}
# Professors de les taules professor × mes de l'informe de direcció
MAX_PROFESSORS_PER_MES = 20


def valida_interval(data_inici: str, data_final: str) -> None:
    if data_iso(data_inici) > data_iso(data_final):
        raise IntervalNoValid("La data inicial ha de ser anterior o igual a la final", codi="interval_invertit")


# ===== Les substitucions que compten =====


class _AlliberatsPerData(dict):
    """Alliberats efectius de cada data (els del dia més els per període),
    calculats només per a les dates que es consulten."""

    def __init__(self, db: Session):
        super().__init__()
        self.db = db

    def __missing__(self, data):
        valor = GrupsAlliberatsRepository.get_by_date(self.db, data) if data else {}
        self[data] = valor
        return valor


def es_substitucio_real(s: dict, no_sub: set, alliberats_per_data: dict) -> bool:
    """Una absència o un servei d'una activitat que s'havia de cobrir: amb
    assignatura que no és a «No substituir», que no és una encadenada ni una
    vigilància, i amb el professor que tenia classe (el grup no estava sense
    classe ni ell alliberat)."""
    assignatura = (s.get("assignatura") or "").strip()
    if not assignatura or assignatura in no_sub:
        return False
    if s["tipus_absencia"] in ("ENCADENADA", "VIGILANCIA"):
        return False
    grup = (s.get("grup") or "").strip()
    grups_hora = alliberats_per_data[s.get("data", "")].get(s.get("hora", ""), [])
    if sense_classe(s.get("professor_absent", ""), grup, grups_hora):
        return False
    return True


def substitucions_reals(db: Session, data_inici: str, data_final: str) -> list[dict]:
    """Les substitucions de l'interval que compten als informes, per data i
    per ordre de creació."""
    no_sub = set(NoSubstituirRepository.get_all(db))
    alliberats_per_data = _AlliberatsPerData(db)
    return [
        s
        for s in InformesRepository.substitucions_entre(db, data_inici, data_final)
        if es_substitucio_real(s, no_sub, alliberats_per_data)
    ]


# Els informes (de direcció i per professor) només compten les hores en què
# falta un professor amb classe. La vigilància de vigilant absent es pot
# resoldre reassignant-la (sense substitució), i les encadenades i les
# vigilàncies no són de ningú que falti: no hi compten (FUNCIONAMENT.md,
# apartat 6).
TIPUS_QUE_COMPTEN_ALS_INFORMES = ("ABSENCIA", "SERVEI")


def compta_als_informes(subs_reals: list[dict]) -> list[dict]:
    """Les absències i els serveis (les files que compten als informes)."""
    return [s for s in subs_reals if s["tipus_absencia"] in TIPUS_QUE_COMPTEN_ALS_INFORMES]


def _absent(s: dict) -> str:
    return (s.get("professor_absent") or "").strip()


def _substitut(s: dict) -> str:
    return (s.get("substitut") or "").strip()


def _nom_mes(s: dict, mesos_nom: dict) -> str:
    d = datetime.strptime(s["data"], "%Y-%m-%d")
    return f"{mesos_nom[d.month]} {d.year}"


# ===== Informe de direcció: un apartat per funció =====


def resum(subs_reals: list[dict], total_baixes: int) -> dict:
    """Els totals de la portada."""
    assignades = [s for s in subs_reals if _substitut(s)]
    return {
        "total_absencies": sum(1 for s in subs_reals if s["tipus_absencia"] == "ABSENCIA"),
        "total_serveis": sum(1 for s in subs_reals if s["tipus_absencia"] == "SERVEI"),
        "total_baixes": total_baixes,
        "total_substitucions": len(assignades),
        "total_necessiten": len(subs_reals),
        "cobertura_pct": len(assignades) / len(subs_reals) * 100 if subs_reals else 0,
        "dies_actius": len({s["data"] for s in subs_reals}),
    }


def per_mes(subs_reals: list[dict], mesos_nom: dict) -> list[dict]:
    """Absències, serveis i substitucions fetes de cada mes, per ordre. Un mes
    només hi surt si té alguna absència o algun servei. La cobertura es
    calcula com la global: fetes / absències + serveis."""
    per_mes_raw = defaultdict(lambda: {"absencies": 0, "serveis": 0, "substitucions": 0})
    for s in subs_reals:
        d = datetime.strptime(s["data"], "%Y-%m-%d")
        clau = (d.year, d.month)
        if s["tipus_absencia"] == "ABSENCIA":
            per_mes_raw[clau]["absencies"] += 1
        elif s["tipus_absencia"] == "SERVEI":
            per_mes_raw[clau]["serveis"] += 1
        if _substitut(s):
            per_mes_raw[clau]["substitucions"] += 1

    mesos = []
    for (any_, mes), v in sorted(per_mes_raw.items()):
        total_m = v["absencies"] + v["serveis"]
        mesos.append(
            {
                "mes": f"{mesos_nom[mes]} {any_}",
                "absencies": v["absencies"],
                "serveis": v["serveis"],
                "substitucions": v["substitucions"],
                "cobertura": v["substitucions"] / total_m * 100 if total_m else 0,
            }
        )
    return mesos


def professors_absencies(subs_reals: list[dict]) -> list[dict]:
    """Absències i serveis de cada professor absent, de més a menys (els
    empats, en l'ordre en què surten)."""
    per_professor = defaultdict(lambda: {"absencies": 0, "serveis": 0})
    for s in subs_reals:
        prof = _absent(s)
        if not prof:
            continue
        if s["tipus_absencia"] == "ABSENCIA":
            per_professor[prof]["absencies"] += 1
        elif s["tipus_absencia"] == "SERVEI":
            per_professor[prof]["serveis"] += 1
    return sorted(
        [{"nom": p, **v, "total": v["absencies"] + v["serveis"]} for p, v in per_professor.items()],
        key=lambda x: x["total"],
        reverse=True,
    )


def professors_substitucions(subs_reals: list[dict]) -> list[dict]:
    """Substitucions fetes per cada professor, de més a menys."""
    per_professor = defaultdict(int)
    for s in subs_reals:
        sub = _substitut(s)
        if sub:
            per_professor[sub] += 1
    return sorted([{"nom": p, "total": n} for p, n in per_professor.items()], key=lambda x: x["total"], reverse=True)


def per_dia_i_hora(subs_reals: list[dict]) -> tuple[dict, dict]:
    """Substitucions («absencies») i cobertes («substitucions») per hora i per
    dia de la setmana i hora. El dia és l'índex (0 = dilluns): el nom el posa
    el PDF en el seu idioma."""
    per_hora = defaultdict(lambda: {"absencies": 0, "substitucions": 0})
    per_dia_hora = defaultdict(lambda: {"absencies": 0, "substitucions": 0})
    for s in subs_reals:
        dia = datetime.strptime(s["data"], "%Y-%m-%d").weekday()
        hora = normalitzar_hora(s.get("hora", "") or "") or "Desconeguda"
        cobert = bool(_substitut(s))
        for comptador in (per_hora[hora], per_dia_hora[(dia, hora)]):
            comptador["absencies"] += 1
            if cobert:
                comptador["substitucions"] += 1
    return dict(per_hora), dict(per_dia_hora)


def per_professor_i_mes(
    subs_reals: list[dict], absents: list[str], substituts: list[str], mesos: list[str], mesos_nom: dict
) -> tuple[dict, dict, dict]:
    """Les taules professor × mes: absències i serveis dels `absents`, i
    substitucions fetes pels `substituts`. Els mesos de totes aquestes files
    són a `mesos` (per_mes hi posa tot mes amb absències, serveis o cobertes)."""
    absencies = {p: {m: 0 for m in mesos} for p in absents}
    serveis = {p: {m: 0 for m in mesos} for p in absents}
    substitucions = {p: {m: 0 for m in mesos} for p in substituts}
    for s in subs_reals:
        prof = _absent(s)
        if prof in absencies:
            if s["tipus_absencia"] == "ABSENCIA":
                absencies[prof][_nom_mes(s, mesos_nom)] += 1
            elif s["tipus_absencia"] == "SERVEI":
                serveis[prof][_nom_mes(s, mesos_nom)] += 1
        sub = _substitut(s)
        if sub in substitucions:
            substitucions[sub][_nom_mes(s, mesos_nom)] += 1
    return absencies, serveis, substitucions


def nivells_dels_grups(db: Session) -> tuple[list[str], dict[str, str]]:
    """Mapa grup -> nivell i ordre de nivells segons la configuració d'exàmens del centre.

    Font de veritat: el master config (nivells/grups/abreviatures), el mateix que gestiona
    la configuració d'exàmens. Cada centre anomena nivells i grups a la seva manera, així que
    no s'infereix res del nom del grup.

    Retorna (ordre_nivells, grup2nivell):
      - ordre_nivells: nivells en l'ordre configurat + "Altres" al final
      - grup2nivell: codi de grup -> nivell ("Altres" per GENERAL/RECERCA i desconeguts)
    """
    try:
        master = MasterConfigRepository.get_master_config(db)
    except Exception:
        log.warning("No s'ha pogut llegir la configuració de nivells", exc_info=True)
        return [ALTRES], {}

    grup2nivell = {}
    ordre_nivells = []
    for codi, data in master.get("nivells", {}).items():  # {codi: {"grups": [...], ...}}, ja ordenat
        if codi in NIVELLS_EXCLOSOS:
            nom_niv = ALTRES
        else:
            nom_niv = codi
            ordre_nivells.append(codi)
        for g in data.get("grups", []):
            grup2nivell[g] = nom_niv

    # Grups combinats (abreviatures): hereten el nivell del primer grup original conegut.
    for originals, abreviatura in master.get("abreviatures", {}).items():
        if abreviatura in grup2nivell:
            continue
        for og in (originals or "").split(","):
            og = og.strip()
            if og in grup2nivell:
                grup2nivell[abreviatura] = grup2nivell[og]
                break

    ordre_nivells.append(ALTRES)
    return ordre_nivells, grup2nivell


def _percentatge(cobertes: int, absencies: int) -> int:
    return round(cobertes / absencies * 100) if absencies else 0


def per_grup_i_nivell(
    subs_reals: list[dict],
    ordre_nivells: list[str],
    grup2nivell: dict[str, str],
    mesos: list[str],
    mesos_nom: dict,
) -> dict:
    """Substitucions i cobertes per grup (i per grup i mes) i per nivell. Les
    substitucions sense grup («-» o buit) no hi compten."""

    def nivell(grup):
        return grup2nivell.get(grup, ALTRES)

    per_grup = defaultdict(lambda: {"absencies": 0, "cobertes": 0})
    per_grup_mes = {}
    for s in subs_reals:
        grup = (s.get("grup") or "").strip()
        if not grup or grup == "-":
            continue
        per_grup[grup]["absencies"] += 1
        if _substitut(s):
            per_grup[grup]["cobertes"] += 1
        if grup not in per_grup_mes:
            per_grup_mes[grup] = {m: 0 for m in mesos}
        mes = _nom_mes(s, mesos_nom)
        if mes in mesos:  # un mes sense absències, serveis ni cobertes no hi és
            per_grup_mes[grup][mes] += 1

    per_nivell = defaultdict(lambda: {"absencies": 0, "cobertes": 0, "grups": set()})
    for grup, v in per_grup.items():
        niv = nivell(grup)
        per_nivell[niv]["absencies"] += v["absencies"]
        per_nivell[niv]["cobertes"] += v["cobertes"]
        per_nivell[niv]["grups"].add(grup)

    return {
        "per_nivell": {
            niv: {
                "absencies": v["absencies"],
                "cobertes": v["cobertes"],
                "pendents": v["absencies"] - v["cobertes"],
                "pct": _percentatge(v["cobertes"], v["absencies"]),
                "n_grups": len(v["grups"]),
            }
            for niv, v in per_nivell.items()
        },
        "ordre_nivells": ordre_nivells,
        "per_grup_mes": per_grup_mes,
        "mesos": mesos,
        "grups_ordenats": sorted(
            [
                {
                    "nom": g,
                    **v,
                    "pendents": v["absencies"] - v["cobertes"],
                    "pct": _percentatge(v["cobertes"], v["absencies"]),
                    "nivell": nivell(g),
                }
                for g, v in per_grup.items()
            ],
            key=lambda x: (ordre_nivells.index(x["nivell"]) if x["nivell"] in ordre_nivells else 99, x["nom"]),
        ),
    }


def dades_direccio(db: Session, data_inici: str, data_final: str, hores_xml: list, lang: str = "ca") -> dict:
    """Tot el que dibuixa l'informe de direcció: només les absències i els
    serveis (compta_als_informes)."""
    subs_reals = compta_als_informes(substitucions_reals(db, data_inici, data_final))
    mesos_nom = MESOS.get(lang, MESOS["ca"])
    # Només les absències cobertes que toquen l'interval
    total_baixes = InformesRepository.compta_absencies_cobertes(db, data_inici, data_final)

    mesos = per_mes(subs_reals, mesos_nom)
    mesos_ordenats = [m["mes"] for m in mesos]
    absencies = professors_absencies(subs_reals)
    substitucions = professors_substitucions(subs_reals)
    per_hora, per_dia_hora = per_dia_i_hora(subs_reals)
    per_professor_mes_abs, per_professor_mes_serv, per_substitut_mes = per_professor_i_mes(
        subs_reals,
        [p["nom"] for p in absencies[:MAX_PROFESSORS_PER_MES]],
        [p["nom"] for p in substitucions[:MAX_PROFESSORS_PER_MES]],
        mesos_ordenats,
        mesos_nom,
    )
    # Grups — nivell segons la configuració d'exàmens del centre (no s'infereix del nom)
    ordre_nivells, grup2nivell = nivells_dels_grups(db)

    return {
        "stats": resum(subs_reals, total_baixes),
        "per_mes": mesos,
        "professors_absencies": absencies,
        "professors_substitucions": substitucions,
        "per_hora": per_hora,
        "per_dia_hora": per_dia_hora,
        "per_professor_mes_abs": per_professor_mes_abs,
        "per_professor_mes_serv": per_professor_mes_serv,
        "per_substitut_mes": per_substitut_mes,
        "mesos_ordenats": mesos_ordenats,
        "hores_ordre": hores_xml,
        "grups_data": per_grup_i_nivell(subs_reals, ordre_nivells, grup2nivell, mesos_ordenats, mesos_nom),
    }


# ===== Informe per professor =====


def dades_professors(db: Session, data_inici: str, data_final: str, professor: str = None) -> list[dict]:
    """Per a cada professor (per ordre alfabètic), les seves absències i les
    substitucions que ha fet. Amb `professor`, només aquell professor (el nom
    sencer, sense distingir majúscules ni comptar els espais dels extrems).
    Només les absències i els serveis (compta_als_informes), com a l'informe
    de direcció."""
    per_absent = defaultdict(list)
    per_substitut = defaultdict(list)
    for s in compta_als_informes(substitucions_reals(db, data_inici, data_final)):
        prof = _absent(s)
        if prof:
            per_absent[prof].append(s)
        sub = _substitut(s)
        if sub:
            per_substitut[sub].append(s)

    tots = sorted(set(per_absent.keys()) | set(per_substitut.keys()), key=ordre_alfabetic)
    if professor:
        professor = professor.strip().lower()
        tots = [p for p in tots if p.lower() == professor]

    return [
        {"nom": p, "absencies": per_absent.get(p, []), "substitucions_fetes": per_substitut.get(p, [])} for p in tots
    ]


def professors_amb_activitat(db: Session, data_inici: str, data_final: str) -> list[str]:
    return [p["nom"] for p in dades_professors(db, data_inici, data_final)]


# ===== Dades comunes dels dos informes =====


def idioma(db: Session) -> str:
    try:
        return ConfiguracioRepository.get(db, "idioma") or "ca"
    except Exception:
        log.warning("No s'ha pogut llegir l'idioma del centre", exc_info=True)
        return "ca"


def nom_centre(db: Session, institucio: str) -> str:
    """Retorna el nom visible de la institució des de la config, o el slug si no hi ha."""
    try:
        name = ConfiguracioRepository.get(db, "institucio_display_name")
        return name or institucio
    except Exception:
        log.warning("No s'ha pogut llegir el nom del centre", exc_info=True)
        return institucio


def hores_xml(institucio: str, data: str) -> list:
    """Les hores, en l'ordre de l'XML, de l'horari vigent a `data`."""
    xml_path = Dia.de_text(data, institucio).xml_path
    if not xml_path or not Path(xml_path).exists():
        return []
    hores = []
    try:
        for teacher in ET.parse(xml_path).getroot().findall("Teacher"):
            for day in teacher.findall("Day"):
                for hour in day.findall("Hour"):
                    h = normalitzar_hora(hour.get("name", "").strip())
                    if h and h not in hores:
                        hores.append(h)
            if hores:
                break  # Un professor n'hi ha prou per l'ordre
    except Exception:
        log.warning("No s'ha pogut calcular l'ordre de les hores", exc_info=True)
    return hores
