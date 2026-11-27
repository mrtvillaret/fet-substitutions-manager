"""Rollback de les operacions compostes del mòdul de substitucions."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from suport_api import crea_app, crea_usuari, entra, nova_institucio
from suport_noms import unic

from database import get_data_db_session
from models import Substitucio
from substitucions import router as substitucions_router
from substitucions import services
from substitucions.repositories import SubstitucioRepository

DATA = "2026-04-20"
URL = f"/api/substitucions/{DATA}"
ABSENT = "Prof 15"
APP = crea_app(substitucions_router.router)


@pytest.fixture
def centre():
    return nova_institucio(amb_xml=True)


@pytest.fixture
def client(centre):
    nom = f"admin_{unic()}"
    crea_usuari(nom, centre, "admin")
    client_sense_excepcions = TestClient(APP, base_url="https://testserver", raise_server_exceptions=False)
    return entra(client_sense_excepcions, nom)


def _marca_absencia(client, professor=ABSENT, hores=None):
    return client.put(
        f"{URL}/absencies/{professor}",
        json={"hores_absencia": hores or ["10:00"], "updated_at_map": {}},
    )


def _bolcat(centre):
    with get_data_db_session(centre) as db:
        return sorted(SubstitucioRepository.get_by_date(db, DATA), key=lambda fila: fila.id)


def test_generar_desfa_tots_els_canvis_si_falla_despres_de_mutar(client, centre, monkeypatch):
    assert _marca_absencia(client).status_code == 200
    abans = _bolcat(centre)
    genera_real = services.genera_substitucions_dia

    def genera_i_falla(*args, **kwargs):
        genera_real(*args, **kwargs)
        raise RuntimeError("error simulat després de generar")

    monkeypatch.setattr(services, "genera_substitucions_dia", genera_i_falla)

    assert client.post(f"{URL}/generar").status_code == 500
    assert _bolcat(centre) == abans


def test_actualitzar_absencies_desfa_tots_els_canvis_si_falla_despres_de_mutar(client, centre, monkeypatch):
    abans = _bolcat(centre)
    desa_real = services.desa_absencies

    def desa_i_falla(*args, **kwargs):
        desa_real(*args, **kwargs)
        raise RuntimeError("error simulat després de desar absències")

    monkeypatch.setattr(services, "desa_absencies", desa_i_falla)

    assert _marca_absencia(client, hores=["10:00", "11:30"]).status_code == 500
    assert _bolcat(centre) == abans


def test_actualitzar_substitut_desfa_tots_els_canvis_si_falla_la_reconciliacio(client, centre, monkeypatch):
    assert _marca_absencia(client).status_code == 200
    abans = _bolcat(centre)
    fila = abans[0]

    def reconciliacio_que_falla(*_args, **_kwargs):
        raise RuntimeError("error simulat reconciliant encadenades")

    monkeypatch.setattr(services, "reconcilia_encadenades", reconciliacio_que_falla)

    resposta = client.put(
        f"{URL}/10:00/{ABSENT}",
        json={"substitut": "Prof 21", "updated_at": fila.updated_at},
    )
    assert resposta.status_code == 500
    assert _bolcat(centre) == abans


def test_moure_substitut_desfa_l_alliberament_si_la_fila_canvia_abans_de_desar(client, centre, monkeypatch):
    assert _marca_absencia(client).status_code == 200
    assert _marca_absencia(client, professor="Prof 30").status_code == 200
    origen, desti = _bolcat(centre)
    resposta = client.put(
        f"{URL}/10:00/{origen.professor_absent}", json={"substitut": "Prof 21", "updated_at": origen.updated_at}
    )
    assert resposta.status_code == 200, resposta.text
    abans = _bolcat(centre)
    actualitza = SubstitucioRepository.update

    def canvia_abans_de_desar(db, sub_id, canvis, **opcions):
        if sub_id == int(desti.id):
            # La petició té la reserva d'escriptura de SQLite. Injectem el canvi
            # dins de la mateixa transacció, just abans que es comprovi la versió.
            fila = db.get(Substitucio, sub_id)
            fila.updated_at = datetime(2026, 4, 20, 8)
            fila.comentaris = "Canvi intercalat"
            db.flush()
        return actualitza(db, sub_id, canvis, **opcions)

    monkeypatch.setattr(SubstitucioRepository, "update", staticmethod(canvia_abans_de_desar))

    resposta = client.put(
        f"{URL}/10:00/{desti.professor_absent}",
        json={"substitut": "Prof 21", "updated_at": desti.updated_at, "moure": True, "comentaris": "Canvi rebutjat"},
    )

    assert resposta.status_code == 409, resposta.text
    detall = resposta.json()["detail"]
    assert detall["error"] == "conflict"
    assert detall["current_data"]["id"] == desti.id
    assert detall["current_data"]["updated_at"] == desti.updated_at
    assert detall["current_data"]["comentaris"] == desti.comentaris
    assert detall["current_data"]["substitut"] == desti.substitut
    assert _bolcat(centre) == abans


def test_moure_substitut_absent_conserva_les_dues_files(client, centre):
    assert _marca_absencia(client).status_code == 200
    assert _marca_absencia(client, professor="Prof 30").status_code == 200
    assert _marca_absencia(client, professor="Prof 21").status_code == 200
    origen, desti, _ = _bolcat(centre)
    with get_data_db_session(centre) as db:
        # Reproduïm una assignació desada que ha quedat invàlida.
        SubstitucioRepository.update(
            db, int(origen.id), {"substitut": "Prof 21", "tipus_substitut": "disponible (Guàrdia)"}
        )
        db.commit()
    abans = _bolcat(centre)

    resposta = client.put(
        f"{URL}/10:00/{desti.professor_absent}",
        json={"substitut": "Prof 21", "updated_at": desti.updated_at, "moure": True},
    )

    assert resposta.status_code == 400, resposta.text
    assert resposta.json()["codi"] == "substitut_absent"
    assert _bolcat(centre) == abans


def test_reassignar_desfa_la_neteja_basica_si_falla_abans_del_final(client, centre, monkeypatch):
    assert _marca_absencia(client).status_code == 200
    with get_data_db_session(centre) as db:
        fila = SubstitucioRepository.get_by_date(db, DATA)[0]
        SubstitucioRepository.update(db, fila.id, {"substitut": "Prof 1"})
        db.commit()
    abans = _bolcat(centre)

    def generacio_que_falla(*_args, **_kwargs):
        raise RuntimeError("error simulat després de netejar substituts")

    monkeypatch.setattr(services, "genera_substitucions_dia", generacio_que_falla)

    assert client.post(f"{URL}/reassign-problematics").status_code == 500
    assert _bolcat(centre) == abans


def test_reassignar_conserva_la_base_i_desfa_tota_la_millora_si_aquesta_falla(client, centre, monkeypatch):
    assert _marca_absencia(client, hores=["10:00", "11:30"]).status_code == 200
    with get_data_db_session(centre) as db:
        files = SubstitucioRepository.get_by_date(db, DATA)
        SubstitucioRepository.update(db, files[0].id, {"substitut": "Prof 21"})
        SubstitucioRepository.update(db, files[1].id, {"substitut": "Prof 28"})
        db.commit()
        ids = [fila.id for fila in files]

    def neteja_basica(db, _data):
        SubstitucioRepository.update(db, ids[0], {"substitut": "", "tipus_substitut": ""})
        return [{"id": ids[0]}]

    class MilloraQueFalla:
        def __init__(self, *_args, **_kwargs):
            self.crides = 0

        def millor(self, _fila):
            self.crides += 1
            if self.crides == 2:
                raise RuntimeError("error simulat a mitja millora")
            return "Prof 3", "Guàrdia", "", 0

        def canvia(self, *_args):
            pass

    monkeypatch.setattr(services, "treu_substituts_no_valids", neteja_basica)
    monkeypatch.setattr(
        services,
        "genera_substitucions_dia",
        lambda *_args, **_kwargs: {"avisos": []},
    )
    monkeypatch.setattr(services, "MillorsSubstituts", MilloraQueFalla)

    resposta = client.post(f"{URL}/reassign-problematics")

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["avisos"] == [
        "No s'ha pogut millorar l'assignació segons les prioritats. Revisa les substitucions."
    ]
    despres = {fila.id: fila for fila in _bolcat(centre)}
    assert despres[ids[0]].substitut == ""
    assert despres[ids[1]].substitut == "Prof 28"
