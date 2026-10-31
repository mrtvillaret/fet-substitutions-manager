import json
import logging
import os
import re
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from auth.dependencies import require_admin
from cursos.repositories import CursRepository
from database import get_data_db_session
from models import AbreviaturaGrup, ExamCostProfessor, ExamRestriccio, Grup, Nivell
from noms import NomNet, nom_net
from parametres import data_iso
from repositories import (
    ConfiguracioExamenRepository,
    ConfiguracioRepository,
    MasterConfigRepository,
)
from routes.scheduler_analysis_helpers import (
    _afegir_recompte_nivells,
    _diagnosticar_incompatibilitats,
    _identificar_sessions_no_collocades,
    _precheck_incompatibilitats_deterministes,
    _write_analysis_pdf,
)
from routes.scheduler_config import (
    aplica_restriccions_derivades,
    carrega_config,
    horari_de_la_planificacio,
)
from routes.scheduler_cost import (
    IncidenciesFranja,
    conflicte_de_nivell,
    excessos_limit_dies,
    hores_lectives,
    incidencies,
)
from routes.scheduler_helpers import (
    _build_assignatures_options,
    _extract_assignatures_from_restriccions,
    _nivells_master,
    _normalitzar_hora,
    _treu_assignatures_de_restriccions,
    extreure_hores_examen_des_alliberaments,
)
from routes.scheduler_planificacio import prepara_planificacio
from routes.scheduler_service import (
    SCHEDULER_ALLIBERAMENTS_KEY,
    SCHEDULER_DATES_KEY,
    SCHEDULER_DURADA_EXAMEN_KEY,
    SCHEDULER_DURADA_KEY,
    SCHEDULER_DURADES_GRUPS_KEY,
    SCHEDULER_DURADES_SESSIO_KEY,
    SCHEDULER_NIVELLS_KEY,
    _build_restriccions_from_db,
    _load_json,
    _save_restriccions_to_db,
)
from scheduler_engine.core.date_mapping import construir_mapa_dia_data_iso
from scheduler_engine.core.horaris_xml import (
    horaris_professors as llegeix_horaris_professors,
)
from scheduler_engine.core.normalitzacio import normalitzar_dia
from scheduler_engine.defaults import DEFAULT_COST_PROFESSORS, DEFAULT_DURADA_TITULAR
from schemas import (
    HorariRecalcularRequest,
    SchedulerDatesRequest,
    SchedulerGenerateRequest,
    SchedulerPinRequest,
    SchedulerPublicarRequest,
    SchedulerRestriccionsRequest,
)
from serveis.dia import Dia
from serveis.publicacio_examens import PublicacioExamens, data_del_dia, primera_data


def _expandir_dies_per_analisi(dies_util: list, dia_a_data_iso: dict) -> list:
    """Expandeix dies_util a dates ISO quan hi ha múltiples setmanes per dia."""
    from scheduler_engine.core.normalitzacio import normalitzar_dia as _nd

    result = []
    for dia in dies_util:
        dates = dia_a_data_iso.get(_nd(dia), [])
        if isinstance(dates, str):
            dates = [dates]
        if len(dates) > 1:
            result.extend(dates)
        else:
            result.append(dia)
    return result


router = APIRouter(prefix="/api/scheduler", tags=["Scheduler"])

log = logging.getLogger(__name__)


@router.get("/status")
async def scheduler_status(current_user=Depends(require_admin)):
    p = Path(__file__).resolve().parents[1] / "scheduler_engine" / "generators" / "v3_sa.py"
    return {
        "available": p.exists(),
        "engine_path": str(p.parent),
        "message": "OK" if p.exists() else "Pending",
        "institucio": current_user.institucio,
    }


@router.get("/motors")
async def scheduler_motors(current_user=Depends(require_admin)):
    """Retorna els motors disponibles amb paràmetres i defaults per al frontend."""
    from scheduler_engine.factory import get_motors_info

    return {
        "motors": get_motors_info(),
        "cost_defaults": dict(DEFAULT_COST_PROFESSORS),
    }


@router.get("/grups-nivells")
async def scheduler_grups_nivells(current_user=Depends(require_admin)):
    """
    Retorna tots els grups agrupats per nivell, amb les abreviatures expandides.
    Cada grup té: codi, es_abreviatura, grups_expandits (si és abreviatura).
    """
    with get_data_db_session(current_user.institucio) as db:
        # Carregar abreviatures per poder expandir
        abreviatures = {}
        for abr in db.query(AbreviaturaGrup).all():
            abreviatures[abr.abreviatura] = [g.strip() for g in abr.grups_originals.split(",")]

        # Carregar grups per nivell
        result = {}
        nivells = db.query(Nivell).filter(Nivell.actiu.is_(True)).order_by(Nivell.ordre).all()
        for nivell in nivells:
            if nivell.codi in ("GENERAL", "RECERCA"):
                continue
            grups = (
                db.query(Grup)
                .filter(Grup.nivell_id == nivell.id, Grup.actiu.is_(True))
                .order_by(Grup.ordre, Grup.codi)
                .all()
            )

            grups_list = []
            for g in grups:
                expandits = abreviatures.get(g.codi)
                grups_list.append(
                    {
                        "codi": g.codi,
                        "es_abreviatura": expandits is not None,
                        "grups_expandits": expandits or [],
                    }
                )
            if grups_list:
                result[nivell.codi] = grups_list

    return {"grups_per_nivell": result}


@router.get("/config")
async def scheduler_config(current_user=Depends(require_admin)):
    with get_data_db_session(current_user.institucio) as db:
        master = MasterConfigRepository.get_master_config(db)
        assignacions = ConfiguracioExamenRepository.get_all(db)
        d = int(ConfiguracioRepository.get(db, SCHEDULER_DURADA_KEY) or DEFAULT_DURADA_TITULAR)
        de_raw = ConfiguracioRepository.get(db, SCHEDULER_DURADA_EXAMEN_KEY)
        de = int(de_raw) if de_raw else d  # per defecte = durada_titular
        n = _load_json(ConfiguracioRepository.get(db, SCHEDULER_NIVELLS_KEY), [])
        alliberaments = _load_json(ConfiguracioRepository.get(db, SCHEDULER_ALLIBERAMENTS_KEY), {})
        durades_grups = _load_json(ConfiguracioRepository.get(db, SCHEDULER_DURADES_GRUPS_KEY), None)
        # Migració backward compat: si no hi ha grups, convertir format antic
        if not durades_grups:
            durades_per_sessio_antic = _load_json(ConfiguracioRepository.get(db, SCHEDULER_DURADES_SESSIO_KEY), {})
            durades_grups = [
                {"nom": "", "assignatures": [sessio], "durada": dur, "durada_examen": dur}
                for sessio, dur in durades_per_sessio_antic.items()
            ]
    nivells = list(master.get("nivells", {}).keys())
    # La selecció desada pot ser d'un horari anterior: els nivells que ja no
    # existeixen sortirien al selector com a `null` i amb pestanyes pròpies.
    n = [nivell for nivell in n if nivell in nivells]
    alliberaments = {nivell: v for nivell, v in alliberaments.items() if nivell in nivells}
    h, hpn = extreure_hores_examen_des_alliberaments(alliberaments)
    return {
        "nivells": nivells,
        "assignacions_total": len(assignacions),
        "hores_examen": h,
        "durada_titular": d,
        "durada_examen": de,
        "nivells_seleccionats": n,
        "hores_per_nivell": hpn,
        "alliberaments_per_nivell": alliberaments,
        "durades_grups": durades_grups,
    }


@router.put("/config")
async def scheduler_config_update(payload: dict, current_user=Depends(require_admin)):
    with get_data_db_session(current_user.institucio) as db:
        if "durada_titular" in payload:
            ConfiguracioRepository.set(db, SCHEDULER_DURADA_KEY, str(payload["durada_titular"]), tipus="integer")
        if "durada_examen" in payload:
            ConfiguracioRepository.set(db, SCHEDULER_DURADA_EXAMEN_KEY, str(payload["durada_examen"]), tipus="integer")
        if "nivells_actius" in payload:
            ConfiguracioRepository.set(db, SCHEDULER_NIVELLS_KEY, json.dumps(payload["nivells_actius"]), tipus="json")
        if "alliberaments_per_nivell" in payload:
            ConfiguracioRepository.set(
                db, SCHEDULER_ALLIBERAMENTS_KEY, json.dumps(payload["alliberaments_per_nivell"]), tipus="json"
            )
        if "durades_grups" in payload:
            ConfiguracioRepository.set(
                db, SCHEDULER_DURADES_GRUPS_KEY, json.dumps(payload["durades_grups"]), tipus="json"
            )
    return {"success": True}


def _assignatures_inexistents(db, restr: dict) -> list[str]:
    """Assignatures de les restriccions que no són a la configuració d'exàmens
    actual (p.ex. d'un curs anterior o d'abans de canviar el nom d'un nivell).
    Un nom sense nivell ("Anglès") val si hi ha aquesta assignatura a algun nivell."""
    assignacions = ConfiguracioExamenRepository.get_all(db)
    actuals = set(_build_assignatures_options(assignacions, _nivells_master(db)))
    actuals |= {a.get("assignatura") if isinstance(a, dict) else a.assignatura for a in assignacions}
    return sorted(n for n in _extract_assignatures_from_restriccions(restr) if n not in actuals)


@router.get("/restriccions")
async def scheduler_restriccions(current_user=Depends(require_admin)):
    with get_data_db_session(current_user.institucio) as db:
        restr = _build_restriccions_from_db(db)
        return {"restriccions": restr, "assignatures_inexistents": _assignatures_inexistents(db, restr)}


@router.post("/restriccions/treure-inexistents")
async def scheduler_treure_assignatures_inexistents(current_user=Depends(require_admin)):
    """Treu de les restriccions les assignatures que ja no existeixen."""
    with get_data_db_session(current_user.institucio) as db:
        restr = _build_restriccions_from_db(db)
        trets = _assignatures_inexistents(db, restr)
        if trets:
            _save_restriccions_to_db(db, _treu_assignatures_de_restriccions(restr, set(trets)))
        return {"trets": trets, "restriccions": _build_restriccions_from_db(db)}


def _agrupacions_amb_diversos_nivells(restriccions: dict) -> list:
    """Noms de les agrupacions (mateix_slot) amb exàmens de més d'un nivell.

    Els motors col·loquen cada agrupació dins d'un nivell; per a exàmens de
    nivells diferents al mateix moment hi ha la preferència "Mateix dia i hora".
    El nivell és el sufix del nom de la sessió: "Anglès (1-BAT)" -> "1-BAT".
    """
    barrejades = []
    for grup in (restriccions.get("restriccions_dures") or {}).get("mateix_slot") or []:
        assignatures = grup.get("assignatures", []) if isinstance(grup, dict) else grup
        nivells = {
            m.group(1) for a in assignatures or [] if isinstance(a, str) and (m := re.search(r"\(([^()]+)\)\s*$", a))
        }
        if len(nivells) > 1:
            barrejades.append((grup.get("nom") if isinstance(grup, dict) else "") or ", ".join(assignatures))
    return barrejades


@router.put("/restriccions")
async def scheduler_restriccions_update(payload: SchedulerRestriccionsRequest, current_user=Depends(require_admin)):
    barrejades = _agrupacions_amb_diversos_nivells(payload.restriccions or {})
    if barrejades:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Una agrupació ha de ser d'exàmens d'un mateix nivell: {', '.join(barrejades)}. "
                "Per posar exàmens de nivells diferents al mateix moment, feu servir la preferència "
                '"Mateix dia i hora".'
            ),
        )
    with get_data_db_session(current_user.institucio) as db:
        _save_restriccions_to_db(db, payload.restriccions or {})
    return {"success": True}


@router.post("/restriccions/pin")
async def scheduler_pin_sessions(payload: SchedulerPinRequest, current_user=Depends(require_admin)):
    """
    Fixa o desfixa sessions a un dia/hora concret modificant les restriccions
    assignatures_dia_fix i assignatures_hora_fix a la BD.
    """
    with get_data_db_session(current_user.institucio) as db:
        try:
            # Desfixar: eliminar restriccions dia_fix i hora_fix per cada nom
            for nom in payload.unpins:
                db.query(ExamRestriccio).filter(
                    ExamRestriccio.tipus.in_(["assignatures_dia_fix", "assignatures_hora_fix"]),
                    ExamRestriccio.clau == nom,
                ).delete(synchronize_session=False)

            # Fixar: afegir/actualitzar restriccions dia_fix i hora_fix per cada pin
            for pin in payload.pins:
                for tipus, valor in [("assignatures_dia_fix", pin.dia), ("assignatures_hora_fix", pin.hora)]:
                    existing = (
                        db.query(ExamRestriccio)
                        .filter(
                            ExamRestriccio.tipus == tipus,
                            ExamRestriccio.clau == pin.nom,
                        )
                        .first()
                    )
                    if existing:
                        existing.configuracio = json.dumps(valor, ensure_ascii=False)
                        existing.pes = 100
                        existing.activa = True
                    else:
                        db.add(
                            ExamRestriccio(
                                tipus=tipus,
                                clau=pin.nom,
                                configuracio=json.dumps(valor, ensure_ascii=False),
                                pes=100,
                                activa=True,
                            )
                        )

            db.commit()

            # Retornar l'estat actual dels pins
            pins_dia = {}
            pins_hora = {}
            for r in (
                db.query(ExamRestriccio)
                .filter(
                    ExamRestriccio.tipus.in_(["assignatures_dia_fix", "assignatures_hora_fix"]),
                    ExamRestriccio.activa.is_(True),
                )
                .all()
            ):
                val = json.loads(r.configuracio) if r.configuracio else None
                if r.tipus == "assignatures_dia_fix":
                    pins_dia[r.clau] = val
                else:
                    pins_hora[r.clau] = val

            return {
                "success": True,
                "pins": {
                    "assignatures_dia_fix": pins_dia,
                    "assignatures_hora_fix": pins_hora,
                },
            }
        except Exception:
            db.rollback()
            raise


# ===== COSTOS DE PROFESSORS =====


@router.get("/costos-professors")
async def get_costos_professors(current_user=Depends(require_admin)):
    """
    Retorna els costos de professors (globals i individuals).

    Estructura retornada:
    {
        "globals": {"substitucio": 80, "abans_jornada": 30, ...},
        "individuals": {"Prof A": {"substitucio": 100}, ...}
    }
    """
    with get_data_db_session(current_user.institucio) as db:
        costos = {"globals": {}, "individuals": {}}

        defaults = dict(DEFAULT_COST_PROFESSORS)

        try:
            for cp in db.query(ExamCostProfessor).all():
                if cp.professor is None:
                    costos["globals"][cp.tipus] = cp.pes
                else:
                    if cp.professor not in costos["individuals"]:
                        costos["individuals"][cp.professor] = {}
                    costos["individuals"][cp.professor][cp.tipus] = cp.pes
        except Exception:
            log.warning("No s'han pogut llegir els costos individuals", exc_info=True)

        # Assegurar que existeixen tots els globals
        for tipus, default_pes in defaults.items():
            if tipus not in costos["globals"]:
                costos["globals"][tipus] = default_pes

        return {"costos_professors": costos}


@router.put("/costos-professors")
async def update_costos_professors(payload: dict, current_user=Depends(require_admin)):
    """
    Actualitza els costos de professors.

    Payload esperat:
    {
        "globals": {"substitucio": 80, ...},
        "individuals": {"Prof A": {"substitucio": 100}, ...}
    }
    """
    with get_data_db_session(current_user.institucio) as db:
        try:
            db.query(ExamCostProfessor).delete()

            # Globals
            for tipus, pes in payload.get("globals", {}).items():
                db.add(ExamCostProfessor(professor=None, tipus=tipus, pes=int(pes)))

            # Individuals
            for professor, tipus_dict in payload.get("individuals", {}).items():
                for tipus, pes in tipus_dict.items():
                    db.add(ExamCostProfessor(professor=nom_net(professor), tipus=tipus, pes=int(pes)))

            db.commit()
            return {"success": True}
        except Exception:
            db.rollback()
            raise


@router.put("/costos-professors/{professor}")
async def update_cost_professor_individual(professor: NomNet, payload: dict, current_user=Depends(require_admin)):
    """
    Actualitza els costos d'un professor específic.

    Payload esperat:
    {"substitucio": 100, "abans_jornada": 50, ...}
    """
    with get_data_db_session(current_user.institucio) as db:
        try:
            # Esborrar costos anteriors d'aquest professor
            db.query(ExamCostProfessor).filter(ExamCostProfessor.professor == professor).delete()

            # Afegir nous costos
            for tipus, pes in payload.items():
                db.add(ExamCostProfessor(professor=professor, tipus=tipus, pes=int(pes)))

            db.commit()
            return {"success": True, "professor": professor}
        except Exception:
            db.rollback()
            raise


@router.delete("/costos-professors/{professor}")
async def delete_cost_professor_individual(professor: NomNet, current_user=Depends(require_admin)):
    """Elimina els costos individuals d'un professor (tornarà a usar globals)."""
    with get_data_db_session(current_user.institucio) as db:
        try:
            deleted = db.query(ExamCostProfessor).filter(ExamCostProfessor.professor == professor).delete()
            db.commit()
            return {"success": True, "deleted": deleted}
        except Exception:
            db.rollback()
            raise


@router.get("/dates")
async def scheduler_dates(current_user=Depends(require_admin)):
    with get_data_db_session(current_user.institucio) as db:
        return {"selected_dates": _load_json(ConfiguracioRepository.get(db, SCHEDULER_DATES_KEY), [])}


@router.put("/dates")
async def scheduler_dates_update(payload: SchedulerDatesRequest, current_user=Depends(require_admin)):
    with get_data_db_session(current_user.institucio) as db:
        ConfiguracioRepository.set(db, SCHEDULER_DATES_KEY, json.dumps(payload.selected_dates or []), tipus="json")
    return {"success": True}


@router.get("/sessions-info")
async def get_scheduler_sessions_info(nivells: str = None, current_user=Depends(require_admin)):
    with get_data_db_session(current_user.institucio) as db:
        assignacions = ConfiguracioExamenRepository.get_all(db)
        nivells_master = _nivells_master(db)
    filtre = nivells.split(",") if nivells else []
    # Només les assignatures actuals: les de restriccions antigues es mostren a
    # part (GET /restriccions → assignatures_inexistents)
    return _build_assignatures_options(assignacions, nivells_master, only_nivells=filtre)


@router.get("/assignatures-actives")
async def get_assignatures_actives(current_user=Depends(require_admin)):
    with get_data_db_session(current_user.institucio) as db:
        assignacions = ConfiguracioExamenRepository.get_all(db)
        nivells_master = _nivells_master(db)
    return _build_assignatures_options(assignacions, nivells_master)


# L'últim horari generat (o editat a mà): el planificador el recorda en tornar
# a la pantalla, des de qualsevol ordinador. Es desa en generar i en recalcular
# el cost després d'una edició.
SCHEDULER_ULTIM_RESULTAT_KEY = "scheduler_ultim_resultat"


def _desa_ultim_resultat(institucio: str, horari: dict, dies_utilitzar: list | None = None) -> None:
    if not isinstance(horari, dict) or not horari.get("dies"):
        return  # un intent no viable no substitueix l'últim horari bo
    with get_data_db_session(institucio) as db:
        if dies_utilitzar is None:
            anterior = _load_json(ConfiguracioRepository.get(db, SCHEDULER_ULTIM_RESULTAT_KEY), {}) or {}
            dies_utilitzar = (anterior.get("resultat") or {}).get("dies_utilitzar")
        from fastapi.encoders import jsonable_encoder

        ConfiguracioRepository.set(
            db,
            SCHEDULER_ULTIM_RESULTAT_KEY,
            json.dumps(
                jsonable_encoder(
                    {
                        "desat": datetime.now().isoformat(timespec="seconds"),
                        "resultat": {"dies_utilitzar": dies_utilitzar, "horari": horari},
                    }
                ),
                ensure_ascii=False,
            ),
            tipus="json",
        )


@router.get("/horari")
async def scheduler_horari(dates: Optional[str] = None, current_user=Depends(require_admin)):
    """Quin horari (XML) fa servir el planificador per a les dates (AAAA-MM-DD
    separades per comes; sense, les desades): la data de referència, des de
    quan és vigent i si dins les dates en comença un altre."""
    llista = [data_iso(d.strip()).isoformat() for d in (dates or "").split(",") if d.strip()]
    return horari_de_la_planificacio(current_user.institucio, llista)


@router.get("/ultim-resultat")
async def scheduler_ultim_resultat(current_user=Depends(require_admin)):
    """L'últim horari generat o editat ({desat, resultat}), o null."""
    with get_data_db_session(current_user.institucio) as db:
        return _load_json(ConfiguracioRepository.get(db, SCHEDULER_ULTIM_RESULTAT_KEY), None)


def _cursos_anteriors(db, dates: list[str]) -> dict | None:
    """Si alguna data és d'un curs anterior a l'actual, {cursos, curs_actual}.

    La configuració d'exàmens i les restriccions són les del curs actual: amb
    dates d'un curs anterior es barrejarien amb l'horari d'aquell curs, i
    publicar escriuria vigilàncies damunt de l'històric. Sense cursos definits
    no es comprova res.
    """
    from datetime import date as _date

    actual = CursRepository.get_for_date(db, _date.today().isoformat())
    if not actual:
        return None
    anteriors = set()
    for data in dates:
        curs = CursRepository.get_for_date(db, data)
        if curs is None or curs.data_inici < actual.data_inici:
            anteriors.add(curs.nom if curs else "anterior al primer curs")
    return {"cursos": sorted(anteriors), "curs_actual": actual.nom} if anteriors else None


@router.get("/curs-dates")
async def scheduler_curs_dates(dates: str = "", current_user=Depends(require_admin)):
    """Avís si les dates (separades per comes) són d'un curs anterior."""
    llista = [d for d in dates.split(",") if d]
    with get_data_db_session(current_user.institucio) as db:
        return {"curs_anterior": _cursos_anteriors(db, llista)}


# Les rutes que executen el motor (segons) són síncrones: FastAPI les atén en
# un fil a part i el backend continua responent la resta de peticions.
PARAMETRES_V3 = (
    "temperatura_inicial",
    "temperatura_final",
    "factor_refredament",
    "iteracions_per_temperatura",
    "max_iteracions",
)


def _executa_motor(gen, metode: str, motor: str, payload: SchedulerGenerateRequest, pla) -> dict:
    """Genera l'horari amb el motor (els paràmetres propis de cada motor) i
    n'apunta el temps."""
    kwargs = {
        "data_inici": datetime.strptime(payload.data_inici, "%Y-%m-%d").strftime("%d/%m/%Y"),
        "data_inici_iso": payload.data_inici,
        "dies_utilitzar": pla.dies,
        "dia_a_data_iso": pla.dia_a_data_iso,
        "max_dies": payload.max_dies,
        "selected_dates": pla.dates,
    }
    if motor == "v2":
        kwargs.update(
            max_intents_validacio=payload.max_intents_validacio,
            estrategia=payload.estrategia,
            epsilon=payload.epsilon,
            track_intents=True,
        )
    elif motor == "v2-backtrack":
        kwargs["max_solucions"] = 100
        for clau in ("random_seed", "seeds_count", "max_nodes", "shuffle_top_n"):
            if getattr(payload, clau) is not None:
                kwargs[clau] = getattr(payload, clau)

    import time

    t0 = time.monotonic()
    resultat = getattr(gen, metode)(**kwargs)
    temps_ms = int((time.monotonic() - t0) * 1000)

    if motor == "v2-backtrack":
        # Retorna la llista de solucions: la primera, i quantes n'hi ha
        if resultat:
            horari = resultat[0]
            if horari.get("metadata", {}).get("viable", True):
                horari["metadata"]["alternatives"] = len(resultat)
                horari["metadata"]["motor"] = "v2-backtrack"
        else:
            horari = {
                "metadata": {
                    "viable": False,
                    "error": "El backtracking no ha trobat cap solució vàlida",
                    "motor": "v2-backtrack",
                },
                "dies": [],
            }
    else:
        horari = resultat
    if isinstance(horari, dict):
        horari.setdefault("metadata", {})["temps_generacio_ms"] = temps_ms
    return horari


def _marca_sessions_pendents(horari: dict, gen) -> None:
    """Recompte per nivell de les sessions col·locades; si en falta alguna,
    l'horari no és viable."""
    sessions_per_nivell = getattr(gen, "sessions_per_nivell", {}) or {}
    if not isinstance(sessions_per_nivell, dict):
        sessions_per_nivell = {}
    sessions = getattr(gen, "sessions", None)
    if sessions and not any(isinstance(v, (list, tuple, set, dict)) and v for v in sessions_per_nivell.values()):
        # El motor no les té per nivell: s'agrupen a partir de la llista
        per_nivell = defaultdict(list)
        for sessio in sessions:
            nivell = sessio.get("curs") if isinstance(sessio, dict) else getattr(sessio, "curs", None)
            if nivell:
                per_nivell[nivell].append(sessio)
        sessions_per_nivell = per_nivell
    _afegir_recompte_nivells(horari, sessions_per_nivell)
    recompte = (horari.get("metadata") or {}).get("recompte_nivells") or {}
    pendents = sum((info or {}).get("pendents", 0) for info in recompte.values())
    if pendents > 0:
        meta = horari.setdefault("metadata", {})
        meta.setdefault("logs", []).append(f"⚠️ Sessions pendents de col·locar: {pendents}")
        if meta.get("viable", True):
            meta["viable"] = False
            meta["error"] = "No s'han pogut col·locar tots els exàmens"


def _explica_no_viable(horari: dict, gen, pla, del_precheck: bool = False) -> None:
    """Per què no s'han pogut col·locar tots els exàmens: primer el
    diagnòstic de restriccions i després el que n'ha dit el motor, sense
    repetir-los. Si el motor no s'ha executat perquè el precheck ja ho ha
    vist, el precheck només es mostra quan el diagnòstic no diu res: tots dos
    analitzen el mateix i es repetirien amb paraules diferents."""
    meta = horari["metadata"]
    error = meta.get("error", "No és possible col·locar tots els exàmens")
    diagnostic = _diagnosticar_incompatibilitats(
        gen=gen,
        restriccions=pla.restriccions,
        dies_utilitzar=pla.dies,
        dia_a_data_iso=pla.dia_a_data_iso,
        alliberaments_cfg=pla.cfg.alliberaments,
        nivells_actius=pla.nivells,
    )
    if diagnostic and del_precheck:
        incompat = diagnostic
    else:
        del_motor = (
            meta.get("incompatibilitats")
            or getattr(gen, "_incompatibilitats_bt", [])
            or _identificar_sessions_no_collocades(horari, gen)
        )
        incompat = list(dict.fromkeys(diagnostic + list(del_motor)))
    if incompat:
        meta["incompatibilitats"] = incompat
    meta["logs"] = list(dict.fromkeys(meta.get("logs", []) + [f"❌ {error}"]))


@router.post("/generate")
def scheduler_generate(payload: SchedulerGenerateRequest, current_user=Depends(require_admin)):
    with prepara_planificacio(payload, current_user.institucio) as pla:
        if not pla.dates:
            # La pantalla no ho permet: els motors col·loquen exàmens en dates concretes
            raise HTTPException(status_code=400, detail="Cal triar les dates dels exàmens")
        motor = (payload.motor or "v3").lower()
        parametres = {
            k: getattr(payload, k, None)
            for k in PARAMETRES_V3
            if motor == "v3" and getattr(payload, k, None) is not None
        }

        from captura_sortida import captura_stdout

        with captura_stdout() as sortida:
            gen, metode = pla.motor(motor, **parametres)
            incompatibilitats = _precheck_incompatibilitats_deterministes(
                gen=gen,
                restriccions=pla.restriccions,
                dies_utilitzar=pla.dies,
                nivells_actius=pla.nivells,
                selected_dates=pla.dates,
            )
            if incompatibilitats:
                horari = {
                    "dies": [],
                    "metadata": {
                        "viable": False,
                        "error": "No s'han pogut col·locar tots els exàmens",
                        "incompatibilitats": incompatibilitats,
                        "motor": motor,
                        "logs": ["❌ Precheck de viabilitat: incompatibilitats deterministes detectades"],
                    },
                }
            else:
                horari = _executa_motor(gen, metode, motor, payload, pla)

        if isinstance(horari, dict):
            _marca_sessions_pendents(horari, gen)

        if horari and "metadata" in horari:
            meta = horari["metadata"]
            if not meta.get("viable", True):
                _explica_no_viable(horari, gen, pla, del_precheck=bool(incompatibilitats))
                return {"status": "ok", "horari": horari}

            # Incidències: les del motor, la sortida capturada i la validació
            from scheduler_engine.validacio import ValidadorHorari

            validacio = ValidadorHorari(horari, pla.restriccions, pla.cfg.no_substituir).validar()
            logs = [linia.strip() for linia in meta.get("logs", []) if linia.strip()]
            logs += [linia.strip() for linia in sortida.getvalue().splitlines() if linia.strip()]
            logs += validacio["logs"]
            meta["logs"] = list(dict.fromkeys(logs))

        _desa_ultim_resultat(current_user.institucio, horari, pla.dies)
        return {"dies_utilitzar": pla.dies, "horari": horari}


def _informes_analisi(payload: SchedulerGenerateRequest, institucio: str) -> dict:
    """Els tres informes de l'anàlisi de disponibilitat (per franja, per
    examen i professors per franja) amb el motor v2, com a /analisi i al PDF.
    Les dates són les desades a la configuració (no les de la petició)."""
    with prepara_planificacio(payload, institucio, dates_de_la_peticio=False) as pla:
        gen, _ = pla.motor("v2")
        gen.dia_a_data_iso = {normalitzar_dia(k): v for k, v in (pla.dia_a_data_iso or {}).items() if v}
        dies_analisi = _expandir_dies_per_analisi(pla.dies, gen.dia_a_data_iso)
        matriu_costos = gen._analitzar_tots_slots(dies_analisi)
        return {
            "per_slots": gen.generar_informe_per_slots(matriu_costos, dies_analisi),
            "per_sessio": gen.generar_informe_disponibilitat(matriu_costos, dies_analisi),
            "professors_slot": gen.generar_informe_professors_per_slot(dies_analisi),
        }


@router.post("/analisi")
def scheduler_analisi(payload: SchedulerGenerateRequest, current_user=Depends(require_admin)):
    return _informes_analisi(payload, current_user.institucio)


@router.post("/analisi/pdf")
def scheduler_analisi_pdf(payload: SchedulerGenerateRequest, current_user=Depends(require_admin)):
    informes = _informes_analisi(payload, current_user.institucio)
    seccions = {
        "per_slots": ("Per Hora/Dia", "per_slots", informes["per_slots"]),
        "per_sessio": ("Per Agrupacio", "per_sessio", informes["per_sessio"]),
        "professors_slot": ("Professors per Slot", "professors_slot", informes["professors_slot"]),
    }
    pestanya = (payload.analisi_tab or "").strip()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as pdf_f:
        pdf_path = pdf_f.name
    _write_analysis_pdf(pdf_path, [seccions[pestanya]] if pestanya in seccions else list(seccions.values()))
    # El fitxer temporal s'esborra un cop enviat
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"analisi_{payload.data_inici}.pdf",
        background=BackgroundTask(os.remove, pdf_path),
    )


# ===== PUBLICAR VIGILÀNCIES =====


@router.post("/publicar")
async def scheduler_publicar(payload: SchedulerPublicarRequest, current_user=Depends(require_admin)):
    """
    Transforma l'horari generat en vigilàncies reals.
    Crea Vigilancia + GrupAlliberat records per cada data concreta.
    Opcionalment auto-assigna titulars (fase 1 d'assignació).
    """
    horari = payload.horari
    setmanes = payload.setmanes
    grups_sense_classe = payload.grups_sense_classe or []
    opcions = payload.opcions
    dry_run = payload.dry_run

    if not horari or not horari.get("dies"):
        raise HTTPException(status_code=400, detail="L'horari no conté dies")
    if not setmanes:
        raise HTTPException(status_code=400, detail="Cal indicar almenys una setmana amb dates")

    dates_horari = [d.get("data") for d in horari["dies"] if isinstance(d, dict) and d.get("data")]
    dates_horari += [v for setmana in setmanes for v in setmana.values() if isinstance(v, str)]
    with get_data_db_session(current_user.institucio) as db:
        anterior = _cursos_anteriors(db, dates_horari)
    if anterior:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Les dates són del curs {', '.join(anterior['cursos'])}, anterior a l'actual "
                f"({anterior['curs_actual']}). El planificador fa servir la configuració d'exàmens del "
                "curs actual; les vigilàncies de cursos anteriors es consulten a Vigilàncies."
            ),
        )

    # Hores lectives del centre (per allargar els exàmens de més d'una hora)
    totes_hores = []
    data_hores = primera_data(horari, setmanes)
    if data_hores:
        try:
            totes_hores = Dia.de_text(data_hores, current_user.institucio).horari.hores or []
        except Exception as e:
            log.warning(f"No s'han pogut carregar hores lectives: {e}")

    with get_data_db_session(current_user.institucio) as db:
        publicacio = PublicacioExamens(
            db, carrega_config(current_user.institucio), totes_hores, grups_sense_classe, opcions.netejar_existents
        )
        resum = publicacio.resum
        for dia_info in horari["dies"]:
            data_iso = data_del_dia(dia_info, setmanes)
            if not data_iso:
                continue
            resum.dates.append(data_iso)
            try:
                publicacio.publica_dia(dia_info, data_iso)
            except Exception as e:
                resum.errors.append(f"{data_iso}: {str(e)}")

        if opcions.auto_assign_titulars and not resum.errors and not dry_run:
            publicacio.assigna_titulars(current_user.institucio)

        if dry_run or resum.errors:
            db.rollback()
        else:
            db.flush()
            from substitucions.cobertures import refresca_cobertures

            for data_iso, hora in sorted(resum.hores_esborrades):
                refresca_cobertures(data_iso, hora, db)
            db.commit()

    return {
        "success": len(resum.errors) == 0,
        "dry_run": dry_run,
        "dates_processades": sorted(set(resum.dates)),
        "vigilancies_creades": resum.creades,
        "vigilancies_actualitzades": resum.actualitzades,
        "vigilancies_sense_canvis": resum.sense_canvis,
        "vigilancies_eliminades": resum.eliminades,
        "grups_alliberats_creats": resum.grups_alliberats,
        "titulars_assignats": resum.titulars,
        "errors": resum.errors or None,
        "avisos": resum.avisos or None,
    }


# ===== RECALCULAR COST (EDITOR INTERACTIU) =====


@router.post("/recalcular-cost")
def recalcular_cost(payload: HorariRecalcularRequest, current_user=Depends(require_admin)):
    """
    Recalcula el cost d'un horari modificat sense regenerar.
    Usat per l'editor interactiu de drag-and-drop.
    """
    horari = payload.horari
    if not horari or not horari.get("dies"):
        raise HTTPException(status_code=400, detail="L'horari no conté dies")

    from scheduler_engine.core.normalitzacio import normalitzar_dia, normalitzar_text

    cfg = carrega_config(current_user.institucio)
    restriccions = cfg.restriccions
    nivells_actius = cfg.nivells_actius()
    selected_dates = cfg.dates(payload.selected_dates, nivells_actius)
    no_subst_norm = {normalitzar_text(a) for a in cfg.no_substituir if a}

    hores_examen, _ = extreure_hores_examen_des_alliberaments(cfg.alliberaments)

    # Determinar data per XML
    data_ref = payload.data_referencia
    if not data_ref:
        meta = horari.get("metadata", {})
        data_ref = meta.get("data_inici")
    if not data_ref:
        from datetime import date

        data_ref = date.today().isoformat()

    dies_horari = [d.get("dia") for d in horari.get("dies", []) if d.get("dia")]
    dia_a_data_iso = construir_mapa_dia_data_iso(
        dies_utilitzar=dies_horari,
        selected_dates=selected_dates,
        data_inici_iso=data_ref,
    )

    xml_path = Dia.de_text(data_ref, current_user.institucio).xml_path
    if not xml_path or not os.path.exists(xml_path):
        raise HTTPException(status_code=400, detail="XML d'horaris no disponible")

    # Carregar horaris professors
    import xml.etree.ElementTree as ET

    tree = ET.parse(xml_path)
    root = tree.getroot()

    totes_hores = hores_lectives(root, hores_examen)

    # Aplicar també en recàlcul la restricció derivada de slots vàlids per nivell (marques 🟦).
    aplica_restriccions_derivades(
        restriccions, cfg.alliberaments, nivells_actius, dies_horari, dia_a_data_iso, totes_hores
    )

    horaris_professors = llegeix_horaris_professors(root, cfg.ultim_professor, normalitza_hores=True)

    # Recalcular cost amb el mòdul d'estadístiques
    from scheduler_engine.core.availability import analitzar_disponibilitat_sessio
    from scheduler_engine.core.durada import (
        detectar_nivell_sessio,
        get_durada_per_sessio_key,
    )
    from scheduler_engine.estadistiques import recalcular_cost_i_breakdown
    from scheduler_engine.validacio import ValidadorHorari

    ctx = SimpleNamespace(
        restriccions=restriccions,
        horaris_professors=horaris_professors,
        hores_examen=hores_examen,
        durada_titular=cfg.durada_titular,
        no_substituir_norm=no_subst_norm,
        totes_hores=totes_hores,
        nivells_actius=nivells_actius,
        dia_a_data_iso=dia_a_data_iso,
        alliberaments_per_nivell=cfg.alliberaments,
        durades_per_sessio=cfg.durades_per_sessio,
    )
    cost_info = recalcular_cost_i_breakdown(horari, ctx)

    # Cost, avisos i conflictes de cada franja
    slots_info = []
    conflicte_global = False
    for dia in horari.get("dies", []):
        dia_nom = dia.get("dia", "")
        _dates = dia_a_data_iso.get(normalitzar_dia(dia_nom))
        data_iso_slot = dia.get("data") or (_dates[0] if isinstance(_dates, list) else _dates)
        for slot in dia.get("sessions", []):
            hora = slot.get("hora", "")
            hora_norm = _normalitzar_hora(hora)
            sessions_sim = slot.get("sessions_simultanees", [])
            conflicte_nivell = conflicte_de_nivell(sessions_sim)
            conflicte_global = conflicte_global or conflicte_nivell

            franja = IncidenciesFranja()
            item_avisos = {}
            for idx, sessio in enumerate(sessions_sim):
                altres = [s for i, s in enumerate(sessions_sim) if i != idx]
                nivell_sessio = detectar_nivell_sessio(sessio, nivells_actius or [])
                sessio_nom_d = sessio.get("nom") if isinstance(sessio, dict) else None
                durada_sessio = get_durada_per_sessio_key(
                    sessio_nom_d, nivell_sessio, cfg.durades_per_sessio, cfg.alliberaments, cfg.durada_titular
                )
                durada_exam = get_durada_per_sessio_key(
                    sessio_nom_d, nivell_sessio, cfg.durades_examen_per_sessio, cfg.alliberaments, cfg.durada_titular
                )
                durada_exam = max(durada_exam, durada_sessio)
                if hora_norm in totes_hores:
                    idx_inici = totes_hores.index(hora_norm)
                    hores_ocupades = totes_hores[idx_inici : min(idx_inici + max(1, durada_sessio), len(totes_hores))]
                    hores_exam = totes_hores[idx_inici : min(idx_inici + max(1, durada_exam), len(totes_hores))]
                else:
                    hores_ocupades = [hora_norm]
                    hores_exam = [hora_norm]
                analisi = analitzar_disponibilitat_sessio(
                    sessio=sessio,
                    dia=dia_nom,
                    hora=hora_norm,
                    horaris_professors=horaris_professors,
                    totes_hores=totes_hores,
                    nivells_actius=nivells_actius,
                    durada_titular=durada_sessio,
                    no_substituir_norm=no_subst_norm,
                    sessions_al_slot=altres,
                    hores_override=hores_exam,
                    hores_supervisio=hores_ocupades,
                    alliberaments_per_nivell=cfg.alliberaments,
                    data_iso=data_iso_slot,
                )
                # El validador posterior fa servir l'anàlisi nova
                if isinstance(sessio, dict):
                    sessio["analisi"] = analisi

                incidencies_sessio = list(incidencies(analisi, hora, dia_nom, restriccions))
                for incidencia in incidencies_sessio:
                    franja.afegeix(*incidencia)
                # Els avisos de cada examen, per a l'editor (per _uid i per item_id)
                if isinstance(sessio, dict) and incidencies_sessio:
                    avisos_sessio = [avis for _, _, _, avis, _ in incidencies_sessio]
                    for clau in (sessio.get("_uid"), sessio.get("item_id")):
                        if clau:
                            item_avisos[clau] = avisos_sessio

            avisos = franja.avisos
            if conflicte_nivell:
                avisos.insert(0, "⚠️ CONFLICTE: Múltiples exàmens del mateix nivell!")

            slots_info.append(
                {
                    "slot_key": f"{data_iso_slot or dia_nom}_{hora}",
                    "cost": franja.cost,
                    "breakdown": {"sessions": len(sessions_sim)},
                    "conflicte_nivell": conflicte_nivell,
                    "avisos": avisos,
                    "item_avisos": item_avisos,
                }
            )

    # Netejar logs antics per evitar que el validador ometi avisos (p. ex. LÍMIT DIES)
    if horari.get("metadata", {}).get("logs"):
        horari["metadata"]["logs"] = []
    validation_result = ValidadorHorari(horari, restriccions, cfg.no_substituir).validar()

    breakdown_details = {}
    excessos = excessos_limit_dies(horari, restriccions)
    if excessos:
        breakdown_details["limit_dies_professor"] = excessos

    # L'horari editat a mà passa a ser l'últim, amb el cost i les incidències nous
    horari_desat = dict(
        horari,
        metadata={
            **(horari.get("metadata") or {}),
            "cost_total": cost_info.get("cost_total", 0),
            "logs": validation_result.get("logs", []),
            "total_substitucions": cost_info.get("total_substitucions", 0),
            "professors_abans": cost_info.get("professors_abans", 0),
            "professors_despres": cost_info.get("professors_despres", 0),
            "professors_no_treballa": cost_info.get("professors_no_treballa", 0),
        },
    )
    _desa_ultim_resultat(current_user.institucio, horari_desat)

    return {
        "cost_total": cost_info.get("cost_total", 0),
        "cost_breakdown": cost_info.get("cost_breakdown", {}),
        "cost_breakdown_details": breakdown_details,
        "slots": slots_info,
        "valid": not conflicte_global,
        "logs": validation_result.get("logs", []),
        "stats": {
            "total_substitucions": cost_info.get("total_substitucions", 0),
            "professors_abans": cost_info.get("professors_abans", 0),
            "professors_despres": cost_info.get("professors_despres", 0),
            "professors_no_treballa": cost_info.get("professors_no_treballa", 0),
        },
    }
