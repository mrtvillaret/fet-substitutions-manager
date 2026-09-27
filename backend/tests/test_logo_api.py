"""
Pujada del logo (routes/files.py, upload-logo): només s'accepten imatges PNG
o JPG de debò, i el que es desa és sempre una còpia nova en PNG, reduïda.
"""
import io
import uuid

import pytest
from PIL import Image

from database import get_data_db_session, get_data_dir_for_institucio
from rate_limit import limiter
from repositories import ConfiguracioRepository
from routes import files
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio

APP = crea_app(files.router)
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
