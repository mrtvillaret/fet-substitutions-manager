"""
Cursos acadèmics (/api/cursos): una seqüència contínua de períodes. Només es
desa la data d'inici; la de fi és el dia abans del curs següent, i l'últim
queda obert. Llegir-los, qualsevol usuari; canviar-los, només admins.
"""

import uuid
from datetime import date

import pytest
from fastapi import Depends
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio

from auth.dependencies import get_current_user
from cursos import router as cursos
from database import get_data_db_session
from horari.repositories import XMLVersionRepository
from rate_limit import limiter

APP = crea_app()
APP.include_router(cursos.router, dependencies=[Depends(get_current_user)])  # com a main.py
URL = "/api/cursos"


@pytest.fixture
def centre():
    limiter.reset()
    return nova_institucio(amb_xml=True)


def _client(centre, rol):
    nom = f"{rol}_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, centre, rol)
    return entra(client_per(APP), nom)


def test_la_data_de_fi_es_el_dia_abans_del_curs_seguent(centre):
    admin = _client(centre, "admin")
    assert admin.post(URL, json={"nom": "2026-27", "data_inici": "2026-09-07"}).json()["data_fi"] is None
    admin.post(URL, json={"nom": "2027-28", "data_inici": "2027-09-06"})

    assert [(c["nom"], c["data_inici"], c["data_fi"]) for c in admin.get(URL).json()] == [
        ("2027-28", "2027-09-06", None),
        ("2026-27", "2026-09-07", "2027-09-05"),
    ]


def test_editar_i_esborrar_reencadenen_els_cursos(centre):
    admin = _client(centre, "admin")
    primer = admin.post(URL, json={"nom": "2026-27", "data_inici": "2026-09-07"}).json()
    segon = admin.post(URL, json={"nom": "2027-28", "data_inici": "2027-09-06"}).json()

    editat = admin.put(f"{URL}/{segon['id']}", json={"nom": "2027-28", "data_inici": "2027-09-13"})
    assert editat.status_code == 200
    assert admin.get(URL).json()[1]["data_fi"] == "2027-09-12"

    assert admin.delete(f"{URL}/{segon['id']}").json() == {"success": True, "message": "Curs eliminat"}
    assert admin.get(URL).json() == [{**primer, "data_fi": None}]


def test_un_curs_inexistent_dona_404(centre):
    admin = _client(centre, "admin")
    cos = {"nom": "X", "data_inici": "2026-09-07"}
    assert admin.put(f"{URL}/999999", json=cos).json() == {"detail": "Curs no trobat"}
    assert admin.delete(f"{URL}/999999").status_code == 404


def test_l_usuari_els_llegeix_pero_no_els_canvia(centre):
    curs = _client(centre, "admin").post(URL, json={"nom": "2026-27", "data_inici": "2026-09-07"}).json()
    usuari = _client(centre, "user")

    assert usuari.get(URL).json() == [curs]
    assert usuari.post(URL, json={"nom": "X", "data_inici": "2027-09-06"}).status_code == 403
    assert usuari.put(f"{URL}/{curs['id']}", json={"nom": "X", "data_inici": "2026-09-07"}).status_code == 403
    assert usuari.delete(f"{URL}/{curs['id']}").status_code == 403


def test_avisa_del_curs_que_comencaria_amb_l_horari_de_l_anterior(centre):
    with get_data_db_session(centre) as db:
        XMLVersionRepository.create(db, path="teachers.xml", data_inici=date(2025, 7, 1), hash_contingut="a")
        XMLVersionRepository.encadena(db)
        db.commit()
    admin = _client(centre, "admin")
    admin.post(URL, json={"nom": "2025-26", "data_inici": "2025-09-08"})  # el primer: no té anterior
    futur = admin.post(URL, json={"nom": "2099-00", "data_inici": "2099-09-07"}).json()

    assert admin.get(f"{URL}/validacio-xml").json() == [
        {
            "curs_id": futur["id"],
            "curs_nom": "2099-00",
            "curs_inici": "2099-09-07",
            "xml_inici": "2025-07-01",
            "xml_path": "teachers.xml",
        }
    ]


def test_dos_cursos_no_poden_comencar_el_mateix_dia(centre):
    # Abans es creava i la cadena quedava amb una data de fi anterior a la d'inici
    admin = _client(centre, "admin")
    primer = admin.post(URL, json={"nom": "2026-27", "data_inici": "2026-09-07"}).json()
    segon = admin.post(URL, json={"nom": "2027-28", "data_inici": "2027-09-06"}).json()
    abans = admin.get(URL).json()

    creat = admin.post(URL, json={"nom": "Repetit", "data_inici": "2026-09-07"})
    editat = admin.put(f"{URL}/{segon['id']}", json={"nom": "2027-28", "data_inici": "2026-09-07"})

    for resposta in (creat, editat):
        assert resposta.status_code == 400
        assert resposta.json() == {"detail": "Ja hi ha un altre curs que comença aquest dia"}
    assert admin.get(URL).json() == abans
    # Editar un curs sense canviar-ne la data d'inici sí que es pot
    assert admin.put(f"{URL}/{primer['id']}", json={"nom": "Nou nom", "data_inici": "2026-09-07"}).status_code == 200
