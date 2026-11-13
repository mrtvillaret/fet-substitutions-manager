"""
Centres (/api/settings/institucions): els gestiona el superadmin.
"""

import shutil
import uuid

import pytest
from fastapi import Depends
from suport_api import CONTRASENYA, client_per, crea_app, crea_usuari, entra, nova_institucio
from suport_noms import unic

from auth.dependencies import require_admin
from auth.repositories import UserRepository
from centres import router as centres
from config.settings import config
from configuracio.repositories import ConfiguracioRepository
from database import DATA_BASE_DIR, AuthSessionLocal, get_data_db_session
from rate_limit import limiter

APP = crea_app()
APP.include_router(centres.router, dependencies=[Depends(require_admin)])  # com a main.py
URL = "/api/settings/institucions"


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


def _superadmin():
    nom = f"super_{unic()}"
    crea_usuari(nom, nova_institucio(), "super_admin")
    return entra(client_per(APP), nom)


def test_crear_un_centre_desa_i_mostra_el_nom_visible():
    superadmin = _superadmin()
    centre = f"centre_{unic()}"
    nom_visible = "Centre de prova"

    resposta = superadmin.post(URL, json={"nom": centre, "display_name": nom_visible})

    assert resposta.status_code == 200, resposta.text
    assert resposta.json() == {"success": True, "institucio": centre}
    with get_data_db_session(centre) as db:
        assert ConfiguracioRepository.nom_visible_institucio(db, centre) == nom_visible
    institucions = {fila["slug"]: fila for fila in superadmin.get(URL).json()["institucions"]}
    assert institucions[centre] == {"slug": centre, "display_name": nom_visible, "active": True}


@pytest.mark.parametrize("nom", ["../fora", "Centre E", ".amagat", "", "a/b"])
def test_un_nom_de_centre_no_valid_dona_400_i_no_crea_res(nom):
    # Abans: 500 (el ValueError de la carpeta no es controlava)
    superadmin = _superadmin()
    abans = sorted(DATA_BASE_DIR.iterdir())

    resposta = superadmin.post(URL, json={"nom": nom})

    assert resposta.status_code == 400, resposta.text
    assert resposta.json()["detail"] == "Nom de centre no vàlid"
    assert sorted(DATA_BASE_DIR.iterdir()) == abans


def test_un_nom_de_centre_de_mes_de_64_caracters_dona_400_i_no_crea_res():
    # Abans: 500 (el sistema de fitxers no accepta noms tan llargs)
    superadmin = _superadmin()
    abans = sorted(DATA_BASE_DIR.iterdir())

    for nom in ("a" * 65, "a" * 300):
        resposta = superadmin.post(URL, json={"nom": nom})
        assert resposta.status_code == 400, resposta.text
        assert resposta.json()["detail"] == "El nom del centre pot tenir com a molt 64 caràcters"
    assert sorted(DATA_BASE_DIR.iterdir()) == abans

    nom = f"c{uuid.uuid4().hex}".ljust(64, "x")
    assert superadmin.post(URL, json={"nom": nom}).status_code == 200
    assert (DATA_BASE_DIR / nom / "gestor.db").exists()


def test_es_pot_canviar_el_nom_visible_d_un_centre_desactivat():
    # Abans donava 404: només el buscava entre els actius
    superadmin = _superadmin()
    centre = nova_institucio()
    config.set_institucio_activa(centre, False)

    resposta = superadmin.put(f"{URL}/{centre}", json={"display_name": "Nom nou"})

    assert resposta.status_code == 200, resposta.text
    with get_data_db_session(centre) as db:
        assert ConfiguracioRepository.nom_visible_institucio(db, centre) == "Nom nou"


def test_un_centre_que_no_existeix_continua_donant_404():
    assert _superadmin().put(f"{URL}/no_hi_es", json={"display_name": "X"}).status_code == 404


def _usuaris_actius(centre):
    with AuthSessionLocal() as db:
        return sorted((u.username, bool(u.active)) for u in UserRepository.list_by_institucio(db, centre))


def test_desactivar_un_centre_no_desactiva_els_usuaris_pero_no_hi_poden_entrar():
    # Abans es desactivaven tots (admins inclosos) i en reactivar el centre
    # s'havien de reactivar un per un. Ara n'hi ha prou amb el centre: cada
    # petició i l'entrada comproven que és actiu.
    superadmin = _superadmin()
    centre = nova_institucio()
    admin, usuari = f"admin_{unic()}", f"user_{unic()}"
    crea_usuari(admin, centre, "admin")
    crea_usuari(usuari, centre, "user")
    ja_dins = entra(client_per(APP), usuari)  # una sessió oberta abans de desactivar-lo
    abans = _usuaris_actius(centre)

    assert superadmin.put(f"{URL}/{centre}/status", json={"active": False}).status_code == 200

    assert _usuaris_actius(centre) == abans  # tots continuen actius
    for nom in (admin, usuari):
        resposta = client_per(APP).post("/api/login", json={"username": nom, "password": CONTRASENYA})
        assert resposta.status_code == 401, nom
    assert ja_dins.get("/api/users/profile").status_code == 403
    assert ja_dins.get(URL).status_code == 403

    assert superadmin.put(f"{URL}/{centre}/status", json={"active": True}).status_code == 200

    assert ja_dins.get("/api/users/profile").status_code == 200
    assert entra(client_per(APP), admin).get(URL).status_code == 200


def test_el_superadmin_continua_treballant_en_un_centre_desactivat():
    # Abans: 403 a tot (també reactivar-lo, canviar de centre o tornar a
    # entrar), tot i que a l'entrada el superadmin sí que hi entra.
    nom = f"super_{unic()}"
    centre, altre = nova_institucio(), nova_institucio()
    crea_usuari(nom, centre, "super_admin")
    superadmin = entra(client_per(APP), nom)

    assert superadmin.put(f"{URL}/{centre}/status", json={"active": False}).status_code == 200

    assert superadmin.get("/api/users/profile").status_code == 200
    assert superadmin.get(URL).json()["actual"] == centre
    assert entra(client_per(APP), nom).get(URL).status_code == 200  # també en tornar a entrar
    assert superadmin.put(f"{URL}/{centre}/status", json={"active": True}).status_code == 200
    assert config.is_institucio_activa(centre)
    config.set_institucio_activa(centre, False)
    assert superadmin.post("/api/users/profile/institucio", json={"institucio": altre}).status_code == 200


def _esborra_carpeta(centre):
    """Com l'esborrat definitiu des del servidor: la carpeta ja no hi és."""
    shutil.rmtree(DATA_BASE_DIR / centre)


CENTRE_INEXISTENT = {"detail": "El centre d'aquesta sessió ja no existeix: torna a entrar o canvia de centre"}


def test_superadmin_amb_la_sessio_en_un_centre_que_ja_no_existeix_pot_sortir_i_canviar_de_centre():
    # Abans: 500 a tot fins que canviava de centre
    nom = f"super_{unic()}"
    propi, esborrat = nova_institucio(), nova_institucio()
    crea_usuari(nom, propi, "super_admin")
    superadmin = entra(client_per(APP), nom)
    assert superadmin.post("/api/users/profile/institucio", json={"institucio": esborrat}).status_code == 200
    _esborra_carpeta(esborrat)

    for metode, url in [("GET", "/api/users/profile"), ("GET", URL), ("PUT", f"{URL}/{propi}/status")]:
        resposta = superadmin.request(metode, url, json={"active": True})
        assert resposta.status_code == 409, (url, resposta.text)
        assert resposta.json() == CENTRE_INEXISTENT
    assert not (DATA_BASE_DIR / esborrat).exists()  # no es torna a crear

    assert superadmin.post("/api/users/profile/institucio", json={"institucio": propi}).status_code == 200
    assert superadmin.get(URL).json()["actual"] == propi
    assert not (DATA_BASE_DIR / esborrat).exists()


def test_amb_la_sessio_en_un_centre_que_ja_no_existeix_es_pot_sortir():
    nom = f"user_{unic()}"
    centre = nova_institucio()
    crea_usuari(nom, centre, "user")
    usuari = entra(client_per(APP), nom)
    _esborra_carpeta(centre)
    try:
        resposta = usuari.get("/api/users/profile")
        assert resposta.status_code == 409, resposta.text
        assert resposta.json() == CENTRE_INEXISTENT
        # canviar de centre és només del superadmin
        assert usuari.post("/api/users/profile/institucio", json={"institucio": centre}).status_code == 403
        assert usuari.post("/api/logout").status_code == 200
        assert usuari.get("/api/users/profile").status_code == 401
        assert not (DATA_BASE_DIR / centre).exists()
    finally:
        # L'esborrat definitiu també n'esborra els usuaris: que no en quedi cap
        # d'un centre sense carpeta per als altres tests
        with AuthSessionLocal() as db:
            UserRepository.delete(db, UserRepository.get_by_username(db, nom))
            db.commit()
