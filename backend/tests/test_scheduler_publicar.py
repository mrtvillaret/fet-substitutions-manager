"""
Publicar l'horari d'exàmens del planificador (POST /api/scheduler/publicar):
converteix l'horari generat en vigilàncies i marca els grups sense classe.

Descriuen el comportament actual (characterization tests). Treballen sobre
una institució temporal amb l'horari d'exemple. Dilluns 20/04/2026:
  10:00  Prof 48 fa Filosofia amb 1-BAT-A; Prof 15 fa Anglès amb 3-ESO-A
"""

import json
import uuid
from datetime import date, timedelta

import pytest
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio

from absencia_coberta.repositories import AbsenciaCobertaRepository
from absencia_coberta.router import router as absencia_coberta_router
from database import get_data_db_session
from models import ConfiguracioExamen, Grup, GrupAlliberat, Nivell
from rate_limit import limiter
from repositories import ConfiguracioRepository
from routes import scheduler
from routes.scheduler_service import (
    SCHEDULER_ALLIBERAMENTS_KEY,
    SCHEDULER_DURADA_EXAMEN_KEY,
    SCHEDULER_DURADA_KEY,
    SCHEDULER_DURADES_GRUPS_KEY,
    SCHEDULER_NIVELLS_KEY,
)
from substitucions import router as substitucions
from vigilancies.router import router as vigilancies_router

APP = crea_app(scheduler.router, vigilancies_router, substitucions.router, absencia_coberta_router)
URL = "/api/scheduler/publicar"
DATA = "2026-04-20"  # dilluns
SETMANES = [{"Dilluns": DATA}]


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


def _usuari_de(institucio, role="admin"):
    nom = f"{role}_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, institucio, role)
    return entra(client_per(APP), nom)


@pytest.fixture
def centre():
    return nova_institucio(amb_xml=True)


@pytest.fixture
def client(centre):
    return _usuari_de(centre)


def _examen(grup, assignatura, aula="A01"):
    return {"grup": grup, "aula": aula, "assignatura": assignatura}


def _horari(*examens_per_curs, hora="10:00"):
    """Horari del planificador amb una sola franja: (curs, [exàmens]) per curs."""
    return {
        "dies": [
            {
                "dia": "Dilluns",
                "data": DATA,
                "sessions": [
                    {
                        "hora": hora,
                        "sessions_simultanees": [
                            {"curs": curs, "nom": curs, "examens": examens} for curs, examens in examens_per_curs
                        ],
                    }
                ],
            }
        ]
    }


FILOSOFIA_1BAT = ("1-BAT", [_examen("1-BAT-A", "Filosofia")])
ANGLES_2BAT = ("2-BAT", [_examen("2-BAT-A", "Anglès", "A02")])


def _publica(client, horari, auto_assign=False, netejar=False, **camps):
    cos = {
        "horari": horari,
        "setmanes": SETMANES,
        "opcions": {"auto_assign_titulars": auto_assign, "netejar_existents": netejar},
    }
    cos.update(camps)
    resp = client.post(URL, json=cos)
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"], resp.json()
    return resp.json()


def _vigilancies(client):
    return client.get(f"/api/vigilancies/{DATA}").json()


def _resum(client):
    return sorted((v["hora"], v["nivell"], v["grups"], v["tipus"], v["vigilant"]) for v in _vigilancies(client))


def _grups_alliberats(centre):
    with get_data_db_session(centre) as db:
        return sorted((g.hora, g.grups) for g in db.query(GrupAlliberat).all())


def _cobertures_de_vigilancia(client):
    files = client.get(f"/api/substitucions/{DATA}", params={"include_all": True}).json()
    return [
        (s["hora"], s["professor_absent"], s["tipus_absencia"])
        for s in files
        if s["tipus_absencia"] in ("VIGILANCIA", "VIGILANCIA_ABSENT")
    ]


def _assigna_vigilant(client, grups, vigilant, comentaris=""):
    vig = next(v for v in _vigilancies(client) if v["grups"] == grups)
    resp = client.put(
        f"/api/vigilancies/{DATA}/{vig['id']}",
        json={"vigilant": vigilant, "comentaris": comentaris, "updated_at": vig["updated_at"]},
    )
    assert resp.status_code == 200, resp.text


def _alliberaments(centre, nivell, hores, seleccionats=None):
    """Hores en què el nivell queda sense classe el dia de l'examen; els
    nivells seleccionats al planificador (per defecte, aquest)."""
    config = {nivell: {"durada": 1, "dates": [DATA], "config": {DATA: {h: {"a": True, "i": True} for h in hores}}}}
    with get_data_db_session(centre) as db:
        ConfiguracioRepository.set(db, SCHEDULER_ALLIBERAMENTS_KEY, json.dumps(config), tipus="json")
        ConfiguracioRepository.set(db, SCHEDULER_NIVELLS_KEY, json.dumps(seleccionats or [nivell]), tipus="json")


def _durades(centre, titular=1, examen=1, grups=None):
    """Durades del planificador: generals i, opcionalment, grups de durada."""
    with get_data_db_session(centre) as db:
        ConfiguracioRepository.set(db, SCHEDULER_DURADA_KEY, str(titular), tipus="integer")
        ConfiguracioRepository.set(db, SCHEDULER_DURADA_EXAMEN_KEY, str(examen), tipus="integer")
        if grups is not None:
            ConfiguracioRepository.set(db, SCHEDULER_DURADES_GRUPS_KEY, json.dumps(grups), tipus="json")


# ------------------------------------------------------------------ accés


def test_nomes_els_admins_poden_publicar(centre):
    resp = _usuari_de(centre, role="user").post(URL, json={"horari": _horari(FILOSOFIA_1BAT), "setmanes": SETMANES})
    assert resp.status_code == 403


@pytest.mark.parametrize(
    "cos",
    [
        {"horari": {"dies": []}, "setmanes": SETMANES},
        {"horari": _horari(FILOSOFIA_1BAT), "setmanes": []},
    ],
    ids=["sense dies", "sense setmanes"],
)
def test_cal_un_horari_amb_dies_i_setmanes(client, cos):
    assert client.post(URL, json=cos).status_code == 400


# ------------------------------------------------------------- vigilàncies


def test_crea_una_vigilancia_per_examen(client):
    resultat = _publica(client, _horari(FILOSOFIA_1BAT, ANGLES_2BAT))
    assert resultat["vigilancies_creades"] == 2
    assert resultat["dates_processades"] == [DATA]
    assert _resum(client) == [
        ("10:00", "1-BAT", "1-BAT-A", "Filosofia", ""),
        ("10:00", "2-BAT", "2-BAT-A", "Anglès", ""),
    ]


def test_un_examen_de_dues_hores_te_vigilancia_a_cada_hora(client, centre):
    _durades(centre, examen=2)
    _publica(client, _horari(FILOSOFIA_1BAT, hora="08:00"))
    assert [v[0] for v in _resum(client)] == ["08:00", "09:00"]


def test_les_hores_d_un_examen_llarg_son_les_seguents_de_l_horari_del_centre(client, centre):
    # Decidit: les hores són les que vénen a continuació a l'horari, siguin
    # quines siguin (aquí, el pati). Si cal, s'ajusta a mà a vigilàncies.
    _durades(centre, examen=2)
    _publica(client, _horari(FILOSOFIA_1BAT, hora="10:00"))
    assert [v[0] for v in _resum(client)] == ["10:00", "PATI"]


def test_la_simulacio_no_desa_res(client, centre):
    _alliberaments(centre, "1-BAT", ["10:00"])
    resultat = _publica(client, _horari(FILOSOFIA_1BAT), dry_run=True, grups_sense_classe=["1-BAT-A"])
    assert resultat["dry_run"] is True
    assert resultat["vigilancies_creades"] == 1
    assert _vigilancies(client) == []
    assert _grups_alliberats(centre) == []


# ------------------------------------------------------ tornar a publicar


def test_tornar_a_publicar_conserva_el_vigilant_i_els_comentaris(client):
    _publica(client, _horari(FILOSOFIA_1BAT))
    _assigna_vigilant(client, "1-BAT-A", "Prof 3", "porta calculadora")

    resultat = _publica(client, _horari(FILOSOFIA_1BAT))
    assert (resultat["vigilancies_creades"], resultat["vigilancies_sense_canvis"]) == (0, 1)
    [vig] = _vigilancies(client)
    assert (vig["vigilant"], vig["comentaris"]) == ("Prof 3", "porta calculadora")


def test_si_canvia_l_assignatura_s_actualitza_i_conserva_el_vigilant(client):
    _publica(client, _horari(FILOSOFIA_1BAT))
    _assigna_vigilant(client, "1-BAT-A", "Prof 3")

    resultat = _publica(client, _horari(("1-BAT", [_examen("1-BAT-A", "Història")])))
    assert resultat["vigilancies_actualitzades"] == 1
    assert _resum(client) == [("10:00", "1-BAT", "1-BAT-A", "Història", "Prof 3")]


def test_un_examen_que_ja_no_hi_es_s_esborra_i_no_toca_els_altres_nivells(client):
    _publica(client, _horari(FILOSOFIA_1BAT, ANGLES_2BAT))

    resultat = _publica(client, _horari(("1-BAT", [_examen("1-BAT-B", "Filosofia")])))
    assert (resultat["vigilancies_creades"], resultat["vigilancies_eliminades"]) == (1, 1)
    assert _resum(client) == [
        ("10:00", "1-BAT", "1-BAT-B", "Filosofia", ""),
        ("10:00", "2-BAT", "2-BAT-A", "Anglès", ""),
    ]


def test_netejar_esborra_totes_les_vigilancies_del_dia(client):
    _publica(client, _horari(FILOSOFIA_1BAT, ANGLES_2BAT))
    _assigna_vigilant(client, "1-BAT-A", "Prof 3")

    resultat = _publica(client, _horari(("1-BAT", [_examen("1-BAT-B", "Filosofia")])), netejar=True)
    assert resultat["vigilancies_eliminades"] == 2
    assert _resum(client) == [("10:00", "1-BAT", "1-BAT-B", "Filosofia", "")]


def test_si_un_examen_amb_vigilant_desapareix_la_seva_classe_ja_no_queda_coberta(client):
    # Prof 15 té classe a les 10:00: en fer de vigilant, la seva classe queda
    # coberta (VIGILANCIA). Si l'examen desapareix, ja no vigila.
    _publica(client, _horari(FILOSOFIA_1BAT))
    _assigna_vigilant(client, "1-BAT-A", "Prof 15")
    assert _cobertures_de_vigilancia(client) == [("10:00", "Prof 15", "VIGILANCIA")]

    _publica(client, _horari(("1-BAT", [_examen("1-BAT-B", "Filosofia")])))
    assert _cobertures_de_vigilancia(client) == []


def test_netejar_tambe_treu_les_cobertures_dels_vigilants_que_ja_no_vigilen(client):
    # Prof 15 vigila i és absent: la vigilància la cobreix la VIGILANCIA_ABSENT.
    _publica(client, _horari(FILOSOFIA_1BAT))
    _assigna_vigilant(client, "1-BAT-A", "Prof 15")
    resp = client.put(
        f"/api/substitucions/{DATA}/absencies/Prof 15", json={"hores_absencia": ["10:00"], "updated_at_map": {}}
    )
    assert resp.status_code == 200, resp.text
    assert _cobertures_de_vigilancia(client) == [("10:00", "Prof 15", "VIGILANCIA_ABSENT")]

    _publica(client, _horari(("1-BAT", [_examen("1-BAT-B", "Filosofia")])), netejar=True)
    assert _cobertures_de_vigilancia(client) == []


def test_la_simulacio_no_toca_les_cobertures(client):
    _publica(client, _horari(FILOSOFIA_1BAT))
    _assigna_vigilant(client, "1-BAT-A", "Prof 15")
    _publica(client, _horari(("1-BAT", [_examen("1-BAT-B", "Filosofia")])), dry_run=True)
    assert _cobertures_de_vigilancia(client) == [("10:00", "Prof 15", "VIGILANCIA")]


# -------------------------------------------------------- grups sense classe


def test_marca_sense_classe_els_grups_indicats_a_les_hores_alliberades(client, centre):
    _alliberaments(centre, "1-BAT", ["10:00", "11:30"])
    resultat = _publica(client, _horari(FILOSOFIA_1BAT), grups_sense_classe=["1-BAT-A", "1-BAT-B"])
    assert resultat["grups_alliberats_creats"] == 4
    assert _grups_alliberats(centre) == [
        ("10:00", "1-BAT-A"),
        ("10:00", "1-BAT-B"),
        ("11:30", "1-BAT-A"),
        ("11:30", "1-BAT-B"),
    ]


def test_sense_llista_de_grups_marca_els_grups_actius_del_nivell(client, centre):
    _alliberaments(centre, "1-BAT", ["10:00"])
    with get_data_db_session(centre) as db:
        nivell = Nivell(codi="1-BAT", nom="1-BAT", ordre=0)
        db.add(nivell)
        db.flush()
        db.add_all(
            [
                Grup(codi="1-BAT-A", nom="1-BAT-A", nivell_id=nivell.id, ordre=0, actiu=True),
                Grup(codi="1-BAT-B", nom="1-BAT-B", nivell_id=nivell.id, ordre=1, actiu=False),
            ]
        )
        db.commit()
    _publica(client, _horari(FILOSOFIA_1BAT))
    assert _grups_alliberats(centre) == [("10:00", "1-BAT-A")]


def test_un_nivell_sense_hores_alliberades_no_marca_cap_grup(client, centre):
    _alliberaments(centre, "2-BAT", ["10:00"])
    _publica(client, _horari(FILOSOFIA_1BAT), grups_sense_classe=["1-BAT-A"])
    assert _grups_alliberats(centre) == []


def test_tornar_a_publicar_no_duplica_els_grups_sense_classe(client, centre):
    _alliberaments(centre, "1-BAT", ["10:00"])
    _publica(client, _horari(FILOSOFIA_1BAT), grups_sense_classe=["1-BAT-A"])
    resultat = _publica(client, _horari(FILOSOFIA_1BAT), grups_sense_classe=["1-BAT-A"])
    assert resultat["grups_alliberats_creats"] == 0
    assert _grups_alliberats(centre) == [("10:00", "1-BAT-A")]


# ------------------------------------------------- titulars com a vigilants


@pytest.fixture
def titular_alliberat(centre):
    """Prof 48, titular de Filosofia de 1-BAT-A, que queda sense classe a les 10:00."""
    _alliberaments(centre, "1-BAT", ["10:00"])
    with get_data_db_session(centre) as db:
        db.add(ConfiguracioExamen(assignatura="Filosofia", grup="1-BAT-A", titular="Prof 48", aula="A01"))
        db.commit()


def test_assigna_el_titular_alliberat_com_a_vigilant(client, titular_alliberat):
    resultat = _publica(client, _horari(FILOSOFIA_1BAT), auto_assign=True, grups_sense_classe=["1-BAT-A"])
    assert resultat["titulars_assignats"] == 1
    assert _resum(client) == [("10:00", "1-BAT", "1-BAT-A", "Filosofia", "Prof 48")]


def test_no_canvia_un_vigilant_ja_assignat(client, titular_alliberat):
    _publica(client, _horari(FILOSOFIA_1BAT), grups_sense_classe=["1-BAT-A"])
    _assigna_vigilant(client, "1-BAT-A", "Prof 3")
    resultat = _publica(client, _horari(FILOSOFIA_1BAT), auto_assign=True, grups_sense_classe=["1-BAT-A"])
    assert resultat["titulars_assignats"] == 0
    assert _resum(client) == [("10:00", "1-BAT", "1-BAT-A", "Filosofia", "Prof 3")]


def test_sense_l_opcio_no_s_assignen_titulars(client, titular_alliberat):
    _publica(client, _horari(FILOSOFIA_1BAT), auto_assign=False, grups_sense_classe=["1-BAT-A"])
    assert _resum(client) == [("10:00", "1-BAT", "1-BAT-A", "Filosofia", "")]


# ------------------------------------------- titular amb una absència coberta
# El planificador planifica exàmens, no persones: la persona es decideix en
# publicar, amb l'horari de cada data (Dia), que ja no té els professors amb
# una absència coberta aquell dia.


def test_un_titular_amb_absencia_coberta_no_s_assigna_i_hi_ha_un_avis(client, centre, titular_alliberat):
    with get_data_db_session(centre) as db:
        AbsenciaCobertaRepository.create(db, "Prof 48", DATA, DATA, "Llarga")
        db.commit()
    resultat = _publica(client, _horari(FILOSOFIA_1BAT), auto_assign=True, grups_sense_classe=["1-BAT-A"])
    assert resultat["titulars_assignats"] == 0
    assert _resum(client) == [("10:00", "1-BAT", "1-BAT-A", "Filosofia", "")]
    assert resultat["avisos"] == [
        {
            "codi": "titular_amb_absencia_coberta",
            "params": {
                "data": DATA,
                "hora": "10:00",
                "titular": "Prof 48",
                "assignatura": "Filosofia",
                "grups": "1-BAT-A",
            },
        }
    ]
    # Ni el titular ni ningú amb una absència coberta surt per vigilar-la
    disponibles = client.get(f"/api/vigilancies/{DATA}/10:00/disponibles").json()
    assert "Prof 48" not in {d["value"] for d in disponibles}


def test_sense_absencia_coberta_no_hi_ha_cap_avis(client, titular_alliberat):
    resultat = _publica(client, _horari(FILOSOFIA_1BAT), auto_assign=True, grups_sense_classe=["1-BAT-A"])
    assert resultat["titulars_assignats"] == 1 and resultat["avisos"] is None


def test_una_absencia_coberta_desada_despres_de_publicar_treu_les_vigilancies_futures(client, centre):
    """Publicat amb el titular com a vigilant; si després se li desa una
    absència coberta, se li treu la vigilància (d'avui endavant)."""
    avui = date.today()
    futur = (avui + timedelta(days=7 - avui.weekday())).isoformat()  # dilluns vinent
    config = {"1-BAT": {"durada": 1, "dates": [futur], "config": {futur: {"10:00": {"a": True, "i": True}}}}}
    with get_data_db_session(centre) as db:
        ConfiguracioRepository.set(db, SCHEDULER_ALLIBERAMENTS_KEY, json.dumps(config), tipus="json")
        ConfiguracioRepository.set(db, SCHEDULER_NIVELLS_KEY, json.dumps(["1-BAT"]), tipus="json")
        db.add(ConfiguracioExamen(assignatura="Filosofia", grup="1-BAT-A", titular="Prof 48", aula="A01"))
        db.commit()
    horari = _horari(FILOSOFIA_1BAT)
    horari["dies"][0]["data"] = futur
    resp = client.post(
        URL,
        json={
            "horari": horari,
            "setmanes": [{"Dilluns": futur}],
            "opcions": {"auto_assign_titulars": True, "netejar_existents": False},
            "grups_sense_classe": ["1-BAT-A"],
        },
    )
    assert resp.status_code == 200 and resp.json()["titulars_assignats"] == 1, resp.text
    assert [v["vigilant"] for v in client.get(f"/api/vigilancies/{futur}").json()] == ["Prof 48"]

    resp = client.post(
        "/api/absencies-cobertes",
        json={"professor": "Prof 48", "data_inici": futur, "data_final": futur, "motiu": ""},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["canvis"]["vigilancies_buidades"]
    assert [v["vigilant"] for v in client.get(f"/api/vigilancies/{futur}").json()] == [""]


# ------------------------------------------------- dates d'un curs anterior
# La configuració d'exàmens és la del curs actual: no es pot publicar sobre
# dates d'un curs anterior (seria escriure damunt de l'històric).


@pytest.fixture
def amb_cursos(centre):
    from datetime import date, timedelta

    from cursos.repositories import CursRepository

    avui = date.today()
    with get_data_db_session(centre) as db:
        CursRepository.create(db, "Curs anterior", avui - timedelta(days=400))
        CursRepository.create(db, "Curs actual", avui - timedelta(days=30))
        db.commit()
    return avui


def test_no_es_pot_publicar_en_dates_d_un_curs_anterior(client, amb_cursos):
    resp = client.post(URL, json={"horari": _horari(FILOSOFIA_1BAT), "setmanes": SETMANES})
    assert resp.status_code == 400
    assert "Curs anterior" in resp.json()["detail"] and "Curs actual" in resp.json()["detail"]
    assert _vigilancies(client) == []


def test_el_planificador_sap_si_les_dates_son_d_un_curs_anterior(client, amb_cursos):
    avui = amb_cursos.isoformat()
    assert client.get("/api/scheduler/curs-dates", params={"dates": avui}).json() == {"curs_anterior": None}
    assert client.get("/api/scheduler/curs-dates", params={"dates": f"{DATA},{avui}"}).json() == {
        "curs_anterior": {"cursos": ["Curs anterior"], "curs_actual": "Curs actual"}
    }


def test_sense_cursos_definits_no_es_comprova(client):
    assert client.get("/api/scheduler/curs-dates", params={"dates": DATA}).json() == {"curs_anterior": None}


# ------------------------------------- durades de l'examen i del titular


def _horari_amb_nom(nom, hora="10:00"):
    """Una sola franja amb l'examen de Filosofia de 1-BAT amb nom de sessió `nom`."""
    return {
        "dies": [
            {
                "dia": "Dilluns",
                "data": DATA,
                "sessions": [
                    {
                        "hora": hora,
                        "sessions_simultanees": [
                            {"curs": "1-BAT", "nom": nom, "examens": [_examen("1-BAT-A", "Filosofia")]}
                        ],
                    }
                ],
            }
        ]
    }


def test_un_examen_te_vigilancia_a_totes_les_hores_del_seu_grup_de_durada(client, centre):
    _durades(
        centre, titular=1, examen=1, grups=[{"assignatures": ["Filosofia (1-BAT)"], "durada": 1, "durada_examen": 2}]
    )
    _publica(client, _horari_amb_nom("Filosofia (1-BAT)", hora="08:00"))
    assert [v[0] for v in _resum(client)] == ["08:00", "09:00"]
    # Un altre examen sense grup de durada: la durada general (1 hora)
    _publica(client, _horari_amb_nom("Anglès (1-BAT)", hora="11:30"))
    assert [v[0] for v in _resum(client)] == ["11:30"]


def test_el_titular_vigila_les_hores_de_l_examen_en_que_esta_disponible(client, centre, titular_alliberat):
    # Examen de 2 hores a les 9:00. Prof 48 a les 9:00 fa classe amb 4-ESO-A
    # (no se li assigna); a les 10:00 el seu grup (1-BAT-A) no té classe: sí
    _alliberaments(centre, "1-BAT", ["09:00", "10:00"])
    _durades(centre, titular=1, examen=2)
    resultat = _publica(client, _horari(FILOSOFIA_1BAT, hora="09:00"), auto_assign=True, grups_sense_classe=["1-BAT-A"])
    assert resultat["titulars_assignats"] == 1
    assert _resum(client) == [
        ("09:00", "1-BAT", "1-BAT-A", "Filosofia", ""),
        ("10:00", "1-BAT", "1-BAT-A", "Filosofia", "Prof 48"),
    ]


def test_en_una_hora_lliure_no_s_assigna_el_titular(client, centre, titular_alliberat):
    # Al pati Prof 48 no té cap activitat («lliure»): pot no ser al centre
    _alliberaments(centre, "1-BAT", ["10:00", "PATI"])
    _durades(centre, titular=1, examen=2)
    _publica(client, _horari(FILOSOFIA_1BAT), auto_assign=True, grups_sense_classe=["1-BAT-A"])
    assert _resum(client) == [
        ("10:00", "1-BAT", "1-BAT-A", "Filosofia", "Prof 48"),
        ("PATI", "1-BAT", "1-BAT-A", "Filosofia", ""),
    ]


# ------------------------------------- grups sense classe: hores marcades


def test_s_alliberen_les_hores_marcades_encara_que_no_hi_hagi_examen_a_aquella_hora(client, centre):
    _alliberaments(centre, "1-BAT", ["09:00", "10:00", "11:30"])
    _publica(client, _horari(FILOSOFIA_1BAT, hora="10:00"), grups_sense_classe=["1-BAT-A"])
    assert _grups_alliberats(centre) == [("09:00", "1-BAT-A"), ("10:00", "1-BAT-A"), ("11:30", "1-BAT-A")]


def test_s_allibera_un_nivell_seleccionat_amb_marques_encara_que_no_tingui_examen_aquell_dia(client, centre):
    config = {
        niv: {"durada": 1, "dates": [DATA], "config": {DATA: {"10:00": {"a": True, "i": True}}}}
        for niv in ("1-BAT", "2-BAT")
    }
    with get_data_db_session(centre) as db:
        ConfiguracioRepository.set(db, SCHEDULER_ALLIBERAMENTS_KEY, json.dumps(config), tipus="json")
        ConfiguracioRepository.set(db, SCHEDULER_NIVELLS_KEY, json.dumps(["1-BAT", "2-BAT"]), tipus="json")
    _publica(client, _horari(FILOSOFIA_1BAT), grups_sense_classe=["1-BAT-A", "2-BAT-A"])  # només examen de 1-BAT
    assert _grups_alliberats(centre) == [("10:00", "1-BAT-A"), ("10:00", "2-BAT-A")]


def test_no_s_allibera_un_nivell_amb_marques_que_no_esta_seleccionat(client, centre):
    _alliberaments(centre, "2-BAT", ["10:00"], seleccionats=["1-BAT"])
    _publica(client, _horari(FILOSOFIA_1BAT), grups_sense_classe=["2-BAT-A"])
    assert _grups_alliberats(centre) == []
