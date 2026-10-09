"""
Tests de les rutes de substitucions (routes/substitucions.py) a través de l'API.

Cada test treballa sobre una institució temporal amb l'horari d'exemple
(data/exemple/teachers.xml) i les prioritats mínimes de suport_api: hi ha
substituts disponibles si fan guàrdia sense grup o si tenen el grup alliberat.

Escenari base, dilluns 20/04/2026, Prof 15 absent:
  10:00  Anglès 3-ESO-A   (a la mateixa hora fan guàrdia Prof 3, Prof 21 i Prof 28)
  11:30  Anglès 1-ESO-A
  12:30  Pares            (activitat sense grup)
"""
import contextlib
import io
import uuid

import pytest
from fastapi.testclient import TestClient

from database import get_data_db_session
from horari_web import GestorHorariWeb
from rate_limit import limiter
from repositories import (
    GrupsAlliberatsRepository,
    NoSubstituirRepository,
    SubstitucioRepository,
    VigilanciaRepository,
)
from routes import substitucions
from suport_api import XML_EXEMPLE, client_per, crea_app, crea_usuari, entra, nova_institucio

APP = crea_app(substitucions.router)
DATA = "2026-04-20"  # dilluns
URL = f"/api/substitucions/{DATA}"
ABSENT = "Prof 15"
HORES_ABSENT = ["10:00", "11:30", "12:30"]

with contextlib.redirect_stdout(io.StringIO()):
    HORARI = GestorHorariWeb(str(XML_EXEMPLE))


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


def _admin_de(institucio, client=None):
    nom = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, institucio, "admin")
    return entra(client or client_per(APP), nom)


@pytest.fixture
def centre():
    return nova_institucio(amb_xml=True)


@pytest.fixture
def client(centre):
    return _admin_de(centre)


def _marca_absencia(client, professor=ABSENT, hores=HORES_ABSENT, **extra):
    body = {"hores_absencia": hores, "updated_at_map": {}, **extra}
    return client.put(f"{URL}/absencies/{professor}", json=body)


def _subs(client, include_all=False):
    resp = client.get(URL, params={"include_all": include_all})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _sub(client, hora, professor=ABSENT):
    return next(s for s in _subs(client, include_all=True)
                if s["hora"] == hora and s["professor_absent"] == professor)


def _assigna(client, hora, substitut, professor=ABSENT, **extra):
    body = {"substitut": substitut, "updated_at": _sub(client, hora, professor)["updated_at"], **extra}
    return client.put(f"{URL}/{hora}/{professor}", json=body)


# ------------------------------------------------------------------ accés

def test_sense_sessio_no_es_pot_accedir():
    assert client_per(APP).get(URL).status_code == 401


def test_cada_institucio_nomes_veu_les_seves_substitucions(client, centre):
    _marca_absencia(client)
    altre = _admin_de(nova_institucio(amb_xml=True))
    assert _subs(altre, include_all=True) == []
    # Tampoc no pot modificar-les: per a ella no existeixen.
    resp = altre.put(f"{URL}/10:00/{ABSENT}", json={"substitut": "Prof 21", "force": True})
    assert resp.status_code == 404


@pytest.mark.parametrize("metode, ruta", [
    ("get", "/api/substitucions/20-04-2026"),
    ("post", "/api/substitucions/20-04-2026/generar"),
    ("get", "/api/substitucions/2026-13-01/10:00/disponibles"),
])
def test_data_amb_format_invalid_dona_400(client, metode, ruta):
    assert getattr(client, metode)(ruta).status_code == 400


def test_institucio_sense_xml_ho_indica(client):
    sense_xml = _admin_de(nova_institucio(amb_xml=False))
    resp = sense_xml.get(URL)
    assert resp.status_code == 400
    assert resp.json()["detail"]["xml_missing"] is True


# -------------------------------------------------------------- absències

def test_marcar_absencia_crea_una_fila_per_hora_amb_l_activitat_de_l_horari(client):
    resp = _marca_absencia(client)
    assert resp.status_code == 200
    assert resp.json()["hores_afegides"] == 3

    files = [(s["hora"], s["assignatura"], s["grup"], s["substitut"], s["tipus_absencia"])
             for s in _subs(client, include_all=True)]
    assert files == [
        ("10:00", "Anglès", "3-ESO-A", "", "ABSENCIA"),
        ("11:30", "Anglès", "1-ESO-A", "", "ABSENCIA"),
        ("12:30", "Pares", "", "", "ABSENCIA"),
    ]


def test_marcar_absencia_sense_updated_at_map_es_rebutja(client):
    resp = client.put(f"{URL}/absencies/{ABSENT}", json={"hores_absencia": ["10:00"]})
    assert resp.status_code == 400


def test_treure_una_hora_d_absencia_n_esborra_la_fila(client):
    _marca_absencia(client)
    resp = _marca_absencia(client, hores=["10:00", "12:30"])
    assert resp.json()["hores_eliminades"] == 1
    assert [s["hora"] for s in _subs(client, include_all=True)] == ["10:00", "12:30"]


def test_absencia_i_servei_conviuen_per_al_mateix_professor(client):
    resp = _marca_absencia(client, hores=["10:00"], hores_servei=["11:30"])
    assert resp.status_code == 200
    tipus = {s["hora"]: s["tipus_absencia"] for s in _subs(client, include_all=True)}
    assert tipus == {"10:00": "ABSENCIA", "11:30": "SERVEI"}


def test_absencia_modificada_per_un_altre_usuari_dona_conflicte(client):
    _marca_absencia(client)
    resp = _marca_absencia(client, hores=["10:00"], updated_at_map={"10:00": "2000-01-01T00:00:00"})
    assert resp.status_code == 409


# --------------------------------------------------------- vista per defecte

def test_la_vista_per_defecte_amaga_activitats_que_no_se_substitueixen(client, centre):
    with get_data_db_session(centre) as db:
        NoSubstituirRepository.create(db, "Pares")
    _marca_absencia(client)
    assert [s["hora"] for s in _subs(client)] == ["10:00", "11:30"]
    assert [s["hora"] for s in _subs(client, include_all=True)] == HORES_ABSENT


def test_la_vista_per_defecte_amaga_grups_alliberats(client, centre):
    with get_data_db_session(centre) as db:
        GrupsAlliberatsRepository.set_for_date(db, DATA, {"10:00": ["3-ESO-A"]})
    _marca_absencia(client)
    assert "10:00" not in [s["hora"] for s in _subs(client)]


# ------------------------------------------------------------------ generar

def _te_classe_amb_grup(professor, hora):
    act = HORARI.get_activitat("Dilluns", hora, professor) or {}
    return bool(act.get("grup"))


def test_generar_assigna_substituts_que_estan_lliures(client):
    _marca_absencia(client)
    resp = client.post(f"{URL}/generar")
    assert resp.status_code == 200
    cos = resp.json()
    assert cos["assignades"] + cos["pendents"] == cos["total"]
    assert cos["assignades"] > 0

    per_hora = {}
    for s in _subs(client, include_all=True):
        if not s["substitut"]:
            continue
        assert s["substitut"] != s["professor_absent"]
        assert s["substitut"] != ABSENT
        assert not _te_classe_amb_grup(s["substitut"], s["hora"]), s
        per_hora.setdefault(s["hora"], []).append(s["substitut"])
    for hora, substituts in per_hora.items():
        assert len(substituts) == len(set(substituts)), f"substitut repetit a les {hora}"


def test_qui_deixa_una_guardia_per_substituir_genera_una_substitucio_encadenada(client):
    _marca_absencia(client, hores=["10:00"])
    client.post(f"{URL}/generar")
    files = _subs(client, include_all=False)
    principal = next(s for s in files if s["professor_absent"] == ABSENT)
    assert principal["substitut"]
    encadenada = next(s for s in files if s["professor_absent"] == principal["substitut"])
    assert (encadenada["hora"], encadenada["assignatura"]) == ("10:00", "Guàrdia")
    assert encadenada["tipus_absencia"] == "ENCADENADA"
    # En mode edició (include_all) les encadenades no es mostren.
    assert all(s["tipus_absencia"] != "ENCADENADA" for s in _subs(client, include_all=True))


def test_generar_dues_vegades_no_duplica_files(client):
    _marca_absencia(client)
    client.post(f"{URL}/generar")
    primer = sorted((s["hora"], s["professor_absent"]) for s in _subs(client))
    client.post(f"{URL}/generar")
    assert sorted((s["hora"], s["professor_absent"]) for s in _subs(client)) == primer


def test_generar_respecta_el_substitut_assignat_a_ma(client):
    _marca_absencia(client, hores=["10:00"])
    assert _assigna(client, "10:00", "Prof 21").status_code == 200
    client.post(f"{URL}/generar")
    assert _sub(client, "10:00")["substitut"] == "Prof 21"


# ---------------------------------------------------- assignació manual

def test_assignar_a_ma_calcula_el_tipus_de_substitut(client):
    _marca_absencia(client, hores=["10:00"])
    resp = _assigna(client, "10:00", "Prof 21")
    assert resp.status_code == 200
    assert resp.json()["updated_at"]
    assert _sub(client, "10:00")["substitut"] == "Prof 21"


def test_assignar_sense_updated_at_es_rebutja(client):
    _marca_absencia(client, hores=["10:00"])
    resp = client.put(f"{URL}/10:00/{ABSENT}", json={"substitut": "Prof 21"})
    assert resp.status_code == 400


def test_assignar_amb_updated_at_antic_dona_conflicte(client):
    _marca_absencia(client, hores=["10:00"])
    resp = client.put(f"{URL}/10:00/{ABSENT}",
                      json={"substitut": "Prof 21", "updated_at": "2000-01-01T00:00:00"})
    assert resp.status_code == 409


def test_substitucio_inexistent_dona_404(client):
    resp = client.put(f"{URL}/10:00/Prof 99", json={"substitut": "Prof 21", "force": True})
    assert resp.status_code == 404


def test_no_es_pot_assignar_qui_te_classe_a_aquella_hora(client):
    _marca_absencia(client, hores=["10:00"])
    assert _te_classe_amb_grup("Prof 1", "10:00")
    resp = _assigna(client, "10:00", "Prof 1")
    assert resp.status_code == 400
    assert "CLASSE" in resp.json()["detail"]


def test_si_el_grup_del_substitut_esta_alliberat_se_li_pot_assignar(client, centre):
    grup = HORARI.get_activitat("Dilluns", "10:00", "Prof 1")["grup"]
    with get_data_db_session(centre) as db:
        GrupsAlliberatsRepository.set_for_date(db, DATA, {"10:00": [grup]})
    _marca_absencia(client, hores=["10:00"])
    assert _assigna(client, "10:00", "Prof 1").status_code == 200


def test_no_es_pot_assignar_un_professor_absent(client):
    _marca_absencia(client, hores=["10:00"])
    _marca_absencia(client, professor="Prof 21", hores=["10:00"])
    resp = _assigna(client, "10:00", "Prof 21")
    assert resp.status_code == 400
    assert "ABSENT" in resp.json()["detail"]


def test_no_es_pot_assignar_el_mateix_substitut_dues_vegades_a_la_mateixa_hora(client):
    _marca_absencia(client, hores=["10:00"])
    _marca_absencia(client, professor="Prof 1", hores=["10:00"])
    assert _assigna(client, "10:00", "Prof 21").status_code == 200
    resp = _assigna(client, "10:00", "Prof 21", professor="Prof 1")
    assert resp.status_code == 400
    assert "SUBSTITUT" in resp.json()["detail"]


def test_no_es_pot_assignar_qui_vigila_un_examen_a_aquella_hora(client, centre):
    with get_data_db_session(centre) as db:
        VigilanciaRepository.create(db, DATA, {
            "hora": "10:00", "tipus": "examen", "grups": "2-BAT-A", "aula": "",
            "vigilant": "Prof 21", "nivell": "2-BAT",
        })
    _marca_absencia(client, hores=["10:00"])
    resp = _assigna(client, "10:00", "Prof 21")
    assert resp.status_code == 400
    assert "VIGILANT" in resp.json()["detail"]


def test_no_es_pot_assignar_substitut_a_una_activitat_que_no_se_substitueix(client, centre):
    with get_data_db_session(centre) as db:
        NoSubstituirRepository.create(db, "Pares")
    _marca_absencia(client, hores=["12:30"])
    assert _assigna(client, "12:30", "Prof 21").status_code == 400


def test_buidar_el_substitut_el_deixa_pendent(client):
    _marca_absencia(client, hores=["10:00"])
    _assigna(client, "10:00", "Prof 21")
    assert _assigna(client, "10:00", "").status_code == 200
    assert _sub(client, "10:00")["estat"] == "pendent"


# --------------------------------------------------------------- esborrar

def _esborra(client, hora, updated_at=None, **params):
    s = _sub(client, hora)
    url = f"{URL}/{hora}/{ABSENT}/{s['assignatura']}/{s['grup'] or ' '}"
    if updated_at is None:
        updated_at = s["updated_at"]
    return client.delete(url, params={"updated_at": updated_at, **params})


def test_esborrar_una_substitucio(client):
    _marca_absencia(client, hores=["10:00", "11:30"])
    s = _sub(client, "10:00")
    resp = client.delete(f"{URL}/10:00/{ABSENT}/{s['assignatura']}/{s['grup']}",
                         params={"updated_at": s["updated_at"]})
    assert resp.status_code == 200
    assert [x["hora"] for x in _subs(client, include_all=True)] == ["11:30"]


def test_esborrar_demana_updated_at_i_detecta_conflictes(client):
    _marca_absencia(client, hores=["10:00"])
    ruta = f"{URL}/10:00/{ABSENT}/Anglès/3-ESO-A"
    assert client.delete(ruta).status_code == 400
    assert client.delete(ruta, params={"updated_at": "2000-01-01T00:00:00"}).status_code == 409
    assert client.delete(ruta, params={"force": True}).status_code == 200


def test_esborrar_una_substitucio_inexistent_dona_404(client):
    assert client.delete(f"{URL}/10:00/{ABSENT}/Anglès/3-ESO-A", params={"force": True}).status_code == 404
    _marca_absencia(client, hores=["10:00"])
    assert client.delete(f"{URL}/10:00/{ABSENT}/Música/3-ESO-A", params={"force": True}).status_code == 404


# ------------------------------------------------------------------- nova

def test_nova_substitucio_agafa_l_activitat_de_l_horari_i_no_duplica(client):
    body = {"professor": ABSENT, "hores": ["10:00", "12:30"], "tipus_absencia": "ABSENCIA"}
    resp = client.post(f"{URL}/nova", json=body)
    assert resp.status_code == 200
    files = [(s["hora"], s["assignatura"], s["grup"]) for s in _subs(client, include_all=True)]
    assert files == [("10:00", "Anglès", "3-ESO-A"), ("12:30", "Pares", "")]

    assert client.post(f"{URL}/nova", json=body).json()["count"] == 0
    assert len(_subs(client, include_all=True)) == 2


def test_nova_substitucio_sense_hores_es_rebutja(client):
    body = {"professor": ABSENT, "hores": [], "tipus_absencia": "ABSENCIA"}
    assert client.post(f"{URL}/nova", json=body).status_code == 400


def test_nova_substitucio_amb_error_inesperat_dona_500_sense_detalls_interns(client, monkeypatch, caplog):
    def falla(*args, **kwargs):
        raise RuntimeError("error de prova")

    monkeypatch.setattr(substitucions, "get_gestors", falla)
    body = {"professor": ABSENT, "hores": ["10:00"], "tipus_absencia": "ABSENCIA"}
    resp = client.post(f"{URL}/nova", json=body)
    assert resp.status_code == 500
    # L'usuari només rep una referència; el detall és al registre del servidor.
    assert set(resp.json()) == {"error_ref"}
    ref = resp.json()["error_ref"]
    assert any(ref in r.getMessage() and "error de prova" in r.getMessage() for r in caplog.records)


# ------------------------------------------------ consultes auxiliars

def test_hores_professor_separa_classes_d_activitats_que_no_se_substitueixen(client, centre):
    with get_data_db_session(centre) as db:
        NoSubstituirRepository.create(db, "Pares")
    resp = client.get(f"{URL}/hores-professor/{ABSENT}")
    assert resp.status_code == 200
    assert resp.json() == {
        "hores_amb_classe": ["10:00", "11:30", "15:00", "16:00"],
        "hores_al_centre": ["12:30"],
    }


def test_disponibles_marca_qui_ja_esta_assignat_o_absent(client):
    _marca_absencia(client, hores=["10:00"])
    _assigna(client, "10:00", "Prof 21")
    resp = client.get(f"{URL}/10:00/disponibles")
    assert resp.status_code == 200
    per_prof = {d["professor"]: d for d in resp.json()["disponibles"]}

    assert {"Prof 3", "Prof 21", "Prof 28"} <= set(per_prof)
    assert per_prof["Prof 21"]["ja_assignat"] is True
    assert per_prof["Prof 28"]["ja_assignat"] is False
    assert per_prof["Prof 28"]["absent"] is False
    # Ningú amb classe amb grup no surt com a disponible.
    assert not any(_te_classe_amb_grup(p, "10:00") for p in per_prof)


# ------------------------------------------------- reassignar problemàtics

def test_reassignar_treu_substituts_que_ara_tenen_classe(client, centre):
    _marca_absencia(client, hores=["10:00"])
    # Prof 1 té classe a les 10:00: l'API no el deixaria assignar, així que es
    # desa directament, com si l'horari hagués canviat després d'assignar-lo.
    with get_data_db_session(centre) as db:
        fila = next(f for f in SubstitucioRepository.get_by_date(db, DATA) if f["hora"] == "10:00")
        SubstitucioRepository.update(db, int(fila["id"]), {"substitut": "Prof 1"})
    resp = client.post(f"{URL}/reassign-problematics")
    assert resp.status_code == 200
    assert resp.json()["cleared"] == 1
    assert _sub(client, "10:00")["substitut"] != "Prof 1"


# Regla: el que allibera un professor és que el seu grup estigui marcat sense
# classe. Que el grup tingui un examen (una vigilància) no n'hi ha prou: pot
# tenir classe igualment.

def _vigilancia_del_grup_de_prof_1(centre):
    grup = HORARI.get_activitat("Dilluns", "10:00", "Prof 1")["grup"]
    with get_data_db_session(centre) as db:
        VigilanciaRepository.create(db, DATA, {
            "hora": "10:00", "tipus": "examen", "grups": grup, "aula": "",
            "vigilant": "", "nivell": grup.rsplit("-", 1)[0],
        })
    return grup


def test_reassignar_mante_qui_te_el_grup_sense_classe(client, centre):
    grup = HORARI.get_activitat("Dilluns", "10:00", "Prof 1")["grup"]
    with get_data_db_session(centre) as db:
        GrupsAlliberatsRepository.set_for_date(db, DATA, {"10:00": [grup]})
    _marca_absencia(client, hores=["10:00"])
    assert _assigna(client, "10:00", "Prof 1").status_code == 200
    assert client.post(f"{URL}/reassign-problematics").json()["cleared"] == 0
    assert _sub(client, "10:00")["substitut"] == "Prof 1"


def test_reassignar_no_allibera_per_tenir_el_grup_d_examen(client, centre):
    _vigilancia_del_grup_de_prof_1(centre)
    _marca_absencia(client, hores=["10:00"])
    with get_data_db_session(centre) as db:
        fila = next(f for f in SubstitucioRepository.get_by_date(db, DATA) if f["hora"] == "10:00")
        SubstitucioRepository.update(db, int(fila["id"]), {"substitut": "Prof 1"})
    assert client.post(f"{URL}/reassign-problematics").json()["cleared"] == 1
    assert _sub(client, "10:00")["substitut"] != "Prof 1"


def test_assignar_a_ma_no_allibera_per_tenir_el_grup_d_examen(client, centre):
    # Pot ser un examen extra: el grup continua tenint classe amb Prof 1.
    _vigilancia_del_grup_de_prof_1(centre)
    _marca_absencia(client, hores=["10:00"])
    resp = _assigna(client, "10:00", "Prof 1")
    assert resp.status_code == 400
    assert "CLASSE" in resp.json()["detail"]


# ------------------------------------------------------------------ ordre

def _ordre(client):
    return [(s["hora"], s["professor_absent"], s["tipus_absencia"]) for s in _subs(client)]


def test_regenerar_tot_no_canvia_l_ordre_de_les_files(client):
    # Les encadenades depenen de quin substitut tria el motor (pot variar);
    # la resta de files han de quedar sempre al mateix lloc.
    def no_encadenades():
        return [f for f in _ordre(client) if f[2] != "ENCADENADA"]
    _marca_absencia(client)
    _marca_absencia(client, professor="Prof 1", hores=["10:00", "11:30"])
    client.post(f"{URL}/generar", params={"regenerar_tot": True})
    primer = no_encadenades()
    for _ in range(3):
        client.post(f"{URL}/generar", params={"regenerar_tot": True})
        assert no_encadenades() == primer


def test_dins_de_cada_hora_per_professor_i_encadenades_al_final(client):
    _marca_absencia(client, hores=["10:00"])
    _marca_absencia(client, professor="Prof 1", hores=["10:00"])
    client.post(f"{URL}/generar")
    files = [(p, t) for h, p, t in _ordre(client) if h == "10:00"]
    absencies = [p for p, t in files if t == "ABSENCIA"]
    assert absencies == ["Prof 1", "Prof 15"]         # ordre natural, no per id
    tipus = [t for _, t in files]
    assert tipus == sorted(tipus, key=lambda t: t == "ENCADENADA")
