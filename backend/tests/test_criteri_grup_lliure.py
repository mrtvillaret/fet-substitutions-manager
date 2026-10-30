"""
Les validacions (assignar un substitut a mà, avisos abans del PDF i
«Reassignar problemàtics») decideixen si un professor té classe amb el mateix
criteri que la generació automàtica (core/alliberats.sense_classe): el grup de
la seva classe ha de ser, tal com surt a l'horari, un dels grups marcats sense
classe; per a vigilàncies, també un dels grups que fan examen.

Dilluns 20/04/2026 a les 10:00, Prof 26 fa classe a l'agrupació
«2-BAT-A,2-BAT-B». Marcar només «2-BAT-A» no l'allibera: hi queden els
alumnes de 2-BAT-B.
"""

import uuid

import pytest
from suport_api import (
    XML_EXEMPLE,
    client_per,
    crea_app,
    crea_usuari,
    entra,
    nova_institucio,
)

from database import get_data_db_session
from horari_web import GestorHorariWeb
from pdf import router as pdf
from rate_limit import limiter
from repositories import GrupsAlliberatsRepository
from substitucions import router as substitucions
from substitucions.repositories import SubstitucioRepository
from vigilancies.repositories import VigilanciaRepository
from vigilancies.router import router as vigilancies_router

APP = crea_app(vigilancies_router, substitucions.router, pdf.router)
DATA = "2026-04-20"  # dilluns
HORA = "10:00"
PROFESSOR = "Prof 26"
AGRUPACIO = "2-BAT-A,2-BAT-B"
CLASSE_PROF_26 = f"Substitut {PROFESSOR} té classe"
VIGILANT_PROF_26 = f"Vigilant {PROFESSOR} té classe"


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


@pytest.fixture
def centre():
    return nova_institucio(amb_xml=True)


@pytest.fixture
def client(centre):
    nom = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, centre, "admin")
    return entra(client_per(APP), nom)


def _sense_classe(centre, grups):
    with get_data_db_session(centre) as db:
        GrupsAlliberatsRepository.set_for_date(db, DATA, {HORA: grups})
        db.commit()


def _examen(centre, grups, vigilant=""):
    # Directament a la BD: l'API crearia la cobertura de la classe del vigilant.
    with get_data_db_session(centre) as db:
        VigilanciaRepository.create(
            db,
            DATA,
            {
                "hora": HORA,
                "tipus": "examen",
                "grups": grups,
                "aula": "A1",
                "vigilant": vigilant,
                "nivell": "2-BAT",
            },
        )
        db.commit()


def _prof_26_substitut(client, centre):
    # Directament a la BD, com si l'horari o els grups haguessin canviat després.
    resp = client.put(
        f"/api/substitucions/{DATA}/absencies/Prof 15", json={"hores_absencia": [HORA], "updated_at_map": {}}
    )
    assert resp.status_code == 200, resp.text
    with get_data_db_session(centre) as db:
        fila = next(f for f in SubstitucioRepository.get_by_date(db, DATA) if f["hora"] == HORA)
        SubstitucioRepository.update(db, int(fila["id"]), {"substitut": PROFESSOR})
        db.commit()


def _avisos(client):
    resp = client.get(f"/api/pdf/{DATA}/validacions")
    assert resp.status_code == 200, resp.text
    return " | ".join(resp.json()["warnings"])


def test_prof_26_fa_classe_a_l_agrupacio():
    horari = GestorHorariWeb(str(XML_EXEMPLE))
    assert horari.get_activitat("Dilluns", HORA, PROFESSOR)["grup"] == AGRUPACIO


# ------------------------------------------------------------ substitucions


@pytest.mark.parametrize(
    "marcats, problematic",
    [
        ([], True),
        (["2-BAT-A"], True),  # només una part de l'agrupació
        (["2-BAT-A", "2-BAT-B"], True),  # tots dos per separat: cal marcar l'agrupació
        ([AGRUPACIO], False),
    ],
)
def test_substitut_amb_classe_a_una_agrupacio(client, centre, marcats, problematic):
    _sense_classe(centre, marcats)
    _prof_26_substitut(client, centre)

    assert (CLASSE_PROF_26 in _avisos(client)) == problematic
    resp = client.post(f"/api/substitucions/{DATA}/reassign-problematics")
    assert resp.status_code == 200, resp.text
    assert resp.json()["cleared"] == (1 if problematic else 0)


@pytest.mark.parametrize(
    "marcats, acceptat",
    [
        (["2-BAT-A"], False),
        ([AGRUPACIO], True),
    ],
)
def test_assignar_a_ma_un_substitut_amb_classe_a_una_agrupacio(client, centre, marcats, acceptat):
    _sense_classe(centre, marcats)
    resp = client.put(
        f"/api/substitucions/{DATA}/absencies/Prof 15", json={"hores_absencia": [HORA], "updated_at_map": {}}
    )
    assert resp.status_code == 200, resp.text
    fila = next(
        s
        for s in client.get(f"/api/substitucions/{DATA}", params={"include_all": True}).json()
        if s["hora"] == HORA and s["professor_absent"] == "Prof 15"
    )
    resp = client.put(
        f"/api/substitucions/{DATA}/{HORA}/Prof 15", json={"substitut": PROFESSOR, "updated_at": fila["updated_at"]}
    )
    assert (resp.status_code == 200) == acceptat, resp.text


def test_l_examen_de_l_agrupacio_no_allibera_el_substitut(client, centre):
    _examen(centre, AGRUPACIO, vigilant="Prof 21")
    _prof_26_substitut(client, centre)

    assert CLASSE_PROF_26 in _avisos(client)
    assert client.post(f"/api/substitucions/{DATA}/reassign-problematics").json()["cleared"] == 1


# ------------------------------------------------------------- vigilàncies


@pytest.mark.parametrize(
    "examen, marcats, problematic",
    [
        ("2-BAT-A", [], True),  # l'examen és només d'una part de l'agrupació
        (AGRUPACIO, [], False),  # l'examen és de tota l'agrupació
        ("1-ESO-A", ["2-BAT-A"], True),
        ("1-ESO-A", [AGRUPACIO], False),  # l'agrupació està sense classe
    ],
)
def test_vigilant_amb_classe_a_una_agrupacio(client, centre, examen, marcats, problematic):
    _sense_classe(centre, marcats)
    _examen(centre, examen, vigilant=PROFESSOR)

    assert (VIGILANT_PROF_26 in _avisos(client)) == problematic
