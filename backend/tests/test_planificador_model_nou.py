"""Compatibilitat del model nou amb dades inventades i sense rellotge real."""

import xml.etree.ElementTree as ET
from copy import deepcopy
from dataclasses import FrozenInstanceError

import pytest
from suport_motor_nou import config_inventada as config_inventada
from suport_motor_nou import problema_inventat
from suport_motor_nou import xml_inventat as xml_inventat

from planificador.motor import compatibilitat as p
from planificador.motor.construccio import (
    construeix_problema,
    graella_cost,
    graella_derivada,
    graella_motor,
    mapa_dies,
    particio_antiga,
    particio_nova,
)
from planificador.motor.disponibilitat import Disponibilitat, analitzar_disponibilitat_sessio
from planificador.motor.durades import examen_config, examen_motor, examen_recalcul, per_nivell
from planificador.motor.model import DataAmbOrigen, HorariEditable, congela
from planificador.motor.regles import (
    Agrupacio,
    Ambit,
    Fixacio,
    LimitProfessor,
    coincideix_exacte,
    coincideix_normalitzat,
    construeix_regles,
    percent_examen_fixat,
    recompte_limit_professor,
)


def test_problema_es_una_instantania_profunda(config_inventada, xml_inventat):
    problema = problema_inventat(config_inventada, xml_inventat)
    with pytest.raises(FrozenInstanceError):
        problema.graella = ()
    with pytest.raises(TypeError):
        problema.regles.originals["nova"] = True
    with pytest.raises(TypeError):
        problema.examens[0].dades["examens"][0]["grup"] = "N2-A"
    config_inventada.config["assignatures"]["A"]["assignacions"][0]["grup"] = "N2-A"
    assert problema.examens[0].dades["examens"][0]["grup"] == "N1-A"
    assert problema.examens[0].hores_examen == 1  # el recàlcul ignora la general d'examen
    assert len(problema.franges) == 2


def test_editable_conserva_ocurrencies_extres_i_absencies():
    sessio = {"nom": "A", "curs": "N1", "examens": [], "extra": {"null": None}}
    original = {
        "dies": [
            {"dia": "Dilluns", "sessions": [{"hora": "09:00", "sessions_simultanees": [sessio, deepcopy(sessio)]}]}
        ],
        "metadata": {"extra": [True, 1, 1.0]},
    }
    editable = HorariEditable(original)
    assert editable.a_diccionari() == original
    assert editable.ocurrencies[0].sessio is not editable.ocurrencies[1].sessio
    assert [o.posicio for o in editable.ocurrencies] == [(0, 0, 0), (0, 0, 1)]
    assert "id" not in editable.ocurrencies[0].sessio
    editable.ocurrencies[0].sessio["analisi"] = {}
    assert "analisi" not in original["dies"][0]["sessions"][0]["sessions_simultanees"][0]
    # Ni els identificadors públics iguals ni el contingut igual dedupliquen el límit.
    for o in editable.ocurrencies:
        o.sessio.update(nom_base="A", id="repetit", item_id="repetit", examens=[{"titular": "Prof 01"}])
    sessions = [o.sessio for o in editable.ocurrencies]
    limit = {"assignatures": ["A"], "dies_restringits": ["Dilluns"], "max_examens": 1}
    assert recompte_limit_professor("Prof 01", limit, {"Dilluns": sessions}, sessions).excedent == 1


@pytest.mark.parametrize("propia,vigilancia,esperat", [(None, None, (3, 1, 1)), (1, 2, (2, 2, 1)), (4, 2, (4, 4, 4))])
def test_tres_durades_es_conserven(propia, vigilancia, esperat):
    examens, vigilancies = {"A": propia}, {"A": vigilancia}
    assert (
        examen_config("A", examens, vigilancies, 3, 1),
        examen_recalcul("A", examens, vigilancies, 1),
        examen_motor("A", examens, vigilancies, 1),
    ) == esperat
    assert per_nivell("N1", {"N1": {"durada": 2}}, 1) == 2


def test_dates_amb_procedencia_i_franges_no_filtrades(config_inventada, xml_inventat):
    data = DataAmbOrigen.de_text("2027-3-1", "peticio")
    assert (data.original, data.normalitzada) == ("2027-3-1", "2027-03-01")
    mapa = mapa_dies(["Dilluns"], ["2027-03-01", "2027-03-02"])
    problema = construeix_problema(
        config_inventada, xml_inventat, ["N1"], ["Dilluns"], ["2027-03-01", "2027-03-02"], mapa, ["09:00"], p.GREEDY
    )
    assert mapa == {"dilluns": ["2027-03-01"]}
    assert [f.prefix for f in problema.franges] == ["2027-03-01", "2027-03-02"]


def test_tres_graelles_conserven_ordre_normalitzacio_i_reserva(tmp_path):
    fitxer = tmp_path / "graella.xml"
    fitxer.write_text('<Horari><Day><Hour name="11:00"/><Hour name="8:00"/><Hour name="PATI"/></Day></Horari>')
    arrel = ET.parse(fitxer).getroot()
    assert graella_motor(arrel) == ["11:00", "8:00", "PATI"]
    assert graella_cost(arrel, []) == ["11:00", "08:00", "PATI"]
    assert graella_cost(arrel, ["07:00"]) == ["PATI", "07:00", "08:00", "11:00"]
    assert graella_derivada(str(fitxer), []) == ["08:00", "11:00", "PATI"]
    assert graella_cost(ET.fromstring("<Horari/>"), ["8:00", "11:00"]) == ["08:00", "11:00"]


def test_regles_conserven_pes_ambit_text_i_posicio():
    original = {
        "restriccions_dures": {
            "mateix_slot": [{"assignatures": [" a ", "B"], "pes": 0}],
            "assignatures_dia_fix": {"A": "2027-03-01", "_pes_A": 0},
            "professors_limit_dies_especifics": {"Prof 01": {"assignatures": ["A"], "pes_penalitzacio": -5}},
        }
    }
    regles = construeix_regles(original)
    assert regles.a_diccionari() == original
    assert isinstance(regles.regles_en_ordre[0], Agrupacio) and regles.regles_en_ordre[0].pes == 0
    assert regles.regles_en_ordre[0].noms == (" a ", "B")
    assert isinstance(regles.regles_en_ordre[1], Fixacio) and regles.regles_en_ordre[1].ambit == Ambit.DATA
    assert regles.regles_en_ordre[1].origen == ("restriccions_dures", "assignatures_dia_fix", "A")
    assert isinstance(regles.regles_en_ordre[2], LimitProfessor) and regles.regles_en_ordre[2].pes == -5
    assert not coincideix_exacte(" a ", {"nom": "A", "nom_base": "A"})
    assert coincideix_normalitzat(" a ", {"nom": "A", "nom_base": "A"})
    # L'error del pin de pes zero es conserva.
    assert percent_examen_fixat({"nom": "A"}, "Dimarts", "09:00", original, "2027-03-02") == 100


PARTICIO_ANTIGA = {
    "ABC": [
        ("grup_0 (2 assig)", "item_d703fd201b9b", ["A_N1", "B_N1"]),
        ("grup_1 (1 assig)", "item_b696ff57704e", ["C_N1"]),
    ],
    "BAC": [
        ("grup_1 (2 assig)", "item_6b4dbab7b514", ["B_N1", "C_N1"]),
        ("grup_0 (1 assig)", "item_4c352d49e28f", ["A_N1"]),
    ],
    "ACB": [
        ("grup_0 (2 assig)", "item_d703fd201b9b", ["A_N1", "B_N1"]),
        ("grup_1 (1 assig)", "item_b696ff57704e", ["C_N1"]),
    ],
}
PARTICIO_NOVA = {
    "ABC": [("A (G)", "item_d703fd201b9b", ["A_N1", "B_N1"]), ("C (G)", "item_b696ff57704e", ["C_N1"])],
    "BAC": [("B (G)", "item_d703fd201b9b", ["B_N1", "A_N1"]), ("C (G)", "item_b696ff57704e", ["C_N1"])],
    "ACB": [("A (G)", "item_d703fd201b9b", ["A_N1", "B_N1"]), ("C (G)", "item_b696ff57704e", ["C_N1"])],
}


@pytest.mark.parametrize("ordre,esperat", [("ABC", ["AB", "C"]), ("BAC", ["BC", "A"]), ("ACB", ["AB", "C"])])
def test_particions_superposades_amb_ordres_efectius(config_inventada, xml_inventat, ordre, esperat):
    regles = construeix_regles(
        {"restriccions_dures": {"mateix_slot": [{"assignatures": ["A", "B"], "pes": 0}, {"assignatures": ["B", "C"]}]}}
    )
    problema = problema_inventat(config_inventada, xml_inventat)
    examens = tuple(next(e for e in problema.examens if e.nom_base == nom) for nom in ordre)
    antic = particio_antiga(examens, regles)
    assert ["".join(e.nom_base for e in item.examens) for item in antic] == esperat

    # Identificadors i etiquetes de les dues particions, fixats amb les
    # primitives antigues abans de retirar-les (hashes inclosos).
    projeccio = [(it.dades["nom"], it.dades["item_id"], [x["id"] for x in it.dades["sessions"]]) for it in antic]
    assert projeccio == PARTICIO_ANTIGA[ordre]
    assert all(it.dades["examens_count"] == len(it.dades["sessions"]) for it in antic)
    nova = particio_nova(examens, regles, ["N1"])
    projeccio = [(it.dades["nom"], it.dades["item_id"], [x["id"] for x in it.dades["sessions"]]) for it in nova]
    assert projeccio == PARTICIO_NOVA[ordre]


@pytest.mark.parametrize("agrupacions", [[], [{"assignatures": ["inexistent"]}]])
def test_particio_antiga_sense_i_amb_agrupacio_aliena(config_inventada, xml_inventat, agrupacions):
    problema = problema_inventat(config_inventada, xml_inventat)
    items = particio_antiga(problema.examens, construeix_regles({"restriccions_dures": {"mateix_slot": agrupacions}}))
    assert all((it.id is not None) == bool(agrupacions) for it in items)


@pytest.mark.parametrize("hores", [["09:00"], ["PATI"], ["11:00"], ["09:00", "PATI"], ["fora"]])
@pytest.mark.parametrize("altres", [[], [{"nom": "B", "examens": [{"titular": "Prof 01"}]}]])
def test_disponibilitat_i_cache_amb_context(config_inventada, xml_inventat, hores, altres):
    problema = problema_inventat(config_inventada, xml_inventat)
    sessio = problema.examens[0].a_diccionari()
    arguments = dict(
        sessio=sessio,
        dia="Dilluns",
        hora=hores[0],
        horaris_professors={"Prof 01": {"dilluns": {"09:00": {"assignatura": "Activitat", "grup": "N1-A"}}}},
        totes_hores=["09:00", "PATI", "11:00"],
        nivells_actius=["N1"],
        sessions_al_slot=altres,
        hores_override=hores,
        hores_supervisio=hores,
        nivells_dels_grups=config_inventada.nivells_dels_grups,
    )
    disponible = Disponibilitat(problema)
    esperat = analitzar_disponibilitat_sessio(**arguments)
    assert disponible.analitza(sessio, "Dilluns", hores[0], None, hores, hores, altres) == esperat
    primera = disponible.analitza(sessio, "Dilluns", hores[0], None, hores, hores, altres)
    primera["lliures"].append({"canvi": True})
    assert disponible.analitza(sessio, "Dilluns", hores[0], None, hores, hores, altres) == esperat
    assert len(disponible._estatica) == 1


def test_cache_no_arrossega_alliberament_d_una_altra_franja(config_inventada, xml_inventat):
    problema = problema_inventat(config_inventada, xml_inventat)
    # Activitat que no allibera per nivell: només el context de titular simultani.
    horaris = {"Prof 01": {"dilluns": {"09:00": {"assignatura": "Activitat", "grup": ""}}}}
    from dataclasses import replace

    problema = replace(problema, horaris_professors=congela(horaris))
    disponible = Disponibilitat(problema)
    sessio = problema.examens[0].a_diccionari()
    altres = [{"nom": "B", "examens": [{"titular": "Prof 01"}]}]
    assert disponible.analitza(sessio, "Dilluns", "09:00", None, ["09:00"], ["09:00"], altres)["alliberats"]
    assert disponible.analitza(sessio, "Dilluns", "09:00", None, ["09:00"], ["09:00"])["alliberats"] == []


def test_combinacions_fusionen_nomes_a_la_particio_nova(config_inventada, xml_inventat):
    problema = problema_inventat(config_inventada, xml_inventat)
    regles = construeix_regles({"restriccions_dures": {"combinacions_permeses": [{"assignatures": ["a", "b"]}]}})
    nova = particio_nova(problema.examens, regles, ["N1"])
    antiga = particio_antiga(problema.examens, regles)
    assert [[e.nom_base for e in it.examens] for it in nova] == [["A", "B"], ["C"]]
    assert nova[0].nom == "A (+)"
    assert len(antiga) == 3


@pytest.mark.parametrize("grups", [[], [{"assignatures": ["inexistent"]}], [{"assignatures": ["A", "B"]}]])
def test_claus_i_etiquetes_del_recuit(config_inventada, xml_inventat, grups):
    from dataclasses import replace

    from planificador.motor.construccio import particio

    problema = problema_inventat(config_inventada, xml_inventat)
    regles = construeix_regles({"restriccions_dures": {"mateix_slot": grups}})
    items = particio(replace(problema, regles=regles), p.RECUIT)
    assert items[0].id == items[0].nom
    assert items[0].nom == ("grup_0" if grups and len(grups[0]["assignatures"]) == 2 else "A (N1)")
    for item in items:
        for e in item.examens:
            identificador = e.dades["item_id"]
            assert identificador.startswith("item_") if grups else identificador == e.nom


def test_particio_antiga_separa_nivells_amb_noms_base_iguals(config_inventada, xml_inventat):
    from dataclasses import replace

    from planificador.motor.construccio import particio

    problema = problema_inventat(config_inventada, xml_inventat)
    primer = problema.examens[0]
    segon = replace(
        primer,
        id="A_N2",
        curs="N2",
        nom="A (N2)",
        dades=congela({**primer.a_diccionari(), "id": "A_N2", "curs": "N2", "nom": "A (N2)"}),
    )
    regles = construeix_regles({"restriccions_dures": {"mateix_slot": [{"nom": "comu", "assignatures": ["A"]}]}})
    items = particio(replace(problema, examens=(primer, segon), regles=regles), p.RECUIT)
    assert len(items) == 2
    assert [item.id for item in items] == ["comu", "comu"]  # el recuit els trepitjarà: es conserva
    assert items[0].examens[0].dades["item_id"] != items[1].examens[0].dades["item_id"]


def test_resolucio_no_esborra_la_diferencia_entre_comparadors(config_inventada, xml_inventat):
    config_inventada.restriccions = {"restriccions_dures": {"mateix_slot": [{"assignatures": [" a ", "absent"]}]}}
    problema = problema_inventat(config_inventada, xml_inventat)
    regla = problema.regles.agrupacions[0]
    assert regla.resolucio_exacta == ((" a ", ()), ("absent", ()))
    assert regla.resolucio_normalitzada == ((" a ", ("A_N1",)), ("absent", ()))
    assert regla.valor["assignatures"] == (" a ", "absent")


def test_preferencies_per_data_al_cost_i_per_nom_a_la_cerca():
    original = {"preferencies": {"dies_diferents": [{"assignatures": ["A", "B"], "pes": 100}]}}
    del_cost = construeix_regles(original, politiques=p.COST_MOSTRAT).regles_en_ordre[0]
    del_recalcul = construeix_regles(original, politiques=p.RECALCUL).regles_en_ordre[0]
    de_la_cerca = construeix_regles(original, politiques=p.BACKTRACKING).regles_en_ordre[0]
    assert del_cost.ambit == del_recalcul.ambit == Ambit.DATA
    assert de_la_cerca.ambit == Ambit.NOM_DIA


def test_guardia_no_permet_dependencia_web_dins_una_peca_neutra():
    from test_dependencies_capes import _violacions

    fonts = {
        "planificador/motor/prova.py": "from planificador.compartit.nivells import NivellsDelsGrups",
        "planificador/compartit/nivells.py": "class NivellsDelsGrups: pass",
    }
    assert _violacions(fonts, excepcions={}) == []
    fonts["planificador/compartit/nivells.py"] += "\nfrom planificador.config import carrega_config"
    fonts["planificador/config.py"] = "def carrega_config(): pass"
    assert any("peça neutra depèn de l’aplicació" in error for error in _violacions(fonts, excepcions={}))


def test_analisi_editable_no_modifica_la_vista_de_consulta(config_inventada, xml_inventat):
    problema = problema_inventat(config_inventada, xml_inventat)
    disponible = Disponibilitat(problema)
    sessio = problema.examens[0].a_diccionari()
    arguments = (sessio, "Dilluns", "09:00", None, ["09:00"], ["09:00"])
    vista = disponible.consulta(*arguments)
    esperat = deepcopy(vista)
    editable = disponible.analitza(*arguments)
    assert editable == esperat
    # Protecció profunda: ni les assignacions ni les activitats de l'XML es comparteixen.
    for entrades in editable.values():
        for entrada in entrades:
            entrada["examen"]["titular"] = "Prof 99"
            if "activitat" in entrada:
                entrada["activitat"]["assignatura"] = "Canviada"
        entrades.append({"canvi": True})
    assert disponible.consulta(*arguments) == esperat
    assert disponible.analitza(*arguments) == esperat
