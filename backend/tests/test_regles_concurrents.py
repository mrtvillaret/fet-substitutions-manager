"""Dues sessions reals: la segona escriptura ha de rellegir la regla entre files."""

from datetime import date
from threading import Event, Thread, current_thread

import pytest
from sqlalchemy import event
from suport_api import nova_institucio

from auth.domain import UsuariActual
from config.context import fixa_institucio_peticio
from database import AUTH_ENGINE, AuthSessionLocal, create_auth_tables, get_data_db_session, get_engine_for_institucio
from errors_domini import ErrorDeDomini
from horari.domain import Dia
from models import Substitucio, User
from substitucions import services as substitucions
from substitucions.repositories import SubstitucioRepository
from substitucions.schemas import SubstitucioUpdate
from usuaris import services as usuaris

DATA = "2026-04-20"


def _dues_escriptures(engine, monkeypatch, propietari, metode, operacio):
    """Atura la primera després de validar. En el codi antic, la segona
    completa el canvi abans que continuï la primera. Amb BEGIN IMMEDIATE,
    la segona allibera la primera abans d'esperar el bloqueig de SQLite.
    Cap sondeig temporal ni sleep decideix l'ordre de les lectures.
    """
    preparada, continua = Event(), Event()
    resultats = {}
    original = getattr(propietari, metode)

    def pausa(*args, **kwargs):
        resultat = original(*args, **kwargs)
        if current_thread().name == "primer" and not preparada.is_set():
            preparada.set()
            assert continua.wait(10), "la primera no ha estat alliberada"
        return resultat

    # En substitucions cal pausar abans d'UPDATE (després de totes les lectures).
    if propietari is SubstitucioRepository:

        def pausa(*args, **kwargs):
            if current_thread().name == "primer" and not preparada.is_set():
                preparada.set()
                assert continua.wait(10), "la primera no ha estat alliberada"
            return original(*args, **kwargs)

    monkeypatch.setattr(propietari, metode, pausa)

    def abans_sql(conn, cursor, statement, parameters, context, executemany):
        if current_thread().name == "segon" and statement == "BEGIN IMMEDIATE":
            continua.set()

    def executa(index):
        try:
            operacio(index)
            resultats[index] = "ok"
        except ErrorDeDomini as error:
            resultats[index] = error.codi
        except Exception as error:
            resultats[index] = error
        finally:
            if index == 1:
                continua.set()

    event.listen(engine, "before_cursor_execute", abans_sql)
    primer = Thread(target=executa, args=(0,), name="primer")
    segon = Thread(target=executa, args=(1,), name="segon")
    try:
        primer.start()
        assert preparada.wait(10), "la primera no ha arribat a la comprovació"
        segon.start()
        segon.join(10)
        primer.join(10)
    finally:
        continua.set()
        primer.join(10)
        if segon.ident is not None:
            segon.join(10)
        event.remove(engine, "before_cursor_execute", abans_sql)
    assert not primer.is_alive() and not segon.is_alive()
    return resultats


def test_un_substitut_no_es_pot_assignar_a_dues_files_simultanies(monkeypatch):
    centre = nova_institucio(amb_xml=True)
    with get_data_db_session(centre) as db:
        db.add_all(
            [
                Substitucio(data=date.fromisoformat(DATA), hora="10:00", professor_absent=p, tipus_absencia="ABSENCIA")
                for p in ("Prof 15", "Prof 16")
            ]
        )
        db.commit()

    def operacio(index):
        token = fixa_institucio_peticio(centre)
        try:
            with get_data_db_session(centre) as db:
                substitucions.actualitza_substitut(
                    db,
                    Dia.de_text(DATA, centre),
                    DATA,
                    "10:00",
                    ("Prof 15", "Prof 16")[index],
                    SubstitucioUpdate(substitut="Prof 21", force=True),
                )
        finally:
            from config.context import _institucio

            _institucio.reset(token)

    resultat = _dues_escriptures(
        get_engine_for_institucio(centre), monkeypatch, SubstitucioRepository, "update", operacio
    )
    assert sorted(resultat.values()) == ["ok", "substitut_repetit"], resultat
    with get_data_db_session(centre) as db:
        assert sum(s["substitut"] == "Prof 21" for s in SubstitucioRepository.get_by_date(db, DATA)) == 1


@pytest.mark.parametrize("accio", ["desactivar", "esborrar", "treure_rol", "canviar_centre"])
def test_dues_operacions_no_deixen_el_centre_sense_admin(monkeypatch, accio):
    centre, altre = nova_institucio(), nova_institucio()
    create_auth_tables()
    with AuthSessionLocal() as db:
        admins = [
            User(
                username=f"admin_{centre}_{i}",
                password_hash="hash-de-prova",
                institucio=centre,
                role="admin",
                active=True,
            )
            for i in range(2)
        ]
        db.add_all(admins)
        db.commit()
        ids = [u.id for u in admins]
    actor = UsuariActual(id=0, username="superadmin_prova", institucio=centre, role="super_admin", versio_sessio=0)

    def operacio(index):
        with AuthSessionLocal() as db:
            match accio:
                case "desactivar":
                    usuaris.desactiva_usuari(db, actor, ids[index])
                case "esborrar":
                    usuaris.elimina_usuari(db, actor, ids[index])
                case "treure_rol":
                    usuaris.edita_usuari(db, actor, ids[index], {"role": "user"})
                case "canviar_centre":
                    usuaris.edita_usuari(db, actor, ids[index], {"institucio": altre})

    resultat = _dues_escriptures(
        AUTH_ENGINE, monkeypatch, usuaris, "_comprova_que_el_centre_conserva_un_admin", operacio
    )
    assert sorted(resultat.values()) == ["centre_sense_admin", "ok"], resultat
    with AuthSessionLocal() as db:
        assert db.query(User).filter_by(institucio=centre, role="admin", active=True).count() == 1
