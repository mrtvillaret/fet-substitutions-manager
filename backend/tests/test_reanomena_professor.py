"""
Reanomenar (anonimitzar) un professor inactiu (POST /api/dades/professors/reanomena):
el nom canvia a totes les taules on surt i la resposta diu quantes files de
cadascuna. Només admins i només professors que ja no són a l'XML.
"""

import uuid
from datetime import date

import pytest
from fastapi import Depends
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio

from auth.dependencies import require_admin
from dades import router as dades
from database import get_data_db_session
from models import Professor, Substitucio, Vigilancia
from rate_limit import limiter

APP = crea_app()
APP.include_router(dades.router, dependencies=[Depends(require_admin)])  # com a main.py
URL = "/api/dades/professors/reanomena"
DIA = date(2026, 3, 2)


@pytest.fixture
def centre():
    limiter.reset()
    centre = nova_institucio()
    with get_data_db_session(centre) as db:
        db.add_all(
            [
                Professor(nom="Prof Antic", actiu=False),
                Professor(nom="Prof Actiu", actiu=True),
                Substitucio(data=DIA, hora="08:00", professor_absent="Prof Antic", substitut="Prof Actiu"),
                Substitucio(data=DIA, hora="09:00", professor_absent="Prof Actiu", substitut="Prof Antic"),
                Substitucio(data=DIA, hora="10:00", professor_absent="Prof Actiu", substitut="Prof Antic"),
                Vigilancia(
                    data=DIA,
                    hora="08:00",
                    tipus="Examen",
                    grups="1-ESO-A",
                    aula="A1",
                    nivell="1-ESO",
                    vigilant="Prof Antic",
                ),
            ]
        )
        db.commit()
    return centre


def _client(centre, rol="admin"):
    nom = f"{rol}_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, centre, rol)
    return entra(client_per(APP), nom)


def test_el_nom_canvia_a_totes_les_taules(centre):
    resposta = _client(centre).post(URL, json={"nom_actual": " Prof Antic ", "nom_nou": "Anònim 1"})

    assert resposta.json() == {
        "ok": True,
        "counts": {
            "substitucions_absent": 1,
            "substitucions_substitut": 2,
            "vigilancies": 1,
            "baixes": 0,
            "costos_examens": 0,
            "professor": 1,
        },
        "total": 5,
    }
    with get_data_db_session(centre) as db:
        assert {p.nom for p in db.query(Professor)} == {"Anònim 1", "Prof Actiu"}
        assert sorted((s.professor_absent, s.substitut) for s in db.query(Substitucio)) == [
            ("Anònim 1", "Prof Actiu"),
            ("Prof Actiu", "Anònim 1"),
            ("Prof Actiu", "Anònim 1"),
        ]
        assert [v.vigilant for v in db.query(Vigilancia)] == ["Anònim 1"]


@pytest.mark.parametrize(
    "cos, missatge",
    [
        ({"nom_actual": "Prof Actiu", "nom_nou": "X"}, "Només es poden reanomenar professors inactius"),
        ({"nom_actual": "Prof Antic", "nom_nou": "Prof Actiu"}, "Ja existeix un professor amb el nom «Prof Actiu»."),
        ({"nom_actual": "No hi és", "nom_nou": "X"}, "No existeix cap professor amb el nom «No hi és»."),
        ({"nom_actual": "Prof Antic", "nom_nou": " "}, "Cal indicar el nom actual i el nom nou."),
    ],
)
def test_els_casos_no_valids_donen_400_i_no_canvien_res(centre, cos, missatge):
    resposta = _client(centre).post(URL, json=cos)

    assert resposta.status_code == 400
    assert resposta.json()["detail"].startswith(missatge)
    with get_data_db_session(centre) as db:
        assert {p.nom for p in db.query(Professor)} == {"Prof Antic", "Prof Actiu"}


def test_un_usuari_no_admin_no_pot_reanomenar(centre):
    resposta = _client(centre, "user").post(URL, json={"nom_actual": "Prof Antic", "nom_nou": "X"})
    assert resposta.status_code == 403
