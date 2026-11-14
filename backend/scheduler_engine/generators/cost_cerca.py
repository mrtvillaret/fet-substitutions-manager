"""
El cost de restriccions i preferències d'un horari a mig fer, per a la cerca
del backtracking.

La cerca ha de minimitzar el mateix cost que després es mostra: per això aquí
no hi ha cap fórmula de punts. Tot surt de les incidències del cost final
(`estadistiques.incidencies_restriccions_dia`, dia a dia) i del límit
d'exàmens per professor (`constraints.calcular_penalitzacio_total_professors`).
El cost dels professors (substitucions, esperes...) el porta la cerca mateixa,
per franja.

Dues coses més, totes dues tretes de preguntar a aquestes mateixes funcions:

- Què no cal tornar a calcular. Un examen «independent» costa el mateix
  hi hagi qui hi hagi el mateix dia o a la mateixa franja (es comprova
  posant-lo sol i amb tots els altres); el seu cost és fix per franja. Només
  els exàmens que depenen dels altres es tornen a calcular quan canvia el seu dia.

- La fita inferior per podar. El cost d'un horari a mig fer pot baixar en
  afegir-hi exàmens per dos motius, i la fita els descompta tots dos:
    1. Les bonificacions (punts negatius: «mateix dia» amb pes positiu, «dies
       diferents» amb pes negatiu). Cada examen en pot rebre, com a molt, la
       que rebria amb cada company tot sol; la suma del que encara poden
       aportar els exàmens pendents (`pendent`) es resta del cost.
    2. «No al mateix moment» i «no el mateix dia» valen el percentatge de la
       primera regla que s'incompleix: si un examen és a dues regles amb forces
       diferents, un company nou pot canviar quina és la primera. A la fita
       cada una compta pel mínim que pot valer per a aquell examen (`_terra`).
  La resta del cost no baixa mai si els pesos no són negatius (`poda_valida`).
"""

from collections import defaultdict
from typing import NamedTuple

from scheduler_engine.core.constraints import calcular_penalitzacio_total_professors, compta_per_algun_limit
from scheduler_engine.core.franja import Franja
from scheduler_engine.core.punts import pes_restriccio_dura, pes_restriccio_violada
from scheduler_engine.core.scoring import costos_professors_no_negatius
from scheduler_engine.estadistiques import clau_de_data, incidencies_restriccions_dia

# Valen el percentatge de la primera regla incomplerta (`violacio_no_mateix_slot`
# i `violacio_no_mateix_dia`): l'única part positiva del cost que pot baixar
CONCEPTES_PRIMERA_REGLA = ("no_mateix_slot", "no_mateix_dia")


class CostFita(NamedTuple):
    """El cost d'una part de l'horari i el mínim que valdrà quan s'hi afegeixin
    exàmens, sense comptar les bonificacions noves (`pendent`)."""

    cost: int = 0
    fita: int = 0


ZERO = CostFita()
_BUIT = frozenset()
# Sostre dels resultats desats (dies i límits): passat, es torna a començar
MAX_DIES_DESATS = 200_000


class CostDeLaCerca:
    """Cost de restriccions, preferències i límits per professor de qualsevol
    col·locació parcial dels ítems preparats.

    Una col·locació es descriu amb conjunts de (franja, ítem): els resultats es
    desen per conjunt, perquè la cerca torna moltes vegades al mateix dia amb
    els mateixos exàmens."""

    def __init__(
        self,
        restriccions: dict,
        dia_a_data_iso: dict | None,
        items_info: list[dict],
        franges: list[Franja],
        comprova_termini=lambda: None,
    ):
        self._restriccions = restriccions
        self._dia_a_data_iso = dia_a_data_iso
        self._franges = {franja.clau: franja for franja in franges}
        self._sessions = {it["id"]: it["item"]["sessions"] for it in items_info}
        self._comprova_termini = comprova_termini
        self._dies: dict[frozenset, CostFita] = {_BUIT: ZERO}
        self._limits: dict[frozenset, int] = {_BUIT: 0}
        self._fixos: dict[tuple[int, str], int] = {}
        self.poda_valida = (
            pes_restriccio_dura(restriccions) >= 0
            and pes_restriccio_violada(restriccions) >= 0
            and costos_professors_no_negatius(restriccions)
        )
        self._terra: dict[tuple[str, str, str], int] = {}
        self._regals: dict[tuple[int, int], int] = defaultdict(int)  # (ítem que arriba, ítem que la rep) → punts
        self._dependents: set[int] = set()
        if franges:
            self._classifica(franges[0])
        self.depen = {
            item: any(id(s) in self._dependents for s in sessions) for item, sessions in self._sessions.items()
        }
        self.compta_limit = {
            item: any(compta_per_algun_limit(s, restriccions) for s in sessions)
            for item, sessions in self._sessions.items()
        }

    # ------------------------------------------------------------------
    # Preparació: què depèn de què
    # ------------------------------------------------------------------

    def _incidencies(self, franja: Franja, de_la_franja: list[dict], del_dia: list[dict], nomes=None) -> list:
        """Les incidències del cost final d'una franja d'un dia, amb `del_dia`
        com a exàmens d'aquella data."""
        dia = self._dia(franja, {franja.hora: de_la_franja})
        return incidencies_restriccions_dia(
            dia, {clau_de_data(dia): del_dia}, self._restriccions, self._dia_a_data_iso, nomes
        )

    @staticmethod
    def _dia(franja: Franja, sessions_per_hora: dict[str, list[dict]]) -> dict:
        """Un dia amb la forma de l'horari final (com `_construir_horari_desde_slots`)."""
        dia = {
            "dia": franja.dia,
            "sessions": [{"hora": hora, "sessions_simultanees": ss} for hora, ss in sessions_per_hora.items()],
        }
        if franja.data_iso:
            dia["data"] = franja.data_iso
        return dia

    def _classifica(self, franja: Franja) -> None:
        """Quins exàmens depenen dels altres, quina bonificació pot aportar
        cada parella i el mínim de les regles de «la primera que s'incompleix».
        Les relacions entre exàmens no depenen del dia ni de l'hora: es
        pregunten totes a una mateixa franja."""
        items = [(item, s) for item, sessions in self._sessions.items() for s in sessions]
        totes = [s for _, s in items]

        def punts(sessio, de_la_franja, del_dia):
            self._comprova_termini()
            return sorted(
                (inc.concepte, inc.punts) for inc in self._incidencies(franja, de_la_franja, del_dia, {id(sessio)})
            )

        for item, sessio in items:
            sola = punts(sessio, [sessio], [sessio])
            amb_tothom = punts(sessio, totes, totes)
            amb_tothom_a_altres_hores = punts(sessio, [sessio], totes)
            if sola == amb_tothom == amb_tothom_a_altres_hores:
                continue
            self._dependents.add(id(sessio))
            rep = any(
                p < 0 or concepte in CONCEPTES_PRIMERA_REGLA for concepte, p in amb_tothom + amb_tothom_a_altres_hores
            )
            if not rep:
                continue
            bonificacio_sola = sum(p for _, p in sola if p < 0)
            clau = (sessio.get("nom", ""), sessio.get("curs", ""))
            for item_altra, altra in items:
                if altra is sessio:
                    continue
                parella = punts(sessio, [sessio, altra], [sessio, altra])
                regal = bonificacio_sola - sum(p for _, p in parella if p < 0)
                if regal > 0:
                    self._regals[(item_altra, item)] += regal
                for concepte, p in parella:
                    if concepte in CONCEPTES_PRIMERA_REGLA and p > 0:
                        anterior = self._terra.get((concepte, *clau), p)
                        self._terra[(concepte, *clau)] = min(anterior, p)

    # ------------------------------------------------------------------
    # Cost d'una col·locació
    # ------------------------------------------------------------------

    def fix(self, item: int, clau_franja: str) -> int:
        """El que costen, a la franja, els exàmens de l'ítem que no depenen de
        cap altre (dia o hora fixats, dies exclosos...)."""
        clau = (item, clau_franja)
        if clau not in self._fixos:
            franja = self._franges[clau_franja]
            self._fixos[clau] = sum(
                inc.punts
                for s in self._sessions[item]
                if id(s) not in self._dependents
                for inc in self._incidencies(franja, [s], [s])
            )
        return self._fixos[clau]

    def del_dia(self, collocats: frozenset) -> CostFita:
        """Cost i fita dels exàmens que depenen dels altres, en un dia amb
        aquests (franja, ítem) col·locats."""
        resultat = self._dies.get(collocats)
        if resultat is None:
            if len(self._dies) >= MAX_DIES_DESATS:
                self._dies = {_BUIT: ZERO}
            resultat = self._dies[collocats] = self._calcula_dia(collocats)
        return resultat

    def _calcula_dia(self, collocats: frozenset) -> CostFita:
        per_hora: dict[str, list[dict]] = {}
        franja = None
        for clau_franja, item in sorted(collocats):
            franja = self._franges[clau_franja]
            per_hora.setdefault(franja.hora, []).extend(self._sessions[item])
        del_dia = [s for sessions in per_hora.values() for s in sessions]
        nomes = {id(s) for s in del_dia if id(s) in self._dependents}
        if not nomes:
            return ZERO
        dia = self._dia(franja, per_hora)
        incidencies = incidencies_restriccions_dia(
            dia, {clau_de_data(dia): del_dia}, self._restriccions, self._dia_a_data_iso, nomes
        )
        cost = fita = 0
        for inc in incidencies:
            cost += inc.punts
            if inc.punts > 0 and inc.concepte in CONCEPTES_PRIMERA_REGLA:
                fita += min(inc.punts, self._terra.get((inc.concepte, inc.nom, inc.curs), 0))
            else:
                fita += inc.punts
        return CostFita(cost, fita)

    def limit(self, collocats: frozenset) -> int:
        """Els punts del límit d'exàmens per professor amb aquests (nom del
        dia, ítem) col·locats (només cal passar-hi els ítems de `compta_limit`)."""
        punts = self._limits.get(collocats)
        if punts is None:
            if len(self._limits) >= MAX_DIES_DESATS:
                self._limits = {_BUIT: 0}
            sessions_per_dia = defaultdict(list)
            for dia, item in sorted(collocats):
                sessions_per_dia[dia].extend(self._sessions[item])
            punts = self._limits[collocats] = calcular_penalitzacio_total_professors(
                sessions_per_dia, self._restriccions
            )
        return punts

    def sol(self, item: int, franja: Franja) -> int:
        """Restriccions, preferències i límits de l'ítem tot sol a la franja."""
        de_l_item = frozenset({(franja.clau, item)})
        limit = self.limit(frozenset({(franja.dia, item)})) if self.compta_limit[item] else 0
        return self.fix(item, franja.clau) + self.del_dia(de_l_item).cost + limit

    # ------------------------------------------------------------------
    # Fita: les bonificacions que encara poden arribar
    # ------------------------------------------------------------------

    def pendent(self, ordre: list[int]) -> list[int]:
        """pendent[i]: la bonificació màxima que encara pot arribar quan
        falten per col·locar els ítems `ordre[i:]`. La d'una parella es compta
        quan es col·loca el segon dels dos; pendent[len(ordre)] és 0."""
        posicio = {item: i for i, item in enumerate(ordre)}
        per_posicio = [0] * (len(ordre) + 1)
        for (arriba, rep), punts in self._regals.items():
            if arriba in posicio and rep in posicio:
                per_posicio[max(posicio[arriba], posicio[rep])] += punts
        for i in range(len(ordre) - 1, -1, -1):
            per_posicio[i] += per_posicio[i + 1]
        return per_posicio
