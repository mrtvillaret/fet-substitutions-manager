"""
Els errors del planificador no s'empassen. Una lectura que falla és un error
intern (500 amb una referència; el detall, al registre), no uns valors per
defecte. Si falla publicar un dia o assignar-ne els titulars, la resposta ho
diu amb un missatge genèric (no es publica res) i el detall, que pot ser
intern, només va al registre.
"""

import uuid
import xml.etree.ElementTree as ET

import pytest
from fastapi.testclient import TestClient
from suport_api import crea_app, crea_usuari, entra, nova_institucio

from configuracio.repositories import ConfiguracioRepository
from planificador import publicacio
from planificador.alliberaments import _hores_lectives_des_de_xml
from planificador.repositories import CostProfessorRepository
from planificador.router import router
from rate_limit import limiter

APP = crea_app(router)
DATA = "2026-04-20"  # dilluns
DETALL = "detall intern /ruta/secreta"
HORARI = {
    "dies": [
        {
            "dia": "Dilluns",
            "data": DATA,
            "sessions": [
                {
                    "hora": "10:00",
                    "sessions_simultanees": [
                        {
                            "curs": "1-BAT",
                            "nom": "Filosofia (1-BAT)",
                            "examens": [{"grup": "1-BAT-A", "aula": "A01", "assignatura": "Filosofia"}],
                        }
                    ],
                }
            ],
        }
    ]
}


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


@pytest.fixture
def client():
    centre = nova_institucio(amb_xml=True)
    nom = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, centre, "admin")
    # Els errors interns com els veu la pantalla (500 amb referència)
    return entra(TestClient(APP, base_url="https://testserver", raise_server_exceptions=False), nom)


def _falla(*_args, **_kwargs):
    raise RuntimeError(DETALL)


def _publica(client, auto_assign=False):
    return client.post(
        "/api/scheduler/publicar",
        json={"horari": HORARI, "setmanes": [{"Dilluns": DATA}], "opcions": {"auto_assign_titulars": auto_assign}},
    )


@pytest.mark.parametrize("ruta", ["/api/scheduler/costos-professors", "/api/scheduler/restriccions"])
def test_si_no_es_poden_llegir_els_costos_es_un_error_intern(client, monkeypatch, caplog, ruta):
    monkeypatch.setattr(CostProfessorRepository, "get_all", _falla)
    resp = client.get(ruta)
    assert resp.status_code == 500
    assert set(resp.json()) == {"error_ref"}
    assert DETALL in caplog.text


def test_si_no_es_poden_llegir_les_hores_lectives_publicar_es_un_error_intern(client, monkeypatch, caplog):
    class DiaQueFalla:
        de_text = staticmethod(_falla)

    monkeypatch.setattr(publicacio, "Dia", DiaQueFalla)
    resp = _publica(client)
    assert resp.status_code == 500
    assert set(resp.json()) == {"error_ref"}
    assert DETALL in caplog.text


def test_un_dia_que_no_es_pot_publicar_dona_un_missatge_generic(client, monkeypatch, caplog):
    monkeypatch.setattr(publicacio.PublicacioExamens, "publica_dia", _falla)
    resum = _publica(client).json()
    assert resum["success"] is False
    assert len(resum["errors"]) == 1
    assert resum["errors"][0].startswith(f"{DATA}: no s'ha pogut publicar aquest dia")
    assert DETALL not in resum["errors"][0]
    assert DETALL in caplog.text


def test_si_no_es_poden_assignar_els_titulars_dona_un_missatge_generic(client, monkeypatch, caplog):
    monkeypatch.setattr(publicacio, "calcula_assignacio", _falla)
    resum = _publica(client, auto_assign=True).json()
    assert resum["success"] is False
    assert len(resum["errors"]) == 1
    assert resum["errors"][0].startswith(f"{DATA}: no s'han pogut assignar els titulars")
    assert DETALL not in resum["errors"][0]
    assert DETALL in caplog.text


def test_un_xml_il_legible_no_es_substitueix_per_unes_hores_per_defecte(tmp_path):
    xml = tmp_path / "trencat.xml"
    xml.write_text("<Teachers_Timetable><Day name='Dilluns'>", encoding="utf-8")
    with pytest.raises(ET.ParseError):
        _hores_lectives_des_de_xml(str(xml), fallback=["09:00"])


def test_desar_la_configuracio_es_tot_o_res(client, monkeypatch):
    client.put("/api/scheduler/config", json={"durada_titular": 1, "durada_examen": 1})
    originals = {nom: getattr(ConfiguracioRepository, nom) for nom in ("set", "desa")}

    def falla_a_les_durades(nom):
        def escriu(db, clau, *args, **kwargs):
            if clau == "scheduler_durades_grups":
                raise RuntimeError(DETALL)
            return originals[nom](db, clau, *args, **kwargs)

        return staticmethod(escriu)

    for nom in originals:
        monkeypatch.setattr(ConfiguracioRepository, nom, falla_a_les_durades(nom))
    resp = client.put("/api/scheduler/config", json={"durada_titular": 3, "durada_examen": 4, "durades_grups": []})
    assert resp.status_code == 500
    monkeypatch.undo()
    config = client.get("/api/scheduler/config").json()
    assert (config["durada_titular"], config["durada_examen"]) == (1, 1)
