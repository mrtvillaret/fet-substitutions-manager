"""
Planificador: el nivell d'un grup surt de les taules de la configuració
d'exàmens (grups de cada nivell i abreviatures), mai de trossos del nom.
Amb nivells que comparteixen
el començament («1-ESO» i «1-ESO-PDC»), un grup de 1-ESO-PDC no és de 1-ESO.
Un grup d'una assignació que no és a cap nivell no es planifica, amb avís.
"""

import json
from types import SimpleNamespace

import pytest
from suport_planificador import DATES, DIES, alliberaments, centre_amb_examens, configura

from planificador.examens import examens
from planificador.publicacio import PublicacioExamens
from rate_limit import limiter
from scheduler_engine.core.availability import analitzar_disponibilitat_sessio
from scheduler_engine.core.constraints import es_slot_valid_per_nivell
from scheduler_engine.core.missatges import missatge
from scheduler_engine.core.nivells import NivellsDelsGrups
from scheduler_engine.generators.v2_intents import GeneradorV2Intents
from scheduler_engine.generators.v3_sa import GeneradorV3SA

NIVELLS = ["1-ESO", "1-ESO-PDC"]
TAULES = NivellsDelsGrups(
    {"1-ESO": ["1-ESO-A", "1-ESO-B"], "1-ESO-PDC": ["1-ESO-PDC-A"]},
    {"1-ESO-AB": ["1-ESO-A", "1-ESO-B"]},
)


# ------------------------------------------------------------------ la funció


def test_nivell_de_cada_grup_per_les_taules():
    assert TAULES.nivell("1-ESO-A") == "1-ESO"
    assert TAULES.nivell("1-ESO-PDC-A") == "1-ESO-PDC"
    assert TAULES.nivell("1-ESO-AB") == "1-ESO"  # abreviatura
    assert TAULES.nivell("1-ESO-A, 1-ESO-B") == "1-ESO"  # llista de l'XML
    assert TAULES.nivell("1-ESO-PDC") == "1-ESO-PDC"  # el nivell sencer


def test_un_grup_que_no_es_a_cap_nivell_no_en_te():
    assert TAULES.nivell("1-ESO-C") is None  # comença com 1-ESO, però no hi és
    assert TAULES.nivells("1-ESO-C") == set()
    assert TAULES.sense_nivell("1-ESO-C, 1-ESO-A, 1-ESO-C") == ["1-ESO-C"]
    assert TAULES.sense_nivell("1-ESO-AB") == []


def test_grups_de_dos_nivells():
    assert TAULES.nivells("1-ESO-A,1-ESO-PDC-A") == {"1-ESO", "1-ESO-PDC"}
    assert TAULES.nivell("1-ESO-A,1-ESO-PDC-A") is None


def test_nivell_entre_els_actius():
    assert TAULES.nivell("1-ESO-PDC-A", entre=["1-ESO"]) is None
    assert TAULES.nivell("1-ESO-PDC-A", entre=NIVELLS) == "1-ESO-PDC"


def test_de_la_configuracio_mestra_i_anada_i_tornada_pels_motors():
    master = {
        "nivells": {"1-ESO": {"grups": ["1-ESO-A", "1-ESO-B"]}, "1-ESO-PDC": {"grups": ["1-ESO-PDC-A"]}},
        "abreviatures": {"1-ESO-A, 1-ESO-B": "1-ESO-AB"},
    }
    taules = NivellsDelsGrups.de_master(master)
    assert taules.grups_per_nivell == TAULES.grups_per_nivell
    assert taules.abreviatures == TAULES.abreviatures
    tornada = NivellsDelsGrups.de_config(json.loads(json.dumps(taules.a_config())))
    assert tornada.grups_per_nivell == TAULES.grups_per_nivell
    assert tornada.abreviatures == TAULES.abreviatures


# ------------------------------------------------------- exàmens de cada nivell


def _config(tmp_path, assignacions):
    config = {"assignatures": {"Mates": {"assignacions": assignacions}}, **TAULES.a_config()}
    ruta = tmp_path / "config.json"
    ruta.write_text(json.dumps(config), encoding="utf-8")
    return str(ruta)


@pytest.mark.parametrize("motor", [GeneradorV2Intents, GeneradorV3SA])
def test_cada_examen_va_al_nivell_del_seu_grup(tmp_path, motor):
    ruta = _config(
        tmp_path,
        [
            {"grup": "1-ESO-A", "titular": "Anna", "aula": ""},
            {"grup": "1-ESO-PDC-A", "titular": "Pere", "aula": ""},
            {"grup": "1-ESO-C", "titular": "Joan", "aula": ""},  # a cap nivell
        ],
    )
    gen = motor(ruta, "", nivells_actius=NIVELLS)
    gen.carregar_dades()
    grups = {n: [g for s in ss for g in (e["grup"] for e in s["examens"])] for n, ss in gen.sessions_per_nivell.items()}
    assert grups == {"1-ESO": ["1-ESO-A"], "1-ESO-PDC": ["1-ESO-PDC-A"]}


# ------------------------------------------------- alliberats a l'anàlisi


def test_la_classe_dun_grup_de_pdc_no_queda_alliberada_pel_nivell_1_eso():
    """1-ESO està alliberat a les 9 i 1-ESO-PDC no: qui té classe amb 1-ESO-PDC-A
    l'ha de deixar (substitució), i la classe és de 1-ESO-PDC."""
    alliberaments = {
        "1-ESO": {"config": {"2026-04-20": {"09:00": {"a": True}}}},
        "1-ESO-PDC": {"config": {"2026-04-20": {"09:00": {"a": False}}}},
    }
    horaris = {"Pere": {"dilluns": {"09:00": {"grup": "1-ESO-PDC-A", "assignatura": "Mates"}}}}
    sessio = {"nom": "Mates (1-ESO)", "curs": "1-ESO", "examens": [{"titular": "Pere", "grup": "1-ESO-A"}]}
    analisi = analitzar_disponibilitat_sessio(
        sessio,
        "Dilluns",
        "09:00",
        horaris,
        ["09:00", "10:00"],
        NIVELLS,
        alliberaments_per_nivell=alliberaments,
        data_iso="2026-04-20",
        nivells_dels_grups=TAULES,
    )
    assert [d["professor"] for d in analisi["substitucions"]] == ["Pere"]
    assert [d["professor"] for d in analisi["classe_1-ESO-PDC"]] == ["Pere"]
    assert analisi["classe_1-ESO"] == []


# --------------------------------------------- franges d'inici de cada nivell


def test_inicis_del_nivell_1_eso_pdc_no_son_els_de_1_eso():
    restriccions = {
        "restriccions_dures": {
            "slots_valids_per_nivell": {"1-ESO": {"Dilluns": ["09:00"]}, "1-ESO-PDC": {"Dilluns": ["10:00"]}}
        }
    }
    assert es_slot_valid_per_nivell("1-ESO-PDC", "Dilluns", "10:00", restriccions)
    assert not es_slot_valid_per_nivell("1-ESO-PDC", "Dilluns", "09:00", restriccions)


# ----------------------------------- llista d'exàmens i grups que es publiquen


def test_llista_dexamens_amb_el_nivell_de_les_taules():
    assignacions = [
        {"assignatura": "Mates", "grup": "1-ESO-PDC-A"},
        {"assignatura": "Català", "grup": "1-ESO-AB"},
        {"assignatura": "Física", "grup": "1-ESO-C"},
    ]
    assert examens(assignacions, TAULES) == ["Català (1-ESO)", "Física", "Mates (1-ESO-PDC)"]
    assert examens(assignacions, TAULES, only_nivells=["1-ESO"]) == ["Català (1-ESO)"]


def test_publicar_allibera_cada_grup_amb_el_seu_nivell():
    cfg = SimpleNamespace(
        alliberaments={"1-ESO": {}, "1-ESO-PDC": {}}, nivells_actius=lambda: NIVELLS, nivells_dels_grups=TAULES
    )
    publicacio = PublicacioExamens(None, cfg, [], [], False)
    assert publicacio._nivell_del_grup("1-ESO-PDC-A") == "1-ESO-PDC"
    assert publicacio._nivell_del_grup("1-ESO-C") is None


# ---------------------------------------------------- avís a la generació


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


def test_generar_avisa_dels_grups_que_no_son_a_cap_nivell():
    _, client = centre_amb_examens()
    configura(client)
    resp = client.post("/api/config/assignacions", json={"assignatura": "Filosofia", "grup": "1-BAT-Z"})
    assert resp.status_code == 200, resp.text
    peticio = {"data_inici": DATES[0], "data_final": DATES[-1], "selected_dates": DATES, "dies_utilitzar": DIES}
    resp = client.post("/api/scheduler/generate", json=dict(peticio, motor="v2"))
    assert resp.status_code == 200, resp.text
    horari = resp.json()["horari"]
    assert missatge("grup_sense_nivell", grup="1-BAT-Z", assignatures=["Filosofia"]) in horari["metadata"]["logs"]
    # L'examen no es planifica amb 1-BAT
    grups = {
        e["grup"]
        for d in horari["dies"]
        for s in d["sessions"]
        for ss in s["sessions_simultanees"]
        for e in ss["examens"]
    }
    assert "1-BAT-Z" not in grups


# ---------------------------------------- avís: nivell sense hores alliberades


def _cfg(alliberaments):
    from planificador.config import ConfigPlanificador

    return ConfigPlanificador(
        config={"assignatures": {}},
        restriccions={},
        durada_titular=1,
        durada_examen=1,
        nivells_configurats=[],
        nivells_master=[],
        dates_configurades=[],
        alliberaments=alliberaments,
        durades_per_sessio={},
        durades_examen_per_sessio={},
        no_substituir=frozenset(),
        ultim_professor="",
    )


def test_sense_cap_hora_alliberada_avisa_de_cada_nivell_actiu():
    """Sense alliberaments, l'anàlisi considera cada nivell
    actiu lliure tot el dia (no canvia); la pantalla ho avisa."""
    assert _cfg({}).avisos(NIVELLS) == [
        missatge("nivell_sense_hores_alliberades", nivell="1-ESO"),
        missatge("nivell_sense_hores_alliberades", nivell="1-ESO-PDC"),
    ]


def test_amb_hores_alliberades_no_hi_ha_avis():
    alliberaments = {"1-ESO": {"config": {"2026-04-20": {"09:00": {"a": True}}}}}
    assert _cfg(alliberaments).avisos(NIVELLS) == []


def test_recalcular_el_cost_amb_un_grup_sense_nivell_respon_amb_l_avis():
    """Els avisos de la configuració (dades, no text) també van als logs del
    recàlcul; l'esquema de resposta només hi acceptava text i responia 500."""
    _, client = centre_amb_examens()
    configura(client)
    resp = client.post("/api/config/assignacions", json={"assignatura": "Filosofia", "grup": "1-BAT-Z"})
    assert resp.status_code == 200, resp.text
    peticio = {"data_inici": DATES[0], "data_final": DATES[-1], "selected_dates": DATES, "dies_utilitzar": DIES}
    horari = client.post("/api/scheduler/generate", json=dict(peticio, motor="v2")).json()["horari"]
    resp = client.post(
        "/api/scheduler/recalcular-cost",
        json={"horari": horari, "data_referencia": DATES[0], "selected_dates": DATES},
    )
    assert resp.status_code == 200, resp.text
    assert missatge("grup_sense_nivell", grup="1-BAT-Z", assignatures=["Filosofia"]) in resp.json()["logs"]


def test_nivell_amb_alliberaments_pero_cap_hora_a_avisa():
    """Un nivell actiu amb alliberaments però cap hora «a» no té cap hora
    lliure per als exàmens (l'anàlisi no canvia, només s'avisa). Un nivell
    actiu que no surt als alliberaments no en té de definits: no avisa."""
    alliberaments = {
        "1-ESO": {"config": {"2026-04-20": {"09:00": {"i": True}, "10:00": {"a": False}}}},
        "1-ESO-PDC": {"config": {"2026-04-20": {"09:00": {"a": True}}}},
        "2-ESO": {"config": {}},
    }
    assert _cfg(alliberaments).avisos([*NIVELLS, "2-ESO", "3-ESO"]) == [
        missatge("nivell_alliberaments_sense_hores", nivell="1-ESO"),
        missatge("nivell_alliberaments_sense_hores", nivell="2-ESO"),
    ]
    # Només els nivells actius
    assert _cfg(alliberaments).avisos(["1-ESO-PDC"]) == []


# ------------------------------- avís de grup sense nivell: no viable i anàlisi


def _centre_amb_grup_sense_nivell(**config):
    _, client = centre_amb_examens()
    configura(client, **config)
    resp = client.post("/api/config/assignacions", json={"assignatura": "Filosofia", "grup": "1-BAT-Z"})
    assert resp.status_code == 200, resp.text
    return client


AVIS_GRUP_Z = missatge("grup_sense_nivell", grup="1-BAT-Z", assignatures=["Filosofia"])


def test_no_viable_porta_l_avis_del_grup_sense_nivell():
    """El diàleg de no viable el mostra dels logs del resultat."""
    # Tres exàmens de 1-BAT i una sola franja amb inici: no és viable
    client = _centre_amb_grup_sense_nivell(
        alliberaments_per_nivell=alliberaments(dates=[DATES[0]], hores_inici=("09:00",))
    )
    peticio = {"data_inici": DATES[0], "data_final": DATES[0], "selected_dates": [DATES[0]], "dies_utilitzar": DIES[:1]}
    resp = client.post("/api/scheduler/generate", json=dict(peticio, motor="v2"))
    assert resp.status_code == 200, resp.text
    meta = resp.json()["horari"]["metadata"]
    assert meta["viable"] is False
    assert AVIS_GRUP_Z in meta["logs"]


def test_l_analisi_previa_porta_l_avis_del_grup_sense_nivell():
    client = _centre_amb_grup_sense_nivell()
    peticio = {"data_inici": DATES[0], "data_final": DATES[-1], "selected_dates": DATES, "dies_utilitzar": DIES}
    resp = client.post("/api/scheduler/analisi", json=peticio)
    assert resp.status_code == 200, resp.text
    assert resp.json()["avisos"] == [AVIS_GRUP_Z]
