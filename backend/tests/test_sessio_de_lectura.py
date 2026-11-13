"""
La sessió de només lectura (`dependencies.get_db_lectura`): la fan servir les
rutes POST que només llegeixen, perquè no reservin l'escriptura de SQLite
(`BEGIN IMMEDIATE`) i no facin esperar qui desa.

Guardians:
- La sessió no pot escriure: ni per l'ORM ni amb SQL directe (SQLite ho
  rebutja), ni passar a escriptura amb `inicia_escriptura`.
- La connexió següent del mateix centre torna a poder escriure.
- Amb una altra connexió que té reservada l'escriptura, la ruta respon igual.
Que les rutes marcades no canvien res de la BD ni dels fitxers ho comprova
l'inventari de `test_seguretat.py` (`test_les_rutes_de_lectura_no_escriuen`).
"""

import sqlite3
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio
from suport_noms import unic

from database import DATA_BASE_DIR, get_data_db_session, inicia_escriptura
from models import Substitucio
from rate_limit import limiter
from substitucions import router as substitucions

APP = crea_app(substitucions.router)
DATA = "2026-04-20"  # dilluns


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


@pytest.fixture
def centre():
    return nova_institucio(amb_xml=True)


def _files(centre):
    con = sqlite3.connect(f"file:{DATA_BASE_DIR / centre / 'gestor.db'}?mode=ro", uri=True)
    try:
        return con.execute("SELECT count(*) FROM substitucions").fetchone()[0]
    finally:
        con.close()


def test_una_sessio_de_lectura_no_pot_escriure_per_l_orm(centre):
    with get_data_db_session(centre, nomes_lectura=True) as db:
        assert db.query(Substitucio).count() == 0  # llegir sí
        db.add(Substitucio(data=date(2026, 4, 20), hora="10:00", professor_absent="Prof 1"))
        with pytest.raises(OperationalError, match="readonly"):
            db.flush()
    assert _files(centre) == 0


def test_una_sessio_de_lectura_no_pot_escriure_amb_sql(centre):
    with get_data_db_session(centre, nomes_lectura=True) as db:
        with pytest.raises(OperationalError, match="readonly"):
            db.execute(
                text(
                    "INSERT INTO substitucions (data, hora, professor_absent) VALUES ('2026-04-20', '10:00', 'Prof 1')"
                )
            )
    assert _files(centre) == 0


def test_una_sessio_de_lectura_no_pot_passar_a_escriptura(centre):
    with get_data_db_session(centre, nomes_lectura=True) as db:
        with pytest.raises(RuntimeError, match="només lectura"):
            inicia_escriptura(db)


def test_despres_d_una_sessio_de_lectura_es_torna_a_poder_escriure(centre):
    with get_data_db_session(centre, nomes_lectura=True) as db:
        db.query(Substitucio).count()
    with get_data_db_session(centre) as db:
        db.add(Substitucio(data=date(2026, 4, 20), hora="10:00", professor_absent="Prof 1"))
        db.commit()
    assert _files(centre) == 1


def test_la_ruta_de_lectura_no_espera_qui_te_l_escriptura(centre):
    nom = f"user_{unic()}"
    crea_usuari(nom, centre)
    client = entra(client_per(APP), nom)
    url = f"/api/substitucions/{DATA}/disponibles-batch"
    # La primera petició del dia sincronitza els professors (escriu): abans del bloqueig
    esperat = client.post(url, json={"hores": ["10:00"]})
    assert esperat.status_code == 200, esperat.text

    altre = sqlite3.connect(DATA_BASE_DIR / centre / "gestor.db", isolation_level=None, timeout=0)
    try:
        altre.execute("BEGIN IMMEDIATE")  # una altra petició a mig desar
        resp = client.post(url, json={"hores": ["10:00"]})
    finally:
        altre.rollback()
        altre.close()
    assert resp.status_code == 200, resp.text
    assert resp.json() == esperat.json()
