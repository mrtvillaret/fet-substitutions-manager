"""Tests de la generació i regeneració de substitucions."""

from substitucions import generacio


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
    monkeypatch.setattr(generacio.SubstitucioRepository, "get_by_date", lambda db, data: [fila])
    monkeypatch.setattr(generacio.GrupsAlliberatsRepository, "get_by_date", lambda db, data: {})
    monkeypatch.setattr(generacio.VigilanciaRepository, "get_by_date", lambda db, data: {})

    estat = generacio.llegeix_estat(object(), "2026-04-20", _Horari())

    assert estat.activitats_fallback[("Prof A", "09:00")] == {
        "assignatura": "Matemàtiques",
        "grup": "1-ESO-A",
        "aula": "A1",
    }
