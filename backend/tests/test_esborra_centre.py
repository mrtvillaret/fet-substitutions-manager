"""
L'esborrat definitiu d'un centre, des del servidor (scripts/esborra_centre.py):
diu què s'esborrarà, demana el nom del centre, en fa una còpia comprimida (la
carpeta i els usuaris) i després esborra la carpeta i els usuaris. Sobre
centres temporals.
"""

import json
import tarfile
import uuid

import pytest
from suport_api import crea_usuari, nova_institucio

from auth.repositories import UserRepository
from database import DATA_BASE_DIR, AuthSessionLocal
from scripts import esborra_centre


def _usuaris(centre):
    with AuthSessionLocal() as db:
        return sorted(u.username for u in UserRepository.list_by_institucio(db, centre))


@pytest.fixture
def centre():
    centre = nova_institucio(amb_xml=True)
    sufix = uuid.uuid4().hex[:8]
    crea_usuari(f"admin_{sufix}", centre, "admin")
    crea_usuari(f"user_{sufix}", centre, "user")
    return centre


def _executa(args, resposta, capsys):
    preguntes = []

    def entrada(pregunta):
        preguntes.append(pregunta)
        return resposta

    codi = esborra_centre.main(args, entrada=entrada)
    return codi, preguntes, capsys.readouterr().out


def test_esborra_la_carpeta_i_els_usuaris_despres_de_fer_la_copia(centre, tmp_path, capsys):
    altre = nova_institucio()
    crea_usuari(f"altre_{uuid.uuid4().hex[:8]}", altre, "admin")
    usuaris, usuaris_altre = _usuaris(centre), _usuaris(altre)
    fitxers = sorted(p.relative_to(DATA_BASE_DIR).as_posix() for p in (DATA_BASE_DIR / centre).rglob("*"))

    codi, preguntes, sortida = _executa([centre, "--copia-dir", str(tmp_path)], centre, capsys)

    assert codi == 0, sortida
    assert len(preguntes) == 1
    for nom in usuaris:  # abans de preguntar, diu què s'esborrarà
        assert nom in sortida
    assert not (DATA_BASE_DIR / centre).exists()
    assert _usuaris(centre) == []
    assert _usuaris(altre) == usuaris_altre and (DATA_BASE_DIR / altre / "gestor.db").is_file()

    [copia] = tmp_path.glob(f"{centre}_*.tar.gz")
    # En acabar: on és la còpia i que s'ha d'esborrar quan ja no calgui
    final = sortida.strip().splitlines()[-2:]
    assert final[0] == f"La còpia és a {copia}."
    assert "protecció de dades" in final[1] and "esborra-la quan ja no calgui" in final[1]
    with tarfile.open(copia) as tar:
        noms = tar.getnames()
        assert sorted(n for n in noms if n != "usuaris.json") == sorted([centre, *fitxers])
        desats = json.load(tar.extractfile("usuaris.json"))
    assert sorted(u["username"] for u in desats) == usuaris
    assert all(u["password_hash"] and u["institucio"] == centre for u in desats)


@pytest.mark.parametrize("resposta", ["", "no", "ELIMINA"])
def test_sense_la_confirmacio_no_toca_res(centre, tmp_path, capsys, resposta):
    usuaris = _usuaris(centre)

    codi, _, _ = _executa([centre, "--copia-dir", str(tmp_path)], resposta, capsys)

    assert codi != 0
    assert (DATA_BASE_DIR / centre / "gestor.db").is_file()
    assert _usuaris(centre) == usuaris
    assert list(tmp_path.iterdir()) == []


def test_no_esborra_el_centre_propi_d_un_superadmin(centre, tmp_path, capsys):
    crea_usuari(f"super_{uuid.uuid4().hex[:8]}", centre, "super_admin")
    usuaris = _usuaris(centre)

    codi, preguntes, sortida = _executa([centre, "--copia-dir", str(tmp_path)], centre, capsys)

    assert codi != 0 and preguntes == []
    assert "superadmin" in sortida
    assert (DATA_BASE_DIR / centre / "gestor.db").is_file()
    assert _usuaris(centre) == usuaris
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("nom", ["no_hi_es", "../fora", ""])
def test_un_centre_que_no_existeix_no_toca_res(tmp_path, capsys, nom):
    abans = sorted(DATA_BASE_DIR.iterdir())

    codi, preguntes, _ = _executa([nom, "--copia-dir", str(tmp_path)], nom, capsys)

    assert codi != 0 and preguntes == []
    assert sorted(DATA_BASE_DIR.iterdir()) == abans
    assert list(tmp_path.iterdir()) == []
