"""
Dependències compartides de les rutes: la BD de dades de l'usuari (get_db;
get_db_lectura per a les POST que només llegeixen) i el dia (amb l'horari que
hi correspon) segons cada regla:

- dia_de_la_peticio: la data de la petició (a l'adreça, /{data}, o ?data=), obligatòria.
- dia_del_calendari: ?data= opcional (la data del calendari de la pantalla); sense, avui.
- dia_de_la_planificacio: la primera data planificada (sense dates, avui).
- dia_d_avui: avui (p. ex. qui és actiu o inactiu).
"""

from fastapi import Depends, Request

from auth.dependencies import get_current_user
from database import get_data_db
from horari.domain import Dia
from parametres import DataISO
from planificador.config import data_referencia


def get_db(request: Request, current_user=Depends(get_current_user)):
    yield from get_data_db(current_user.institucio, lectura=request.method in {"GET", "HEAD", "OPTIONS"})


def get_db_lectura(current_user=Depends(get_current_user)):
    """Per a les rutes POST que només llegeixen (consultes grans al cos de la
    petició): no reserven l'escriptura de SQLite (`BEGIN IMMEDIATE`) i no
    fan esperar qui desa. La sessió no pot escriure: SQLite ho rebutja
    (`database._opcions_de_sessio`; ho vigila `tests/test_sessio_de_lectura.py`)."""
    yield from get_data_db(current_user.institucio, nomes_lectura=True)


def dia_de_la_peticio(data: DataISO, current_user=Depends(get_current_user)) -> Dia:
    return Dia.de_text(data, current_user.institucio)


def dia_del_calendari(data: DataISO | None = None, current_user=Depends(get_current_user)) -> Dia:
    return Dia.de_text(data, current_user.institucio) if data else Dia.avui(current_user.institucio)


def dia_de_la_planificacio(current_user=Depends(get_current_user)) -> Dia:

    return Dia.de_text(data_referencia(current_user.institucio), current_user.institucio)


def dia_d_avui(current_user=Depends(get_current_user)) -> Dia:
    return Dia.avui(current_user.institucio)
