"""
Substitucions encadenades: un professor que fa una activitat de les
prioritats que no és a «No substituir» (p.ex. Guàrdia) i passa a fer una
substitució deixa la seva activitat sense fer; se'n crea una substitució
(tipus ENCADENADA) a la mateixa hora.

Horari d'exemple, dilluns 20/04/2026 a les 09:00: Prof 1 fa E.F. amb
3-ESO-A; Prof 2 i Prof 9 fan Guàrdia. Per defecte, Guàrdia és a les
prioritats i «No substituir» és buit.
"""

import uuid
from datetime import date

import pytest
from fastapi import Depends
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio

from auth.dependencies import get_current_user, require_admin
from database import get_data_db_session
from grups import router as grups
from models import Substitucio
from prioritats.router import router as prioritats_router
from rate_limit import limiter
from substitucions import router as substitucions

APP = crea_app()
APP.include_router(prioritats_router, dependencies=[Depends(require_admin)])  # com a main.py
APP.include_router(substitucions.router, dependencies=[Depends(get_current_user)])
APP.include_router(grups.router, dependencies=[Depends(get_current_user)])
DATA = "2026-04-20"
GUARDIA = {"Prof 2", "Prof 9"}


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


@pytest.fixture
def centre():
    institucio = nova_institucio(amb_xml=True)
    nom = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, institucio, "admin")
    return institucio, entra(client_per(APP), nom)


def _files(institucio):
    """Les files del dia, a la BD (amb tipus_substitut, que l'API no torna)."""
    with get_data_db_session(institucio) as db:
        return [
            {
                c: getattr(s, c)
                for c in ("hora", "professor_absent", "assignatura", "substitut", "tipus_substitut", "tipus_absencia")
            }
            for s in db.query(Substitucio).filter(Substitucio.data == date.fromisoformat(DATA)).all()
        ]


def _absent_i_genera(client, hores=("09:00",)):
    resp = client.put(
        f"/api/substitucions/{DATA}/absencies/Prof 1", json={"hores_absencia": list(hores), "updated_at_map": {}}
    )
    assert resp.status_code == 200, resp.text
    resp = client.post(f"/api/substitucions/{DATA}/generar", params={"regenerar_tot": False})
    assert resp.status_code == 200, resp.text


def test_genera_pendents_crea_l_encadenada_d_un_substitut_de_guardia(centre):
    institucio, client = centre
    _absent_i_genera(client)
    files = _files(institucio)

    sub = next(f for f in files if f["professor_absent"] == "Prof 1")
    assert sub["substitut"] in GUARDIA
    # L'activitat, entre parèntesis: d'aquí la treu el motor per decidir l'encadenada
    assert sub["tipus_substitut"] == "disponible (Guàrdia)"

    encadenada = next(f for f in files if f["tipus_absencia"] == "ENCADENADA")
    assert encadenada["hora"] == "09:00"
    assert encadenada["professor_absent"] == sub["substitut"]
    assert encadenada["assignatura"] == "Guàrdia"
    # La cobreix l'altre professor de guàrdia
    assert encadenada["substitut"] == (GUARDIA - {sub["substitut"]}).pop()


def test_amb_guardia_a_no_substituir_no_hi_ha_encadenada(centre):
    institucio, client = centre
    assert client.post("/api/prioritats/no-substituir", json={"assignatura": "Guàrdia"}).status_code == 200
    _absent_i_genera(client)

    assert not any(f["tipus_absencia"] == "ENCADENADA" for f in _files(institucio))


# ------------------------------------------------- triar el substitut a mà
# Proposta: la mateixa regla que el motor (activitat de les prioritats que no
# és a «No substituir»), en un sol lloc; en canviar o treure el substitut,
# l'encadenada que havia provocat s'esborra.


def _absent(client, hores=("09:00",)):
    resp = client.put(
        f"/api/substitucions/{DATA}/absencies/Prof 1", json={"hores_absencia": list(hores), "updated_at_map": {}}
    )
    assert resp.status_code == 200, resp.text


def _tria(client, substitut, hora="09:00"):
    resp = client.put(f"/api/substitucions/{DATA}/{hora}/Prof 1", json={"substitut": substitut, "force": True})
    assert resp.status_code == 200, resp.text


def _encadenades(institucio):
    return sorted(
        (f["hora"], f["professor_absent"], f["assignatura"], f["substitut"] or "")
        for f in _files(institucio)
        if f["tipus_absencia"] == "ENCADENADA"
    )


def test_triar_a_ma_un_substitut_de_guardia_crea_l_encadenada(centre):
    institucio, client = centre
    _absent(client)
    _tria(client, "Prof 2")
    # Pendent: el substitut de l'encadenada es tria (o el posa «Genera pendents»)
    assert _encadenades(institucio) == [("09:00", "Prof 2", "Guàrdia", "")]


def test_canviar_el_substitut_esborra_l_encadenada_d_abans_i_crea_la_nova(centre):
    institucio, client = centre
    _absent(client)
    _tria(client, "Prof 2")
    _tria(client, "Prof 9")
    assert _encadenades(institucio) == [("09:00", "Prof 9", "Guàrdia", "")]


def test_treure_el_substitut_esborra_l_encadenada(centre):
    institucio, client = centre
    _absent(client)
    _tria(client, "Prof 2")
    _tria(client, "")
    assert _encadenades(institucio) == []


def test_un_substitut_alliberat_no_crea_encadenada(centre):
    # Prof 10 fa Religió amb 1-BAT-B a les 09:00: amb el grup sense classe, queda alliberat
    institucio, client = centre
    resp = client.put(f"/api/grups/{DATA}", json={"grups": {"09:00": ["1-BAT-B"]}, "professors": {}})
    assert resp.status_code == 200, resp.text
    _absent(client)
    _tria(client, "Prof 10")
    assert _encadenades(institucio) == []


def test_triar_a_ma_amb_guardia_a_no_substituir_no_crea_encadenada(centre):
    institucio, client = centre
    assert client.post("/api/prioritats/no-substituir", json={"assignatura": "Guàrdia"}).status_code == 200
    _absent(client)
    _tria(client, "Prof 2")
    assert _encadenades(institucio) == []


def test_genera_pendents_respecta_l_encadenada_creada_a_ma(centre):
    # La de la tria a mà i la del motor són la mateixa: no se'n fan dues
    institucio, client = centre
    _absent(client)
    _tria(client, "Prof 2")
    assert client.post(f"/api/substitucions/{DATA}/generar", params={"regenerar_tot": False}).status_code == 200
    assert [e[:3] for e in _encadenades(institucio)] == [("09:00", "Prof 2", "Guàrdia")]


def test_triar_a_ma_desa_l_activitat_entre_parentesis(centre):
    institucio, client = centre
    _absent(client)
    _tria(client, "Prof 2")
    sub = next(f for f in _files(institucio) if f["professor_absent"] == "Prof 1")
    assert sub["tipus_substitut"] == "disponible (Guàrdia)"


def test_esborrar_les_absencies_esborra_les_encadenades(centre):
    # Prof 1 ja no és absent: el seu substitut torna a la guàrdia
    institucio, client = centre
    _absent(client)
    _tria(client, "Prof 2")
    resp = client.put(f"/api/substitucions/{DATA}/absencies/Prof 1", json={"hores_absencia": [], "updated_at_map": {}})
    assert resp.status_code == 200, resp.text
    assert _encadenades(institucio) == []


def test_treure_una_hora_d_absencia_esborra_nomes_la_seva_encadenada(centre):
    institucio, client = centre
    _absent(client, hores=("09:00", "10:00"))
    _tria(client, "Prof 2", hora="09:00")
    _tria(client, "Prof 3", hora="10:00")
    resp = client.put(
        f"/api/substitucions/{DATA}/absencies/Prof 1", json={"hores_absencia": ["10:00"], "updated_at_map": {}}
    )
    assert resp.status_code == 200, resp.text
    assert _encadenades(institucio) == [("10:00", "Prof 3", "Guàrdia", "")]


def test_genera_pendents_descarta_l_encadenada_que_ja_no_cal(centre):
    # Com feia el motor: només conserva l'encadenada d'un substitut actiu
    institucio, client = centre
    _absent(client)
    _tria(client, "Prof 2")
    _tria(client, "")
    assert client.post(f"/api/substitucions/{DATA}/generar", params={"regenerar_tot": False}).status_code == 200
    encadenades = _encadenades(institucio)
    substitut = next(f["substitut"] for f in _files(institucio) if f["professor_absent"] == "Prof 1")
    assert [e[:3] for e in encadenades] == [("09:00", substitut, "Guàrdia")]


def test_la_resposta_diu_si_han_canviat_les_encadenades(centre):
    # La pantalla torna a carregar la llista si n'hi ha de noves o d'esborrades
    _, client = centre
    _absent(client)
    url = f"/api/substitucions/{DATA}/09:00/Prof 1"
    assert client.put(url, json={"substitut": "Prof 2", "force": True}).json()["encadenades"] == {
        "creades": 1,
        "esborrades": 0,
    }
    assert client.put(url, json={"substitut": "Prof 9", "force": True}).json()["encadenades"] == {
        "creades": 1,
        "esborrades": 1,
    }


def test_l_ordre_posa_cada_encadenada_sota_la_seva_substitucio():
    # El de la pantalla i el PDF (SubstitucioRepository.ordena)
    from substitucions.repositories import SubstitucioRepository

    def fila(hora, absent, grup, substitut="", tipus="ABSENCIA"):
        return {"hora": hora, "professor_absent": absent, "grup": grup, "substitut": substitut, "tipus_absencia": tipus}

    files = [
        fila("10:00", "Prof 9", "", "Prof 4", "ENCADENADA"),
        fila("10:00", "Prof 1", "3-ESO-C", "Prof 9"),
        fila("09:00", "Prof 3", "2-BAT-A"),
        fila("10:00", "Prof 15", "3-ESO-A", "Prof 2"),
        fila("10:00", "Prof 7", "10-ESO-A"),
    ]
    ordre = [(f["hora"], f["professor_absent"]) for f in SubstitucioRepository.ordena(files, ["09:00", "10:00"])]
    assert ordre == [
        ("09:00", "Prof 3"),
        ("10:00", "Prof 15"),  # 3-ESO-A
        ("10:00", "Prof 1"),  # 3-ESO-C
        ("10:00", "Prof 9"),  # l'encadenada del seu substitut
        ("10:00", "Prof 7"),  # 10-ESO-A: ordre natural
    ]
