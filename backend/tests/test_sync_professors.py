"""La sincronització d'avui és independent de la memòria cau i del dia consultat."""

import io
import uuid
from unittest.mock import Mock

from fastapi import Depends
from fastapi.testclient import TestClient
from suport_api import crea_app, crea_usuari, entra, nova_institucio
from suport_xml import amb_horari_futur, dia, professor_que_plega

from auth.dependencies import get_current_user, require_admin
from database import get_data_db_session
from horari.context import get_horari
from horari.repositories import ProfessorRepository, XMLVersionRepository
from horari.router import router, router_admin
from models import Professor
from rate_limit import limiter

APP = crea_app()
APP.include_router(router, dependencies=[Depends(get_current_user)])
APP.include_router(router_admin, dependencies=[Depends(require_admin)])
XML = b'<Teachers_Timetable><Teacher name="Prof nou"><Day name="Dilluns"><Hour name="09:00"/></Day></Teacher></Teachers_Timetable>'


def _client(centre):
    limiter.reset()
    nom = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, centre, "admin")
    return entra(TestClient(APP, base_url="https://testserver", raise_server_exceptions=False), nom)


def _estat(centre):
    with get_data_db_session(centre) as db:
        return {p.nom: (p.actiu, p.ultima_aparicio) for p in db.query(Professor).all()}


def _versio(centre, path):
    with get_data_db_session(centre) as db:
        return next(v.id for v in XMLVersionRepository.list_all(db) if v.path == path)


def test_pujar_xml_sincronitza_abans_de_la_resposta():
    centre = nova_institucio()
    client = _client(centre)
    resposta = client.post("/api/files/upload-xml", files={"file": ("nou.xml", io.BytesIO(XML), "application/xml")})
    assert resposta.status_code == 200, resposta.text
    assert _estat(centre) == {"Prof nou": (True, dia(0))}


def test_canviar_la_versio_vigent_sincronitza_i_esborrar_la_restaura():
    centre = amb_horari_futur()
    client = _client(centre)
    # Prepara els actius d'avui; l'edició següent és una altra operació.
    assert client.get("/api/professors").status_code == 200
    versio = _versio(centre, "futur.xml")
    assert (
        client.put(f"/api/settings/xml-versions/{versio}", json={"data_inici": dia(-1).isoformat()}).status_code == 200
    )
    assert _estat(centre)[professor_que_plega()][0] is False
    assert client.delete(f"/api/settings/xml-versions/{versio}").status_code == 200
    assert _estat(centre)[professor_que_plega()][0] is True


def test_primera_peticio_del_dia_sincronitza_avui_amb_cache_calenta_i_data_passada(rellotge_fix, monkeypatch):
    centre = amb_horari_futur()
    client = _client(centre)
    # La versió futura ja és a la memòria cau abans d'entrar en vigor.
    get_horari(centre, data_iso=dia(4).isoformat())
    lectura = Mock(wraps=ProfessorRepository.sync_from_xml)
    monkeypatch.setattr(ProfessorRepository, "sync_from_xml", lectura)
    assert client.get("/api/professors", params={"data": dia(-2).isoformat()}).status_code == 200
    assert _estat(centre)[professor_que_plega()][0] is True
    assert lectura.call_count == 1
    assert client.get("/api/hores").status_code == 200
    assert lectura.call_count == 1
    rellotge_fix.avanca(days=3)
    client = _client(centre)  # la sessió anterior ha caducat després de tres dies
    assert client.get("/api/professors", params={"data": dia(-5).isoformat()}).status_code == 200
    assert _estat(centre)[professor_que_plega()][0] is False
    assert lectura.call_count == 2


def test_error_de_sync_no_bloqueja_ni_es_memoritza(monkeypatch, caplog):
    """Un error de sincronització (p. ex. XML vigent il·legible) no fa fallar la
    petició: queda al registre i es reintenta passada l'espera."""
    from horari import sincronitzacio

    centre = nova_institucio(amb_xml=True)
    client = _client(centre)
    real = ProfessorRepository.sync_from_xml
    lectura = Mock(side_effect=OSError("sync de prova"))
    ara = [1000.0]
    monkeypatch.setattr(sincronitzacio.time, "monotonic", lambda: ara[0])
    monkeypatch.setattr(ProfessorRepository, "sync_from_xml", lectura)
    assert client.get("/api/professors").status_code == 200
    assert "No s'han pogut sincronitzar" in caplog.text
    monkeypatch.setattr(ProfessorRepository, "sync_from_xml", real)
    ara[0] += sincronitzacio.REINTENT_DESPRES_D_ERROR + 1
    assert client.get("/api/professors").status_code == 200
    assert _estat(centre)
    assert centre not in sincronitzacio._ultim_error


def test_llegir_horari_no_escriu_en_una_altra_sessio(monkeypatch):
    centre = nova_institucio(amb_xml=True)
    lectura = Mock(side_effect=AssertionError("una lectura no sincronitza"))
    monkeypatch.setattr(ProfessorRepository, "sync_from_xml", lectura)
    assert get_horari(centre, data_iso=dia(0).isoformat()).professors
    lectura.assert_not_called()


def test_error_de_sync_desfa_el_canvi_de_versio(monkeypatch):
    centre = amb_horari_futur()
    client = _client(centre)
    assert client.get("/api/professors").status_code == 200
    abans = _estat(centre)
    versio = _versio(centre, "futur.xml")
    monkeypatch.setattr(ProfessorRepository, "sync_from_xml", Mock(side_effect=OSError("sync de prova")))
    resposta = client.put(f"/api/settings/xml-versions/{versio}", json={"data_inici": dia(-1).isoformat()})
    assert resposta.status_code == 500
    with get_data_db_session(centre) as db:
        assert XMLVersionRepository.vigent(db).path == "actual.xml"
    assert _estat(centre) == abans
