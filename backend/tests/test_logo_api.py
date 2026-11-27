"""
Pujada del logo (configuracio/router.py, upload-logo): només s'accepten imatges PNG
o JPG de debò, i el que es desa és sempre una còpia nova en PNG, reduïda.
/api/settings diu si el centre té logo (te_logo), perquè la pantalla no el
demani si no en té: no tenir-ne és normal, no un error.
"""

import io

import pytest
from PIL import Image
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio
from suport_noms import unic

from configuracio import router as configuracio
from configuracio.repositories import ConfiguracioRepository
from database import get_data_db_session, get_data_dir_for_institucio
from pdf import informes
from pdf import router as pdf
from rate_limit import limiter

APP = crea_app(configuracio.router, pdf.router, informes.router)
URL = "/api/files/upload-logo"


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


@pytest.fixture
def centre():
    return nova_institucio()


def _usuari_de(institucio):
    nom = f"admin_{unic()}"
    crea_usuari(nom, institucio, "admin")
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


@pytest.mark.parametrize(
    "format, nom, mida, desada",
    [
        ("PNG", "logo.png", (40, 20), (40, 20)),
        ("JPEG", "escut.jpg", (40, 20), (40, 20)),
        ("PNG", "logo.png", (3000, 1500), (1000, 500)),  # un logo gran es redueix
    ],
)
def test_es_desa_una_copia_en_png(client, centre, format, nom, mida, desada):
    resp = _puja(client, _imatge(format, mida), nom=nom)
    assert resp.status_code == 200, resp.text
    desat = get_data_dir_for_institucio(centre) / "logo.png"
    assert resp.json()["path"] == str(desat)
    with Image.open(desat) as imatge:
        assert imatge.format == "PNG" and imatge.size == desada


LOGOS_INVALIDS = {
    "text amb extensió png": (b"<script>alert(1)</script>", "logo.png"),
    "svg": (b'<svg xmlns="http://www.w3.org/2000/svg"/>', "logo.svg"),
    "gif amb extensió png": (_imatge("GIF"), "logo.png"),
    "dimensions enormes": (_imatge(mida=(6000, 5000), mode="1"), "logo.png"),
}


@pytest.mark.parametrize("contingut, nom", LOGOS_INVALIDS.values(), ids=LOGOS_INVALIDS.keys())
def test_es_rebutja_el_que_no_es_una_imatge_png_o_jpg(client, centre, contingut, nom):
    assert _puja(client, contingut, nom=nom).status_code == 400
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


# Fitxers a la carpeta del centre, logo_path desat -> si hi ha logo. Una sola
# regla (configuracio.services.cami_logo) per al PDF del dia, l'informe de
# direcció, te_logo de la configuració i /api/files/logo: el logo és el logo.*
# de la carpeta del centre; la clau logo_path (de versions anteriors) no compta.
CASOS_LOGO = {
    "sense logo": ([], None, False),
    "logo.png a la carpeta": (["logo.png"], None, True),
    "logo.jpg a la carpeta": (["logo.jpg"], None, True),
    "logo_path que ja no hi és i logo.png": (["logo.png"], "no-hi-es.png", True),
    "logo_path a un altre fitxer": (["escut.png"], "escut.png", False),
}


@pytest.mark.parametrize("fitxers, configurat, esperat", CASOS_LOGO.values(), ids=CASOS_LOGO.keys())
def test_quin_logo_porten_els_pdf(fitxers, configurat, esperat):
    centre = nova_institucio(amb_xml=True)
    carpeta = get_data_dir_for_institucio(centre)
    for nom in fitxers:
        (carpeta / nom).write_bytes(_imatge("JPEG" if nom.endswith(".jpg") else "PNG"))
    if configurat:
        with get_data_db_session(centre) as db:
            ConfiguracioRepository.set(db, "logo_path", str(carpeta / configurat), "")
            db.commit()
    client = _usuari_de(centre)
    dia = client.get("/api/pdf/complete/2026-04-20")
    direccio = client.get("/api/informes/direccio", params={"data_inici": "2026-04-20", "data_final": "2026-04-20"})
    assert dia.status_code == direccio.status_code == 200
    amb_imatge = (
        b"/Subtype /Image" in dia.content,
        b"/Subtype /Image" in direccio.content,
        _te_logo(client),
        client.get("/api/files/logo").status_code == 200,
    )
    assert amb_imatge == (esperat,) * 4
