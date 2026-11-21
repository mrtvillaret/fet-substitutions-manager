"""Una sola durada d'examen i, a tots els motors, un examen només pot
començar a una hora si hi cap sencer abans que s'acabi la jornada."""

from dataclasses import replace

from suport_motor_nou import config_inventada as config_inventada
from suport_motor_nou import problema_inventat
from suport_motor_nou import xml_inventat as xml_inventat

from planificador.motor.compatibilitat import BACKTRACKING, GREEDY, RECUIT
from planificador.motor.construccio import particio
from planificador.motor.cost_cerca import CostCercaGreedy, CostCercaRecuit, SolucioRecuit
from planificador.motor.durades import examen_del_problema, examen_hi_cap, hores_ocupades
from planificador.motor.estrategies import backtracking as bt
from textos import normalitzar_hora


def _problema(config, xml, durada_examen):
    return replace(problema_inventat(config, xml), durada_examen=durada_examen)


def test_la_durada_general_d_examen_arriba_als_motors(config_inventada, xml_inventat):
    problema = _problema(config_inventada, xml_inventat, 2)
    assert examen_del_problema(problema.examens[0].nom, problema) == 2


def test_cap_motor_col_loca_un_examen_que_no_hi_cap(config_inventada, xml_inventat):
    durada = 2
    problema = _problema(config_inventada, xml_inventat, durada)
    nom = problema.examens[0].nom
    ultima = problema.graella[-1]
    assert not examen_hi_cap(nom, ultima, problema)
    assert examen_hi_cap(nom, problema.graella[0], problema)
    franges_ultima = [f for f in problema.franges if f.hora == ultima]
    assert franges_ultima

    greedy = CostCercaGreedy(problema)
    item = {"sessions": [problema.examens[0].a_diccionari()]}
    for franja in franges_ultima:
        assert greedy.item(item, franja, [], [], {}, [], set(), GREEDY) is None

    recuit = CostCercaRecuit(problema)
    items = particio(problema, RECUIT)
    recuit.prepara(items, RECUIT)
    for franja in franges_ultima:
        assert not recuit.compatible(SolucioRecuit({}), items[0], franja)

    motor = bt.Backtracking()
    motor.problema, motor.politiques = problema, BACKTRACKING
    motor.disponibilitat = None
    dures = bt._Dures(problema, BACKTRACKING)
    for franja in franges_ultima:
        assert motor._professors_item_a_franja(item, franja, dures) is None


def test_amb_hores_sense_zero_a_l_xml_l_examen_hi_cap(config_inventada, xml_inventat):
    """La graella dels motors és el text cru de l'XML («9:00») i les hores d'inici arriben
    normalitzades («09:00»): abans no es trobaven i cap examen de més d'una hora no hi cabia."""
    problema = _problema(config_inventada, xml_inventat, 2)
    crua = tuple(h.lstrip("0") if h[:1] == "0" else h for h in problema.graella)
    assert crua != problema.graella  # la graella inventada té alguna hora amb zero al davant
    problema = replace(problema, graella=crua)
    nom = problema.examens[0].nom
    inici = normalitzar_hora(crua[0])
    assert examen_hi_cap(nom, inici, problema)
    assert hores_ocupades(inici, crua, 2) == [normalitzar_hora(h) for h in crua[:2]]
    assert not examen_hi_cap(nom, normalitzar_hora(crua[-1]), problema)


def _encavalcable(config, xml):
    """Graella 09:00, PATI, 11:00: A dura 3 h (09:00–11:00) i B, 1 h."""
    base = _problema(config, xml, 1)
    a, b = (e.a_diccionari() for e in base.examens[:2])
    return replace(base, durades_examen={a["nom"]: 3}), a, b


def test_dos_examens_del_mateix_nivell_no_s_encavalquen(config_inventada, xml_inventat):
    """Un examen llarg ocupa també les hores següents per al seu nivell."""
    from planificador.motor.durades import encavalca_amb_el_nivell  # noqa: PLC0415

    problema, a, b = _encavalcable(config_inventada, xml_inventat)
    franja_09, franja_11 = problema.franges
    assert encavalca_amb_el_nivell([b], franja_11.clau, [(a, franja_09.clau)], problema)
    assert encavalca_amb_el_nivell([a], franja_09.clau, [(b, franja_11.clau)], problema)
    # Un altre nivell, una altra data o la mateixa sessió no compten
    assert not encavalca_amb_el_nivell([dict(b, curs="N9")], franja_11.clau, [(a, franja_09.clau)], problema)
    assert not encavalca_amb_el_nivell([b], "2099-01-01_11:00", [(a, franja_09.clau)], problema)
    assert not encavalca_amb_el_nivell([a], franja_09.clau, [(a, franja_09.clau)], problema)

    greedy = CostCercaGreedy(problema)
    assert greedy.item({"sessions": [b]}, franja_11, [], [], {}, [(a, franja_09.clau)], set(), GREEDY) is None
    assert greedy.item({"sessions": [b]}, franja_11, [], [], {}, [], set(), GREEDY) is not None

    recuit = CostCercaRecuit(problema)
    items = particio(problema, RECUIT)
    recuit.prepara(items, RECUIT)
    item_a = next(it for it in items if it.examens[0].nom == a["nom"])
    item_b = next(it for it in items if it.examens[0].nom == b["nom"])
    assert not recuit.compatible(SolucioRecuit({item_a.id: franja_09}), item_b, franja_11)
    assert recuit.compatible(SolucioRecuit({}), item_b, franja_11)


def test_l_editor_marca_dos_examens_encavalcats(config_inventada, xml_inventat):
    from planificador.motor.sortida import encavalcaments_del_dia  # noqa: PLC0415

    problema, a, b = _encavalcable(config_inventada, xml_inventat)
    dia = {"sessions": [{"hora": "09:00", "sessions_simultanees": [a]}, {"hora": "11:00", "sessions_simultanees": [b]}]}
    assert encavalcaments_del_dia(dia, problema) == {"09:00": [b["nom"]], "11:00": [a["nom"]]}


def test_l_analisi_no_compta_cost_a_la_zona_d_examen(config_inventada, tmp_path):
    """Revisió de la fase 2: l'anàlisi segueix la regla única de durada. Examen de 3 h amb
    vigilància d'1 h a les 08:00; el titular té classe amb un altre grup a les 09:00 i les 10:00
    (zona d'examen): no hi ha cap substitució, com al cost mostrat. Abans, 160 punts."""
    from planificador.compartit.nivells import NivellsDelsGrups
    from planificador.motor.avaluador import cost
    from planificador.motor.compatibilitat import ANALISI, COST_MOSTRAT
    from planificador.motor.construccio import construeix_problema
    from planificador.motor.model import HorariEditable
    from planificador.motor.textos_analisi import TextosAnalisi

    hores = [("08:00", None), ("09:00", "N1-B"), ("10:00", "N1-B")]
    xml = tmp_path / "horari.xml"
    xml.write_text(
        '<Teachers_Timetable><Teacher name="Prof 01"><Day name="Dilluns">'
        + "".join(
            f'<Hour name="{h}">'
            + (f'<Subject name="Mat"/><Students name="{g}"/>' if g else '<Subject name="Guardia"/>')
            + "</Hour>"
            for h, g in hores
        )
        + "</Day></Teacher></Teachers_Timetable>"
    )
    cfg = replace(
        config_inventada,
        config={"assignatures": {"A": {"assignacions": [{"grup": "N1-A", "titular": "Prof 01", "aula": ""}]}}},
        durada_examen=3,
        nivells_dels_grups=NivellsDelsGrups({"N1": ["N1-A"], "N2": ["N1-B"]}),
    )

    def problema(politiques):
        return construeix_problema(
            cfg, str(xml), ["N1"], ["Dilluns"], ["2027-03-01"], {"dilluns": ["2027-03-01"]}, ["08:00"], politiques
        )

    analisi = TextosAnalisi(problema(ANALISI))
    (slots,) = (v["slots"] for v in analisi.matriu(["Dilluns"]).values())
    franja = slots["Dilluns_08:00"]
    assert (franja["cost_total"], franja["cost_substitucions"]) == (0, 0)
    assert franja["per_hour"]["09:00"]["zona_professors"] == ["Prof 01"]
    examen = problema(COST_MOSTRAT).examens[0].a_diccionari()
    horari = {
        "dies": [
            {"dia": "Dilluns", "data": "2027-03-01", "sessions": [{"hora": "08:00", "sessions_simultanees": [examen]}]}
        ]
    }
    assert cost(HorariEditable(horari), problema(COST_MOSTRAT)).total == 0
    [sessio] = analisi.informes(["Dilluns"], lambda g: g)["per_sessio"]
    assert {"tipus": "zona", "noms": ["Prof 01"]} in [d for f in sessio["files"] for d in f["detalls"]]
