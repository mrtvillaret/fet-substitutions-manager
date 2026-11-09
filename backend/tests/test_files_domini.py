"""Contracte de les instantànies de persistència de les files del domini."""

from dataclasses import FrozenInstanceError

import pytest

from substitucions.files import FilaSubstitucio
from substitucions.repositories import SubstitucioRepository


def test_fila_substitucio_es_immutable_i_sense_interficie_de_diccionari():
    fila = FilaSubstitucio()
    assert fila.hora == ""
    assert fila.updated_at is None
    assert not hasattr(fila, "get")
    with pytest.raises(TypeError):
        fila["hora"]
    with pytest.raises(FrozenInstanceError):
        fila.hora = "10:00"


def test_lectura_tipada_conserva_el_contracte_diari(db_session):
    creada = SubstitucioRepository.create(
        db_session, {"data": "2026-11-09", "hora": "10:00", "professor_absent": "Prof test"}
    )
    files = SubstitucioRepository.get_by_date(db_session, "2026-11-09")
    assert files == [
        FilaSubstitucio(
            id=str(creada.id),
            data="2026-11-09",
            hora="10:00",
            professor_absent="Prof test",
            updated_at=creada.updated_at.isoformat(),
        )
    ]


def test_els_recomptes_conserven_null_id_enter_i_timestamps_sql(db_session):
    from recomptes.repositories import RecomptesRepository

    creada = SubstitucioRepository.create(
        db_session,
        {"data": "2026-11-09", "hora": "10:00", "professor_absent": "Prof test", "assignatura": None},
    )
    diaria = SubstitucioRepository.get_by_date(db_session, "2026-11-09")[0]
    recompte = RecomptesRepository.substitucions_entre(db_session, "2026-11-09", "2026-11-09")[0]
    assert isinstance(recompte, FilaSubstitucio)
    assert diaria.id == str(creada.id)
    assert recompte.id == creada.id
    assert diaria.assignatura == ""
    assert recompte.assignatura is None
    assert diaria.updated_at == creada.updated_at.isoformat()
    assert recompte.updated_at == creada.updated_at.strftime("%Y-%m-%d %H:%M:%S.%f")
    assert recompte.created_at == creada.created_at.strftime("%Y-%m-%d %H:%M:%S.%f")


def test_fila_vigilancia_es_immutable_i_sense_interficie_de_diccionari():
    from vigilancies.files import FilaVigilancia

    fila = FilaVigilancia()
    assert fila.ordre is None
    assert not hasattr(fila, "get")
    with pytest.raises(TypeError):
        fila["hora"]
    with pytest.raises(FrozenInstanceError):
        fila.vigilant = "Prof test"


def test_vigilancies_conserven_buits_diari_i_null_dels_recomptes(db_session):
    from recomptes.repositories import RecomptesRepository
    from vigilancies.files import FilaVigilancia
    from vigilancies.repositories import VigilanciaRepository

    creada = VigilanciaRepository.create(
        db_session,
        "2026-11-09",
        {
            "hora": "10:00",
            "tipus": "Prova",
            "grups": "G1",
            "aula": "A1",
            "nivell": "N1",
            "vigilant": None,
            "comentaris": None,
        },
    )
    diaria = VigilanciaRepository.get_by_date(db_session, "2026-11-09")["N1"][0]
    recompte = RecomptesRepository.vigilancies_entre(db_session, "2026-11-09", "2026-11-09")[0]
    assert isinstance(diaria, FilaVigilancia) and isinstance(recompte, FilaVigilancia)
    assert diaria.id == str(creada.id)
    assert not hasattr(diaria, "db_id")
    from vigilancies.schemas import resposta_vigilancia

    resposta = resposta_vigilancia(diaria).model_dump()
    assert resposta["id"] == str(creada.id) and resposta["db_id"] == creada.id
    assert diaria.vigilant == diaria.comentaris == ""
    assert diaria.updated_at == creada.updated_at.isoformat()
    assert recompte.data == "2026-11-09" and recompte.hora == "10:00"
    assert recompte.vigilant is None
