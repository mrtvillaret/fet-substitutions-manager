"""El repositori de substitucions deixa la transacció en mans del servei."""

from sqlalchemy.orm import sessionmaker

from substitucions.repositories import SubstitucioRepository

DATA = "2026-04-20"


def _fila(professor="Prof de prova"):
    return {
        "data": DATA,
        "hora": "10:00",
        "professor_absent": professor,
        "assignatura": "Activitat de prova",
        "grup": "Grup de prova",
        "tipus_absencia": "ABSENCIA",
    }


def test_crear_i_rollback_no_deixa_res_desat(db_session):
    creada = SubstitucioRepository.create(db_session, _fila())
    assert creada.id is not None

    db_session.rollback()

    assert SubstitucioRepository.get_by_date(db_session, DATA) == []


def test_actualitzar_i_rollback_conserva_el_valor_anterior(db_session):
    creada = SubstitucioRepository.create(db_session, _fila())
    db_session.commit()

    SubstitucioRepository.update(db_session, creada.id, {"substitut": "Substitut de prova"})
    db_session.rollback()

    assert SubstitucioRepository.get_by_date(db_session, DATA)[0]["substitut"] == ""


def test_esborrar_i_rollback_conserva_la_fila(db_session):
    creada = SubstitucioRepository.create(db_session, _fila())
    db_session.commit()

    assert SubstitucioRepository.delete(db_session, creada.id) is True
    db_session.rollback()

    assert len(SubstitucioRepository.get_by_date(db_session, DATA)) == 1


def test_una_altra_sessio_no_veu_els_canvis_sense_commit(db_session):
    creada = SubstitucioRepository.create(db_session, _fila())

    Sessio = sessionmaker(autocommit=False, autoflush=False, bind=db_session.bind)
    with Sessio() as altra:
        assert SubstitucioRepository.get_by_date(altra, DATA) == []

    db_session.rollback()
    assert creada.id is not None
