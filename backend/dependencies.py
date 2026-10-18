"""
Dependències compartides de les rutes: la BD de dades de l'usuari i el dia
(amb l'horari que hi correspon) segons cada regla:

- dia_de_la_peticio: la data de la petició (a l'adreça, /{data}, o ?data=), obligatòria.
- dia_del_calendari: ?data= opcional (la data del calendari de la pantalla); sense, avui.
- dia_de_la_planificacio: la primera data planificada (sense dates, avui).
- dia_d_avui: avui (p. ex. qui és actiu o inactiu).
"""
from typing import Optional

from fastapi import Depends

from auth_utils import get_current_user
from database import get_data_db
from routes.parametres import DataISO
from serveis.dia import Dia


def get_db(current_user=Depends(get_current_user)):
    yield from get_data_db(current_user.institucio)


def dia_de_la_peticio(data: DataISO, current_user=Depends(get_current_user)) -> Dia:
    return Dia.de_text(data, current_user.institucio)


def dia_del_calendari(data: Optional[DataISO] = None, current_user=Depends(get_current_user)) -> Dia:
    return Dia.de_text(data, current_user.institucio) if data else Dia.avui(current_user.institucio)


def dia_de_la_planificacio(current_user=Depends(get_current_user)) -> Dia:
    from routes.scheduler_config import data_referencia
    return Dia.de_text(data_referencia(current_user.institucio), current_user.institucio)


def dia_d_avui(current_user=Depends(get_current_user)) -> Dia:
    return Dia.avui(current_user.institucio)
