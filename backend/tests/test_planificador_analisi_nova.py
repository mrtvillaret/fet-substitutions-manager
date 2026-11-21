"""Matriu i textos de l'anàlisi: contracte del lector real i context únic."""

import json
from copy import deepcopy
from dataclasses import replace

import pytest
from suport_motor_nou import config_inventada as config_inventada
from suport_motor_nou import xml_inventat as xml_inventat
from test_planificador_greedy_nou import problema_de

from planificador.motor.model import congela
from planificador.motor.textos_analisi import TextosAnalisi


def _bytes(dades):
    return json.dumps(dades, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _contextos(cfg, xml, variant):
    if variant in ("agrupacio", "agrupacio_sense_nom", "superposades", "combinacions"):
        cfg.restriccions = {
            "restriccions_dures": {"mateix_slot": [{"nom": "Grup", "assignatures": ["A", "B"], "pes": 10}]}
        }
        dures = cfg.restriccions["restriccions_dures"]
        if variant == "agrupacio_sense_nom":
            dures["mateix_slot"][0]["nom"] = ""
        if variant == "superposades":
            dures["mateix_slot"].append({"assignatures": ["B", "C"]})
        if variant == "combinacions":
            dures["combinacions_permeses"] = [["A", "C"]]
    elif variant == "durada":
        cfg.durades_examen_per_sessio = {"A (N1)": 3}
    elif variant == "examen_mes_curt":
        cfg.durades_per_sessio = {"A (N1)": 3}
        cfg.durades_examen_per_sessio = {"A (N1)": 1}
    elif variant == "vigilancia":
        cfg.durades_per_sessio = {"A (N1)": 3}
    elif variant == "nivell_dos":
        cfg.alliberaments = {"N1": {"durada": 2}}
    elif variant == "limit":
        cfg.restriccions = {
            "restriccions_dures": {
                "professors_limit_dies_especifics": {
                    "Prof 01": {
                        "max_examens": 0,
                        "pes_penalitzacio": 60,
                        "dies_restringits": ["Dilluns"],
                        "assignatures": ["A", "B"],
                    }
                }
            }
        }
    elif variant == "estricte":
        cfg.restriccions = {"restriccions_dures": {"professors_horari_estricte": ["Prof 01"]}}
    elif variant == "pin_zero":
        cfg.restriccions = {"restriccions_dures": {"assignatures_hora_fix": {"A": "fora", "_pes_A": 0}}}
    elif variant == "sense_sessions":
        cfg.config["assignatures"] = {}
    problema = problema_de(cfg, xml)
    if variant == "hores_crues":
        problema = replace(problema, graella=("9:00", "PATI", "11:00"))
    elif variant == "classe_aliena":
        horaris = {
            "Prof 01": {
                "dilluns": {
                    "09:00": {"assignatura": "Activitat | text; final", "grup": "ALTRE"},
                    "PATI": {},
                    "11:00": {"assignatura": "Guàrdia", "grup": ""},
                }
            }
        }
        problema = replace(problema, horaris_professors=congela(horaris))
    problema = replace(problema, mapa_dies=congela({"dilluns": ["2027-03-01", "2027-03-08"]}))
    return TextosAnalisi(problema)


@pytest.mark.parametrize(
    "variant",
    [
        "base",
        "agrupacio",
        "agrupacio_sense_nom",
        "superposades",
        "combinacions",
        "durada",
        "vigilancia",
        "examen_mes_curt",
        "nivell_dos",
        "limit",
        "estricte",
        "pin_zero",
        "sense_sessions",
        "hores_crues",
        "classe_aliena",
    ],
)
@pytest.mark.parametrize("dies", [["Dilluns"], ["2027-03-01", "2027-03-08"], ["Dilluns", "Dimarts"]])
def test_els_tres_informes_no_modifiquen_la_matriu(config_inventada, xml_inventat, variant, dies):
    """Els informes no toquen la matriu que reben."""
    nou = _contextos(config_inventada, xml_inventat, variant)
    obtinguda = nou.matriu(dies)
    originals = deepcopy(obtinguda)
    assert nou.informe_per_slots(obtinguda, dies)
    assert isinstance(nou.informe_per_sessio(obtinguda, dies), list)

    def abrevia(grup):
        return grup.replace("N1", "N")

    assert isinstance(nou.informe_professors_per_slot(dies, aplicar_abreviatura_grup=abrevia), list)
    assert obtinguda == originals


def test_examen_llarg_s_analitza_sencer_i_el_nom_sense_grup_es_literal(config_inventada, xml_inventat):
    nou = _contextos(config_inventada, xml_inventat, "durada")
    sessions = {s["titol"]: s for s in nou.informes(["Dilluns"], lambda grup: grup)["per_sessio"]}
    assert {f["hora"] for f in sessions["A (N1)"]["files"]} >= {"09:00", "PATI", "11:00"}
    nou = _contextos(config_inventada, xml_inventat, "agrupacio_sense_nom")
    assert "grup_0 (2 assig)" in {s["titol"] for s in nou.informes(["Dilluns"], lambda grup: grup)["per_sessio"]}


def test_els_tres_informes_son_dades_per_a_la_pantalla(config_inventada, xml_inventat):
    """La pantalla els dibuixa sense interpretar cap text."""
    nou = _contextos(config_inventada, xml_inventat, "base")
    dies = ["2027-03-01", "2027-03-08"]
    informes = nou.informes(dies, lambda grup: grup)
    assert all(informes[clau] for clau in ("per_slots", "per_sessio", "professors_slot"))
    sessio = informes["per_sessio"][0]
    assert (sessio["titol"], sessio["professors"]) == ("A (N1)", ["Prof 01"])
    fila = sessio["files"][0]
    assert fila["dia"] in dies and isinstance(fila["cost"], (int, float))
    assert all(set(d) == {"tipus", "noms"} for d in fila["detalls"])
    assert [d["dia"] for d in informes["per_slots"]] == dies and informes["per_slots"][0]["slots"]
    hora = informes["professors_slot"][0]["hores"][0]
    assert hora["alliberats"] and set(hora["alliberats"][0]) == {"professor", "assignatura", "grup"}
    json.dumps(informes)  # es pot enviar tal qual


@pytest.mark.parametrize(
    "variant",
    [
        "base",
        "dates_peticio_ignorades",
        "sense_alliberaments",
        "sense_dates_desades",
        "dues_setmanes",
        "durada",
        "nivell_inexistent",
        "sense_sessions",
    ],
)
def test_api_analisi_nova_conserva_textos_dates_i_context(monkeypatch, variant):
    from suport_planificador import DATES, DIES, alliberaments, centre_amb_examens, configura

    from planificador import analisi_nova

    _, client = centre_amb_examens()
    camps = {}
    peticio = {"data_inici": DATES[0], "dies_utilitzar": DIES, "selected_dates": DATES}
    if variant == "sense_alliberaments":
        camps["alliberaments_per_nivell"] = {}
    elif variant == "sense_dates_desades":
        # La configuració exigeix dates ISO: sense alliberaments ni dates desades.
        camps["alliberaments_per_nivell"] = {}
    elif variant == "dues_setmanes":
        camps["alliberaments_per_nivell"] = alliberaments(dates=[DATES[0], "2026-04-27"])
    elif variant == "durada":
        camps["durades_grups"] = [{"assignatures": ["Filosofia (1-BAT)"], "durada": 2, "durada_examen": 3}]
    elif variant == "dates_peticio_ignorades":
        peticio["selected_dates"] = ["2026-04-29"]
    elif variant in ("nivell_inexistent", "sense_sessions"):
        peticio["nivells_actius"] = ["inexistent"] if variant == "nivell_inexistent" else []
        if variant == "sense_sessions":
            peticio["nivells_actius"] = ["2-BAT"]
    configura(client, **camps)
    if variant == "sense_alliberaments":
        client.put("/api/scheduler/dates", json={"selected_dates": DATES})
    problemes, contextos, opcions = [], [], []
    prepara_original = analisi_nova.prepara_planificacio
    construeix_original = analisi_nova.construeix_problema
    textos_original = analisi_nova.TextosAnalisi

    def prepara(*args, **kwargs):
        opcions.append(kwargs)
        return prepara_original(*args, **kwargs)

    def construeix(*args, **kwargs):
        problema = construeix_original(*args, **kwargs)
        problemes.append(problema)
        return problema

    def textos(problema):
        contextos.append(problema)
        return textos_original(problema)

    monkeypatch.setattr(analisi_nova, "prepara_planificacio", prepara)
    monkeypatch.setattr(analisi_nova, "construeix_problema", construeix)
    monkeypatch.setattr(analisi_nova, "TextosAnalisi", textos)
    obtingut = client.post("/api/scheduler/analisi", json=peticio)
    assert obtingut.status_code == 200, obtingut.text
    assert set(obtingut.json()) >= {"per_slots", "per_sessio", "professors_slot", "avisos"}
    assert opcions == [{"dates_de_la_peticio": False}]
    assert len(problemes) == len(contextos) == 1
    assert contextos[0] is problemes[0]
