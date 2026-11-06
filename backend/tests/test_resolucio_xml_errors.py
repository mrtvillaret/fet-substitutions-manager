"""Sense versió hi ha alternativa; un error de BD no és absència de dades."""

from pathlib import Path

import pytest
from sqlalchemy.exc import OperationalError
from suport_api import XML_EXEMPLE, nova_institucio

from database import get_data_dir_for_institucio
from horari import context as horari_context

DATA = "2026-04-20"


@pytest.mark.parametrize("lectura", ["versio", "configuracio", "sessio"])
def test_un_error_de_bd_no_activa_cap_alternativa_xml(monkeypatch, lectura):
    centre = nova_institucio(amb_xml=True)
    monkeypatch.setenv("APP_XML_PATH", str(XML_EXEMPLE))

    def falla(*args, **kwargs):
        raise OperationalError("lectura de prova", {}, RuntimeError("BD simulada"))

    if lectura == "versio":
        monkeypatch.setattr(horari_context.XMLVersionRepository, "vigent", falla)
    elif lectura == "configuracio":
        monkeypatch.setattr(horari_context.XMLVersionRepository, "vigent", lambda *_: None)
        monkeypatch.setattr(horari_context.ConfiguracioRepository, "get", falla)
    else:
        monkeypatch.setattr(horari_context, "get_data_db_session", falla)
    with pytest.raises(OperationalError, match="BD simulada"):
        horari_context.get_xml_path_for_date(centre, DATA)


def test_sense_versions_es_conserva_el_cami_de_configuracio(monkeypatch):
    centre = nova_institucio(amb_xml=True)
    monkeypatch.delenv("APP_XML_PATH", raising=False)
    assert (
        Path(horari_context.get_xml_path_for_date(centre, DATA)) == get_data_dir_for_institucio(centre) / "teachers.xml"
    )


def test_sense_versions_ni_configuracio_es_conserva_l_alternativa_d_entorn(monkeypatch):
    centre = nova_institucio()
    monkeypatch.setenv("APP_XML_PATH", str(XML_EXEMPLE))
    assert horari_context.get_xml_path_for_date(centre, DATA) == str(XML_EXEMPLE)


def test_sense_cap_xml_retorna_none(monkeypatch):
    centre = nova_institucio()
    monkeypatch.delenv("APP_XML_PATH", raising=False)
    assert horari_context.get_xml_path_for_date(centre, DATA) is None
