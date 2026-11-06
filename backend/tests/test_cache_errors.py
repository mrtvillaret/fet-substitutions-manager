"""Una fallada transitòria no pot convertir-se en un resultat buit permanent."""

from unittest.mock import Mock

import pytest
from suport_api import XML_EXEMPLE, nova_institucio

from grups import abreviatures
from grups.repositories import AbreviaturaGrupRepository, GrupsAmagatsRepository
from horari import context


def test_abreviatures_reintenten_despres_d_error(monkeypatch):
    centre = nova_institucio()
    monkeypatch.setattr(abreviatures, "_get_institucio_actual", lambda: centre)
    lectura = Mock(side_effect=[OSError("lectura de prova"), [{"grups_originals": "A,B", "abreviatura": "AB"}]])
    monkeypatch.setattr(AbreviaturaGrupRepository, "get_all", lectura)
    with pytest.raises(OSError):
        abreviatures.get_abreviatures_cached()
    assert centre not in abreviatures._abreviatures_cache
    assert abreviatures.get_abreviatures_cached() == {"A,B": "AB"}


@pytest.mark.parametrize("repositori", [GrupsAmagatsRepository, AbreviaturaGrupRepository])
def test_horari_no_es_memoritza_si_falla_una_lectura(monkeypatch, repositori):
    centre = nova_institucio()
    lectura = Mock(side_effect=[OSError("lectura de prova"), []])
    monkeypatch.setattr(repositori, "get_all", lectura)
    with pytest.raises(OSError):
        context.get_horari(centre, data_iso="2026-04-20", xml_path=str(XML_EXEMPLE))
    assert not any(k.startswith(centre + ":") for k in context._horari)
    assert context.get_horari(centre, data_iso="2026-04-20", xml_path=str(XML_EXEMPLE)).professors


def test_traduccions_reintenten_despres_d_error(monkeypatch):
    import gettext

    import i18n_setup

    monkeypatch.setattr(i18n_setup, "_traductors", {})
    lectura = Mock(side_effect=OSError("lectura de prova"))
    monkeypatch.setattr(gettext, "translation", lectura)
    with pytest.raises(OSError):
        i18n_setup.carrega_idioma("ca")
    assert "ca" not in i18n_setup._traductors
    lectura.side_effect = lambda *args, **kwargs: gettext.NullTranslations()
    i18n_setup.carrega_idioma("ca")
    assert "ca" in i18n_setup._traductors


def test_dia_tolerant_reintenta_despres_d_error(db_session):
    from datetime import date
    from types import SimpleNamespace

    from substitucions.domain import DiaEscolar

    class DiaIntermitent:
        institucio = "centre_prova"
        iso = "2026-04-20"
        data = date(2026, 4, 20)
        lectures = 0

        @property
        def horari(self):
            self.lectures += 1
            if self.lectures == 1:
                raise OSError("lectura de prova")
            return SimpleNamespace(get_dia_name=lambda _: "Dilluns")

    dia = DiaEscolar(db_session, DiaIntermitent())
    assert dia.nom_del_dia == ""
    assert dia.nom_del_dia == "Dilluns"
