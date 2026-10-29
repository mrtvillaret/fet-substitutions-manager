"""L'absència coberta i tots els seus efectes es desen en una transacció."""

import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from suport_api import crea_app, crea_usuari, entra, nova_institucio

from absencia_coberta import services
from absencia_coberta.repositories import AbsenciaCobertaRepository
from absencia_coberta.router import router as absencia_coberta_router
from database import get_data_db_session
from substitucions import router as substitucions_router
from substitucions.repositories import SubstitucioRepository
from vigilancies.repositories import VigilanciaRepository
from vigilancies.router import router as vigilancies_router

AVUI = date.today()
FUTUR = (AVUI + timedelta(days=7 - AVUI.weekday())).isoformat()
PASSAT = (AVUI - timedelta(days=AVUI.weekday() + 7)).isoformat()
URL = "/api/absencies-cobertes"
APP = crea_app(substitucions_router.router, vigilancies_router, absencia_coberta_router)


@pytest.fixture
def centre():
    return nova_institucio(amb_xml=True)


@pytest.fixture
def client(centre):
    nom = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, centre, "admin")
    client_sense_excepcions = TestClient(APP, base_url="https://testserver", raise_server_exceptions=False)
    return entra(client_sense_excepcions, nom)


def _prepara_efectes(client):
    resposta = client.put(
        f"/api/substitucions/{FUTUR}/absencies/Prof 15",
        json={"hores_absencia": ["10:00"], "updated_at_map": {}},
    )
    assert resposta.status_code == 200, resposta.text
    fila = client.get(f"/api/substitucions/{FUTUR}", params={"include_all": True}).json()[0]
    resposta = client.put(
        f"/api/substitucions/{FUTUR}/10:00/Prof 15",
        json={"substitut": "Prof 3", "updated_at": fila["updated_at"]},
    )
    assert resposta.status_code == 200, resposta.text
    resposta = client.put(
        f"/api/substitucions/{FUTUR}/absencies/Prof 3",
        json={"hores_absencia": ["12:30"], "updated_at_map": {}},
    )
    assert resposta.status_code == 200, resposta.text
    resposta = client.post(
        f"/api/vigilancies/{FUTUR}",
        json={
            "hora": "11:30",
            "tipus": "Anglès",
            "grups": "2-BAT-A",
            "aula": "A1",
            "vigilant": "Prof 3",
            "comentaris": "",
            "nivell": "2-BAT",
        },
    )
    assert resposta.status_code == 200, resposta.text


def _bolcat(centre):
    with get_data_db_session(centre) as db:
        vigilancies = [v for files in VigilanciaRepository.get_by_date(db, FUTUR).values() for v in files]
        return {
            "absencies_cobertes": AbsenciaCobertaRepository.get_all(db),
            "vigilancies": sorted(vigilancies, key=lambda fila: fila["id"]),
            "substitucions": sorted(SubstitucioRepository.get_by_date(db, FUTUR), key=lambda fila: fila["id"]),
        }


def _falla_despres_de_refrescar(monkeypatch):
    refresca_real = services.refresca_cobertures

    def refresca_i_falla(*args, **kwargs):
        refresca_real(*args, **kwargs)
        raise RuntimeError("error simulat després de refrescar cobertures")

    monkeypatch.setattr(services, "refresca_cobertures", refresca_i_falla)


def test_crear_desfa_l_absencia_i_tots_els_efectes_si_falla_a_mig_aplicar(client, centre, monkeypatch):
    _prepara_efectes(client)
    abans = _bolcat(centre)
    _falla_despres_de_refrescar(monkeypatch)

    resposta = client.post(
        URL,
        json={"professor": "Prof 3", "data_inici": PASSAT, "data_final": FUTUR, "motiu": ""},
    )

    assert resposta.status_code == 500
    assert _bolcat(centre) == abans


def test_editar_desfa_l_edicio_i_tots_els_efectes_si_falla_a_mig_aplicar(client, centre, monkeypatch):
    resposta = client.post(
        URL,
        json={"professor": "Prof 3", "data_inici": PASSAT, "data_final": PASSAT, "motiu": "Inicial"},
    )
    assert resposta.status_code == 200, resposta.text
    absencia_id = resposta.json()["id"]
    _prepara_efectes(client)
    abans = _bolcat(centre)
    _falla_despres_de_refrescar(monkeypatch)

    resposta = client.put(
        f"{URL}/{absencia_id}",
        json={"professor": "Prof 3", "data_inici": PASSAT, "data_final": FUTUR, "motiu": "Editada"},
    )

    assert resposta.status_code == 500
    assert _bolcat(centre) == abans
