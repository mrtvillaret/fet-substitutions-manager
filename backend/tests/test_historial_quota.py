"""L'historial de la quota: només el curs del dia (també les dates futures del
curs); sense cap curs definit, dos anys enrere. Sempre amb l'índex de la data."""

from datetime import date, timedelta

from sqlalchemy import event

from models import Curs, Substitucio
from substitucions.repositories import HISTORIAL_QUOTA, SubstitucioRepository

DIA = date(2026, 4, 20)  # dilluns


def _fila(db, data, substitut, hora="10:00"):
    db.add(Substitucio(data=data, hora=hora, professor_absent="Prof 1", substitut=substitut, tipus_substitut="G"))


def test_sense_curs_el_limit_es_de_dos_anys():
    assert HISTORIAL_QUOTA == timedelta(days=730)


def test_compta_fins_al_limit_i_les_futures_i_no_el_mateix_dia(db_session):
    limit = DIA - HISTORIAL_QUOTA
    primer_dilluns = limit + timedelta(days=(7 - limit.weekday()) % 7)
    _fila(db_session, primer_dilluns - timedelta(days=7), "Prof antic")  # fora del límit
    _fila(db_session, primer_dilluns, "Prof límit")
    _fila(db_session, DIA - timedelta(days=7), "Prof passat")
    _fila(db_session, DIA, "Prof del dia")
    _fila(db_session, DIA + timedelta(days=7), "Prof futur")
    _fila(db_session, DIA + timedelta(days=1), "Prof dimarts")
    db_session.commit()

    assert SubstitucioRepository.historial_quota(db_session, DIA.isoformat()) == [
        ("10:00", "Prof límit", "G"),
        ("10:00", "Prof passat", "G"),
        ("10:00", "Prof futur", "G"),
    ]


def test_la_consulta_fa_servir_l_index_de_la_data(db_session):
    consultes = []

    def recull(conn, cursor, statement, parameters, context, executemany):
        if "FROM substitucions" in statement:
            consultes.append((statement, parameters))

    event.listen(db_session.bind, "before_cursor_execute", recull)
    try:
        SubstitucioRepository.historial_quota(db_session, DIA.isoformat())
    finally:
        event.remove(db_session.bind, "before_cursor_execute", recull)
    ((statement, parameters),) = consultes
    pla = db_session.connection().exec_driver_sql(f"EXPLAIN QUERY PLAN {statement}", parameters).all()
    # SEARCH: busca per l'interval de l'índex; abans el recorria sencer (SCAN) per ordenar
    assert any(fila[-1].startswith("SEARCH") and "idx_substitucions_data" in fila[-1] for fila in pla), pla


def test_amb_curs_nomes_compta_el_curs_del_dia(db_session):
    db_session.add(Curs(nom="Curs anterior", data_inici=date(2025, 9, 1), data_fi=date(2026, 3, 31)))
    db_session.add(Curs(nom="Curs del dia", data_inici=date(2026, 4, 1), data_fi=date(2026, 6, 30)))
    db_session.add(Curs(nom="Curs següent", data_inici=date(2026, 7, 1), data_fi=None))
    _fila(db_session, date(2026, 3, 30), "Prof curs anterior")  # dilluns, curs anterior
    _fila(db_session, date(2026, 4, 6), "Prof inici")  # dilluns, curs del dia
    _fila(db_session, DIA, "Prof del dia")
    _fila(db_session, DIA + timedelta(days=7), "Prof futur")
    _fila(db_session, date(2026, 7, 6), "Prof curs següent")  # dilluns, curs següent
    db_session.commit()

    assert SubstitucioRepository.historial_quota(db_session, DIA.isoformat()) == [
        ("10:00", "Prof inici", "G"),
        ("10:00", "Prof futur", "G"),
    ]
