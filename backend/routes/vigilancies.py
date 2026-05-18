"""
Routes per gestió de vigilàncies d'exàmens:
- Configuració (nivells, professors, hores, grups, aules)
- CRUD vigilàncies (crear, obtenir, actualitzar, eliminar)
- Professors disponibles per hora
- Assignació automàtica (titulars, pendents)
- Operacions (netejar, ordenar)
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime
from collections import defaultdict

from dependencies import get_db
from auth_utils import get_current_user
from repositories import VigilanciaRepository, SubstitucioRepository, GrupsAlliberatsRepository, MasterConfigRepository, parse_date
from routes.vigilancia_absent import crear_vigilancia_absent
from models import Substitucio
from helpers import (
    get_horari,
    get_vigilancia_core,
    get_gestors,
    assign_phase1_titulars,
    assign_phase2_professors_grup,
    assign_phase3_passada,
    get_vigilancies_afinitats
)
from schemas import (
    VigilanciaCreate,
    VigilanciaUpdate,
    AssignmentResponse,
    VigilanciaDisponiblesBatchRequest
)

router = APIRouter(prefix="/api/vigilancies", tags=["Vigilàncies"])


def _collect_vigilants_by_hour(vigilancies_dict: dict) -> dict:
    vigilants_per_hora = defaultdict(set)
    for vigilancies_list in vigilancies_dict.values():
        for vig in vigilancies_list:
            hora = (vig.get("hora") or "").strip()
            vigilant = (vig.get("vigilant") or "").strip()
            if hora and vigilant and vigilant != "-- selecciona vigilant --":
                vigilants_per_hora[hora].add(vigilant)
    return vigilants_per_hora


def _alliberar_substitucions_en_conflicte(data: str, db: Session, hores: set | None = None) -> int:
    """
    Política A: vigilàncies tenen prioritat sobre substitucions.
    Si un professor està assignat com a vigilant a una hora, no pot quedar de substitut a la mateixa hora.
    """
    vigilancies_dict = VigilanciaRepository.get_by_date(db, data)
    vigilants_per_hora = _collect_vigilants_by_hour(vigilancies_dict)
    if not vigilants_per_hora:
        return 0

    cleared = 0
    for sub in SubstitucioRepository.get_by_date(db, data):
        sub_id = sub.get("id")
        hora = (sub.get("hora") or "").strip()
        substitut = (sub.get("substitut") or "").strip()
        if not sub_id or not hora or not substitut:
            continue
        if hores is not None and hora not in hores:
            continue
        if substitut in vigilants_per_hora.get(hora, set()):
            SubstitucioRepository.update(
                db,
                int(sub_id),
                {"substitut": "", "tipus_substitut": ""}
            )
            cleared += 1
    return cleared


def _vig_to_payload(vig) -> dict:
    return {
        "id": str(vig.id),
        "hora": vig.hora,
        "tipus": vig.tipus,
        "grups": vig.grups,
        "aula": vig.aula,
        "vigilant": vig.vigilant or "",
        "comentaris": vig.comentaris or "",
        "nivell": vig.nivell,
        "updated_at": vig.updated_at.isoformat() if vig.updated_at else None
    }


def _refresh_vigilancia_substitucions(data: str, hora: str, db: Session) -> None:
    """Refresca substitucions derivades de vigilàncies per una hora concreta."""
    hora = (hora or "").strip()
    if not hora:
        return

    # Carregar ÚNICAMENT Tipus B (VIGILANCIA): la cobertura de classe
    # Els Tipus A (VIGILANCIA_ABSENT: vigilant absent) es preserven sempre
    existing_subs = db.query(Substitucio).filter(
        and_(
            Substitucio.data == parse_date(data),
            Substitucio.hora == hora,
            Substitucio.tipus_absencia == "VIGILANCIA"
        )
    ).all()

    # Restaurar substituts ja assignats als Tipus B
    existing_map = {}
    for sub in existing_subs:
        key = f"{sub.professor_absent}|{sub.hora}|{sub.assignatura or ''}|{sub.grup or ''}"
        existing_map[key] = {
            "substitut": sub.substitut or "",
            "tipus_substitut": sub.tipus_substitut or "",
            "comentaris": sub.comentaris or ""
        }

    if existing_subs:
        ids_cobertura = [s.id for s in existing_subs]
        db.query(Substitucio).filter(
            Substitucio.id.in_(ids_cobertura)
        ).delete(synchronize_session=False)
        db.commit()

    vigilants = VigilanciaRepository.get_vigilants_per_hora(db, data, hora)

    # Eliminar Tipus A (VIGILANCIA_ABSENT) per professors que ja no son vigilants
    tipus_a_hora = db.query(Substitucio).filter(
        and_(
            Substitucio.data == parse_date(data),
            Substitucio.hora == hora,
            Substitucio.tipus_absencia == "VIGILANCIA_ABSENT"
        )
    ).all()
    for sub_a in tipus_a_hora:
        if (sub_a.professor_absent or "").strip() not in vigilants:
            db.delete(sub_a)
    if tipus_a_hora:
        db.commit()

    if not vigilants:
        return

    substitucions_mgr, horari, _, _ = get_gestors(data_iso=data)
    date_obj = datetime.strptime(data, "%Y-%m-%d")
    dia_name = horari.get_dia_name(date_obj.weekday())

    grups_sense_classe = GrupsAlliberatsRepository.get_by_date(db, data)
    grups_hora = grups_sense_classe.get(hora, [])
    grups_hora = set(grups_hora) if isinstance(grups_hora, list) else set(grups_hora or [])

    substitucions_mgr.professors_ocupats_examens = {hora: set(vigilants)}
    substitucions_mgr.grups_sense_classe_dict = {hora: grups_hora}
    substitucions_mgr.grups_sense_classe_actual = set(grups_hora)

    noves = substitucions_mgr._generar_substitucions_vigilants(dia_name, substitucions_mgr.grups_sense_classe_actual)

    for sub in noves:
        if (sub.get("hora") or "").strip() != hora:
            continue
        key = f"{sub.get('professor_absent', '')}|{sub.get('hora', '')}|{sub.get('assignatura', '')}|{sub.get('grup', '')}"
        existent = existing_map.get(key)
        if existent and existent.get("substitut"):
            sub["substitut"] = existent.get("substitut", "")
            sub["tipus_substitut"] = existent.get("tipus_substitut", "")
            sub["comentaris"] = existent.get("comentaris", "")

        SubstitucioRepository.create(db, {
            "data": data,
            "hora": sub.get("hora", ""),
            "professor_absent": sub.get("professor_absent", ""),
            "assignatura": sub.get("assignatura", ""),
            "grup": sub.get("grup", ""),
            "aula": sub.get("aula", ""),
            "substitut": sub.get("substitut", ""),
            "tipus_substitut": sub.get("tipus_substitut", ""),
            "tipus_absencia": sub.get("tipus_absencia", "VIGILANCIA"),
            "comentaris": sub.get("comentaris", "")
        })

    # Crear Tipus A (VIGILANCIA_ABSENT) si un vigilant ja és absent a aquesta hora
    tipus_a_existents = {
        (s.professor_absent or "").strip()
        for s in db.query(Substitucio).filter(
            and_(
                Substitucio.data == parse_date(data),
                Substitucio.hora == hora,
                Substitucio.tipus_absencia == "VIGILANCIA_ABSENT"
            )
        ).all()
    }
    absents_hora = {
        (s.professor_absent or "").strip()
        for s in db.query(Substitucio).filter(
            and_(
                Substitucio.data == parse_date(data),
                Substitucio.hora == hora,
                Substitucio.tipus_absencia.notin_(["VIGILANCIA", "ENCADENADA", "VIGILANCIA_ABSENT"])
            )
        ).all()
        if (s.professor_absent or "").strip()
    }
    vigilancies_dia = VigilanciaRepository.get_by_date(db, data)
    for nivell_vigs in vigilancies_dia.values():
        for vig in nivell_vigs:
            vigilant = (vig.get("vigilant") or "").strip()
            if (vig.get("hora") == hora
                    and vigilant in vigilants
                    and vigilant in absents_hora
                    and vigilant not in tipus_a_existents):
                crear_vigilancia_absent(db, data, vigilant,
                                        hora, vig.get("grups", ""), vig.get("aula", ""))
                tipus_a_existents.add(vigilant)

    # Política A: allibera substitucions en conflicte a aquesta mateixa hora.
    _alliberar_substitucions_en_conflicte(data, db, {hora})


@router.get("/{data}/pdf")
async def generar_pdf_vigilancies_alias(
    data: str,
    nivells: str = "",
    compress: bool = False,
    show_comments: bool = True,
    show_hours: bool = False,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Alias per compatibilitat: delega a /api/pdf/vigilancies/{data}."""
    from routes.pdf import generar_pdf_vigilancies

    return await generar_pdf_vigilancies(
        data=data,
        nivells=nivells,
        compress=compress,
        show_comments=show_comments,
        show_hours=show_hours,
        db=db,
        current_user=current_user
    )


@router.get("/pdf/interval")
async def generar_pdf_interval_alias(
    data_inici: str,
    data_final: str,
    nivells: str = "",
    include_weekends: bool = False,
    include_empty_days: bool = False,
    compress: bool = False,
    show_comments: bool = True,
    show_hours: bool = False,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Alias per compatibilitat: delega a /api/pdf/vigilancies/interval."""
    from routes.pdf import generar_pdf_interval

    return await generar_pdf_interval(
        data_inici=data_inici,
        data_final=data_final,
        nivells=nivells,
        include_weekends=include_weekends,
        include_empty_days=include_empty_days,
        compress=compress,
        show_comments=show_comments,
        show_hours=show_hours,
        db=db,
        current_user=current_user
    )


def _normalize_disponibles_param(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _disponibles_cache_key(hora: str, tipus: str | None, grups: str | None, aula: str | None) -> str:
    if tipus:
        return f"{hora}|{tipus}|{grups or ''}|{aula or ''}"
    return hora


def _categoria_prioritat(tipus_activitat: str, ordre_prioritats: list) -> int:
    for i, categoria in enumerate(ordre_prioritats):
        if tipus_activitat in categoria:
            return i
    return len(ordre_prioritats)


def _build_disponibles_context(data: str, db: Session, hores_consulta: set[str], necessita_titulars: bool) -> dict:
    from config.constants import PRIORITATS, PROFESSORS_BAIXA, ORDRE_PRIORITATS

    horari = get_horari(data_iso=data)
    date_obj = datetime.strptime(data, "%Y-%m-%d")
    dia_name = horari.get_dia_name(date_obj.weekday())

    vigilancies_dict = VigilanciaRepository.get_by_date(db, data)
    vigilants_per_hora = _collect_vigilants_by_hour(vigilancies_dict)

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
    grups_sense_classe_per_hora = {
        hora: set(grups or [])
        for hora, grups in grups_sense_classe_raw.items()
    }

    professors_baixa = set()
    data_obj_date = date_obj.date()
    for baixa in PROFESSORS_BAIXA:
        try:
            data_inici = datetime.strptime(baixa['data_inici'], '%Y-%m-%d').date()
            data_final = datetime.strptime(baixa['data_final'], '%Y-%m-%d').date()
        except Exception:
            continue
        if data_inici <= data_obj_date <= data_final:
            professors_baixa.add(baixa['professor'])

    activitats_per_hora = {}
    for hora in hores_consulta:
        activitats_per_hora[hora] = {}
        for professor in horari.professors:
            activitat = horari.get_activitat(dia_name, hora, professor) or {}
            activitats_per_hora[hora][professor] = (
                activitat.get("assignatura", ""),
                activitat.get("grup", "")
            )

    vigilancia_core = get_vigilancia_core(data, db) if necessita_titulars else None

    return {
        "ordre_prioritats": ORDRE_PRIORITATS,
        "prioritats": set(PRIORITATS),
        "vigilants_per_hora": vigilants_per_hora,
        "absents_per_professor": absents_per_professor,
        "absents_tipus": absents_tipus,
        "substituts_ocupats_per_hora": substituts_ocupats_per_hora,
        "grups_sense_classe_per_hora": grups_sense_classe_per_hora,
        "professors_baixa": professors_baixa,
        "activitats_per_hora": activitats_per_hora,
        "vigilancia_core": vigilancia_core,
        "professors_ordenats": sorted(horari.professors),
    }


def _build_disponibles_for_query(context: dict, hora: str, tipus: str | None, grups: str | None, aula: str | None) -> list[dict]:
    ordre_prioritats = context["ordre_prioritats"]
    vigilants_assignats = context["vigilants_per_hora"].get(hora, set())
    absents_per_professor = context["absents_per_professor"]
    absents_tipus = context["absents_tipus"]
    substituts_ocupats_hora = context["substituts_ocupats_per_hora"].get(hora, set())
    grups_sense_classe_hora = context["grups_sense_classe_per_hora"].get(hora, set())
    professors_baixa = context["professors_baixa"]
    activitats_hora = context["activitats_per_hora"].get(hora, {})
    vigilancia_core = context["vigilancia_core"]
    prioritats = context["prioritats"]

    professors_info = []
    for professor in context["professors_ordenats"]:
        es_titular = False
        if vigilancia_core and tipus and tipus != "VIGILÀNCIA":
            try:
                es_titular = vigilancia_core.es_titular_per_assignatura(
                    professor, tipus, grups or "", aula or ""
                )
            except Exception:
                es_titular = False

        assignatura, grup = activitats_hora.get(professor, ("", ""))
        es_absent = hora in absents_per_professor.get(professor, set())
        es_substituint = professor in substituts_ocupats_hora

        base_icon = "👨‍🏫 " if es_titular else ""
        titular_text = f" (TITULAR {tipus})" if es_titular else ""

        if professor in professors_baixa:
            emoji = "🏥"
            estat = "DE BAIXA"
            info = "DE BAIXA"
            if assignatura:
                info += f" - tenia {assignatura}"
                if grup:
                    info += f" - {grup}"
            ordre_tipus = 6
            color = "rgba(255, 160, 122, 0.5)"
        elif es_absent:
            emoji = "⚠️"
            estat = "ABSENT"
            tipus_abs = absents_tipus.get(professor, "ABSENCIA")
            info = f"absent ({tipus_abs})"
            if assignatura:
                info += f" - tenia {assignatura}"
                if grup:
                    info += f" - {grup}"
            ordre_tipus = 5
            color = "#FFFF00"
        elif assignatura and grup and grup in grups_sense_classe_hora:
            emoji = "✅"
            estat = "ALLIBERAT"
            info = f"alliberat (tenia {assignatura} - {grup})"
            ordre_tipus = 1
            color = "#90EE90"
        elif assignatura and not grup:
            if assignatura in prioritats:
                emoji = "🟢"
                estat = "DISPONIBLE"
                info = assignatura
                ordre_tipus = 2
                color = "#AFEEEE"
            else:
                emoji = "⚪"
                estat = "LLIURE"
                info = assignatura if assignatura else "lliure"
                ordre_tipus = 4
                color = "#F5F5F5"
        elif assignatura and grup:
            emoji = "🔴"
            estat = "CLASSE"
            info = f"{assignatura} - {grup}"
            ordre_tipus = 3
            color = "#FFDCB4"
        else:
            emoji = "⚪"
            estat = "LLIURE"
            info = "lliure"
            ordre_tipus = 4
            color = "#F5F5F5"

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
        professors_info.append({
            "value": professor,
            "label": label,
            "emoji": emoji,
            "estat": estat,
            "info": info,
            "ordre_tipus": ordre_tipus,
            "categoria": categoria,
            "color": color,
            "ja_assignat": ja_assignat,
            "es_titular": es_titular
        })

    professors_info.sort(key=lambda x: (x["ordre_tipus"], x["value"]))
    return professors_info


@router.get("/config")
async def obtenir_config_vigilancies(db: Session = Depends(get_db)):
    """
    Retorna configuració necessària per gestionar vigilàncies (SQLite):
    - Nivells disponibles
    - Professors disponibles
    - Hores del dia
    - Grups i aules (de SQLite)
    - Tipus d'exàmens únics (de SQLite)
    """
    try:
        horari = get_horari()

        # Carregar master config des de SQLite
        master_config = MasterConfigRepository.get_master_config(db)

        nivells_data = master_config.get("nivells", {})
        nivells = list(nivells_data.keys())
        grups_per_nivell = {
            nivell: dades.get("grups", [])
            for nivell, dades in nivells_data.items()
        }
        aules = master_config.get("aules", [])

        # Si no hi ha nivells, usar defaults
        if not nivells:
            nivells = ["GENERAL", "1-ESO", "2-ESO", "3-ESO", "4-ESO", "1-BATX", "2-BATX"]

        # Extreure tipus únics de SQLite
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
            "tipus_per_nivell": {
                nivell: dades.get("assignatures", [])
                for nivell, dades in nivells_data.items()
            }
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en carregar configuració: {str(e)}")


@router.get("/{data}/{hora}/disponibles")
async def obtenir_disponibles_vigilancia(
    data: str,
    hora: str,
    tipus: str = None,
    grups: str = None,
    aula: str = None,
    db: Session = Depends(get_db)
):
    """
    Retorna professors disponibles per vigilància amb informació detallada (SQLite)
    Similar a populate_vigilant_combo de l'app desktop

    Args:
        data: Data en format YYYY-MM-DD
        hora: Hora (ex: "09:00")
        tipus: Tipus d'examen opcional (ex: "1.1 MATES C.") per detectar titular
        grups: Grups opcional (ex: "1-BATX-A") per detectar titular
        aula: Aula opcional (ex: "1-BATX-A") per detectar titular
    """
    try:
        hora_norm = (hora or "").strip()
        tipus_norm = _normalize_disponibles_param(tipus)
        grups_norm = _normalize_disponibles_param(grups)
        aula_norm = _normalize_disponibles_param(aula)

        context = _build_disponibles_context(
            data=data,
            db=db,
            hores_consulta={hora_norm},
            necessita_titulars=bool(tipus_norm and tipus_norm != "VIGILÀNCIA")
        )
        return _build_disponibles_for_query(
            context=context,
            hora=hora_norm,
            tipus=tipus_norm,
            grups=grups_norm,
            aula=aula_norm
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en obtenir disponibles: {str(e)}")


@router.post("/{data}/disponibles-batch")
async def obtenir_disponibles_vigilancia_batch(
    data: str,
    payload: VigilanciaDisponiblesBatchRequest,
    db: Session = Depends(get_db)
):
    """
    Retorna disponibles per múltiples consultes en una sola crida.
    """
    try:
        queries = []
        keys_seen = set()
        for query in payload.queries:
            hora_norm = (query.hora or "").strip()
            if not hora_norm:
                continue
            tipus_norm = _normalize_disponibles_param(query.tipus)
            grups_norm = _normalize_disponibles_param(query.grups)
            aula_norm = _normalize_disponibles_param(query.aula)
            cache_key = _disponibles_cache_key(hora_norm, tipus_norm, grups_norm, aula_norm)
            if cache_key in keys_seen:
                continue
            keys_seen.add(cache_key)
            queries.append({
                "hora": hora_norm,
                "tipus": tipus_norm,
                "grups": grups_norm,
                "aula": aula_norm,
                "cache_key": cache_key
            })

        if not queries:
            return {"results": {}}

        hores_consulta = {q["hora"] for q in queries}
        necessita_titulars = any(q["tipus"] and q["tipus"] != "VIGILÀNCIA" for q in queries)
        context = _build_disponibles_context(
            data=data,
            db=db,
            hores_consulta=hores_consulta,
            necessita_titulars=necessita_titulars
        )

        results = {}
        for query in queries:
            results[query["cache_key"]] = _build_disponibles_for_query(
                context=context,
                hora=query["hora"],
                tipus=query["tipus"],
                grups=query["grups"],
                aula=query["aula"]
            )
        return {"results": results}

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en obtenir disponibles batch: {str(e)}")


@router.get("/{data}")
async def obtenir_vigilancies(data: str, db: Session = Depends(get_db)):
    """
    Retorna totes les vigilàncies d'una data específica (SQLite)
    Format: llista plana amb ID únic per cada vigilància
    """
    try:
        # Carregar des de SQLite
        vigilancies_dict = VigilanciaRepository.get_by_date(db, data)

        # Aplanar l'estructura {nivell: [vigilancies]} -> llista amb IDs
        result = []
        for nivell, vigilancies_list in vigilancies_dict.items():
            result.extend(vigilancies_list)

        # Ordenar per hora i nivell
        result.sort(key=lambda x: (x["hora"], x["nivell"]))

        return result

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en carregar vigilàncies: {str(e)}")


@router.post("/{data}")
async def crear_vigilancia(data: str, vigilancia: VigilanciaCreate, db: Session = Depends(get_db)):
    """
    Afegeix una nova vigilància a una data específica (SQLite)
    """
    try:
        # Normalitzar vigilant: convertir placeholder a string buit
        vigilant_normalized = (
            vigilancia.vigilant
            if vigilancia.vigilant and not vigilancia.vigilant.startswith("--")
            else ""
        )

        # Crear vigilància amb el repository
        vigilancia_data = {
            "hora": vigilancia.hora,
            "tipus": vigilancia.tipus,
            "grups": vigilancia.grups,
            "aula": vigilancia.aula,
            "vigilant": vigilant_normalized,
            "comentaris": vigilancia.comentaris,
            "nivell": vigilancia.nivell
        }

        nova_vig = VigilanciaRepository.create(db, data, vigilancia_data)
        _refresh_vigilancia_substitucions(data, vigilancia.hora, db)

        # Generar ID compatible amb frontend
        # Obtenir totes les vigilàncies de la mateixa hora i nivell per calcular index
        vigilancies_dict = VigilanciaRepository.get_by_date(db, data)
        nivell_vigs = vigilancies_dict.get(vigilancia.nivell, [])

        # Trobar l'index de la nova vigilància
        idx = next((i for i, v in enumerate(nivell_vigs)
                   if v['hora'] == vigilancia.hora and v['vigilant'] == vigilant_normalized),
                  len(nivell_vigs) - 1)

        vig_id = f"{vigilancia.hora}|{vigilancia.nivell}|{idx}"

        return {
            "success": True,
            "message": "Vigilància creada correctament",
            "vigilancia": {
                "id": vig_id,
                "hora": nova_vig.hora,
                "tipus": nova_vig.tipus,
                "grups": nova_vig.grups,
                "aula": nova_vig.aula,
                "vigilant": nova_vig.vigilant or "",
                "comentaris": nova_vig.comentaris or "",
                "nivell": nova_vig.nivell,
                "updated_at": nova_vig.updated_at.isoformat() if nova_vig.updated_at else None
            }
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en crear vigilància: {str(e)}")


@router.put("/{data}/{vig_id}")
async def actualitzar_vigilancia(data: str, vig_id: str, update: VigilanciaUpdate, db: Session = Depends(get_db)):
    """
    Actualitza una vigilància existent (SQLite)
    ID format: hora|nivell|index
    """
    try:
        # Preparar updates només amb camps que no són None
        updates = {}
        if update.hora is not None:
            updates["hora"] = update.hora
        if update.tipus is not None:
            updates["tipus"] = update.tipus
        if update.grups is not None:
            updates["grups"] = update.grups
        if update.aula is not None:
            updates["aula"] = update.aula
        if update.vigilant is not None:
            # Normalitzar vigilant: convertir placeholder a string buit
            updates["vigilant"] = (
                update.vigilant
                if update.vigilant and not update.vigilant.startswith("--")
                else ""
            )

        if update.comentaris is not None:
            updates["comentaris"] = update.comentaris
        if update.nivell is not None:
            updates["nivell"] = update.nivell

        vig_abans = VigilanciaRepository.get_by_id(db, data, vig_id)

        if not update.force:
            if not update.updated_at:
                raise HTTPException(status_code=400, detail="Falta el camp updated_at per comprovar conflictes")
            if not vig_abans:
                raise HTTPException(status_code=404, detail="Vigilància no trobada")
            current_ts = vig_abans.updated_at.isoformat() if vig_abans.updated_at else None
            if update.updated_at != current_ts:
                raise HTTPException(status_code=409, detail={
                    "error": "conflict",
                    "message": "Aquest registre ha estat modificat per un altre usuari",
                    "current_data": _vig_to_payload(vig_abans)
                })

        # Actualitzar via repository
        vig_updated = VigilanciaRepository.update_by_id(db, data, vig_id, updates)

        if not vig_updated:
            raise HTTPException(status_code=404, detail="Vigilància no trobada")

        hores_refresc = set()
        if vig_abans and vig_abans.hora:
            hores_refresc.add(vig_abans.hora)
        if "hora" in updates and updates.get("hora"):
            hores_refresc.add(updates["hora"])
        for hora in hores_refresc:
            _refresh_vigilancia_substitucions(data, hora, db)

        return {
            "success": True,
            "message": "Vigilància actualitzada correctament",
            "updated_at": vig_updated.updated_at.isoformat() if vig_updated.updated_at else None
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en actualitzar vigilància: {str(e)}")


@router.delete("/{data}/{vig_id}")
async def eliminar_vigilancia(
    data: str,
    vig_id: str,
    updated_at: str = None,
    force: bool = False,
    db: Session = Depends(get_db)
):
    """
    Elimina una vigilància (SQLite)
    ID format: hora|nivell|index
    """
    try:
        vig_abans = VigilanciaRepository.get_by_id(db, data, vig_id)

        if not force:
            if not updated_at:
                raise HTTPException(status_code=400, detail="Falta el paràmetre updated_at per comprovar conflictes")
            if not vig_abans:
                raise HTTPException(status_code=404, detail="Vigilància no trobada")
            current_ts = vig_abans.updated_at.isoformat() if vig_abans.updated_at else None
            if updated_at != current_ts:
                raise HTTPException(status_code=409, detail={
                    "error": "conflict",
                    "message": "Aquest registre ha estat modificat per un altre usuari",
                    "current_data": _vig_to_payload(vig_abans)
                })

        # Eliminar via repository
        success = VigilanciaRepository.delete_by_id(db, data, vig_id)

        if not success:
            raise HTTPException(status_code=404, detail="Vigilància no trobada")

        if vig_abans and vig_abans.hora:
            _refresh_vigilancia_substitucions(data, vig_abans.hora, db)

        return {
            "success": True,
            "message": "Vigilància eliminada correctament"
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en eliminar vigilància: {str(e)}")


# ===== Endpoints d'Assignació Automàtica =====

@router.post("/{data}/assign/titulars", response_model=AssignmentResponse)
async def assignar_titulars(data: str, db: Session = Depends(get_db)):
    """
    Assigna automàticament NOMÉS titulars alliberats/disponibles (SQLite)
    """
    try:
        # Carregar vigilàncies des de SQLite
        vigilancies_dict = VigilanciaRepository.get_by_date(db, data)

        if not vigilancies_dict:
            return {"changes": [], "message": f"No hi ha vigilàncies per {data}"}

        vigilants_abans = _collect_vigilants_by_hour(vigilancies_dict)

        # Configurar core
        core = get_vigilancia_core(data, db)

        # Tracking global de vigilants assignats per hora
        # IMPORTANT: Carregar vigilants JA assignats per evitar duplicats
        vigilants_assignats_global = {}
        for nivell, vigilancies_list in vigilancies_dict.items():
            for vig in vigilancies_list:
                hora = vig.get('hora', '')
                vigilant = vig.get('vigilant', '')
                if hora and vigilant and vigilant != "-- selecciona vigilant --":
                    if hora not in vigilants_assignats_global:
                        vigilants_assignats_global[hora] = set()
                    vigilants_assignats_global[hora].add(vigilant)

        assigned_count = 0

        # Processar tots els nivells (modifica in-place)
        for nivell, vigilancies_list in vigilancies_dict.items():
            count = assign_phase1_titulars(vigilancies_list, core, vigilants_assignats_global, db)
            assigned_count += count

        # Desar canvis a SQLite (actualitzar cada vigilància modificada)
        for nivell, vigilancies_list in vigilancies_dict.items():
            for vig in vigilancies_list:
                # Actualitzar si té vigilant assignat (i té ID)
                if 'id' in vig and vig.get('vigilant'):
                    updates = {'vigilant': vig['vigilant']}
                    VigilanciaRepository.update_by_id(db, data, vig['id'], updates)

        # Comptar pendents
        remaining_count = 0
        for nivell, vigilancies_list in vigilancies_dict.items():
            for vig in vigilancies_list:
                vigilant = vig.get('vigilant', '')
                if not vigilant or vigilant == "-- selecciona vigilant --":
                    remaining_count += 1

        vigilants_despres = _collect_vigilants_by_hour(vigilancies_dict)
        hores_refresc = set(vigilants_abans.keys()) | set(vigilants_despres.keys())
        for hora in sorted(hores_refresc):
            if vigilants_abans.get(hora, set()) != vigilants_despres.get(hora, set()):
                _refresh_vigilancia_substitucions(data, hora, db)

        return AssignmentResponse(
            assigned_count=assigned_count,
            remaining_count=remaining_count,
            message=f"✅ S'han assignat {assigned_count} titulars. Queden {remaining_count} vigilàncies pendents."
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en assignar titulars: {str(e)}")


@router.post("/{data}/assign/pendents", response_model=AssignmentResponse)
async def assignar_pendents(data: str, disponibles: bool = False, db: Session = Depends(get_db)):
    """
    Assigna vigilàncies pendents amb scoring intel·ligent (SQLite)

    Args:
        disponibles: Si True, inclou professors disponibles (guàrdia, etc.)
                     Si False, només alliberats
    """
    try:
        # Carregar vigilàncies des de SQLite
        vigilancies_dict = VigilanciaRepository.get_by_date(db, data)

        if not vigilancies_dict:
            return {"changes": [], "message": f"No hi ha vigilàncies per {data}"}

        vigilants_abans = _collect_vigilants_by_hour(vigilancies_dict)

        # Configurar core
        core = get_vigilancia_core(data, db)
        afinitats_cfg = get_vigilancies_afinitats(db)

        # Tracking global de vigilants assignats per hora
        # IMPORTANT: Carregar vigilants JA assignats per evitar duplicats
        vigilants_assignats_global = {}
        for nivell, vigilancies_list in vigilancies_dict.items():
            for vig in vigilancies_list:
                hora = vig.get('hora', '')
                vigilant = vig.get('vigilant', '')
                if hora and vigilant and vigilant != "-- selecciona vigilant --":
                    if hora not in vigilants_assignats_global:
                        vigilants_assignats_global[hora] = set()
                    vigilants_assignats_global[hora].add(vigilant)

        assigned_count = 0

        # FASE 1: Titulars (tots els nivells)
        for nivell, vigilancies_list in vigilancies_dict.items():
            count = assign_phase1_titulars(vigilancies_list, core, vigilants_assignats_global, db)
            assigned_count += count

        # FASE 2: Professors del grup (tots els nivells)
        for nivell, vigilancies_list in vigilancies_dict.items():
            count = assign_phase2_professors_grup(vigilancies_list, core, vigilants_assignats_global)
            assigned_count += count

        # FASE 3 - PASSADA 1: Alliberats del mateix prefix (prioritat absoluta)
        for nivell, vigilancies_list in vigilancies_dict.items():
            count = assign_phase3_passada(
                vigilancies_list, nivell, core, vigilants_assignats_global,
                filter_mode="afinitat_exacta",
                only_alliberats=True,
                afinitats_cfg=afinitats_cfg
            )
            assigned_count += count

        # FASE 3 - PASSADA 2: Alliberats per proximitat de prefix (sense mateix prefix)
        for nivell, vigilancies_list in vigilancies_dict.items():
            count = assign_phase3_passada(
                vigilancies_list, nivell, core, vigilants_assignats_global,
                filter_mode="afinitat_propera",
                only_alliberats=True,
                afinitats_cfg=afinitats_cfg
            )
            assigned_count += count

        # FASE 3 - PASSADA 3: Alliberats sense prefix resolt (al final dels alliberats)
        for nivell, vigilancies_list in vigilancies_dict.items():
            count = assign_phase3_passada(
                vigilancies_list, nivell, core, vigilants_assignats_global,
                filter_mode="sense_prefix",
                only_alliberats=True,
                afinitats_cfg=afinitats_cfg
            )
            assigned_count += count

        # FASE 3 - PASSADA 4: DISPONIBLES (guàrdies, etc.) - GLOBAL
        if disponibles:
            for nivell, vigilancies_list in vigilancies_dict.items():
                count = assign_phase3_passada(
                    vigilancies_list, nivell, core, vigilants_assignats_global,
                    filter_mode="tots",
                    only_alliberats=False,
                    afinitats_cfg=afinitats_cfg
                )
                assigned_count += count

        # Desar canvis a SQLite (actualitzar cada vigilància modificada)
        for nivell, vigilancies_list in vigilancies_dict.items():
            for vig in vigilancies_list:
                # Actualitzar si té vigilant assignat (i té ID)
                if 'id' in vig and vig.get('vigilant'):
                    updates = {'vigilant': vig['vigilant']}
                    VigilanciaRepository.update_by_id(db, data, vig['id'], updates)

        # Comptar pendents
        remaining_count = 0
        for nivell, vigilancies_list in vigilancies_dict.items():
            for vig in vigilancies_list:
                vigilant = vig.get('vigilant', '')
                if not vigilant or vigilant == "-- selecciona vigilant --":
                    remaining_count += 1

        vigilants_despres = _collect_vigilants_by_hour(vigilancies_dict)
        hores_refresc = set(vigilants_abans.keys()) | set(vigilants_despres.keys())
        for hora in sorted(hores_refresc):
            if vigilants_abans.get(hora, set()) != vigilants_despres.get(hora, set()):
                _refresh_vigilancia_substitucions(data, hora, db)

        tipus_text = "alliberats + disponibles" if disponibles else "alliberats"
        return AssignmentResponse(
            assigned_count=assigned_count,
            remaining_count=remaining_count,
            message=f"✅ S'han assignat {assigned_count} vigilants ({tipus_text}). Queden {remaining_count} pendents."
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en assignar pendents: {str(e)}")


@router.post("/{data}/reassign-problematics")
async def reassignar_problematics(data: str, db: Session = Depends(get_db)):
    """
    Reassigna vigilàncies problemàtiques (absents, duplicats, amb classe, de baixa o substituts).
    """
    try:
        vigilancies_dict = VigilanciaRepository.get_by_date(db, data)
        if not vigilancies_dict:
            return {"changes": [], "message": f"No hi ha vigilàncies per reassignar el {data}"}

        vigilancies = []
        vigilants_abans = {}
        vigilancies_by_hora = defaultdict(list)
        for nivell, vigs in vigilancies_dict.items():
            for vig in vigs:
                vigilancies.append(vig)
                hora = (vig.get("hora") or "").strip()
                if hora:
                    vigilancies_by_hora[hora].append(vig)
                if vig.get("id"):
                    vigilants_abans[str(vig.get("id"))] = (vig.get("vigilant") or "").strip()

        substitucions_data = SubstitucioRepository.get_by_date(db, data)
        absents_per_hora = defaultdict(set)
        substituts_per_hora = defaultdict(set)
        for sub in substitucions_data:
            hora = (sub.get("hora") or "").strip()
            prof_absent = (sub.get("professor_absent") or "").strip()
            substitut = (sub.get("substitut") or "").strip()
            tipus_abs = (sub.get("tipus_absencia") or "").strip()

            if hora and prof_absent and tipus_abs not in ["VIGILANCIA", "ENCADENADA"]:
                absents_per_hora[hora].add(prof_absent)
            if hora and substitut:
                substituts_per_hora[hora].add(substitut)

        from config.constants import PROFESSORS_BAIXA
        professors_baixa = set()
        try:
            data_obj_date = datetime.strptime(data, "%Y-%m-%d").date()
            for baixa in PROFESSORS_BAIXA:
                data_inici = datetime.strptime(baixa['data_inici'], '%Y-%m-%d').date()
                data_final = datetime.strptime(baixa['data_final'], '%Y-%m-%d').date()
                if data_inici <= data_obj_date <= data_final:
                    professors_baixa.add(baixa['professor'])
        except:
            pass

        horari_mgr = get_horari(data_iso=data)
        date_obj = datetime.strptime(data, "%Y-%m-%d")
        dia_name = horari_mgr.get_dia_name(date_obj.weekday())
        grups_alliberats_data = GrupsAlliberatsRepository.get_by_date(db, data)

        def grups_compatible(grup_classe: str, grup_examen: str) -> bool:
            if not grup_classe or not grup_examen:
                return False
            gc = grup_classe.strip().upper()
            ge = grup_examen.strip().upper()
            if gc == ge:
                return True
            if ge in gc or gc in ge:
                return True
            parts_classe = gc.split('-')
            parts_examen = ge.split('-')
            if len(parts_classe) >= 2 and len(parts_examen) >= 2:
                nivell_classe = '-'.join(parts_classe[:-1])
                nivell_examen = '-'.join(parts_examen[:-1])
                if nivell_classe == nivell_examen:
                    lletra_classe = parts_classe[-1]
                    lletra_examen = parts_examen[-1]
                    if lletra_examen in lletra_classe or lletra_classe in lletra_examen:
                        return True
            return False

        problemes = set()

        # Duplicats per hora
        for hora, vigs in vigilancies_by_hora.items():
            vigilants = [v.get("vigilant", "").strip() for v in vigs if v.get("vigilant")]
            for vigilant in set(vigilants):
                if vigilants.count(vigilant) > 1:
                    for v in vigs:
                        if v.get("vigilant", "").strip() == vigilant:
                            problemes.add(v.get("id"))

        # Absents, baixa, substituts i classe
        for hora, vigs in vigilancies_by_hora.items():
            grups_examen = set()
            for vig in vigs:
                grups_vig = (vig.get("grups") or "").strip()
                if grups_vig:
                    grups_examen.add(grups_vig)
            for grup_alliberat in grups_alliberats_data.get(hora, []):
                grups_examen.add(grup_alliberat)

            for vig in vigs:
                vigilant = (vig.get("vigilant") or "").strip()
                if not vigilant:
                    continue

                if vigilant in absents_per_hora.get(hora, set()):
                    problemes.add(vig.get("id"))
                    continue

                if vigilant in professors_baixa:
                    problemes.add(vig.get("id"))
                    continue

                if vigilant in substituts_per_hora.get(hora, set()):
                    problemes.add(vig.get("id"))
                    continue

                activitat = horari_mgr.get_activitat(dia_name, hora, vigilant)
                if activitat:
                    assignatura = activitat.get("assignatura", "")
                    grup = activitat.get("grup", "")
                    if grup and assignatura:
                        grup_alliberat = False
                        for grup_exam in grups_examen:
                            if grups_compatible(grup, grup_exam):
                                grup_alliberat = True
                                break
                        if not grup_alliberat:
                            problemes.add(vig.get("id"))

        # Netejar vigilants problemàtics
        cleared = 0
        hores_cleared = set()
        for vig_id in problemes:
            if not vig_id:
                continue
            vig = VigilanciaRepository.get_by_id(db, data, str(vig_id))
            if vig and vig.hora:
                hores_cleared.add(vig.hora)
            VigilanciaRepository.update_by_id(db, data, str(vig_id), {"vigilant": ""})
            cleared += 1

        # Reassignar pendents (incloent els que hem netejat)
        assign_response = await assignar_pendents(data, disponibles=True, db=db)

        for hora in sorted(hores_cleared):
            _refresh_vigilancia_substitucions(data, hora, db)

        vigilancies_dict_despres = VigilanciaRepository.get_by_date(db, data)
        canvis = []
        for nivell, vigs in vigilancies_dict_despres.items():
            for vig in vigs:
                vig_id = str(vig.get("id")) if vig.get("id") else ""
                if not vig_id:
                    continue
                abans = vigilants_abans.get(vig_id, "")
                despres = (vig.get("vigilant") or "").strip()
                if abans != despres and (abans or despres):
                    canvis.append({
                        "hora": vig.get("hora", ""),
                        "nivell": vig.get("nivell", ""),
                        "tipus": vig.get("tipus", ""),
                        "abans": abans,
                        "despres": despres
                    })

        return {
            "success": True,
            "cleared": cleared,
            "assigned": assign_response.assigned_count,
            "remaining": assign_response.remaining_count,
            "changes": canvis,
            "message": "Reassignació de vigilàncies completada"
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en reassignar problemàtics: {str(e)}")


@router.post("/{data}/clear")
async def netejar_assignacions(data: str, db: Session = Depends(get_db)):
    """
    Neteja totes les assignacions de vigilants (manté tipus, grups, aules) (SQLite)
    """
    try:
        # Netejar directament amb una query SQL per evitar problemes amb IDs compostos
        from models import Vigilancia
        vigilancies = db.query(Vigilancia).filter(
            and_(
                Vigilancia.data == parse_date(data),
                Vigilancia.vigilant.isnot(None),
                Vigilancia.vigilant != '',
                Vigilancia.vigilant != '-- selecciona vigilant --'
            )
        ).all()

        cleared_count = 0
        hores_cleared = set()
        for vig in vigilancies:
            if vig.hora:
                hores_cleared.add(vig.hora)
            vig.vigilant = ''
            cleared_count += 1

        db.commit()

        for hora in sorted(hores_cleared):
            _refresh_vigilancia_substitucions(data, hora, db)

        return {
            "success": True,
            "cleared_count": cleared_count,
            "message": f"✅ S'han netejat {cleared_count} assignacions"
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en netejar assignacions: {str(e)}")


@router.post("/{data}/sort")
async def ordenar_per_hora(data: str, db: Session = Depends(get_db)):
    """
    Ordena vigilàncies per hora seguint l'ordre de l'horari (SQLite)

    Nota: En SQLite no hi ha camp d'ordre explícit. Les vigilàncies es retornen
    ordenades per hora quan es consulten. Aquest endpoint retorna èxit per compatibilitat.
    """
    try:
        # Verificar que hi ha vigilàncies per aquesta data
        vigilancies_dict = VigilanciaRepository.get_by_date(db, data)

        if not vigilancies_dict:
            raise HTTPException(status_code=404, detail=f"No hi ha vigilàncies per {data}")

        # Comptar vigilàncies
        sorted_count = sum(len(vigs) for vigs in vigilancies_dict.values())

        return {
            "success": True,
            "sorted_count": sorted_count,
            "message": f"✅ Vigilàncies ordenades per hora"
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en ordenar vigilàncies: {str(e)}")
