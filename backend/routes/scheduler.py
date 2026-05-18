from pathlib import Path
from collections import defaultdict
import json
import os
import tempfile
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from auth_utils import require_admin
from database import get_data_db_session
from repositories import MasterConfigRepository, ConfiguracioExamenRepository, ConfiguracioRepository, VigilanciaRepository, GrupsAlliberatsRepository, parse_date
from helpers import get_xml_path_for_date
from models import ExamCostProfessor, ExamRestriccio, Vigilancia, Substitucio, GrupAlliberat, Nivell, Grup, AbreviaturaGrup
from schemas import SchedulerGenerateRequest, SchedulerDatesRequest, SchedulerRestriccionsRequest, SchedulerPinRequest, SchedulerPublicarRequest, HorariRecalcularRequest
from routes.scheduler_service import (
    SCHEDULER_DATES_KEY,
    SCHEDULER_NIVELLS_KEY,
    SCHEDULER_ALLIBERAMENTS_KEY,
    SCHEDULER_DURADA_KEY,
    SCHEDULER_DURADA_EXAMEN_KEY,
    SCHEDULER_DURADES_SESSIO_KEY,
    SCHEDULER_DURADES_GRUPS_KEY,
    _load_json,
    _dies_entre_dates,
    _build_config_from_db,
    _build_restriccions_from_db,
    _save_restriccions_to_db,
)
from routes.scheduler_helpers import (
    _nivells_master,
    _detectar_nivell,
    _extract_assignatures_from_restriccions,
    _selected_dates_from_alliberaments,
    _normalitzar_hora,
    _hores_lectives_des_de_xml,
    _build_slots_valids_from_alliberaments,
    _build_slots_valids_iso_from_alliberaments,
    _merge_slots_valids,
    _build_assignatures_options,
    extreure_hores_examen_des_alliberaments,
)
from routes.scheduler_analysis_helpers import (
    _diagnosticar_incompatibilitats,
    _precheck_incompatibilitats_deterministes,
    _afegir_recompte_nivells,
    _write_analysis_pdf,
    _identificar_sessions_no_collocades,
)

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

from scheduler_engine.defaults import DEFAULT_COST_PROFESSORS, DEFAULT_DURADA_TITULAR
from scheduler_engine.core.date_mapping import construir_mapa_dia_data_iso
from scheduler_engine.core.normalitzacio import normalitzar_dia

@router.get("/status")
async def scheduler_status(current_user=Depends(require_admin)):
    p = Path(__file__).resolve().parents[1] / "scheduler_engine" / "generators" / "v3_sa.py"
    return {"available": p.exists(), "engine_path": str(p.parent), "message": "OK" if p.exists() else "Pending", "institucio": current_user.institucio}

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
    També retorna les hores lectives del centre i la durada titular configurada.
    """
    with get_data_db_session(current_user.institucio) as db:
        # Carregar abreviatures per poder expandir
        abreviatures = {}
        for abr in db.query(AbreviaturaGrup).all():
            abreviatures[abr.abreviatura] = [g.strip() for g in abr.grups_originals.split(',')]

        # Carregar grups per nivell
        result = {}
        nivells = db.query(Nivell).filter(Nivell.actiu == True).order_by(Nivell.ordre).all()
        for nivell in nivells:
            if nivell.codi in ('GENERAL', 'RECERCA'):
                continue
            grups = db.query(Grup).filter(
                Grup.nivell_id == nivell.id, Grup.actiu == True
            ).order_by(Grup.ordre, Grup.codi).all()

            grups_list = []
            for g in grups:
                expandits = abreviatures.get(g.codi)
                grups_list.append({
                    'codi': g.codi,
                    'es_abreviatura': expandits is not None,
                    'grups_expandits': expandits or [],
                })
            if grups_list:
                result[nivell.codi] = grups_list

        # Carregar durades configurades
        d_raw = ConfiguracioRepository.get(db, SCHEDULER_DURADA_KEY)
        durada_titular = int(d_raw) if d_raw else DEFAULT_DURADA_TITULAR
        de_raw = ConfiguracioRepository.get(db, SCHEDULER_DURADA_EXAMEN_KEY)
        durada_examen_cfg = int(de_raw) if de_raw else durada_titular

    # Carregar hores lectives del centre (des de l'XML, usant data actual)
    hores_lectives = []
    try:
        from helpers import get_horari
        from datetime import date
        data_avui = date.today().isoformat()
        horari_obj = get_horari(current_user.institucio, data_avui)
        hores_lectives = horari_obj.hores or []
    except Exception:
        pass

    return {
        "grups_per_nivell": result,
        "hores_lectives": hores_lectives,
        "durada_titular": durada_titular,
        "durada_examen": durada_examen_cfg,
    }


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
    h, hpn = extreure_hores_examen_des_alliberaments(alliberaments)
    return {
        "nivells": list(master.get("nivells", {}).keys()),
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
        if "durada_titular" in payload: ConfiguracioRepository.set(db, SCHEDULER_DURADA_KEY, str(payload["durada_titular"]), tipus="integer")
        if "durada_examen" in payload: ConfiguracioRepository.set(db, SCHEDULER_DURADA_EXAMEN_KEY, str(payload["durada_examen"]), tipus="integer")
        if "nivells_actius" in payload: ConfiguracioRepository.set(db, SCHEDULER_NIVELLS_KEY, json.dumps(payload["nivells_actius"]), tipus="json")
        if "alliberaments_per_nivell" in payload: ConfiguracioRepository.set(db, SCHEDULER_ALLIBERAMENTS_KEY, json.dumps(payload["alliberaments_per_nivell"]), tipus="json")
        if "durades_grups" in payload: ConfiguracioRepository.set(db, SCHEDULER_DURADES_GRUPS_KEY, json.dumps(payload["durades_grups"]), tipus="json")
    return {"success": True}

@router.get("/restriccions")
async def scheduler_restriccions(current_user=Depends(require_admin)):
    with get_data_db_session(current_user.institucio) as db: return {"restriccions": _build_restriccions_from_db(db)}

@router.put("/restriccions")
async def scheduler_restriccions_update(payload: SchedulerRestriccionsRequest, current_user=Depends(require_admin)):
    with get_data_db_session(current_user.institucio) as db:
        try:
            _save_restriccions_to_db(db, payload.restriccions or {})
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
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
                    existing = db.query(ExamRestriccio).filter(
                        ExamRestriccio.tipus == tipus,
                        ExamRestriccio.clau == pin.nom,
                    ).first()
                    if existing:
                        existing.configuracio = json.dumps(valor, ensure_ascii=False)
                        existing.pes = 100
                        existing.activa = True
                    else:
                        db.add(ExamRestriccio(
                            tipus=tipus,
                            clau=pin.nom,
                            configuracio=json.dumps(valor, ensure_ascii=False),
                            pes=100,
                            activa=True,
                        ))

            db.commit()

            # Retornar l'estat actual dels pins
            pins_dia = {}
            pins_hora = {}
            for r in db.query(ExamRestriccio).filter(
                ExamRestriccio.tipus.in_(["assignatures_dia_fix", "assignatures_hora_fix"]),
                ExamRestriccio.activa == True,
            ).all():
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
                }
            }
        except Exception as exc:
            db.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc


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
            pass

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
                    db.add(ExamCostProfessor(professor=professor, tipus=tipus, pes=int(pes)))

            db.commit()
            return {"success": True}
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=str(e))


@router.put("/costos-professors/{professor}")
async def update_cost_professor_individual(professor: str, payload: dict, current_user=Depends(require_admin)):
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
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=str(e))


@router.delete("/costos-professors/{professor}")
async def delete_cost_professor_individual(professor: str, current_user=Depends(require_admin)):
    """Elimina els costos individuals d'un professor (tornarà a usar globals)."""
    with get_data_db_session(current_user.institucio) as db:
        try:
            deleted = db.query(ExamCostProfessor).filter(ExamCostProfessor.professor == professor).delete()
            db.commit()
            return {"success": True, "deleted": deleted}
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/dates")
async def scheduler_dates(current_user=Depends(require_admin)):
    with get_data_db_session(current_user.institucio) as db: return {"selected_dates": _load_json(ConfiguracioRepository.get(db, SCHEDULER_DATES_KEY), [])}

@router.put("/dates")
async def scheduler_dates_update(payload: SchedulerDatesRequest, current_user=Depends(require_admin)):
    with get_data_db_session(current_user.institucio) as db: ConfiguracioRepository.set(db, SCHEDULER_DATES_KEY, json.dumps(payload.selected_dates or []), tipus="json")
    return {"success": True}

@router.get("/sessions-info")
async def get_scheduler_sessions_info(nivells: str = None, current_user=Depends(require_admin)):
    with get_data_db_session(current_user.institucio) as db:
        assignacions = ConfiguracioExamenRepository.get_all(db)
        restr = _build_restriccions_from_db(db)
        nivells_master = _nivells_master(db)
    filtre = nivells.split(',') if nivells else []
    extra = _extract_assignatures_from_restriccions(restr)
    return _build_assignatures_options(assignacions, nivells_master, only_nivells=filtre, extra=extra)

@router.get("/assignatures-actives")
async def get_assignatures_actives(current_user=Depends(require_admin)):
    with get_data_db_session(current_user.institucio) as db:
        assignacions = ConfiguracioExamenRepository.get_all(db)
        restr = _build_restriccions_from_db(db)
        nivells_master = _nivells_master(db)
    extra = _extract_assignatures_from_restriccions(restr)
    return _build_assignatures_options(assignacions, nivells_master, extra=extra)

@router.post("/generate")
async def scheduler_generate(payload: SchedulerGenerateRequest, current_user=Depends(require_admin)):
    with get_data_db_session(current_user.institucio) as db:
        assignacions = ConfiguracioExamenRepository.get_all(db)
        config = _build_config_from_db(assignacions)
        restriccions = _build_restriccions_from_db(db)
        print(f"🔍 Restriccions carregades de BD:")
        print(f"   mateix_slot: {len(restriccions.get('restriccions_dures', {}).get('mateix_slot', []))} grups")
        print(f"   no_mateix_slot: {len(restriccions.get('restriccions_dures', {}).get('no_mateix_slot', {}))} grups")
        for i, grup in enumerate(restriccions.get('restriccions_dures', {}).get('mateix_slot', [])[:5]):
            print(f"      Grup {i+1}: {grup}")
        d_raw = ConfiguracioRepository.get(db, SCHEDULER_DURADA_KEY)
        n_raw = ConfiguracioRepository.get(db, SCHEDULER_NIVELLS_KEY)
        dates_raw = ConfiguracioRepository.get(db, SCHEDULER_DATES_KEY)
        ultim_professor = ConfiguracioRepository.get(db, "ultim_professor_subs") or ""
        d_cfg = int(d_raw) if d_raw else DEFAULT_DURADA_TITULAR
        n_cfg = _load_json(n_raw, [])
        selected_dates_cfg = _load_json(dates_raw, [])
        nivells_master = _nivells_master(db)

        # Carregar alliberaments per nivell (estructura amb dates ISO i config per hora)
        alliberaments_raw = ConfiguracioRepository.get(db, SCHEDULER_ALLIBERAMENTS_KEY)
        alliberaments_cfg = _load_json(alliberaments_raw, {})

        # Carregar durades específiques per sessió (format grups → dict pla)
        durades_grups_raw = ConfiguracioRepository.get(db, SCHEDULER_DURADES_GRUPS_KEY)
        durades_grups_cfg = _load_json(durades_grups_raw, None)
        if durades_grups_cfg:
            durades_per_sessio_cfg = {}
            durades_examen_per_sessio_cfg = {}
            for grup in durades_grups_cfg:
                for ass in grup.get("assignatures", []):
                    durades_per_sessio_cfg[ass] = grup.get("durada", 1)
                    durades_examen_per_sessio_cfg[ass] = grup.get("durada_examen", grup.get("durada", 1))
        else:
            # Backward compat: llegir format antic
            durades_per_sessio_cfg = _load_json(ConfiguracioRepository.get(db, SCHEDULER_DURADES_SESSIO_KEY), {})
            durades_examen_per_sessio_cfg = dict(durades_per_sessio_cfg)  # Igual que supervisió si no hi ha grups
        print(f"   alliberaments_per_nivell: {len(alliberaments_cfg)} nivells configurats")

        # Carregar assignatures que NO necessiten substitució
        from repositories import NoSubstituirRepository
        no_subst = set(NoSubstituirRepository.get_all(db))
        print(f"   no_substituir: {len(no_subst)} assignatures")

    # Derivar hores d'examen únicament dels alliberaments (marques i=true)
    h_cfg, hpn_cfg = extreure_hores_examen_des_alliberaments(alliberaments_cfg)

    xml_path = get_xml_path_for_date(current_user.institucio, payload.data_inici)
    if not xml_path or not os.path.exists(xml_path): raise HTTPException(status_code=400, detail="XML missing")

    dies_util = payload.dies_utilitzar or _dies_entre_dates(payload.data_inici, payload.data_final or payload.data_inici)
    nivells_actius = payload.nivells_actius or n_cfg or nivells_master
    selected_dates = payload.selected_dates or selected_dates_cfg or []
    dates_allib = _selected_dates_from_alliberaments(alliberaments_cfg, nivells_actius)
    if dates_allib:
        selected_dates = dates_allib
    dia_a_data_iso = construir_mapa_dia_data_iso(
        dies_utilitzar=dies_util,
        selected_dates=selected_dates,
        data_inici_iso=payload.data_inici,
    )

    # Derivar slots vàlids per nivell des de les marques (inici examen) del Tab 1.
    hores_xml = _hores_lectives_des_de_xml(xml_path, fallback=h_cfg)
    slots_derivats = _build_slots_valids_from_alliberaments(
        alliberaments_cfg=alliberaments_cfg,
        nivells_actius=nivells_actius,
        dies_utilitzar=dies_util,
        dia_a_data_iso=dia_a_data_iso,
        hores_disponibles=hores_xml,
    )
    dures = restriccions.setdefault("restriccions_dures", {})
    slots_actuals = dures.get("slots_valids_per_nivell") or {}
    dures["slots_valids_per_nivell"] = _merge_slots_valids(slots_actuals, slots_derivats)
    dates_per_nivell = {
        niv: [d for d in (alliberaments_cfg.get(niv) or {}).get("dates", []) if isinstance(d, str)]
        for niv in (nivells_actius or [])
        if isinstance((alliberaments_cfg or {}).get(niv), dict) and (alliberaments_cfg[niv].get("dates") or [])
    }
    if dates_per_nivell:
        dures["dates_per_nivell"] = dates_per_nivell
    slots_iso = _build_slots_valids_iso_from_alliberaments(alliberaments_cfg, nivells_actius, hores_xml)
    if slots_iso:
        dures["slots_valids_iso_per_nivell"] = slots_iso

    data_inici_fmt = datetime.strptime(payload.data_inici, "%Y-%m-%d").strftime("%d/%m/%Y")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as cfg_f: json.dump(config, cfg_f, ensure_ascii=False); cfg_p = cfg_f.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as res_f: json.dump(restriccions, res_f, ensure_ascii=False); res_p = res_f.name

    try:
        import io, sys
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            motor = (payload.motor or "v3").lower()

            # Crear motor via factory (elimina duplicació de constructor)
            from scheduler_engine.factory import crear_motor
            override_params = {}
            if motor == "v3":
                for key in ('temperatura_inicial', 'temperatura_final', 'factor_refredament',
                            'iteracions_per_temperatura', 'max_iteracions'):
                    val = getattr(payload, key, None)
                    if val is not None:
                        override_params[key] = val

            gen, method_name = crear_motor(
                motor, cfg_p, xml_path,
                restriccions_path=res_p,
                ultim_professor=ultim_professor,
                nivells_actius=nivells_actius,
                hores_examen=h_cfg,
                hores_per_nivell=hpn_cfg,
                durada_titular=d_cfg,
                no_substituir=no_subst,
                alliberaments_per_nivell=alliberaments_cfg,
                durades_per_sessio=durades_per_sessio_cfg,
                durades_examen_per_sessio=durades_examen_per_sessio_cfg,
                **override_params
            )
            gen.carregar_dades()
            gen.carregar_horaris_professors()

            precheck_incompat = _precheck_incompatibilitats_deterministes(
                gen=gen,
                restriccions=restriccions,
                dies_utilitzar=dies_util,
                nivells_actius=nivells_actius,
                selected_dates=selected_dates,
            )

            if precheck_incompat:
                horari = {
                    'dies': [],
                    'metadata': {
                        'viable': False,
                        'error': "No s'han pogut col·locar tots els exàmens",
                        'incompatibilitats': precheck_incompat,
                        'motor': motor,
                        'logs': ["❌ Precheck de viabilitat: incompatibilitats deterministes detectades"],
                    }
                }
            else:
                # Preparar arguments específics del mètode
                method = getattr(gen, method_name)
                method_kwargs = {
                    'data_inici': data_inici_fmt,
                    'data_inici_iso': payload.data_inici,  # Format YYYY-MM-DD per als alliberaments
                    'dies_utilitzar': dies_util,
                    'dia_a_data_iso': dia_a_data_iso,
                    'max_dies': payload.max_dies,
                    'selected_dates': selected_dates,
                }
                if motor == "v2":
                    method_kwargs.update({
                        'max_intents_validacio': payload.max_intents_validacio,
                        'estrategia': payload.estrategia,
                        'epsilon': payload.epsilon,
                        'track_intents': True,
                    })
                elif motor == "v2-backtrack":
                    method_kwargs['max_solucions'] = 100
                    if payload.random_seed is not None:
                        method_kwargs['random_seed'] = payload.random_seed
                    if payload.seeds_count is not None:
                        method_kwargs['seeds_count'] = payload.seeds_count
                    if payload.max_nodes is not None:
                        method_kwargs['max_nodes'] = payload.max_nodes
                    if payload.shuffle_top_n is not None:
                        method_kwargs['shuffle_top_n'] = payload.shuffle_top_n

                import time as _time
                _t0 = _time.monotonic()
                result = method(**method_kwargs)
                _temps_ms = int((_time.monotonic() - _t0) * 1000)

                # Post-processament per v2-backtrack (retorna llista)
                if motor == "v2-backtrack":
                    if result:
                        horari = result[0]
                        if horari.get('metadata', {}).get('viable', True):
                            horari['metadata']['alternatives'] = len(result)
                            horari['metadata']['motor'] = 'v2-backtrack'
                    else:
                        horari = {
                            'metadata': {
                                'viable': False,
                                'error': 'El backtracking no ha trobat cap solució vàlida',
                                'motor': 'v2-backtrack'
                            },
                            'dies': []
                        }
                else:
                    horari = result

                if isinstance(horari, dict):
                    horari.setdefault('metadata', {})['temps_generacio_ms'] = _temps_ms

        if isinstance(horari, dict):
            sessions_per_nivell = getattr(gen, "sessions_per_nivell", {}) or {}
            if not isinstance(sessions_per_nivell, dict):
                sessions_per_nivell = {}
            has_expected = False
            for v in sessions_per_nivell.values():
                if isinstance(v, (list, tuple, set)) and v:
                    has_expected = True
                    break
                if isinstance(v, dict) and v:
                    has_expected = True
                    break
            if not has_expected:
                sessions_list = getattr(gen, "sessions", None)
                if sessions_list:
                    tmp = defaultdict(list)
                    for s in sessions_list:
                        nivell = getattr(s, "curs", None) if not isinstance(s, dict) else s.get("curs")
                        if nivell:
                            tmp[nivell].append(s)
                    sessions_per_nivell = tmp
            _afegir_recompte_nivells(horari, sessions_per_nivell)
            recompte = ((horari.get("metadata") or {}).get("recompte_nivells") or {})
            pendents_total = sum((info or {}).get("pendents", 0) for info in recompte.values())
            if pendents_total > 0:
                meta_h = horari.setdefault("metadata", {})
                meta_h.setdefault("logs", []).append(
                    f"⚠️ Sessions pendents de col·locar: {pendents_total}"
                )
                if meta_h.get("viable", True):
                    meta_h["viable"] = False
                    meta_h["error"] = "No s'han pogut col·locar tots els exàmens"

        # FORA del redirect_stdout - validació post-generació
        if horari and "metadata" in horari:
            meta = horari.get('metadata', {})

            # Comprovar viabilitat
            if not meta.get('viable', True):
                error_msg = meta.get('error', 'No és possible col·locar tots els exàmens')
                incompat = _diagnosticar_incompatibilitats(
                    gen=gen,
                    restriccions=restriccions,
                    dies_utilitzar=dies_util,
                    dia_a_data_iso=dia_a_data_iso,
                    alliberaments_cfg=alliberaments_cfg,
                    nivells_actius=nivells_actius,
                )
                if not incompat:
                    # Prioritat 2: missatges propis del motor (ex: ítem sense slot de v3-SA)
                    incompat = meta.get('incompatibilitats') or []
                if not incompat:
                    # Prioritat 2.5: infactibilitats del motor (ex: items exclosos backtrack o dead-end)
                    incompat = getattr(gen, '_incompatibilitats_bt', []) or []
                if not incompat:
                    # Prioritat 3: identificació per nom + fallback recompte_nivells
                    incompat = _identificar_sessions_no_collocades(horari, gen)
                if incompat:
                    meta['incompatibilitats'] = incompat
                logs_viable = meta.setdefault('logs', [])
                logs_viable.append(f"❌ {error_msg}")
                seen_logs = set()
                horari['metadata']['logs'] = [l for l in logs_viable if not (l in seen_logs or seen_logs.add(l))]
                return {"status": "ok", "horari": horari}

            # Validar horari contra restriccions
            from scheduler_engine.validacio import ValidadorHorari
            validador = ValidadorHorari(horari, restriccions, no_subst)
            validation_result = validador.validar()

            # Capturar tots els logs: motor metadata + stdout capturada + validació
            raw_logs = []
            raw_logs.extend([line.strip() for line in meta.get("logs", []) if line.strip()])
            raw_logs.extend([line.strip() for line in f.getvalue().splitlines() if line.strip()])
            raw_logs.extend(validation_result["logs"])
            # Dedup mantenint ordre
            seen = set()
            horari["metadata"]["logs"] = [l for l in raw_logs if not (l in seen or seen.add(l))]

        return {"dies_utilitzar": dies_util, "horari": horari}
    finally:
        for p in (cfg_p, res_p):
            try: os.remove(p)
            except: pass


@router.post("/analisi")
async def scheduler_analisi(payload: SchedulerGenerateRequest, current_user=Depends(require_admin)):
    with get_data_db_session(current_user.institucio) as db:
        assignacions = ConfiguracioExamenRepository.get_all(db)
        config = _build_config_from_db(assignacions)
        restriccions = _build_restriccions_from_db(db)
        d_raw = ConfiguracioRepository.get(db, SCHEDULER_DURADA_KEY)
        n_raw = ConfiguracioRepository.get(db, SCHEDULER_NIVELLS_KEY)
        dates_raw = ConfiguracioRepository.get(db, SCHEDULER_DATES_KEY)
        alliberaments_raw = ConfiguracioRepository.get(db, SCHEDULER_ALLIBERAMENTS_KEY)
        ultim_professor = ConfiguracioRepository.get(db, "ultim_professor_subs") or ""
        d_cfg = int(d_raw) if d_raw else DEFAULT_DURADA_TITULAR
        n_cfg = _load_json(n_raw, [])
        selected_dates_cfg = _load_json(dates_raw, [])
        alliberaments_cfg = _load_json(alliberaments_raw, {})
        nivells_master = _nivells_master(db)

        from repositories import NoSubstituirRepository
        no_subst = set(NoSubstituirRepository.get_all(db))

    h_cfg, hpn_cfg = extreure_hores_examen_des_alliberaments(alliberaments_cfg)

    xml_path = get_xml_path_for_date(current_user.institucio, payload.data_inici)
    if not xml_path or not os.path.exists(xml_path):
        raise HTTPException(status_code=400, detail="XML missing")

    dies_util = payload.dies_utilitzar or _dies_entre_dates(payload.data_inici, payload.data_final or payload.data_inici)
    nivells_actius = (payload.nivells_actius or n_cfg or nivells_master)
    selected_dates = selected_dates_cfg or []
    dates_allib = _selected_dates_from_alliberaments(alliberaments_cfg, nivells_actius)
    if dates_allib:
        selected_dates = dates_allib
    dia_a_data_iso = construir_mapa_dia_data_iso(
        dies_utilitzar=dies_util,
        selected_dates=selected_dates,
        data_inici_iso=payload.data_inici,
    )

    # Derivar slots vàlids per nivell (inici examen)
    hores_xml = _hores_lectives_des_de_xml(xml_path, fallback=h_cfg)
    slots_derivats = _build_slots_valids_from_alliberaments(
        alliberaments_cfg=alliberaments_cfg,
        nivells_actius=nivells_actius,
        dies_utilitzar=dies_util,
        dia_a_data_iso=dia_a_data_iso,
        hores_disponibles=hores_xml,
    )
    dures = restriccions.setdefault("restriccions_dures", {})
    slots_actuals = dures.get("slots_valids_per_nivell") or {}
    dures["slots_valids_per_nivell"] = _merge_slots_valids(slots_actuals, slots_derivats)
    dates_per_nivell = {
        niv: [d for d in (alliberaments_cfg.get(niv) or {}).get("dates", []) if isinstance(d, str)]
        for niv in (nivells_actius or [])
        if isinstance((alliberaments_cfg or {}).get(niv), dict) and (alliberaments_cfg[niv].get("dates") or [])
    }
    if dates_per_nivell:
        dures["dates_per_nivell"] = dates_per_nivell
    slots_iso = _build_slots_valids_iso_from_alliberaments(alliberaments_cfg, nivells_actius, hores_xml)
    if slots_iso:
        dures["slots_valids_iso_per_nivell"] = slots_iso

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as cfg_f:
        json.dump(config, cfg_f, ensure_ascii=False)
        cfg_p = cfg_f.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as res_f:
        json.dump(restriccions, res_f, ensure_ascii=False)
        res_p = res_f.name

    try:
        from scheduler_engine.factory import crear_motor
        gen, _ = crear_motor(
            "v2",
            cfg_p,
            xml_path,
            restriccions_path=res_p,
            ultim_professor=ultim_professor,
            nivells_actius=nivells_actius,
            hores_examen=h_cfg,
            hores_per_nivell=hpn_cfg,
            durada_titular=d_cfg,
            no_substituir=no_subst,
            alliberaments_per_nivell=alliberaments_cfg,
        )
        gen.carregar_dades()
        gen.carregar_horaris_professors()
        gen.dia_a_data_iso = {normalitzar_dia(k): v for k, v in (dia_a_data_iso or {}).items() if v}
        dies_analisi = _expandir_dies_per_analisi(dies_util, gen.dia_a_data_iso)

        matriu_costos = gen._analitzar_tots_slots(dies_analisi)
        informe_slots = gen.generar_informe_per_slots(matriu_costos, dies_analisi)
        informe_sessio = gen.generar_informe_disponibilitat(matriu_costos, dies_analisi)
        informe_prof = gen.generar_informe_professors_per_slot(dies_analisi)

        return {
            "per_slots": informe_slots,
            "per_sessio": informe_sessio,
            "professors_slot": informe_prof
        }
    finally:
        for p in (cfg_p, res_p):
            try:
                os.remove(p)
            except:
                pass


@router.post("/analisi/pdf")
async def scheduler_analisi_pdf(payload: SchedulerGenerateRequest, current_user=Depends(require_admin)):
    with get_data_db_session(current_user.institucio) as db:
        assignacions = ConfiguracioExamenRepository.get_all(db)
        config = _build_config_from_db(assignacions)
        restriccions = _build_restriccions_from_db(db)
        d_raw = ConfiguracioRepository.get(db, SCHEDULER_DURADA_KEY)
        n_raw = ConfiguracioRepository.get(db, SCHEDULER_NIVELLS_KEY)
        dates_raw = ConfiguracioRepository.get(db, SCHEDULER_DATES_KEY)
        alliberaments_raw = ConfiguracioRepository.get(db, SCHEDULER_ALLIBERAMENTS_KEY)
        ultim_professor = ConfiguracioRepository.get(db, "ultim_professor_subs") or ""
        d_cfg = int(d_raw) if d_raw else DEFAULT_DURADA_TITULAR
        n_cfg = _load_json(n_raw, [])
        selected_dates_cfg = _load_json(dates_raw, [])
        alliberaments_cfg = _load_json(alliberaments_raw, {})
        nivells_master = _nivells_master(db)

        from repositories import NoSubstituirRepository
        no_subst = set(NoSubstituirRepository.get_all(db))

    h_cfg, hpn_cfg = extreure_hores_examen_des_alliberaments(alliberaments_cfg)

    xml_path = get_xml_path_for_date(current_user.institucio, payload.data_inici)
    if not xml_path or not os.path.exists(xml_path):
        raise HTTPException(status_code=400, detail="XML missing")

    dies_util = payload.dies_utilitzar or _dies_entre_dates(payload.data_inici, payload.data_final or payload.data_inici)
    nivells_actius = (payload.nivells_actius or n_cfg or nivells_master)
    selected_dates = selected_dates_cfg or []
    dates_allib = _selected_dates_from_alliberaments(alliberaments_cfg, nivells_actius)
    if dates_allib:
        selected_dates = dates_allib
    dia_a_data_iso = construir_mapa_dia_data_iso(
        dies_utilitzar=dies_util,
        selected_dates=selected_dates,
        data_inici_iso=payload.data_inici,
    )

    hores_xml = _hores_lectives_des_de_xml(xml_path, fallback=h_cfg)
    slots_derivats = _build_slots_valids_from_alliberaments(
        alliberaments_cfg=alliberaments_cfg,
        nivells_actius=nivells_actius,
        dies_utilitzar=dies_util,
        dia_a_data_iso=dia_a_data_iso,
        hores_disponibles=hores_xml,
    )
    dures = restriccions.setdefault("restriccions_dures", {})
    slots_actuals = dures.get("slots_valids_per_nivell") or {}
    dures["slots_valids_per_nivell"] = _merge_slots_valids(slots_actuals, slots_derivats)
    dates_per_nivell = {
        niv: [d for d in (alliberaments_cfg.get(niv) or {}).get("dates", []) if isinstance(d, str)]
        for niv in (nivells_actius or [])
        if isinstance((alliberaments_cfg or {}).get(niv), dict) and (alliberaments_cfg[niv].get("dates") or [])
    }
    if dates_per_nivell:
        dures["dates_per_nivell"] = dates_per_nivell
    slots_iso = _build_slots_valids_iso_from_alliberaments(alliberaments_cfg, nivells_actius, hores_xml)
    if slots_iso:
        dures["slots_valids_iso_per_nivell"] = slots_iso

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as cfg_f:
        json.dump(config, cfg_f, ensure_ascii=False)
        cfg_p = cfg_f.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as res_f:
        json.dump(restriccions, res_f, ensure_ascii=False)
        res_p = res_f.name

    pdf_path = None
    try:
        from scheduler_engine.factory import crear_motor
        gen, _ = crear_motor(
            "v2",
            cfg_p,
            xml_path,
            restriccions_path=res_p,
            ultim_professor=ultim_professor,
            nivells_actius=nivells_actius,
            hores_examen=h_cfg,
            hores_per_nivell=hpn_cfg,
            durada_titular=d_cfg,
            no_substituir=no_subst,
            alliberaments_per_nivell=alliberaments_cfg,
        )
        gen.carregar_dades()
        gen.carregar_horaris_professors()
        gen.dia_a_data_iso = {normalitzar_dia(k): v for k, v in (dia_a_data_iso or {}).items() if v}
        dies_analisi = _expandir_dies_per_analisi(dies_util, gen.dia_a_data_iso)

        matriu_costos = gen._analitzar_tots_slots(dies_analisi)
        informe_slots = gen.generar_informe_per_slots(matriu_costos, dies_analisi)
        informe_sessio = gen.generar_informe_disponibilitat(matriu_costos, dies_analisi)
        informe_prof = gen.generar_informe_professors_per_slot(dies_analisi)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as pdf_f:
            pdf_path = pdf_f.name
        requested_tab = (payload.analisi_tab or "").strip()
        sections_map = {
            "per_slots": ("Per Hora/Dia", "per_slots", informe_slots),
            "per_sessio": ("Per Agrupacio", "per_sessio", informe_sessio),
            "professors_slot": ("Professors per Slot", "professors_slot", informe_prof)
        }
        if requested_tab in sections_map:
            sections = [sections_map[requested_tab]]
        else:
            sections = [
                ("Per Hora/Dia", "per_slots", informe_slots),
                ("Per Agrupacio", "per_sessio", informe_sessio),
                ("Professors per Slot", "professors_slot", informe_prof)
            ]
        _write_analysis_pdf(pdf_path, sections)
        filename = f"analisi_{payload.data_inici}.pdf"
        return FileResponse(pdf_path, media_type="application/pdf", filename=filename)
    finally:
        for p in (cfg_p, res_p):
            try:
                os.remove(p)
            except:
                pass


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
    durada_examen = max(1, payload.durada_examen)
    opcions = payload.opcions
    dry_run = payload.dry_run

    if not horari or not horari.get('dies'):
        raise HTTPException(status_code=400, detail="L'horari no conté dies")
    if not setmanes:
        raise HTTPException(status_code=400, detail="Cal indicar almenys una setmana amb dates")

    # Carregar hores lectives del centre (per expandir durada)
    totes_hores = []
    # Trobar la primera data per carregar l'XML
    primera_data = None
    for die in horari.get('dies', []):
        primera_data = die.get('data') if isinstance(die, dict) else None
        if primera_data:
            break
    if not primera_data:
        for setmana in setmanes:
            for dia_nom in horari.get('dies', []):
                d = setmana.get(dia_nom.get('dia', '')) if isinstance(dia_nom, dict) else setmana.get(dia_nom, '')
                if d:
                    primera_data = d
                    break
            if primera_data:
                break

    if primera_data:
        try:
            from helpers import get_horari as get_horari_fn
            horari_obj = get_horari_fn(current_user.institucio, primera_data)
            totes_hores = horari_obj.hores or []
        except Exception as e:
            import logging
            logging.warning(f"No s'han pogut carregar hores lectives: {e}")

    dates_processades = []
    vigilancies_creades = 0
    vigilancies_actualitzades = 0
    vigilancies_sense_canvis = 0
    vigilancies_eliminades = 0
    grups_alliberats_creats = 0
    titulars_assignats = 0
    errors = []

    with get_data_db_session(current_user.institucio) as db:
        alliberaments_raw = ConfiguracioRepository.get(db, SCHEDULER_ALLIBERAMENTS_KEY)
        alliberaments_cfg = _load_json(alliberaments_raw, {})
        nivells_alliberaments = list(alliberaments_cfg.keys()) if isinstance(alliberaments_cfg, dict) else []

        def _nivell_per_grup(grup: str) -> str | None:
            if not grup:
                return None
            for nivell in nivells_alliberaments:
                if nivell and nivell in grup:
                    return nivell
            try:
                from scheduler_engine.core.constraints import detectar_nivell_grup
                nivell = detectar_nivell_grup(grup, nivells_alliberaments)
                return None if nivell == 'altres' else nivell
            except Exception:
                return None

        def _hores_alliberades(nivell: str, data_iso: str) -> list[str]:
            data_cfg = (alliberaments_cfg or {}).get(nivell, {})
            dia_cfg = (data_cfg.get('config') or {}).get(data_iso, {})
            hores = []
            for h, flags in (dia_cfg or {}).items():
                if isinstance(flags, dict) and flags.get('a'):
                    hores.append(_normalitzar_hora(h))
            if totes_hores:
                ordre = {h: i for i, h in enumerate(totes_hores)}
                hores = sorted(set(hores), key=lambda h: ordre.get(h, 10**9))
            else:
                hores = sorted(set(hores))
            return hores

        for dia_info in horari['dies']:
            dia_nom = dia_info.get('dia', '')
            data_iso = dia_info.get('data')
            if not data_iso:
                for setmana in setmanes:
                    d = setmana.get(dia_nom)
                    if d:
                        data_iso = d
                        break
            if not data_iso:
                continue

            data_parsed = parse_date(data_iso)
            dates_processades.append(data_iso)

            try:
                # Mode forçat: esborra tot i recrea (opció d'emergència)
                if opcions.netejar_existents:
                    deleted = db.query(Vigilancia).filter(
                        Vigilancia.data == data_parsed
                    ).delete(synchronize_session=False)
                    vigilancies_eliminades += deleted
                    db.query(GrupAlliberat).filter(
                        GrupAlliberat.data == data_parsed
                    ).delete(synchronize_session=False)
                    db.query(Substitucio).filter(
                        Substitucio.data == data_parsed,
                        Substitucio.tipus_absencia == "VIGILANCIA"
                    ).delete(synchronize_session=False)
                    db.flush()

                # 1. Construir el conjunt de vigilàncies que ha de quedar
                # Clau: (hora, nivell, grups) — preserva vigilant i comentaris
                # Detectar els nivells presents en aquest dia de l'horari
                nivells_dia = set()
                for slot in dia_info.get('sessions', []):
                    for sessio in slot.get('sessions_simultanees', []):
                        if sessio.get('curs'):
                            nivells_dia.add(sessio['curs'])

                # Carregar NOMÉS les existents d'aquests nivells (no tocar els altres nivells)
                # Clau: (hora, nivell, grups, aula) — aula necessari per distingir exàmens
                # del mateix grup en sales diferents dins el mateix slot
                existing_vigs = {
                    (v.hora, v.nivell or '', v.grups or '', v.aula or ''): v
                    for v in db.query(Vigilancia).filter(
                        Vigilancia.data == data_parsed,
                        Vigilancia.nivell.in_(list(nivells_dia)) if nivells_dia else False
                    ).all()
                }
                noves_claus = set()

                for slot in dia_info.get('sessions', []):
                    hora_inici = slot.get('hora', '')
                    if not hora_inici:
                        continue

                    hores_vigilancia = [hora_inici]
                    if durada_examen > 1 and totes_hores and hora_inici in totes_hores:
                        idx = totes_hores.index(hora_inici)
                        hores_vigilancia = totes_hores[idx:idx + durada_examen]

                    for sessio in slot.get('sessions_simultanees', []):
                        curs = sessio.get('curs', '')
                        for examen in sessio.get('examens', []):
                            grup = examen.get('grup', '')
                            aula = examen.get('aula', '') or ''
                            tipus = examen.get('assignatura') or sessio.get('nom_base') or sessio.get('nom', '')

                            for hora in hores_vigilancia:
                                clau = (hora, curs, grup, aula)
                                noves_claus.add(clau)

                                if clau in existing_vigs:
                                    v = existing_vigs[clau]
                                    if (v.tipus or '') != tipus:
                                        v.tipus = tipus
                                        vigilancies_actualitzades += 1
                                    else:
                                        vigilancies_sense_canvis += 1
                                else:
                                    vig = Vigilancia(
                                        data=data_parsed,
                                        hora=hora,
                                        tipus=tipus,
                                        grups=grup,
                                        aula=aula,
                                        vigilant=None,
                                        comentaris='',
                                        nivell=curs
                                    )
                                    db.add(vig)
                                    vigilancies_creades += 1

                # Eliminar NOMÉS les d'aquests nivells que ja no estan a l'horari
                for clau, v in existing_vigs.items():
                    if clau not in noves_claus:
                        db.delete(v)
                        vigilancies_eliminades += 1

                # 2. Grups alliberats: obtenir els grups dels nivells del dia des de la BD
                if not grups_sense_classe:
                    grups_dia = []
                    for niv in nivells_dia:
                        nivell_obj = db.query(Nivell).filter(Nivell.codi == niv).first()
                        if nivell_obj:
                            grups_niv = db.query(Grup).filter(
                                Grup.nivell_id == nivell_obj.id, Grup.actiu == True
                            ).all()
                            grups_dia.extend(g.codi for g in grups_niv)
                else:
                    grups_dia = grups_sense_classe

                # Deduplicar GrupAlliberat per (hora, grups)
                existing_ga = {
                    (ga.hora, ga.grups or '')
                    for ga in db.query(GrupAlliberat).filter(GrupAlliberat.data == data_parsed).all()
                }
                for grup in grups_dia:
                    nivell = _nivell_per_grup(grup)
                    if not nivell:
                        continue
                    for hora in _hores_alliberades(nivell, data_iso):
                        if (hora, grup) not in existing_ga:
                            db.add(GrupAlliberat(data=data_parsed, hora=hora, grups=grup))
                            grups_alliberats_creats += 1

                db.flush()

            except Exception as e:
                errors.append(f"{data_iso}: {str(e)}")
                continue

        # 4. Auto-assignar titulars si cal (no en dry_run)
        if opcions.auto_assign_titulars and not errors and not dry_run:
            try:
                from helpers import get_vigilancia_core, assign_phase1_titulars
                for data_iso in sorted(set(dates_processades)):
                    db.flush()
                    vigilancies_dict = VigilanciaRepository.get_by_date(db, data_iso)
                    all_vigl = []
                    for nivell_vigs in vigilancies_dict.values():
                        all_vigl.extend(nivell_vigs)

                    if not all_vigl:
                        continue

                    try:
                        core = get_vigilancia_core(data_iso, db)
                        vigilants_global = {}
                        for v in all_vigl:
                            h = v.get('hora', '')
                            vigilants_global.setdefault(h, set())
                            if v.get('vigilant'):
                                vigilants_global[h].add(v['vigilant'])

                        assigned = assign_phase1_titulars(all_vigl, core, vigilants_global, db)
                        for v in all_vigl:
                            if v.get('vigilant'):
                                db_id = v.get('db_id') or v.get('id')
                                if db_id:
                                    vig_obj = db.query(Vigilancia).filter(
                                        Vigilancia.id == int(db_id)
                                    ).first()
                                    if vig_obj and not vig_obj.vigilant:
                                        vig_obj.vigilant = v['vigilant']
                                        titulars_assignats += 1
                    except Exception as e:
                        errors.append(f"Auto-assignació {data_iso}: {str(e)}")
            except ImportError:
                errors.append("No s'ha pogut importar el mòdul d'assignació de titulars")

        if dry_run or errors:
            db.rollback()
        else:
            db.commit()

    return {
        "success": len(errors) == 0,
        "dry_run": dry_run,
        "dates_processades": sorted(set(dates_processades)),
        "vigilancies_creades": vigilancies_creades,
        "vigilancies_actualitzades": vigilancies_actualitzades,
        "vigilancies_sense_canvis": vigilancies_sense_canvis,
        "vigilancies_eliminades": vigilancies_eliminades,
        "grups_alliberats_creats": grups_alliberats_creats,
        "titulars_assignats": titulars_assignats,
        "errors": errors if errors else None,
        "debug": {
            "durada_examen_rebuda": durada_examen,
            "hores_lectives_carregades": len(totes_hores),
            "hores_lectives": totes_hores[:5] if totes_hores else []
        }
    }


# ===== RECALCULAR COST (EDITOR INTERACTIU) =====

@router.post("/recalcular-cost")
async def recalcular_cost(payload: HorariRecalcularRequest, current_user=Depends(require_admin)):
    """
    Recalcula el cost d'un horari modificat sense regenerar.
    Usat per l'editor interactiu de drag-and-drop.
    """
    horari = payload.horari
    if not horari or not horari.get('dies'):
        raise HTTPException(status_code=400, detail="L'horari no conté dies")

    from scheduler_engine.core.normalitzacio import normalitzar_dia, normalitzar_text

    with get_data_db_session(current_user.institucio) as db:
        restriccions = _build_restriccions_from_db(db)
        d_raw = ConfiguracioRepository.get(db, SCHEDULER_DURADA_KEY)
        n_raw = ConfiguracioRepository.get(db, SCHEDULER_NIVELLS_KEY)
        dates_raw = ConfiguracioRepository.get(db, SCHEDULER_DATES_KEY)
        alliberaments_raw = ConfiguracioRepository.get(db, SCHEDULER_ALLIBERAMENTS_KEY)
        durades_grups_raw = ConfiguracioRepository.get(db, SCHEDULER_DURADES_GRUPS_KEY)
        ultim_professor = ConfiguracioRepository.get(db, "ultim_professor_subs") or ""
        durada_titular = int(d_raw) if d_raw else DEFAULT_DURADA_TITULAR
        nivells_actius = _load_json(n_raw, []) or _nivells_master(db)
        selected_dates = payload.selected_dates or _load_json(dates_raw, [])
        alliberaments_cfg = _load_json(alliberaments_raw, {})
        durades_grups_cfg = _load_json(durades_grups_raw, None)
        if durades_grups_cfg:
            durades_per_sessio_recalc = {}
            durades_examen_per_sessio_recalc = {}
            for grup in durades_grups_cfg:
                for ass in grup.get("assignatures", []):
                    durades_per_sessio_recalc[ass] = grup.get("durada", 1)
                    durades_examen_per_sessio_recalc[ass] = grup.get("durada_examen", grup.get("durada", 1))
        else:
            durades_per_sessio_recalc = _load_json(ConfiguracioRepository.get(db, SCHEDULER_DURADES_SESSIO_KEY), {})
            durades_examen_per_sessio_recalc = dict(durades_per_sessio_recalc)
        dates_allib = _selected_dates_from_alliberaments(alliberaments_cfg, nivells_actius)
        if dates_allib:
            selected_dates = dates_allib

        from repositories import NoSubstituirRepository
        no_subst = set(NoSubstituirRepository.get_all(db))
        no_subst_norm = {normalitzar_text(a) for a in no_subst if a}

    hores_examen, _ = extreure_hores_examen_des_alliberaments(alliberaments_cfg)

    # Determinar data per XML
    data_ref = payload.data_referencia
    if not data_ref:
        meta = horari.get('metadata', {})
        data_ref = meta.get('data_inici')
    if not data_ref:
        from datetime import date
        data_ref = date.today().isoformat()

    dies_horari = [d.get('dia') for d in horari.get('dies', []) if d.get('dia')]
    dia_a_data_iso = construir_mapa_dia_data_iso(
        dies_utilitzar=dies_horari,
        selected_dates=selected_dates,
        data_inici_iso=data_ref,
    )

    xml_path = get_xml_path_for_date(current_user.institucio, data_ref)
    if not xml_path or not os.path.exists(xml_path):
        raise HTTPException(status_code=400, detail="XML d'horaris no disponible")

    # Carregar horaris professors
    import xml.etree.ElementTree as ET
    tree = ET.parse(xml_path)
    root = tree.getroot()

    def _hour_to_minutes(h):
        try:
            parts = h.split(':')
            return int(parts[0]) * 60 + int(parts[1])
        except Exception:
            return 0

    totes_hores = []
    for day in root.findall('.//Day'):
        for hour in day.findall('Hour'):
            h = hour.get('name')
            if h and h not in totes_hores:
                totes_hores.append(h)

    totes_hores = [_normalitzar_hora(h) for h in totes_hores if h]

    if not totes_hores:
        totes_hores = [_normalitzar_hora(h) for h in (hores_examen or [])]
    else:
        missing = []
        for h in (hores_examen or []):
            h_norm = _normalitzar_hora(h)
            if h_norm and h_norm not in totes_hores:
                missing.append(h_norm)
        if missing:
            combined = list({*totes_hores, *missing})
            combined.sort(key=_hour_to_minutes)
            totes_hores = combined

    # Aplicar també en recàlcul la restricció derivada de slots vàlids per nivell (marques 🟦).
    slots_derivats = _build_slots_valids_from_alliberaments(
        alliberaments_cfg=alliberaments_cfg,
        nivells_actius=nivells_actius,
        dies_utilitzar=dies_horari,
        dia_a_data_iso=dia_a_data_iso,
        hores_disponibles=totes_hores,
    )
    dures_recalc = restriccions.setdefault("restriccions_dures", {})
    slots_actuals = dures_recalc.get("slots_valids_per_nivell") or {}
    dures_recalc["slots_valids_per_nivell"] = _merge_slots_valids(slots_actuals, slots_derivats)
    dates_per_nivell = {
        niv: [d for d in (alliberaments_cfg.get(niv) or {}).get("dates", []) if isinstance(d, str)]
        for niv in (nivells_actius or [])
        if isinstance((alliberaments_cfg or {}).get(niv), dict) and (alliberaments_cfg[niv].get("dates") or [])
    }
    if dates_per_nivell:
        dures_recalc["dates_per_nivell"] = dates_per_nivell
    slots_iso = _build_slots_valids_iso_from_alliberaments(alliberaments_cfg, nivells_actius, totes_hores)
    if slots_iso:
        dures_recalc["slots_valids_iso_per_nivell"] = slots_iso

    horaris_professors = {}
    ultim_prof = (ultim_professor or "").strip()
    for teacher in root.findall('Teacher'):
        nom = teacher.get('name').strip()
        horaris_professors[nom] = {}
        for day in teacher.findall('Day'):
            d = normalitzar_dia(day.get('name'))
            horaris_professors[nom][d] = {}
            for hour in day.findall('Hour'):
                h_raw = hour.get('name')
                h = _normalitzar_hora(h_raw)
                sub = hour.find('Subject')
                act = hour.find('Activity')
                if (act is not None and act.get('id')) or sub is not None:
                    s = sub.get('name') if sub is not None else ''
                    g = hour.find('Students').get('name') if hour.find('Students') is not None else ''
                    horaris_professors[nom][d][h] = {'assignatura': s, 'grup': g}
        # El professor límit també s'ha d'incloure en el recàlcul.
        if ultim_prof and nom == ultim_prof:
            break

    # Recalcular cost amb el mòdul d'estadístiques
    from scheduler_engine.estadistiques import recalcular_cost_i_breakdown
    from scheduler_engine.core.availability import analitzar_disponibilitat_sessio
    from scheduler_engine.core.durada import get_durada_per_nivell, get_durada_per_sessio_key, detectar_nivell_sessio
    from scheduler_engine.validacio import ValidadorHorari
    from scheduler_engine.core.constraints import sessio_in_group, _percent_penalty, _pes_obligatori

    class SimpleContext:
        pass
    ctx = SimpleContext()
    ctx.restriccions = restriccions
    ctx.horaris_professors = horaris_professors
    ctx.hores_examen = hores_examen
    ctx.durada_titular = durada_titular
    ctx.no_substituir_norm = no_subst_norm
    ctx.totes_hores = totes_hores
    ctx.nivells_actius = nivells_actius
    ctx.dia_a_data_iso = dia_a_data_iso
    ctx.alliberaments_per_nivell = alliberaments_cfg
    ctx.durades_per_sessio = durades_per_sessio_recalc

    cost_info = recalcular_cost_i_breakdown(horari, ctx)

    # Calcular informació per slot i detectar conflictes de nivell
    slots_info = []
    conflicte_global = False

    def _log_with_score(msg: str, score: int) -> str:
        return f"{msg} (punt: {score})" if score is not None else msg

    def _build_sessions_per_dia(horari_data):
        sessions_per_dia = defaultdict(list)
        for dia_data in horari_data.get('dies', []):
            dia_nom = dia_data.get('dia', '')
            dia_norm = normalitzar_dia(dia_nom)
            for slot_data in dia_data.get('sessions', []):
                for sessio_data in slot_data.get('sessions_simultanees', []):
                    sessions_per_dia[dia_nom].append(sessio_data)
                    if dia_norm and dia_norm != dia_nom:
                        sessions_per_dia[dia_norm].append(sessio_data)
        return sessions_per_dia

    for dia in horari.get('dies', []):
        dia_nom = dia.get('dia', '')
        _dates = dia_a_data_iso.get(normalitzar_dia(dia_nom))
        data_iso_slot = dia.get('data') or (_dates[0] if isinstance(_dates, list) else _dates)
        for slot in dia.get('sessions', []):
            hora = slot.get('hora', '')
            hora_norm = _normalitzar_hora(hora)
            slot_key = f"{data_iso_slot or dia_nom}_{hora}"

            sessions_sim = slot.get('sessions_simultanees', [])

            # Detectar conflicte de nivell
            items_per_nivell = {}
            for sessio in sessions_sim:
                item_id = sessio.get('item_id') or sessio.get('id') or f"{sessio.get('nom')}_{sessio.get('curs')}"
                curs = sessio.get('curs', '')
                if curs and item_id not in items_per_nivell:
                    items_per_nivell[item_id] = curs

            nivells_items = list(items_per_nivell.values())
            conflicte_nivell = len(nivells_items) != len(set(nivells_items))
            if conflicte_nivell:
                conflicte_global = True

            # Obtenir pesos de la configuració
            costos_globals = restriccions.get('costos_professors', {}).get('globals', {})
            pes_substitucio = costos_globals.get('substitucio', DEFAULT_COST_PROFESSORS['substitucio'])
            pes_abans = costos_globals.get('abans_jornada', DEFAULT_COST_PROFESSORS['abans_jornada'])
            pes_despres = costos_globals.get('despres_jornada', DEFAULT_COST_PROFESSORS['despres_jornada'])
            pes_no_treballa = costos_globals.get('no_treballa_dia', DEFAULT_COST_PROFESSORS['no_treballa_dia'])

            # Calcular cost del slot i avisos (recalculant anàlisi per evitar duplicats)
            cost_slot = 0
            avisos = []
            seen_subs = set()
            seen_abans = set()
            seen_despres = set()
            seen_no_treballa = set()

            item_avisos = {}

            for idx, sessio in enumerate(sessions_sim):
                altres = [s for i, s in enumerate(sessions_sim) if i != idx]
                nivell_sessio = detectar_nivell_sessio(sessio, nivells_actius or [])
                sessio_nom_d = sessio.get('nom') if isinstance(sessio, dict) else None
                durada_sessio = get_durada_per_sessio_key(
                    sessio_nom_d, nivell_sessio, durades_per_sessio_recalc, alliberaments_cfg, durada_titular
                )
                durada_exam = get_durada_per_sessio_key(
                    sessio_nom_d, nivell_sessio, durades_examen_per_sessio_recalc, alliberaments_cfg, durada_titular
                )
                durada_exam = max(durada_exam, durada_sessio)
                if hora_norm in totes_hores:
                    idx_inici = totes_hores.index(hora_norm)
                    hores_ocupades = totes_hores[idx_inici:min(idx_inici + max(1, durada_sessio), len(totes_hores))]
                    hores_exam = totes_hores[idx_inici:min(idx_inici + max(1, durada_exam), len(totes_hores))]
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
                    alliberaments_per_nivell=alliberaments_cfg,
                    data_iso=data_iso_slot,
                )
                # Actualitzar analisi per a validació posterior
                if isinstance(sessio, dict):
                    sessio['analisi'] = analisi

                item_keys = []
                if isinstance(sessio, dict):
                    if sessio.get('_uid'):
                        item_keys.append(sessio['_uid'])
                    if sessio.get('item_id'):
                        item_keys.append(sessio['item_id'])
                if item_keys:
                    avisos_item = []
                    seen_item = set()

                    for item in analisi.get('substitucions', []):
                        prof = item.get('professor')
                        if not prof:
                            continue
                        hora_item = item.get('hora', hora)
                        key = ('sub', prof, hora_item)
                        if key in seen_item:
                            continue
                        seen_item.add(key)
                        act = item.get('activitat', {})
                        assig = act.get('assignatura', 'Assignatura')
                        grp = act.get('grup', 'un grup')
                        msg = f"🚨 {prof} → ha de ser SUBSTITUÏT a {assig} amb {grp} a les {hora_item} el {dia_nom}"
                        avisos_item.append(_log_with_score(msg, pes_substitucio))

                    for item in analisi.get('abans_jornada', []):
                        prof = item.get('professor')
                        if not prof:
                            continue
                        hora_item = item.get('hora', hora)
                        key = ('abans', prof, hora_item)
                        if key in seen_item:
                            continue
                        seen_item.add(key)
                        primera = item.get('primera_hora', '?')
                        msg = f"🕐 {prof} → arriba abans a {hora_item} el {dia_nom} (primera hora: {primera})"
                        avisos_item.append(_log_with_score(msg, pes_abans))

                    for item in analisi.get('despres_jornada', []):
                        prof = item.get('professor')
                        if not prof:
                            continue
                        hora_item = item.get('hora', hora)
                        key = ('despres', prof, hora_item)
                        if key in seen_item:
                            continue
                        seen_item.add(key)
                        ultima = item.get('ultima_hora', '?')
                        msg = f"🕐 {prof} → queda més estona a {hora_item} el {dia_nom} (última hora: {ultima})"
                        avisos_item.append(_log_with_score(msg, pes_despres))

                    for item in analisi.get('no_treballa_dia', []):
                        prof = item.get('professor')
                        if not prof:
                            continue
                        hora_item = item.get('hora', hora)
                        key = ('no', prof, hora_item)
                        if key in seen_item:
                            continue
                        seen_item.add(key)
                        msg = f"🚫 {prof} → no treballa aquest dia a les {hora_item} el {dia_nom}"
                        avisos_item.append(_log_with_score(msg, pes_no_treballa))

                    if avisos_item:
                        for k in item_keys:
                            if k:
                                item_avisos[k] = avisos_item

                for item in analisi.get('substitucions', []):
                    prof = item.get('professor')
                    if not prof:
                        continue
                    hora_item = item.get('hora', hora)
                    key = (prof, hora_item)
                    if key in seen_subs:
                        continue
                    seen_subs.add(key)
                    cost_slot += pes_substitucio
                    act = item.get('activitat', {})
                    assig = act.get('assignatura', 'Assignatura')
                    grp = act.get('grup', 'un grup')
                    msg = f"🚨 {prof} → ha de ser SUBSTITUÏT a {assig} amb {grp} a les {hora_item} el {dia_nom}"
                    avisos.append(_log_with_score(msg, pes_substitucio))

                for item in analisi.get('abans_jornada', []):
                    prof = item.get('professor')
                    if not prof:
                        continue
                    hora_item = item.get('hora', hora)
                    key = (prof, hora_item)
                    if key in seen_abans:
                        continue
                    seen_abans.add(key)
                    cost_slot += pes_abans
                    primera = item.get('primera_hora', '?')
                    msg = f"🕐 {prof} → arriba abans a {hora_item} el {dia_nom} (primera hora: {primera})"
                    avisos.append(_log_with_score(msg, pes_abans))

                for item in analisi.get('despres_jornada', []):
                    prof = item.get('professor')
                    if not prof:
                        continue
                    hora_item = item.get('hora', hora)
                    key = (prof, hora_item)
                    if key in seen_despres:
                        continue
                    seen_despres.add(key)
                    cost_slot += pes_despres
                    ultima = item.get('ultima_hora', '?')
                    msg = f"🕐 {prof} → queda més estona a {hora_item} el {dia_nom} (última hora: {ultima})"
                    avisos.append(_log_with_score(msg, pes_despres))

                for item in analisi.get('no_treballa_dia', []):
                    prof = item.get('professor')
                    if not prof:
                        continue
                    hora_item = item.get('hora', hora)
                    key = (prof, hora_item)
                    if key in seen_no_treballa:
                        continue
                    seen_no_treballa.add(key)
                    cost_slot += pes_no_treballa
                    msg = f"🚫 {prof} → no treballa aquest dia a les {hora_item} el {dia_nom}"
                    avisos.append(_log_with_score(msg, pes_no_treballa))

            if conflicte_nivell:
                avisos.insert(0, "⚠️ CONFLICTE: Múltiples exàmens del mateix nivell!")

            slots_info.append({
                "slot_key": slot_key,
                "cost": cost_slot,
                "breakdown": {"sessions": len(sessions_sim)},
                "conflicte_nivell": conflicte_nivell,
                "avisos": avisos,
                "item_avisos": item_avisos
            })

    # Netejar logs antics per evitar que el validador ometi avisos (p. ex. LÍMIT DIES)
    if horari.get('metadata', {}).get('logs'):
        horari['metadata']['logs'] = []
    validation_result = ValidadorHorari(horari, restriccions, no_subst).validar()

    breakdown_details = {}
    restr_limit = restriccions.get('restriccions_dures', {}).get('professors_limit_dies_especifics', {})
    restr_limit = {k: v for k, v in restr_limit.items() if not k.startswith('_')}
    if restr_limit:
        sessions_per_dia = _build_sessions_per_dia(horari)
        base_cost = restriccions.get('pesos_optimitzacio', {}).get('restriccio_dura', 10000)
        hard_cost = restriccions.get('pesos_optimitzacio', {}).get('restriccio_dura_violada', 20000)
        detalls = []
        for professor, config_prof in restr_limit.items():
            assignatures_restringides = config_prof.get('assignatures', [])
            dies_restringits = config_prof.get('dies_restringits', [])
            max_examens = int(config_prof.get('max_examens', 999))
            _v = config_prof.get('pes_penalitzacio')
            pes = int(_v) if _v is not None else 50

            count_examens = 0
            for dia_check in dies_restringits:
                for s in sessions_per_dia.get(dia_check, []):
                    profs_s = {e.get('titular') for e in s.get('examens', []) if e.get('titular')}
                    if professor in profs_s and sessio_in_group(s, assignatures_restringides):
                        count_examens += 1

            if count_examens > max_examens:
                excedent = count_examens - max_examens
                if _pes_obligatori(pes):
                    _ = hard_cost * excedent
                else:
                    _ = _percent_penalty(base_cost, pes) * excedent
                detalls.append(f"{professor} +{excedent}")
        if detalls:
            breakdown_details["limit_dies_professor"] = detalls

    return {
        "cost_total": cost_info.get('cost_total', 0),
        "cost_breakdown": cost_info.get('cost_breakdown', {}),
        "cost_breakdown_details": breakdown_details,
        "slots": slots_info,
        "valid": not conflicte_global,
        "logs": validation_result.get("logs", []),
        "stats": {
            "total_substitucions": cost_info.get('total_substitucions', 0),
            "professors_abans": cost_info.get('professors_abans', 0),
            "professors_despres": cost_info.get('professors_despres', 0),
            "professors_no_treballa": cost_info.get('professors_no_treballa', 0),
        }
    }


@router.post("/debug-substitucions")
async def debug_substitucions(payload: dict, current_user=Depends(require_admin)):
    """
    Endpoint de debug per verificar la detecció de substitucions.
    Payload: { professor: str, dia: str, hora: str, data_referencia?: str }
    """
    from scheduler_engine.core.availability import analitzar_disponibilitat_sessio
    from scheduler_engine.core.normalitzacio import normalitzar_dia, normalitzar_text
    import xml.etree.ElementTree as ET

    professor = payload.get("professor", "")
    dia = payload.get("dia", "Dilluns")
    hora = payload.get("hora", "09:00")
    data_ref = payload.get("data_referencia")

    with get_data_db_session(current_user.institucio) as db:
        n_raw = ConfiguracioRepository.get(db, SCHEDULER_NIVELLS_KEY)
        nivells_actius = _load_json(n_raw, []) or _nivells_master(db)

        from repositories import NoSubstituirRepository
        no_subst = set(NoSubstituirRepository.get_all(db))
        no_subst_norm = {normalitzar_text(a) for a in no_subst if a}

    if not data_ref:
        from datetime import date
        data_ref = date.today().isoformat()

    xml_path = get_xml_path_for_date(current_user.institucio, data_ref)
    if not xml_path or not os.path.exists(xml_path):
        return {"error": "XML not found", "xml_path": xml_path}

    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Obtenir totes les hores del XML
    totes_hores = []
    for h in root.findall('.//Hour'):
        nom = h.get('name')
        if nom and nom not in totes_hores:
            totes_hores.append(nom)

    totes_hores_norm = [_normalitzar_hora(h) for h in totes_hores]

    # Carregar horaris professors
    horaris_professors = {}
    for teacher in root.findall('Teacher'):
        nom = teacher.get('name').strip()
        horaris_professors[nom] = {}
        for day in teacher.findall('Day'):
            d = normalitzar_dia(day.get('name'))
            horaris_professors[nom][d] = {}
            for hour in day.findall('Hour'):
                h_raw = hour.get('name')
                h = _normalitzar_hora(h_raw)
                sub = hour.find('Subject')
                act = hour.find('Activity')
                if (act is not None and act.get('id')) or sub is not None:
                    s = sub.get('name') if sub is not None else ''
                    g = hour.find('Students').get('name') if hour.find('Students') is not None else ''
                    horaris_professors[nom][d][h] = {'assignatura': s, 'grup': g}

    # Verificar si el professor existeix
    if professor and professor not in horaris_professors:
        professors_similars = [p for p in horaris_professors.keys() if professor.lower() in p.lower()]
        return {
            "error": f"Professor '{professor}' no trobat",
            "professors_similars": professors_similars[:10],
            "total_professors": len(horaris_professors)
        }

    # Si no es passa professor, mostrar info general
    if not professor:
        dia_norm = normalitzar_dia(dia)
        hora_norm = _normalitzar_hora(hora)
        profs_amb_classe = []
        for prof, horari in horaris_professors.items():
            if dia_norm in horari and hora_norm in horari[dia_norm]:
                act = horari[dia_norm][hora_norm]
                profs_amb_classe.append({
                    "professor": prof,
                    "assignatura": act.get('assignatura', ''),
                    "grup": act.get('grup', '')
                })
        return {
            "dia": dia,
            "dia_normalitzat": dia_norm,
            "hora": hora,
            "hora_normalitzada": hora_norm,
            "professors_amb_classe": profs_amb_classe,
            "total": len(profs_amb_classe),
            "nivells_actius": nivells_actius,
            "no_substituir": list(no_subst)[:20],
            "totes_hores": totes_hores_norm
        }

    # Analitzar un professor concret
    dia_norm = normalitzar_dia(dia)
    hora_norm = _normalitzar_hora(hora)

    horari_prof = horaris_professors.get(professor, {})
    horari_dia = horari_prof.get(dia_norm, {})

    # Crear una sessió fictícia per testejar
    sessio_test = {
        "nom": "TEST",
        "examens": [{"titular": professor}]
    }

    analisi = analitzar_disponibilitat_sessio(
        sessio=sessio_test,
        dia=dia,
        hora=hora_norm,
        horaris_professors=horaris_professors,
        totes_hores=totes_hores_norm,
        nivells_actius=nivells_actius,
        durada_titular=1,
        no_substituir_norm=no_subst_norm,
        sessions_al_slot=None,
        hores_override=[hora_norm]
    )

    return {
        "professor": professor,
        "dia": dia,
        "dia_normalitzat": dia_norm,
        "hora": hora,
        "hora_normalitzada": hora_norm,
        "dies_professor": list(horari_prof.keys()),
        "horari_dia": horari_dia,
        "nivells_actius": nivells_actius,
        "no_substituir": list(no_subst)[:20],
        "analisi": {
            "substitucions": analisi.get('substitucions', []),
            "alliberats": analisi.get('alliberats', []),
            "lliures": analisi.get('lliures', []),
            "abans_jornada": analisi.get('abans_jornada', []),
            "despres_jornada": analisi.get('despres_jornada', []),
            "no_treballa_dia": analisi.get('no_treballa_dia', []),
            "altres": analisi.get('altres', [])
        }
    }
