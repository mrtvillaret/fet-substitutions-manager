"""
Pujada del logo (configuracio/router.py, upload-logo): només s'accepten imatges PNG
o JPG de debò, i el que es desa és sempre una còpia nova en PNG, reduïda.
/api/settings diu si el centre té logo (te_logo), perquè la pantalla no el
demani si no en té: no tenir-ne és normal, no un error.
"""

import io
import uuid

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.exc import OperationalError
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio

from configuracio import router as configuracio
from database import get_data_db_session, get_data_dir_for_institucio
from models import Configuracio
from rate_limit import limiter
from repositories import ConfiguracioRepository

APP = crea_app(configuracio.router)
URL = "/api/files/upload-logo"


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


@pytest.fixture
def centre():
    return nova_institucio()


def _usuari_de(institucio, role="admin"):
    nom = f"{role}_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, institucio, role)
    return entra(client_per(APP), nom)


@pytest.fixture
def client(centre):
    return _usuari_de(centre)


def _imatge(format="PNG", mida=(40, 20), mode="RGB"):
    buffer = io.BytesIO()
    Image.new(mode, mida, "white").save(buffer, format=format)
    return buffer.getvalue()


def _puja(client, contingut, nom="logo.png"):
    return client.post(URL, files={"file": (nom, contingut, "image/png")})


def _logo_desat(centre):
    with get_data_db_session(centre) as db:
        return ConfiguracioRepository.get(db, "logo_path")


def test_nomes_els_admins_poden_pujar_el_logo(centre):
    assert _puja(_usuari_de(centre, role="user"), _imatge()).status_code == 403


@pytest.mark.parametrize("format, nom", [("PNG", "logo.png"), ("JPEG", "escut.jpg")])
def test_es_desa_una_copia_en_png(client, centre, format, nom):
    resp = _puja(client, _imatge(format), nom=nom)
    assert resp.status_code == 200, resp.text
    desat = get_data_dir_for_institucio(centre) / "logo.png"
    assert _logo_desat(centre) == str(desat)
    with Image.open(desat) as imatge:
        assert imatge.format == "PNG" and imatge.size == (40, 20)


def test_un_logo_gran_es_redueix(client, centre):
    assert _puja(client, _imatge(mida=(3000, 1500))).status_code == 200
    with Image.open(get_data_dir_for_institucio(centre) / "logo.png") as imatge:
        assert imatge.size == (1000, 500)


LOGOS_INVALIDS = {
    "text amb extensió png": (b"<script>alert(1)</script>", "logo.png"),
    "svg": (b'<svg xmlns="http://www.w3.org/2000/svg"/>', "logo.svg"),
    "gif amb extensió png": (_imatge("GIF"), "logo.png"),
    "dimensions enormes": (_imatge(mida=(6000, 5000), mode="1"), "logo.png"),
}


@pytest.mark.parametrize("contingut, nom", LOGOS_INVALIDS.values(), ids=LOGOS_INVALIDS.keys())
def test_es_rebutja_el_que_no_es_una_imatge_png_o_jpg(client, centre, contingut, nom):
    assert _puja(client, contingut, nom=nom).status_code == 400
    assert not _logo_desat(centre)
    assert not list(get_data_dir_for_institucio(centre).glob("logo*"))


# ------------------------------------------------------------------ te_logo


def _te_logo(client):
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    return resp.json()["te_logo"]


def test_un_centre_sense_logo_ho_diu_a_la_configuracio(client):
    assert _te_logo(client) is False
    assert client.get("/api/files/logo").status_code == 404


def test_despres_de_pujar_el_logo_la_configuracio_diu_que_en_te(client):
    assert _puja(client, _imatge()).status_code == 200
    assert _te_logo(client) is True
    resp = client.get("/api/files/logo")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"


def test_un_logo_a_la_carpeta_sense_configurar_tambe_compta(client, centre):
    (get_data_dir_for_institucio(centre) / "logo.jpg").write_bytes(_imatge("JPEG"))
    assert _te_logo(client) is True
    resp = client.get("/api/files/logo")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"


def test_un_logo_configurat_que_ja_no_hi_es_no_compta(client, centre):
    with get_data_db_session(centre) as db:
        ConfiguracioRepository.set(db, "logo_path", str(get_data_dir_for_institucio(centre) / "no-hi-es.png"), "")
        db.commit()
    assert _te_logo(client) is False
    assert client.get("/api/files/logo").status_code == 404


def test_el_cami_del_logo_es_desa_com_a_text_amb_la_seva_descripcio(client, centre):
    # Abans la descripció anava al camp «tipus» (argument a la posició equivocada)
    assert _puja(client, _imatge()).status_code == 200

    with get_data_db_session(centre) as db:
        fila = db.query(Configuracio).filter(Configuracio.clau == "logo_path").one()
        assert (fila.tipus, fila.descripcio) == ("string", "Path del logo de la institució")


def _logo_a_la_carpeta(centre):
    (get_data_dir_for_institucio(centre) / "logo.png").write_bytes(_imatge())


def test_si_la_bd_no_es_pot_llegir_es_fa_servir_el_logo_de_la_carpeta(client, centre, monkeypatch, caplog):
    _logo_a_la_carpeta(centre)

    def bd_que_falla(*_args, **_kwargs):
        raise OperationalError("SELECT", {}, Exception("database is locked"))

    monkeypatch.setattr(ConfiguracioRepository, "get", bd_que_falla)

    assert client.get("/api/files/logo").status_code == 200
    assert "logo_path" in caplog.text  # i queda al registre


def test_un_error_que_no_es_de_la_bd_no_es_calla(centre, monkeypatch):
    # Abans, qualsevol excepció es callava i es responia amb el logo de la carpeta
    _logo_a_la_carpeta(centre)
    client = TestClient(APP, base_url="https://testserver", raise_server_exceptions=False)
    nom = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, centre, "admin")
    entra(client, nom)

    def error_del_codi(*_args, **_kwargs):
        raise RuntimeError("error del codi")

    monkeypatch.setattr(ConfiguracioRepository, "get", error_del_codi)

    assert client.get("/api/files/logo").status_code == 500
