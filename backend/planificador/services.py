"""Regles del planificador d'exàmens que no executen el motor: la seva
configuració (nivells, hores marcades, durades, dates), les restriccions, els
exàmens fixats, els costos dels professors, l'últim horari generat i l'avís
de dates d'un curs anterior.

Generar i analitzar són a generacio.py; el cost d'un horari editat, a
cost.py; publicar-lo com a vigilàncies, a publicacio.py."""

import json
from datetime import date

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

import rellotge
from configuracio.repositories import ConfiguracioRepository
from configuracio_examens.repositories import ConfiguracioExamenRepository, MasterConfigRepository
from cursos.repositories import CursRepository
from database import get_data_db_session
from errors_domini import NoValid
from planificador import restriccions as regles
from planificador.alliberaments import extreure_hores_examen_des_alliberaments
from planificador.compartit.constants import DEFAULT_COST_PROFESSORS, DEFAULT_DURADA_TITULAR
from planificador.documents import (
    data_desada,
    document_iso,
    horari_amb_dates,
    llegeix_alliberaments,
    llegeix_dates,
    resultat_amb_dates,
)
from planificador.examens import examens, nivells_dels_grups
from planificador.motor.cataleg import informacio_motors
from planificador.repositories import (
    SCHEDULER_ALLIBERAMENTS_KEY,
    SCHEDULER_DATES_KEY,
    SCHEDULER_DURADA_EXAMEN_KEY,
    SCHEDULER_DURADA_KEY,
    SCHEDULER_DURADES_GRUPS_KEY,
    SCHEDULER_NIVELLS_KEY,
    SCHEDULER_ULTIM_RESULTAT_KEY,
    TIPUS_FIXATS,
    CostProfessorRepository,
    RestriccioRepository,
    llegeix_json,
)

# ---------------------------------------------------------------- motors


def motors() -> dict:
    """Els motors disponibles amb els seus paràmetres i valors per defecte."""

    return {"motors": informacio_motors()}


# ---------------------------------------------------------------- configuració


def config(db: Session) -> dict:
    master = MasterConfigRepository.get_master_config(db)
    d = int(ConfiguracioRepository.get(db, SCHEDULER_DURADA_KEY) or DEFAULT_DURADA_TITULAR)
    de_raw = ConfiguracioRepository.get(db, SCHEDULER_DURADA_EXAMEN_KEY)
    de = int(de_raw) if de_raw else d  # per defecte = durada_titular
    n = llegeix_json(db, SCHEDULER_NIVELLS_KEY, [])
    alliberaments = llegeix_alliberaments(db)
    durades_grups = llegeix_json(db, SCHEDULER_DURADES_GRUPS_KEY, None) or []
    nivells = list(master.get("nivells", {}).keys())
    # La selecció desada pot ser d'un horari anterior: els nivells que ja no
    # existeixen sortirien al selector com a `null` i amb pestanyes pròpies.
    n = [nivell for nivell in n if nivell in nivells]
    alliberaments = {nivell: v for nivell, v in alliberaments.items() if nivell in nivells}
    h, hpn = extreure_hores_examen_des_alliberaments(alliberaments)
    return {
        "nivells": nivells,
        "hores_examen": h,
        "durada_titular": d,
        "durada_examen": de,
        "nivells_seleccionats": n,
        "hores_per_nivell": hpn,
        "alliberaments_per_nivell": alliberaments,
        "durades_grups": durades_grups,
    }


def desa_config(db: Session, payload: dict) -> None:
    """Desa els camps que hi són, tots o cap (un sol commit)."""
    claus = {
        "durada_titular": (SCHEDULER_DURADA_KEY, "integer"),
        "durada_examen": (SCHEDULER_DURADA_EXAMEN_KEY, "integer"),
        "nivells_actius": (SCHEDULER_NIVELLS_KEY, "json"),
        "alliberaments_per_nivell": (SCHEDULER_ALLIBERAMENTS_KEY, "json"),
        "durades_grups": (SCHEDULER_DURADES_GRUPS_KEY, "json"),
    }
    for camp, (clau, tipus) in claus.items():
        if camp in payload:
            valor = str(payload[camp]) if tipus == "integer" else json.dumps(document_iso(payload[camp]))
            ConfiguracioRepository.desa(db, clau, valor, tipus=tipus)
    db.commit()


def dates(db: Session) -> list[date]:
    return llegeix_dates(db)


def desa_dates(db: Session, dates: list[date]) -> None:
    ConfiguracioRepository.set(db, SCHEDULER_DATES_KEY, json.dumps(document_iso(dates or [])), tipus="json")
    db.commit()


# ---------------------------------------------------------------- exàmens


def examens_dels_nivells(db: Session, nivells: str | None) -> list[str]:
    """Els exàmens actuals dels nivells (separats per comes; sense, tots).
    Els de restriccions antigues es mostren a part (assignatures_inexistents)."""
    filtre = nivells.split(",") if nivells else []
    return examens(ConfiguracioExamenRepository.get_all(db), nivells_dels_grups(db), only_nivells=filtre)


def examens_actius(db: Session) -> list[str]:
    return examens(ConfiguracioExamenRepository.get_all(db), nivells_dels_grups(db))


# ---------------------------------------------------------------- restriccions


def _assignatures_inexistents(db: Session, restr: dict) -> list[str]:
    """Assignatures de les restriccions que no són a la configuració d'exàmens
    actual (p.ex. d'un curs anterior o d'abans de canviar el nom d'un nivell).
    Un nom sense nivell ("Anglès") val si hi ha aquesta assignatura a algun nivell."""
    assignacions = ConfiguracioExamenRepository.get_all(db)
    actuals = set(examens(assignacions, nivells_dels_grups(db)))
    actuals.update(nom for a in assignacions if (nom := a.get("assignatura") if isinstance(a, dict) else a.assignatura))
    return sorted(n for n in regles.assignatures_de(restr) if n not in actuals)


def restriccions(db: Session) -> dict:
    restr = regles.llegeix(db)
    return {"restriccions": restr, "assignatures_inexistents": _assignatures_inexistents(db, restr)}


def treu_assignatures_inexistents(db: Session) -> dict:
    """Treu de les restriccions les assignatures que ja no existeixen."""
    restr = regles.llegeix(db)
    trets = _assignatures_inexistents(db, restr)
    if trets:
        regles.desa(db, regles.treu_assignatures(restr, set(trets)))
        db.commit()
    return {"trets": trets, "restriccions": regles.llegeix(db)}


def desa_restriccions(db: Session, restriccions: dict) -> None:
    barrejades = regles.agrupacions_amb_diversos_nivells(restriccions or {})
    if barrejades:
        raise NoValid(
            f"Una agrupació ha de ser d'exàmens d'un mateix nivell: {', '.join(barrejades)}. "
            "Per posar exàmens de nivells diferents al mateix moment, feu servir la preferència "
            '"Mateixa data i hora".',
            codi="agrupacio_de_diversos_nivells",
            params={"agrupacions": ", ".join(barrejades)},
        )
    regles.desa(db, restriccions or {})
    db.commit()


def fixa_examens(db: Session, pins: list, unpins: list) -> None:
    """Fixa (`pins`: nom, dia, hora) o desfixa (`unpins`: noms) exàmens a un
    dia i una hora (restriccions assignatures_dia_fix i assignatures_hora_fix)."""
    for nom in unpins:
        RestriccioRepository.desfixa(db, nom)
    for pin in pins:
        for tipus, valor in zip(TIPUS_FIXATS, (pin.dia, pin.hora), strict=True):
            RestriccioRepository.fixa(
                db, tipus, pin.nom, data_desada(valor) if tipus == "assignatures_dia_fix" else valor
            )
    db.commit()


# ---------------------------------------------------------------- costos


def costos(db: Session) -> dict:
    """Els costos de fer venir o substituir els professors (globals i
    individuals). Els globals que no s'han desat, amb el valor per defecte
    (el mateix que fa servir el motor quan no n'hi ha)."""
    desats = CostProfessorRepository.costos(db)
    return {**desats, "globals": {**DEFAULT_COST_PROFESSORS, **desats["globals"]}}


def desa_costos(db: Session, payload: dict) -> None:
    """Substitueix tots els costos pels de `payload` (globals i individuals)."""
    CostProfessorRepository.substitueix(db, payload)
    db.commit()


# ---------------------------------------------------------------- últim horari


def ultim_resultat(db: Session):
    """L'últim horari generat o editat ({desat, resultat}), o None."""
    return resultat_amb_dates(llegeix_json(db, SCHEDULER_ULTIM_RESULTAT_KEY, None))


def desa_ultim_resultat(institucio: str, horari: dict, dies_utilitzar: list | None = None) -> None:
    """Franja de sortida del recàlcul del motor cap a la persistència."""
    desa_horari(institucio, horari_amb_dates(horari), dies_utilitzar)


def desa_horari(institucio: str, horari: dict, dies_utilitzar: list | None = None) -> None:
    if not isinstance(horari, dict) or not horari.get("dies"):
        return  # un intent no viable no substitueix l'últim horari bo
    with get_data_db_session(institucio) as db:
        if dies_utilitzar is None:
            anterior = ultim_resultat(db) or {}
            dies_utilitzar = (anterior.get("resultat") or {}).get("dies_utilitzar")

        ConfiguracioRepository.set(
            db,
            SCHEDULER_ULTIM_RESULTAT_KEY,
            json.dumps(
                jsonable_encoder(
                    {
                        "desat": rellotge.ara().isoformat(timespec="seconds"),
                        "resultat": {"dies_utilitzar": dies_utilitzar, "horari": horari},
                    }
                ),
                ensure_ascii=False,
            ),
            tipus="json",
        )
        db.commit()


# ---------------------------------------------------------------- cursos


def cursos_anteriors(db: Session, dates: list[date], avui: date) -> dict | None:
    """Si alguna data és d'un curs anterior a l'actual, {cursos, curs_actual}.

    La configuració d'exàmens i les restriccions són les del curs actual: amb
    dates d'un curs anterior es barrejarien amb l'horari d'aquell curs, i
    publicar escriuria vigilàncies damunt de l'històric. Sense cursos definits
    no es comprova res. El curs actual és el d'`avui`.
    """
    actual = CursRepository.get_for_date(db, avui)
    if not actual:
        return None
    anteriors = set()
    for data in dates:
        curs = CursRepository.get_for_date(db, data)
        if curs is None or curs.data_inici < actual.data_inici:
            anteriors.add(curs.nom if curs else "anterior al primer curs")
    return {"cursos": sorted(anteriors), "curs_actual": actual.nom} if anteriors else None
