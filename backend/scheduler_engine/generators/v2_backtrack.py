"""
Motor de generació d'horaris V2 - Backtracking (Cerca exhaustiva).

Optimitzacions implementades:
1. Matriu de compatibilitat pre-calculada entre items
2. Bitmask per nivells ocupats (O(1) per detectar conflictes)
3. Forward Checking (propaga restriccions, detecta dead-ends aviat)
4. Undo/Redo en lloc de còpies profundes
"""

import random
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from itertools import groupby

from scheduler_engine.core.constraints import (
    _percent_penalty,
    es_item_compatible_amb_slot,
    percent_no_mateix_slot_violation,
    percent_pref_mateix_slot_violation,
    viola_restriccio_dura,
)
from scheduler_engine.core.date_mapping import construir_mapa_dia_data_iso
from scheduler_engine.core.franja import Franja, dia_de_prefix
from scheduler_engine.core.franja import franja as _franja
from scheduler_engine.core.missatges import missatge
from scheduler_engine.core.normalitzacio import normalitzar_dia
from scheduler_engine.core.punts import pes_restriccio_dura, pes_restriccio_violada
from scheduler_engine.core.restriction_engine import RestrictionEngine, causa_principal
from scheduler_engine.core.scoring import calcular_cost_slot
from scheduler_engine.defaults import DEFAULT_PES_RESTRICCIO_DURA, DIES_SETMANA
from scheduler_engine.estadistiques import aplicar_estadistiques
from scheduler_engine.generators.v2_intents import GeneradorV2Intents
from scheduler_engine.informe import log


class _TempsEsgotat(Exception):
    """S'ha acabat el termini a mitja preparació."""


def _get_nivell_mask(sessions: list[dict], bits: dict[str, int]) -> int:
    """Un bit per a cada nivell de les sessions. `bits` és el bit de cada
    nivell ja vist en aquesta preparació; un nivell nou en pren el següent.
    Abans el mapa era fix («1-ESO»…«2-BATX», «CFGM»…) i un nivell com «1-BAT»
    tenia màscara 0: la drecera no feia res (la regla d'or de la matriu de
    compatibilitat ho aturava igualment)."""
    mask = 0
    for s in sessions:
        curs = s.get("curs", "")
        if not curs:
            continue  # sense nivell, la regla d'or tampoc no hi veu conflicte
        mask |= 1 << bits.setdefault(curs, len(bits))
    return mask


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
        self.mascara_nivells = {clau: 0 for clau in self._franges}  # Bitmask de nivells ocupats per franja
        self.items_franja = {clau: [] for clau in self._franges}  # Ítems (índexs) de cada franja
        self.professors_franja = {clau: Counter() for clau in self._franges}  # Professors comptats per franja
        self.sessions_dia = defaultdict(list)  # per nom de dia: límits per professor
        self.sessions_data = defaultdict(list)  # per data ISO (o nom de dia sense dates): no_mateix_dia
        self.franja_item = [None] * len(items)  # Franja de cada ítem
        # Forward Checking: franges encara possibles de cada ítem no assignat
        self.franges_restants = [set(it["slots_possibles"]) for it in items]
        self._fets = []  # (ítem, franja, franges tretes per la propagació)

    def franja(self, clau: str) -> Franja:
        return self._franges[clau]

    def hi_cap(self, idx: int, clau: str) -> bool:
        """L'ítem pot compartir la franja amb els que ja hi són."""
        if self.mascara_nivells[clau] & self._items[idx]["nivell_mask"]:
            return False  # Conflicte de nivell (O(1))
        return all(self._compat[idx][existent] for existent in self.items_franja[clau])

    def sessions_a(self, clau: str) -> list[dict]:
        """Sessions ja col·locades a la franja."""
        sessions = []
        for existent in self.items_franja[clau]:
            sessions.extend(self._items[existent]["item"]["sessions"])
        return sessions

    def ubicacions(self) -> list[tuple[dict, str]]:
        """On són les sessions ja col·locades (per a «Mateix dia i hora» entre nivells)."""
        return [
            (s, clau)
            for clau, idxs in self.items_franja.items()
            for i in idxs
            for s in self._items[i]["item"]["sessions"]
        ]

    def assigna(self, idx: int, franja: Franja) -> None:
        it_info = self._items[idx]
        clau = franja.clau
        self.mascara_nivells[clau] |= it_info["nivell_mask"]
        self.items_franja[clau].append(idx)
        self.professors_franja[clau].update(it_info["claus_slot"].get(clau, {}).keys())
        self.franja_item[idx] = clau
        for s in it_info["item"]["sessions"]:
            self.sessions_dia[franja.dia].append(s)
            self.sessions_data[franja.prefix].append(s)
        self._fets.append((idx, franja, self._propaga(idx, franja)))

    def desfes(self) -> None:
        """Desfà l'última assignació."""
        idx, franja, tretes = self._fets.pop()
        for altre, franges in tretes:
            self.franges_restants[altre] |= franges
        it_info = self._items[idx]
        clau = franja.clau
        self.mascara_nivells[clau] ^= it_info["nivell_mask"]
        self.items_franja[clau].pop()
        self.professors_franja[clau].subtract(it_info["claus_slot"].get(clau, {}).keys())
        self.franja_item[idx] = None
        for _ in it_info["item"]["sessions"]:
            self.sessions_dia[franja.dia].pop()
            self.sessions_data[franja.prefix].pop()

    def _propaga(self, idx: int, franja: Franja) -> list[tuple[int, set[str]]]:
        """Forward Checking: treu als ítems posteriors les franges que
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

    engine: object
    items: list[dict]
    estat: EstatCerca
    rng: random.Random
    max_nodes: int
    shuffle_top_n: int
    solucions: list = field(default_factory=list)  # la millor: [(cost, {franja: [ítems]})] o []
    millor_cost: float = float("inf")
    nodes: int = 0  # els nodes explorats (mai més que max_nodes)
    tallada_per_nodes: bool = False  # s'ha deixat algun node per explorar pel límit
    poda_abans: bool = False  # es pot podar abans de calcular el cost afegit (pesos no negatius)
    atzucac_idx: int = -1  # l'ítem més profund que s'ha quedat sense franges
    atzucac_label: str | None = None

    def apunta_atzucac(self, idx: int) -> None:
        if idx > self.atzucac_idx:
            self.atzucac_idx = idx
            self.atzucac_label = self.items[idx]["label"]


@dataclass
class _Preparacio:
    """Fases 1 i 2 de la cerca: el que no depèn de la llavor."""

    franges: list[Franja]
    engine: object
    items_info: list[dict]  # els ítems amb alguna franja, en l'ordre de la partició
    compat: list[list[bool]]  # compatibilitat entre ítems, amb aquest mateix ordre


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


class GeneradorV2Backtrack(GeneradorV2Intents):
    def _temps_esgotat(self):
        return time.monotonic() >= getattr(self, "_termini_bt", float("inf"))

    def _marca_aturada(self, motiu: str) -> None:
        """La cerca no ha estat exhaustiva: «temps» (el termini compartit de
        totes les llavors) mana sobre «nodes» (el límit d'una llavor)."""
        if getattr(self, "_aturada_bt", None) != "temps":
            self._aturada_bt = motiu

    def generar_horari_optimitzat(
        self,
        data_inici: str = None,
        data_inici_iso: str = None,
        max_dies: int = 5,
        dies_utilitzar: list[str] = None,
        dia_a_data_iso: dict[str, str] = None,
        **kwargs,
    ) -> dict:
        solucions = self.generar_totes_solucions_optimes(
            data_inici, data_inici_iso, max_dies, dies_utilitzar, dia_a_data_iso=dia_a_data_iso, **kwargs
        )
        if not solucions or not solucions[0].get("dies"):
            return (
                solucions[0]
                if solucions
                else {"dies": [], "metadata": {"cost_total": 999999, "error": missatge("sense_solucions")}}
            )
        return solucions[0]

    def generar_totes_solucions_optimes(
        self,
        data_inici=None,
        data_inici_iso=None,
        max_dies=5,
        dies_utilitzar=None,
        random_seed=None,
        seeds_count=None,
        dia_a_data_iso=None,
        max_nodes=100000,
        shuffle_top_n=0,
        **kwargs,
    ):
        """[horari]: el millor horari de totes les llavors (als empats de cost,
        el de la primera llavor que hi arriba) o, si no n'hi ha cap, un horari
        buit amb l'error. Abans també retornava les llavors empatades
        («alternatives», que la pantalla no feia servir)."""
        self._termini_bt = time.monotonic() + self.segons_maxims
        if dies_utilitzar is None:
            dies_utilitzar = list(DIES_SETMANA)[:max_dies]

        self.selected_dates = sorted(kwargs.get("selected_dates") or [])

        self.dia_a_data_iso = {}
        if dia_a_data_iso:
            self.dia_a_data_iso = {normalitzar_dia(k): v for k, v in (dia_a_data_iso or {}).items() if v}
        else:
            self.dia_a_data_iso = construir_mapa_dia_data_iso(
                dies_utilitzar=dies_utilitzar,
                selected_dates=self.selected_dates or None,
                data_inici_iso=data_inici_iso,
            )

        seeds_count = int(seeds_count or 1)
        if seeds_count < 1:
            seeds_count = 1

        seed_rng = random.SystemRandom() if random_seed is None else random.Random(random_seed)

        self._incompatibilitats_bt = []
        self._aturada_bt = None
        best_cost = float("inf")
        best_solutions = []  # [(cost, {franja: [ítems]})] de la millor llavor

        preparacio = _PreparacioCompartida(lambda: self._prepara_cerca(dies_utilitzar))
        for _ in range(seeds_count):
            if self._temps_esgotat():
                self._marca_aturada("temps")
                break
            seed = seed_rng.randrange(0, 1_000_000_000)
            sols = self._backtrack_with_seed(seed, dies_utilitzar, max_nodes, shuffle_top_n, preparacio)
            if self._temps_esgotat():
                self._marca_aturada("temps")
            if sols and sols[0][0] < best_cost:
                best_cost = sols[0][0]
                best_solutions = sols

        resultats = []
        for cost, s_occ in best_solutions:
            h = self._construir_horari_desde_slots(s_occ, None, dies_utilitzar)
            h["metadata"].update({"cost_total": cost, "motor": "v2-backtrack"})
            resultats.append(h)

        motiu = self._aturada_bt
        if resultats:
            if motiu:
                resultats[0]["metadata"]["motiu_aturada"] = motiu
            return resultats
        if motiu == "temps":
            error = missatge("cerca_tallada_temps", segons=self.segons_maxims)
        elif motiu == "nodes":
            error = missatge("cerca_tallada_nodes", nodes=max_nodes)
        else:
            return [{"metadata": {"error": missatge("no_viable"), "viable": False}, "dies": []}]
        return [{"metadata": {"error": error, "viable": False, "motiu_aturada": motiu}, "dies": []}]

    def _franges(self, dies_utilitzar) -> list[Franja]:
        """Les franges on pot començar un examen: cada data triada (o, sense
        dates, cada dia) amb cada hora d'examen."""
        prefixos = getattr(self, "selected_dates", None) or dies_utilitzar
        return [_franja(f"{prefix}_{h}") for prefix in prefixos for h in self.hores_examen]

    def _comprova_termini(self) -> None:
        if self._temps_esgotat():
            raise _TempsEsgotat

    def _cost_item_a_franja(self, item: dict, franja: Franja, engine) -> tuple[int, dict] | None:
        """(cost, professors comptats) de posar l'ítem tot sol a la franja;
        None si no hi pot anar: restricció dura, no hi caben les hores o
        alguna sessió hi costa tant com una restricció dura."""
        cost = 0
        # Professors comptats a la franja (per no tornar-los a comptar si un
        # altre bloc de la mateixa franja els fa deixar la mateixa classe)
        claus = {}
        for s in item["sessions"]:
            if engine.check_hard(s, franja.dia, franja.hora, franja.prefix, [], [], {}):
                return None
            nom_s = s.get("nom")
            curs_s = s.get("curs")
            durada_supervisio = self.get_durada_per_sessio_key(nom_s, curs_s)
            if len(self._get_hores_ocupades(franja.hora, curs_s, nom_s)) < durada_supervisio:
                return None
            analisi = self.analitzar_disponibilitat_sessio(
                s, franja.dia, franja.hora, sessions_al_slot=None, data_iso=franja.data_iso
            )
            res_c = calcular_cost_slot(
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
            if res_c["cost_total"] >= DEFAULT_PES_RESTRICCIO_DURA:
                return None
            cost += res_c["cost_total"]
            claus.update(res_c.get("costos_professors") or {})
        return cost, claus

    def _prepara_items(self, items: list[dict], franges: list[Franja], engine) -> list[dict]:
        """Fase 1: per a cada ítem, què costa a cada franja on pot anar. Els
        ítems sense cap franja no hi surten (queden fora de la cerca)."""
        items_info = []
        bits_nivell = {}
        for item in items:
            self._comprova_termini()
            slots_costs = {}
            slots_claus = {}
            for franja in franges:
                self._comprova_termini()
                resultat = self._cost_item_a_franja(item, franja, engine)
                if resultat is not None:
                    slots_costs[franja.clau], slots_claus[franja.clau] = resultat

            if slots_costs:
                items_info.append(
                    {
                        # Identificador dens (0..N-1) només dels ítems viables
                        "id": len(items_info),
                        "label": item["nom"],
                        "item": item,
                        "millor_cost": min(slots_costs.values()),
                        "tots_slots": slots_costs,
                        "claus_slot": slots_claus,
                        "slots_possibles": set(slots_costs.keys()),  # Per Forward Checking
                        "nivell_mask": _get_nivell_mask(item["sessions"], bits_nivell),
                    }
                )
        return items_info

    def _causa_estructural(self, sessions: list[dict], franges: list[Franja], engine, amb_termini=False) -> str | None:
        """La restricció dura que treu més franges a un ítem tot sol (sense
        comptar què hi ha col·locat); None si cap franja en viola cap."""
        raons: Counter = Counter()
        for franja in franges:
            if amb_termini:
                self._comprova_termini()
            for s in sessions:
                violation = engine.check_hard(s, franja.dia, franja.hora, franja.prefix, [], [], {})
                if violation:
                    raons[violation.restriction] += 1
                    break
        return causa_principal(raons)

    def _motius_exclosos(self, items: list[dict], items_info: list[dict], franges: list[Franja], engine) -> None:
        """Apunta per què cada ítem sense cap franja ha quedat fora de la cerca."""
        n_exclosos = len(items) - len(items_info)
        if n_exclosos <= 0:
            return
        # Per ítem i no per nom: amb dos exàmens del mateix nom, un de viable i
        # l'altre no, el que quedava fora no tenia missatge
        dins = {id(ii["item"]) for ii in items_info}
        exclosos_items = [item for item in items if id(item) not in dins]
        exclosos_noms = [it.get("nom", "?") for it in exclosos_items]
        log.info(f"   ⚠️ {n_exclosos} items sense cap slot viable (exclosos del backtrack): {exclosos_noms}")
        # Només la primera vegada: les llavors posteriors no els tornen a apuntar
        if self._incompatibilitats_bt:
            return
        for item in exclosos_items:
            self._comprova_termini()
            nom = item.get("nom", "?")
            motiu = self._causa_estructural(item["sessions"], franges, engine, amb_termini=True)
            if motiu:
                self._incompatibilitats_bt.append(missatge("examen_sense_hora_causa", nom=nom, causa=motiu))
            else:
                self._incompatibilitats_bt.append(missatge("examen_sense_hora_motor", nom=nom))

    def _matriu_compatibilitat(self, items_info: list[dict]) -> list[list[bool]]:
        """Fase 2: matriu[i][j] diu si els ítems i i j poden compartir franja."""
        n = len(items_info)
        compat_matrix = [[True] * n for _ in range(n)]
        for i in range(n):
            self._comprova_termini()
            item_i = items_info[i]
            mask_i = item_i["nivell_mask"]
            for j in range(i + 1, n):
                self._comprova_termini()
                item_j = items_info[j]
                # Conflicte de nivell: si comparteixen algun bit
                if mask_i & item_j["nivell_mask"]:
                    compatible = False
                else:
                    # Comprovar altres restriccions (no_mateix_slot, etc.)
                    sessions_j = [{"sessio": s} for s in item_j["item"]["sessions"]]
                    compatible, _ = es_item_compatible_amb_slot(item_i["item"], sessions_j, self.restriccions)
                compat_matrix[i][j] = compatible
                compat_matrix[j][i] = compatible
        return compat_matrix

    def _ordena_items(self, preparacio: _Preparacio, rng, shuffle_top_n: int) -> tuple[list[dict], list[list[bool]]]:
        """Els ítems en l'ordre de la cerca d'una llavor (més restringits
        primer) i la matriu de compatibilitat amb aquest ordre. També
        reparteix, amb el rng de la llavor, el rang que desfà els empats de
        cost entre franges."""

        def restringit(x):
            return (len(x["slots_possibles"]), x["millor_cost"])

        # Cada llavor treballa amb còpies dels ítems preparats: hi apunta el seu
        # ordre i els seus rangs
        items_info = [dict(it) for it in preparacio.items_info]
        franges, compat_matrix = preparacio.franges, preparacio.compat
        ordenats = sorted(items_info, key=restringit)
        # Si shuffle_top_n > 0, barreja dins de cada grup d'igual restricció
        if shuffle_top_n > 0:
            shuffled_items = []
            for _, grp in groupby(ordenats, key=restringit):
                g = list(grp)
                rng.shuffle(g)
                shuffled_items.extend(g)
            ordenats = shuffled_items

        for new_idx, it in enumerate(ordenats):
            it["sorted_id"] = new_idx

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
        new_compat = [[True] * n for _ in range(n)]
        for i, it_i in enumerate(ordenats):
            self._comprova_termini()
            for j, it_j in enumerate(ordenats):
                new_compat[i][j] = compat_matrix[it_i["id"]][it_j["id"]]
        return ordenats, new_compat

    def _franges_per_provar(self, cerca: _Cerca, idx: int) -> list[tuple[str, int]]:
        """(franja, cost) de les franges que li queden a l'ítem, per cost i,
        als empats, pel rang a l'atzar de la llavor; els top-N es barregen
        per diversitat entre llavors."""
        it_info = cerca.items[idx]
        slots_to_try = [
            (sk, it_info["tots_slots"].get(sk, float("inf")))
            for sk in cerca.estat.franges_restants[idx]
            if sk in it_info["tots_slots"]
        ]
        rang_empat = it_info["rang_empat"]
        slots_to_try.sort(key=lambda x: (x[1], rang_empat[x[0]]))
        if cerca.shuffle_top_n > 0:
            top_n = min(cerca.shuffle_top_n, len(slots_to_try))
            top = slots_to_try[:top_n]
            cerca.rng.shuffle(top)
            slots_to_try = top + slots_to_try[top_n:]
        return slots_to_try

    def _cost_extra(self, it_info: dict, franja: Franja, estat: EstatCerca, ubicacions: list, engine) -> int | None:
        """El que suma (o resta) posar l'ítem a la franja pel que ja hi ha
        col·locat; None si alguna restricció dura no ho deixa fer."""
        sk = franja.clau
        sessions_slot_ara = estat.sessions_a(sk)
        cost_extra = 0
        for s in it_info["item"]["sessions"]:
            if engine.check_hard(
                s,
                franja.dia,
                franja.hora,
                franja.prefix,
                estat.sessions_data.get(franja.prefix, []),
                sessions_slot_ara,
                estat.sessions_dia,
            ):
                return None
            cost_extra += self._calcular_penalitzacio_professors_dies(s, franja.dia, estat.sessions_dia)
            pct_slot = percent_no_mateix_slot_violation(s, sessions_slot_ara, self.restriccions)
            if pct_slot:
                pesos_opt = self.restriccions.get("pesos_optimitzacio", {})
                pes_d = pesos_opt.get("restriccio_dura", DEFAULT_PES_RESTRICCIO_DURA)
                cost_extra += _percent_penalty(pes_d, pct_slot)
            pct_pref = percent_pref_mateix_slot_violation(s, sk, ubicacions, self.restriccions)
            if pct_pref >= 100:
                return None
            cost_extra += _percent_penalty(DEFAULT_PES_RESTRICCIO_DURA, pct_pref)

        return cost_extra - self._descompte(it_info, sk, estat)

    @staticmethod
    def _descompte(it_info: dict, sk: str, estat: EstatCerca) -> int:
        """Un professor ja comptat a la franja per un altre bloc deixa la
        mateixa classe: no es torna a comptar (l'única part del cost afegit
        que resta, si els pesos no són negatius)."""
        claus_item = it_info["claus_slot"].get(sk, {})
        return sum(c for k, c in claus_item.items() if estat.professors_franja[sk][k] > 0)

    def _poda_abans_del_cost_extra(self) -> bool:
        """El cost afegit, sense el descompte, mai és negatiu si els pesos de
        les restriccions no ho són: aleshores es pot podar abans de calcular-lo."""
        return pes_restriccio_dura(self.restriccions) >= 0 and pes_restriccio_violada(self.restriccions) >= 0

    def _desa_solucio(self, cerca: _Cerca, cost: float) -> None:
        """Una solució completa. La poda és amb `>=` (a `_cerca`): només hi
        arriben les que milloren la millor, i en queda una sola."""
        sol_slots = {}
        for i, sk in enumerate(cerca.estat.franja_item):
            if sk is not None:
                sol_slots.setdefault(sk, []).append(cerca.items[i])
        cerca.millor_cost = cost
        cerca.solucions = [(cost, sol_slots)]

    def _cerca(self, cerca: _Cerca, idx: int, cost_ac: float) -> None:
        """Fase 3: col·loca l'ítem idx a cada franja que li queda, de la més
        barata a la més cara, i continua amb el següent."""
        if self._temps_esgotat():
            return
        # Al límit, la crida no és cap node explorat (abans també es comptava)
        if cerca.nodes >= cerca.max_nodes:
            cerca.tallada_per_nodes = True
            return
        cerca.nodes += 1
        if cost_ac >= cerca.millor_cost:
            return

        if idx >= len(cerca.items):
            self._desa_solucio(cerca, cost_ac)
            return

        estat = cerca.estat
        # Forward Checking: si no queden franges possibles, atzucac
        if not estat.franges_restants[idx]:
            cerca.apunta_atzucac(idx)
            return

        it_info = cerca.items[idx]
        slots_to_try = self._franges_per_provar(cerca, idx)
        ubicacions = estat.ubicacions()

        for sk, base_cost in slots_to_try:
            if self._temps_esgotat():
                return
            if not estat.hi_cap(idx, sk):
                continue
            if cerca.poda_abans and cost_ac + base_cost - self._descompte(it_info, sk, estat) >= cerca.millor_cost:
                continue  # Poda: ni amb el millor cost afegit possible no milloraria
            franja = estat.franja(sk)
            cost_extra = self._cost_extra(it_info, franja, estat, ubicacions, cerca.engine)
            if cost_extra is None:
                continue
            new_cost = cost_ac + base_cost + cost_extra
            if new_cost >= cerca.millor_cost:
                continue  # Poda

            estat.assigna(idx, franja)
            sense_franges = estat.primer_sense_franges(idx + 1)
            if sense_franges is None:
                self._cerca(cerca, idx + 1, new_cost)
            else:
                cerca.apunta_atzucac(sense_franges)
            estat.desfes()

        # Esgotament del bucle: cap franja vàlida per a idx en aquest context
        cerca.apunta_atzucac(idx)

    def _motiu_sense_solucio(self, cerca: _Cerca, franges: list[Franja], tallada_per_nodes: bool) -> None:
        """Sense cap solució, apunta l'examen de l'atzucac més profund i la
        seva causa. Només si la cerca ha estat exhaustiva: tallada pel temps o
        pels nodes, l'últim atzucac no diu que l'examen no tingui cap hora."""
        if (
            self._temps_esgotat()
            or tallada_per_nodes
            or cerca.solucions
            or not cerca.atzucac_label
            or self._incompatibilitats_bt
        ):
            return
        label = cerca.atzucac_label
        # Motiu estructural (sense context), igual que v3-SA
        deadend_item = next((ii for ii in cerca.items if ii["label"] == label), None)
        motiu = None
        if deadend_item:
            motiu = self._causa_estructural(deadend_item["item"]["sessions"], franges, cerca.engine)
        msg = missatge("examen_sense_hora_causa", nom=label, causa=motiu or "conflicte_restriccions")
        self._incompatibilitats_bt.append(msg)

    def _prepara_cerca(self, dies_utilitzar) -> _Preparacio | None:
        """Fases 1 i 2, iguals per a totes les llavors: franges, ítems amb el
        cost de cada franja i compatibilitat entre ítems. None si s'acaba el
        temps a mitges."""
        engine = RestrictionEngine(self.restriccions, self.nivells_actius)
        franges = self._franges(dies_utilitzar)
        # Com els altres dos motors: les hores dels professors, normalitzades
        # una sola vegada (si no, es normalitzen a cada anàlisi)
        self._horaris_norm = self._pre_normalitzar_horaris() if getattr(self, "horaris_professors", None) else None

        # Obtenir partició atòmica centralitzada
        items = self.preparar_particio_nivells(slots_disponibles=len(franges))
        if not items:
            return _Preparacio(franges, engine, [], [])

        log.info(f"🔍 Pre-calculant costos i compatibilitats per {len(items)} items...")
        try:
            items_info = self._prepara_items(items, franges, engine)
            self._motius_exclosos(items, items_info, franges, engine)
            if not items_info:
                return _Preparacio(franges, engine, [], [])
            log.info(f"   Calculant matriu de compatibilitat {len(items_info)}x{len(items_info)}...")
            compat_matrix = self._matriu_compatibilitat(items_info)
        except _TempsEsgotat:
            return None
        return _Preparacio(franges, engine, items_info, compat_matrix)

    def _backtrack_with_seed(self, seed, dies_utilitzar, max_nodes=100000, shuffle_top_n=0, compartida=None):
        """La cerca d'una llavor: [(cost, {franja: [ítems]})] amb la millor
        solució, o [] si no n'ha trobat cap. `compartida` és la preparació de totes les llavors de la
        petició; sense, es prepara aquí."""
        rng = random.Random(seed)
        compartida = compartida or _PreparacioCompartida(lambda: self._prepara_cerca(dies_utilitzar))
        preparacio = compartida.obte()
        if preparacio is None or not preparacio.items_info:
            return []
        engine, franges = preparacio.engine, preparacio.franges
        try:
            items_info, compat_matrix = self._ordena_items(preparacio, rng, shuffle_top_n)
        except _TempsEsgotat:
            return []

        log.info(f"   ✅ {len(items_info)} items preparats")

        estat = EstatCerca(franges, items_info, compat_matrix, self.restriccions, self._temps_esgotat)
        cerca = _Cerca(engine, items_info, estat, rng, max_nodes, shuffle_top_n)
        cerca.poda_abans = self._poda_abans_del_cost_extra()
        self._cerca(cerca, 0, 0)

        tallada_per_nodes = cerca.tallada_per_nodes
        if tallada_per_nodes:
            self._marca_aturada("nodes")
            log.info(f"   ⚠️ Límit de nodes assolit ({max_nodes}), backtrack tallat")
        log.info(f"   📊 Nodes explorats: {cerca.nodes}, solucions trobades: {len(cerca.solucions)}")
        self._motiu_sense_solucio(cerca, franges, tallada_per_nodes)
        return cerca.solucions

    def _construir_horari_desde_slots(self, slots_occ, data_inici, dies_utilitzar):

        selected = getattr(self, "selected_dates", None) or []
        if selected:
            dies_iter = []
            for prefix in selected:
                dia_nom, data_iso = dia_de_prefix(prefix)
                if data_iso:
                    dies_iter.append((dia_nom, data_iso, data_iso))
        else:
            dies_iter = [(d, None, d) for d in dies_utilitzar]

        res_dies = []
        for dia_nom, data_iso, sk_prefix in dies_iter:
            di = {"dia": dia_nom, "sessions": []}
            if data_iso:
                di["data"] = data_iso
            for h in self.hores_examen:
                sk = f"{sk_prefix}_{h}"
                its = slots_occ.get(sk, [])
                if its:
                    sim = []
                    all_s = []
                    for it in its:
                        all_s.extend(it["item"]["sessions"])
                    for s in all_s:
                        sc = s.copy()
                        sc["analisi"] = self.analitzar_disponibilitat_sessio(
                            s, dia_nom, h, [x for x in all_s if x != s], data_iso=data_iso
                        )
                        sim.append(sc)
                    di["sessions"].append({"hora": h, "sessions_simultanees": sim})
            res_dies.append(di)
        final = {
            "dies": res_dies,
            "metadata": {"total_sessions": self.get_total_sessions_count(), "data_inici": data_inici},
        }
        aplicar_estadistiques(final)
        return final
