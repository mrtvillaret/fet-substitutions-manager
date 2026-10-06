"""
Professors alliberats: alliberar un professor sense alliberar el seu grup.

Cas d'ús: en una optativa amb diversos professors, un es queda els alumnes
d'un altre (p.ex. per fer un taller) i aquest altre queda lliure. El grup
continua tenint classe, i la resta de professors de l'optativa també.

Horari d'exemple, dilluns 20/04/2026 a les 10:00:
  - Prof 26, 31, 35 i 47 fan «2.3» amb 2-BAT-A,2-BAT-B (la mateixa franja).
  - Prof 15 fa Anglès amb 3-ESO-A.
A les 11:30, Prof 26 fa «2.1» amb 2-BAT-A,2-BAT-B.
"""
import uuid

import pytest

from rate_limit import limiter
from routes import grups, substitucions, vigilancies
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio

APP = crea_app(grups.router, substitucions.router, vigilancies.router)
DATA = "2026-04-20"  # dilluns
URL_GRUPS = f"/api/grups/{DATA}"
URL_SUBS = f"/api/substitucions/{DATA}"
URL_VIGS = f"/api/vigilancies/{DATA}"

ALLIBERAT = "Prof 26"
COMPANY = "Prof 31"  # la mateixa franja, no alliberat
GRUP_FRANJA = "2-BAT-A,2-BAT-B"


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


@pytest.fixture
def client():
    centre = nova_institucio(amb_xml=True)
    nom = f"user_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, centre, "user")
    return entra(client_per(APP), nom)


def _allibera(client, professors=None, grups_per_hora=None):
    resp = client.put(URL_GRUPS, json={
        "grups": grups_per_hora or {},
        "professors": professors if professors is not None else {"10:00": [ALLIBERAT]},
    })
    assert resp.status_code == 200, resp.text
    return resp.json()


def _marca_absencia(client, professor, hores=("10:00",)):
    resp = client.put(f"{URL_SUBS}/absencies/{professor}",
                      json={"hores_absencia": list(hores), "updated_at_map": {}})
    assert resp.status_code == 200, resp.text


def _fila(client, professor, hora="10:00"):
    files = client.get(URL_SUBS, params={"include_all": True}).json()
    return next(s for s in files if s["professor_absent"] == professor and s["hora"] == hora)


def _assigna(client, substitut, hora="10:00", absent="Prof 15"):
    return client.put(f"{URL_SUBS}/{hora}/{absent}", json={
        "substitut": substitut, "updated_at": _fila(client, absent, hora)["updated_at"]})


def _disponibles_subs(client, hora="10:00"):
    resp = client.get(f"{URL_SUBS}/{hora}/disponibles")
    assert resp.status_code == 200, resp.text
    return {d["professor"]: d["tipus"] for d in resp.json()["disponibles"]}


# ------------------------------------------------------------------ desar i llegir

def test_es_desen_i_es_llegeixen_separats_dels_grups(client):
    resposta = _allibera(client, grups_per_hora={"10:00": ["3-ESO-C"]})
    assert (resposta["total_grups"], resposta["total_professors"]) == (1, 1)

    cos = client.get(URL_GRUPS).json()
    assert cos["grups_seleccionats_per_hora"] == {"10:00": ["3-ESO-C"]}
    assert cos["professors_alliberats_per_hora"] == {"10:00": [ALLIBERAT]}
    assert sorted(cos["professors_per_grup_hora"]["10:00"][GRUP_FRANJA]) == [
        "Prof 26", "Prof 31", "Prof 35", "Prof 47"]
    assert not any(g.startswith("professor:") for g in cos["grups_disponibles"])


def test_els_grups_amb_un_sol_professor_no_hi_surten(client):
    # A les 10:00 Prof 15 fa Anglès sol amb 3-ESO-A: s'allibera el grup.
    compartits = client.get(URL_GRUPS).json()["professors_per_grup_hora"]["10:00"]
    assert "3-ESO-A" not in compartits
    assert all(len(profs) > 1 for profs in compartits.values())


def test_desar_sense_professors_els_treu(client):
    _allibera(client)
    _allibera(client, professors={})
    assert client.get(URL_GRUPS).json()["professors_alliberats_per_hora"] == {}


def test_un_grup_no_es_pot_fer_passar_per_professor(client):
    _allibera(client, professors={}, grups_per_hora={"10:00": [f"professor:{ALLIBERAT}"]})
    cos = client.get(URL_GRUPS).json()
    assert cos["professors_alliberats_per_hora"] == {}
    assert cos["grups_seleccionats_per_hora"] == {}


# ------------------------------------------------------------------ substitucions

def test_surt_com_a_alliberat_i_els_companys_no(client):
    assert ALLIBERAT not in _disponibles_subs(client)
    _allibera(client)
    disponibles = _disponibles_subs(client)
    assert disponibles[ALLIBERAT] == "alliberat"
    assert COMPANY not in disponibles


def test_nomes_a_les_hores_marcades(client):
    _allibera(client)
    assert ALLIBERAT not in _disponibles_subs(client, "11:30")


def test_se_li_pot_assignar_una_substitucio(client):
    _marca_absencia(client, "Prof 15")
    assert _assigna(client, ALLIBERAT).status_code == 400  # té classe
    _allibera(client)
    assert _assigna(client, ALLIBERAT).status_code == 200
    assert _assigna(client, COMPANY).status_code == 400


def test_generar_el_pot_triar(client):
    # Sense guàrdies ni altres alliberats lliures, l'únic candidat és ell.
    _allibera(client)
    _marca_absencia(client, "Prof 15")
    for guardia in ("Prof 3", "Prof 21", "Prof 28"):
        _marca_absencia(client, guardia)
    assert client.post(f"{URL_SUBS}/generar").status_code == 200
    assert _fila(client, "Prof 15")["substitut"] == ALLIBERAT


def test_si_es_absent_no_cal_substituir_lo(client):
    _allibera(client)
    _marca_absencia(client, ALLIBERAT)
    _marca_absencia(client, COMPANY)
    visibles = {(s["professor_absent"], s["hora"]) for s in client.get(URL_SUBS).json()}
    assert (ALLIBERAT, "10:00") not in visibles
    assert (COMPANY, "10:00") in visibles


# ------------------------------------------------------------------ vigilàncies

def test_a_vigilancies_tambe_surt_com_a_alliberat(client):
    def estat(professor):
        llista = client.get(f"{URL_VIGS}/10:00/disponibles").json()
        return next(p["estat"] for p in llista if p["value"] == professor)

    assert estat(ALLIBERAT) == "CLASSE"
    _allibera(client)
    assert estat(ALLIBERAT) == "ALLIBERAT"
    assert estat(COMPANY) == "CLASSE"


def test_si_vigila_no_cal_cobrir_la_seva_classe(client):
    def cobertures(professor):
        files = client.get(URL_SUBS, params={"include_all": True}).json()
        return [s for s in files if s["professor_absent"] == professor and s["tipus_absencia"] == "VIGILANCIA"]

    resp = client.post(URL_VIGS, json={
        "hora": "10:00", "tipus": "Anglès", "grups": "3-ESO-A", "aula": "",
        "nivell": "3-ESO", "vigilant": ALLIBERAT})
    assert resp.status_code == 200, resp.text
    assert len(cobertures(ALLIBERAT)) == 1

    _allibera(client)
    assert cobertures(ALLIBERAT) == []
