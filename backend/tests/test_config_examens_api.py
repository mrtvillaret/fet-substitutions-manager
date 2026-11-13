"""
Configuració d'exàmens (/api/config/*): nivells, assignatures, grups, aules i
assignacions. La configuració no es sincronitza mai amb l'XML.
"""

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio
from suport_noms import unic

from auth.dependencies import require_admin
from configuracio_examens import router as config_examens
from configuracio_examens.importacio import llegeix_csv
from configuracio_examens.repositories import ConfiguracioExamenRepository, MasterConfigRepository
from database import get_data_db_session
from errors_domini import NoValid
from grups.repositories import AbreviaturaGrupRepository
from grups.router import router_admin as grups_admin_router
from rate_limit import limiter
from vigilancies.assignacio import get_vigilancies_afinitats
from vigilancies.router import router_admin as vigilancies_admin_router

APP = crea_app()
APP.include_router(config_examens.router, dependencies=[Depends(require_admin)])  # com a main.py
APP.include_router(grups_admin_router, dependencies=[Depends(require_admin)])  # abreviatures
APP.include_router(vigilancies_admin_router, dependencies=[Depends(require_admin)])  # afinitats
C = "/api/config"


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


@pytest.fixture
def centre():
    return nova_institucio()


@pytest.fixture
def admin(centre):
    nom = f"admin_{unic()}"
    crea_usuari(nom, centre, "admin")
    client = entra(client_per(APP), nom)
    assert client.post(f"{C}/nivells", json={"codi": "1-ESO"}).status_code == 200
    return client


def _assignatures(centre, nivell="1-ESO"):
    with get_data_db_session(centre) as db:
        return MasterConfigRepository.get_assignatures_per_nivell(db, nivell)


def _aules(centre):
    with get_data_db_session(centre) as db:
        return MasterConfigRepository.get_aules(db)


# ------------------------------------------------------------ noms nets (E2)


def test_una_assignatura_nova_es_desa_amb_el_nom_net(admin, centre):
    assert admin.post(f"{C}/assignatures/1-ESO", json={"nom": " Matemàtiques "}).status_code == 200
    assert _assignatures(centre) == ["Matemàtiques"]
    # és la mateixa
    assert admin.post(f"{C}/assignatures/1-ESO", json={"nom": "Matemàtiques"}).status_code == 400


def test_els_canvis_de_nom_d_assignatura_i_d_aula_deixen_el_nom_net(admin, centre):
    admin.post(f"{C}/assignatures/1-ESO", json={"nom": "Mates"})
    admin.post(f"{C}/grups/1-ESO", json={"codi": "1-ESO-A"})
    admin.post(f"{C}/aules", json={"codi": "A1"})
    with get_data_db_session(centre) as db:
        ConfiguracioExamenRepository.create(db, "Mates", "1-ESO-A", None, "A1")
        db.commit()

    assert admin.put(f"{C}/assignatures/1-ESO/Mates", json={"nou_nom": " Matemàtiques "}).status_code == 200
    assert admin.put(f"{C}/aules/A1", json={"nou_nom": " A01 "}).status_code == 200

    assert _assignatures(centre) == ["Matemàtiques"]
    assert _aules(centre) == ["A01"]
    with get_data_db_session(centre) as db:
        assignacio = ConfiguracioExamenRepository.get_all(db)[0]
    assert (assignacio["assignatura"], assignacio["aula"]) == ("Matemàtiques", "A01")


def test_un_nom_de_nomes_espais_es_buit_i_no_es_desa(admin, centre):
    assert admin.post(f"{C}/assignatures/1-ESO", json={"nom": "   "}).status_code == 400
    assert _assignatures(centre) == []


# ------------------------------------------------- canvi de nom per nivell (E3)


def test_canviar_el_nom_d_una_assignatura_nomes_afecta_els_grups_del_seu_nivell(admin, centre):
    # Abans canviava totes les assignacions amb aquell nom, de qualsevol nivell.
    # Els grups de cada nivell són els de la configuració d'exàmens, no els de l'XML.
    admin.post(f"{C}/nivells", json={"codi": "2-ESO"})
    for nivell, grup in (("1-ESO", "1-ESO-A"), ("2-ESO", "2-ESO-A")):
        admin.post(f"{C}/assignatures/{nivell}", json={"nom": "Mates"})
        admin.post(f"{C}/grups/{nivell}", json={"codi": grup})
    for grup in ("1-ESO-A", "2-ESO-A", "1-ESO-B"):  # 1-ESO-B no és a la configuració
        admin.post(f"{C}/assignacions", json={"assignatura": "Mates", "grup": grup})

    assert admin.put(f"{C}/assignatures/1-ESO/Mates", json={"nou_nom": "Matemàtiques"}).status_code == 200

    with get_data_db_session(centre) as db:
        assignacions = {a["grup"]: a["assignatura"] for a in ConfiguracioExamenRepository.get_all(db)}
    assert assignacions == {"1-ESO-A": "Matemàtiques", "2-ESO-A": "Mates", "1-ESO-B": "Mates"}
    assert _assignatures(centre, "2-ESO") == ["Mates"]


# --------------------------------- esborrar diu quantes assignacions ho fan servir (E5)


def _amb_assignacions(admin):
    admin.post(f"{C}/grups/1-ESO", json={"codi": "1-ESO-A"})
    admin.post(f"{C}/grups/1-ESO", json={"codi": "1-ESO-B"})
    admin.post(f"{C}/aules", json={"codi": "A1"})
    for grup, aula in (("1-ESO-A", "A1"), ("1-ESO-A", ""), ("1-ESO-B", "A1"), ("2-ESO-A", "A1")):
        admin.post(f"{C}/assignacions", json={"assignatura": "Mates", "grup": grup, "aula": aula})


def _assignacions(centre):
    with get_data_db_session(centre) as db:
        return sorted((a["grup"], a["aula"]) for a in ConfiguracioExamenRepository.get_all(db))


@pytest.mark.parametrize(
    "ruta, quantes",
    [
        ("grups/1-ESO-A", 2),  # les del grup
        ("aules/A1", 3),  # les de l'aula
        ("nivells/1-ESO", 3),  # les dels grups del nivell (segons la configuració: 2-ESO-A no hi és)
    ],
)
def test_esborrar_diu_quantes_assignacions_ho_fan_servir_i_no_les_toca(admin, centre, ruta, quantes):
    _amb_assignacions(admin)
    abans = _assignacions(centre)

    resposta = admin.delete(f"{C}/{ruta}")

    assert resposta.status_code == 200
    assert resposta.json()["assignacions"] == quantes
    assert _assignacions(centre) == abans


def test_esborrar_el_que_no_fa_servir_ningu_diu_zero(admin):
    admin.post(f"{C}/aules", json={"codi": "A9"})
    assert admin.delete(f"{C}/aules/A9").json()["assignacions"] == 0


# -------------------------------------------------- importacions atòmiques (E6)


def _estat_config(centre):
    with get_data_db_session(centre) as db:
        return {
            "abreviatures": AbreviaturaGrupRepository.get_all(db),
            "afinitats": get_vigilancies_afinitats(db),
            "nivells": MasterConfigRepository.get_nivells(db),
            "aules": MasterConfigRepository.get_aules(db),
            "assignacions": [(a["assignatura"], a["grup"]) for a in ConfiguracioExamenRepository.get_all(db)],
        }


def _falla_a_la_segona_assignacio(monkeypatch):
    crea = ConfiguracioExamenRepository.create
    crides = []

    def crea_i_falla(*args, **kwargs):
        crides.append(1)
        if len(crides) == 2:
            raise RuntimeError("error simulat a mitja importació")
        return crea(*args, **kwargs)

    monkeypatch.setattr(ConfiguracioExamenRepository, "create", crea_i_falla)


PROPOSTES = [
    {"nivell": "3-ESO", "assignatura": "Física", "grup": "3-ESO-A", "aula": "A30"},
    {"nivell": "3-ESO", "assignatura": "Química", "grup": "3-ESO-A", "aula": "A31"},
]
CSV = "nivell,assignatura,grup,titular,aula\n3-ESO,Física,3-ESO-A,,A30\n3-ESO,Química,3-ESO-A,,A31\n"


@pytest.mark.parametrize("overwrite", [False, True])
@pytest.mark.parametrize("format", ["propostes", "csv"])
def test_una_importacio_que_falla_a_mitges_no_deixa_res_a_mitges(centre, monkeypatch, overwrite, format):
    # Abans, cada alta tenia el seu commit (i «Sobreescriu» esborrava i en feia
    # un abans d'importar): si fallava a mitges, la configuració quedava a mitges
    nom = f"admin_{unic()}"
    crea_usuari(nom, centre, "admin")
    client = entra(TestClient(APP, base_url="https://testserver", raise_server_exceptions=False), nom)
    client.post(f"{C}/nivells", json={"codi": "1-ESO"})
    client.post(f"{C}/aules", json={"codi": "A1"})
    client.post(f"{C}/assignacions", json={"assignatura": "Mates", "grup": "1-ESO-A"})
    abans = _estat_config(centre)
    _falla_a_la_segona_assignacio(monkeypatch)

    if format == "propostes":
        resposta = client.post(f"{C}/importar-assignacions", json={"propostes": PROPOSTES, "overwrite": overwrite})
    else:
        resposta = client.post(
            f"{C}/importar-assignacions-csv",
            files={"file": ("a.csv", CSV.encode(), "text/csv")},
            data={"overwrite": str(overwrite).lower()},
        )

    assert resposta.status_code == 500
    assert _estat_config(centre) == abans


# ------------------------------------------------------- cossos estrictes (E7)

COSSOS_DOLENTS = [
    ("post", "nivells", {}),
    ("post", "nivells", {"codi": 3}),
    ("post", "grups/1-ESO", {}),
    ("post", "aules", {"codi": ["A1"]}),
    ("post", "assignatures/1-ESO", {}),
    ("post", "assignacions", {"assignatura": "X"}),
    ("post", "assignacions", {"assignatura": "X", "grup": "1-ESO-A", "ordre": "primer"}),
    ("put", "assignacions/1", {"titular": 7}),
    ("delete", "assignacions", {"ids": "1"}),
    ("delete", "assignacions", {"ids": ["u"]}),
    ("post", "importar-assignacions", {"propostes": "totes"}),
    ("post", "importar-assignacions/dry-run", {"propostes": [1, 2]}),
    ("post", "importar-assignacions", {"propostes": [], "descartades": "cap"}),
    ("post", "abreviatures", {"abreviatura": "1-ESO-AB"}),
    ("post", "abreviatures", {"grups_originals": ["1-ESO-A", "1-ESO-B"], "abreviatura": "1-ESO-AB"}),
    ("put", "abreviatures/1", {"abreviatura": 3}),
    ("put", "afinitats", {"afinitats": "1-ESO"}),
    ("put", "afinitats", {"afinitats": [{"base": "1-ESO", "ordre": "2-ESO"}]}),
]


@pytest.mark.parametrize("metode, ruta, cos", COSSOS_DOLENTS)
def test_un_cos_que_no_es_el_que_toca_dona_422_i_no_canvia_res(admin, centre, metode, ruta, cos):
    # Abans eren diccionaris sense validar: alguns donaven 500, d'altres es desaven
    admin.post(f"{C}/abreviatures", json={"grups_originals": "1-ESO-A,1-ESO-B", "abreviatura": "1-ESO-X"})
    abans = _estat_config(centre)
    resposta = admin.request(metode.upper(), f"{C}/{ruta}", json=cos)
    assert resposta.status_code == 422, resposta.text
    assert _estat_config(centre) == abans


# ------------------------------------------------ afinitats desades i normalitzades


def test_les_afinitats_es_desen_i_es_llegeixen_normalitzades(admin):
    esperades = [{"base": "1-ESO", "ordre": ["1-ESO", "2-ESO"]}]

    resposta = admin.put(
        f"{C}/afinitats",
        json={"afinitats": [{"base": " 1-ESO ", "ordre": ["2-ESO", "2-ESO"]}]},
    )

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["afinitats"] == esperades
    assert admin.get(f"{C}/afinitats").json() == {"afinitats": esperades}


# ------------------------------------------------- abreviatures repetides (E8)


def test_una_abreviatura_dels_mateixos_grups_que_una_altra_dona_409(admin, centre):
    # Abans: 500 (la restricció d'unicitat de la BD, sense controlar)
    url = f"{C}/abreviatures"
    primera = admin.post(url, json={"grups_originals": "1-ESO-A,1-ESO-B", "abreviatura": "1-ESO-AB"}).json()
    segona = admin.post(url, json={"grups_originals": "1-ESO-C,1-ESO-D", "abreviatura": "1-ESO-CD"}).json()
    abans = _estat_config(centre)

    creada = admin.post(url, json={"grups_originals": "1-ESO-A,1-ESO-B", "abreviatura": "1-ESO-X"})
    editada = admin.put(f"{url}/{segona['id']}", json={"grups_originals": "1-ESO-A,1-ESO-B"})

    for resposta in (creada, editada):
        assert resposta.status_code == 409, resposta.text
        assert resposta.json()["detail"] == "Ja hi ha una abreviatura per a aquests grups"
    assert _estat_config(centre) == abans
    # Editar-ne una amb els seus mateixos grups sí que es pot
    assert admin.put(f"{url}/{primera['id']}", json={"grups_originals": "1-ESO-A,1-ESO-B"}).status_code == 200


# ---------------------------------------------- CSV sense nom o no UTF-8 (E9)


@pytest.mark.parametrize("ruta", ["importar-assignacions-csv", "importar-assignacions-csv/dry-run"])
def test_un_csv_que_no_es_utf8_dona_400(admin, centre, ruta):
    # Abans: 500 (UnicodeDecodeError)
    contingut = "nivell,assignatura,grup\n1-ESO,Física i Química,1-ESO-A\n".encode("latin-1")
    abans = _estat_config(centre)
    resposta = admin.post(f"{C}/{ruta}", files={"file": ("a.csv", contingut, "text/csv")})
    assert resposta.status_code == 400, resposta.text
    assert resposta.json()["detail"] == "El fitxer CSV ha d'estar desat en UTF-8"
    assert _estat_config(centre) == abans


def test_un_csv_sense_nom_dona_400():
    # Abans: 500 (el nom era None). Amb la pantalla no passa: es prova al servei
    with pytest.raises(NoValid, match="El fitxer ha de ser CSV"):
        llegeix_csv(None, b"nivell,assignatura,grup\n")


# ------------------------------------------ els nivells no es poden editar (E4)


def test_un_nivell_no_es_pot_editar_ni_canviar_de_codi(admin, centre):
    # El codi és la clau que fa servir el planificador i el nom no es mostra
    # enlloc: un nivell es crea i s'esborra, però no es canvia
    resposta = admin.put(f"{C}/nivells/1-ESO", json={"nou_codi": "1-ESO-NOU"})
    assert resposta.status_code == 405
    with get_data_db_session(centre) as db:
        assert MasterConfigRepository.get_nivells(db) == ["1-ESO"]
    assert admin.delete(f"{C}/nivells/1-ESO").status_code == 200


# ------------------------------- la simulació compta com la importació real (2)

SENSE_TITULAR = [{"nivell": "1-ESO", "assignatura": "Mates", "grup": "1-ESO-A", "titular": "", "aula": ""}]
CSV_SENSE_TITULAR = "nivell,assignatura,grup,titular,aula\n1-ESO,Mates,1-ESO-A,,\n"


def _simula_i_importa(admin, format):
    if format == "propostes":
        cos = {"propostes": SENSE_TITULAR}
        simulacio = admin.post(f"{C}/importar-assignacions/dry-run", json=cos).json()
        real = admin.post(f"{C}/importar-assignacions", json=cos).json()
    else:
        fitxer = {"file": ("a.csv", CSV_SENSE_TITULAR.encode(), "text/csv")}
        simulacio = admin.post(f"{C}/importar-assignacions-csv/dry-run", files=fitxer).json()
        real = admin.post(f"{C}/importar-assignacions-csv", files=fitxer).json()
    return simulacio, real


@pytest.mark.parametrize("format", ["propostes", "csv"])
def test_la_simulacio_compta_l_assignacio_sense_titular_que_ja_hi_es_com_la_real(admin, centre, format):
    # Abans, la simulació la comptava com a nova i la importació real com a existent
    admin.post(f"{C}/assignacions", json={"assignatura": "Mates", "grup": "1-ESO-A"})
    abans = _estat_config(centre)

    simulacio, real = _simula_i_importa(admin, format)

    assert simulacio["ja_existien"] == 1 and simulacio["assignacions_creades"] == []
    assert {k: v for k, v in real.items() if k not in ("success", "avisos")} == {
        k: v for k, v in simulacio.items() if k != "avisos"
    }
    assert _estat_config(centre)["assignacions"] == abans["assignacions"]


def test_una_abreviatura_amb_el_mateix_text_que_una_altra_dona_409(admin, centre):
    # Abans es desava: el mateix text representava dues llistes de grups
    url = f"{C}/abreviatures"
    primera = admin.post(url, json={"grups_originals": "1-ESO-A,1-ESO-B", "abreviatura": "1-ESO-AB"}).json()
    segona = admin.post(url, json={"grups_originals": "1-ESO-C,1-ESO-D", "abreviatura": "1-ESO-CD"}).json()
    abans = _estat_config(centre)

    creada = admin.post(url, json={"grups_originals": "1-ESO-E,1-ESO-F", "abreviatura": "1-ESO-AB"})
    editada = admin.put(f"{url}/{segona['id']}", json={"abreviatura": "1-ESO-AB"})

    for resposta in (creada, editada):
        assert resposta.status_code == 409, resposta.text
        assert resposta.json()["detail"] == "Ja hi ha una abreviatura amb aquest text"
    assert _estat_config(centre) == abans
    # Editar-ne una amb el seu mateix text sí que es pot
    assert admin.put(f"{url}/{primera['id']}", json={"abreviatura": "1-ESO-AB"}).status_code == 200


# ------------------------- esborrar un nivell o un grup amb les assignacions (4)


@pytest.mark.parametrize("ruta, quantes", [("nivells/1-ESO", 3), ("grups/1-ESO-A", 2)])
def test_es_pot_saber_quantes_assignacions_el_fan_servir_abans_d_esborrar(admin, centre, ruta, quantes):
    _amb_assignacions(admin)
    resposta = admin.get(f"{C}/{ruta}/assignacions")
    assert resposta.status_code == 200, resposta.text
    assert resposta.json() == {"assignacions": quantes}


@pytest.mark.parametrize("ruta", ["nivells/9-ZZZ", "grups/9-ZZZ-A"])
def test_les_assignacions_d_un_nivell_o_grup_que_no_hi_es_donen_404(admin, ruta):
    assert admin.get(f"{C}/{ruta}/assignacions").status_code == 404


@pytest.mark.parametrize(
    "ruta, queden",
    [("nivells/1-ESO", [("2-ESO-A", "A1")]), ("grups/1-ESO-A", [("1-ESO-B", "A1"), ("2-ESO-A", "A1")])],
)
def test_esborrar_amb_les_assignacions_les_esborra_tambe(admin, centre, ruta, queden):
    _amb_assignacions(admin)

    resposta = admin.delete(f"{C}/{ruta}", params={"amb_assignacions": True})

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["assignacions_esborrades"] is True
    assert _assignacions(centre) == queden


def test_sense_esborrar_les_assignacions_es_queden_i_tornen_a_servir(admin, centre):
    _amb_assignacions(admin)
    abans = _assignacions(centre)

    assert admin.delete(f"{C}/nivells/1-ESO").json()["assignacions_esborrades"] is False
    assert _assignacions(centre) == abans
    admin.post(f"{C}/nivells", json={"codi": "1-ESO"})
    admin.post(f"{C}/grups/1-ESO", json={"codi": "1-ESO-A"})
    assert admin.get(f"{C}/grups/1-ESO-A/assignacions").json() == {"assignacions": 2}


def test_esborrar_amb_les_assignacions_es_tot_o_res(centre, monkeypatch):
    nom = f"admin_{unic()}"
    crea_usuari(nom, centre, "admin")
    client = entra(TestClient(APP, base_url="https://testserver", raise_server_exceptions=False), nom)
    client.post(f"{C}/nivells", json={"codi": "1-ESO"})
    _amb_assignacions(client)
    abans = (_estat_config(centre), _assignacions(centre))

    def falla(*_args, **_kwargs):
        raise RuntimeError("error simulat després d'esborrar les assignacions")

    monkeypatch.setattr(MasterConfigRepository, "delete_nivell", falla)

    assert client.delete(f"{C}/nivells/1-ESO", params={"amb_assignacions": True}).status_code == 500
    assert (_estat_config(centre), _assignacions(centre)) == abans
