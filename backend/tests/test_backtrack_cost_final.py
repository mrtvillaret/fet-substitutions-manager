"""El backtracking minimitza el cost final que es mostra.

Abans la cerca sumava un cost propi (sense les preferències «mateix dia» i
«dies diferents» ni el «no el mateix dia» no obligatori, i amb el límit per
professor acumulat): podia acabar sense tall amb un horari més car que el dels
altres motors. Ara una cerca sense tall dona el cost mínim, i aquí es comprova
per força bruta: totes les col·locacions possibles, puntuades amb les funcions
del cost final (`avaluador.incidencies_restriccions`).

La poda fa servir una fita inferior, perquè el cost d'un horari a mig fer pot
baixar en afegir-hi exàmens (bonificacions, i les regles que valen «la primera
que s'incompleix»). Es comprova de dues maneres: amb poda i sense, el mateix
cost; i a cada camí de la cerca sense poda, la fita de cada pas no supera mai
el cost de l'horari complet on acaba.

El motor és el real (`planificador/motor/estrategies/backtracking.py`); se'n
substitueixen l'anàlisi i el cost dels professors de cada franja (taules fixes).
Escenaris a l'atzar amb llavor fixa. La força bruta, les fites, la poda i la
baixada del cost dels 24 escenaris són a `test_planificador_backtracking_nou.py`,
que fa servir aquests mateixos escenaris i ajudants.
"""

import itertools
import random
from copy import deepcopy
from dataclasses import replace

import pytest
from suport_motor_nou import config_inventada as config_inventada
from suport_motor_nou import problema_inventat
from suport_motor_nou import xml_inventat as xml_inventat

from planificador.compartit.franja import franja
from planificador.motor.avaluador import incidencies_restriccions
from planificador.motor.compatibilitat import BACKTRACKING
from planificador.motor.cost_cerca import CostCercaBacktracking
from planificador.motor.estrategies import backtracking as bt
from planificador.motor.estrategies.base import Pressupost
from planificador.motor.model import Examen, congela
from planificador.motor.regles import construeix_regles

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


class Rellotge:
    def __init__(self, tic=0):
        self.consultes = 0
        self.tic = tic

    def __call__(self):
        valor = self.consultes * self.tic
        self.consultes += 1
        return valor


def problema_escenari(base, escenari):
    sessions = [dict(s, id=f"examen_{i}") for i, s in enumerate(escenari.sessions)]
    regles = deepcopy(escenari.restriccions)
    if any(len(it) > 1 for it in escenari.items):
        regles.setdefault("restriccions_dures", {})["mateix_slot"] = [
            {"assignatures": [s["nom"] for s in it]} for it in escenari.items if len(it) > 1
        ]
    return replace(
        base,
        examens=tuple(Examen(s["id"], s["nom"], s["nom_base"], s["curs"], 1, 1, congela(s)) for s in sessions),
        franges=tuple(franja(f"{d}_{h}") for d in DATES for h in HORES),
        graella=tuple(HORES),
        hores_inici=tuple(HORES),
        nivells=tuple(sorted({s["curs"] for s in sessions})),
        dies=tuple(DIES),
        dates=(),
        mapa_dies=congela({}),
        regles=construeix_regles(regles),
    )


class MotorComprovat(bt.Backtracking):
    def __init__(self, poda=True):
        self.amb_poda = poda
        self.fulles, self.cami_fites, self.cami_costos, self.cerques = [], [], [], []

    def _poda_valida(self, cost):
        return self.amb_poda and super()._poda_valida(cost)

    def _cerca(self, cerca, idx, cost_ac, fita_ac):
        if idx == 0:
            self.cerques.append(cerca)
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


def prepara_nou(monkeypatch, escenari):
    monkeypatch.setattr(bt.Backtracking, "_analitza", lambda *_: {})

    def cost_professors(**k):
        comptats = escenari.professors.get((k["sessio"]["nom"], f"{k['data_iso']}_{k['hora']}"), {})
        nous = {clau: punts for clau, punts in comptats.items() if clau not in k["ja_comptats"]}
        return {"cost_total": sum(nous.values()), "costos_professors": nous}

    monkeypatch.setattr(bt, "cost_sessio", cost_professors)


def cerca_nou(problema, llavor=1, poda=True, tic=0, **parametres):
    motor = MotorComprovat(poda)
    rellotge = Rellotge(tic)
    resultat = motor.cerca(
        problema,
        BACKTRACKING,
        CostCercaBacktracking(problema),
        parametres,
        Pressupost(20, rellotge),
        random.Random(llavor),
    )
    return resultat, motor, rellotge


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


def resol(monkeypatch, config, xml, escenari, llavor=1, poda=True, **parametres):
    """La cerca nova d'una llavor sobre l'escenari, sense cap tall: (resultat, motor)."""
    problema = problema_escenari(problema_inventat(config, xml), escenari)
    prepara_nou(monkeypatch, escenari)
    resultat, motor, _ = cerca_nou(problema, llavor, poda, **parametres)
    assert resultat.complet and resultat.motiu_aturada is None
    return resultat, motor


def test_una_bonificacio_fa_triar_una_franja_mes_cara(monkeypatch, config_inventada, xml_inventat):
    """«Mateix dia» amb pes positiu bonifica coincidir: 120 punts a cada
    examen. Sense la preferència cada examen aniria al seu dia barat (cost 0);
    amb ella, tots dos dimarts (50 de substitució − 240 de bonificació)."""
    escenari = _dos_examens(pes_mateix_dia=300)
    assert escenari.minim_per_forca_bruta() == -190
    resultat, _ = resol(monkeypatch, config_inventada, xml_inventat, escenari)
    assert resultat.cost == -190
    assert {f.clau.split("_")[0] for f in resultat.assignacio.values()} == {"2026-04-21"}


def test_amb_pes_negatiu_la_mateixa_preferencia_penalitza(monkeypatch, config_inventada, xml_inventat):
    escenari = _dos_examens(pes_mateix_dia=-300)
    assert escenari.minim_per_forca_bruta() == 0
    assert resol(monkeypatch, config_inventada, xml_inventat, escenari)[0].cost == 0


def test_el_limit_per_professor_compta_l_excedent(monkeypatch, config_inventada, xml_inventat):
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
    assert resol(monkeypatch, config_inventada, xml_inventat, escenari)[0].cost == 600


@pytest.mark.parametrize("llavor", [1, 2, 3])
def test_un_examen_que_no_depen_dels_altres_no_es_torna_a_calcular(monkeypatch, config_inventada, xml_inventat, llavor):
    """Sense restriccions entre exàmens, el cost de restriccions de cada examen
    és fix per franja (aquí, un dia exclòs): la cerca no demana les incidències
    de cap dia a mig fer."""
    escenari = escenari_a_l_atzar(llavor)
    exclos = escenari.restriccions["restriccions_dures"]["assignatures_dies_exclosos"]
    escenari.restriccions = {
        "restriccions_dures": {"assignatures_dies_exclosos": exclos},
        "pesos_optimitzacio": {"restriccio_dura": 1000},
    }
    dies_calculats = []
    real = CostCercaBacktracking._calcula_dia
    monkeypatch.setattr(CostCercaBacktracking, "_calcula_dia", lambda *a: dies_calculats.append(a) or real(*a))
    resultat, _ = resol(monkeypatch, config_inventada, xml_inventat, escenari, llavor=llavor)
    assert resultat.cost == escenari.minim_per_forca_bruta()
    # Només el de cada ítem tot sol a cada franja (per ordenar la cerca), i dona zero
    assert len(dies_calculats) == len(escenari.items) * len(FRANGES)
