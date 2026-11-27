"""Sense centre explícit ni autenticat, cap operació pot triar un centre per defecte."""

from datetime import date

import pytest
from suport_api import client_per, crea_app, nova_institucio

from config import context
from errors_domini import NoValid
from grups import abreviatures
from grups.lectures import AlliberatsDelDia
from horari import context as horari
from horari.domain import Dia
from substitucions.context import get_gestors

DATA = "2026-04-20"
TEXT = "Cal indicar el centre per accedir a l'horari"


@pytest.mark.parametrize("fallback", ["entorn", "exemple"])
@pytest.mark.parametrize("porta", ["centre", "dia", "xml", "horari", "gestors", "vigilancies", "abreviatures"])
def test_peticio_sense_centre_no_fa_servir_cap_fallback(monkeypatch, fallback, porta):
    centre = nova_institucio(amb_xml=True)
    if fallback == "entorn":
        monkeypatch.setenv("APP_INSTITUCIO", centre)
    else:
        monkeypatch.delenv("APP_INSTITUCIO", raising=False)
    monkeypatch.setattr(context, "_institucio", context.ContextVar("sense_centre", default=None))
    monkeypatch.setattr(abreviatures, "_abreviatures_cache", {})
    app = crea_app()

    @app.get("/prova")
    def prova():
        if porta == "centre":
            return horari._get_institucio_actual()
        if porta == "dia":
            return Dia.del_centre(date.fromisoformat(DATA)).institucio
        if porta == "xml":
            return Dia.del_centre(date.fromisoformat(DATA)).xml_path
        if porta == "horari":
            return len(horari.get_horari(data_iso=date.fromisoformat(DATA)).professors)
        if porta == "gestors":
            return len(get_gestors(data_iso=date.fromisoformat(DATA))[1].professors)
        if porta == "vigilancies":
            from database import get_data_db_session
            from vigilancies.context import get_vigilancia_core

            with get_data_db_session(centre, lectura=True) as db:
                return len(get_vigilancia_core(date.fromisoformat(DATA), db).professors)
        return abreviatures.get_abreviatures_cached()

    resposta = client_per(app).get("/prova")
    assert resposta.status_code == 400, resposta.text
    assert resposta.json()["detail"] == TEXT


def test_script_sense_centre_tambe_ha_de_ser_explicit(monkeypatch):
    monkeypatch.setattr(context, "_institucio", context.ContextVar("script_sense_centre", default=None))
    monkeypatch.setenv("APP_INSTITUCIO", "exemple")
    with pytest.raises(NoValid) as error:
        Dia.del_centre(date.fromisoformat(DATA))
    assert error.value.codi == "centre_obligatori"


def test_un_script_amb_centre_explicit_no_necessita_context(monkeypatch):
    monkeypatch.setattr(context, "_institucio", context.ContextVar("script_amb_centre", default=None))
    centre = nova_institucio(amb_xml=True)
    assert Dia(date.fromisoformat(DATA), centre).horari.professors


@pytest.mark.parametrize("generador", [False, True])
def test_la_sessio_identifica_el_centre_sense_dependre_del_context(monkeypatch, generador):
    from contextlib import contextmanager

    from database import get_data_db, get_data_db_session

    centre = nova_institucio(amb_xml=True)
    monkeypatch.setattr(context, "_institucio", context.ContextVar("sessio_sense_context", default=None))
    factoria = contextmanager(get_data_db) if generador else get_data_db_session
    with factoria(centre, lectura=True) as db:
        assert db.info.get("institucio") == centre
        dia = date.fromisoformat(DATA)
        assert AlliberatsDelDia.get_by_date(db, dia) == {}
        assert AlliberatsDelDia.get_entre_dates(db, [dia]) == {dia: {}}
