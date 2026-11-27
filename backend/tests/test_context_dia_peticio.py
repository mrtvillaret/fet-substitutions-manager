"""Cap estat del dia no es comparteix entre peticions simultànies."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier
from types import SimpleNamespace
from xml.etree.ElementTree import ParseError

import pytest

from errors_domini import MissingXmlError
from horari.domain import Dia
from substitucions.domain import DiaEscolar
from substitucions.files import FilaSubstitucio
from vigilancies import context as vigilancia_context


def test_dos_dies_simultanis_tenen_nuclis_independents(monkeypatch):
    barrera = Barrier(2, timeout=5)

    def absencies(_db, data):
        barrera.wait()
        return [FilaSubstitucio(professor_absent=f"Prof {data.day}", hora="09:00")]

    monkeypatch.setattr(vigilancia_context.SubstitucioRepository, "get_by_date", absencies)
    monkeypatch.setattr(vigilancia_context.AlliberatsDelDia, "get_by_date", lambda _, data: {"09": [data.isoformat()]})
    with ThreadPoolExecutor(2) as fils:
        futures = [
            fils.submit(vigilancia_context.get_vigilancia_core, data, object(), "temporal")
            for data in (date(2026, 4, 20), date(2026, 4, 21))
        ]
        primer, segon = [f.result() for f in futures]
    assert primer is not segon
    assert primer.absents_actuals == {"Prof 20": ["09:00"]}
    assert segon.absents_actuals == {"Prof 21": ["09:00"]}
    assert primer.grups_sense_classe == {"09": ["2026-04-20"]}
    assert segon.grups_sense_classe == {"09": ["2026-04-21"]}


def test_dia_escolar_reutilitza_el_dia_i_el_seu_horari(db_session, monkeypatch):
    dia = Dia(date.fromisoformat("2026-04-20"), "temporal")
    lectures = []
    horari = SimpleNamespace(get_dia_name=lambda _: "Dilluns")

    def llegeix(_dia):
        lectures.append(_dia.iso)
        return horari

    monkeypatch.setattr(Dia, "horari", property(llegeix))
    estat = DiaEscolar(db_session, dia)
    assert lectures == []
    assert estat.data == dia.data
    assert estat.horari is horari
    assert estat.horari is horari
    assert lectures == [dia.iso]
    assert estat.dia is dia
    assert estat.nom_del_dia == "Dilluns"


@pytest.mark.parametrize("estricte", [False, True])
@pytest.mark.parametrize(
    "error",
    [
        MissingXmlError("temporal", None),
        ParseError("XML mal format"),
        OSError("il·legible"),
        RuntimeError("error de codi"),
    ],
    ids=["sense_xml", "mal_format", "illegible", "inesperat"],
)
def test_errors_d_horari_conserven_el_mode_i_els_reintents(db_session, monkeypatch, caplog, estricte, error):
    """Sense horari (XML que falta o il·legible) el mode tolerant continua amb
    un sol avís i no rellegeix; la resta d'errors (de codi) sempre arriben."""
    lectures = []

    def falla(_dia):
        lectures.append(_dia.iso)
        raise error

    monkeypatch.setattr(Dia, "horari", property(falla))
    estat = DiaEscolar(db_session, Dia(date.fromisoformat("2026-04-20"), "temporal"), estricte=estricte)
    assert lectures == []
    tolera = not estricte and not isinstance(error, RuntimeError)
    for _ in range(2):
        if tolera:
            assert estat.horari is None
            assert estat.baixes == frozenset()
            assert estat.activitat("Prof 1", "09:00") == {}
            assert estat.professor_a_horari("Prof 1") is None
        else:
            with pytest.raises(type(error)) as capturada:
                _ = estat.horari
            assert capturada.value is error
    if tolera:
        assert len(lectures) == 1
        assert [r.exc_info[1] for r in caplog.records] == [error]
    else:
        assert len(lectures) == 2
        assert caplog.records == []
