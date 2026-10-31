"""
Funcions auxiliars compartides pel backend
- Gestors singleton (horari, substitucions, etc.)
- Funcions d'assignació automàtica de vigilàncies
"""

import logging
import os
from datetime import date, datetime
from typing import Dict, Optional

from sqlalchemy.orm import Session

from core.absencies import GestorAbsencies
from core.alliberats import GestorAlliberats
from core.vigilancia_core import VigilanciaCore
from database import get_data_db_session, get_data_dir_for_institucio
from grups.repositories import GrupsAlliberatsRepository
from horari.repositories import XMLVersionRepository
from horari_web import GestorHorariWeb  # Versió web que llegeix de SQLite
from repositories import ConfiguracioExamenRepository, ConfiguracioRepository, ProfessorRepository
from substitucions.assignacio import GestorSubstitucions
from substitucions.repositories import SubstitucioRepository
from vigilancies.repositories import VigilanciaRepository

log = logging.getLogger(__name__)


# ===== Memòria cau per institució =====
# Només l'horari (llegir i processar l'XML és costós). Els gestors d'alliberats,
# absències i substitucions es creen a cada petició (get_gestors): cada petició
# hi fixa la seva data i els seus vigilants, i compartits entre peticions es
# podrien trepitjar.
_horari: Dict[str, GestorHorariWeb] = {}
_vigilancia_core: Dict[str, VigilanciaCore] = {}


class MissingXmlError(RuntimeError):
    def __init__(self, institucio: str, xml_path: Optional[str]):
        message = f"Cal pujar un fitxer XML d'horari per a la institució {institucio}."
        super().__init__(message)
        self.institucio = institucio
        self.xml_path = xml_path


def _cache_key(institucio: str, xml_path: str) -> str:
    return f"{institucio}:{xml_path}"


def _get_institucio_actual() -> str:
    """Institució de la petició en curs; fora d'una petició, la per defecte."""
    from config.context import institucio_peticio
    from config.settings import config

    return institucio_peticio() or config.global_data.get("institucio") or os.getenv("APP_INSTITUCIO") or "exemple"


def invalidar_horari(institucio: str = None):
    """Invalida el singleton de l'horari per forçar recàrrega"""
    global _horari, _vigilancia_core
    if institucio:
        prefix = f"{institucio}:"
        for cache in (_horari, _vigilancia_core):
            for key in list(cache.keys()):
                if key.startswith(prefix):
                    cache.pop(key, None)
    else:
        _horari = {}
        _vigilancia_core = {}
    log.debug("🔄 Singleton d'horari invalidat - es recarregarà en proper ús")


def avui() -> str:
    """La data d'avui (AAAA-MM-DD). L'horari sempre es demana per a una data:
    qui vol el d'avui ho ha de dir."""
    return date.today().isoformat()


def _resolve_xml_path(institucio: str, data_iso: str) -> Optional[str]:
    if not data_iso:
        # Sense data no se sap quin horari: abans s'agafava un per defecte en
        # silenci i l'error passava desapercebut
        raise ValueError("Cal la data per saber quin horari (XML) fer servir")
    xml_path = None
    try:
        with get_data_db_session(institucio) as db:
            # La versió vigent aquell dia (si no n'hi ha cap, la més propera)
            version = XMLVersionRepository.vigent(db, data_iso)
            if version:
                xml_path = version.path
    except Exception:
        xml_path = None

    if not xml_path:
        try:
            with get_data_db_session(institucio) as db:
                xml_path = ConfiguracioRepository.get(db, "xml_horari_path")
        except Exception:
            xml_path = None

    if xml_path:
        # La ruta desada a la BD ha de ser dins la carpeta del centre: abans
        # s'hi podia escriure qualsevol ruta des de la configuració.
        data_dir = os.path.realpath(get_data_dir_for_institucio(institucio))
        xml_path = os.path.realpath(os.path.join(data_dir, xml_path))
        if os.path.commonpath([data_dir, xml_path]) != data_dir:
            log.warning("XML fora de la carpeta del centre %s: no es fa servir", institucio)
            xml_path = None

    if not xml_path:
        xml_path = os.getenv("APP_XML_PATH")
        if xml_path and not os.path.isabs(xml_path):
            xml_path = os.path.join(str(get_data_dir_for_institucio(institucio)), xml_path)

    return xml_path


def get_xml_path_for_date(institucio: Optional[str], data_iso: str) -> Optional[str]:
    instit = institucio or _get_institucio_actual()
    return _resolve_xml_path(instit, data_iso)


def get_horari(institucio: str = None, *, data_iso: str) -> GestorHorariWeb:
    """L'horari vigent a `data_iso` (de memòria cau). Sense institució, la de
    la petició en curs."""
    global _horari
    institucio = institucio or _get_institucio_actual()
    xml_path = _resolve_xml_path(institucio, data_iso)
    if not xml_path or not os.path.exists(xml_path):
        raise MissingXmlError(institucio, xml_path)
    key = _cache_key(institucio, xml_path or "none")
    if key in _horari:
        return _del_dia(_horari[key], institucio, data_iso)

    # Llegir configuració de SQLite
    with get_data_db_session(institucio) as db:
        ultim_professor_subs = ConfiguracioRepository.get(db, "ultim_professor_subs")
        if not ultim_professor_subs:
            ultim_professor_subs = None  # Sense límit

    # Obtenir path XML (SQLite per institució)
    horari = GestorHorariWeb(xml_path, ultim_professor_subs, institucio)
    _horari[key] = horari

    # Qui és actiu o inactiu ho decideix l'horari d'avui
    if data_iso == avui():
        try:
            with get_data_db_session(institucio) as db:
                sync_info = ProfessorRepository.sync_from_xml(db, horari.professors)
                log.debug(f"✅ Professors sincronitzats ({institucio}): {sync_info}")
        except Exception as e:
            log.warning(f"⚠️  Error sincronitzant professors ({institucio}): {e}")

    log.debug(
        f"✅ Horari carregat ({institucio}): {len(horari.professors)} professors (límit: {ultim_professor_subs or 'cap'})"
    )
    return _del_dia(horari, institucio, data_iso)


def _del_dia(horari: GestorHorariWeb, institucio: str, data_iso: str) -> GestorHorariWeb:
    """L'horari tal com és aquell dia: sense els professors amb una absència
    coberta (el punt únic de la regla; absencia_coberta.services)."""
    from absencia_coberta.services import absents_coberts, sense_absents_coberts

    with get_data_db_session(institucio) as db:
        return sense_absents_coberts(horari, absents_coberts(db, data_iso))


def get_gestors(institucio: str = None, *, data_iso: str, horari=None):
    """Retorna (substitucions, horari, alliberats, absencies) per a una petició.

    L'horari surt de la memòria cau (get_horari). Els altres tres gestors es
    creen nous a cada crida: són lleugers (només guarden referències a
    l'horari) i cada petició hi fixa el seu estat (data, vigilants, grups sense
    classe), que no s'ha de compartir amb cap altra."""
    institucio = institucio or _get_institucio_actual()
    horari = horari or get_horari(institucio, data_iso=data_iso)
    alliberats = GestorAlliberats(horari)
    absencies = GestorAbsencies(horari)
    substitucions_mgr = GestorSubstitucions(horari, alliberats, absencies)

    return substitucions_mgr, horari, alliberats, absencies


def get_vigilancia_core(data: str, db: Session = None, institucio: str = None) -> VigilanciaCore:
    """Crea i configura VigilanciaCore per una data específica"""
    global _vigilancia_core
    instit = institucio or _get_institucio_actual()

    # Sempre crear nou (per actualitzar amb dades del dia)
    xml_path = _resolve_xml_path(instit, data)
    key = _cache_key(instit, xml_path or "none")
    _vigilancia_core[key] = VigilanciaCore()

    # Obtenir gestors
    _, horari, alliberats, _ = get_gestors(instit, data_iso=data)

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
        log.warning(f"⚠️ No s'han pogut afegir grups d'examen als alliberats: {e}")

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
        dia_actual=dia_name,
    )

    return _vigilancia_core[key]


# ===== Funcions d'Assignació Automàtica =====
