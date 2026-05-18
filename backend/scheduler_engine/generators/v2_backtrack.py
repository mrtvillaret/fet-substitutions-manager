"""
Motor de generació d'horaris V2 - Backtracking (Cerca exhaustiva).

Optimitzacions implementades:
1. Matriu de compatibilitat pre-calculada entre items
2. Bitmask per nivells ocupats (O(1) per detectar conflictes)
3. Forward Checking (propaga restriccions, detecta dead-ends aviat)
4. Undo/Redo en lloc de còpies profundes
"""

import random
from typing import List, Dict, Tuple, Set, Optional
from collections import defaultdict, Counter

from scheduler_engine.core.normalitzacio import normalitzar_text, normalitzar_dia, nom_base_assignatura
from scheduler_engine.core.date_mapping import construir_mapa_dia_data_iso, DIES_CAT as _DIES_CAT
from scheduler_engine.core.constraints import (
    viola_restriccio_dura,
    es_item_compatible_amb_slot, percent_no_mateix_slot_violation,
    _percent_penalty
)
from scheduler_engine.core.restriction_engine import RestrictionEngine
from scheduler_engine.core.availability import analitzar_disponibilitat_sessio
from scheduler_engine.core.scoring import calcular_cost_slot
from scheduler_engine.generators.v2_intents import GeneradorV2Intents
from scheduler_engine.estadistiques import aplicar_estadistiques
from scheduler_engine.defaults import DEFAULT_PES_RESTRICCIO_DURA


# Mapa de nivells a índexs per bitmask
NIVELL_TO_BIT = {
    '1-ESO': 0, '2-ESO': 1, '3-ESO': 2, '4-ESO': 3,
    '1-BATX': 4, '2-BATX': 5,
    'CFGM': 6, 'CFGS': 7,
    # Aliases
    'ESO1': 0, 'ESO2': 1, 'ESO3': 2, 'ESO4': 3,
    'BAC1': 4, 'BAC2': 5,
}


def _get_nivell_mask(sessions: List[Dict]) -> int:
    """Retorna un bitmask amb els nivells de les sessions."""
    mask = 0
    for s in sessions:
        curs = s.get('curs', '')
        bit = NIVELL_TO_BIT.get(curs)
        if bit is not None:
            mask |= (1 << bit)
    return mask


class GeneradorV2Backtrack(GeneradorV2Intents):
    def generar_horari_optimitzat(self, data_inici: str = None, data_inici_iso: str = None, max_dies: int = 5,
                                  dies_utilitzar: List[str] = None,
                                  dia_a_data_iso: Dict[str, str] = None,
                                  max_solucions: int = 100, **kwargs) -> Dict:
        solucions = self.generar_totes_solucions_optimes(
            data_inici, data_inici_iso, max_dies, dies_utilitzar, max_solucions,
            dia_a_data_iso=dia_a_data_iso, **kwargs
        )
        if not solucions or not solucions[0].get('dies'):
            return solucions[0] if solucions else {'dies': [], 'metadata': {'cost_total': 999999, 'error': "No solucions"}}
        return solucions[0]

    def generar_totes_solucions_optimes(self, data_inici=None, data_inici_iso=None, max_dies=5, dies_utilitzar=None, max_solucions=100, random_seed=None, seeds_count=None, dia_a_data_iso=None, max_nodes=100000, shuffle_top_n=0, **kwargs):
        if dies_utilitzar is None:
            from scheduler_engine.defaults import DIES_SETMANA
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

        if random_seed is None:
            seed_rng = random.SystemRandom()
            seeds = [seed_rng.randrange(0, 1_000_000_000) for _ in range(seeds_count)]
        else:
            seed_rng = random.Random(random_seed)
            seeds = [seed_rng.randrange(0, 1_000_000_000) for _ in range(seeds_count)]

        self._incompatibilitats_bt = []
        best_cost = float('inf')
        best_solutions = []

        for seed in seeds:
            sols = self._backtrack_with_seed(seed, dies_utilitzar, max_solucions, max_nodes, shuffle_top_n)
            if not sols:
                continue
            cost_seed = sols[0][0]
            if cost_seed < best_cost:
                best_cost = cost_seed
                best_solutions = sols
            elif cost_seed == best_cost and best_solutions is not None:
                best_solutions.extend(sols)
                best_solutions = best_solutions[:max_solucions]

        totes_solucions = best_solutions

        resultats = []
        for cost, s_occ in (totes_solucions or []):
            h = self._construir_horari_desde_slots(s_occ, None, dies_utilitzar)
            h['metadata'].update({'cost_total': cost, 'motor': 'v2-backtrack'})
            resultats.append(h)

        return resultats if resultats else [{'metadata': {'error': "No viable", 'viable': False}, 'dies': []}]

    def _backtrack_with_seed(self, seed, dies_utilitzar, max_solucions, max_nodes=100000, shuffle_top_n=0):
        from datetime import datetime as _dt

        def _parse_prefix(prefix: str):
            try:
                dt = _dt.strptime(prefix, "%Y-%m-%d")
                return _DIES_CAT[dt.weekday()], prefix
            except ValueError:
                return prefix, None

        rng = random.Random(seed)
        engine = RestrictionEngine(self.restriccions, self.nivells_actius)

        selected = getattr(self, 'selected_dates', None) or []
        if selected:
            slots_disp = [f"{data}_{h}" for data in selected for h in self.hores_examen]
        else:
            slots_disp = [f"{d}_{h}" for d in dies_utilitzar for h in self.hores_examen]
        slot_to_idx = {sk: i for i, sk in enumerate(slots_disp)}
        num_slots = len(slots_disp)

        # Obtenir partició atòmica centralitzada
        items = self.preparar_particio_nivells(slots_disponibles=num_slots)
        num_items = len(items)

        if num_items == 0:
            return []

        print(f"🔍 Pre-calculant costos i compatibilitats per {num_items} items...")

        # =============================================================
        # FASE 1: Pre-calcular costos item-slot i màscares de nivell
        # =============================================================
        items_info = []
        for item in items:
            slots_costs = {}
            for sk in slots_disp:
                _idx = sk.rfind('_')
                prefix, h = sk[:_idx], sk[_idx + 1:]
                d, data_iso_bt = _parse_prefix(prefix)  # d = dia_nom per restriccions
                cost, possible = 0, True
                for s in item['sessions']:
                    if engine.check_hard(s, d, h, prefix, [], [], {}):
                        possible = False
                        break
                    nom_s = s.get('nom')
                    curs_s = s.get('curs')
                    durada_supervisio = self.get_durada_per_sessio_key(nom_s, curs_s)
                    hores_sup_bt = self._get_hores_ocupades(h, curs_s, nom_s)
                    if len(hores_sup_bt) < durada_supervisio:
                        possible = False
                        break
                    analisi = self.analitzar_disponibilitat_sessio(
                        s, d, h, sessions_al_slot=None, data_iso=data_iso_bt
                    )
                    res_c = calcular_cost_slot(
                        sessio=s, dia=d, hora=h, analisi=analisi,
                        restriccions=self.restriccions, sessions_dia=[], sessions_slot=None,
                        data_iso=data_iso_bt or ""
                    )
                    if res_c['cost_total'] >= DEFAULT_PES_RESTRICCIO_DURA:
                        possible = False
                        break
                    cost += res_c['cost_total']
                if possible:
                    slots_costs[sk] = cost

            if slots_costs:
                nivell_mask = _get_nivell_mask(item['sessions'])
                millor = min(slots_costs.values())
                # Identificador dens (0..N-1) només pels items realment viables.
                # Evita índexs fora de rang quan alguns items no tenen cap slot possible.
                dense_id = len(items_info)
                items_info.append({
                    'id': dense_id,
                    'label': item['nom'],
                    'item': item,
                    'millor_cost': millor,
                    'tots_slots': slots_costs,
                    'slots_possibles': set(slots_costs.keys()),  # Per Forward Checking
                    'nivell_mask': nivell_mask,
                    '_rand': rng.random()
                })

        n_exclosos = len(items) - len(items_info)
        if n_exclosos > 0:
            items_info_labels = {ii['label'] for ii in items_info}
            exclosos_items = [item for item in items if item.get('nom', '?') not in items_info_labels]
            exclosos_noms = [it.get('nom', '?') for it in exclosos_items]
            print(f"   ⚠️ {n_exclosos} items sense cap slot viable (exclosos del backtrack): {exclosos_noms}")
            # Detectar raó principal per cada ítem exclòs (primera vegada, les seeds posteriors ometen)
            if not self._incompatibilitats_bt:
                for item in exclosos_items:
                    nom = item.get('nom', '?')
                    raons: Counter = Counter()
                    for sk in slots_disp:
                        _idx_sk = sk.rfind('_')
                        prefix_sk, h_sk = sk[:_idx_sk], sk[_idx_sk + 1:]
                        d_sk, _ = _parse_prefix(prefix_sk)
                        for s in item['sessions']:
                            violation = engine.check_hard(s, d_sk, h_sk, prefix_sk, [], [], {})
                            if violation:
                                raons[violation.label] += 1
                                break
                    if raons:
                        motiu = raons.most_common(1)[0][0]
                        self._incompatibilitats_bt.append(f"Cap slot per a '{nom}' — {motiu}")
                    else:
                        self._incompatibilitats_bt.append(f"Cap slot disponible per a '{nom}'")

        if not items_info:
            return []

        num_items_valid = len(items_info)

        # =============================================================
        # FASE 2: Pre-calcular matriu de compatibilitat entre items
        # =============================================================
        # compat_matrix[i][j] = True si items i i j poden coexistir al mateix slot
        print(f"   Calculant matriu de compatibilitat {num_items_valid}x{num_items_valid}...")

        compat_matrix = [[True] * num_items_valid for _ in range(num_items_valid)]

        for i in range(num_items_valid):
            item_i = items_info[i]
            mask_i = item_i['nivell_mask']
            for j in range(i + 1, num_items_valid):
                item_j = items_info[j]
                mask_j = item_j['nivell_mask']

                # Conflicte de nivell: si comparteixen algun bit
                if mask_i & mask_j:
                    compat_matrix[i][j] = False
                    compat_matrix[j][i] = False
                else:
                    # Comprovar altres restriccions (no_mateix_slot, etc.)
                    sessions_j = [{'sessio': s} for s in item_j['item']['sessions']]
                    compatible, _ = es_item_compatible_amb_slot(item_i['item'], sessions_j, self.restriccions)
                    compat_matrix[i][j] = compatible
                    compat_matrix[j][i] = compatible

        # Ordenació: items més restringits primer; si shuffle_top_n > 1, barreja dins grups
        items_info.sort(key=lambda x: (len(x['slots_possibles']), x['millor_cost']))
        if shuffle_top_n > 0:
            from itertools import groupby
            shuffled_items = []
            for _, grp in groupby(items_info, key=lambda x: (len(x['slots_possibles']), x['millor_cost'])):
                g = list(grp)
                rng.shuffle(g)
                shuffled_items.extend(g)
            items_info = shuffled_items

        # Reasignar IDs després de l'ordenació
        for new_idx, it in enumerate(items_info):
            it['sorted_id'] = new_idx

        # Reconstruir matriu amb nous índexs
        new_compat = [[True] * num_items_valid for _ in range(num_items_valid)]
        for i, it_i in enumerate(items_info):
            for j, it_j in enumerate(items_info):
                old_i, old_j = it_i['id'], it_j['id']
                new_compat[i][j] = compat_matrix[old_i][old_j]
        compat_matrix = new_compat

        print(f"   ✅ {num_items_valid} items preparats")

        # =============================================================
        # FASE 3: Backtracking amb optimitzacions
        # =============================================================
        totes_solucions = []
        millor_c = [float('inf')]
        nodes = [0]
        deepest_deadend = [-1, None]  # [idx, label]

        # Estat mutable (undo/redo)
        slot_nivell_mask = {sk: 0 for sk in slots_disp}  # Bitmask de nivells ocupats per slot
        slot_items = {sk: [] for sk in slots_disp}       # Items assignats per slot (índexs)
        dia_sessions = defaultdict(list)    # keyed per dia-nom: usat per professor limit functions
        data_sessions = defaultdict(list)   # keyed per data ISO (o dia-nom si no hi ha ISO): usat per no_mateix_dia
        item_assigned_slot = [None] * num_items_valid     # Slot assignat a cada item

        # Forward Checking: slots encara possibles per cada item no assignat
        remaining_slots = [set(it['slots_possibles']) for it in items_info]

        def forward_check(assigned_idx: int, assigned_slot: str) -> List[Tuple[int, Set[str]]]:
            """
            Propaga restriccions després d'assignar un item.
            Retorna llista de (item_idx, slots_eliminats) per poder fer undo.
            """
            changes = []
            assigned_item = items_info[assigned_idx]
            assigned_mask = assigned_item['nivell_mask']
            assigned_prefix = assigned_slot[:assigned_slot.rfind('_')]
            assigned_dia, _ = _parse_prefix(assigned_prefix)  # nom del dia

            for other_idx in range(assigned_idx + 1, num_items_valid):
                if item_assigned_slot[other_idx] is not None:
                    continue  # Ja assignat

                other_item = items_info[other_idx]
                removed = set()

                # Si no són compatibles, eliminar el slot assignat
                if not compat_matrix[assigned_idx][other_idx]:
                    if assigned_slot in remaining_slots[other_idx]:
                        removed.add(assigned_slot)

                # no_mateix_dia: propagar restricció dura al FC
                sessions_al_dia_assigned = data_sessions.get(assigned_prefix, [])
                for s in other_item['item']['sessions']:
                    if viola_restriccio_dura(s, sessions_al_dia_assigned, self.restriccions):
                        for sk in list(remaining_slots[other_idx]):
                            if sk[:sk.rfind('_')] == assigned_prefix:
                                removed.add(sk)
                        break

                if removed:
                    remaining_slots[other_idx] -= removed
                    changes.append((other_idx, removed))

            return changes

        def undo_forward_check(changes: List[Tuple[int, Set[str]]]):
            """Desfà els canvis del forward checking."""
            for other_idx, removed in changes:
                remaining_slots[other_idx] |= removed

        def backtrack(idx: int, cost_ac: float):
            nodes[0] += 1
            if nodes[0] > max_nodes or cost_ac >= millor_c[0]:
                return

            if idx >= num_items_valid:
                # Solució trobada
                if cost_ac < millor_c[0]:
                    millor_c[0] = cost_ac
                    totes_solucions.clear()
                if cost_ac == millor_c[0] and len(totes_solucions) < max_solucions:
                    # Guardar còpia de l'estat actual
                    sol_slots = {}
                    for i, sk in enumerate(item_assigned_slot):
                        if sk is not None:
                            sol_slots.setdefault(sk, []).append(items_info[i])
                    totes_solucions.append((cost_ac, sol_slots))
                return

            it_info = items_info[idx]
            nivell_mask = it_info['nivell_mask']

            # Forward Checking: si no queden slots possibles, dead-end
            if not remaining_slots[idx]:
                if idx > deepest_deadend[0]:
                    deepest_deadend[0] = idx
                    deepest_deadend[1] = it_info['label']
                return

            # Ordenar slots per cost; els top-N es barregen per diversitat entre seeds
            slots_to_try = [(sk, it_info['tots_slots'].get(sk, float('inf')))
                           for sk in remaining_slots[idx]
                           if sk in it_info['tots_slots']]
            slots_to_try.sort(key=lambda x: x[1])
            if shuffle_top_n > 0:
                top_n = min(shuffle_top_n, len(slots_to_try))
                top = slots_to_try[:top_n]
                rng.shuffle(top)
                slots_to_try = top + slots_to_try[top_n:]

            for sk, base_cost in slots_to_try:
                # Verificar compatibilitat amb bitmask (O(1))
                if slot_nivell_mask[sk] & nivell_mask:
                    continue  # Conflicte de nivell

                # Verificar compatibilitat amb matriu pre-calculada
                compatible = True
                for existing_idx in slot_items[sk]:
                    if not compat_matrix[idx][existing_idx]:
                        compatible = False
                        break
                if not compatible:
                    continue

                # Verificar restriccions de dia
                prefix_s = sk[:sk.rfind('_')]
                dia_s, data_iso_s = _parse_prefix(prefix_s)  # nom del dia per restriccions
                # Sessions ja assignades al slot sk (per calcular no_mateix_slot)
                sessions_slot_ara = []
                for existing_idx in slot_items[sk]:
                    sessions_slot_ara.extend(items_info[existing_idx]['item']['sessions'])

                hora_s = sk[sk.rfind('_') + 1:]
                cost_extra = 0
                possible = True
                for s in it_info['item']['sessions']:
                    if engine.check_hard(
                        s, dia_s, hora_s, prefix_s,
                        data_sessions.get(prefix_s, []),
                        sessions_slot_ara,
                        dia_sessions,
                    ):
                        possible = False
                        break
                    cost_extra += self._calcular_penalitzacio_professors_dies(s, dia_s, dia_sessions)
                    pct_slot = percent_no_mateix_slot_violation(s, sessions_slot_ara, self.restriccions)
                    if pct_slot:
                        pesos_opt = self.restriccions.get('pesos_optimitzacio', {})
                        pes_d = pesos_opt.get('restriccio_dura', DEFAULT_PES_RESTRICCIO_DURA)
                        cost_extra += _percent_penalty(pes_d, pct_slot)

                if not possible:
                    continue

                new_cost = cost_ac + base_cost + cost_extra
                if new_cost >= millor_c[0]:
                    continue  # Poda

                # === ASSIGNAR (do) ===
                slot_nivell_mask[sk] |= nivell_mask
                slot_items[sk].append(idx)
                item_assigned_slot[idx] = sk
                for s in it_info['item']['sessions']:
                    dia_sessions[dia_s].append(s)
                    data_sessions[prefix_s].append(s)

                # Forward Checking
                fc_changes = forward_check(idx, sk)

                # Check dead-end després de FC
                dead_end = False
                for future_idx in range(idx + 1, num_items_valid):
                    if not remaining_slots[future_idx]:
                        dead_end = True
                        # Rastreja l'ítem que quedaria sense slots per FC
                        if future_idx > deepest_deadend[0]:
                            deepest_deadend[0] = future_idx
                            deepest_deadend[1] = items_info[future_idx]['label']
                        break

                if not dead_end:
                    backtrack(idx + 1, new_cost)

                # === DESASSIGNAR (undo) ===
                undo_forward_check(fc_changes)
                slot_nivell_mask[sk] ^= nivell_mask
                slot_items[sk].pop()
                item_assigned_slot[idx] = None
                for s in it_info['item']['sessions']:
                    dia_sessions[dia_s].pop()
                    data_sessions[prefix_s].pop()

            # Esgotament del bucle: cap slot vàlid per a idx en aquest context
            if idx > deepest_deadend[0]:
                deepest_deadend[0] = idx
                deepest_deadend[1] = it_info['label']

        backtrack(0, 0)

        if nodes[0] > max_nodes:
            print(f"   ⚠️ Límit de nodes assolit ({max_nodes}), backtrack tallat")
        print(f"   📊 Nodes explorats: {nodes[0]}, solucions trobades: {len(totes_solucions)}")
        # Si no hi ha solucions i hi ha un dead-end contextual, guardar-lo (Fase 3)
        if not totes_solucions and deepest_deadend[1] and not self._incompatibilitats_bt:
            label = deepest_deadend[1]
            # Detectar motiu estructural (sense context), igual que v3-SA
            deadend_item = next((ii for ii in items_info if ii['label'] == label), None)
            motiu = None
            if deadend_item:
                raons_dd: Counter = Counter()
                for sk in slots_disp:
                    _idx_sk = sk.rfind('_')
                    prefix_sk, h_sk = sk[:_idx_sk], sk[_idx_sk + 1:]
                    d_sk, _ = _parse_prefix(prefix_sk)
                    for s in deadend_item['item']['sessions']:
                        violation = engine.check_hard(s, d_sk, h_sk, prefix_sk, [], [], {})
                        if violation:
                            raons_dd[violation.label] += 1
                            break
                if raons_dd:
                    motiu = raons_dd.most_common(1)[0][0]
            msg = f"Cap slot per a '{label}'"
            if motiu:
                msg += f" — {motiu}"
            else:
                msg += " — conflicte entre restriccions"
            self._incompatibilitats_bt.append(msg)
        return totes_solucions

    def _construir_horari_desde_slots(self, slots_occ, data_inici, dies_utilitzar):
        from datetime import datetime as _dt2

        def _parse_prefix_local(prefix: str):
            try:
                dt = _dt2.strptime(prefix, "%Y-%m-%d")
                return _DIES_CAT[dt.weekday()], prefix
            except ValueError:
                return prefix, None

        selected = getattr(self, 'selected_dates', None) or []
        if selected:
            dies_iter = []
            for data_iso in selected:
                try:
                    dia_nom = _DIES_CAT[_dt2.strptime(data_iso, "%Y-%m-%d").weekday()]
                    dies_iter.append((dia_nom, data_iso, data_iso))
                except (ValueError, IndexError):
                    continue
        else:
            dies_iter = [(d, None, d) for d in dies_utilitzar]

        res_dies = []
        for dia_nom, data_iso, sk_prefix in dies_iter:
            di = {'dia': dia_nom, 'sessions': []}
            if data_iso:
                di['data'] = data_iso
            for h in self.hores_examen:
                sk = f"{sk_prefix}_{h}"
                its = slots_occ.get(sk, [])
                if its:
                    sim = []
                    all_s = []
                    for it in its:
                        all_s.extend(it['item']['sessions'])
                    for s in all_s:
                        sc = s.copy()
                        sc['analisi'] = self.analitzar_disponibilitat_sessio(
                            s, dia_nom, h, [x for x in all_s if x != s], data_iso=data_iso
                        )
                        sim.append(sc)
                    di['sessions'].append({'hora': h, 'sessions_simultanees': sim})
            res_dies.append(di)
        final = {'dies': res_dies, 'metadata': {'total_sessions': self.get_total_sessions_count(), 'data_inici': data_inici}}
        aplicar_estadistiques(final)
        return final

