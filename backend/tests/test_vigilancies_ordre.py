"""
Ordre de les files de vigilància dins de cada hora (columna `ordre`):
- les files d'abans de la columna prenen l'ordre que es veia a la pantalla
  (per nivell i, dins del nivell, per id);
- una fila nova, o que canvia d'hora, va al final del bloc de la seva hora;
  la còpia d'una fila («+», `despres_de`), just a sota;
- en publicar, un dia sense ordre fet a mà surt ordenat automàticament
  (nivell, grup, aula); si n'hi havia, les files noves van al final;
- el llistat i el PDF segueixen l'ordre desat; PUT .../ordre el desa per a
  una hora; «Ordena» desa l'automàtic; l'«ordre manual» es dedueix.
"""

import sqlite3
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio, text_pdf
from test_scheduler_publicar import DATA as DATA_PUBLICAR
from test_scheduler_publicar import _examen, _publica

from database import _ensure_vigilancies_ordre_column, get_data_db_session
from models import Vigilancia
from pdf import router as pdf
from rate_limit import limiter
from repositories import parse_date
from routes import scheduler
from vigilancies.router import router as vigilancies_router
from vigilancies.services import completa_ordre, ordena_automaticament, te_ordre_manual

APP = crea_app(vigilancies_router, scheduler.router, pdf.router)
DATA = "2026-04-20"
URL = f"/api/vigilancies/{DATA}"


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


@pytest.fixture
def centre():
    return nova_institucio(amb_xml=True)


@pytest.fixture
def client(centre):
    nom = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, centre, "admin")
    return entra(client_per(APP), nom)


def _crea(client, grups, hora="10:00", nivell="2-ESO", tipus="Castellà"):
    body = {"hora": hora, "tipus": tipus, "grups": grups, "aula": "A1", "vigilant": "", "nivell": nivell}
    resp = client.post(URL, json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()["vigilancia"]


def _ordres(centre, data=DATA):
    with get_data_db_session(centre) as db:
        files = db.query(Vigilancia).filter(Vigilancia.data == parse_date(data)).all()
        return {(v.hora, v.grups): v.ordre for v in files}


# ------------------------------------------------------------ migració


def _bd_antiga(tmp_path, files):
    """Una BD amb la taula vigilancies d'abans de la columna ordre."""
    cami = tmp_path / "gestor.db"
    con = sqlite3.connect(cami)
    con.execute(
        "CREATE TABLE vigilancies (id INTEGER PRIMARY KEY, data DATE, hora VARCHAR, tipus VARCHAR, grups VARCHAR,"
        " aula VARCHAR, vigilant VARCHAR, comentaris TEXT, nivell VARCHAR, created_at DATETIME, updated_at DATETIME)"
    )
    con.executemany(
        "INSERT INTO vigilancies (id, data, hora, tipus, grups, aula, nivell) VALUES (?, ?, ?, 'X', ?, 'A', ?)", files
    )
    con.commit()
    con.close()
    return cami


def _llegeix(cami):
    con = sqlite3.connect(cami)
    try:
        return {r[0]: r[1] for r in con.execute("SELECT id, ordre FROM vigilancies")}
    finally:
        con.close()


def test_la_migracio_dona_a_les_files_d_abans_l_ordre_de_la_pantalla(tmp_path):
    # Pantalla d'abans: per hora i, dins de l'hora, per nivell i id
    cami = _bd_antiga(
        tmp_path,
        [
            (1, "2026-04-20", "10:00", "G1", "3-ESO"),
            (2, "2026-04-20", "10:00", "G2", "1-ESO"),
            (3, "2026-04-20", "10:00", "G3", "3-ESO"),
            (4, "2026-04-20", "11:30", "G4", "2-ESO"),
            (5, "2026-04-21", "10:00", "G5", "2-ESO"),
        ],
    )
    engine = create_engine(f"sqlite:///{cami}")
    _ensure_vigilancies_ordre_column(engine)
    assert _llegeix(cami) == {2: 0, 1: 1, 3: 2, 4: 0, 5: 0}
    # Tornar-la a passar no canvia res
    _ensure_vigilancies_ordre_column(engine)
    assert _llegeix(cami) == {2: 0, 1: 1, 3: 2, 4: 0, 5: 0}


def test_la_migracio_posa_al_final_les_files_sense_ordre_d_una_hora_que_ja_en_te(tmp_path):
    cami = _bd_antiga(tmp_path, [(1, "2026-04-20", "10:00", "G1", "1-ESO"), (2, "2026-04-20", "10:00", "G2", "1-ESO")])
    engine = create_engine(f"sqlite:///{cami}")
    _ensure_vigilancies_ordre_column(engine)
    con = sqlite3.connect(cami)
    con.execute(
        "INSERT INTO vigilancies (id, data, hora, tipus, grups, aula, nivell) VALUES (3, '2026-04-20', '10:00', 'X', 'G0', 'A', '0-ESO')"
    )
    con.commit()
    con.close()
    _ensure_vigilancies_ordre_column(engine)
    assert _llegeix(cami) == {1: 0, 2: 1, 3: 2}


# ------------------------------------------------------------ files noves i canvis d'hora


def test_una_fila_nova_va_al_final_del_bloc_de_la_seva_hora(client, centre):
    _crea(client, "2-ESO-B")
    _crea(client, "2-ESO-A")
    _crea(client, "1-BAT-A", hora="11:30", nivell="1-BAT")
    _crea(client, "1-ESO-A", nivell="1-ESO")
    assert _ordres(centre) == {
        ("10:00", "2-ESO-B"): 0,
        ("10:00", "2-ESO-A"): 1,
        ("10:00", "1-ESO-A"): 2,
        ("11:30", "1-BAT-A"): 0,
    }


def test_una_copia_amb_despres_de_va_just_a_sota_de_la_fila(client, centre):
    a = _crea(client, "2-ESO-A")
    _crea(client, "2-ESO-B")
    _crea(client, "2-ESO-C")
    body = {
        "hora": "10:00",
        "tipus": "Castellà",
        "grups": "2-ESO-D",
        "aula": "A1",
        "nivell": "2-ESO",
        "despres_de": a["id"],
    }
    assert client.post(URL, json=body).status_code == 200
    ordres = _ordres(centre)
    assert sorted(ordres, key=ordres.get) == [
        ("10:00", "2-ESO-A"),
        ("10:00", "2-ESO-D"),
        ("10:00", "2-ESO-B"),
        ("10:00", "2-ESO-C"),
    ]
    assert [v["grups"] for v in client.get(URL).json()] == ["2-ESO-A", "2-ESO-D", "2-ESO-B", "2-ESO-C"]


def test_despres_de_una_fila_d_una_altra_hora_o_que_no_existeix_dona_400(client, centre):
    a = _crea(client, "2-ESO-A")
    for referencia in (a["id"], "99999"):
        body = {
            "hora": "11:30",
            "tipus": "Castellà",
            "grups": "2-ESO-B",
            "aula": "A1",
            "nivell": "2-ESO",
            "despres_de": referencia,
        }
        assert client.post(URL, json=body).status_code == 400
    assert ("11:30", "2-ESO-B") not in _ordres(centre)  # no s'ha creat


def test_canviar_l_hora_porta_la_fila_al_final_del_bloc_de_l_hora_nova(client, centre):
    _crea(client, "2-ESO-A")
    b = _crea(client, "2-ESO-B")
    _crea(client, "1-BAT-A", hora="11:30", nivell="1-BAT")
    assert client.put(f"{URL}/{b['id']}", json={"hora": "11:30", "force": True}).status_code == 200
    assert _ordres(centre) == {("10:00", "2-ESO-A"): 0, ("11:30", "1-BAT-A"): 0, ("11:30", "2-ESO-B"): 1}
    # Un canvi que no és d'hora no mou la fila
    assert client.put(f"{URL}/{b['id']}", json={"comentaris": "x", "force": True}).status_code == 200
    assert _ordres(centre)[("11:30", "2-ESO-B")] == 1


# ------------------------------------------------------------ publicar


def _horari_publicar(examens):
    return {
        "dies": [
            {
                "dia": "Dilluns",
                "data": DATA_PUBLICAR,
                "sessions": [
                    {"hora": "10:00", "sessions_simultanees": [{"curs": "2-ESO", "nom": "2-ESO", "examens": examens}]}
                ],
            }
        ]
    }


def test_publicar_un_dia_sense_ordre_l_ordena_automaticament(client, centre):
    examens = [
        _examen("2-ESO-C", "Socials", "A3"),
        _examen("2-ESO-A", "Socials", "A1"),
        _examen("2-ESO-B", "Socials", "A2"),
    ]
    _publica(client, _horari_publicar(examens))
    assert _ordres(centre, DATA_PUBLICAR) == {("10:00", "2-ESO-A"): 0, ("10:00", "2-ESO-B"): 1, ("10:00", "2-ESO-C"): 2}


def test_publicar_un_dia_amb_ordre_fet_a_ma_hi_afegeix_les_noves_al_final(client, centre):
    _publica(client, _horari_publicar([_examen("2-ESO-A", "Socials", "A1"), _examen("2-ESO-B", "Socials", "A2")]))
    with get_data_db_session(centre) as db:  # retoc a mà: B abans que A
        for v in db.query(Vigilancia).all():
            v.ordre = {"2-ESO-A": 1, "2-ESO-B": 0}[v.grups]
        db.commit()
    examens = [
        _examen("2-ESO-A", "Socials", "A1"),
        _examen("2-ESO-B", "Socials", "A2"),
        _examen("1-ESO-A", "Socials", "A0"),
    ]
    _publica(client, _horari_publicar(examens))
    assert _ordres(centre, DATA_PUBLICAR) == {("10:00", "2-ESO-B"): 0, ("10:00", "2-ESO-A"): 1, ("10:00", "1-ESO-A"): 2}


# ------------------------------------------------------------ llistat, PDF, desar l'ordre i «Ordena»


def _grups_en_ordre(client, hora="10:00"):
    return [v["grups"] for v in client.get(URL).json() if v["hora"] == hora]


def test_desar_l_ordre_d_una_hora_el_llistat_el_segueix(client):
    a = _crea(client, "2-ESO-A")
    b = _crea(client, "2-ESO-B")
    c = _crea(client, "1-ESO-A", nivell="1-ESO")
    _crea(client, "1-BAT-A", hora="11:30", nivell="1-BAT")
    assert client.put(f"{URL}/ordre", json={"hora": "10:00", "ids": [c["id"], b["id"], a["id"]]}).status_code == 200
    assert _grups_en_ordre(client) == ["1-ESO-A", "2-ESO-B", "2-ESO-A"]
    assert _grups_en_ordre(client, "11:30") == ["1-BAT-A"]


def test_el_pdf_segueix_l_ordre_desat(client):
    a = _crea(client, "2-ESO-A", tipus="Matemàtiques")
    b = _crea(client, "2-ESO-B", tipus="Socials")
    for ids, primer in [([b["id"], a["id"]], "Socials"), ([a["id"], b["id"]], "Matem")]:
        client.put(f"{URL}/ordre", json={"hora": "10:00", "ids": ids})
        resp = client.get(f"/api/pdf/vigilancies/{DATA}")
        assert resp.status_code == 200
        textos = [t for t in text_pdf(resp.content) if t.startswith(("Socials", "Matem"))]
        assert textos and textos[0].startswith(primer), textos


def test_desar_l_ordre_amb_files_d_una_altra_hora_o_repetides_dona_400(client):
    a = _crea(client, "2-ESO-A")
    b = _crea(client, "2-ESO-B")
    altra = _crea(client, "1-BAT-A", hora="11:30", nivell="1-BAT")
    assert client.put(f"{URL}/ordre", json={"hora": "10:00", "ids": [a["id"], b["id"], altra["id"]]}).status_code == 400
    assert client.put(f"{URL}/ordre", json={"hora": "10:00", "ids": [a["id"], a["id"], b["id"]]}).status_code == 400


def test_desar_l_ordre_si_les_files_de_l_hora_han_canviat_dona_409(client):
    a = _crea(client, "2-ESO-A")
    b = _crea(client, "2-ESO-B")
    _crea(client, "2-ESO-C")  # algú n'ha afegit una mentrestant
    assert client.put(f"{URL}/ordre", json={"hora": "10:00", "ids": [b["id"], a["id"]]}).status_code == 409
    assert client.put(f"{URL}/ordre", json={"hora": "10:00", "ids": [b["id"], a["id"], "9999"]}).status_code == 409
    assert _grups_en_ordre(client) == ["2-ESO-A", "2-ESO-B", "2-ESO-C"]  # no s'ha tocat res


def test_ordena_desa_l_ordre_automatic_i_l_ordre_manual_es_dedueix(client):
    b = _crea(client, "2-ESO-B")
    a = _crea(client, "2-ESO-A")
    _crea(client, "1-ESO-A", nivell="1-ESO")
    assert client.get(f"{URL}/ordre").json() == {"ordre_manual": True}  # creades fora de l'ordre automàtic
    assert client.post(f"{URL}/sort").json()["sorted_count"] == 3
    assert _grups_en_ordre(client) == ["1-ESO-A", "2-ESO-A", "2-ESO-B"]
    assert client.get(f"{URL}/ordre").json() == {"ordre_manual": False}
    client.put(
        f"{URL}/ordre",
        json={
            "hora": "10:00",
            "ids": [b["id"], a["id"], next(v["id"] for v in client.get(URL).json() if v["grups"] == "1-ESO-A")],
        },
    )
    assert client.get(f"{URL}/ordre").json() == {"ordre_manual": True}


# ------------------------------------------------------------ peces


def _v(i, hora, nivell, grups="", aula="", ordre=None):
    return SimpleNamespace(id=i, hora=hora, nivell=nivell, grups=grups, aula=aula, ordre=ordre)


def test_ordre_manual_es_dedueix_de_si_l_ordre_desat_no_es_l_automatic():
    a, b = _v(1, "10:00", "1-ESO", "A"), _v(2, "10:00", "1-ESO", "B")
    ordena_automaticament([a, b])
    assert (a.ordre, b.ordre) == (0, 1)
    assert te_ordre_manual([a, b]) is False
    a.ordre, b.ordre = 1, 0
    assert te_ordre_manual([a, b]) is True
    # Cada hora va a part
    c = _v(3, "11:30", "1-ESO", "A", ordre=0)
    assert te_ordre_manual([c, _v(4, "10:00", "1-ESO", "A", ordre=0)]) is False


def test_completa_ordre_no_mou_les_files_que_ja_en_tenen():
    a, b = _v(1, "10:00", "2-ESO", "A", ordre=1), _v(2, "10:00", "1-ESO", "B", ordre=0)
    n1, n2 = _v(3, "10:00", "3-ESO", "C"), _v(4, "10:00", "1-ESO", "A")
    completa_ordre([a, b, n1, n2])
    assert (a.ordre, b.ordre, n2.ordre, n1.ordre) == (1, 0, 2, 3)
