"""Cost, textos, extres i errors del recàlcul amb dades inventades."""

from copy import deepcopy
from dataclasses import replace
from datetime import date
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from suport_incidencies import punts
from suport_motor import config_inventada as config_inventada
from suport_motor import problema_inventat
from suport_motor import xml_inventat as xml_inventat

from errors_domini import NoValid
from horari.domain import Dia
from planificador import recalcul_frontera
from planificador.compartit.franja import franja
from planificador.config import ConfigMotor
from planificador.motor import recalcul
from planificador.motor.avaluador import causa_dura, cost, cost_sessio
from planificador.motor.compatibilitat import BACKTRACKING, GREEDY, RECUIT
from planificador.motor.disponibilitat import Disponibilitat
from planificador.motor.model import HorariEditable, congela
from planificador.motor.regles import construeix_regles
from planificador.motor.sortida import finalitza_recalcul
from planificador.schemas import HorariRecalcularRequest

DATA = "2027-03-01"


def _sessio(nom="A", **extres):
    return {
        "id": f"{nom}_N1",
        "nom": f"{nom} (N1)",
        "nom_base": nom,
        "curs": "N1",
        "examens": [{"titular": "Prof 01", "grup": "N1-A", "aula": ""}],
        **extres,
    }


def _horari(sessions=None, hora="09:00"):
    return {
        "dies": [
            {
                "dia": "Dilluns",
                "data": DATA,
                "sessions": [{"hora": hora, "sessions_simultanees": sessions if sessions is not None else [_sessio()]}],
            }
        ],
        "metadata": {"logs": ["antic"], "camp_extra": [True, 1, 1.0, None]},
        "extra": {"nul": None},
    }


def _prepara(monkeypatch, cfg, xml):
    desats = []
    monkeypatch.setattr(recalcul, "carrega_config", lambda _: ConfigMotor(deepcopy(cfg)))
    monkeypatch.setattr(recalcul, "xml_del_dia", lambda _: xml)
    monkeypatch.setattr(recalcul, "desa_ultim_resultat", lambda _, document: desats.append(deepcopy(document)))
    return desats


@pytest.mark.parametrize("forma", ["completa", "sense_dates"])
@pytest.mark.parametrize(
    "variant",
    [
        "base",
        "duplicada",
        "encavalcada",
        "sense_identificadors",
        "uid",
        "separada",
        "dia_sense_data",
        "franja_buida",
        "hora_fora",
        "sense_zero",
        "preferencies",
        "pin_zero",
        "estricte",
        "negatius",
        "limit",
    ],
)
def test_recalcul_desa_un_document_i_no_modifica_la_peticio(
    monkeypatch, config_inventada, xml_inventat, forma, variant
):
    cfg = config_inventada
    cfg.alliberaments = {
        "N1": {
            "dates": [DATA],
            "config": {
                DATA: {
                    "09:00": {"i": True, "a": False},
                    "PATI": {"i": True, "a": False},
                    "11:00": {"i": True, "a": False},
                }
            },
        }
    }
    document = _horari()
    sessions = document["dies"][0]["sessions"][0]["sessions_simultanees"]
    if variant == "duplicada":
        sessions.append(deepcopy(sessions[0]))
    elif variant == "encavalcada":
        cfg.durades_per_sessio = {"A (N1)": 2, "B (N1)": 2}
        document["dies"][0]["sessions"].append({"hora": "PATI", "sessions_simultanees": [_sessio("B")]})
    elif variant == "sense_identificadors":
        sessions[0].pop("id")
        sessions.append({"nom": "B (N1)", "curs": "N1", "examens": []})
    elif variant == "uid":
        sessions[0].update(item_id="comu", _uid="primera")
        sessions.append(_sessio("B", item_id="comu", _uid="segona"))
    elif variant == "separada":
        cfg.restriccions = {"restriccions_dures": {"mateix_slot": [{"assignatures": ["A", "B"]}]}}
        document["dies"][0]["sessions"].append({"hora": "11:00", "sessions_simultanees": [_sessio("B")]})
    elif variant == "dia_sense_data":
        document["dies"][0].pop("data")
    elif variant == "franja_buida":
        sessions.clear()
    elif variant == "hora_fora":
        document["dies"][0]["sessions"][0]["hora"] = "15:15"
    elif variant == "sense_zero":
        document["dies"][0]["sessions"][0]["hora"] = "9:00"
    elif variant == "preferencies":
        sessions.append(_sessio("B"))
        cfg.restriccions = {
            "preferencies": {"mateix_dia": [{"assignatures": ["A", "B (N1)"], "pes": 75}]},
            "pesos_optimitzacio": {"preferencia_mateix_dia": 100},
        }
    elif variant == "pin_zero":
        cfg.restriccions = {"restriccions_dures": {"assignatures_hora_fix": {"A": "11:00", "_pes_A": 0}}}
    elif variant == "estricte":
        cfg.restriccions = {"restriccions_dures": {"professors_horari_estricte": ["Prof 01"]}}
        document["dies"][0]["sessions"][0]["hora"] = "11:00"
    elif variant == "negatius":
        cfg.restriccions = {"costos_professors": {"globals": {"substitucio": -17}}}
    elif variant == "limit":
        sessions.append(deepcopy(sessions[0]))
        cfg.restriccions = {
            "restriccions_dures": {
                "professors_limit_dies_especifics": {
                    "Prof 01": {
                        "assignatures": ["A"],
                        "dies_restringits": ["Dilluns"],
                        "max_examens": 1,
                        "pes_penalitzacio": 50,
                    }
                }
            }
        }
    desats = _prepara(monkeypatch, cfg, xml_inventat)
    dades = {"horari": document}
    if forma == "completa":
        dades.update(data_referencia=DATA, selected_dates=[DATA])
    payload = HorariRecalcularRequest.model_validate(dades)
    abans = payload.model_dump()
    dia = Dia(date.fromisoformat(DATA), "inventat")
    resposta = recalcul_frontera.recalcula(payload, "inventat", dia)
    assert resposta["cost_total"] == desats[0]["metadata"]["cost_total"]
    assert len(desats) == 1
    assert payload.model_dump() == abans


@pytest.mark.parametrize(
    "error,tipus,text",
    [
        ("sense_dies", NoValid, "L'horari no conté dies"),
        ("metadades_nulles", AttributeError, "'NoneType' object has no attribute 'get'"),
    ],
)
def test_els_errors_del_recalcul_no_desen_cap_resultat(monkeypatch, config_inventada, xml_inventat, error, tipus, text):
    """L'error (tipus i text) és el que donava el recàlcul antic (fixat abans de
    retirar-lo); cap error no desa res."""
    document = _horari()
    dades = {"horari": document}
    if error == "sense_dies":
        document["dies"] = []
    else:
        document["metadata"] = None
    desats = _prepara(monkeypatch, config_inventada, xml_inventat)
    payload = HorariRecalcularRequest.model_validate(dades)
    with pytest.raises(Exception) as captura:
        recalcul_frontera.recalcula(payload, "inventat", Dia(date.fromisoformat(DATA), "inventat"))
    assert (type(captura.value), str(captura.value)) == (tipus, text)
    assert desats == []


def test_referencia_sense_zeros_es_normalitza_en_entrar():
    """Abans `data_referencia` «2027-3-1» passava l'esquema i petava al recàlcul (500)."""
    payload = HorariRecalcularRequest.model_validate({"horari": _horari(), "data_referencia": "2027-3-1"})
    assert payload.data_referencia == date(2027, 3, 1)


def test_oracle_petit_cost_espera_pati_deduplicacio_i_registre(config_inventada, xml_inventat):
    """Oracle manual: dues hores d'espera de 30 punts; dos exàmens, una franja."""
    problema = problema_inventat(config_inventada, xml_inventat)
    problema = replace(
        problema,
        horaris_professors=congela({"Prof 01": {"dilluns": {"11:00": {"assignatura": "Activitat", "grup": "N1-A"}}}}),
    )
    editable = HorariEditable(_horari([_sessio(), _sessio("B")]))
    disponible = Disponibilitat(problema)
    resultat = cost(editable, problema, disponible)
    # Graella: 09:00, PATI, 11:00. Ha d'esperar 09:00 i PATI, un sol cop.
    assert resultat.total == 60.0
    assert resultat.recomptes["professors_abans"] == 2
    desat, resposta = finalitza_recalcul(editable, problema, resultat, disponible, lambda: [])
    assert punts(resposta["logs"]) == 60
    assert desat["metadata"]["cost_total"] == 60.0
    assert resposta["valid"] is False  # el conflicte de nivell no suma cost
    assert resposta["cost_desglossament"] == [{"concepte": "abans_jornada", "quantitat": 2, "pes": 30, "punts": 60}]
    abans = {"professor": "Prof 01", "examens": [], "dia": "Dilluns", "data": DATA, "primera": "11:00"}
    assert resposta["slots"][0]["avisos"] == [
        {"codi": "inc_mateix_nivell", "params": {}},
        {"codi": "inc_abans", "params": {**abans, "hora": "09:00"}, "punts": 30},
        {"codi": "inc_abans", "params": {**abans, "hora": "PATI"}, "punts": 30},
    ]


def test_l_horari_estricte_es_obligatori_a_tots_els_motors():
    """Sense tall numèric; l'horari estricte és una regla obligatòria."""
    sessio = _sessio()
    franja_prova = franja(f"{DATA}_09:00")
    regles = construeix_regles(
        {
            "restriccions_dures": {"assignatures_hora_fix": {"A": "11:00"}},
            "pesos_optimitzacio": {"restriccio_dura_violada": 5},
        }
    )
    assert (
        causa_dura(
            sessio,
            franja_prova,
            regles,
        ).clau
        == "examen_fixat"
    )
    regles = construeix_regles(
        {
            "restriccions_dures": {"professors_horari_estricte": ["Prof 01"]},
            "pesos_optimitzacio": {"restriccio_dura_violada": 5},
        }
    )
    analisi = {"abans_jornada": [{"professor": "Prof 01"}]}
    for politiques in (BACKTRACKING, GREEDY, RECUIT):
        assert causa_dura(sessio, franja_prova, regles, analisi=analisi, politiques=politiques).clau == (
            "professors_estrictes"
        )
    assert cost_sessio(sessio, "Dilluns", "09:00", analisi, regles.a_diccionari())["cost_total"] == 5


def test_un_camp_extra_no_canvia_el_servei_de_l_api(monkeypatch):
    from planificador import router

    crides = []
    monkeypatch.setattr(recalcul, "recalcula", lambda *_: crides.append("nou") or {})
    payload = HorariRecalcularRequest.model_validate({"horari": _horari(), "selector_intern": 1})
    router.recalcular_cost(payload, SimpleNamespace(institucio="inventat"), Dia(date.fromisoformat(DATA), "inventat"))
    router.recalcular_cost(payload, SimpleNamespace(institucio="inventat"), Dia(date.fromisoformat(DATA), "inventat"))
    assert crides == ["nou", "nou"]


def test_cost_de_consulta_conserva_document_i_identitats(config_inventada, xml_inventat):
    problema = problema_inventat(config_inventada, xml_inventat)
    sessio = _sessio(analisi={"extra": {"valors": [True, 1, None]}})
    document = _horari([sessio, sessio, deepcopy(sessio)])
    original = deepcopy(document)
    disponible = Disponibilitat(problema)
    esperat = cost(HorariEditable(document), problema).a_info()
    assert cost(document, problema, disponible).a_info() == esperat
    assert cost(document, problema, disponible).a_info() == esperat
    assert document == original
    sessions = document["dies"][0]["sessions"][0]["sessions_simultanees"]
    assert sessions[0] is sessions[1]
    assert sessions[0] is not sessions[2]


@pytest.mark.parametrize("titular", [["Prof 01"], {"nom": "Prof 01"}, 7])
def test_un_titular_que_no_es_text_no_passa_la_validacio(titular):
    """El titular d'un examen és text o res; abans una llista passava i
    petava al recàlcul (500)."""
    document = _horari()
    document["dies"][0]["sessions"][0]["sessions_simultanees"][0]["examens"][0]["titular"] = titular
    with pytest.raises(ValidationError):
        HorariRecalcularRequest.model_validate({"horari": document})


def test_el_titular_arriba_net():
    document = _horari()
    examen = document["dies"][0]["sessions"][0]["sessions_simultanees"][0]["examens"][0]
    examen["titular"] = "  Prof 01 "
    model = HorariRecalcularRequest.model_validate({"horari": document})
    dumped = model.horari.model_dump(exclude_unset=True)
    assert dumped["dies"][0]["sessions"][0]["sessions_simultanees"][0]["examens"][0]["titular"] == "Prof 01"
