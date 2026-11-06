"""Professors actius segons l'XML d'avui, fora de les lectures de l'horari."""

from pathlib import Path
from threading import Lock

import rellotge
from configuracio.repositories import ConfiguracioRepository
from database import get_data_db_session
from horari.context import _resolve_xml_path
from horari.lector import GestorHorariWeb
from horari.repositories import ProfessorRepository

_ultim_dia = {}
_lock = Lock()


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

    La marca només avança després del commit; qualsevol error es propaga i
    permet reintentar-ho. El bloqueig evita duplicar la feina entre fils.
    """
    with _lock:
        data = rellotge.avui()
        if _ultim_dia.get(institucio) == data:
            return
        with get_data_db_session(institucio) as db:
            sincronitza_professors(db, institucio)
            db.commit()
        _ultim_dia[institucio] = data
