"""
Configuració del planificador d'exàmens a través de l'API: durades, dates,
restriccions, exàmens fixats, costos dels professors i llistes d'opcions.
Descriuen el comportament actual (characterization tests).
"""
import pytest

from rate_limit import limiter
from suport_planificador import DATES, admin_de, alliberaments, centre_amb_examens, configura


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


@pytest.fixture
def centre():
    return centre_amb_examens()


@pytest.fixture
def client(centre):
    return centre[1]


# ------------------------------------------------------------------ accés

@pytest.mark.parametrize("metode, ruta", [
    ("get", "/api/scheduler/config"), ("put", "/api/scheduler/config"),
    ("get", "/api/scheduler/restriccions"), ("get", "/api/scheduler/costos-professors"),
    ("get", "/api/scheduler/dates"), ("post", "/api/scheduler/generate"),
])
def test_nomes_els_admins_fan_servir_el_planificador(centre, metode, ruta):
    client = admin_de(centre[0], role="user")
    assert getattr(client, metode)(ruta, **({} if metode == "get" else {"json": {}})).status_code == 403


# ------------------------------------------------------ durades i nivells

def test_la_configuracio_es_desa_i_es_torna(client):
    configura(client, durada_titular=1, durada_examen=2)
    config = client.get("/api/scheduler/config").json()
    assert config["nivells"] == ["1-BAT"]
    assert config["nivells_seleccionats"] == ["1-BAT"]
    assert config["assignacions_total"] == 6
    assert (config["durada_titular"], config["durada_examen"]) == (1, 2)
    assert config["alliberaments_per_nivell"] == alliberaments()


def test_les_hores_d_inici_venen_de_les_hores_alliberades_marcades(client):
    allib = alliberaments(hores_inici=("09:00",))
    allib["1-BAT"]["config"][DATES[0]]["10:00"] = {"a": True, "i": False}  # sense classe, però no s'hi comença
    configura(client, alliberaments_per_nivell=allib)
    assert client.get("/api/scheduler/config").json()["hores_per_nivell"] == {"1-BAT": ["09:00"]}


def test_sense_durada_d_examen_es_la_del_professor(client):
    client.put("/api/scheduler/config", json={"durada_titular": 2})
    config = client.get("/api/scheduler/config").json()
    assert (config["durada_titular"], config["durada_examen"]) == (2, 2)


# ------------------------------------------------------------------ dates

def test_les_dates_es_desen_i_es_tornen(client):
    assert client.get("/api/scheduler/dates").json() == {"selected_dates": []}
    assert client.put("/api/scheduler/dates", json={"selected_dates": DATES}).status_code == 200
    assert client.get("/api/scheduler/dates").json() == {"selected_dates": DATES}


# ----------------------------------------------------------- restriccions

AGRUPACIO = {"nom": "Llengües", "assignatures": ["Anglès (1-BAT)", "Català (1-BAT)"]}
INCOMPATIBLES = ["Filosofia (1-BAT)", "Català (1-BAT)"]


def _desa_restriccions(client, **dures):
    restr = client.get("/api/scheduler/restriccions").json()["restriccions"]
    restr["restriccions_dures"].update(dures)
    resp = client.put("/api/scheduler/restriccions", json={"restriccions": restr})
    assert resp.status_code == 200, resp.text
    return client.get("/api/scheduler/restriccions").json()["restriccions"]["restriccions_dures"]


def test_les_agrupacions_i_incompatibilitats_es_desen_amb_el_seu_pes(client):
    dures = _desa_restriccions(
        client, mateix_slot=[AGRUPACIO],
        no_mateix_slot={"Prof X": INCOMPATIBLES, "_pes_Prof X": 80})
    assert dures["mateix_slot"] == [dict(AGRUPACIO, pes=100)]
    assert dures["no_mateix_slot"] == {"Prof X": INCOMPATIBLES, "_pes_Prof X": 80}


def test_desar_les_restriccions_substitueix_les_anteriors(client):
    # La pantalla envia totes les restriccions cada cop: el que no hi és, s'esborra.
    _desa_restriccions(client, mateix_slot=[AGRUPACIO], no_mateix_slot={"Prof X": INCOMPATIBLES})
    dures = _desa_restriccions(client, mateix_slot=[], no_mateix_slot={})
    assert (dures["mateix_slot"], dures["no_mateix_slot"]) == ([], {})


def test_una_agrupacio_no_pot_barrejar_nivells(client):
    # Els motors col·loquen cada agrupació dins d'un nivell: per a exàmens de
    # nivells diferents al mateix moment hi ha la preferència "Mateix dia i hora".
    _desa_restriccions(client, mateix_slot=[AGRUPACIO])
    restr = client.get("/api/scheduler/restriccions").json()["restriccions"]
    restr["restriccions_dures"]["mateix_slot"] = [
        AGRUPACIO, {"nom": "Anglès", "assignatures": ["Anglès (1-BAT)", "Anglès (2-BAT)"]}]
    resp = client.put("/api/scheduler/restriccions", json={"restriccions": restr})
    assert resp.status_code == 400
    assert "Anglès" in resp.json()["detail"]
    # No es desa res: es conserven les restriccions d'abans
    dures = client.get("/api/scheduler/restriccions").json()["restriccions"]["restriccions_dures"]
    assert dures["mateix_slot"] == [dict(AGRUPACIO, pes=100)]


def test_els_examens_de_nivells_diferents_poden_anar_junts_amb_la_preferencia(client):
    restr = client.get("/api/scheduler/restriccions").json()["restriccions"]
    restr["preferencies"]["mateix_slot"] = [{"assignatures": ["Anglès (1-BAT)", "Anglès (2-BAT)"], "pes": 100}]
    assert client.put("/api/scheduler/restriccions", json={"restriccions": restr}).status_code == 200


# ------------------------------------------ restriccions d'un curs anterior
# Si canvien els noms (p.ex. el nivell passa de 1-BATX a 1-BAT), les
# restriccions antigues ja no s'apliquen a cap examen.

ANTIGUES = {
    "mateix_slot": [{"nom": "Llengües", "assignatures": ["Català (1-BAT)", "Llengua Catalana (1-BAT)"]},
                    {"nom": "1.1", "assignatures": ["1.1-Mat (1-BATX)", "1.1-Llatí (1-BATX)"]}],
    "no_mateix_slot": {"Prof X": ["1.1-Mat (1-BATX)", "Filosofia (1-BAT)"], "_pes_Prof X": 100,
                       "Prof 48": ["Filosofia (1-BAT)", "Anglès"], "_pes_Prof 48": 80},
    "assignatures_dia_fix": {"Castellà (1-BATX)": "Dilluns", "_pes_Castellà (1-BATX)": 100},
}


def test_el_desplegable_nomes_te_les_assignatures_actuals(client):
    _desa_restriccions(client, **ANTIGUES)
    esperat = ["Anglès (1-BAT)", "Català (1-BAT)", "Filosofia (1-BAT)"]
    assert client.get("/api/scheduler/sessions-info", params={"nivells": "1-BAT"}).json() == esperat
    assert client.get("/api/scheduler/assignatures-actives").json() == esperat


def test_es_detecten_les_restriccions_amb_assignatures_que_ja_no_existeixen(client):
    _desa_restriccions(client, **ANTIGUES)
    resp = client.get("/api/scheduler/restriccions").json()
    # "Anglès" sense nivell sí que existeix (s'aplica a l'Anglès de cada nivell)
    assert resp["assignatures_inexistents"] == [
        "1.1-Llatí (1-BATX)", "1.1-Mat (1-BATX)", "Castellà (1-BATX)", "Llengua Catalana (1-BAT)"]


def test_treure_les_assignatures_que_ja_no_existeixen(client):
    _desa_restriccions(client, **ANTIGUES)
    restr = client.get("/api/scheduler/restriccions").json()["restriccions"]
    restr["preferencies"]["mateix_slot"] = [{"assignatures": ["Anglès (1-BAT)", "Anglès (1-BATX)"], "pes": 100}]
    client.put("/api/scheduler/restriccions", json={"restriccions": restr})

    resp = client.post("/api/scheduler/restriccions/treure-inexistents")
    assert resp.status_code == 200, resp.text
    assert resp.json()["trets"] == [
        "1.1-Llatí (1-BATX)", "1.1-Mat (1-BATX)", "Anglès (1-BATX)", "Castellà (1-BATX)", "Llengua Catalana (1-BAT)"]

    restr = client.get("/api/scheduler/restriccions").json()
    assert restr["assignatures_inexistents"] == []
    dures = restr["restriccions"]["restriccions_dures"]
    # L'agrupació que es queda amb un examen es conserva; la que es queda buida, no
    assert dures["mateix_slot"] == [{"nom": "Llengües", "assignatures": ["Català (1-BAT)"], "pes": 100}]
    # Una incompatibilitat amb un sol examen ja no té sentit; les altres es conserven amb el seu pes
    assert dures["no_mateix_slot"] == {"Prof 48": ["Filosofia (1-BAT)", "Anglès"], "_pes_Prof 48": 80}
    assert dures["assignatures_dia_fix"] == {}
    assert restr["restriccions"]["preferencies"]["mateix_slot"] == []


def test_fixar_i_desfixar_un_examen(client):
    resp = client.post("/api/scheduler/restriccions/pin",
                       json={"pins": [{"nom": "Català (1-BAT)", "dia": "Dilluns", "hora": "11:30"}]})
    assert resp.json()["pins"] == {"assignatures_dia_fix": {"Català (1-BAT)": "Dilluns"},
                                   "assignatures_hora_fix": {"Català (1-BAT)": "11:30"}}
    # Tornar-lo a fixar el mou; no el duplica
    resp = client.post("/api/scheduler/restriccions/pin",
                       json={"pins": [{"nom": "Català (1-BAT)", "dia": "Dimarts", "hora": "09:00"}]})
    assert resp.json()["pins"]["assignatures_dia_fix"] == {"Català (1-BAT)": "Dimarts"}

    resp = client.post("/api/scheduler/restriccions/pin", json={"unpins": ["Català (1-BAT)"]})
    assert resp.json()["pins"] == {"assignatures_dia_fix": {}, "assignatures_hora_fix": {}}


# ---------------------------------------------------- costos dels professors

def test_sense_costos_desats_es_tornen_els_de_per_defecte(client):
    from scheduler_engine.defaults import DEFAULT_COST_PROFESSORS
    costos = client.get("/api/scheduler/costos-professors").json()["costos_professors"]
    assert costos == {"globals": dict(DEFAULT_COST_PROFESSORS), "individuals": {}}


def test_costos_globals_i_individuals(client):
    client.put("/api/scheduler/costos-professors",
               json={"globals": {"substitucio": 50}, "individuals": {"Prof 48": {"abans_jornada": 90}}})
    client.put("/api/scheduler/costos-professors/Prof 26", json={"substitucio": 100})
    costos = client.get("/api/scheduler/costos-professors").json()["costos_professors"]
    assert costos["globals"]["substitucio"] == 50
    assert costos["individuals"] == {"Prof 48": {"abans_jornada": 90}, "Prof 26": {"substitucio": 100}}

    assert client.delete("/api/scheduler/costos-professors/Prof 48").json()["deleted"] == 1
    costos = client.get("/api/scheduler/costos-professors").json()["costos_professors"]
    assert costos["individuals"] == {"Prof 26": {"substitucio": 100}}


# ---------------------------------------------------------------- opcions

def test_les_sessions_son_assignatura_i_nivell(client):
    assert client.get("/api/scheduler/sessions-info").json() == [
        "Anglès (1-BAT)", "Català (1-BAT)", "Filosofia (1-BAT)"]
    assert client.get("/api/scheduler/sessions-info", params={"nivells": "2-BAT"}).json() == []


def test_els_grups_combinats_s_expandeixen(client):
    client.post("/api/config/abreviatures", json={"grups_originals": "1-BAT-A,1-BAT-B", "abreviatura": "1-BAT-AB"})
    client.post("/api/config/grups/1-BAT", json={"codi": "1-BAT-AB"})
    grups = client.get("/api/scheduler/grups-nivells").json()
    per_codi = {g["codi"]: g for g in grups["grups_per_nivell"]["1-BAT"]}
    assert per_codi["1-BAT-A"] == {"codi": "1-BAT-A", "es_abreviatura": False, "grups_expandits": []}
    assert per_codi["1-BAT-AB"]["grups_expandits"] == ["1-BAT-A", "1-BAT-B"]
    assert "09:00" in grups["hores_lectives"]


# -------------------------------- configuració d'exàmens d'un curs anterior

def test_es_detecten_les_assignacions_amb_grups_o_titulars_que_ja_no_son_a_l_horari(client):
    for assignacio in (
        {"assignatura": "1.1-Mat", "grup": "1-BATX-A", "titular": "Prof 1"},            # grup antic
        {"assignatura": "Filosofia", "grup": "1-BAT-A", "titular": "Prof Jubilat"},     # titular que ja no hi és
        {"assignatura": "1.1 Prof 7", "grup": "1-BAT-A,1-BAT-B", "titular": "Prof 7"},  # nom canviat a mà: vàlida
    ):
        assert client.post("/api/config/assignacions", json=assignacio).status_code == 200
    client.post("/api/config/abreviatures", json={"grups_originals": "1-BAT-A,1-BAT-B", "abreviatura": "1-BAT-AB"})
    client.post("/api/config/assignacions", json={"assignatura": "1.2 Prof 20", "grup": "1-BAT-AB", "titular": "Prof 20"})

    obsoletes = client.get("/api/config/assignacions-obsoletes").json()["assignacions"]
    assert sorted((a["assignatura"], a["grup"], a["titular"], a["motius"]) for a in obsoletes) == [
        ("1.1-Mat", "1-BATX-A", "Prof 1", ["grup"]),
        ("Filosofia", "1-BAT-A", "Prof Jubilat", ["titular"]),
    ]

    # Es treuen amb l'esborrat de diverses assignacions que ja existeix
    resp = client.request("DELETE", "/api/config/assignacions", json={"ids": [a["id"] for a in obsoletes]})
    assert resp.json()["eliminades"] == 2
    assert client.get("/api/config/assignacions-obsoletes").json()["assignacions"] == []
    assert len(client.get("/api/config/assignacions").json()["assignacions"]) == 8
