"""
«No substituir» amb vigència per dates, per l'API com la pantalla.

Abans, afegir una activitat a «No substituir» amagava files ja existents i
feia baixar les absències, els serveis i les hores a cobrir dels cursos
passats. Ara cada canvi val des d'una data (avui per defecte): els dies
d'abans no canvien, llevat que es triï a propòsit una data passada.

Avui és el 04/11/2026 (rellotge de la suite). Prof 15 fa, cada dilluns:
  10:00  Anglès 3-ESO-A
  11:30  Anglès 1-ESO-A
  12:30  Pares            (activitat sense grup)
"""

import uuid

import pytest
from fastapi import Depends
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio

from auth.dependencies import require_admin
from database import get_data_db_session
from estadistiques.router import router as estadistiques_router
from prioritats.repositories import NoSubstituirRepository
from prioritats.router import router as prioritats_router
from rate_limit import limiter
from substitucions import router as substitucions

APP = crea_app(substitucions.router, prioritats_router)
APP.include_router(estadistiques_router, dependencies=[Depends(require_admin)])  # com a main.py

ABSENT = "Prof 15"
HORES = ["10:00", "11:30", "12:30"]
PASSAT = "2026-04-20"  # dilluns d'abans d'avui
FUTUR = "2026-11-09"  # el dilluns que ve
MES_ENDAVANT = "2026-11-16"  # el dilluns següent
INTERVAL = {"data_inici": "2026-04-01", "data_final": "2026-04-30"}
NS = "/api/prioritats/no-substituir"


@pytest.fixture
def centre():
    limiter.reset()
    return nova_institucio(amb_xml=True)


@pytest.fixture
def client(centre):
    usuari = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(usuari, centre, "admin")
    return entra(client_per(APP), usuari)


def _marca_absencia(client, data):
    resp = client.put(
        f"/api/substitucions/{data}/absencies/{ABSENT}", json={"hores_absencia": HORES, "updated_at_map": {}}
    )
    assert resp.status_code == 200, resp.text


def _visibles(client, data):
    resp = client.get(f"/api/substitucions/{data}")
    assert resp.status_code == 200, resp.text
    return sorted(s["hora"] for s in resp.json())


def _cobertura(client):
    resp = client.get("/api/estadistiques/resum", params=INTERVAL)
    assert resp.status_code == 200, resp.text
    return resp.json()["cobertura"]


def _afegeix(client, assignatura, data=None):
    return client.post(NS, json={"assignatura": assignatura, **({"data": data} if data else {})})


def _treu(client, assignatura, data=None):
    return client.delete(f"{NS}/{assignatura}", params={"data": data} if data else {})


def _entrades(centre):
    with get_data_db_session(centre) as db:
        return [
            (e.assignatura, *(d.isoformat() if d else None for d in (e.vigent_des_de, e.vigent_fins_a)))
            for e in NoSubstituirRepository.de_l_activitat(db, "Pares")
        ]


def test_afegir_una_activitat_avui_no_canvia_els_dies_passats(client):
    _marca_absencia(client, PASSAT)
    abans = (_visibles(client, PASSAT), _cobertura(client))
    assert "12:30" in abans[0]

    assert _afegeix(client, "Pares").status_code == 200

    assert (_visibles(client, PASSAT), _cobertura(client)) == abans


def test_treure_una_activitat_avui_no_fa_apareixer_files_als_dies_passats(client, centre):
    # Com una entrada d'abans de la migració: vàlida des de sempre
    with get_data_db_session(centre) as db:
        NoSubstituirRepository.create(db, "Pares")
        db.commit()
    _marca_absencia(client, PASSAT)
    abans = (_visibles(client, PASSAT), _cobertura(client))
    assert "12:30" not in abans[0]

    assert _treu(client, "Pares").status_code == 200

    assert (_visibles(client, PASSAT), _cobertura(client)) == abans
    # No s'esborra: només deixa de valer a partir d'avui
    assert _entrades(centre) == [("Pares", None, "2026-11-03")]
    _marca_absencia(client, FUTUR)
    assert "12:30" in _visibles(client, FUTUR)


def test_una_data_passada_triada_a_proposit_canvia_aquell_interval(client):
    _marca_absencia(client, PASSAT)
    abans = _cobertura(client)

    assert _afegeix(client, "Pares", data="2026-04-01").status_code == 200

    assert "12:30" not in _visibles(client, PASSAT)
    despres = _cobertura(client)
    assert despres["a_cobrir"] == abans["a_cobrir"] - 1
    assert despres["absencies"] == abans["absencies"] - 1


def test_la_generacio_d_un_dia_futur_fa_servir_la_llista_d_aquell_dia(client):
    # «Pares» no se substitueix a partir del 16/11; el 09/11 encara sí
    assert _afegeix(client, "Pares", data=MES_ENDAVANT).status_code == 200
    for data in (FUTUR, MES_ENDAVANT):
        _marca_absencia(client, data)
        resp = client.post(f"/api/substitucions/{data}/generar")
        assert resp.status_code == 200, resp.text
    assert "12:30" in _visibles(client, FUTUR)
    assert "12:30" not in _visibles(client, MES_ENDAVANT)
    totes = client.get(f"/api/substitucions/{MES_ENDAVANT}", params={"include_all": True}).json()
    assert all(not s["substitut"] for s in totes if s["hora"] == "12:30")


def test_les_entrades_d_una_activitat_no_es_poden_solapar(client, centre):
    assert _afegeix(client, "Pares").status_code == 200
    repetida = _afegeix(client, "Pares")
    assert repetida.status_code == 409
    assert repetida.json()["codi"] == "no_substituir_repetida"

    # Deixarà de valer el 01/12: abans d'aquesta data encara hi és
    assert _treu(client, "Pares", data="2026-12-01").status_code == 200
    assert _afegeix(client, "Pares", data="2026-11-20").json()["codi"] == "no_substituir_repetida"
    assert _afegeix(client, "Pares", data="2026-12-15").status_code == 200
    # Una entrada des del 05/12 se solaparia amb la que comença el 15/12
    solapada = _afegeix(client, "Pares", data="2026-12-05")
    assert solapada.status_code == 409
    assert solapada.json()["codi"] == "no_substituir_solapada"

    assert _entrades(centre) == [("Pares", "2026-11-04", "2026-11-30"), ("Pares", "2026-12-15", None)]


def test_la_llista_mostra_les_vigents_avui_i_les_dates_futures(client):
    assert _afegeix(client, "Pares").status_code == 200
    assert _afegeix(client, "Reunió", data="2026-12-01").status_code == 200
    assert _afegeix(client, "Tutoria", data="2026-01-01").status_code == 200
    assert _treu(client, "Tutoria", data="2026-12-01").status_code == 200
    assert _afegeix(client, "Antiga", data="2026-01-01").status_code == 200
    assert _treu(client, "Antiga", data="2026-02-01").status_code == 200

    resp = client.get(NS)
    assert resp.status_code == 200
    cos = resp.json()
    assert cos["assignatures"] == ["Pares", "Tutoria"]
    assert cos["entrades"] == [
        {"assignatura": "Pares", "vigent_des_de": "2026-11-04", "vigent_fins_a": None},
        {"assignatura": "Reunió", "vigent_des_de": "2026-12-01", "vigent_fins_a": None},
        {"assignatura": "Tutoria", "vigent_des_de": "2026-01-01", "vigent_fins_a": "2026-11-30"},
    ]


def test_treure_una_activitat_que_encara_no_havia_comencat_l_anul_la(client, centre):
    assert _afegeix(client, "Pares", data="2026-12-01").status_code == 200
    assert _treu(client, "Pares", data="2026-12-01").status_code == 200
    assert _entrades(centre) == []
    assert _treu(client, "Pares").status_code == 404


def test_una_data_mal_escrita_dona_400(client):
    assert _afegeix(client, "Pares", data="01/12/2026").status_code == 400
    assert _treu(client, "Pares", data="2026-13-01").status_code == 400


def test_treure_des_d_avui_no_toca_un_periode_futur_de_la_mateixa_activitat(client, centre):
    # «Pares» fins al 20/11 i, programada, des de l'01/12: la creu de la
    # vigent (sense data) només tanca la vigent; la futura es conserva.
    assert _afegeix(client, "Pares", data="2026-10-01").status_code == 200
    assert _treu(client, "Pares", data="2026-11-21").status_code == 200
    assert _afegeix(client, "Pares", data="2026-12-01").status_code == 200

    assert _treu(client, "Pares").status_code == 200

    assert _entrades(centre) == [("Pares", "2026-10-01", "2026-11-03"), ("Pares", "2026-12-01", None)]
    # Entre els dos períodes no n'hi ha cap de vigent: res a treure
    assert _treu(client, "Pares", data="2026-11-25").status_code == 404
    assert _entrades(centre) == [("Pares", "2026-10-01", "2026-11-03"), ("Pares", "2026-12-01", None)]


def test_el_solapament_diu_la_data_del_periode_que_hi_ha(client):
    assert _afegeix(client, "Pares", data="2026-12-15").status_code == 200
    solapada = _afegeix(client, "Pares", data="2026-12-05")
    assert solapada.status_code == 409
    cos = solapada.json()
    assert cos["codi"] == "no_substituir_solapada"
    assert cos["params"] == {"assignatura": "Pares", "data": "2026-12-15", "inici": "15/12/2026"}
    assert "15/12/2026" in cos["detail"]
