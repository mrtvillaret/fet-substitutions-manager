"""
Funcions auxiliars compartides pel backend
- Gestors singleton (horari, substitucions, etc.)
- Funcions d'assignació automàtica de vigilàncies
"""
from typing import Optional, Dict, List, Any
from datetime import datetime
from sqlalchemy.orm import Session
import os
import json

from horari_web import GestorHorariWeb  # Versió web que llegeix de SQLite
from core.substitucions import GestorSubstitucions
from core.alliberats import GestorAlliberats
from core.absencies import GestorAbsencies
from core.vigilancia_core import VigilanciaCore
from core.vigilancia_assignacio import escollir_aleatoriament_amb_pesos
from config.constants import PRIORITATS
from repositories import (
    SubstitucioRepository,
    GrupsAlliberatsRepository,
    VigilanciaRepository,
    ConfiguracioExamenRepository,
    ConfiguracioRepository,
    XMLVersionRepository,
    ProfessorRepository
)
from database import get_db_session, get_data_db_session, get_data_dir_for_institucio


# ===== Variables globals (singleton pattern) =====
_horari: Dict[str, GestorHorariWeb] = {}
_alliberats: Dict[str, GestorAlliberats] = {}
_vigilancia_core: Dict[str, VigilanciaCore] = {}
_absencies: Dict[str, GestorAbsencies] = {}
_substitucions_mgr: Dict[str, GestorSubstitucions] = {}

VIGILANCIES_AFINITATS_KEY = "vigilancies_afinitats"


class MissingXmlError(RuntimeError):
    def __init__(self, institucio: str, xml_path: Optional[str]):
        message = f"Cal pujar un fitxer XML d'horari per a la institució {institucio}."
        super().__init__(message)
        self.institucio = institucio
        self.xml_path = xml_path


def _cache_key(institucio: str, xml_path: str) -> str:
    return f"{institucio}:{xml_path}"


def _get_institucio_actual() -> str:
    from config.settings import config
    return config.global_data.get("institucio") or os.getenv("APP_INSTITUCIO") or "exemple"


def invalidar_horari(institucio: str = None):
    """Invalida el singleton de l'horari per forçar recàrrega"""
    global _horari, _alliberats, _absencies, _substitucions_mgr, _vigilancia_core
    if institucio:
        prefix = f"{institucio}:"
        for cache in (_horari, _alliberats, _absencies, _substitucions_mgr, _vigilancia_core):
            for key in list(cache.keys()):
                if key.startswith(prefix):
                    cache.pop(key, None)
    else:
        _horari = {}
        _alliberats = {}
        _absencies = {}
        _substitucions_mgr = {}
        _vigilancia_core = {}
    print("🔄 Singleton d'horari invalidat - es recarregarà en proper ús")


def invalidar_cache_horari(institucio: str = None):
    """
    Invalida només el cache d'abreviatures de l'horari, sense recarregar-lo tot.
    Útil quan es modifiquen les abreviatures de grups.
    """
    global _horari
    if institucio:
        prefix = f"{institucio}:"
        for key, horari in _horari.items():
            if key.startswith(prefix):
                horari._abreviatures_cache = None
        print("✅ Cache d'abreviatures invalidat")
        return
    for horari in _horari.values():
        horari._abreviatures_cache = None
    if _horari:
        print("✅ Cache d'abreviatures invalidat")


def _resolve_xml_path(institucio: str, data_iso: str = None) -> Optional[str]:
    xml_path = None
    try:
        with get_data_db_session(institucio) as db:
            if data_iso:
                version = XMLVersionRepository.get_for_date(db, data_iso)
            else:
                version = XMLVersionRepository.get_current(db)
            if version:
                xml_path = version.path
    except Exception:
        xml_path = None

    if not xml_path:
        try:
            with get_data_db_session(institucio) as db:
                xml_path = ConfiguracioRepository.get(db, 'xml_horari_path')
        except Exception:
            xml_path = None

    if not xml_path:
        xml_path = os.getenv("APP_XML_PATH")

    if xml_path and not os.path.isabs(xml_path):
        data_dir = get_data_dir_for_institucio(institucio)
        xml_path = os.path.join(str(data_dir), xml_path)

    return xml_path


def get_xml_path_for_date(institucio: str = None, data_iso: str = None) -> Optional[str]:
    instit = institucio or _get_institucio_actual()
    return _resolve_xml_path(instit, data_iso)


def get_horari(institucio: str = None, data_iso: str = None) -> GestorHorariWeb:
    """Singleton del gestor d'horari - Versió Web amb configuració de SQLite"""
    global _horari
    institucio = institucio or _get_institucio_actual()
    xml_path = _resolve_xml_path(institucio, data_iso)
    if not xml_path or not os.path.exists(xml_path):
        raise MissingXmlError(institucio, xml_path)
    key = _cache_key(institucio, xml_path or "none")
    if key in _horari:
        return _horari[key]

    # Llegir configuració de SQLite
    with get_data_db_session(institucio) as db:
        ultim_professor_subs = ConfiguracioRepository.get(db, 'ultim_professor_subs')
        if not ultim_professor_subs:
            ultim_professor_subs = None  # Sense límit

    # Obtenir path XML (SQLite per institució)
    horari = GestorHorariWeb(xml_path, ultim_professor_subs)
    _horari[key] = horari

    if data_iso is None:
        try:
            with get_data_db_session(institucio) as db:
                sync_info = ProfessorRepository.sync_from_xml(db, horari.professors)
                print(f"✅ Professors sincronitzats ({institucio}): {sync_info}")
        except Exception as e:
            print(f"⚠️  Error sincronitzant professors ({institucio}): {e}")

    print(f"✅ Horari carregat ({institucio}): {len(horari.professors)} professors (límit: {ultim_professor_subs or 'cap'})")
    return horari


def get_gestors(institucio: str = None, data_iso: str = None):
    """Retorna tots els gestors necessaris (singleton)"""
    global _horari, _alliberats, _absencies, _substitucions_mgr
    institucio = institucio or _get_institucio_actual()

    xml_path = _resolve_xml_path(institucio, data_iso)
    key = _cache_key(institucio, xml_path or "none")

    if key not in _substitucions_mgr:
        horari = get_horari(institucio, data_iso)
        alliberats = GestorAlliberats(horari)
        absencies = GestorAbsencies(horari)
        substitucions_mgr = GestorSubstitucions(horari, alliberats, absencies)

        _horari[key] = horari
        _alliberats[key] = alliberats
        _absencies[key] = absencies
        _substitucions_mgr[key] = substitucions_mgr

        print(f"✅ Gestors inicialitzats correctament ({institucio})")

    # El gestor d'alliberats necessita la data per filtrar professors de baixa.
    if data_iso:
        try:
            _alliberats[key].set_data_actual(datetime.strptime(data_iso, "%Y-%m-%d").date())
        except Exception:
            pass

    return (
        _substitucions_mgr[key],
        _horari[key],
        _alliberats[key],
        _absencies[key]
    )


def get_vigilancia_core(data: str, db: Session = None) -> VigilanciaCore:
    """Crea i configura VigilanciaCore per una data específica"""
    global _vigilancia_core
    instit = _get_institucio_actual()

    # Sempre crear nou (per actualitzar amb dades del dia)
    xml_path = _resolve_xml_path(instit, data)
    key = _cache_key(instit, xml_path or "none")
    _vigilancia_core[key] = VigilanciaCore()

    # Obtenir gestors
    _, horari, alliberats, _ = get_gestors(instit, data)

    # Validar que tenim sessió de base de dades (obligatori)
    if not db:
        raise ValueError("get_vigilancia_core() requereix sessió de base de dades (db)")

    # Carregar configuració d'exàmens des de SQLite
    assignatures_config = ConfiguracioExamenRepository.get_all_as_dict(db)
    date_obj = datetime.strptime(data, "%Y-%m-%d")

    substitucions_data = SubstitucioRepository.get_by_date(db, data)
    absents = {}
    absents_tipus = {}

    for sub in substitucions_data:
        professor = sub.get("professor_absent", "")
        hora = sub.get("hora", "")
        tipus_abs = sub.get("tipus_absencia", "") or "ABSENCIA"

        if tipus_abs in ["VIGILANCIA", "ENCADENADA"]:
            continue

        if professor and hora:
            if professor not in absents:
                absents[professor] = []
                absents_tipus[professor] = tipus_abs
            if hora not in absents[professor]:
                absents[professor].append(hora)

    # Professors de baixa: absents a totes les hores (regla única de no-assignació automàtica).
    try:
        from config.constants import PROFESSORS_BAIXA

        hores_dia = list(getattr(horari, "hores", []) or [])
        data_obj_date = date_obj.date()

        for baixa in PROFESSORS_BAIXA:
            professor = (baixa.get("professor") or "").strip()
            if not professor:
                continue

            data_inici = datetime.strptime(baixa["data_inici"], "%Y-%m-%d").date()
            data_final = datetime.strptime(baixa["data_final"], "%Y-%m-%d").date()
            if not (data_inici <= data_obj_date <= data_final):
                continue

            absents.setdefault(professor, [])
            for hora in hores_dia:
                if hora not in absents[professor]:
                    absents[professor].append(hora)
            absents_tipus[professor] = "BAIXA"
    except Exception:
        pass

    # Grups sense classe (Des de SQLite)
    grups_sense_classe = GrupsAlliberatsRepository.get_by_date(db, data)

    # Afegir grups amb examen (vigilàncies) com a alliberats per l'hora corresponent
    try:
        vigilancies_data = VigilanciaRepository.get_by_date(db, data)
        for vig_list in vigilancies_data.values():
            for vig in vig_list:
                hora_vig = vig.get("hora")
                grup_vig = vig.get("grups")
                if not hora_vig or not grup_vig:
                    continue
                grups_sense_classe.setdefault(hora_vig, [])
                if grup_vig not in grups_sense_classe[hora_vig]:
                    grups_sense_classe[hora_vig].append(grup_vig)
    except Exception as e:
        print(f"⚠️ No s'han pogut afegir grups d'examen als alliberats: {e}")

    # Dia de la setmana
    weekday_idx = date_obj.weekday()
    dia_name = horari.get_dia_name(weekday_idx)

    # Configurar core
    _vigilancia_core[key].set_config(
        assignatures_config=assignatures_config,
        professors=sorted(horari.professors),
        absents_actuals=absents,
        horari_gestor=horari,
        alliberats_gestor=alliberats,
        grups_sense_classe=grups_sense_classe,
        dia_actual=dia_name
    )

    return _vigilancia_core[key]


# ===== Funcions d'Assignació Automàtica =====

def get_vigilants_assignats_hora(vigilancies_dict: Dict, data: str, hora: str) -> set:
    """Retorna set de professors ja assignats a una hora"""
    vigilants = set()
    if data in vigilancies_dict:
        for nivell, vig_list in vigilancies_dict[data].items():
            for vig in vig_list:
                if vig.get('hora') == hora and vig.get('vigilant'):
                    vigilants.add(vig['vigilant'])
    return vigilants


def normalize_vigilancies_afinitats(rows: List[Dict[str, Any]]) -> List[Dict[str, List[str]]]:
    """Normalitza i valida files d'afinitats."""
    normalized: List[Dict[str, List[str]]] = []
    seen_bases = set()
    rows = rows or []

    for row in rows:
        if not isinstance(row, dict):
            continue
        base = str(row.get("base", "")).strip()
        if not base or base in seen_bases:
            continue
        ordre_raw = row.get("ordre", [])
        if isinstance(ordre_raw, str):
            ordre_items = [x.strip() for x in ordre_raw.split(",")]
        elif isinstance(ordre_raw, list):
            ordre_items = [str(x).strip() for x in ordre_raw]
        else:
            ordre_items = []
        ordre = []
        for item in ordre_items:
            if item and item not in ordre:
                ordre.append(item)

        if base not in ordre:
            ordre.insert(0, base)
        if not ordre:
            ordre = [base]

        normalized.append({"base": base, "ordre": ordre})
        seen_bases.add(base)

    return normalized


def get_vigilancies_afinitats(db: Session) -> List[Dict[str, List[str]]]:
    """
    Carrega afinitats de BD (sense fallback hardcoded).
    """
    raw = ConfiguracioRepository.get(db, VIGILANCIES_AFINITATS_KEY)
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        normalized = normalize_vigilancies_afinitats(parsed if isinstance(parsed, list) else [])
        return normalized
    except Exception:
        return []


def save_vigilancies_afinitats(db: Session, rows: List[Dict[str, Any]]) -> List[Dict[str, List[str]]]:
    normalized = normalize_vigilancies_afinitats(rows)
    ConfiguracioRepository.set(
        db,
        VIGILANCIES_AFINITATS_KEY,
        json.dumps(normalized, ensure_ascii=False),
        tipus="json",
        descripcio="Afinitats de grups per autoassignació de vigilàncies"
    )
    return normalized


def _split_group_tokens(value: str) -> List[str]:
    if not value:
        return []
    normalized = str(value).replace(";", ",")
    return [p.strip() for p in normalized.split(",") if p.strip()]


def _resolve_affinity_prefix(grups: str, bases_sorted: List[str]) -> Optional[str]:
    """Retorna el prefix (base) que millor coincideix per començament de grup."""
    for token in _split_group_tokens(grups):
        token_upper = token.upper()
        for base in bases_sorted:
            if token_upper.startswith(base.upper()):
                return base
    return None


def get_nivell_proximitat_order(nivell_base: str) -> list:
    """Retorna ordre de proximitat de nivells"""
    nivells_hierarchy = {
        "1-BATX": ["1-BATX", "2-BATX", "4-ESO", "3-ESO", "2-ESO", "1-ESO"],
        "2-BATX": ["2-BATX", "1-BATX", "4-ESO", "3-ESO", "2-ESO", "1-ESO"],
        "4-ESO": ["4-ESO", "3-ESO", "2-ESO", "1-ESO", "1-BATX", "2-BATX"],
        "3-ESO": ["3-ESO", "4-ESO", "2-ESO", "1-ESO", "1-BATX", "2-BATX"],
        "2-ESO": ["2-ESO", "1-ESO", "3-ESO", "4-ESO", "1-BATX", "2-BATX"],
        "1-ESO": ["1-ESO", "2-ESO", "3-ESO", "4-ESO", "1-BATX", "2-BATX"],
        "GENERAL": ["GENERAL"]
    }
    return nivells_hierarchy.get(nivell_base, [nivell_base])


def get_professor_main_level(horari, dia_name: str, professor: str, hora: str) -> str:
    """
    Obté el nivell on ensenyava el professor A AQUELLA HORA CONCRETA
    Si tenia 2n BATX a les 12:30, té prioritat per vigilar 2n BATX
    """
    try:
        # Mirar què tenia el professor a AQUESTA HORA CONCRETA
        activitat = horari.get_activitat(dia_name, hora, professor)
        if activitat:
            grup = activitat.get("grup", "")
            if not grup:
                return "Unknown"

            # Extreure nivell del grup (ex: "1-BATX-A" -> "1-BATX")
            if "BATX" in grup:
                if "1" in grup and not "12" in grup:  # Evitar 1-2-BATX
                    return "1-BATX"
                elif "2" in grup:
                    return "2-BATX"
            elif "ESO" in grup:
                if grup.startswith("3") or "-3-" in grup:
                    return "3-ESO"
                elif grup.startswith("4") or "-4-" in grup:
                    return "4-ESO"
                elif grup.startswith("2") or "-2-" in grup:
                    return "2-ESO"
                elif grup.startswith("1") or "-1-" in grup:
                    return "1-ESO"
    except:
        pass
    return "Unknown"


def _get_tipus_activitat_professor(core: VigilanciaCore, professor: str, hora: str) -> str:
    """
    Determina el tipus d'activitat per aplicar la política d'autoassignació.
    """
    try:
        activitat = core.horari_gestor.get_activitat(core.dia_actual, hora, professor) or {}
        assignatura = (activitat.get("assignatura") or "").strip()
        grup = (activitat.get("grup") or "").strip()
        if not assignatura:
            return ""

        # Si estava amb grup alliberat, es considera "alliberat" (categoria pròpia).
        grups_hora = core.grups_sense_classe.get(hora, set()) if isinstance(core.grups_sense_classe, dict) else core.grups_sense_classe
        if grup and grup in set(grups_hora or []):
            return "alliberat"
        return assignatura
    except Exception:
        return ""


def assign_phase1_titulars(vigilancies_list: list, core: VigilanciaCore,
                           vigilants_assignats_global: Dict[str, set], db: Session = None) -> int:
    """FASE 1: Assigna NOMÉS titulars alliberats/disponibles"""
    assigned_count = 0

    for vigilance in vigilancies_list:
        vigilant_actual = vigilance.get('vigilant', '')

        # Saltar si ja té vigilant
        if vigilant_actual and vigilant_actual != "-- selecciona vigilant --":
            continue

        tipus = vigilance.get('tipus', '')
        grups = vigilance.get('grups', '')
        aula = vigilance.get('aula', '')
        hora = vigilance.get('hora', '')

        # Intentar assignar titular
        if tipus not in ["VIGILÀNCIA"] and grups:
            # Buscar titular directament des de SQLite si tenim db
            if db:
                titular = ConfiguracioExamenRepository.buscar_titular(db, tipus, grups, aula)
            else:
                titular = core.buscar_professor_titular(tipus, grups, aula)

            if titular:
                titular_status = core.get_titular_status(titular, hora)
                vigilants_hora = vigilants_assignats_global.get(hora, set())

                if (titular_status in ["alliberat", "disponible"] and
                    titular not in vigilants_hora):
                    # Regla funcional: si és titular i està disponible/alliberat,
                    # s'ha d'assignar sempre que no estigui absent.
                    if titular not in core.absents_actuals or hora not in core.absents_actuals.get(titular, []):
                        vigilance['vigilant'] = titular
                        vigilants_hora.add(titular)
                        vigilants_assignats_global[hora] = vigilants_hora
                        assigned_count += 1

    return assigned_count


def assign_phase2_professors_grup(vigilancies_list: list, core: VigilanciaCore,
                                   vigilants_assignats_global: Dict[str, set]) -> int:
    """FASE 2: Assigna professors que tenien classe amb el grup (alliberats)"""
    assigned_count = 0

    for vigilance in vigilancies_list:
        vigilant_actual = vigilance.get('vigilant', '')

        if vigilant_actual and vigilant_actual != "-- selecciona vigilant --":
            continue

        grups = vigilance.get('grups', '')
        hora = vigilance.get('hora', '')

        if grups and isinstance(core.grups_sense_classe, dict):
            # Obtenir professors que tenien aquest grup
            professors_del_grup = []
            try:
                for prof in core.professors:
                    activitat = core.horari_gestor.get_activitat(core.dia_actual, hora, prof)
                    if activitat:
                        grup_prof = activitat.get("grup", "")
                        if grup_prof == grups:
                            professors_del_grup.append(prof)
            except:
                pass

            vigilants_hora = vigilants_assignats_global.get(hora, set())

            for prof in professors_del_grup:
                if prof not in vigilants_hora:
                    # Verificar que està alliberat
                    grups_hora = core.grups_sense_classe.get(hora, set())
                    if grups in grups_hora:
                        # Fail-safe: regla de domini abans d'assignar
                        if core.is_professor_assignable(prof, hora, "alliberat"):
                            vigilance['vigilant'] = prof
                            vigilants_hora.add(prof)
                            vigilants_assignats_global[hora] = vigilants_hora
                            assigned_count += 1
                            break

    return assigned_count


def assign_phase3_passada(vigilancies_list: list, nivell: str, core: VigilanciaCore,
                          vigilants_assignats_global: Dict[str, set],
                          filter_mode: str,
                          only_alliberats: bool,
                          afinitats_cfg: Optional[List[Dict[str, List[str]]]] = None) -> int:
    """
    Una passada d'assignació amb filtre específic

    filter_mode:
        - "afinitat_exacta": mateix prefix configurat del grup (prioritat màxima)
        - "afinitat_propera": proximitat configurable per prefix (sense mateix prefix)
        - "sense_prefix": alliberats que no casen amb cap prefix (al final)
        - "mateix_nivell": només professors del mateix nivell
        - "nivells_propers": professors de nivells propers (no mateix)
        - "tots": tots els disponibles
    """
    assigned_count = 0
    afinitats_norm = normalize_vigilancies_afinitats(afinitats_cfg or [])
    afinitat_map = {row["base"]: row["ordre"] for row in afinitats_norm}
    bases_sorted = sorted(afinitat_map.keys(), key=len, reverse=True)

    for vigilance in vigilancies_list:
        vigilant_actual = vigilance.get('vigilant', '')

        if vigilant_actual and vigilant_actual != "-- selecciona vigilant --":
            continue

        tipus = vigilance.get('tipus', '')
        grups = vigilance.get('grups', '')
        aula = vigilance.get('aula', '')
        hora = vigilance.get('hora', '')

        # Obtenir disponibles
        disponibles = core.get_disponibles_for_vigilance(hora, vigilance)
        vigilants_hora = vigilants_assignats_global.get(hora, set())

        # Ordre de proximitat legacy per compatibilitat (si cal)
        proximitat_order = get_nivell_proximitat_order(nivell)
        # Proximitat configurable per afinitats
        vig_prefix = _resolve_affinity_prefix(grups, bases_sorted)
        vig_order = afinitat_map.get(vig_prefix, [])

        candidats = []

        for prof_data in disponibles:
            if isinstance(prof_data, tuple) and len(prof_data) >= 3:
                nom, tipus_disp, detall = prof_data[:3]

                # Saltar si ja assignat
                if nom in vigilants_hora:
                    continue

                # Regla única de domini (absents/baixa + categories no autoassignables)
                if not core.is_professor_assignable(nom, hora, tipus_disp):
                    continue

                # Categoria per scoring (ja validada com autoassignable)
                categoria = core.get_categoria_prioritat(tipus_disp)

                # Detectar alliberats reals
                es_alliberat_real = (tipus_disp == "alliberat" or
                                    (tipus_disp == "vigilància" and "tenia" in detall and " - " in detall))

                # Filtrar per tipus si només volem alliberats
                if only_alliberats and not es_alliberat_real:
                    continue

                # Dades de grup del professor a l'hora
                activitat_prof = core.horari_gestor.get_activitat(core.dia_actual, hora, nom) or {}
                grup_prof = (activitat_prof.get("grup") or "").strip()
                prof_prefix = _resolve_affinity_prefix(grup_prof, bases_sorted)
                prox_idx = None

                # APLICAR FILTRE SEGONS MODE
                if filter_mode == "afinitat_exacta":
                    # Mateix prefix estrictament.
                    if not vig_order:
                        continue
                    if not prof_prefix or prof_prefix != vig_prefix:
                        continue
                    prox_idx = 0
                elif filter_mode == "afinitat_propera":
                    # Prefix proper segons ordre configurable (exclou mateix prefix).
                    if not vig_order:
                        continue
                    if (not prof_prefix or
                        prof_prefix not in vig_order or
                        prof_prefix == vig_prefix):
                        continue
                    prox_idx = vig_order.index(prof_prefix)
                elif filter_mode == "sense_prefix":
                    # Si vigilància té prefix, només entren candidats sense prefix.
                    if vig_prefix and prof_prefix:
                        continue
                elif filter_mode == "mateix_nivell":
                    # Legacy
                    prof_nivell = get_professor_main_level(core.horari_gestor, core.dia_actual, nom, hora)
                    # NOMÉS professors del mateix nivell
                    if prof_nivell not in proximitat_order or proximitat_order.index(prof_nivell) != 0:
                        continue
                elif filter_mode == "nivells_propers":
                    # Legacy
                    prof_nivell = get_professor_main_level(core.horari_gestor, core.dia_actual, nom, hora)
                    # NOMÉS professors de nivells propers (NO mateix nivell)
                    if prof_nivell not in proximitat_order or proximitat_order.index(prof_nivell) == 0:
                        continue
                # filter_mode == "tots": no filtrem

                # Verificar si és titular
                es_titular = core.es_titular_per_assignatura(nom, tipus, grups, aula)

                # Scoring de prioritat
                priority_score = 0

                # 1. Bonus titular (màxima prioritat)
                if es_titular:
                    priority_score += 1000

                # 2. Prioritat basada en categoria
                category_score = 800 - (categoria * 100)
                priority_score += category_score

                # 3. Pes dins categoria
                pes = PRIORITATS.get(tipus_disp, 1)
                weight_score = pes * 10
                priority_score += weight_score

                # 4. Proximitat de nivell/afinitat
                if filter_mode in ("afinitat_exacta", "afinitat_propera") and prox_idx is not None:
                    priority_score += 50 - (prox_idx * 10)
                elif filter_mode in ("mateix_nivell", "nivells_propers"):
                    prof_nivell = get_professor_main_level(core.horari_gestor, core.dia_actual, nom, hora)
                    if prof_nivell in proximitat_order:
                        idx = proximitat_order.index(prof_nivell)
                        priority_score += 50 - (idx * 10)
                    elif prof_nivell == "Unknown":
                        priority_score += 25

                candidats.append((nom, tipus_disp, detall, priority_score))

        # Ordenar i assignar millor candidat
        if candidats:
            candidats.sort(key=lambda x: x[3], reverse=True)

            max_score = candidats[0][3]
            millors = [c for c in candidats if c[3] == max_score]

            if len(millors) > 1:
                # Selecció aleatòria amb pesos
                millors_sense_score = [(c[0], c[1], c[2]) for c in millors]
                best_candidate = escollir_aleatoriament_amb_pesos(millors_sense_score)
            else:
                best_candidate = millors[0]

            # Fail-safe final abans d'escriure l'assignació
            if not core.is_professor_assignable(best_candidate[0], hora, best_candidate[1]):
                continue

            vigilance['vigilant'] = best_candidate[0]
            vigilants_hora.add(best_candidate[0])
            vigilants_assignats_global[hora] = vigilants_hora
            assigned_count += 1

    return assigned_count
