"""
En crear, canviar o esborrar una baixa o una activitat a «No substituir», les
llistes que fan servir el motor i les validacions (config.constants) es
recarreguen de seguida, sense haver de reiniciar ni desar les prioritats.
"""

import uuid
from datetime import date, timedelta

import pytest
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio

from absencia_coberta.router import router as absencia_coberta_router
from database import get_data_db_session
from prioritats.router import router as prioritats_router
from rate_limit import limiter
from routes import pdf, settings
from substitucions import router as substitucions
from substitucions.repositories import SubstitucioRepository

APP = crea_app(substitucions.router, pdf.router, prioritats_router, absencia_coberta_router, settings.router)
_avui = date.today()
# Un dilluns passat: la baixa no hi treu res (absencia_coberta/services.py), però s'hi ha de veure.
DATA = (_avui - timedelta(days=_avui.weekday() + 7)).isoformat()


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


@pytest.fixture
def centre():
    return nova_institucio(amb_xml=True)


@pytest.fixture
def client(centre):
    nom = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, centre, "admin")
    return entra(client_per(APP), nom)


def _avis_baixa(client):
    avisos = client.get(f"/api/pdf/{DATA}/validacions").json()["warnings"]
    return any("Prof 3 té una absència coberta" in a for a in avisos)


def test_una_baixa_nova_es_te_en_compte_de_seguida(client, centre):
    resp = client.put(
        f"/api/substitucions/{DATA}/absencies/Prof 15", json={"hores_absencia": ["10:00"], "updated_at_map": {}}
    )
    assert resp.status_code == 200, resp.text
    with get_data_db_session(centre) as db:
        fila = next(f for f in SubstitucioRepository.get_by_date(db, DATA) if f["hora"] == "10:00")
        SubstitucioRepository.update(db, int(fila["id"]), {"substitut": "Prof 3"})
        db.commit()
    assert not _avis_baixa(client)

    resp = client.post(
        "/api/absencies-cobertes",
        json={"professor": "Prof 3", "data_inici": DATA, "data_final": DATA, "motiu": ""},
    )
    assert resp.status_code == 200, resp.text
    assert _avis_baixa(client)

    baixa_id = resp.json()["id"]
    resp = client.put(
        f"/api/absencies-cobertes/{baixa_id}",
        json={"professor": "Prof 3", "data_inici": "2020-09-01", "data_final": "2020-09-30", "motiu": ""},
    )
    assert resp.status_code == 200, resp.text
    assert not _avis_baixa(client)

    client.put(
        f"/api/absencies-cobertes/{baixa_id}",
        json={"professor": "Prof 3", "data_inici": DATA, "data_final": DATA, "motiu": ""},
    )
    assert _avis_baixa(client)
    assert client.delete(f"/api/absencies-cobertes/{baixa_id}").status_code == 200
    assert not _avis_baixa(client)


def test_no_substituir_es_te_en_compte_de_seguida(client):
    def no_substituir():
        resp = client.get("/api/settings")
        assert resp.status_code == 200, resp.text
        return resp.json()["no_substituir"]

    assert "Pares" not in no_substituir()
    assert client.post("/api/prioritats/no-substituir", json={"assignatura": "Pares"}).status_code == 200
    assert "Pares" in no_substituir()
    assert client.delete("/api/prioritats/no-substituir/Pares").status_code == 200
    assert "Pares" not in no_substituir()
