"""Caracterització del backtracking del planificador: fixa el que fa
cada fase —preparació dels ítems, matriu de
compatibilitat i ordre, propagació, cerca amb fer/desfer, cost afegit, talls
per nodes i per temps, empats amb la llavor—.

El motor és el real (`planificador/motor/estrategies/backtracking.py`); se'n
substitueixen la partició en ítems, el cost dels professors i l'anàlisi de
cada franja (taules fixes), i a alguns casos les restriccions. El cost de restriccions i preferències és el real (el del cost
final): que la cerca el minimitza es comprova a `test_backtrack_cost_final.py`.
"""

import json
import random
from pathlib import Path
from types import SimpleNamespace

import pytest

from planificador.compartit.franja import franja
from planificador.compartit.missatges import missatge
from planificador.motor.compatibilitat import BACKTRACKING
from planificador.motor.cost_cerca import CostCercaBacktracking
from planificador.motor.estrategies import backtracking as bt
from planificador.motor.estrategies.base import Pressupost
from planificador.motor.model import Item, congela
from planificador.motor.regles import construeix_regles
from planificador.motor.sortida import horari_backtracking

HORES = ["08:00", "09:00", "10:00"]
INSTANTANIA = Path(__file__).parent / "caracteritzacio" / "backtrack_llavors.json"


def sessio(nom, curs="1-ESO"):
    return {"nom": nom, "curs": curs}


def item(nom, curs="1-ESO", sessions=None):
    return {"nom": nom, "sessions": sessions or [sessio(nom, curs)]}


class MotorAmbTaules(bt.Backtracking):
    """El backtracking real amb taules fixes. Conserva el que necessita la
    cerca d'una llavor (`_cerca_amb_llavor`) entre crides, com el motor d'una
    petició: les causes apuntades per una llavor no es tornen a apuntar."""

    def prepara(self, dies):
        if getattr(self, "problema", None) is not None:
            return
        prefixos = self.dates or list(dies)
        self.problema = SimpleNamespace(
            franges=tuple(franja(f"{p}_{h}") for p in prefixos for h in self.hores),
            regles=construeix_regles(self.restriccions_originals),
            nivells=tuple(self.nivells),
            dies=tuple(dies),
            durades_vigilancia=self.durades,
            durada_titular=1,
            # Sense durades d'examen pròpies: l'examen dura el que es vigila.
            durades_examen={},
            durada_examen=1,
            graella=tuple(self.hores),
            mapa_dies={},
        )
        self.politiques = BACKTRACKING
        self.cost_cerca = CostCercaBacktracking(self.problema)
        self.pressupost = Pressupost(20, lambda: self.ara[0])
        self.pressupost.inicia()
        self.restriccions = self.problema.regles.a_diccionari()
        self.nivells_actius = list(self.nivells)
        self.items = ()
        self.registre = []
        self.causes = []
        self.aturada = None
        self.cerca_acabada = False
        self.disponibilitat = None


def crea_motor(
    monkeypatch,
    items,
    costos=None,
    *,
    hores=HORES,
    restriccions=None,
    dates=None,
    durades=None,
    professors=None,
    prohibides=None,
):
    """Motor amb taules fixes. `costos`: {(sessió, dia o data, hora): punts}
    o {sessió: punts}; `professors`: {(sessió, dia o data, hora): {professor:
    punts}}; `prohibides`: {(sessió, dia o data, hora): restricció dura}."""
    costos, professors, durades = costos or {}, professors or {}, durades or {}
    gen = MotorAmbTaules()
    gen.problema = None
    gen.restriccions_originals = restriccions or {}
    gen.nivells = sorted({s["curs"] for it in items for s in it["sessions"]})
    gen.hores = list(hores)
    gen.dates = list(dates or [])
    gen.durades = durades
    gen.ara = [0]
    gen.crides_cost = []
    particio_fixa = tuple(
        Item(f"item_{i}", it["nom"], (), congela({**it, "item_id": f"item_{i}", "sessions": list(it["sessions"])}))
        for i, it in enumerate(items)
    )
    monkeypatch.setattr(bt, "particio", lambda *_: particio_fixa)
    monkeypatch.setattr(bt, "Disponibilitat", lambda _: None)  # l'anàlisi és la taula fixa
    gen._analitza = lambda s, ubicacio, altres=(): {
        "sessio": s["nom"],
        "dia": ubicacio.dia,
        "hora": ubicacio.hora,
        "data": ubicacio.data_iso,
    }

    def cost(**k):
        nom = k["sessio"]["nom"]
        clau = (nom, k["data_iso"] or k["dia"], k["hora"])
        gen.crides_cost.append({**k, "ja_comptats": set(k["ja_comptats"])})
        assert k["analisi"] == {"sessio": nom, "dia": k["dia"], "hora": k["hora"], "data": k["data_iso"] or None}
        punts = costos.get(clau, costos.get(nom, 0))
        # El cost d'una sessió sola a una franja és el dels seus professors: si
        # la taula de professors no en diu cap, un de propi amb tots els punts
        comptats = professors.get(clau, {("cost", nom): punts} if punts else {})
        # Una franja de 10000 punts o més de la taula representa un professor
        # amb horari estricte fora del seu horari: la franja queda fora (abans, el
        # tall numèric de 10000, que ja no existeix).
        estrictes = ["Prof estricte"] if punts >= 10000 else []
        return {"cost_total": punts, "costos_professors": dict(comptats), "professors_estrictes_violats": estrictes}

    monkeypatch.setattr(bt, "cost_sessio", cost)
    if prohibides is not None:

        class Dures:
            def __init__(self, *_):
                pass

            def comprova(self, s, dia, hora, prefix, *_):
                causa = prohibides.get((s["nom"], prefix, hora))
                return SimpleNamespace(clau=causa) if causa else None

        monkeypatch.setattr(bt, "_Dures", Dures)
    return gen


def resol(gen, llavor=1, dies=("Dilluns",), max_nodes=100000, shuffle_top_n=0):
    """(solucions, línies del registre) d'una sola llavor."""
    gen.prepara(dies)
    abans = len(gen.registre)
    solucions = gen._cerca_amb_llavor(llavor, list(dies), max_nodes, shuffle_top_n)
    return solucions, gen.registre[abans:]


def on_va(solucio):
    """{franja: [ítems]} d'una solució (cost, {franja: [info de l'ítem]})."""
    return {sk: sorted(it["etiqueta"] for it in its) for sk, its in solucio[1].items()}


def info(solucio, label):
    return next(it for its in solucio[1].values() for it in its if it["etiqueta"] == label)


# ---------------------------------------------------------------------------
# Fase 1: preparació dels ítems
# ---------------------------------------------------------------------------


def test_preparacio_costos_i_franges_possibles(monkeypatch):
    """Una franja queda fora per restricció dura, per no tenir prou hores o
    perquè deixa un professor amb horari estricte fora del seu horari (a la
    taula, 10000); la resta es queda amb la suma dels costos."""
    gen = crea_motor(
        monkeypatch,
        [item("A"), item("B", "2-ESO")],
        costos={("A", "Dilluns", "09:00"): 10000, ("A", "Dilluns", "10:00"): 5, ("B", "Dilluns", "08:00"): 3, "B": 2},
        durades={"B": 2},
        prohibides={("A", "Dilluns", "08:00"): "dia_hora_fix"},
    )
    solucions, registre = resol(gen)
    assert len(solucions) == 1
    assert solucions[0][0] == 7
    assert on_va(solucions[0]) == {"Dilluns_10:00": ["A"], "Dilluns_09:00": ["B"]}
    a, b = info(solucions[0], "A"), info(solucions[0], "B")
    assert a["totes_franges"] == {"Dilluns_10:00": 5}
    assert a["franges_possibles"] == {"Dilluns_10:00"}
    assert (a["millor_cost"], a["mascara_nivell"], a["id"]) == (5, 1, 0)
    assert b["totes_franges"] == {"Dilluns_08:00": 3, "Dilluns_09:00": 2}
    assert (b["millor_cost"], b["mascara_nivell"], b["id"]) == (2, 2, 1)
    assert a["item"]["nom"] == "A"
    assert gen.causes == []
    assert gen.aturada is None
    # La franja prohibida i la que no té prou hores no arriben a calcular cost
    assert [(c["sessio"]["nom"], c["hora"]) for c in gen.crides_cost] == [
        ("A", "09:00"),
        ("A", "10:00"),
        ("B", "08:00"),
        ("B", "09:00"),
    ]
    assert all(c["sessions_dia"] == [] and c["sessions_slot"] is None for c in gen.crides_cost)
    assert registre == [
        "🔍 Pre-calculant costos i compatibilitats per 2 items...",
        "   Calculant matriu de compatibilitat 2x2...",
        "   ✅ 2 items preparats",
        "   📊 Nodes explorats: 3, solucions trobades: 1",
    ]


def test_preparacio_amb_dates_passa_el_dia_i_la_data(monkeypatch):
    gen = crea_motor(
        monkeypatch, [item("A")], costos={("A", "2026-04-21", "09:00"): 0, "A": 4}, dates=["2026-04-20", "2026-04-21"]
    )
    solucions, _ = resol(gen, dies=("Dilluns", "Dimarts"))
    assert on_va(solucions[0]) == {"2026-04-21_09:00": ["A"]}
    assert [(c["dia"], c["data_iso"]) for c in gen.crides_cost] == [("Dilluns", "2026-04-20")] * 3 + [
        ("Dimarts", "2026-04-21")
    ] * 3


def test_exclosos_sense_cap_franja_i_el_seu_motiu(monkeypatch):
    """Un ítem sense cap franja queda fora de la cerca (la resta es col·loca)
    i deixa un missatge: la restricció dura més freqüent, o cap causa."""
    prohibides = {("A", "Dilluns", h): "dia_hora_fix" for h in HORES[:2]} | {("A", "Dilluns", "10:00"): "no_mateix_dia"}
    gen = crea_motor(monkeypatch, [item("A"), item("B"), item("C")], costos={"B": 10000, "C": 1}, prohibides=prohibides)
    solucions, registre = resol(gen)
    assert [(cost, list(on_va((cost, sol)).values())) for cost, sol in solucions] == [(1, [["C"]])]
    assert gen.causes == [
        missatge("examen_sense_hora_causa", nom="A", causa="dia_hora_fix"),
        missatge("examen_sense_hora_motor", nom="B"),
    ]
    assert registre[1] == "   ⚠️ 2 items sense cap slot viable (exclosos del backtrack): ['A', 'B']"
    assert info(solucions[0], "C")["id"] == 0
    # Una altra llavor no torna a apuntar els motius
    resol(gen, llavor=2)
    assert len(gen.causes) == 2


def test_tots_exclosos_no_hi_ha_cerca(monkeypatch):
    gen = crea_motor(monkeypatch, [item("A")], costos={"A": 10000})
    solucions, registre = resol(gen)
    assert solucions == []
    assert gen.causes == [missatge("examen_sense_hora_motor", nom="A")]
    assert len(registre) == 2


def test_sense_items_no_fa_res(monkeypatch):
    gen = crea_motor(monkeypatch, [])
    assert resol(gen) == ([], [])


def test_professors_ja_comptats_dins_d_un_item(monkeypatch):
    """Les sessions d'un mateix ítem es passen els professors ja comptats."""
    agrupat = item("G", sessions=[sessio("S1"), sessio("S2")])
    gen = crea_motor(
        monkeypatch,
        [agrupat],
        costos={"S1": 4, "S2": 6},
        hores=["08:00"],
        professors={("S1", "Dilluns", "08:00"): {"P1": 4}, ("S2", "Dilluns", "08:00"): {"P2": 6}},
    )
    solucions, _ = resol(gen)
    assert solucions[0][0] == 10
    assert [c["ja_comptats"] for c in gen.crides_cost] == [set(), {"P1"}]
    assert info(solucions[0], "G")["claus_franja"] == {"Dilluns_08:00": {"P1": 4, "P2": 6}}


# ---------------------------------------------------------------------------
# Fase 2: compatibilitat i ordre
# ---------------------------------------------------------------------------


def test_mateix_nivell_no_comparteix_franja(monkeypatch):
    gen = crea_motor(monkeypatch, [item("A"), item("B")], hores=["08:00"])
    solucions, _ = resol(gen)
    assert solucions == []
    assert gen.causes == [missatge("examen_sense_hora_causa", nom="B", causa="conflicte_restriccions")]


def test_qualsevol_nivell_te_bit_i_no_comparteix_franja(monkeypatch):
    """Els bits es reparteixen per nivell a cada preparació: «1-BAT»,
    que no era al mapa fix d'abans (màscara 0), ara també en té. El resultat
    és el mateix: abans ho aturava la regla d'or de la matriu."""
    gen = crea_motor(monkeypatch, [item("A", "1-BAT"), item("B", "1-BAT"), item("C", "")], hores=["08:00"])
    capturats = []
    prepara = gen._prepara_items

    def amb_captura(*args):
        capturats.extend(prepara(*args))
        return capturats

    gen._prepara_items = amb_captura
    assert resol(gen)[0] == []
    assert [it["mascara_nivell"] for it in capturats] == [1, 1, 0]  # sense nivell, cap bit


def test_nivells_diferents_comparteixen_franja(monkeypatch):
    gen = crea_motor(monkeypatch, [item("A"), item("B", "2-ESO")], hores=["08:00"])
    solucions, _ = resol(gen)
    assert on_va(solucions[0]) == {"Dilluns_08:00": ["A", "B"]}


def test_no_mateix_slot_obligatori_no_comparteix_franja(monkeypatch):
    restriccions = {"restriccions_dures": {"no_mateix_slot": {"grup": ["A", "B"]}}}
    gen = crea_motor(monkeypatch, [item("A"), item("B", "2-ESO")], costos={"A": 1}, restriccions=restriccions)
    vist = []
    real = bt.es_item_compatible_amb_slot

    def compatible(it, sessions_slot, restr):
        vist.append((it["nom"], [s["sessio"]["nom"] for s in sessions_slot]))
        return real(it, sessions_slot, restr)

    monkeypatch.setattr(bt, "es_item_compatible_amb_slot", compatible)
    solucions, _ = resol(gen)
    assert vist == [("A", ["B"])]
    franges = on_va(solucions[0])
    assert len(franges) == 2 and sorted(sum(franges.values(), [])) == ["A", "B"]


def test_ordre_dels_items_mes_restringits_primer(monkeypatch):
    """Primer qui té menys franges; a igualtat, qui té el millor cost més baix;
    a igualtat de tot, l'ordre de la partició."""
    costos = {("X", "Dilluns", "08:00"): 10000, ("X", "Dilluns", "09:00"): 10000, "X": 9}
    costos |= {("Z", "Dilluns", "08:00"): 10000, "Z": 5, ("W", "Dilluns", "10:00"): 10000, "W": 2, "Y": 1, "V": 1}
    noms = ["Y", "V", "Z", "W", "X"]
    gen = crea_motor(monkeypatch, [item(n, f"{i + 1}-ESO" if i < 4 else "CFGM") for i, n in enumerate(noms)], costos)
    solucions, _ = resol(gen)
    ordre = sorted(noms, key=lambda n: info(solucions[0], n)["index_ordre"])
    assert ordre == ["X", "W", "Z", "Y", "V"]
    assert [info(solucions[0], n)["id"] for n in noms] == [0, 1, 2, 3, 4]


# ---------------------------------------------------------------------------
# Fase 3: cerca
# ---------------------------------------------------------------------------

COSTOS_OPTIM_UNIC = {
    ("A", "Dilluns", "08:00"): 1,
    ("A", "Dilluns", "09:00"): 2,
    ("A", "Dilluns", "10:00"): 9,
    ("B", "Dilluns", "08:00"): 1,
    ("B", "Dilluns", "09:00"): 7,
    ("B", "Dilluns", "10:00"): 8,
    ("C", "Dilluns", "08:00"): 6,
    ("C", "Dilluns", "09:00"): 5,
    ("C", "Dilluns", "10:00"): 4,
}


@pytest.mark.parametrize("llavor", [1, 2, 3])
def test_cerca_troba_l_optim_unic(monkeypatch, llavor):
    gen = crea_motor(monkeypatch, [item("A"), item("B"), item("C")], COSTOS_OPTIM_UNIC)
    solucions, registre = resol(gen, llavor=llavor)
    assert [(c, on_va((c, s))) for c, s in solucions] == [
        (7, {"Dilluns_09:00": ["A"], "Dilluns_08:00": ["B"], "Dilluns_10:00": ["C"]})
    ]
    assert registre[-1] == "   📊 Nodes explorats: 8, solucions trobades: 1"
    assert gen.aturada is None


def test_tall_per_nodes(monkeypatch):
    """Passat el límit de nodes la cerca s'atura, es queda amb el que tenia i
    no dona la culpa a cap examen."""
    gen = crea_motor(monkeypatch, [item("A"), item("B"), item("C")], COSTOS_OPTIM_UNIC)
    solucions, registre = resol(gen, max_nodes=4)
    assert [(c, on_va((c, s))) for c, s in solucions] == [
        (12, {"Dilluns_08:00": ["A"], "Dilluns_09:00": ["B"], "Dilluns_10:00": ["C"]})
    ]
    assert registre[-2:] == [
        "   ⚠️ Límit de nodes assolit (4), backtrack tallat",
        # Les crides tallades ja no compten; abans deia 7
        "   📊 Nodes explorats: 4, solucions trobades: 1",
    ]
    assert gen.aturada == "nodes"

    gen = crea_motor(monkeypatch, [item("A"), item("B"), item("C")], COSTOS_OPTIM_UNIC)
    solucions, _ = resol(gen, max_nodes=2)
    assert solucions == []
    assert gen.aturada == "nodes"
    assert gen.causes == []


def test_tall_per_temps_a_la_cerca(monkeypatch):
    gen = crea_motor(monkeypatch, [item("A"), item("B"), item("C")], COSTOS_OPTIM_UNIC)
    ara = gen.ara
    afegits = []
    cost_afegit = gen._cost_afegit

    def amb_rellotge(it_info, *args):
        afegits.append(it_info["etiqueta"])
        if len(afegits) == 2:
            ara[0] = 25
        return cost_afegit(it_info, *args)

    gen._cost_afegit = amb_rellotge
    solucions, registre = resol(gen)
    assert solucions == []
    assert afegits == ["A", "B"]
    assert gen.causes == []
    assert gen.aturada is None  # el marca qui reparteix les llavors
    assert registre[-1] == "   📊 Nodes explorats: 2, solucions trobades: 0"


def test_empats_de_cost_nomes_en_queda_una_solucio(monkeypatch):
    """La poda és amb `>=`: d'entre les solucions amb el mateix cost només en
    queda la primera."""
    gen = crea_motor(monkeypatch, [item("A"), item("B")])
    solucions, _ = resol(gen)
    assert len(solucions) == 1 and solucions[0][0] == 0


def test_propagacio_no_mateix_dia(monkeypatch):
    """Dues assignatures que no poden anar el mateix dia: amb un sol dia no hi
    ha solució i el missatge assenyala la que s'ha quedat sense franges."""
    restriccions = {"restriccions_dures": {"no_mateix_dia": [["A", "B"]]}}
    gen = crea_motor(monkeypatch, [item("A"), item("B", "2-ESO")], restriccions=restriccions)
    solucions, registre = resol(gen)
    assert solucions == []
    assert gen.causes == [missatge("examen_sense_hora_causa", nom="B", causa="conflicte_restriccions")]
    assert registre[-1] == "   📊 Nodes explorats: 1, solucions trobades: 0"

    gen = crea_motor(monkeypatch, [item("A"), item("B", "2-ESO")], restriccions=restriccions)
    solucions, registre = resol(gen, dies=("Dilluns", "Dimarts"))
    dies = {sk.split("_")[0] for sk in on_va(solucions[0])}
    assert dies == {"Dilluns", "Dimarts"}
    assert registre[-1] == "   📊 Nodes explorats: 3, solucions trobades: 1"


def test_atzucac_amb_causa_estructural(monkeypatch):
    """Sense solució, el motiu de l'ítem més profund que s'ha quedat sense
    franges és la restricció dura que més franges li treu (sense context)."""
    prohibides = {("B", "Dilluns", "09:00"): "dia_hora_fix", ("B", "Dilluns", "10:00"): "dia_hora_fix"}
    gen = crea_motor(
        monkeypatch, [item("A"), item("B")], costos={"A": 10000, ("A", "Dilluns", "08:00"): 0}, prohibides=prohibides
    )
    solucions, _ = resol(gen)
    assert solucions == []
    assert gen.causes == [missatge("examen_sense_hora_causa", nom="B", causa="dia_hora_fix")]


def test_cost_afegit_limit_per_professor(monkeypatch):
    """El límit d'exàmens per professor suma pels exàmens de més (aquí un,
    al 30 % del pes dur), com al cost final."""
    a = {"nom": "A", "curs": "1-ESO", "examens": [{"titular": "P"}]}
    b = {"nom": "B", "curs": "2-ESO", "examens": [{"titular": "P"}]}
    limit = {"assignatures": ["A", "B"], "dies_restringits": ["Dilluns"], "max_examens": 1, "pes_penalitzacio": 30}
    restriccions = {"restriccions_dures": {"professors_limit_dies_especifics": {"P": limit}}}
    gen = crea_motor(
        monkeypatch, [item("A", sessions=[a]), item("B", sessions=[b])], costos={"A": 1}, restriccions=restriccions
    )
    assert resol(gen)[0][0][0] == 3001


def test_cost_afegit_no_mateix_slot_parcial(monkeypatch):
    """Compartir franja amb una incompatible no obligatòria suma, a cada
    examen, el seu percentatge del pes dur (per defecte, 10000)."""
    grup = {"no_mateix_slot": {"g": ["A", "B"], "_pes_g": 50}}
    gen = crea_motor(
        monkeypatch, [item("A"), item("B", "2-ESO")], hores=["08:00"], restriccions={"restriccions_dures": grup}
    )
    assert resol(gen)[0][0][0] == 10000
    gen = crea_motor(
        monkeypatch,
        [item("A"), item("B", "2-ESO")],
        hores=["08:00"],
        restriccions={"restriccions_dures": grup, "pesos_optimitzacio": {"restriccio_dura": 200}},
    )
    assert resol(gen)[0][0][0] == 200


def test_cost_afegit_preferencia_mateix_slot(monkeypatch):
    """«Mateixa data i hora»: al 100% tanca la franja; per sota, suma els punts
    del cost final (les companyes el mateix dia a una altra hora)."""
    vist = []

    def obligatoria(s, sk, ubicacions, _r):
        vist.append((s["nom"], sk, [(u["nom"], k) for u, k in ubicacions]))
        return 100 if ubicacions and all(k != sk for _, k in ubicacions) else 0

    costos = {("A", "Dilluns", "08:00"): 0, "A": 9, ("B", "Dilluns", "09:00"): 0, "B": 3}
    gen = crea_motor(monkeypatch, [item("A"), item("B", "2-ESO")], costos, hores=HORES[:2])
    monkeypatch.setattr(bt, "percentatge_preferencia_mateix_slot", obligatoria)
    solucions, _ = resol(gen)
    assert (solucions[0][0], on_va(solucions[0])) == (3, {"Dilluns_08:00": ["A", "B"]})
    assert vist == [
        ("A", "Dilluns_08:00", []),
        ("B", "Dilluns_09:00", [("A", "Dilluns_08:00")]),
        ("B", "Dilluns_08:00", [("A", "Dilluns_08:00")]),
        # «A» a les 9:00 (9 punts) ja no pot millorar 3, i no se'n calcula el cost afegit
    ]
    monkeypatch.undo()

    preferencia = {"preferencies": {"mateix_slot": [{"assignatures": ["A", "B"], "pes": 1}]}}
    gen = crea_motor(monkeypatch, [item("A"), item("B", "2-ESO")], costos, hores=HORES[:2], restriccions=preferencia)
    solucions, _ = resol(gen)
    # Separats costarien 100 punts a cada examen (l'1 % de 10000)
    assert (solucions[0][0], on_va(solucions[0])) == (3, {"Dilluns_08:00": ["A", "B"]})


def test_professor_ja_comptat_a_la_franja_no_es_torna_a_comptar(monkeypatch):
    """Dos blocs a la mateixa franja amb el mateix professor: el segon no
    torna a sumar el que ja ha comptat el primer."""
    professors = {("A", "Dilluns", "08:00"): {"P": 4}, ("B", "Dilluns", "08:00"): {"P": 4, "Q": 2}}
    gen = crea_motor(
        monkeypatch, [item("A"), item("B", "2-ESO")], costos={"A": 4, "B": 6}, hores=["08:00"], professors=professors
    )
    assert resol(gen)[0][0][0] == 6


# ---------------------------------------------------------------------------
# Totes les llavors: instantània
# ---------------------------------------------------------------------------


def _escenari_llavors(monkeypatch, random_seed, seeds_count, shuffle_top_n, max_nodes, dies):
    """Tres nivells, empats i costos diferents, un ítem exclòs i una parella
    que no pot coincidir de dia."""
    noms = [
        ("A", "1-ESO"),
        ("B", "1-ESO"),
        ("C", "1-ESO"),
        ("D", "2-ESO"),
        ("E", "2-ESO"),
        ("F", "3-ESO"),
        ("X", "3-ESO"),
    ]
    costos = {
        "X": 10000,
        "C": 2,
        ("D", "Dilluns", "08:00"): 3,
        ("F", "Dimarts", "10:00"): 1,
        ("E", "Dilluns", "09:00"): 10000,
    }
    professors = {("A", d, h): {"P": 0} for d in dies for h in HORES}
    restriccions = {"restriccions_dures": {"no_mateix_dia": [["A", "D"]]}}
    gen = crea_motor(
        monkeypatch, [item(n, c) for n, c in noms], costos, restriccions=restriccions, professors=professors
    )
    solucions_llavor = []
    real = gen._cerca_amb_llavor

    def amb_llavor(*args, **kwargs):
        sols = real(*args, **kwargs)
        solucions_llavor.append(
            [
                {
                    "cost": cost,
                    "franges": sorted((sk, sorted(it["etiqueta"] for it in its)) for sk, its in sol.items()),
                    "ordre": sorted(
                        (it["index_ordre"], it["id"], it["etiqueta"]) for its in sol.values() for it in its
                    ),
                    "empats": {
                        it["etiqueta"]: sorted(it["rang_empat"], key=it["rang_empat"].get)
                        for its in sol.values()
                        for it in its
                    },
                }
                for cost, sol in sols
            ]
        )
        return sols

    gen._cerca_amb_llavor = amb_llavor
    gen.prepara(dies)
    parametres = {"seeds_count": seeds_count, "shuffle_top_n": shuffle_top_n, "max_nodes": max_nodes}
    cerca = gen.cerca(
        gen.problema, BACKTRACKING, gen.cost_cerca, parametres, Pressupost(20, lambda: 0), random.Random(random_seed)
    )
    if cerca.assignacio is None:
        horari = horari_backtracking(cerca, gen.problema, BACKTRACKING, None, 20, max_nodes)
    else:
        etiquetes = {it.id: it.nom for it in cerca.items}
        per_franja = {}
        for identificador, ubicacio in cerca.assignacio.items():
            per_franja.setdefault(ubicacio.clau, []).append(etiquetes[identificador])
        meta = {"cost_total": cerca.cost, "motor": "v2-backtrack"}
        if cerca.motiu_aturada:
            meta["motiu_aturada"] = cerca.motiu_aturada
        horari = {"dies": sorted((sk, sorted(noms)) for sk, noms in per_franja.items()), "metadata": meta}
    return {
        "crides_cost": len(gen.crides_cost),
        "resultat": [horari],
        "llavors": solucions_llavor,
        "incompatibilitats": cerca.causes,
        "aturada": cerca.motiu_aturada,
        "registre": cerca.registre,
    }


def test_la_preparacio_es_fa_una_sola_vegada_per_a_totes_les_llavors(monkeypatch):
    """Els costos de cada ítem a cada franja no depenen de la
    llavor; amb quatre llavors es calculen tants cops com amb una. Amb 12
    nodes totes les llavors es tallen (si una acabés, no se'n farien més)."""
    crides = []
    for seeds_count in (1, 4):
        cas = _escenari_llavors(monkeypatch, 1, seeds_count, 0, 12, ("Dilluns", "Dimarts"))
        assert len(cas["llavors"]) == seeds_count
        crides.append(cas["crides_cost"])
    assert crides[0] == crides[1] == 42  # set ítems (l'exclòs també) a sis franges


def test_amb_llavors_empatades_queda_un_sol_horari(monkeypatch):
    """Les quatre llavors (tallades als 12 nodes) arriben al mateix cost;
    abans es retornaven totes quatre («alternatives»), ara només l'horari de
    la primera."""
    cas = _escenari_llavors(monkeypatch, 1, 4, 0, 12, ("Dilluns", "Dimarts"))
    assert len(cas["llavors"]) == 4
    assert len({sol[0]["cost"] for sol in cas["llavors"]}) == 1
    assert len(cas["resultat"]) == 1
    assert "alternatives" not in cas["resultat"][0]["metadata"]


CASOS_LLAVORS = [
    (random_seed, seeds_count, shuffle_top_n, max_nodes, dies)
    for random_seed in (1, 2, 7)
    for seeds_count, shuffle_top_n, max_nodes, dies in [
        (1, 0, 100000, ("Dilluns", "Dimarts")),
        (4, 0, 100000, ("Dilluns", "Dimarts")),
        (4, 3, 100000, ("Dilluns", "Dimarts")),
        (3, 2, 12, ("Dilluns", "Dimarts")),
        (3, 2, 100000, ("Dilluns",)),
    ]
]


def _clau(cas):
    return "|".join(str(v) for v in cas)


def _instantania(monkeypatch, cas):
    obtingut = _escenari_llavors(monkeypatch, *cas)
    del obtingut["crides_cost"]  # abans, un cop per llavor
    return json.loads(json.dumps(obtingut))


def calcula_instantania(monkeypatch):
    """Per tornar a desar INSTANTANIA si mai canvia el comportament a propòsit."""
    return {_clau(cas): _instantania(monkeypatch, cas) for cas in CASOS_LLAVORS}


@pytest.mark.parametrize("cas", CASOS_LLAVORS, ids=_clau)
def test_instantania_de_totes_les_llavors(monkeypatch, cas):
    """Resultat, solucions de cada llavor (amb l'ordre dels ítems i els rangs
    dels empats), missatges i registre. On la primera llavor acaba sense tall
    només hi ha aquella llavor; amb 12 nodes es tallen i es fan totes."""
    esperat = json.loads(INSTANTANIA.read_text(encoding="utf-8"))[_clau(cas)]
    assert _instantania(monkeypatch, cas) == esperat


def test_exclosos_per_item_i_no_per_nom(monkeypatch):
    """Dos ítems amb el mateix nom, un de viable i l'altre no.
    Abans es buscaven pel nom: el registre deia «1 items … : []» i el que
    quedava fora no tenia missatge."""
    gen = crea_motor(monkeypatch, [item("A")])
    gen.prepara(["Dilluns"])
    dins, fora = item("A", "1-ESO"), item("A", "2-ESO")
    dures = SimpleNamespace(comprova=lambda *_: SimpleNamespace(clau="franja_prohibida"))
    gen._motius_exclosos([dins, fora], [{"item": dins, "etiqueta": "A"}], list(gen.problema.franges), dures)
    assert "   ⚠️ 1 items sense cap slot viable (exclosos del backtrack): ['A']" in gen.registre
    assert gen.causes == [missatge("examen_sense_hora_causa", nom="A", causa="franja_prohibida")]


# ---------------------------------------------------------------------------
# Poda abans de calcular el cost afegit
# ---------------------------------------------------------------------------


def _amb_compte_de_cost_afegit(gen):
    crides = []
    original = gen._cost_afegit

    def compta(*args, **kwargs):
        crides.append(args[1].clau)
        return original(*args, **kwargs)

    gen._cost_afegit = compta
    return crides


def test_no_calcula_el_cost_afegit_d_una_franja_que_ja_no_pot_millorar(monkeypatch):
    gen = crea_motor(monkeypatch, [item("A"), item("B"), item("C")], COSTOS_OPTIM_UNIC)
    crides = _amb_compte_de_cost_afegit(gen)
    solucions, registre = resol(gen)
    assert [(c, on_va((c, s))) for c, s in solucions] == [
        (7, {"Dilluns_09:00": ["A"], "Dilluns_08:00": ["B"], "Dilluns_10:00": ["C"]})
    ]
    assert registre[-1] == "   📊 Nodes explorats: 8, solucions trobades: 1"
    # Abans: 10 crides (totes les franges candidates que hi caben)
    assert len(crides) == 7


def test_amb_pesos_negatius_no_es_poda(monkeypatch):
    """Si un pes configurable és negatiu, el cost pot baixar en afegir
    exàmens: la cerca no deixa cap branca (abans encara podava amb el cost a
    mig fer, que aleshores no és cap fita)."""
    restriccions = {"pesos_optimitzacio": {"restriccio_dura": -10}}
    gen = crea_motor(monkeypatch, [item("A"), item("B"), item("C")], COSTOS_OPTIM_UNIC, restriccions=restriccions)
    crides = _amb_compte_de_cost_afegit(gen)
    solucions, _ = resol(gen)
    assert len(crides) == 15  # 3 + 3·2 + 6·1: totes les col·locacions
    assert solucions[0][0] == 7
