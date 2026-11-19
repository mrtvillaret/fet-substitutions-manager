"""
Costos de cerca propis de greedy, backtracking i recuit.

El greedy conserva el cost de col·locació i tria l'intent pel cost mostrat.
El recuit conserva el cost per sessió i dia i el delta incremental desfasat.
La resta d'aquesta introducció descriu les fites del backtracking.

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

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from typing import NamedTuple

from planificador.compartit.franja import Franja
from planificador.compartit.normalitzacio import normalitzar_dia, normalitzar_text
from planificador.compartit.punts import pes_restriccio_dura, pes_restriccio_violada
from planificador.motor.avaluador import (
    causa_dura,
    clau_de_data,
    cost,
    cost_sessio,
    costos_professors_no_negatius,
    incidencies_restriccions_dia,
    supera_tall,
)
from planificador.motor.compatibilitat import BASE_MATEIX_MOMENT, COST_PROHIBITIU, COST_ZONA_EXAMEN
from planificador.motor.disponibilitat import Disponibilitat, analitza_motor
from planificador.motor.durades import hores_ocupades, vigilancia
from planificador.motor.model import descongela
from planificador.motor.regles import (
    _punts_percentatge,
    calcular_penalitzacio_professors_dies_item,
    calcular_penalitzacio_total_professors,
    compta_per_algun_limit,
    es_item_compatible_amb_slot,
    percentatge_preferencia_mateix_slot,
)
from textos import normalitzar_hora


class CostCercaGreedy:
    """Cost de col·locació propi del greedy i cost mostrat per triar l'intent.

    Les sessions ja col·locades a la franja conserven la projecció embolcallada
    del motor antic: les regles que hi busquen nom_base no el troben.
    El +5 de zona d'examen tampoc forma part del cost que tria l'intent.
    """

    def __init__(self, problema):
        self.problema = problema
        self.restriccions = problema.regles.a_diccionari()
        self.disponibilitat = Disponibilitat(problema)
        self._franges_dures = {
            f.clau: replace(f, data_iso=f.prefix if re.match(r"^\d{4}-\d{2}-\d{2}$", f.prefix) else None)
            for f in problema.franges
        }

    def sessio(self, sessio, ubicacio, sessions_dia, sessions_franja, comptats):
        analisi = analitza_motor(self.problema, self.disponibilitat, sessio, ubicacio, sessions_franja, copia=False)
        resultat = cost_sessio(
            sessio,
            ubicacio.dia,
            ubicacio.hora,
            analisi,
            self.restriccions,
            sessions_dia,
            sessions_franja,
            inclou_limit_dies=False,
            data_iso=ubicacio.data_iso or "",
            ja_comptats=comptats,
        )
        zona = {(i["professor"], i.get("hora", ubicacio.hora)) for i in analisi.get("zona_examen", [])}
        return resultat["cost_total"] + COST_ZONA_EXAMEN * len(zona)

    def item(
        self, item, ubicacio, sessions_dia, sessions_franja, sessions_per_dia, ubicacions, ja_comptats, politiques
    ):
        if not es_item_compatible_amb_slot(item, sessions_franja, self.restriccions)[0]:
            return None
        punts, comptats = 0, set(ja_comptats)
        # Com al comprovador antic, només el prefix ISO amb zeros és una data.
        franja_dura = self._franges_dures[ubicacio.clau]
        for sessio in item["sessions"]:
            if causa_dura(
                sessio,
                franja_dura,
                self.problema.regles,
                self.problema.nivells,
                sessions_dia,
                sessions_franja,
                sessions_per_dia,
                politiques=politiques,
                restriccions=self.restriccions,
            ):
                return None
            cost_individual = self.sessio(sessio, ubicacio, sessions_dia, sessions_franja, comptats)
            if supera_tall(cost_individual):
                return None
            punts += cost_individual
            percent = percentatge_preferencia_mateix_slot(sessio, ubicacio.clau, ubicacions, self.restriccions)
            if percent >= 100:
                return None
            punts += _punts_percentatge(BASE_MATEIX_MOMENT, percent)
        punts += calcular_penalitzacio_professors_dies_item(item, ubicacio.dia, sessions_per_dia, self.restriccions)
        return punts, comptats

    def intent(self, horari):
        # La graella i l'XML són els de build_context del motor, no els de
        # la projecció posterior del servei HTTP (que normalitza l'XML).
        return cost(horari, self.problema, self.disponibilitat).a_info()


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


class CostCercaBacktracking:
    """Cost de restriccions, preferències i límits per professor de qualsevol
    col·locació parcial dels ítems preparats.

    Una col·locació es descriu amb conjunts de (franja, ítem): els resultats es
    desen per conjunt, perquè la cerca torna moltes vegades al mateix dia amb
    els mateixos exàmens."""

    def __init__(self, problema):
        self.problema = problema
        self._restriccions = problema.regles.a_diccionari()
        self._dia_a_data_iso = descongela(problema.mapa_dies)

    def prepara(self, items_info, franges, comprova_termini=lambda: None):
        """Prepara les fites una sola vegada per a totes les llavors."""
        restriccions = self._restriccions
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

        return self

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


@dataclass
class SolucioRecuit:
    """Estat mutable de cerca; els costos desats poden quedar desfasats."""

    assignacions: dict
    cost: float = 0.0
    violacions: list[dict] = field(default_factory=list)
    cost_per_franja: dict[str, float] = field(default_factory=dict)
    cost_global: float = 0.0


class CostCercaRecuit:
    """Cost propi per sessió i dia, amb delta només a origen i destí.

    L'ordre del conjunt de franges afectades també es conserva: canviar la
    suma incremental pot alterar els decimals i la trajectòria del recuit.
    """

    def __init__(self, problema):
        self.problema = problema
        self.restriccions = problema.regles.a_diccionari()
        self.disponibilitat = Disponibilitat(problema)
        self.franges = {f.clau: f for f in problema.franges}
        self.preferencies = self.restriccions.get("preferencies", {}).get("mateix_slot", [])
        self.estrictes = self.restriccions.get("restriccions_dures", {}).get("professors_horari_estricte", [])

    def prepara(self, items, politiques):
        self.items, self.politiques = items, politiques
        self.per_id = {it.id: it for it in items}
        # Com al motor antic: la projecció de sessió és única per id i es comparteix
        # entre franges, límits i agrupacions. Els ítems homònims es trepitgen.
        self.examens = {e.id: e.a_diccionari() for it in items for e in it.examens}

    def precomputa(self, solucio, exclou):
        per_franja, per_dia = defaultdict(list), defaultdict(list)
        for identificador, franja in solucio.assignacions.items():
            if identificador == exclou:
                continue
            for examen in self.per_id[identificador].examens:
                sessio = self.examens[examen.id]
                per_franja[franja.clau].append({"sessio": sessio})
                per_dia[franja.data_iso or normalitzar_dia(franja.dia)].append(sessio)
        return per_franja, per_dia

    def compatible(self, solucio, item, franja, precalcul=None):
        if precalcul is not None:
            per_franja, per_dia = precalcul
            simultanies = per_franja.get(franja.clau, [])
            del_dia = per_dia.get(franja.data_iso or normalitzar_dia(franja.dia), [])
        else:
            # El motor antic posa les sessions de la franja al final del dia quan
            # no rep taules precomputades; les altres mantenen l'ordre d'alta.
            simultanies, del_dia, per_dia = [], [], defaultdict(list)
            clau_dia = franja.data_iso or normalitzar_dia(franja.dia)
            for identificador, altra in solucio.assignacions.items():
                if identificador == item.id:
                    continue
                sessions = [self.examens[e.id] for e in self.per_id[identificador].examens]
                if altra.clau == franja.clau:
                    simultanies.extend({"sessio": s} for s in sessions)
                else:
                    dia_altra = altra.data_iso or normalitzar_dia(altra.dia)
                    if dia_altra == clau_dia:
                        del_dia.extend(sessions)
                    per_dia[dia_altra].extend(sessions)
            for entrada in simultanies:
                del_dia.append(entrada["sessio"])
                per_dia[clau_dia].append(entrada["sessio"])
        sessions = [self.examens[e.id] for e in item.examens]
        if not es_item_compatible_amb_slot({"sessions": sessions}, simultanies, self.restriccions)[0]:
            return False
        for sessio in sessions:
            analisi = None
            if self.estrictes:
                # La comprovació dura només mira les hores de vigilància.
                hores = hores_ocupades(
                    normalitzar_hora(franja.hora),
                    tuple(dict.fromkeys(normalitzar_hora(h) for h in self.problema.graella)),
                    vigilancia(sessio.get("nom"), self.problema.durades_vigilancia, self.problema.durada_titular),
                )
                dates = self.problema.mapa_dies.get(normalitzar_dia(franja.dia))
                data_iso = franja.data_iso or (dates[0] if isinstance(dates, (tuple, list)) else dates)
                analisi = self.disponibilitat.consulta(
                    sessio, franja.dia, franja.hora, data_iso, hores, hores, simultanies
                )
            if causa_dura(
                sessio,
                franja,
                self.problema.regles,
                self.problema.nivells,
                del_dia,
                [s["sessio"] for s in simultanies],
                per_dia,
                analisi,
                self.politiques,
                restriccions=self.restriccions,
            ):
                return False
        return True

    def causa_infactible(self, item):
        raons = Counter()
        for franja in self.problema.franges:
            for examen in item.examens:
                causa = causa_dura(
                    self.examens[examen.id],
                    franja,
                    self.problema.regles,
                    self.problema.nivells,
                    [],
                    [],
                    {},
                    politiques=self.politiques,
                    restriccions=self.restriccions,
                )
                if causa:
                    raons[causa.clau] += 1
                    break
        altres = Counter({clau: n for clau, n in raons.items() if clau != "examen_fixat"})
        return (altres or raons).most_common(1)[0][0] if raons else None

    def franja(self, clau, items, per_dia):
        if not items:
            return 0.0, []
        ubicacio = self.franges[clau]
        dates = self.problema.mapa_dies.get(normalitzar_dia(ubicacio.prefix))
        data_iso = ubicacio.data_iso
        if data_iso is None:
            data_iso = dates[0] if isinstance(dates, (tuple, list)) else dates
        del_dia = per_dia.get(data_iso or normalitzar_dia(ubicacio.dia), [])
        sessions = [self.examens[e.id] for it in items for e in it.examens]
        punts, violacions, comptats = 0.0, [], set()
        for sessio in sessions:
            altres = [s for s in sessions if s is not sessio]
            analisi = analitza_motor(self.problema, self.disponibilitat, sessio, ubicacio, altres, copia=False)
            resultat = cost_sessio(
                sessio,
                ubicacio.dia,
                ubicacio.hora,
                analisi,
                self.restriccions,
                del_dia,
                altres,
                data_iso=data_iso,
                ja_comptats=comptats,
            )
            punts += resultat.get("cost_total", 0)
            zona = {(i["professor"], i.get("hora", ubicacio.hora)) for i in analisi.get("zona_examen", [])}
            punts += len(zona) * COST_ZONA_EXAMEN
            for professor in resultat.get("professors_estrictes_violats", []):
                violacions.append(
                    {
                        "tipus": "professor_estricte",
                        "pes": resultat.get("cost_total", 0),
                        "missatge": f"{professor} horari estricte violat",
                    }
                )
        return punts, violacions

    def global_mateix_moment(self, solucio):
        punts, violacions = 0.0, []
        for preferencia in self.preferencies:
            pes = preferencia.get("pes", 75) if isinstance(preferencia, dict) else 75
            noms = preferencia.get("assignatures", []) if isinstance(preferencia, dict) else preferencia
            normalitzats = {normalitzar_text(n) for n in noms}
            franges = set()
            for item in self.items:
                if any(
                    normalitzar_text(e.nom) in normalitzats or normalitzar_text(e.nom_base) in normalitzats
                    for e in item.examens
                ):
                    if item.id in solucio.assignacions:
                        franges.add(solucio.assignacions[item.id].clau)
            if len(franges) > 1:
                cost = float(COST_PROHIBITIU if pes >= 100 else _punts_percentatge(BASE_MATEIX_MOMENT, pes))
                punts += cost * (len(franges) - 1)
                violacions.append({"tipus": "pref_mateix_slot", "pes": pes, "missatge": f"Slots separats: {noms}"})
        return punts, violacions

    def _agrupa(self, assignacions, afectades=None):
        per_franja, per_dia = defaultdict(list), defaultdict(list)
        for identificador, franja in assignacions.items():
            item = self.per_id[identificador]
            if afectades is None or franja.clau in afectades:
                per_franja[franja.clau].append(item)
            per_dia[franja.data_iso or normalitzar_dia(franja.dia)].extend(self.examens[e.id] for e in item.examens)
        return per_franja, per_dia

    def total(self, solucio):
        punts, violacions = 0.0, []
        solucio.cost_per_franja = {}
        per_franja, per_dia = self._agrupa(solucio.assignacions)
        for clau, items in per_franja.items():
            cost, incidencies = self.franja(clau, items, per_dia)
            solucio.cost_per_franja[clau] = cost
            punts += cost
            violacions.extend(incidencies)
        solucio.cost_global, incidencies = self.global_mateix_moment(solucio)
        punts += solucio.cost_global
        violacions.extend(incidencies)
        return punts, violacions

    def delta(self, anterior, nova, afectades):
        if afectades:
            per_franja, per_dia = self._agrupa(nova.assignacions, afectades)
            # No s'ordena: el motor antic recorria aquest mateix conjunt de claus.
            for clau in afectades:
                antic = nova.cost_per_franja.get(clau, 0.0)
                cost, violacions = self.franja(clau, per_franja.get(clau, []), per_dia)
                nova.cost_per_franja[clau] = cost
                nova.cost = nova.cost - antic + cost
                nova.violacions.extend(violacions)
            antic = nova.cost_global
            nova.cost_global, violacions = self.global_mateix_moment(nova)
            nova.violacions.extend(violacions)
            nova.cost = nova.cost - antic + nova.cost_global
        else:
            nova.violacions = list(anterior.violacions)
        return nova
