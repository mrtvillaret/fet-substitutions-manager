"""
Generar l'horari d'exàmens (POST /api/scheduler/generate) amb la mateixa
petició que fa la pantalla. El motor és aleatori: els tests comproven el que
s'ha de complir sempre, no una solució concreta.

Horari d'exemple: 1-BAT i 2-BAT, grups A i B. Filosofia la fa Prof 48 a tots
dos nivells. Tot el que es fa servir (assignatures, titulars) surt de l'XML
d'exemple a través de la mateixa importació de l'aplicació.
"""
import re

import pytest

from rate_limit import limiter
from suport_planificador import DATES, DIES, admin_de, alliberaments, centre_amb_examens, configura
from suport_api import nova_institucio

URL = "/api/scheduler/generate"
PETICIO = {"data_inici": DATES[0], "data_final": DATES[-1], "selected_dates": DATES, "dies_utilitzar": DIES}


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


def _genera(client, motor="v3"):
    resp = client.post(URL, json=dict(PETICIO, motor=motor))
    assert resp.status_code == 200, resp.text
    return resp.json()["horari"]


def _col_locats(horari):
    """{sessió: (data, hora, [(grup, titular)])}"""
    col = {}
    for dia in horari["dies"]:
        for slot in dia["sessions"]:
            for sessio in slot["sessions_simultanees"]:
                col[sessio["nom"]] = (dia["data"], slot["hora"], sorted((e["grup"], e["titular"]) for e in sessio["examens"]))
    return col


@pytest.fixture
def un_nivell():
    _, client = centre_amb_examens()
    configura(client)
    return client


@pytest.fixture
def dos_nivells():
    _, client = centre_amb_examens(nivells=("1-BAT", "2-BAT"))
    configura(client, nivells_actius=["1-BAT", "2-BAT"],
              alliberaments_per_nivell=alliberaments(nivells=("1-BAT", "2-BAT")))
    return client


def test_col_loca_tots_els_examens_a_les_dates_i_hores_d_inici(un_nivell):
    horari = _genera(un_nivell)
    assert horari["metadata"].get("viable", True)
    col = _col_locats(horari)
    assert sorted(col) == ["Anglès (1-BAT)", "Català (1-BAT)", "Filosofia (1-BAT)"]
    for data, hora, _ in col.values():
        assert data in DATES and hora in ("09:00", "11:30")
    # Un examen per franja: són els mateixos alumnes
    assert len({(data, hora) for data, hora, _ in col.values()}) == 3
    assert col["Filosofia (1-BAT)"][2] == [("1-BAT-A", "Prof 48"), ("1-BAT-B", "Prof 48")]


def test_un_examen_fixat_va_on_s_ha_fixat(un_nivell):
    un_nivell.post("/api/scheduler/restriccions/pin",
                   json={"pins": [{"nom": "Català (1-BAT)", "dia": "Dilluns", "hora": "11:30"}]})
    for _ in range(3):
        assert _col_locats(_genera(un_nivell))["Català (1-BAT)"][:2] == (DATES[0], "11:30")


def _agrupa(client, nom, sessions):
    restr = client.get("/api/scheduler/restriccions").json()["restriccions"]
    restr["restriccions_dures"]["mateix_slot"] = [{"nom": nom, "assignatures": sessions}]
    assert client.put("/api/scheduler/restriccions", json={"restriccions": restr}).status_code == 200


def test_una_franja_d_optatives_va_sencera_a_la_mateixa_hora():
    # Com a la demo: la franja 1.1 de 1-BAT (alumnes de A i B barrejats) la
    # fan tres professors; cada un és un examen i van tots alhora.
    institucio, client = centre_amb_examens()
    propostes = client.get("/api/config/importar-assignacions/preview").json()["propostes"]
    franja = [dict(p, assignatura=f"1.1 {p['titular']}") for p in propostes
              if p["assignatura"] == "1.1" and p["nivell"] == "1-BAT"]
    assert len(franja) == 3
    client.post("/api/config/importar-assignacions", json={"propostes": franja})
    configura(client)
    sessions = [f"{p['assignatura']} (1-BAT)" for p in franja]
    _agrupa(client, "1.1", sessions)
    for _ in range(3):
        horari = _genera(client)
        assert horari["metadata"].get("viable", True), horari["metadata"].get("incompatibilitats")
        col = _col_locats(horari)
        assert len({col[s][:2] for s in sessions}) == 1


@pytest.mark.parametrize("motor", ["v3", "v2", "v2-backtrack"])
def test_dos_examens_de_nivells_diferents_van_junts_amb_la_preferencia(dos_nivells, motor):
    # Una agrupació no pot barrejar nivells (es rebutja en desar-la): per això
    # hi ha la preferència "Mateix dia i hora".
    restr = dos_nivells.get("/api/scheduler/restriccions").json()["restriccions"]
    restr["preferencies"]["mateix_slot"] = [{"assignatures": ["Anglès (1-BAT)", "Anglès (2-BAT)"], "pes": 100}]
    dos_nivells.put("/api/scheduler/restriccions", json={"restriccions": restr})
    for _ in range(3):
        col = _col_locats(_genera(dos_nivells, motor=motor))
        assert len(col) == 6
        assert col["Anglès (1-BAT)"][:2] == col["Anglès (2-BAT)"][:2]


def test_els_examens_incompatibles_no_coincideixen(dos_nivells):
    # El motor no evita sol que un professor tingui dos exàmens alhora: cal
    # definir-ho com a incompatibilitat (Prof 48 fa Filosofia a tots dos nivells).
    restr = dos_nivells.get("/api/scheduler/restriccions").json()["restriccions"]
    restr["restriccions_dures"]["no_mateix_slot"] = {
        "Prof 48": ["Filosofia (1-BAT)", "Filosofia (2-BAT)"], "_pes_Prof 48": 100}
    dos_nivells.put("/api/scheduler/restriccions", json={"restriccions": restr})
    for _ in range(5):
        col = _col_locats(_genera(dos_nivells))
        assert len(col) == 6
        assert col["Filosofia (1-BAT)"][:2] != col["Filosofia (2-BAT)"][:2]


def test_si_no_hi_caben_diu_que_no_es_viable(un_nivell):
    # Tres exàmens del mateix nivell i una sola franja possible
    configura(un_nivell, alliberaments_per_nivell=alliberaments(dates=DATES[:1], hores_inici=("09:00",)))
    horari = _genera(un_nivell)
    assert horari["metadata"]["viable"] is False
    assert horari["metadata"]["incompatibilitats"]


def test_sense_horari_xml_no_es_pot_generar():
    institucio = nova_institucio()
    assert admin_de(institucio).post(URL, json=PETICIO).status_code == 400


def test_un_professor_amb_examens_de_dos_nivells_alhora_surt_a_les_incidencies(dos_nivells):
    # Es permet (si no es vol, es defineix una incompatibilitat), però s'avisa.
    dos_nivells.post("/api/scheduler/restriccions/pin", json={"pins": [
        {"nom": "Filosofia (1-BAT)", "dia": "Dilluns", "hora": "09:00"},
        {"nom": "Filosofia (2-BAT)", "dia": "Dilluns", "hora": "09:00"}]})
    logs = [l for l in _genera(dos_nivells)["metadata"]["logs"] if "Prof 48 →" in l]
    assert any(l.startswith("⚠️ AVÍS: Prof 48 → té exàmens de nivells diferents a 09:00 el Dilluns") for l in logs)
    assert any(l.startswith("🔗 ENLLAÇ: Prof 48 → gestiona 2 exàmens de nivells diferents a 09:00 el Dilluns: "
                            "Filosofia (1-BAT), Filosofia (2-BAT)") for l in logs), logs


# ------------------------------------------------------------------ costos
# El cost que optimitza cada motor ha de ser el real: si el motor el
# calculés diferent, podria donar per bona una solució pitjor. Ha de
# coincidir amb el que recalcula la pantalla i amb la suma de les incidències.

def _punts(logs):
    return sum(int(m.group(1)) for l in logs if (m := re.search(r"\(punt: *(\d+)\)", l)))


def _costos(client, horari):
    recalculat = client.post("/api/scheduler/recalcular-cost", json={
        "horari": horari, "data_referencia": DATES[0], "selected_dates": DATES}).json()
    return horari["metadata"]["cost_total"], recalculat["cost_total"], _punts(horari["metadata"]["logs"])


@pytest.fixture
def filosofia_i_angles_fixats(dos_nivells):
    # Prof 48 vigila Filosofia de 1r i de 2n alhora: deixa una sola classe
    # (Optativa42 amb 4-ESO-A). Prof 25 (Anglès de 1r) en deixa una altra.
    dos_nivells.post("/api/scheduler/restriccions/pin", json={"pins": [
        {"nom": "Filosofia (1-BAT)", "dia": "Dilluns", "hora": "09:00"},
        {"nom": "Filosofia (2-BAT)", "dia": "Dilluns", "hora": "09:00"},
        {"nom": "Anglès (1-BAT)", "dia": "Dilluns", "hora": "11:30"}]})
    dos_nivells.put("/api/scheduler/costos-professors", json={"globals": {"substitucio": 80}})
    return dos_nivells


@pytest.mark.parametrize("motor", ["v3", "v2", "v2-backtrack"])
def test_un_professor_amb_dos_examens_alhora_es_compta_un_sol_cop(filosofia_i_angles_fixats, motor):
    horari = _genera(filosofia_i_angles_fixats, motor=motor)
    assert _costos(filosofia_i_angles_fixats, horari) == (160, 160, 160)
    [linia] = [l for l in horari["metadata"]["logs"] if l.startswith("🚨 Prof 48 ")]
    assert "(Filosofia (1-BAT))->1-BAT, (Filosofia (2-BAT))->2-BAT → ha de ser SUBSTITUÏT a Optativa42" in linia


@pytest.mark.parametrize("motor", ["v3", "v2", "v2-backtrack"])
def test_els_costos_individuals_dels_professors_compten(filosofia_i_angles_fixats, motor):
    filosofia_i_angles_fixats.put("/api/scheduler/costos-professors", json={
        "globals": {"substitucio": 80}, "individuals": {"Prof 25": {"substitucio": 0}, "Prof 48": {"substitucio": 30}}})
    horari = _genera(filosofia_i_angles_fixats, motor=motor)
    assert _costos(filosofia_i_angles_fixats, horari) == (30, 30, 30)


def test_el_motor_v3_fa_tots_els_reinicis(dos_nivells):
    # Abans s'aturava al primer reinici viable: cada reinici acaba en un mínim
    # local diferent i quedar-se amb el primer donava horaris pitjors.
    from scheduler_engine.generators.v3_sa import REINICIS
    logs = _genera(dos_nivells)["metadata"]["logs"]
    assert any(f"Reinici {REINICIS}/{REINICIS}" in l for l in logs) or any("Temps esgotat" in l for l in logs)


# ------------------------------------------------- l'últim horari generat

def test_el_planificador_recorda_l_ultim_horari_generat(un_nivell):
    assert un_nivell.get("/api/scheduler/ultim-resultat").json() is None
    horari = _genera(un_nivell)
    desat = un_nivell.get("/api/scheduler/ultim-resultat").json()
    assert desat["desat"]
    assert desat["resultat"]["dies_utilitzar"] == DIES
    assert _col_locats(desat["resultat"]["horari"]) == _col_locats(horari)


def test_un_horari_editat_a_ma_passa_a_ser_l_ultim(un_nivell):
    horari = _genera(un_nivell)
    # L'editor envia l'horari modificat a recalcular el cost: es desa aquest
    horari["metadata"]["editat_a_ma"] = True
    resp = un_nivell.post("/api/scheduler/recalcular-cost", json={
        "horari": horari, "data_referencia": DATES[0], "selected_dates": DATES})
    assert resp.status_code == 200
    desat = un_nivell.get("/api/scheduler/ultim-resultat").json()["resultat"]
    assert desat["horari"]["metadata"]["editat_a_ma"] is True
    assert desat["horari"]["metadata"]["cost_total"] == resp.json()["cost_total"]
    assert desat["dies_utilitzar"] == DIES


def test_un_intent_no_viable_no_esborra_l_ultim_horari(un_nivell):
    horari = _genera(un_nivell)
    configura(un_nivell, alliberaments_per_nivell=alliberaments(dates=DATES[:1], hores_inici=("09:00",)))
    assert _genera(un_nivell)["metadata"]["viable"] is False
    assert _col_locats(un_nivell.get("/api/scheduler/ultim-resultat").json()["resultat"]["horari"]) == _col_locats(horari)
