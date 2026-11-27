"""Horari vigent i memòria cau per centre; resolució de l’XML per data."""

import logging
import os
from bisect import bisect_right
from collections.abc import Callable
from contextlib import nullcontext
from datetime import date, timedelta

from sqlalchemy.orm import Session

import rellotge
from absencia_coberta.domain import absents_coberts, sense_absents_coberts, vista_per_data
from config.context import institucio_peticio
from configuracio.repositories import ConfiguracioRepository
from database import get_data_db_session, get_data_dir_for_institucio
from errors_domini import MissingXmlError, NoValid
from horari.lector import GestorHorariWeb  # Versió web que llegeix de SQLite
from horari.repositories import XMLVersionRepository
from models import XMLVersion

log = logging.getLogger(__name__)


# ===== Memòria cau per institució =====
# Només l'horari (llegir i processar l'XML és costós). Els gestors d'alliberats,
# absències i substitucions es creen a cada petició (get_gestors): cada petició
# hi fixa la seva data i els seus vigilants, i compartits entre peticions es
# podrien trepitjar.
_horari: dict[str, GestorHorariWeb] = {}


class _SenseValor:
    pass


_SENSE_VALOR = _SenseValor()


def _cache_key(institucio: str, xml_path: str) -> str:
    return f"{institucio}:{xml_path}"


def _get_institucio_actual() -> str:
    """Centre de la petició; els scripts l'han de passar explícitament."""

    institucio = institucio_peticio()
    if not institucio:
        raise NoValid("Cal indicar el centre per accedir a l'horari", codi="centre_obligatori")
    return institucio


def invalidar_horari(institucio: str | None = None) -> None:
    """Invalida el singleton de l'horari per forçar recàrrega"""
    global _horari
    if institucio:
        prefix = f"{institucio}:"
        for cache in (_horari,):
            for key in list(cache.keys()):
                if key.startswith(prefix):
                    cache.pop(key, None)
    else:
        _horari = {}
    log.debug("🔄 Singleton d'horari invalidat - es recarregarà en proper ús")


def avui() -> date:
    """La data d'avui. L'horari sempre es demana per a una data."""
    return rellotge.avui()


def _resolve_xml_path(
    institucio: str, data: date, *, versio: XMLVersion | None | _SenseValor = _SENSE_VALOR, db: Session | None = None
) -> str | None:
    if not data:
        # Sense data no se sap quin horari: abans s'agafava un per defecte en
        # silenci i l'error passava desapercebut
        raise ValueError("Cal la data per saber quin horari (XML) fer servir")
    xml_path = None
    # Només l'absència de dades activa les alternatives. Els errors de BD
    # es propaguen: no s'ha de treballar amb un altre XML en silenci.
    if isinstance(versio, _SenseValor):
        with nullcontext(db) if db is not None else get_data_db_session(institucio, lectura=True) as sessio:
            versio = XMLVersionRepository.vigent(sessio, data)
    if versio:
        xml_path = versio.path

    if not xml_path:
        with nullcontext(db) if db is not None else get_data_db_session(institucio, lectura=True) as sessio:
            xml_path = ConfiguracioRepository.get(sessio, "xml_horari_path")

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


def get_horari(
    institucio: str | None = None, *, data_iso: date, xml_path: str | None | _SenseValor = _SENSE_VALOR
) -> GestorHorariWeb:
    """L'horari vigent el dia demanat (de memòria cau). Sense institució, la de la petició en curs."""
    global _horari
    institucio = institucio or _get_institucio_actual()
    if isinstance(xml_path, _SenseValor):
        xml_path = _resolve_xml_path(institucio, data_iso)
    if not xml_path or not os.path.exists(xml_path):
        raise MissingXmlError(institucio, xml_path)
    key = _cache_key(institucio, xml_path or "none")
    if key in _horari:
        return _del_dia(_horari[key], institucio, data_iso)

    # Llegir configuració de SQLite
    with get_data_db_session(institucio, lectura=True) as db:
        ultim_professor_subs = ConfiguracioRepository.get(db, "ultim_professor_subs")
        if not ultim_professor_subs:
            ultim_professor_subs = None  # Sense límit

    # Obtenir path XML (SQLite per institució)
    horari = GestorHorariWeb(xml_path, ultim_professor_subs, institucio)
    _horari[key] = horari

    log.debug(
        f"✅ Horari carregat ({institucio}): {len(horari.professors)} professors (límit: {ultim_professor_subs or 'cap'})"
    )
    return _del_dia(horari, institucio, data_iso)


def _del_dia(horari: GestorHorariWeb, institucio: str, data: date) -> GestorHorariWeb:
    """L'horari tal com és aquell dia: sense els professors amb una absència
    coberta (el punt únic de la regla; absencia_coberta.domain)."""

    with get_data_db_session(institucio, lectura=True) as db:
        return sense_absents_coberts(horari, absents_coberts(db, data))


def horaris_per_dates(db: Session) -> Callable[[date], GestorHorariWeb]:
    """Lector d'horaris per a una operació d'interval. Reutilitza l'XML
    entre canvis de versió, però aplica les absències cobertes de cada dia.
    També respecta els forats i el fallback a la versió més propera."""

    institucio = db.info.get("institucio")
    versions = XMLVersionRepository.list_all(db)
    limits = sorted(
        {
            d
            for v in versions
            for d in (v.data_inici, v.data_fi + timedelta(days=1) if v.data_fi else None)
            if d is not None
        }
    )
    vista = vista_per_data(db)
    horaris: dict[int, GestorHorariWeb | MissingXmlError] = {}

    def horari_de(data: date) -> GestorHorariWeb:
        tram = bisect_right(limits, data)
        if tram not in horaris:
            try:
                horari = get_horari(institucio, data_iso=data)
                horaris[tram] = getattr(horari, "sencer", horari)
            except MissingXmlError as error:
                horaris[tram] = error
        resultat = horaris[tram]
        if isinstance(resultat, MissingXmlError):
            raise resultat
        return vista(resultat, data)

    return horari_de
