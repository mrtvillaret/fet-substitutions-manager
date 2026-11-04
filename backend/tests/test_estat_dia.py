"""Caracteritza les dues lectures del dia abans d'unificar-ne la classe."""

import pytest

from substitucions import domain, generacio


class Horari:
    def get_dia_name(self, index):
        assert index == 0
        return "Dilluns"


@pytest.fixture
def estat(monkeypatch):
    files = [
        {"professor_absent": "Prof A", "hora": "09", "tipus_absencia": "SERVEI", "aula": "A1"},
        {"professor_absent": "Prof A", "hora": "09", "tipus_absencia": "ABSENCIA", "aula": "A2"},
        {"professor_absent": "Prof A", "hora": "10", "tipus_absencia": "ABSENCIA"},
        {"professor_absent": "Prof B", "hora": "09", "tipus_absencia": None},
        {"professor_absent": "Prof C", "hora": "09", "tipus_absencia": "ALTRE"},
        *[
            {"professor_absent": "Prof D", "hora": "09", "tipus_absencia": tipus}
            for tipus in ("ENCADENADA", "VIGILANCIA", "VIGILANCIA_ABSENT")
        ],
        {"professor_absent": "", "hora": "09"},
        {"professor_absent": "Prof E", "hora": ""},
    ]
    vigilancies = {"09": [{"hora": "09", "vigilant": " Prof V "}, {"hora": "09", "vigilant": ""}]}
    monkeypatch.setattr(domain.SubstitucioRepository, "get_by_date", lambda *_: files)
    monkeypatch.setattr(domain.GrupsAlliberatsRepository, "get_by_date", lambda *_: {"09": ["G1", "G1"]})
    monkeypatch.setattr(domain.VigilanciaRepository, "get_by_date", lambda *_: vigilancies)
    return object(), Horari()


def test_generacio_conserva_els_filtres_l_ordre_i_els_valors_originals(estat):
    db, horari = estat
    dia = generacio.llegeix_estat(db, "2026-04-20", horari)
    assert dia.dia == "Dilluns"
    assert dia.absents == {"Prof A": ["09", "10"], "Prof B": ["09"], "Prof C": ["09"]}
    assert dia.absents_tipus == {"Prof A": "SERVEI", "Prof B": "ABSENCIA", "Prof C": "ALTRE"}
    assert dia.activitats_fallback[("Prof A", "09")]["aula"] == "A1"
    assert dia.grups == {"09": {"G1"}}
    assert dia.vigilants == {"09": {" Prof V "}}


def test_validacio_conserva_els_seus_filtres_i_noms_nets(estat):
    db, horari = estat
    dia = domain.DiaEscolar(db, "2026-04-20", horari=horari)
    assert dict(dia.absents_per_hora) == {"09": {"Prof A"}, "10": {"Prof A"}}
    assert dict(dia.vigilants_per_hora) == {"09": {"Prof V"}}
    assert dia.alliberats == {"09": ["G1", "G1"]}


def test_generacio_i_validacio_comparteixen_la_mateixa_classe(estat):
    db, horari = estat
    assert type(generacio.llegeix_estat(db, "2026-04-20", horari)) is domain.DiaEscolar
