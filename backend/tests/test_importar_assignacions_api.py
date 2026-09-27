"""
Tests de les rutes d'importar assignacions d'exàmens des de l'horari XML
(routes/config_examens.py: importar-assignacions/preview, /dry-run i la
importació real). El càlcul del resum previ en si ja es prova a
test_import_dry_run.py; aquí es prova el recorregut per l'API.

Treballen sobre una institució temporal amb l'horari d'exemple, on Prof 15
fa Anglès amb 3-ESO-A (entre d'altres).
"""
import uuid

import pytest

from database import get_data_db_session
from rate_limit import limiter
from repositories import ConfiguracioExamenRepository, MasterConfigRepository, SubstitucioRepository
from routes import config_examens
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio

APP = crea_app(config_examens.router)
URL = "/api/config/importar-assignacions"
ANGLES_3A = {"assignatura": "Anglès", "grup": "3-ESO-A", "titular": "Prof 15", "nivell": "3-ESO"}


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


def _usuari_de(institucio, role="admin"):
    nom = f"{role}_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, institucio, role)
    return entra(client_per(APP), nom)


@pytest.fixture
def centre():
    return nova_institucio(amb_xml=True)


@pytest.fixture
def client(centre):
    return _usuari_de(centre)


def _preview(client):
    resp = client.get(f"{URL}/preview")
    assert resp.status_code == 200, resp.text
    return resp.json()


def _proposta(preview, **camps):
    return next(p for p in preview["propostes"]
                if all(p[k] == v for k, v in camps.items()))


def _importa(client, propostes, **extra):
    resp = client.post(URL, json={"propostes": propostes, **extra})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _assignacions(centre):
    with get_data_db_session(centre) as db:
        return {(a["assignatura"], a["grup"], a["titular"]) for a in ConfiguracioExamenRepository.get_all(db)}


# ------------------------------------------------------------------ accés

@pytest.mark.parametrize("metode, ruta", [
    ("get", f"{URL}/preview"),
    ("post", f"{URL}/dry-run"),
    ("post", URL),
])
def test_nomes_els_admins_poden_importar(centre, metode, ruta):
    usuari = _usuari_de(centre, role="user")
    kwargs = {} if metode == "get" else {"json": {"propostes": []}}
    assert getattr(usuari, metode)(ruta, **kwargs).status_code == 403


# ---------------------------------------------------------------- preview

def test_preview_proposa_cada_assignatura_i_grup_de_l_horari_amb_el_seu_titular(client):
    preview = _preview(client)
    proposta = _proposta(preview, assignatura="Anglès", grup="3-ESO-A")
    assert proposta["titular"] == "Prof 15"
    assert proposta["nivell"] == "3-ESO"
    assert (proposta["ja_existeix"], proposta["descartada"]) == (False, False)
    # Les activitats sense grup (guàrdies, reunions...) no són sessions d'examen.
    assert not any(p["assignatura"] == "Guàrdia" for p in preview["propostes"])


def test_preview_sense_historic_proposa_tots_els_nivells(client):
    preview = _preview(client)
    assert preview["nivells_valids"] == []
    assert {"1-ESO", "3-ESO", "2-BAT"} <= {p["nivell"] for p in preview["propostes"]}


def test_preview_nomes_proposa_nivells_amb_historic_de_substitucions(client, centre):
    with get_data_db_session(centre) as db:
        SubstitucioRepository.create(db, {
            "data": "2026-04-20", "hora": "10:00", "professor_absent": "Prof 15",
            "assignatura": "Anglès", "grup": "3-ESO-A", "aula": "", "substitut": "",
            "tipus_substitut": "", "tipus_absencia": "ABSENCIA", "comentaris": "",
        })
    preview = _preview(client)
    assert preview["nivells_valids"] == ["3-ESO"]
    assert {p["nivell"] for p in preview["propostes"]} == {"3-ESO"}


def test_preview_marca_les_que_ja_s_han_importat(client):
    _importa(client, [ANGLES_3A])
    assert _proposta(_preview(client), assignatura="Anglès", grup="3-ESO-A")["ja_existeix"] is True


def test_preview_marca_les_descartades(client):
    _importa(client, [], descartades=[ANGLES_3A])
    assert _proposta(_preview(client), assignatura="Anglès", grup="3-ESO-A")["descartada"] is True


def test_preview_no_escriu_res(client, centre):
    _preview(client)
    assert _assignacions(centre) == set()


def test_preview_sense_xml_ho_indica(centre):
    sense_xml = _usuari_de(nova_institucio(amb_xml=False))
    resp = sense_xml.get(f"{URL}/preview")
    assert resp.status_code == 400
    assert resp.json()["detail"]["xml_missing"] is True


# ---------------------------------------------------------------- dry-run

def test_dry_run_diu_el_mateix_que_despres_fa_la_importacio(client, centre):
    propostes = [ANGLES_3A, {**ANGLES_3A, "grup": "3-ESO-B"}, {"assignatura": "Anglès", "grup": ""}]
    resum = client.post(f"{URL}/dry-run", json={"propostes": propostes}).json()
    assert _assignacions(centre) == set()  # el resum previ no escriu res

    resultat = _importa(client, propostes)
    for camp in ("nivells_creats", "grups_creats", "assignatures_creades",
                 "assignacions_creades", "ja_existien"):
        assert resum[camp] == resultat[camp], camp
    # Mateixos avisos, però el resum parla en futur ("no s'importarà") i el
    # resultat en passat ("no s'ha importat").
    assert [a.split(",")[0] for a in resum["avisos"]] == [a.split(",")[0] for a in resultat["avisos"]]


# -------------------------------------------------------------- importar

def test_importar_crea_la_configuracio_mestra_i_les_assignacions(client, centre):
    resultat = _importa(client, [{**ANGLES_3A, "aula": "A1"}])
    assert resultat["nivells_creats"] == ["3-ESO"]
    assert resultat["assignacions_creades"] == ["Anglès – 3-ESO-A (Prof 15)"]
    assert _assignacions(centre) == {("Anglès", "3-ESO-A", "Prof 15")}
    with get_data_db_session(centre) as db:
        assert MasterConfigRepository.get_nivells(db) == ["3-ESO"]
        assert MasterConfigRepository.get_grups_per_nivell(db, "3-ESO") == ["3-ESO-A"]
        assert MasterConfigRepository.get_aules(db) == ["A1"]


def test_importar_dues_vegades_no_duplica(client, centre):
    _importa(client, [ANGLES_3A])
    resultat = _importa(client, [ANGLES_3A])
    assert resultat["ja_existien"] == 1
    assert resultat["assignacions_creades"] == []
    assert len(_assignacions(centre)) == 1


def test_importar_proposta_incompleta_dona_avis(client, centre):
    resultat = _importa(client, [{"assignatura": "Anglès", "grup": "3-ESO-A"}])
    assert resultat["avisos"] == ["Proposta 1: falta nivell, no s'ha importat"]
    assert _assignacions(centre) == set()


def test_importar_amb_sobreescriure_esborra_la_configuracio_anterior(client, centre):
    _importa(client, [ANGLES_3A])
    _importa(client, [{**ANGLES_3A, "grup": "1-ESO-A", "nivell": "1-ESO"}], overwrite=True)
    assert _assignacions(centre) == {("Anglès", "1-ESO-A", "Prof 15")}
    with get_data_db_session(centre) as db:
        assert MasterConfigRepository.get_nivells(db) == ["1-ESO"]


def test_tornar_a_importar_una_descartada_la_deixa_de_marcar(client):
    _importa(client, [], descartades=[ANGLES_3A])
    _importa(client, [ANGLES_3A])
    proposta = _proposta(_preview(client), assignatura="Anglès", grup="3-ESO-A")
    assert (proposta["ja_existeix"], proposta["descartada"]) == (True, False)
