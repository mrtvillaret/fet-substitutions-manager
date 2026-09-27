"""
Tests de les rutes de vigilàncies (routes/vigilancies.py) a través de l'API.

Descriuen el comportament actual del programa (characterization tests), no
una especificació: si algun comportament es canvia a propòsit, cal actualitzar
el test corresponent.

Treballen sobre una institució temporal amb l'horari d'exemple i les
prioritats mínimes de suport_api. Dilluns 20/04/2026 a les 10:00:
  Prof 3, Prof 21, Prof 28   fan guàrdia (sense grup)
  Prof 15                    Anglès amb 3-ESO-A
  Prof 1                     E.F. amb 3-ESO-C
  Prof 48                    Filosofia amb 1-BAT-A
"""
import uuid

import pytest

from database import get_data_db_session
from models import ConfiguracioExamen
from rate_limit import limiter
from repositories import GrupsAlliberatsRepository
from routes import substitucions, vigilancies
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio

APP = crea_app(vigilancies.router, substitucions.router)
DATA = "2026-04-20"  # dilluns
URL = f"/api/vigilancies/{DATA}"
URL_SUBS = f"/api/substitucions/{DATA}"


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


def _admin_de(institucio):
    nom = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, institucio, "admin")
    return entra(client_per(APP), nom)


@pytest.fixture
def centre():
    return nova_institucio(amb_xml=True)


@pytest.fixture
def client(centre):
    return _admin_de(centre)


def _crea(client, vigilant="", hora="10:00", grups="2-BAT-A", tipus="Anglès", nivell="2-BAT"):
    resp = client.post(URL, json={
        "hora": hora, "tipus": tipus, "grups": grups, "aula": "A1",
        "vigilant": vigilant, "comentaris": "", "nivell": nivell,
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["vigilancia"]


def _vigilancies(client):
    resp = client.get(URL)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _vigilants(client):
    return {v["grups"]: v["vigilant"] for v in _vigilancies(client)}


def _subs(client):
    files = client.get(URL_SUBS, params={"include_all": True}).json()
    return {(s["hora"], s["professor_absent"], s["assignatura"], s["tipus_absencia"]): s["substitut"]
            for s in files}


def _absent(client, professor, hores=("10:00",)):
    resp = client.put(f"{URL_SUBS}/absencies/{professor}",
                      json={"hores_absencia": list(hores), "updated_at_map": {}})
    assert resp.status_code == 200, resp.text


def _disponibles(client, hora="10:00", **params):
    resp = client.get(f"{URL}/{hora}/disponibles", params=params)
    assert resp.status_code == 200, resp.text
    return {d["value"]: d for d in resp.json()}


# ------------------------------------------------------------------ accés

def test_sense_sessio_no_es_pot_accedir():
    assert client_per(APP).get(URL).status_code == 401


def test_cada_institucio_nomes_veu_les_seves_vigilancies(client):
    _crea(client, "Prof 21")
    altre = _admin_de(nova_institucio(amb_xml=True))
    assert altre.get(URL).json() == []


# -------------------------------------------------------------- config

def test_config_treu_professors_i_hores_de_l_horari(client):
    resp = client.get("/api/vigilancies/config")
    assert resp.status_code == 200
    cfg = resp.json()
    assert "Prof 15" in cfg["professors"]
    assert cfg["hores"][:3] == ["08:00", "09:00", "10:00"]
    assert cfg["tipus_examens"][0] == "VIGILÀNCIA"
    # Sense nivells configurats, en proposa uns per defecte.
    assert "GENERAL" in cfg["nivells"]


def test_config_inclou_els_tipus_d_examen_ja_usats(client):
    _crea(client, tipus="Història")
    assert client.get("/api/vigilancies/config").json()["tipus_examens"] == ["VIGILÀNCIA", "Història"]


# ----------------------------------------------------------------- CRUD

def test_crear_i_llistar(client):
    creada = _crea(client, "Prof 21")
    assert (creada["hora"], creada["vigilant"], creada["nivell"]) == ("10:00", "Prof 21", "2-BAT")
    [vig] = _vigilancies(client)
    assert (vig["hora"], vig["grups"], vig["vigilant"]) == ("10:00", "2-BAT-A", "Prof 21")


def test_el_placeholder_de_vigilant_es_desa_buit(client):
    _crea(client, "-- selecciona vigilant --")
    assert _vigilancies(client)[0]["vigilant"] == ""


def test_crear_retorna_el_mateix_id_que_el_llistat(client):
    creada = _crea(client, "Prof 21")
    [vig] = _vigilancies(client)
    assert creada["id"] == vig["id"] == str(vig["db_id"])


def test_l_id_retornat_identifica_la_nova_encara_que_n_hi_hagi_d_altres_a_la_mateixa_hora(client):
    # Abans, amb el vigilant buit, l'ID compost apuntava a la primera vigilància
    # buida de la mateixa hora i nivell, no a la que s'acabava de crear.
    _crea(client, grups="2-BAT-A")
    nova = _crea(client, grups="2-BAT-B")
    resp = client.put(f"{URL}/{nova['id']}", json={"comentaris": "és la nova", "force": True})
    assert resp.status_code == 200
    comentaris = {v["grups"]: v["comentaris"] for v in _vigilancies(client)}
    assert comentaris == {"2-BAT-A": "", "2-BAT-B": "és la nova"}


def test_l_id_compost_antic_es_continua_acceptant(client):
    _crea(client, "Prof 21")
    resp = client.put(f"{URL}/10:00|2-BAT|0", json={"comentaris": "amb id compost", "force": True})
    assert resp.status_code == 200
    assert _vigilancies(client)[0]["comentaris"] == "amb id compost"


def test_actualitzar_demana_updated_at_i_detecta_conflictes(client):
    _crea(client, "Prof 21")
    vig = _vigilancies(client)[0]
    ruta = f"{URL}/{vig['id']}"
    assert client.put(ruta, json={"vigilant": "Prof 3"}).status_code == 400
    assert client.put(ruta, json={"vigilant": "Prof 3", "updated_at": "2000-01-01T00:00:00"}).status_code == 409
    assert client.put(ruta, json={"vigilant": "Prof 3", "updated_at": vig["updated_at"]}).status_code == 200
    assert _vigilancies(client)[0]["vigilant"] == "Prof 3"


def test_actualitzar_o_esborrar_una_vigilancia_inexistent_dona_404(client):
    assert client.put(f"{URL}/999", json={"vigilant": "Prof 3", "updated_at": "x"}).status_code == 404
    assert client.delete(f"{URL}/999", params={"updated_at": "x"}).status_code == 404


def test_esborrar_demana_updated_at(client):
    _crea(client, "Prof 21")
    vig = _vigilancies(client)[0]
    assert client.delete(f"{URL}/{vig['id']}").status_code == 400
    assert client.delete(f"{URL}/{vig['id']}", params={"updated_at": vig["updated_at"]}).status_code == 200
    assert _vigilancies(client) == []


# ------------------------------------------- substitucions derivades

def test_si_el_vigilant_te_classe_es_crea_una_substitucio_per_cobrir_la(client):
    _crea(client, "Prof 15")
    assert _subs(client) == {("10:00", "Prof 15", "Anglès", "VIGILANCIA"): ""}


def test_treure_el_vigilant_esborra_la_substitucio_derivada(client):
    _crea(client, "Prof 15")
    vig = _vigilancies(client)[0]
    client.put(f"{URL}/{vig['id']}", json={"vigilant": "", "updated_at": vig["updated_at"]})
    assert _subs(client) == {}


def test_esborrar_la_vigilancia_esborra_la_substitucio_derivada(client):
    _crea(client, "Prof 15")
    vig = _vigilancies(client)[0]
    client.delete(f"{URL}/{vig['id']}", params={"updated_at": vig["updated_at"]})
    assert _subs(client) == {}


def test_el_substitut_de_la_cobertura_es_conserva_si_es_refresca_la_vigilancia(client):
    _crea(client, "Prof 15")
    cobertura = next(s for s in client.get(URL_SUBS, params={"include_all": True}).json()
                     if s["tipus_absencia"] == "VIGILANCIA")
    resp = client.put(f"{URL_SUBS}/10:00/Prof 15",
                      json={"substitut": "Prof 3", "updated_at": cobertura["updated_at"]})
    assert resp.status_code == 200

    vig = _vigilancies(client)[0]
    client.put(f"{URL}/{vig['id']}", json={"comentaris": "canvi", "updated_at": vig["updated_at"]})
    assert _subs(client)[("10:00", "Prof 15", "Anglès", "VIGILANCIA")] == "Prof 3"


def test_si_el_vigilant_es_absent_es_crea_una_vigilancia_absent(client):
    _absent(client, "Prof 21")
    _crea(client, "Prof 21")
    tipus = {t for (_, prof, _, t) in _subs(client) if prof == "Prof 21"}
    assert "VIGILANCIA_ABSENT" in tipus


def test_qui_passa_a_vigilant_deixa_la_substitucio_de_la_mateixa_hora(client):
    _absent(client, "Prof 15")
    fila = client.get(URL_SUBS, params={"include_all": True}).json()[0]
    client.put(f"{URL_SUBS}/10:00/Prof 15", json={"substitut": "Prof 21", "updated_at": fila["updated_at"]})
    assert _subs(client)[("10:00", "Prof 15", "Anglès", "ABSENCIA")] == "Prof 21"

    _crea(client, "Prof 21")
    assert _subs(client)[("10:00", "Prof 15", "Anglès", "ABSENCIA")] == ""


# ---------------------------------------------------------- disponibles

def test_disponibles_classifica_cada_professor_segons_el_que_fa(client, centre):
    with get_data_db_session(centre) as db:
        GrupsAlliberatsRepository.set_for_date(db, DATA, {"10:00": ["3-ESO-A"]})
    _absent(client, "Prof 28")
    disp = _disponibles(client)
    assert disp["Prof 15"]["estat"] == "ALLIBERAT"   # el seu grup no té classe
    assert disp["Prof 21"]["estat"] == "DISPONIBLE"  # fa guàrdia
    assert disp["Prof 1"]["estat"] == "CLASSE"
    assert disp["Prof 28"]["estat"] == "ABSENT"


def test_disponibles_ordena_primer_els_alliberats_i_despres_els_de_guardia(client, centre):
    with get_data_db_session(centre) as db:
        GrupsAlliberatsRepository.set_for_date(db, DATA, {"10:00": ["3-ESO-A"]})
    ordre = [d["value"] for d in client.get(f"{URL}/10:00/disponibles").json()]
    assert ordre[:4] == ["Prof 15", "Prof 21", "Prof 28", "Prof 3"]


def test_disponibles_marca_qui_ja_vigila_a_aquella_hora(client):
    _crea(client, "Prof 21")
    disp = _disponibles(client)
    assert disp["Prof 21"]["ja_assignat"] is True
    assert disp["Prof 3"]["ja_assignat"] is False


def test_disponibles_marca_el_titular_de_l_examen(client, centre):
    with get_data_db_session(centre) as db:
        db.add(ConfiguracioExamen(assignatura="Anglès", grup="2-BAT-A", titular="Prof 3", aula=""))
        db.commit()
    disp = _disponibles(client, tipus="Anglès", grups="2-BAT-A")
    assert disp["Prof 3"]["es_titular"] is True
    assert disp["Prof 21"]["es_titular"] is False


def test_disponibles_en_bloc_dona_el_mateix_que_d_un_en_un(client):
    resp = client.post(f"{URL}/disponibles-batch", json={"queries": [{"hora": "10:00"}, {"hora": "11:30"}]})
    assert resp.status_code == 200
    resultats = resp.json()["results"]
    assert set(resultats) == {"10:00", "11:30"}
    assert resultats["10:00"] == client.get(f"{URL}/10:00/disponibles").json()


# ------------------------------------------------ assignació automàtica

def _comprova_assignacions_valides(client):
    vigs = _vigilancies(client)
    per_hora = {}
    for v in vigs:
        if v["vigilant"]:
            per_hora.setdefault(v["hora"], []).append(v["vigilant"])
    for hora, vigilants in per_hora.items():
        assert len(vigilants) == len(set(vigilants)), f"vigilant repetit a les {hora}"


def test_assignar_pendents_sense_disponibles_nomes_fa_servir_alliberats(client):
    _crea(client)
    resp = client.post(f"{URL}/assign/pendents")
    assert resp.status_code == 200
    assert resp.json()["assigned_count"] == 0
    assert _vigilants(client) == {"2-BAT-A": ""}


def test_assignar_pendents_amb_alliberats(client, centre):
    with get_data_db_session(centre) as db:
        GrupsAlliberatsRepository.set_for_date(db, DATA, {"10:00": ["3-ESO-A"]})
    _crea(client)
    assert client.post(f"{URL}/assign/pendents").json()["assigned_count"] == 1
    assert _vigilants(client) == {"2-BAT-A": "Prof 15"}


def test_assignar_pendents_amb_disponibles_fa_servir_professors_de_guardia(client):
    _crea(client, grups="2-BAT-A")
    _crea(client, grups="2-BAT-B")
    resp = client.post(f"{URL}/assign/pendents", params={"disponibles": True})
    assert resp.json() | {"message": ""} == {"assigned_count": 2, "remaining_count": 0, "message": ""}
    assert set(_vigilants(client).values()) <= {"Prof 3", "Prof 21", "Prof 28"}
    _comprova_assignacions_valides(client)


def test_assignar_pendents_posa_el_professor_del_grup_que_fa_l_examen(client):
    # Prof 48 té classe amb 1-BAT-A a les 10:00: si 1-BAT-A fa examen, el vigila ell.
    _crea(client, grups="1-BAT-A", tipus="Música", nivell="1-BAT")
    client.post(f"{URL}/assign/pendents")
    assert _vigilants(client) == {"1-BAT-A": "Prof 48"}


def test_assignar_pendents_respecta_el_pes_dins_de_la_categoria():
    # A les 10:00 fan guàrdia Prof 3, 21 i 28 (pes 1) i Prof 32 fa C.D. (pes 5),
    # tots a la mateixa categoria: ha de guanyar sempre qui té més pes.
    centre = nova_institucio(amb_xml=True, prioritats=[("Disponibles", [("Guàrdia", 1), ("C.D.", 5)])])
    client = _admin_de(centre)
    for grup in ("2-BAT-A", "2-BAT-B", "1-BAT-A"):
        client.post(f"{URL}/clear")
        _crea(client, grups=grup)
        client.post(f"{URL}/assign/pendents", params={"disponibles": True})
        assert _vigilants(client)[grup] == "Prof 32"
        vig = next(v for v in _vigilancies(client) if v["grups"] == grup)
        client.delete(f"{URL}/{vig['id']}", params={"force": True})


def test_assignar_pendents_no_fa_servir_absents(client):
    _absent(client, "Prof 3")
    _absent(client, "Prof 28")
    _crea(client)
    client.post(f"{URL}/assign/pendents", params={"disponibles": True})
    assert _vigilants(client) == {"2-BAT-A": "Prof 21"}


def test_assignar_titulars_posa_el_titular_si_esta_disponible(client, centre):
    with get_data_db_session(centre) as db:
        db.add(ConfiguracioExamen(assignatura="Anglès", grup="2-BAT-A", titular="Prof 3", aula=""))
        db.commit()
    _crea(client)
    resp = client.post(f"{URL}/assign/titulars")
    assert resp.status_code == 200
    assert resp.json()["assigned_count"] == 1
    assert _vigilants(client) == {"2-BAT-A": "Prof 3"}


@pytest.mark.parametrize("ruta", ["assign/titulars", "assign/pendents"])
def test_assignar_sense_vigilancies(client, ruta):
    resp = client.post(f"{URL}/{ruta}")
    assert resp.status_code == 200
    assert resp.json()["assigned_count"] == 0


# ------------------------------------------------- reassignar i netejar

def test_reassignar_canvia_vigilants_absents_repetits_o_amb_classe(client):
    _crea(client, "Prof 21", grups="2-BAT-A")
    _crea(client, "Prof 21", grups="2-BAT-B")            # repetit a la mateixa hora
    _crea(client, "Prof 1", grups="1-ESO-A", tipus="Música", nivell="1-ESO")  # té classe amb 3-ESO-C
    _absent(client, "Prof 28")
    resp = client.post(f"{URL}/reassign-problematics")
    assert resp.status_code == 200
    assert resp.json()["cleared"] == 3

    vigilants = _vigilants(client)
    assert "Prof 1" not in vigilants.values()
    assert "Prof 28" not in vigilants.values()
    _comprova_assignacions_valides(client)


def test_reassignar_mante_qui_vigila_el_grup_amb_que_tenia_classe(client):
    _crea(client, "Prof 48", grups="1-BAT-A", tipus="Música", nivell="1-BAT")
    assert client.post(f"{URL}/reassign-problematics").json()["cleared"] == 0
    assert _vigilants(client) == {"1-BAT-A": "Prof 48"}


def test_reassignar_sense_vigilancies(client):
    resp = client.post(f"{URL}/reassign-problematics")
    assert resp.status_code == 200
    assert resp.json()["changes"] == []


def test_netejar_buida_els_vigilants_i_les_substitucions_derivades(client):
    _crea(client, "Prof 15", grups="2-BAT-A")
    _crea(client, "Prof 21", grups="2-BAT-B")
    resp = client.post(f"{URL}/clear")
    assert resp.json()["cleared_count"] == 2
    assert _vigilants(client) == {"2-BAT-A": "", "2-BAT-B": ""}
    assert _subs(client) == {}


def test_ordenar(client):
    assert client.post(f"{URL}/sort").status_code == 404
    _crea(client)
    assert client.post(f"{URL}/sort").json()["sorted_count"] == 1


def test_vigilant_que_despres_queda_absent_no_perd_cap_cobertura(client):
    # Prof 15 vigila a les 10:00, hora en què tenia Anglès amb 3-ESO-A, i
    # després se'l marca absent: cal cobrir la seva classe i també l'examen.
    _crea(client, "Prof 15")
    _absent(client, "Prof 15")
    files = _subs(client)
    assert files[("10:00", "Prof 15", "Anglès", "ABSENCIA")] == ""            # la classe
    assert any(t == "VIGILANCIA_ABSENT" and p == "Prof 15" for (_, p, _, t) in files)  # l'examen
    # La classe la cobreix l'ABSENCIA: no hi ha també una VIGILANCIA (seria doble).
    assert ("10:00", "Prof 15", "Anglès", "VIGILANCIA") not in files

    examen = next(s for s in client.get(URL_SUBS, params={"include_all": True}).json()
                  if s["tipus_absencia"] == "VIGILANCIA_ABSENT")
    resp = client.put(f"{URL_SUBS}/10:00/Prof 15",
                      json={"substitut": "Prof 3", "updated_at": examen["updated_at"]})
    assert resp.status_code == 200

    # Tornar a desar la vigilància (refresca les substitucions) no perd res.
    vig = _vigilancies(client)[0]
    client.put(f"{URL}/{vig['id']}", json={"comentaris": "canvi", "updated_at": vig["updated_at"]})
    despres = _subs(client)
    assert despres[("10:00", "Prof 15", "Anglès", "ABSENCIA")] == ""
    tipus_a = {k: v for k, v in despres.items() if k[3] == "VIGILANCIA_ABSENT"}
    assert list(tipus_a.values()) == ["Prof 3"]
