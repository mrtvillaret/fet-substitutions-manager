"""El backtracking minimitza el cost final que es mostra.

Abans la cerca sumava un cost propi (sense les preferències «mateix dia» i
«dies diferents» ni el «no el mateix dia» no obligatori, i amb el límit per
professor acumulat): podia acabar sense tall amb un horari més car que el dels
altres motors. Ara una cerca sense tall dona el cost mínim, i aquí es comprova
per força bruta: totes les col·locacions possibles, puntuades amb les funcions
del cost final (`estadistiques.incidencies_restriccions`).

La poda fa servir una fita inferior, perquè el cost d'un horari a mig fer pot
baixar en afegir-hi exàmens (bonificacions, i les regles que valen «la primera
que s'incompleix»). Es comprova de dues maneres: amb poda i sense, el mateix
cost; i a cada camí de la cerca sense poda, la fita de cada pas no supera mai
el cost de l'horari complet on acaba.

El motor és el real; se'n substitueixen la partició en ítems i el cost dels
professors de cada franja (taules fixes). Escenaris a l'atzar amb llavor fixa.
"""

import itertools
import random

import pytest

from scheduler_engine.estadistiques import incidencies_restriccions
from scheduler_engine.generators import v2_backtrack as bt

DATES = ["2026-04-20", "2026-04-21"]  # dilluns i dimarts
DIES = ["Dilluns", "Dimarts"]
HORES = ["08:00", "09:00"]
FRANGES = [f"{data}_{hora}" for data in DATES for hora in HORES]


def sessio(nom, curs, professor):
    return {"nom": f"{nom} ({curs})", "nom_base": nom, "curs": curs, "examens": [{"titular": professor}]}


class Escenari:
    """Ítems (els exàmens que van junts; si no es diu, un per examen),
    professors comptats a cada franja i restriccions."""

    def __init__(self, sessions, professors, restriccions, junts=()):
        self.sessions = sessions
        self.professors = professors  # {(nom, franja): {clau del professor: punts}}
        self.restriccions = restriccions
        agrupats = {nom for grup in junts for nom in grup}
        self.items = [[s for s in sessions if s["nom"] in grup] for grup in junts]
        self.items += [[s] for s in sessions if s["nom"] not in agrupats]

    def cost(self, on_va: dict[str, str]) -> int:
        """El cost final de l'horari {nom de l'examen: franja}: els professors
        de cada franja (cadascun una sola vegada) i les incidències."""
        per_franja = {}
        for s in self.sessions:
            per_franja.setdefault(on_va[s["nom"]], []).append(s)
        professors = 0
        for clau, sessions in per_franja.items():
            comptats = {}
            for s in sessions:
                comptats.update(self.professors.get((s["nom"], clau), {}))
            professors += sum(comptats.values())
        dies = []
        for data, dia in zip(DATES, DIES, strict=True):
            franges = [
                {"hora": hora, "sessions_simultanees": per_franja[f"{data}_{hora}"]}
                for hora in HORES
                if f"{data}_{hora}" in per_franja
            ]
            dies.append({"dia": dia, "data": data, "sessions": franges})
        return professors + sum(inc.punts for inc in incidencies_restriccions({"dies": dies}, self.restriccions))

    def minim_per_forca_bruta(self) -> int:
        """El cost més baix de totes les col·locacions sense dos exàmens del
        mateix nivell a la mateixa franja (l'única regla obligatòria d'aquests escenaris)."""
        millor = None
        for tria in itertools.product(FRANGES, repeat=len(self.items)):
            ocupades = [(curs, clau) for item, clau in zip(self.items, tria, strict=True) for curs in _nivells(item)]
            if len(set(ocupades)) < len(ocupades):
                continue
            cost = self.cost({s["nom"]: clau for item, clau in zip(self.items, tria, strict=True) for s in item})
            millor = cost if millor is None else min(millor, cost)
        return millor


def _nivells(item):
    return {s["curs"] for s in item}


class MotorComprovat(bt.GeneradorV2Backtrack):
    """El motor real, apuntant a cada horari complet el cost que hi porta la
    cerca, el seu camí de fites i el camí de costos."""

    def _cerca(self, cerca, idx, cost_ac, fita_ac):
        if idx >= len(cerca.items):
            on_va = {
                s["nom"]: cerca.estat.franja_item[i] for i, it in enumerate(cerca.items) for s in it["item"]["sessions"]
            }
            self.fulles.append((cost_ac, on_va, list(self.cami_fites), list(self.cami_costos)))
            return super()._cerca(cerca, idx, cost_ac, fita_ac)
        self.cami_fites.append(fita_ac - cerca.pendent[idx])
        self.cami_costos.append(cost_ac)
        try:
            return super()._cerca(cerca, idx, cost_ac, fita_ac)
        finally:
            self.cami_fites.pop()
            self.cami_costos.pop()


def crea_motor(monkeypatch, escenari, poda=True):
    gen = object.__new__(MotorComprovat)
    gen.restriccions = escenari.restriccions
    gen.nivells_actius = sorted({s["curs"] for s in escenari.sessions})
    gen.hores_examen = list(HORES)
    gen.selected_dates = list(DATES)
    gen._incompatibilitats_bt = []
    gen._aturada_bt = None
    gen.fulles, gen.cami_fites, gen.cami_costos = [], [], []
    gen.preparar_particio_nivells = lambda **_: [
        {"nom": " + ".join(s["nom"] for s in item), "sessions": list(item)} for item in escenari.items
    ]
    gen.get_durada_per_sessio_key = lambda *_: 1
    gen._get_hores_ocupades = lambda hora, *_: [hora]
    gen.analitzar_disponibilitat_sessio = lambda *_, **__: {}

    def cost_dels_professors(**k):
        comptats = escenari.professors.get((k["sessio"]["nom"], f"{k['data_iso']}_{k['hora']}"), {})
        nous = {clau: punts for clau, punts in comptats.items() if clau not in k["ja_comptats"]}
        return {"cost_total": sum(nous.values()), "costos_professors": nous}

    monkeypatch.setattr(bt, "calcular_cost_slot", cost_dels_professors)
    if not poda:
        gen._poda_valida = lambda _cost: False
    return gen


def resol(gen, llavor=1, shuffle_top_n=0):
    """(cost, nodes explorats) de la cerca d'una llavor, sense cap tall."""
    nodes = []
    cerca_real = gen._cerca

    def arrel(cerca, *args):
        nodes.append(cerca)
        return cerca_real(cerca, *args)

    gen._cerca = arrel
    solucions = gen._backtrack_with_seed(llavor, list(DIES), 10_000_000, shuffle_top_n)
    gen._cerca = cerca_real
    assert not nodes[0].tallada_per_nodes
    gen.on_va = {s["nom"]: clau for clau, its in solucions[0][1].items() for it in its for s in it["item"]["sessions"]}
    return solucions[0][0], nodes[0].nodes


def escenari_a_l_atzar(llavor: int) -> Escenari:
    """Sis exàmens de tres nivells en quatre franges, amb una mica de tot:
    preferències que bonifiquen o penalitzen, grups de «no al mateix moment» i
    de «no el mateix dia» que es trepitgen amb forces diferents, «mateix dia i
    hora», un límit per professor, un dia exclòs, professors compartits, dos
    exàmens que van junts (un sol ítem) i grups que anomenen l'assignatura
    sense el nivell («A» és la de 1r i la de 2n)."""
    rng = random.Random(llavor)
    professors_centre = ["Prof 1", "Prof 2", "Prof 3"]
    sessions = [
        sessio(nom, curs, rng.choice(professors_centre))
        for nom, curs in [
            ("A", "1-ESO"),
            ("B", "1-ESO"),
            ("A", "2-ESO"),
            ("C", "2-ESO"),
            ("D", "3-ESO"),
            ("E", "3-ESO"),
        ]
    ]
    noms = [s["nom"] for s in sessions] + ["A"]
    # El que costa cada professor a cada franja (si hi vigila dos exàmens
    # alhora, compta una sola vegada)
    costa = {
        (professor, clau): rng.choice([10, 40, 70])
        for professor in professors_centre
        for clau in FRANGES
        if rng.random() < 0.6
    }
    professors = {}
    for s in sessions:
        titular = s["examens"][0]["titular"]
        for clau in FRANGES:
            if (titular, clau) in costa:
                professors[(s["nom"], clau)] = {("substitucio", titular, clau.split("_")[1]): costa[(titular, clau)]}

    def grup(mida):
        return rng.sample(noms, mida)

    def tria(opcions):
        return rng.choice(opcions)

    restriccions = {
        "restriccions_dures": {
            "no_mateix_slot": {
                "G1": grup(3),
                "_pes_G1": tria([20, 50]),
                "G2": grup(3),
                "_pes_G2": tria([60, 90]),
            },
            "no_mateix_dia": [
                {"assignatures": grup(3), "pes": tria([30, 40])},
                {"assignatures": grup(3), "pes": tria([70, 80])},
            ],
            "professors_limit_dies_especifics": {
                "Prof 1": {
                    "assignatures": grup(4),
                    "dies_restringits": [tria(DIES)],
                    "max_examens": tria([0, 1]),
                    "pes_penalitzacio": tria([20, 60]),
                }
            },
            "assignatures_dies_exclosos": [{"assignatures": grup(1), "dies": [tria(DIES)], "pes": tria([10, 30])}],
        },
        "preferencies": {
            "mateix_dia": [{"assignatures": grup(tria([2, 3])), "pes": tria([30, 80])}],
            "dies_diferents": [{"assignatures": grup(tria([2, 3])), "pes": tria([40, 70])}],
            "mateix_slot": [{"assignatures": grup(2), "pes": tria([10, 50])}],
        },
        "pesos_optimitzacio": {
            "restriccio_dura": 1000,
            # El signe decideix si la preferència bonifica (punts negatius) o penalitza
            "preferencia_mateix_dia": tria([300, -300]),
            "preferencia_dies_diferents": tria([500, -500]),
        },
    }
    return Escenari(sessions, professors, restriccions, junts=[("D (3-ESO)", "E (3-ESO)")])


ESCENARIS = range(1, 25)


@pytest.mark.parametrize("llavor", ESCENARIS)
def test_la_cerca_sense_tall_dona_el_cost_minim_de_la_forca_bruta(monkeypatch, llavor):
    escenari = escenari_a_l_atzar(llavor)
    minim = escenari.minim_per_forca_bruta()
    cost, nodes = resol(crea_motor(monkeypatch, escenari), llavor=llavor)
    assert cost == minim
    # Sense poda, el mateix cost amb més feina (o la mateixa)
    cost_sense, nodes_sense = resol(crea_motor(monkeypatch, escenari, poda=False), llavor=llavor)
    assert cost_sense == minim
    assert nodes <= nodes_sense
    # I amb la barreja de les millors franges, també
    assert resol(crea_motor(monkeypatch, escenari), llavor=llavor, shuffle_top_n=3)[0] == minim


@pytest.mark.parametrize("llavor", ESCENARIS)
def test_el_cost_de_la_cerca_es_el_final_i_la_fita_no_el_supera_mai(monkeypatch, llavor):
    """Sense poda la cerca passa per tots els horaris complets: a cadascun, el
    cost que hi porta (sumat pas a pas) és el cost final calculat de cop, i cap
    fita del camí no el supera."""
    escenari = escenari_a_l_atzar(llavor)
    gen = crea_motor(monkeypatch, escenari, poda=False)
    resol(gen, llavor=llavor)
    assert len(gen.fulles) > 100
    for cost, on_va, fites, _ in gen.fulles:
        assert cost == escenari.cost(on_va), on_va
        assert max(fites) <= cost, (on_va, fites)


def test_els_escenaris_fan_baixar_el_cost_en_afegir_examens(monkeypatch):
    """Si el cost a mig fer no baixés mai, la fita no caldria: en aquests
    escenaris baixa (per bonificacions i per la regla de «la primera que
    s'incompleix»), i podar amb el cost a mig fer hauria estat un error."""
    baixades = 0
    for llavor in ESCENARIS:
        gen = crea_motor(monkeypatch, escenari_a_l_atzar(llavor), poda=False)
        resol(gen, llavor=llavor)
        baixades += any(max(costos) > cost for cost, _, _, costos in gen.fulles)
    assert baixades >= 10


def _dos_examens(pes_mateix_dia):
    a, b = sessio("A", "1-ESO", "Prof 1"), sessio("B", "2-ESO", "Prof 2")
    professors = {
        ("A (1-ESO)", "2026-04-21_08:00"): {("substitucio", "Prof 1", "08:00"): 50},
        ("A (1-ESO)", "2026-04-21_09:00"): {("substitucio", "Prof 1", "09:00"): 50},
        ("B (2-ESO)", "2026-04-20_08:00"): {("substitucio", "Prof 2", "08:00"): 100},
        ("B (2-ESO)", "2026-04-20_09:00"): {("substitucio", "Prof 2", "09:00"): 100},
    }
    restriccions = {
        "preferencies": {"mateix_dia": [{"assignatures": ["A (1-ESO)", "B (2-ESO)"], "pes": 40}]},
        "pesos_optimitzacio": {"preferencia_mateix_dia": pes_mateix_dia},
    }
    return Escenari([a, b], professors, restriccions)


def test_una_bonificacio_fa_triar_una_franja_mes_cara(monkeypatch):
    """«Mateix dia» amb pes positiu bonifica coincidir: 120 punts a cada
    examen. Sense la preferència cada examen aniria al seu dia barat (cost 0);
    amb ella, tots dos dimarts (50 de substitució − 240 de bonificació)."""
    escenari = _dos_examens(pes_mateix_dia=300)
    assert escenari.minim_per_forca_bruta() == -190
    gen = crea_motor(monkeypatch, escenari)
    assert resol(gen)[0] == -190
    assert {clau.split("_")[0] for clau in gen.on_va.values()} == {"2026-04-21"}


def test_amb_pes_negatiu_la_mateixa_preferencia_penalitza(monkeypatch):
    escenari = _dos_examens(pes_mateix_dia=-300)
    assert escenari.minim_per_forca_bruta() == 0
    assert resol(crea_motor(monkeypatch, escenari))[0] == 0


def test_el_limit_per_professor_compta_l_excedent(monkeypatch):
    """Tres exàmens del mateix professor en un dia amb màxim 1: dos de més,
    2 × 30 % de 1000. Abans la cerca hi sumava 1 + 2 + 3 excedents (i un altre
    per examen a la preparació)."""
    sessions = [sessio(nom, curs, "Prof 1") for nom, curs in [("A", "1-ESO"), ("B", "2-ESO"), ("C", "3-ESO")]]
    restriccions = {
        "restriccions_dures": {
            "professors_limit_dies_especifics": {
                "Prof 1": {
                    "assignatures": [s["nom"] for s in sessions],
                    "dies_restringits": ["Dilluns", "Dimarts"],
                    "max_examens": 1,
                    "pes_penalitzacio": 30,
                }
            }
        },
        "pesos_optimitzacio": {"restriccio_dura": 1000},
    }
    escenari = Escenari(sessions, {}, restriccions)
    assert escenari.minim_per_forca_bruta() == 600
    assert resol(crea_motor(monkeypatch, escenari))[0] == 600


def test_amb_un_pes_negatiu_la_cerca_no_poda(monkeypatch):
    """Amb el pes de les restriccions negatiu la fita no val: la cerca passa
    per tots els horaris i continua donant el mínim."""
    escenari = escenari_a_l_atzar(3)
    escenari.restriccions["pesos_optimitzacio"]["restriccio_dura"] = -1000
    gen = crea_motor(monkeypatch, escenari)
    cost, nodes = resol(gen, llavor=3)
    assert cost == escenari.minim_per_forca_bruta()
    assert nodes == resol(crea_motor(monkeypatch, escenari, poda=False), llavor=3)[1]


@pytest.mark.parametrize("llavor", [1, 2, 3])
def test_un_examen_que_no_depen_dels_altres_no_es_torna_a_calcular(monkeypatch, llavor):
    """Sense restriccions entre exàmens, el cost de restriccions de cada examen
    és fix per franja (aquí, un dia exclòs): la cerca no demana les incidències
    de cap dia a mig fer."""
    escenari = escenari_a_l_atzar(llavor)
    exclos = escenari.restriccions["restriccions_dures"]["assignatures_dies_exclosos"]
    escenari.restriccions = {
        "restriccions_dures": {"assignatures_dies_exclosos": exclos},
        "pesos_optimitzacio": {"restriccio_dura": 1000},
    }
    gen = crea_motor(monkeypatch, escenari)
    dies_calculats = []
    real = bt.CostDeLaCerca._calcula_dia
    monkeypatch.setattr(bt.CostDeLaCerca, "_calcula_dia", lambda *a: dies_calculats.append(a) or real(*a))
    assert resol(gen, llavor=llavor)[0] == escenari.minim_per_forca_bruta()
    # Només el de cada ítem tot sol a cada franja (per ordenar la cerca), i dona zero
    assert len(dies_calculats) == len(escenari.items) * len(FRANGES)
