"""Una versió enviada per la pantalla no pot trepitjar un canvi ja desat.

La reserva d'escriptura impedeix intercalar un altre escriptor entre les
lectures i l'UPDATE: aquesta prova intercala el canvi just abans del BEGIN.
Les curses dins del servei es comproven amb fils a test_regles_concurrents.
"""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from sqlalchemy import event
from suport_api import client_per, crea_app, nova_institucio

from auth.dependencies import get_current_user
from database import get_data_db_session, get_engine_for_institucio
from substitucions.repositories import SubstitucioRepository
from substitucions.router import router as substitucions_router
from vigilancies.repositories import VigilanciaRepository
from vigilancies.router import router as vigilancies_router

DATA = "2026-04-20"


@pytest.fixture
def context():
    centre = nova_institucio(amb_xml=True)
    app = crea_app(substitucions_router, vigilancies_router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(institucio=centre, role="admin", es_admin=True)
    return centre, client_per(app)


def _fila(centre, tipus):
    with get_data_db_session(centre) as db:
        if tipus == "substitucions":
            fila = SubstitucioRepository.create(
                db, {"data": DATA, "hora": "10:00", "professor_absent": "Prof 15", "tipus_absencia": "ABSENCIA"}
            )
        else:
            fila = VigilanciaRepository.create(
                db, DATA, {"hora": "10:00", "tipus": "Examen", "grups": "2-BAT-A", "aula": "A1", "nivell": "2-BAT"}
            )
        db.commit()
        return str(fila.id), fila.updated_at.isoformat()


@contextmanager
def _canvi_abans_del_begin(centre, tipus, fila_id):
    engine = get_engine_for_institucio(centre)
    fet = False

    def intercalada(conn, cursor, statement, parameters, context, executemany):
        nonlocal fet
        if fet or statement != "BEGIN IMMEDIATE":
            return
        fet = True
        with get_data_db_session(centre) as altra:
            canvis = {"comentaris": "primera escriptura"}
            if tipus == "substitucions":
                SubstitucioRepository.update(altra, int(fila_id), canvis)
            else:
                VigilanciaRepository.update_by_id(altra, DATA, fila_id, canvis)
            altra.commit()

    event.listen(engine, "before_cursor_execute", intercalada)
    try:
        yield
        assert fet, "la petició ha de reservar l'escriptura abans de llegir"
    finally:
        event.remove(engine, "before_cursor_execute", intercalada)


@pytest.mark.parametrize("tipus", ["substitucions", "vigilancies"])
@pytest.mark.parametrize("force", [False, True])
def test_actualitzacio_no_trepitja_una_versio_antiga(context, tipus, force):
    centre, client = context
    fila_id, versio = _fila(centre, tipus)
    ruta = (
        f"/api/substitucions/{DATA}/10:00/Prof 15" if tipus == "substitucions" else f"/api/vigilancies/{DATA}/{fila_id}"
    )
    with _canvi_abans_del_begin(centre, tipus, fila_id):
        resp = client.put(ruta, json={"comentaris": "segona escriptura", "updated_at": versio, "force": force})
    assert resp.status_code == (200 if force else 409), resp.text
    with get_data_db_session(centre) as db:
        if tipus == "substitucions":
            actual = SubstitucioRepository.get_by_date(db, DATA)[0]
        else:
            actual = next(iter(VigilanciaRepository.get_by_date(db, DATA).values()))[0]
    assert actual.comentaris == ("segona escriptura" if force else "primera escriptura")
    if not force:
        assert resp.json()["detail"]["error"] == "conflict"
        assert resp.json()["detail"]["current_data"]["comentaris"] == "primera escriptura"


def test_el_mapa_de_versions_d_absencies_tambe_es_atomic(context):
    centre, client = context
    fila_id, versio = _fila(centre, "substitucions")
    with _canvi_abans_del_begin(centre, "substitucions", fila_id):
        resp = client.put(
            f"/api/substitucions/{DATA}/absencies/Prof 15",
            json={"hores_absencia": ["10:00", "11:30"], "updated_at_map": {"10:00": versio}},
        )
    assert resp.status_code == 409, resp.text
    with get_data_db_session(centre) as db:
        files = SubstitucioRepository.get_by_date(db, DATA)
        assert len(files) == 1
        assert files[0].comentaris == "primera escriptura"


@pytest.mark.parametrize("force", [False, True])
def test_esborrar_vigilancia_no_perd_una_edicio_simultania(context, force):
    centre, client = context
    fila_id, versio = _fila(centre, "vigilancies")
    with _canvi_abans_del_begin(centre, "vigilancies", fila_id):
        resp = client.delete(f"/api/vigilancies/{DATA}/{fila_id}", params={"updated_at": versio, "force": force})
    assert resp.status_code == (200 if force else 409), resp.text
    with get_data_db_session(centre) as db:
        actual = VigilanciaRepository.get_by_id(db, DATA, fila_id)
        assert (actual is None) == force
        if actual:
            assert actual.comentaris == "primera escriptura"
