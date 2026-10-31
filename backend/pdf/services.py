"""Les dades dels informes de direcció i per professor, sense HTTP ni PDF.
Els recomptes són al mòdul comú `recomptes/`; aquí s'ajunten per a cada
informe, amb el que només fan servir els informes (nivells, mesos, idioma).
"""

import logging
import xml.etree.ElementTree as ET
from collections.abc import Collection
from pathlib import Path

from sqlalchemy.orm import Session

from pdf.repositories import InformesRepository
from recomptes.services import (
    ALTRES,
    absencies_i_serveis,
    dades_professors,
    en_ordre_de_franges,
    franges_de_l_horari,
    mesos_de,
    per_dia_i_hora,
    per_grup_i_nivell,
    per_mes,
    per_professor_i_mes,
    professors_absencies,
    professors_substitucions,
    resum,
    substitucions_fetes,
    substitucions_reals,
)
from repositories import ConfiguracioRepository, MasterConfigRepository
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

# Nivells de la configuració que no compten com a nivell propi (van a ALTRES)
NIVELLS_EXCLOSOS = {"GENERAL", "RECERCA"}
# Professors de les taules professor × mes de l'informe de direcció
MAX_PROFESSORS_PER_MES = 20


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


def dades_direccio(
    db: Session,
    data_inici: str,
    data_final: str,
    hores_xml: list,
    lang: str = "ca",
    hores: Collection[str] | None = None,
) -> dict:
    """Tot el que dibuixa l'informe de direcció: les absències, els serveis i
    la cobertura (absencies_i_serveis) i les substitucions fetes de cada
    professor (substitucions_fetes, de tots els tipus). Amb `hores`, només
    les d'aquestes franges (el filtre per hores d'Estadístiques)."""
    reals = substitucions_reals(db, data_inici, data_final, hores)
    subs_reals = absencies_i_serveis(reals)
    fetes = substitucions_fetes(db, data_inici, data_final, hores)
    mesos_nom = MESOS.get(lang, MESOS["ca"])
    # Només les absències cobertes que toquen l'interval
    total_baixes = InformesRepository.compta_absencies_cobertes(db, data_inici, data_final)

    mesos = per_mes(subs_reals, mesos_nom)
    # També els mesos amb només substitucions fetes (p. ex. vigilàncies)
    mesos_ordenats = mesos_de(subs_reals + fetes, mesos_nom)
    absencies = professors_absencies(subs_reals)
    substitucions = professors_substitucions(fetes)
    per_hora, per_dia_hora = per_dia_i_hora(subs_reals)
    per_professor_mes_abs, per_professor_mes_serv, per_substitut_mes = per_professor_i_mes(
        subs_reals,
        fetes,
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


def professors_amb_activitat(
    db: Session, data_inici: str, data_final: str, hores: Collection[str] | None = None
) -> list[str]:
    return [p["nom"] for p in dades_professors(db, data_inici, data_final, hores=hores)]


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


def hores_triades_en_ordre(db: Session, institucio: str, data_inici: str, data_final: str, hores) -> list[str]:
    """Les hores del filtre en l'ordre de les franges de l'horari de
    l'interval, com les mostra Estadístiques."""
    return en_ordre_de_franges(hores, franges_de_l_horari(db, institucio, data_inici, data_final))


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
