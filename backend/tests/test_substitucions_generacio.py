"""Tests de la generació i regeneració de substitucions."""

from horari.domain import Dia
from substitucions import domain, generacio
from substitucions.files import FilaSubstitucio


class _Horari:
    def get_dia_name(self, weekday_idx):
        assert weekday_idx == 0
        return "Dilluns"


def test_activitat_fallback_conserva_l_aula_desada(monkeypatch):
    fila = {
        "professor_absent": "Prof A",
        "hora": "09:00",
        "assignatura": "Matemàtiques",
        "grup": "1-ESO-A",
        "aula": "A1",
        "tipus_absencia": "ABSENCIA",
    }
    monkeypatch.setattr(generacio.SubstitucioRepository, "get_by_date", lambda db, data: [FilaSubstitucio(**fila)])
    monkeypatch.setattr(domain.AlliberatsDelDia, "get_by_date", lambda db, data: {})
    monkeypatch.setattr(domain.VigilanciaRepository, "get_by_date", lambda db, data: {})

    dia = Dia.de_text("2026-04-20", "centre_de_prova")
    dia.__dict__["horari"] = _Horari()
    estat = domain.DiaEscolar(object(), dia)

    assert estat.activitats_fallback[("Prof A", "09:00")] == {
        "assignatura": "Matemàtiques",
        "grup": "1-ESO-A",
        "aula": "A1",
    }
