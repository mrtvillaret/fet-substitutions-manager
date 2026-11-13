"""Caracterització d'`analitzar_disponibilitat_sessio`: fixa què retorna avui
per a cada situació d'un professor titular
—fora de l'XML, dia absent o buit, alumnes alliberats, «No substituir», classe
real, zona d'examen, abans i després de la jornada— abans de partir la funció.
No diu que el comportament sigui el desitjat.

Horaris inventats: cinc hores de classe i el pati.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scheduler_engine.core.availability import analitzar_disponibilitat_sessio
from scheduler_engine.core.nivells import NivellsDelsGrups

INSTANTANIA = Path(__file__).parent / "caracteritzacio" / "disponibilitat.json"
HORES = ["08:00", "09:00", "10:00", "11:00", "11:30", "12:30"]  # 11:00 és el pati
NIVELLS = ["1-ESO", "2-ESO"]
# Les taules de la configuració d'exàmens (el nivell d'un grup surt d'aquí)
TAULES = NivellsDelsGrups({"1-ESO": ["1-ESO-A"], "2-ESO": ["2-ESO-A"], "3-ESO": ["3-ESO-A", "3-ESO-B"]})
DATA = "2026-04-20"


def classe(grup, assignatura="Mates"):
    return {"grup": grup, "assignatura": assignatura}


HORARIS = {
    # Classe amb el nivell de l'examen a les 9 i amb un altre nivell a les 10
    "Anna": {"dilluns": {"09:00": classe("1-ESO-A"), "10:00": classe("3-ESO-B")}, "dimarts": {}},
    # Guàrdia (sense grup) a les 9 i una assignatura de «No substituir» a les 10
    "Bernat": {"dilluns": {"09:00": classe("", "Guàrdia"), "10:00": classe("3-ESO-A", "Tutoria")}},
    # Jornada de 10 a 11:30: abans, enmig (el pati) i després
    "Carme": {"dilluns": {"10:00": classe("3-ESO-A"), "11:30": classe("3-ESO-B")}},
    # Dia a l'XML amb les franges buides
    "Dídac": {"dilluns": {}},
    # Hores sense zero al davant i una hora que no és a la graella
    "Empar": {"dilluns": {"9:00": classe("2-ESO-A"), "17:00": classe("3-ESO-A")}},
}


def examen(titular, **camps):
    return {"titular": titular, "grup": "1-ESO-A", **camps}


def sessio(*titulars, nom="Mates 1"):
    return {"nom": nom, "curs": "1-ESO", "examens": [examen(t) for t in titulars]}


def analitza(titulars, hora="09:00", dia="Dilluns", **params):
    if isinstance(titulars, str):
        titulars = [titulars]
    arguments = {
        "sessio": sessio(*titulars),
        "dia": dia,
        "hora": hora,
        "horaris_professors": HORARIS,
        "totes_hores": HORES,
        "nivells_actius": NIVELLS,
        "no_substituir_norm": {"tutoria"},
        "data_iso": DATA,
        "nivells_dels_grups": TAULES,
    }
    arguments.update(params)
    return analitzar_disponibilitat_sessio(**arguments)


def resum(analisi):
    """Les categories no buides: [(professor, hora o None)]."""
    return {
        categoria: [(d["professor"], d.get("hora")) for d in detalls]
        for categoria, detalls in analisi.items()
        if detalls
    }


def test_categories_del_resultat():
    analisi = analitza([])
    assert analisi == {
        "lliures": [],
        "alliberats": [],
        "abans_jornada": [],
        "despres_jornada": [],
        "no_treballa_dia": [],
        "substitucions": [],
        "altres": [],
        "zona_examen": [],
        "classe_1-ESO": [],
        "classe_2-ESO": [],
    }


def test_hora_fora_de_la_graella_no_analitza_res():
    assert resum(analitza("Anna", hora="17:00")) == {}


def test_examen_sense_titular_no_compta():
    analisi = analitza([None, ""])
    assert resum(analisi) == {}


def test_professor_fora_de_l_xml_es_lliure():
    analisi = analitza("Ningú")
    assert analisi["lliures"] == [{"professor": "Ningú", "examen": examen("Ningú")}]
    assert resum(analisi) == {"lliures": [("Ningú", None)]}


@pytest.mark.parametrize("professor, dia", [("Bernat", "Dimarts"), ("Anna", "Dimarts"), ("Dídac", "Dilluns")])
def test_dia_absent_o_buit_no_treballa(professor, dia):
    """Tant si el dia no surt a l'XML com si hi surt buit: una entrada per
    cada hora de supervisió."""
    analisi = analitza(professor, dia=dia, durada_titular=2)
    assert analisi["no_treballa_dia"] == [
        {"professor": professor, "examen": examen(professor), "dia": dia.lower(), "hora": hora}
        for hora in ("09:00", "10:00")
    ]
    assert resum(analisi) == {"no_treballa_dia": [(professor, "09:00"), (professor, "10:00")]}


def test_classe_amb_el_nivell_alliberat():
    """Sense alliberaments definits, tots els nivells actius es donen per
    alliberats: la classe amb 1-ESO no cal cobrir-la."""
    analisi = analitza("Anna")
    assert resum(analisi) == {"alliberats": [("Anna", None)]}
    assert analisi["alliberats"] == [{"professor": "Anna", "examen": examen("Anna")}]


def alliberaments(alliberat, hora="09:00", data=DATA):
    return {"1-ESO": {"config": {data: {hora: {"a": alliberat}}}}}


def test_alliberaments_per_data_i_hora():
    assert resum(analitza("Anna", alliberaments_per_nivell=alliberaments(True))) == {"alliberats": [("Anna", None)]}
    # No alliberat, una altra data, una altra hora, nivell sense dades o sense data: cal substituir-la
    substitucio = {"substitucions": [("Anna", "09:00")], "classe_1-ESO": [("Anna", "09:00")]}
    assert resum(analitza("Anna", alliberaments_per_nivell=alliberaments(False))) == substitucio
    assert resum(analitza("Anna", alliberaments_per_nivell=alliberaments(True, data="2026-04-21"))) == substitucio
    assert resum(analitza("Anna", alliberaments_per_nivell=alliberaments(True, hora="10:00"))) == substitucio
    assert resum(analitza("Anna", alliberaments_per_nivell={"2-ESO": {"config": {}}})) == substitucio
    assert resum(analitza("Anna", alliberaments_per_nivell=alliberaments(True), data_iso=None)) == substitucio
    # L'hora de la configuració es busca amb el zero al davant
    assert resum(analitza("Empar", alliberaments_per_nivell={"2-ESO": {"config": {DATA: {"09:00": {"a": True}}}}})) == {
        "alliberats": [("Empar", None)]
    }


def test_classe_real_cal_substituir_la():
    analisi = analitza("Anna", hora="10:00")
    detall = {"professor": "Anna", "examen": examen("Anna"), "activitat": classe("3-ESO-B"), "hora": "10:00"}
    # 3-ESO no és un nivell actiu: el detall va a «altres» i a «substitucions»
    assert analisi["substitucions"] == [detall]
    assert analisi["altres"] == [detall]
    assert resum(analisi) == {"substitucions": [("Anna", "10:00")], "altres": [("Anna", "10:00")]}


def test_classe_real_d_un_nivell_actiu_va_a_la_seva_clau():
    analisi = analitza("Empar", alliberaments_per_nivell={"1-ESO": {"config": {}}})
    assert resum(analisi) == {"substitucions": [("Empar", "09:00")], "classe_2-ESO": [("Empar", "09:00")]}
    assert analisi["classe_2-ESO"][0]["activitat"] == classe("2-ESO-A")


def test_sense_grup_o_no_substituir_va_a_altres():
    analisi = analitza("Bernat", durada_titular=2)
    assert resum(analisi) == {"altres": [("Bernat", "09:00"), ("Bernat", "10:00")]}
    assert analisi["altres"][0]["activitat"] == classe("", "Guàrdia")
    # Sense la llista de «No substituir», la tutoria és una classe real
    assert resum(analitza("Bernat", hora="10:00", no_substituir_norm=None)) == {
        "substitucions": [("Bernat", "10:00")],
        "altres": [("Bernat", "10:00")],
    }


def test_titular_d_una_altra_sessio_de_la_franja_queda_alliberat():
    """Qui només té activitats que no es cobreixen i és titular d'una altra
    sessió de la mateixa franja surt també a «alliberats»."""
    altra = {"nom": "Física 3", "examens": [examen("Bernat")]}
    mateixa = {"nom": "Mates 1", "examens": [examen("Bernat")]}
    esperat = {"altres": [("Bernat", "09:00")], "alliberats": [("Bernat", None)]}
    assert resum(analitza("Bernat", sessions_al_slot=[altra])) == esperat
    assert resum(analitza("Bernat", sessions_al_slot=[{"sessio": altra}])) == esperat
    objecte = SimpleNamespace(nom="Física 3", examens=[SimpleNamespace(titular="Bernat")])
    assert resum(analitza("Bernat", sessions_al_slot=[objecte])) == esperat
    # Una sessió amb el mateix nom no compta
    assert resum(analitza("Bernat", sessions_al_slot=[mateixa])) == {"altres": [("Bernat", "09:00")]}
    # Amb una classe real, no
    assert "alliberats" not in resum(
        analitza("Anna", hora="10:00", sessions_al_slot=[altra | {"examens": [examen("Anna")]}])
    )


def test_abans_de_la_jornada_compta_cada_hora_d_espera():
    analisi = analitza("Carme", hora="08:00")
    assert analisi["abans_jornada"] == [
        {"professor": "Carme", "examen": examen("Carme"), "primera_hora": "10:00", "hora": hora}
        for hora in ("08:00", "09:00")
    ]
    assert resum(analisi) == {"abans_jornada": [("Carme", "08:00"), ("Carme", "09:00")]}
    # Dues hores de supervisió: cada hora d'espera, una sola vegada
    assert resum(analitza("Carme", hora="08:00", durada_titular=2)) == resum(analisi)


def test_despres_de_la_jornada_compta_cada_hora_d_espera():
    analisi = analitza("Anna", hora="12:30")
    assert analisi["despres_jornada"] == [
        {"professor": "Anna", "examen": examen("Anna"), "ultima_hora": "10:00", "hora": hora}
        for hora in ("11:00", "11:30", "12:30")
    ]
    assert resum(analisi) == {"despres_jornada": [("Anna", "11:00"), ("Anna", "11:30"), ("Anna", "12:30")]}


def test_hora_lliure_dins_de_la_jornada_es_lliure():
    analisi = analitza("Carme", hora="11:00")
    assert resum(analisi) == {"lliures": [("Carme", None)]}


def test_hora_lliure_i_classe_a_la_mateixa_supervisio():
    """Pati lliure i classe a les 11:30: només compta la classe."""
    assert resum(analitza("Carme", hora="11:00", durada_titular=2)) == {
        "substitucions": [("Carme", "11:30")],
        "altres": [("Carme", "11:30")],
    }


def test_zona_d_examen_fora_de_la_supervisio():
    """L'examen dura més que la supervisió del titular: les classes de la
    resta d'hores són informatives («zona_examen»), no substitucions."""
    params = {"hores_override": ["09:00", "10:00"], "hores_supervisio": ["09:00"]}
    analisi = analitza("Anna", alliberaments_per_nivell=alliberaments(True), **params)
    assert resum(analisi) == {"alliberats": [("Anna", None)], "zona_examen": [("Anna", "10:00")]}
    assert analisi["zona_examen"] == [
        {"professor": "Anna", "examen": examen("Anna"), "activitat": classe("3-ESO-B"), "hora": "10:00"}
    ]
    # A la zona d'examen no surten ni les activitats que no es cobreixen ni les de nivells alliberats
    assert resum(analitza("Bernat", **params)) == {"altres": [("Bernat", "09:00")]}
    girat = {"hores_override": ["08:00", "09:00"], "hores_supervisio": ["08:00"]}
    assert resum(analitza("Anna", hora="08:00", **girat)) == {"abans_jornada": [("Anna", "08:00")]}
    # Una hora lliure a la zona d'examen no compta com a espera
    assert resum(analitza("Carme", hora="11:30", hores_override=["11:30", "12:30"], hores_supervisio=["11:30"])) == {
        "substitucions": [("Carme", "11:30")],
        "altres": [("Carme", "11:30")],
    }


def test_hores_override_amb_una_hora_fora_de_la_graella():
    """Una hora lliure que no és a la graella no posa el professor enlloc; si
    hi té classe, sí que compta."""
    assert resum(analitza("Anna", hores_override=["17:00"])) == {}
    assert resum(analitza("Empar", hores_override=["17:00"])) == {
        "substitucions": [("Empar", "17:00")],
        "altres": [("Empar", "17:00")],
    }


def test_professor_amb_activitats_nomes_fora_de_la_graella():
    """Sense cap hora de la graella no té jornada: l'hora és «lliure»."""
    horaris = {"Fina": {"dilluns": {"17:00": classe("3-ESO-A")}}}
    assert resum(analitza("Fina", horaris_professors=horaris)) == {"lliures": [("Fina", None)]}


def test_el_dia_es_normalitza_pero_les_claus_de_l_horari_no():
    assert resum(analitza("Anna", dia="lunes")) == resum(analitza("Anna"))
    horaris = {"Anna": {"Dilluns": HORARIS["Anna"]["dilluns"]}}
    assert resum(analitza("Anna", horaris_professors=horaris)) == {"no_treballa_dia": [("Anna", "09:00")]}


def test_sessio_i_examens_com_a_objectes():
    objecte = SimpleNamespace(nom="Mates 1", examens=[SimpleNamespace(titular="Anna")])
    analisi = analitza([], sessio=objecte)
    assert [(d["professor"], d["examen"]) for d in analisi["alliberats"]] == [("Anna", objecte.examens[0])]


def horaris_normalitzats(horaris):
    """El que passen els motors: `GeneradorBase._pre_normalitzar_horaris`."""
    from scheduler_engine.generators.base import GeneradorSessionsExamensBase

    return GeneradorSessionsExamensBase._pre_normalitzar_horaris(SimpleNamespace(horaris_professors=horaris))


CASOS = {
    f"{professor}|{dia}|{hora}|{durada}|{variant}": (professor, dia, hora, durada, variant)
    for professor in [*HORARIS, "Ningú"]
    for dia in ("Dilluns", "Dimarts")
    for hora in HORES
    for durada in (1, 2)
    for variant in ("sense_alliberaments", "alliberat", "zona_examen")
    if dia == "Dilluns" or (hora == "09:00" and variant != "alliberat")  # dimarts gairebé ningú no treballa
}


def _cas(professor, dia, hora, durada, variant, **mes):
    params = {"durada_titular": durada}
    if variant != "sense_alliberaments":
        params["alliberaments_per_nivell"] = alliberaments(True)
    if variant == "zona_examen":
        idx = HORES.index(hora)
        params["hores_override"] = HORES[idx : idx + durada + 1]
        params["hores_supervisio"] = HORES[idx : idx + durada]
    altra = {"nom": "Física 3", "examens": [examen("Bernat"), examen("Carme")]}
    return analitza([professor, "Carme"], hora=hora, dia=dia, sessions_al_slot=[altra], **params, **mes)


def _compacta(analisi):
    """Les categories no buides, amb tot el que hi ha a cada detall:
    [professor, hora, primera o última hora o dia, grup de l'activitat]."""
    compacte = {}
    for categoria, detalls in analisi.items():
        for d in detalls:
            assert d["examen"] == examen(d["professor"])
            assert set(d) <= {"professor", "examen", "hora", "primera_hora", "ultima_hora", "dia", "activitat"}
            extra = d.get("primera_hora") or d.get("ultima_hora") or d.get("dia")
            compacte.setdefault(categoria, []).append(
                [d["professor"], d.get("hora"), extra, (d.get("activitat") or {}).get("grup")]
            )
    return compacte


def calcula_instantania():
    """Per tornar a desar INSTANTANIA si mai canvia el comportament a propòsit."""
    return {clau: _compacta(_cas(*cas)) for clau, cas in CASOS.items()}


def test_instantania_de_tots_els_casos():
    """Cada professor (amb una companya) a cada hora de dos dies, amb durada
    1 i 2 i tres variants: igual que abans de partir la funció."""
    esperat = json.loads(INSTANTANIA.read_text(encoding="utf-8"))
    assert set(esperat) == set(CASOS)
    for clau, cas in CASOS.items():
        assert _compacta(_cas(*cas)) == esperat[clau], clau


def test_amb_l_horari_normalitzat_dona_el_mateix():
    """`horaris_professors_norm` (el que passen els motors) no canvia res."""
    norm = horaris_normalitzats(HORARIS)
    for clau, cas in CASOS.items():
        assert _cas(*cas, horaris_professors_norm=norm) == _cas(*cas), clau


def test_els_dos_camins_normalitzen_les_hores_igual():
    """Amb dues hores que es normalitzen igual («8:00» i
    «08:00») guanya la primera, i una hora de nom buit no hi és, tant si
    l'anàlisi rep l'horari sense normalitzar com si el rep normalitzat."""
    horaris = {"Gina": {"dilluns": {"8:00": classe("3-ESO-A"), "08:00": classe("2-ESO-A"), "": classe("3-ESO-B")}}}
    norm = horaris_normalitzats(horaris)
    assert norm["Gina"]["dilluns"] == {"08:00": classe("3-ESO-A")}
    for hora in HORES:
        lent = analitza("Gina", hora=hora, horaris_professors=horaris)
        rapid = analitza("Gina", hora=hora, horaris_professors=horaris, horaris_professors_norm=norm)
        assert lent == rapid, hora


def test_amb_l_xml_d_exemple_els_dos_camins_donen_el_mateix_horari():
    import xml.etree.ElementTree as ET

    from suport_api import XML_EXEMPLE

    from scheduler_engine.core.availability import horari_del_dia_normalitzat
    from scheduler_engine.core.horaris_xml import horaris_professors

    horaris = horaris_professors(ET.parse(XML_EXEMPLE).getroot())
    norm = horaris_normalitzats(horaris)
    for prof, dies in horaris.items():
        for dia, hores in dies.items():
            assert norm[prof][dia] == horari_del_dia_normalitzat(hores)
