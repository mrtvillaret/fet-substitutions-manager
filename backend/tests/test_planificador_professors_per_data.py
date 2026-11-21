"""Cada hora d'un professor (substitució, espera abans o després) compta un sol cop
per data, encara que surti en exàmens que comencen en franges diferents."""

from dataclasses import replace

from suport_motor_nou import config_inventada as config_inventada

from planificador.compartit.nivells import NivellsDelsGrups
from planificador.motor.avaluador import cost
from planificador.motor.compatibilitat import COST_MOSTRAT, RECUIT
from planificador.motor.construccio import construeix_problema, particio
from planificador.motor.cost_cerca import CostCercaRecuit, SolucioRecuit
from planificador.motor.model import HorariEditable
from planificador.motor.registre import ValidadorHorari

PES_ABANS = 30


def _problema(config_inventada, tmp_path, politiques):
    """Prof 01 comença a les 12:00 (classe amb N3-A) i és titular de A (N1) i B (N2)."""
    xml = tmp_path / "horari.xml"
    xml.write_text(
        '<Teachers_Timetable><Teacher name="Prof 01"><Day name="Dilluns">'
        '<Hour name="09:00"/><Hour name="10:00"/><Hour name="11:00"/>'
        '<Hour name="12:00"><Subject name="Mat"/><Students name="N3-A"/></Hour>'
        "</Day></Teacher></Teachers_Timetable>"
    )
    assignacio = {"titular": "Prof 01", "aula": ""}
    cfg = replace(
        config_inventada,
        config={
            "assignatures": {
                "A": {"assignacions": [{"grup": "N1-A", **assignacio}]},
                "B": {"assignacions": [{"grup": "N2-A", **assignacio}]},
            }
        },
        restriccions={"pesos_optimitzacio": {}},
        nivells_configurats=["N1", "N2"],
        nivells_master=["N1", "N2"],
        nivells_dels_grups=NivellsDelsGrups({"N1": ["N1-A"], "N2": ["N2-A"], "N3": ["N3-A"]}),
    )
    return construeix_problema(
        cfg,
        str(xml),
        ["N1", "N2"],
        ["Dilluns"],
        ["2027-03-01"],
        {"dilluns": ["2027-03-01"]},
        ["09:00", "11:00"],
        politiques,
    )


def test_una_hora_d_espera_es_compta_un_sol_cop_per_data(config_inventada, tmp_path):
    """Exàmens a les 09:00 i a les 11:00 i la primera classe a les 12:00: ha d'arribar abans a
    les 09:00, 10:00 i 11:00. Abans, les 11:00 es comptava dues vegades (una per examen)."""
    problema = _problema(config_inventada, tmp_path, COST_MOSTRAT)
    a, b = (e.a_diccionari() for e in problema.examens)
    horari = {
        "dies": [
            {
                "dia": "Dilluns",
                "data": "2027-03-01",
                "sessions": [
                    {"hora": "09:00", "sessions_simultanees": [a]},
                    {"hora": "11:00", "sessions_simultanees": [b]},
                ],
            }
        ],
        "metadata": {},
    }
    resultat = cost(HorariEditable(horari), problema)
    abans = sorted(i.hora for i in resultat.incidencies if i.concepte == "abans_jornada")
    assert abans == ["09:00", "10:00", "11:00"]
    assert resultat.total == 3 * PES_ABANS

    # El recuit compta el mateix (cost mostrat exacte)
    recuit = _problema(config_inventada, tmp_path, RECUIT)
    cerca = CostCercaRecuit(recuit, problema)
    items = particio(recuit, RECUIT)
    cerca.prepara(items, RECUIT)
    per_nom = {it.examens[0].nom: it for it in items}
    franja = {f.hora: f for f in recuit.franges}
    solucio = SolucioRecuit({per_nom[a["nom"]].id: franja["09:00"], per_nom[b["nom"]].id: franja["11:00"]})
    assert cerca.total(solucio)[0] == resultat.total

    # I el registre, una sola línia per hora (la suma és el cost)
    from planificador.compartit.franja import franja as de_clau  # noqa: PLC0415
    from planificador.motor.disponibilitat import Disponibilitat, analitza_motor  # noqa: PLC0415

    disponible = Disponibilitat(problema)
    for franja_doc in horari["dies"][0]["sessions"]:
        for sessio in franja_doc["sessions_simultanees"]:
            sessio["analisi"] = analitza_motor(
                problema, disponible, sessio, de_clau(f"2027-03-01_{franja_doc['hora']}")
            )
    linies = [
        m
        for m in ValidadorHorari(horari, problema.regles.a_diccionari(), set()).validar()["logs"]
        if m["codi"] == "inc_abans"
    ]
    assert len(linies) == 3
    assert sum(m["punts"] for m in linies) == resultat.total


def test_el_backtracking_tria_amb_les_hores_comptades_un_cop_per_data(config_inventada, tmp_path):
    """Al backtracking. A és fix a les 09:00 i Prof 01 (titular d'A i de B) entra
    a les 12:00. B a les 09:00: esperes 09–11 (90) + substitució de Prof 02 (20) = 110. B a les
    11:00: les mateixes esperes, que ja estan comptades aquella data = 90. Comptant per franja,
    B a les 11:00 sumava 30 més (120) i el backtracking triava les 09:00."""
    import random  # noqa: PLC0415

    from planificador.motor.compatibilitat import BACKTRACKING  # noqa: PLC0415
    from planificador.motor.cost_cerca import CostCercaBacktracking  # noqa: PLC0415
    from planificador.motor.estrategies.backtracking import Backtracking  # noqa: PLC0415
    from planificador.motor.estrategies.base import Pressupost  # noqa: PLC0415

    xml = tmp_path / "horari.xml"
    xml.write_text(
        '<Teachers_Timetable><Teacher name="Prof 01"><Day name="Dilluns">'
        '<Hour name="09:00"/><Hour name="10:00"/><Hour name="11:00"/>'
        '<Hour name="12:00"><Subject name="Mat"/><Students name="N3-A"/></Hour>'
        '</Day></Teacher><Teacher name="Prof 02"><Day name="Dilluns">'
        '<Hour name="09:00"><Subject name="Mat"/><Students name="N3-A"/></Hour>'
        '<Hour name="10:00"/><Hour name="11:00"/>'
        '<Hour name="12:00"><Subject name="Mat"/><Students name="N3-A"/></Hour>'
        "</Day></Teacher></Teachers_Timetable>"
    )
    cfg = replace(
        config_inventada,
        config={
            "assignatures": {
                "A": {"assignacions": [{"grup": "N1-A", "titular": "Prof 01", "aula": ""}]},
                "B": {
                    "assignacions": [
                        {"grup": "N2-A", "titular": "Prof 01", "aula": ""},
                        {"grup": "N2-B", "titular": "Prof 02", "aula": ""},
                    ]
                },
            }
        },
        restriccions={
            "restriccions_dures": {
                "assignatures_dia_fix": {"A (N1)": "Dilluns"},
                "assignatures_hora_fix": {"A (N1)": "09:00"},
            },
            "costos_professors": {"globals": {"substitucio": 20, "abans_jornada": 30}},
        },
        nivells_configurats=["N1", "N2"],
        nivells_master=["N1", "N2"],
        nivells_dels_grups=NivellsDelsGrups({"N1": ["N1-A"], "N2": ["N2-A", "N2-B"], "N3": ["N3-A"]}),
    )
    problema = construeix_problema(
        cfg,
        str(xml),
        ["N1", "N2"],
        ["Dilluns"],
        ["2027-03-01"],
        {"dilluns": ["2027-03-01"]},
        ["09:00", "11:00"],
        BACKTRACKING,
    )
    resultat = Backtracking().cerca(
        problema, BACKTRACKING, CostCercaBacktracking(problema), {}, Pressupost(20), random.Random(1)
    )
    per_nom = {
        it.examens[0].nom: franja.hora
        for it in resultat.items
        for i, franja in resultat.assignacio.items()
        if i == it.id
    }
    assert per_nom == {"A (N1)": "09:00", "B (N2)": "11:00"}
    assert resultat.cost == 90
