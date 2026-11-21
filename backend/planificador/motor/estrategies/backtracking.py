"""Backtracking: mateixa preparació, ordre, poda i consultes de rellotge."""

import random
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from itertools import groupby

from planificador.compartit.franja import Franja
from planificador.compartit.franja import franja as de_clau
from planificador.compartit.missatges import missatge
from planificador.motor.avaluador import causa_dura, cost_sessio
from planificador.motor.construccio import particio
from planificador.motor.cost_cerca import ZERO, CostCercaBacktracking, CostFita
from planificador.motor.disponibilitat import Disponibilitat, analitza_motor
from planificador.motor.durades import encavalca_amb_el_nivell, examen_hi_cap
from planificador.motor.estrategies.base import ResultatCerca, TempsEsgotat
from planificador.motor.model import descongela
from planificador.motor.regles import (
    es_item_compatible_amb_slot,
    percentatge_preferencia_mateix_slot,
    viola_restriccio_dura,
)


class _Dures:
    def __init__(self, problema, politiques):
        self.problema = problema
        self.politiques = politiques
        self.restriccions = problema.regles.a_diccionari()
        self._franges = {}

    def comprova(
        self, sessio, dia, hora, prefix, sessions_dia, sessions_slot, sessions_per_dia, sessions_per_data=None
    ):
        clau = f"{prefix}_{hora}"
        if clau not in self._franges:
            ubicacio = de_clau(clau)
            # Només el prefix amb zeros és una data per al comprovador dur.
            self._franges[clau] = replace(
                ubicacio, data_iso=prefix if re.match(r"^\d{4}-\d{2}-\d{2}$", prefix) else None
            )
        ubicacio = self._franges[clau]
        return causa_dura(
            sessio,
            ubicacio,
            self.problema.regles,
            self.problema.nivells,
            sessions_dia,
            sessions_slot,
            sessions_per_dia,
            politiques=self.politiques,
            restriccions=self.restriccions,
            sessions_per_data=sessions_per_data,
        )


def causa_principal(raons):
    if not raons:
        return None
    altres = Counter({clau: n for clau, n in raons.items() if clau != "examen_fixat"})
    return (altres or raons).most_common(1)[0][0]


def _mascara_nivells(sessions: list[dict], bits: dict[str, int]) -> int:
    """Un bit per a cada nivell de les sessions. `bits` és el bit de cada
    nivell ja vist en aquesta preparació; un nivell nou en pren el següent.
    Abans el mapa era fix («1-ESO»…«2-BATX», «CFGM»…) i un nivell com «1-BAT»
    tenia màscara 0: la drecera no feia res (la regla d'or de la matriu de
    compatibilitat ho aturava igualment)."""
    mascara = 0
    for s in sessions:
        curs = s.get("curs", "")
        if not curs:
            continue  # sense nivell, la regla d'or tampoc no hi veu conflicte
        mascara |= 1 << bits.setdefault(curs, len(bits))
    return mascara


class EstatCerca:
    """El que hi ha col·locat a cada moment de la cerca. `assigna` i `desfes`
    són l'única manera de tocar-ho: totes les estructures canvien alhora i es
    desfan en l'ordre invers."""

    def __init__(
        self, franges: list[Franja], items: list[dict], compat: list[list[bool]], restriccions: dict, temps_esgotat
    ):
        self._franges = {franja.clau: franja for franja in franges}
        self._items = items
        self._compat = compat
        self._restriccions = restriccions
        self._temps_esgotat = temps_esgotat
        self.mascara_nivells = {clau: 0 for clau in self._franges}  # Màscara de bits de nivells ocupats per franja
        self.items_franja = {clau: [] for clau in self._franges}  # Ítems (índexs) de cada franja
        # Professors comptats per data: una hora d'un professor compta un sol cop per data
        self.professors_data = defaultdict(Counter)
        self.sessions_dia = defaultdict(list)  # per nom de dia: límits per professor
        self.sessions_data = defaultdict(list)  # per data ISO (o nom de dia sense dates): no_mateix_dia
        self.franja_item = [None] * len(items)  # Franja de cada ítem
        # Propagació de franges: franges encara possibles de cada ítem no assignat
        self.franges_restants = [set(it["franges_possibles"]) for it in items]
        # Per al cost: els (franja, ítem) de cada data, quants d'aquests ítems
        # depenen dels altres i els (dia, ítem) que compten per a algun límit
        self.collocats_data = defaultdict(frozenset)
        self.dependents_data = Counter()
        self.collocats_limit = frozenset()
        self._fets = []  # (ítem, franja, franges tretes per la propagació, col·locats d'abans)

    def franja(self, clau: str) -> Franja:
        return self._franges[clau]

    def hi_cap(self, idx: int, clau: str) -> bool:
        """L'ítem pot compartir la franja amb els que ja hi són."""
        if self.mascara_nivells[clau] & self._items[idx]["mascara_nivell"]:
            return False  # Conflicte de nivell (O(1))
        return all(self._compat[idx][existent] for existent in self.items_franja[clau])

    def sessions_a(self, clau: str) -> list[dict]:
        """Sessions ja col·locades a la franja."""
        sessions = []
        for existent in self.items_franja[clau]:
            sessions.extend(self._items[existent]["item"]["sessions"])
        return sessions

    def ubicacions(self) -> list[tuple[dict, str]]:
        """On són les sessions ja col·locades (per a «Mateixa data i hora» entre nivells)."""
        return [
            (s, clau)
            for clau, idxs in self.items_franja.items()
            for i in idxs
            for s in self._items[i]["item"]["sessions"]
        ]

    def assigna(self, idx: int, franja: Franja) -> None:
        it_info = self._items[idx]
        clau = franja.clau
        self.mascara_nivells[clau] |= it_info["mascara_nivell"]
        self.items_franja[clau].append(idx)
        self.professors_data[franja.prefix].update(it_info["claus_franja"].get(clau, {}).keys())
        self.franja_item[idx] = clau
        for s in it_info["item"]["sessions"]:
            self.sessions_dia[franja.dia].append(s)
            self.sessions_data[franja.prefix].append(s)
        abans = (self.collocats_data[franja.prefix], self.collocats_limit)
        self.collocats_data[franja.prefix] = abans[0] | {(clau, it_info["id"])}
        self.dependents_data[franja.prefix] += it_info.get("depen", False)
        if it_info.get("compta_limit"):
            self.collocats_limit = abans[1] | {(franja.prefix, it_info["id"])}  # per data
        self._fets.append((idx, franja, self._propaga(idx, franja), abans))

    def desfes(self) -> None:
        """Desfà l'última assignació."""
        idx, franja, tretes, abans = self._fets.pop()
        for altre, franges in tretes:
            self.franges_restants[altre] |= franges
        it_info = self._items[idx]
        clau = franja.clau
        self.collocats_data[franja.prefix], self.collocats_limit = abans
        self.dependents_data[franja.prefix] -= it_info.get("depen", False)
        self.mascara_nivells[clau] ^= it_info["mascara_nivell"]
        self.items_franja[clau].pop()
        self.professors_data[franja.prefix].subtract(it_info["claus_franja"].get(clau, {}).keys())
        self.franja_item[idx] = None
        for _ in it_info["item"]["sessions"]:
            self.sessions_dia[franja.dia].pop()
            self.sessions_data[franja.prefix].pop()

    def _propaga(self, idx: int, franja: Franja) -> list[tuple[int, set[str]]]:
        """Propagació de franges: treu als ítems posteriors les franges que
        l'assignació els tanca. Retorna (ítem, franges tretes) per desfer-ho."""
        canvis = []
        for altre in range(idx + 1, len(self._items)):
            if self._temps_esgotat():
                return canvis
            if self.franja_item[altre] is not None:
                continue  # Ja assignat

            tretes = set()
            # Si no són compatibles, no pot anar a la mateixa franja
            if not self._compat[idx][altre]:
                if franja.clau in self.franges_restants[altre]:
                    tretes.add(franja.clau)

            # no_mateix_dia obligatori: fora totes les franges del mateix dia
            sessions_del_dia = self.sessions_data.get(franja.prefix, [])
            for s in self._items[altre]["item"]["sessions"]:
                if viola_restriccio_dura(s, sessions_del_dia, self._restriccions):
                    for clau in list(self.franges_restants[altre]):
                        if self._franges[clau].prefix == franja.prefix:
                            tretes.add(clau)
                    break

            if tretes:
                self.franges_restants[altre] -= tretes
                canvis.append((altre, tretes))
        return canvis

    def primer_sense_franges(self, des_de: int) -> int | None:
        """El primer ítem posterior que s'ha quedat sense cap franja."""
        for futur in range(des_de, len(self._items)):
            if not self.franges_restants[futur]:
                return futur
        return None


@dataclass
class _Cerca:
    """Una cerca (una llavor): amb què es fa i què ha trobat fins ara."""

    dures: object
    items: list[dict]
    estat: EstatCerca
    rng: random.Random
    max_nodes: int
    barreja_millors: int
    solucions: list = field(default_factory=list)  # la millor: [(cost, {franja: [ítems]})] o []
    millor_cost: float = float("inf")
    nodes: int = 0  # els nodes explorats (mai més que max_nodes)
    tallada_per_nodes: bool = False  # s'ha deixat algun node per explorar pel límit
    cost: CostCercaBacktracking | None = None  # restriccions, preferències i límits de l'horari a mig fer
    poda: bool = False  # la fita inferior del cost és vàlida (pesos no negatius): es pot podar
    pendent: list = field(default_factory=list)  # bonificació que encara pot arribar des de cada ítem
    atzucac_idx: int = -1  # l'ítem més profund que s'ha quedat sense franges
    atzucac_etiqueta: str | None = None

    def apunta_atzucac(self, idx: int) -> None:
        if idx > self.atzucac_idx:
            self.atzucac_idx = idx
            self.atzucac_etiqueta = self.items[idx]["etiqueta"]


@dataclass
class _Preparacio:
    """Fases 1 i 2 de la cerca: el que no depèn de la llavor."""

    franges: list[Franja]
    dures: object
    items_info: list[dict]  # els ítems amb alguna franja, en l'ordre de la partició
    compat: list[list[bool]]  # compatibilitat entre ítems, amb aquest mateix ordre
    cost: CostCercaBacktracking | None = None  # el cost de restriccions i preferències de qualsevol col·locació


class _PreparacioCompartida:
    """La preparació es fa a la primera llavor que la demana i les altres la
    reaprofiten (abans cada llavor la repetia sencera). Les seves
    línies surten una sola vegada al registre."""

    def __init__(self, prepara):
        self._prepara = prepara
        self._feta = None

    def obte(self) -> _Preparacio | None:
        if self._feta is None:
            self._feta = self._prepara()  # None si s'ha acabat el temps: no es desa
        return self._feta


class Backtracking:
    """Cerca exhaustiva: totes les col·locacions, amb fites i poda."""

    id = "v2-backtrack"

    def cerca(self, problema, politiques, cost_cerca, parametres, pressupost, rng):
        pressupost.inicia()
        self.problema = problema
        self.politiques = politiques
        self.cost_cerca = cost_cerca
        self.pressupost = pressupost
        self.restriccions = problema.regles.a_diccionari()
        self.nivells_actius = list(problema.nivells)
        self.items = ()
        self.registre = []
        self.causes = []
        self.aturada = None
        self.cerca_acabada = False
        self.disponibilitat = Disponibilitat(problema)
        nombre_llavors = max(1, int(parametres.get("seeds_count") or 1))
        max_nodes = parametres.get("max_nodes", 100000)
        barreja_millors = parametres.get("shuffle_top_n", 0)
        millor_cost = float("inf")
        millors_solucions = []
        acabada = False
        preparacio = _PreparacioCompartida(lambda: self._prepara_cerca(problema.dies))
        for _ in range(nombre_llavors):
            if self._temps_esgotat():
                self._marca_aturada("temps")
                break
            llavor = rng.randrange(0, 1_000_000_000)
            solucions = self._cerca_amb_llavor(llavor, problema.dies, max_nodes, barreja_millors, preparacio)
            if self._temps_esgotat():
                self._marca_aturada("temps")
            if solucions and solucions[0][0] < millor_cost:
                millor_cost = solucions[0][0]
                millors_solucions = solucions
            if self.cerca_acabada:
                acabada = True
                break
        if acabada:
            self.aturada = None
        assignacio = None
        if millors_solucions:
            per_clau = {f.clau: f for f in problema.franges}
            assignacio = {
                it["item"]["item_id"]: per_clau[clau] for clau, items in millors_solucions[0][1].items() for it in items
            }
        esperats = sum(len(it.examens) for it in self.items)
        collocats = (
            sum(len(it["item"]["sessions"]) for items in millors_solucions[0][1].values() for it in items)
            if millors_solucions
            else 0
        )
        return ResultatCerca(
            assignacio,
            assignacio is not None and collocats == esperats,
            self.aturada,
            self.causes,
            registre=self.registre,
            cost=millor_cost if assignacio is not None else None,
            items=self.items,
        )

    def _temps_esgotat(self):
        return self.pressupost.temps_esgotat()

    def _comprova_termini(self):
        self.pressupost.comprova_termini()

    def _marca_aturada(self, motiu):
        if self.aturada != "temps":
            self.aturada = motiu

    def _analitza(self, sessio, franja, altres=()):
        return analitza_motor(self.problema, self.disponibilitat, sessio, franja, altres, copia=False)

    def _professors_item_a_franja(self, item: dict, franja: Franja, dures) -> dict | None:
        """Els professors comptats (clau → cost) de posar l'ítem tot sol a la
        franja; None si no hi pot anar: restricció dura, no hi caben les hores
        o un professor amb horari estricte en quedaria fora."""
        # Professors comptats a la franja (per no tornar-los a comptar si un
        # altre bloc de la mateixa franja els fa deixar la mateixa classe)
        claus = {}
        for s in item["sessions"]:
            if dures.comprova(s, franja.dia, franja.hora, franja.prefix, [], [], {}):
                return None
            nom_s = s.get("nom")
            if not examen_hi_cap(nom_s, franja.hora, self.problema):  # l'examen hi ha de cabre sencer
                return None
            analisi = self._analitza(s, franja)
            res_c = cost_sessio(
                sessio=s,
                dia=franja.dia,
                hora=franja.hora,
                analisi=analisi,
                restriccions=self.restriccions,
                sessions_dia=[],
                sessions_slot=None,
                data_iso=franja.data_iso or "",
                ja_comptats=set(claus),
            )
            if res_c.get("professors_estrictes_violats"):
                return None  # horari estricte: obligatori
            claus.update(res_c.get("costos_professors") or {})
        return claus

    def _prepara_items(self, items: list[dict], franges: list[Franja], dures) -> list[dict]:
        """Fase 1: per a cada ítem, a quines franges pot anar i quins
        professors hi compten. Els ítems sense cap franja no hi surten (queden
        fora de la cerca)."""
        items_info = []
        bits_nivell = {}
        for item in items:
            self._comprova_termini()
            claus_franges = {}
            for franja in franges:
                self._comprova_termini()
                claus = self._professors_item_a_franja(item, franja, dures)
                if claus is not None:
                    claus_franges[franja.clau] = claus

            if claus_franges:
                items_info.append(
                    {
                        # Identificador dens (0..N-1) només dels ítems viables
                        "id": len(items_info),
                        "etiqueta": item["nom"],
                        "item": item,
                        "claus_franja": claus_franges,
                        "franges_possibles": set(claus_franges.keys()),  # Per Propagació de franges
                        "mascara_nivell": _mascara_nivells(item["sessions"], bits_nivell),
                    }
                )
        return items_info

    def _posa_costos(self, items_info: list[dict], franges: list[Franja], cost: CostCercaBacktracking) -> None:
        """Apunta a cada ítem què costa a cada franja on pot anar: els seus
        professors, els seus exàmens de cost fix i, per ordenar la cerca, el
        cost de l'ítem tot sol."""
        per_clau = {franja.clau: franja for franja in franges}
        for it in items_info:
            self._comprova_termini()
            it["depen"] = cost.depen[it["id"]]
            it["compta_limit"] = cost.compta_limit[it["id"]]
            it["cost_professors"] = {clau: sum(claus.values()) for clau, claus in it["claus_franja"].items()}
            it["cost_fix"] = {clau: cost.fix(it["id"], clau) for clau in it["claus_franja"]}
            it["totes_franges"] = {
                clau: it["cost_professors"][clau] + cost.sol(it["id"], per_clau[clau]) for clau in it["claus_franja"]
            }
            it["millor_cost"] = min(it["totes_franges"].values())

    def _causa_estructural(self, sessions: list[dict], franges: list[Franja], dures, amb_termini=False) -> str | None:
        """La restricció dura que treu més franges a un ítem tot sol (sense
        comptar què hi ha col·locat); None si cap franja en viola cap."""
        raons: Counter = Counter()
        for franja in franges:
            if amb_termini:
                self._comprova_termini()
            for s in sessions:
                violacio = dures.comprova(s, franja.dia, franja.hora, franja.prefix, [], [], {})
                if violacio:
                    raons[violacio.clau] += 1
                    break
        return causa_principal(raons)

    def _motius_exclosos(self, items: list[dict], items_info: list[dict], franges: list[Franja], dures) -> None:
        """Apunta per què cada ítem sense cap franja ha quedat fora de la cerca."""
        n_exclosos = len(items) - len(items_info)
        if n_exclosos <= 0:
            return
        # Per ítem i no per nom: amb dos exàmens del mateix nom, un de viable i
        # l'altre no, el que quedava fora no tenia missatge
        dins = {id(ii["item"]) for ii in items_info}
        exclosos_items = [item for item in items if id(item) not in dins]
        exclosos_noms = [it.get("nom", "?") for it in exclosos_items]
        self.registre.append(f"   ⚠️ {n_exclosos} items sense cap slot viable (exclosos del backtrack): {exclosos_noms}")
        # Només la primera vegada: les llavors posteriors no els tornen a apuntar
        if self.causes:
            return
        for item in exclosos_items:
            self._comprova_termini()
            nom = item.get("nom", "?")
            motiu = self._causa_estructural(item["sessions"], franges, dures, amb_termini=True)
            if motiu:
                self.causes.append(missatge("examen_sense_hora_causa", nom=nom, causa=motiu))
            else:
                self.causes.append(missatge("examen_sense_hora_motor", nom=nom))

    def _matriu_compatibilitat(self, items_info: list[dict]) -> list[list[bool]]:
        """Fase 2: matriu[i][j] diu si els ítems i i j poden compartir franja."""
        n = len(items_info)
        matriu_compat = [[True] * n for _ in range(n)]
        for i in range(n):
            self._comprova_termini()
            item_i = items_info[i]
            mascara_i = item_i["mascara_nivell"]
            for j in range(i + 1, n):
                self._comprova_termini()
                item_j = items_info[j]
                # Conflicte de nivell: si comparteixen algun bit
                if mascara_i & item_j["mascara_nivell"]:
                    compatible = False
                else:
                    # Comprovar altres restriccions (no_mateix_slot, etc.)
                    sessions_j = [{"sessio": s} for s in item_j["item"]["sessions"]]
                    compatible, _ = es_item_compatible_amb_slot(item_i["item"], sessions_j, self.restriccions)
                matriu_compat[i][j] = compatible
                matriu_compat[j][i] = compatible
        return matriu_compat

    def _ordena_items(self, preparacio: _Preparacio, rng, barreja_millors: int) -> tuple[list[dict], list[list[bool]]]:
        """Els ítems en l'ordre de la cerca d'una llavor (més restringits
        primer) i la matriu de compatibilitat amb aquest ordre. També
        reparteix, amb el rng de la llavor, el rang que desfà els empats de
        cost entre franges."""

        def restringit(x):
            return (len(x["franges_possibles"]), x["millor_cost"])

        # Cada llavor treballa amb còpies dels ítems preparats: hi apunta el seu
        # ordre i els seus rangs
        items_info = [dict(it) for it in preparacio.items_info]
        franges, matriu_compat = preparacio.franges, preparacio.compat
        ordenats = sorted(items_info, key=restringit)
        # Si shuffle_top_n > 0, barreja dins de cada grup d'igual restricció
        if barreja_millors > 0:
            items_barrejats = []
            for _, grup in groupby(ordenats, key=restringit):
                g = list(grup)
                rng.shuffle(g)
                items_barrejats.extend(g)
            ordenats = items_barrejats

        for index_nou, it in enumerate(ordenats):
            it["index_ordre"] = index_nou

        # Empats de cost entre franges: a l'atzar, amb el rng de la llavor. Un
        # rang per ítem i franja, tret en un ordre fix (ítems ordenats, franges
        # per data i hora): la mateixa llavor dona el mateix horari amb qualsevol
        # PYTHONHASHSEED (els candidats surten d'un `set`) i llavors diferents
        # poden triar franges diferents entre les que costen igual. Abans els
        # empats es desfeien per data i hora: totes les llavors donaven el mateix.
        for it in ordenats:
            it["rang_empat"] = {franja.clau: rng.random() for franja in franges}

        # La matriu, amb els índexs nous
        n = len(ordenats)
        nova_compat = [[True] * n for _ in range(n)]
        for i, it_i in enumerate(ordenats):
            self._comprova_termini()
            for j, it_j in enumerate(ordenats):
                nova_compat[i][j] = matriu_compat[it_i["id"]][it_j["id"]]
        return ordenats, nova_compat

    def _franges_per_provar(self, cerca: _Cerca, idx: int) -> list[tuple[str, int]]:
        """(franja, cost) de les franges que li queden a l'ítem, per cost i,
        als empats, pel rang a l'atzar de la llavor; els top-N es barregen
        per diversitat entre llavors."""
        it_info = cerca.items[idx]
        franges_prova = [
            (clau, it_info["totes_franges"].get(clau, float("inf")))
            for clau in cerca.estat.franges_restants[idx]
            if clau in it_info["totes_franges"]
        ]
        rang_empat = it_info["rang_empat"]
        franges_prova.sort(key=lambda x: (x[1], rang_empat[x[0]]))
        if cerca.barreja_millors > 0:
            nombre_millors = min(cerca.barreja_millors, len(franges_prova))
            millors = franges_prova[:nombre_millors]
            cerca.rng.shuffle(millors)
            franges_prova = millors + franges_prova[nombre_millors:]
        return franges_prova

    def _cost_afegit(
        self, it_info: dict, franja: Franja, estat: EstatCerca, ubicacions: list, cerca: _Cerca
    ) -> CostFita | None:
        """El que suma (o resta) posar l'ítem a la franja pel que ja hi ha
        col·locat, sense els seus professors ni el seu cost fix: el canvi de
        les incidències del dia i del límit per professor (i el canvi de la
        seva fita). None si alguna restricció obligatòria no ho deixa fer."""
        clau = franja.clau
        sessions_slot_ara = estat.sessions_a(clau)
        for s in it_info["item"]["sessions"]:
            if cerca.dures.comprova(
                s,
                franja.dia,
                franja.hora,
                franja.prefix,
                estat.sessions_data.get(franja.prefix, []),
                sessions_slot_ara,
                estat.sessions_dia,
                estat.sessions_data,
            ):
                return None
            # «Mateixa data i hora» obligatori: no pot anar a un altre moment que una companya
            if percentatge_preferencia_mateix_slot(s, clau, ubicacions, self.restriccions) >= 100:
                return None
        if encavalca_amb_el_nivell(it_info["item"]["sessions"], clau, ubicacions, self.problema):
            return None  # s'encavalcaria amb un altre examen del mateix nivell

        cost = fita = 0
        if it_info["depen"] or estat.dependents_data[franja.prefix]:
            del_dia = estat.collocats_data[franja.prefix]
            abans, despres = cerca.cost.del_dia(del_dia), cerca.cost.del_dia(del_dia | {(clau, it_info["id"])})
            cost += despres.cost - abans.cost
            fita += despres.fita - abans.fita
        if it_info["compta_limit"]:
            del_limit = estat.collocats_limit
            limit = cerca.cost.limit(del_limit | {(franja.prefix, it_info["id"])}) - cerca.cost.limit(del_limit)
            cost += limit
            fita += limit
        return CostFita(cost, fita) if cost or fita else ZERO

    @staticmethod
    def _descompte(it_info: dict, clau: str, estat: EstatCerca) -> int:
        """Una hora d'un professor ja comptada aquella data per un altre bloc (de la
        mateixa franja o d'una altra) no es torna a comptar."""
        claus_item = it_info["claus_franja"].get(clau, {})
        comptats = estat.professors_data[estat.franja(clau).prefix]
        return sum(c for k, c in claus_item.items() if comptats[k] > 0)

    @staticmethod
    def _poda_valida(cost: CostCercaBacktracking) -> bool:
        """Amb algun pes negatiu el cost pot baixar en afegir exàmens i la
        fita no val: la cerca no poda (és exhaustiva de debò, i lenta)."""
        return cost.poda_valida

    def _desa_solucio(self, cerca: _Cerca, cost: float) -> None:
        """Una solució completa que millora la millor (als empats de cost es
        queda la primera): en queda una sola."""
        franges_solucio = {}
        for i, clau in enumerate(cerca.estat.franja_item):
            if clau is not None:
                franges_solucio.setdefault(clau, []).append(cerca.items[i])
        cerca.millor_cost = cost
        cerca.solucions = [(cost, franges_solucio)]

    def _cerca(self, cerca: _Cerca, idx: int, cost_ac: float, fita_ac: float) -> None:
        """Fase 3: col·loca l'ítem idx a cada franja que li queda, de la més
        barata a la més cara, i continua amb el següent.

        cost_ac és el cost (el final que es mostra) dels ítems ja col·locats;
        fita_ac, el mínim que valdran quan l'horari sigui complet, sense les
        bonificacions que encara poden arribar (`cerca.pendent`). Una branca
        es deixa quan `fita - pendent` ja no pot millorar la millor solució."""
        if self._temps_esgotat():
            return
        # Al límit, la crida no és cap node explorat (abans també es comptava)
        if cerca.nodes >= cerca.max_nodes:
            cerca.tallada_per_nodes = True
            return
        cerca.nodes += 1

        if idx >= len(cerca.items):
            if cost_ac < cerca.millor_cost:
                self._desa_solucio(cerca, cost_ac)
            return
        if cerca.poda and fita_ac - cerca.pendent[idx] >= cerca.millor_cost:
            return

        estat = cerca.estat
        # Propagació de franges: si no queden franges possibles, atzucac
        if not estat.franges_restants[idx]:
            cerca.apunta_atzucac(idx)
            return

        it_info = cerca.items[idx]
        franges_prova = self._franges_per_provar(cerca, idx)
        ubicacions = estat.ubicacions()

        for clau, _ in franges_prova:
            if self._temps_esgotat():
                return
            if not estat.hi_cap(idx, clau):
                continue
            # Els professors de l'ítem (sense els ja comptats a la franja) i el seu cost fix
            propi = it_info["cost_professors"][clau] - self._descompte(it_info, clau, estat) + it_info["cost_fix"][clau]
            if cerca.poda and fita_ac + propi - cerca.pendent[idx] >= cerca.millor_cost:
                continue  # Poda: ni amb la millor bonificació possible no milloraria
            franja = estat.franja(clau)
            afegit = self._cost_afegit(it_info, franja, estat, ubicacions, cerca)
            if afegit is None:
                continue
            cost_nou = cost_ac + propi + afegit.cost
            fita_nova = fita_ac + propi + afegit.fita
            if cerca.poda and fita_nova - cerca.pendent[idx + 1] >= cerca.millor_cost:
                continue  # Poda

            estat.assigna(idx, franja)
            sense_franges = estat.primer_sense_franges(idx + 1)
            if sense_franges is None:
                self._cerca(cerca, idx + 1, cost_nou, fita_nova)
            else:
                cerca.apunta_atzucac(sense_franges)
            estat.desfes()

        # Esgotament del bucle: cap franja vàlida per a idx en aquest context
        cerca.apunta_atzucac(idx)

    def _motiu_sense_solucio(self, cerca: _Cerca, franges: list[Franja], tallada_per_nodes: bool) -> None:
        """Sense cap solució, apunta l'examen de l'atzucac més profund i la
        seva causa. Només si la cerca ha estat exhaustiva: tallada pel temps o
        pels nodes, l'últim atzucac no diu que l'examen no tingui cap hora."""
        if self._temps_esgotat() or tallada_per_nodes or cerca.solucions or not cerca.atzucac_etiqueta or self.causes:
            return
        etiqueta = cerca.atzucac_etiqueta
        # Motiu estructural (sense context), igual que v3-SA
        item_atzucac = next((ii for ii in cerca.items if ii["etiqueta"] == etiqueta), None)
        motiu = None
        if item_atzucac:
            motiu = self._causa_estructural(item_atzucac["item"]["sessions"], franges, cerca.dures)
        msg = missatge("examen_sense_hora_causa", nom=etiqueta, causa=motiu or "conflicte_restriccions")
        self.causes.append(msg)

    def _prepara_cerca(self, dies_utilitzar) -> _Preparacio | None:
        """Fases 1 i 2, iguals per a totes les llavors: franges, ítems amb el
        cost de cada franja i compatibilitat entre ítems. None si s'acaba el
        temps a mitges."""
        dures = _Dures(self.problema, self.politiques)
        franges = list(self.problema.franges)
        self.items = particio(self.problema, self.politiques)
        items = [descongela(it.dades) for it in self.items]
        if not items:
            return _Preparacio(franges, dures, [], [])

        self.registre.append(f"🔍 Pre-calculant costos i compatibilitats per {len(items)} items...")
        try:
            items_info = self._prepara_items(items, franges, dures)
            self._motius_exclosos(items, items_info, franges, dures)
            if not items_info:
                return _Preparacio(franges, dures, [], [])
            cost = self.cost_cerca.prepara(items_info, franges, self._comprova_termini)
            self._posa_costos(items_info, franges, cost)
            self.registre.append(f"   Calculant matriu de compatibilitat {len(items_info)}x{len(items_info)}...")
            matriu_compat = self._matriu_compatibilitat(items_info)
        except TempsEsgotat:
            return None
        return _Preparacio(franges, dures, items_info, matriu_compat, cost)

    def _cerca_amb_llavor(self, llavor, dies_utilitzar, max_nodes=100000, barreja_millors=0, compartida=None):
        """La cerca d'una llavor: [(cost, {franja: [ítems]})] amb la millor
        solució, o [] si no n'ha trobat cap. `compartida` és la preparació de totes les llavors de la
        petició; sense, es prepara aquí."""
        rng = random.Random(llavor)
        # La cerca d'aquesta llavor ha acabat sense tall (ni temps ni nodes)
        self.cerca_acabada = False
        compartida = compartida or _PreparacioCompartida(lambda: self._prepara_cerca(dies_utilitzar))
        preparacio = compartida.obte()
        if preparacio is None:
            return []
        if not preparacio.items_info:
            self.cerca_acabada = True  # cap ítem per col·locar: no hi ha res a buscar
            return []
        dures, franges = preparacio.dures, preparacio.franges
        try:
            items_info, matriu_compat = self._ordena_items(preparacio, rng, barreja_millors)
        except TempsEsgotat:
            return []

        self.registre.append(f"   ✅ {len(items_info)} items preparats")

        estat = EstatCerca(franges, items_info, matriu_compat, self.restriccions, self._temps_esgotat)
        cerca = _Cerca(dures, items_info, estat, rng, max_nodes, barreja_millors)
        cerca.cost = preparacio.cost
        cerca.poda = self._poda_valida(preparacio.cost)
        cerca.pendent = preparacio.cost.pendent([it["id"] for it in items_info])
        self._cerca(cerca, 0, 0, 0)

        tallada_per_nodes = cerca.tallada_per_nodes
        if tallada_per_nodes:
            self._marca_aturada("nodes")
            self.registre.append(f"   ⚠️ Límit de nodes assolit ({max_nodes}), backtrack tallat")
        self.registre.append(f"   📊 Nodes explorats: {cerca.nodes}, solucions trobades: {len(cerca.solucions)}")
        self._motiu_sense_solucio(cerca, franges, tallada_per_nodes)
        self.cerca_acabada = not tallada_per_nodes and not self._temps_esgotat()
        return cerca.solucions
