"""Professors actius segons l'XML d'avui, fora de les lectures de l'horari."""

import logging
import time
from pathlib import Path
from threading import Lock

import rellotge
from configuracio.repositories import ConfiguracioRepository
from database import get_data_db_session
from horari.context import _resolve_xml_path
from horari.lector import GestorHorariWeb
from horari.repositories import ProfessorRepository

_ultim_dia = {}
_ultim_error = {}
_lock = Lock()
# Després d'un error, segons fins al reintent: no es rellegeix un XML il·legible
# a cada petició ni s'omple el registre d'avisos.
REINTENT_DESPRES_D_ERROR = 300

log = logging.getLogger(__name__)


def sincronitza_professors(db, institucio: str) -> None:
    """Mateixa sessió i transacció que el canvi de versió; commit del servei.

    Només necessita els professors: no llegeix grups ni abreviatures i no
    obre sessions paral·leles. Manté el límit de professor configurat.
    """
    data = rellotge.avui()
    path = _resolve_xml_path(institucio, data.isoformat(), db=db)
    if not path or not Path(path).exists():
        return  # Centre encara sense horari (la pantalla permet pujar-lo).
    limit = ConfiguracioRepository.get(db, "ultim_professor_subs") or None
    horari = GestorHorariWeb(path, limit)
    ProfessorRepository.sync_from_xml(db, horari.professors, data_sync=data)


def sincronitza_un_cop_al_dia(institucio: str) -> None:
    """La primera petició de cada dia, també amb la memòria cau calenta.

    La marca només avança després del commit. Un error (p. ex. un XML vigent
    il·legible) no fa fallar la petició: queda al registre i es reintenta al cap
    de REINTENT_DESPRES_D_ERROR segons. Així el centre no queda bloquejat i es
    pot pujar un XML nou per arreglar-ho. El bloqueig evita duplicar la feina.
    """
    with _lock:
        data = rellotge.avui()
        if _ultim_dia.get(institucio) == data:
            return
        error = _ultim_error.get(institucio)
        if error is not None and time.monotonic() - error < REINTENT_DESPRES_D_ERROR:
            return
        try:
            with get_data_db_session(institucio) as db:
                sincronitza_professors(db, institucio)
                db.commit()
        except Exception:
            # Les prioritats (més avall) són de la BD: es carreguen igualment.
            _ultim_error[institucio] = time.monotonic()
            log.warning("No s'han pogut sincronitzar els professors de l'XML vigent", exc_info=True)
        else:
            _ultim_error.pop(institucio, None)
            _ultim_dia[institucio] = data
