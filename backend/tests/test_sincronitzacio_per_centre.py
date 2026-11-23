"""La sincronització diària: un bloqueig per centre i cap bloqueig si ja s'ha fet."""

import threading
from contextlib import contextmanager

import pytest

import rellotge
from horari import sincronitzacio

ESPERA = 10  # segons; només s'esgota si el codi es bloqueja


class _Sessio:
    def commit(self):
        pass


@pytest.fixture
def sincronitzacio_simulada(monkeypatch):
    """Sense BD ni XML: `sincronitza_professors` avisa quan comença i espera
    el permís del test per acabar."""
    monkeypatch.setattr(sincronitzacio, "_ultim_dia", {})
    monkeypatch.setattr(sincronitzacio, "_ultim_error", {})
    monkeypatch.setattr(sincronitzacio, "_locks", {})

    @contextmanager
    def sessio(_institucio):
        yield _Sessio()

    monkeypatch.setattr(sincronitzacio, "get_data_db_session", sessio)
    comencades, permisos, crides = {}, {}, []

    def sincronitza(_db, institucio):
        crides.append(institucio)
        comencades.setdefault(institucio, threading.Event()).set()
        assert permisos.setdefault(institucio, threading.Event()).wait(ESPERA)

    monkeypatch.setattr(sincronitzacio, "sincronitza_professors", sincronitza)

    def comencada(institucio):
        return comencades.setdefault(institucio, threading.Event())

    def permet(institucio):
        permisos.setdefault(institucio, threading.Event()).set()

    return comencada, permet, crides


def _en_un_fil(institucio):
    fil = threading.Thread(target=sincronitzacio.sincronitza_un_cop_al_dia, args=(institucio,), daemon=True)
    fil.start()
    return fil


def test_un_centre_que_sincronitza_no_fa_esperar_un_altre(sincronitzacio_simulada):
    comencada, permet, crides = sincronitzacio_simulada
    lent = _en_un_fil("centre_a")
    assert comencada("centre_a").wait(ESPERA)

    # centre_a és a mig sincronitzar (té el seu bloqueig): centre_b no l'espera
    permet("centre_b")
    rapid = _en_un_fil("centre_b")
    rapid.join(ESPERA)
    assert not rapid.is_alive()
    assert lent.is_alive()

    permet("centre_a")
    lent.join(ESPERA)
    assert not lent.is_alive()
    assert sorted(crides) == ["centre_a", "centre_b"]
    assert sincronitzacio._ultim_dia == {"centre_a": rellotge.avui(), "centre_b": rellotge.avui()}


def test_el_mateix_centre_es_sincronitza_un_sol_cop(sincronitzacio_simulada):
    comencada, permet, crides = sincronitzacio_simulada
    primer = _en_un_fil("centre_a")
    assert comencada("centre_a").wait(ESPERA)
    segon = _en_un_fil("centre_a")  # arriba mentre el primer sincronitza

    permet("centre_a")
    for fil in (primer, segon):
        fil.join(ESPERA)
        assert not fil.is_alive()
    assert crides == ["centre_a"]


def test_ja_sincronitzat_avui_no_agafa_el_bloqueig(sincronitzacio_simulada):
    _comencada, _permet, crides = sincronitzacio_simulada
    sincronitzacio._ultim_dia["centre_a"] = rellotge.avui()
    bloqueig = sincronitzacio._lock_de("centre_a")
    assert bloqueig.acquire(timeout=ESPERA)
    try:
        # Amb el bloqueig agafat per un altre, la petició no espera
        fil = _en_un_fil("centre_a")
        fil.join(ESPERA)
        assert not fil.is_alive()
    finally:
        bloqueig.release()
    assert crides == []
