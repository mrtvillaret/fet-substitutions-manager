"""Atomicitat entre vigilàncies i les substitucions que en deriven."""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import object_session
from suport_api import crea_app, crea_usuari, entra, nova_institucio
from suport_noms import unic

from database import get_data_db_session
from models import Vigilancia
from substitucions import assignacio
from substitucions import router as substitucions_router
from substitucions.repositories import SubstitucioRepository
from vigilancies import services
from vigilancies.repositories import CAMPS_EDITABLES, VigilanciaRepository
from vigilancies.router import router as vigilancies_router

DATA = "2026-04-20"
URL = f"/api/vigilancies/{DATA}"
APP = crea_app(vigilancies_router, substitucions_router.router)


@pytest.fixture
def centre():
    return nova_institucio(amb_xml=True)


@pytest.fixture
def client(centre):
    nom = f"admin_{unic()}"
    crea_usuari(nom, centre, "admin")
    client_sense_excepcions = TestClient(APP, base_url="https://testserver", raise_server_exceptions=False)
    return entra(client_sense_excepcions, nom)


def _crea(client, hora="10:00", grups="2-BAT-A"):
    resposta = client.post(
        URL,
        json={
            "hora": hora,
            "tipus": "Anglès",
            "grups": grups,
            "aula": "A1",
            "vigilant": "Prof 15",
            "comentaris": "",
            "nivell": "2-BAT",
        },
    )
    assert resposta.status_code == 200, resposta.text
    return resposta.json()["vigilancia"]


def _bolcat(centre):
    with get_data_db_session(centre) as db:
        vigilancies = [
            v for files in VigilanciaRepository.get_by_date(db, date.fromisoformat(DATA)).values() for v in files
        ]
        substitucions = SubstitucioRepository.get_by_date(db, date.fromisoformat(DATA))
        return {
            "vigilancies": sorted(vigilancies, key=lambda fila: fila.id),
            "substitucions": sorted(substitucions, key=lambda fila: fila.id),
        }


@pytest.mark.parametrize("operacio", ["editar", "esborrar"])
def test_el_conflicte_retorna_la_vigilancia_actual(client, operacio):
    vigilancia = _crea(client)
    ruta = f"{URL}/{vigilancia['id']}"
    versio_antiga = "2000-01-01T00:00:00"

    if operacio == "editar":
        resposta = client.put(ruta, json={"vigilant": "", "updated_at": versio_antiga})
    else:
        resposta = client.delete(ruta, params={"updated_at": versio_antiga})

    assert resposta.status_code == 409, resposta.text
    assert resposta.json() == {
        "detail": {
            "error": "conflict",
            "message": "Aquest registre ha estat modificat per un altre usuari",
            "current_data": vigilancia,
        },
    }


def test_editar_desfa_vigilancia_i_cobertures_si_falla_la_reconciliacio(client, centre, monkeypatch):
    vigilancia = _crea(client)
    abans = _bolcat(centre)
    refresca_real = services.refresca_cobertures

    def refresca_i_falla(*args, **kwargs):
        refresca_real(*args, **kwargs)
        raise RuntimeError("error simulat després de refrescar cobertures")

    monkeypatch.setattr(services, "refresca_cobertures", refresca_i_falla)

    resposta = client.put(
        f"{URL}/{vigilancia['id']}",
        json={"vigilant": "", "updated_at": vigilancia["updated_at"]},
    )

    assert resposta.status_code == 500
    assert _bolcat(centre) == abans


def test_buidar_desfa_tots_els_vigilants_si_falla_una_de_les_hores(client, centre, monkeypatch):
    _crea(client, hora="10:00", grups="2-BAT-A")
    _crea(client, hora="11:30", grups="2-BAT-B")
    abans = _bolcat(centre)
    refresca_real = services.refresca_cobertures

    def refresca_i_falla(*args, **kwargs):
        refresca_real(*args, **kwargs)
        raise RuntimeError("error simulat a la primera hora")

    monkeypatch.setattr(services, "refresca_cobertures", refresca_i_falla)

    assert client.post(f"{URL}/clear").status_code == 500
    assert _bolcat(centre) == abans


@pytest.mark.parametrize("force", [False, True])
def test_editar_sense_cap_canvi_conserva_la_versio(client, centre, force):
    vigilancia = _crea(client)
    abans = _bolcat(centre)
    camps = {k: vigilancia[k] for k in CAMPS_EDITABLES}

    resposta = client.put(
        f"{URL}/{vigilancia['id']}", json={**camps, "updated_at": vigilancia["updated_at"], "force": force}
    )

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["updated_at"] == vigilancia["updated_at"]
    # Ni la vigilància ni la cobertura de la classe del vigilant canvien de versió.
    assert [f.tipus_absencia for f in abans["substitucions"]] == ["VIGILANCIA"]
    assert _bolcat(centre) == abans


def test_un_error_calculant_les_cobertures_no_esborra_les_que_hi_ha(client, centre, monkeypatch):
    vigilancia = _crea(client)
    abans = _bolcat(centre)
    assert [f.tipus_absencia for f in abans["substitucions"]] == ["VIGILANCIA"]

    def falla(*_args):
        raise RuntimeError("error simulat calculant les cobertures")

    monkeypatch.setattr(assignacio, "sense_classe", falla)

    resposta = client.put(
        f"{URL}/{vigilancia['id']}", json={"comentaris": "canvi", "updated_at": vigilancia["updated_at"]}
    )

    assert resposta.status_code == 500
    assert _bolcat(centre) == abans


def test_si_la_versio_canvia_entre_la_lectura_i_l_escriptura_hi_ha_conflicte(client, centre, monkeypatch):
    # Un altre desa la fila just després que l'edició n'hagi comprovat la versió.
    vigilancia = _crea(client)
    comprova_real = services._comprova_versio

    def comprova_i_un_altre_desa(vig_abans, *args):
        comprova_real(vig_abans, *args)
        db = object_session(vig_abans)
        db.query(Vigilancia).filter(Vigilancia.id == vig_abans.id).update({"comentaris": "d'un altre"})
        db.commit()

    monkeypatch.setattr(services, "_comprova_versio", comprova_i_un_altre_desa)

    resposta = client.put(f"{URL}/{vigilancia['id']}", json={"vigilant": "", "updated_at": vigilancia["updated_at"]})

    assert resposta.status_code == 409, resposta.text
    actual = resposta.json()["detail"]["current_data"]
    assert (actual["vigilant"], actual["comentaris"]) == ("Prof 15", "d'un altre")
    assert actual["updated_at"] != vigilancia["updated_at"]
    [desada] = _bolcat(centre)["vigilancies"]
    assert (desada.vigilant, desada.comentaris, desada.updated_at) == ("Prof 15", "d'un altre", actual["updated_at"])
