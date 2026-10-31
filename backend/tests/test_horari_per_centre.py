"""
Cada centre veu els seus grups amagats i les seves abreviatures: l'horari
(GestorHorariWeb) els llegeix de la BD del centre de la petició, no del
centre per defecte del servidor. Abans, un segon centre els veia a
Configuració però la pantalla de grups i la de Substitucions no els feien
servir.
"""

import uuid

from fastapi import Depends
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio

from auth.dependencies import get_current_user, require_admin
from database import get_data_db_session
from grups.router import router as grups_router
from models import AbreviaturaGrup, GrupAmagat
from rate_limit import limiter

APP = crea_app()
APP.include_router(grups_router, dependencies=[Depends(get_current_user)])
DATA = "2026-04-20"  # dilluns


def _centre(amagat: str, originals: str, abreviatura: str):
    centre = nova_institucio(amb_xml=True)
    with get_data_db_session(centre) as db:
        db.add(GrupAmagat(grup=amagat))
        db.add(AbreviaturaGrup(grups_originals=originals, abreviatura=abreviatura))
        db.commit()
    usuari = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(usuari, centre, "admin")
    return entra(client_per(APP), usuari)


def _grups(client) -> list:
    resposta = client.get(f"/api/grups/{DATA}")
    assert resposta.status_code == 200, resposta.text
    return resposta.json()["grups_disponibles"]


def test_cada_centre_veu_nomes_els_seus_grups_amagats_i_abreviatures():
    limiter.reset()
    a = _centre("1-ESO-A", "2-ESO-A,2-ESO-B,2-ESO-C", "2-ESO-TOTS")
    b = _centre("3-ESO-A", "4-ESO-A,4-ESO-B,4-ESO-C", "4-ESO-TOTS")

    grups_a, grups_b = _grups(a), _grups(b)

    assert "1-ESO-A" not in grups_a and "2-ESO-TOTS" in grups_a and "2-ESO-A,2-ESO-B,2-ESO-C" not in grups_a
    assert "3-ESO-A" in grups_a and "4-ESO-A,4-ESO-B,4-ESO-C" in grups_a and "4-ESO-TOTS" not in grups_a
    assert "3-ESO-A" not in grups_b and "4-ESO-TOTS" in grups_b and "4-ESO-A,4-ESO-B,4-ESO-C" not in grups_b
    assert "1-ESO-A" in grups_b and "2-ESO-A,2-ESO-B,2-ESO-C" in grups_b and "2-ESO-TOTS" not in grups_b
    # Una segona petició (l'horari ja és a la memòria cau) no barreja els centres
    assert _grups(a) == grups_a and _grups(b) == grups_b


def test_les_abreviatures_del_planificador_son_les_del_centre_de_la_peticio():
    # utils/grups_utils (l'informe de professors per franja del planificador)
    # agafava les abreviatures del centre per defecte del servidor
    from config.context import fixa_institucio_peticio
    from utils.grups_utils import aplicar_abreviatura_grup

    centres = []
    for abreviatura in ("1-ESO-X", "1-ESO-Y"):
        centre = nova_institucio()
        with get_data_db_session(centre) as db:
            db.add(AbreviaturaGrup(grups_originals="1-ESO-A,1-ESO-B", abreviatura=abreviatura))
            db.commit()
        centres.append(centre)

    vistes = []
    for centre in centres:
        fixa_institucio_peticio(centre)  # com fa get_current_user a cada petició
        try:
            vistes.append(aplicar_abreviatura_grup("1-ESO-A"))
        finally:
            fixa_institucio_peticio(None)
    assert vistes == ["1-ESO-X", "1-ESO-Y"]


def test_canviar_les_abreviatures_buida_la_memoria_cau_del_planificador_del_centre():
    # Abans, la memòria cau del planificador només es buidava en canviar el
    # centre per defecte: després d'editar una abreviatura, l'informe feia
    # servir l'antiga fins que es reiniciava el servidor
    from config.context import fixa_institucio_peticio
    from routes import config_examens
    from utils import grups_utils

    app = crea_app()
    app.include_router(config_examens.router, dependencies=[Depends(require_admin)])
    limiter.reset()
    centre, altre = nova_institucio(), nova_institucio()
    usuari = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(usuari, centre, "admin")
    client = entra(client_per(app), usuari)

    def abreviatura_de(institucio):
        fixa_institucio_peticio(institucio)  # com fa get_current_user a cada petició
        try:
            return grups_utils.aplicar_abreviatura_grup("1-ESO-A")
        finally:
            fixa_institucio_peticio(None)

    creada = client.post(
        "/api/config/abreviatures", json={"grups_originals": "1-ESO-A,1-ESO-B", "abreviatura": "1-ESO-X"}
    )
    assert abreviatura_de(centre) == "1-ESO-X" and abreviatura_de(altre) == "1-ESO-A"

    client.put(
        f"/api/config/abreviatures/{creada.json()['id']}",
        json={"grups_originals": "1-ESO-A,1-ESO-B", "abreviatura": "1-ESO-Y"},
    )
    assert abreviatura_de(centre) == "1-ESO-Y"
    assert altre in grups_utils._abreviatures_cache  # la de l'altre centre es manté

    client.delete(f"/api/config/abreviatures/{creada.json()['id']}")
    assert abreviatura_de(centre) == "1-ESO-A"
