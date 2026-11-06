"""Cap estat del dia no es comparteix entre peticions simultànies."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace

import pytest

from horari import context as horari_context
from horari.domain import Dia
from substitucions.domain import DiaEscolar
from vigilancies import context as vigilancia_context


def test_dos_dies_simultanis_tenen_nuclis_independents(monkeypatch):
    barrera = Barrier(2)
    horari = SimpleNamespace(professors=[], get_dia_name=lambda i: str(i))

    def gestors(*args, **kwargs):
        barrera.wait()
        return None, horari, object(), None

    monkeypatch.setattr(horari_context, "_resolve_xml_path", lambda *_: "exemple.xml")
    monkeypatch.setattr(vigilancia_context, "get_gestors", gestors)
    monkeypatch.setattr(vigilancia_context.ConfiguracioExamenRepository, "get_all_as_dict", lambda *_: {})
    monkeypatch.setattr(vigilancia_context.SubstitucioRepository, "get_by_date", lambda *_: [])
    monkeypatch.setattr(vigilancia_context.GrupsAlliberatsRepository, "get_by_date", lambda _, data: {"09": [data]})
    with ThreadPoolExecutor(2) as fils:
        futures = [
            fils.submit(vigilancia_context.get_vigilancia_core, data, object(), "temporal")
            for data in ("2026-04-20", "2026-04-21")
        ]
        primer, segon = [f.result() for f in futures]
    assert primer is not segon
    assert primer.grups_sense_classe == {"09": ["2026-04-20"]}
    assert segon.grups_sense_classe == {"09": ["2026-04-21"]}


def test_dia_escolar_reutilitza_el_dia_i_el_seu_horari(db_session, monkeypatch):
    dia = Dia.de_text("2026-04-20", "temporal")
    lectures = []
    horari = SimpleNamespace(get_dia_name=lambda _: "Dilluns")

    def llegeix(_dia):
        lectures.append(_dia.iso)
        return horari

    monkeypatch.setattr(Dia, "horari", property(llegeix))
    estat = DiaEscolar(db_session, dia)
    assert lectures == []
    assert estat.data == dia.iso
    assert estat.horari is horari
    assert estat.horari is horari
    assert lectures == [dia.iso]
    assert estat.dia is dia
    assert estat.nom_del_dia == "Dilluns"


@pytest.mark.parametrize("estricte", [False, True])
def test_errors_d_horari_conserven_el_mode_i_els_reintents(db_session, monkeypatch, caplog, estricte):
    lectures = []
    error = RuntimeError("error de prova")

    def falla(_dia):
        lectures.append(_dia.iso)
        raise error

    monkeypatch.setattr(Dia, "horari", property(falla))
    estat = DiaEscolar(db_session, Dia.de_text("2026-04-20", "temporal"), estricte=estricte)
    assert lectures == []
    for _ in range(2):
        if estricte:
            with pytest.raises(RuntimeError) as capturada:
                _ = estat.horari
            assert capturada.value is error
        else:
            assert estat.horari is None
    assert len(lectures) == 2
    assert len(caplog.records) == (0 if estricte else 2)
    if not estricte:
        assert caplog.records[0].exc_info[1] is error
