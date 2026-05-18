"""
Motor de generació d'horaris V3 - Simulated Annealing (SA).
Versió corregida amb totes les restriccions i agrupament modular.
"""

import math
import re
import random
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Set, Optional, Any, Union
from collections import defaultdict
from copy import deepcopy

from scheduler_engine.core.normalitzacio import normalitzar_dia, normalitzar_text, nom_base_assignatura
from scheduler_engine.core.date_mapping import construir_mapa_dia_data_iso, DIES_CAT as _DIES_CAT
from scheduler_engine.core.constraints import (
    sessio_matches, sessio_in_group, get_restriccio_val,
    viola_restriccio_dia_hora_fixos,
    es_item_compatible_amb_slot, es_slot_valid_per_nivell
)
from scheduler_engine.core.availability import analitzar_disponibilitat_sessio
from scheduler_engine.core.scoring import calcular_cost_slot
from scheduler_engine.core.constraints import _percent_penalty
from scheduler_engine.defaults import (
    DEFAULT_SA_PARAMS, DEFAULT_COST_PROFESSORS,
    DEFAULT_PES_RESTRICCIO_DURA, DEFAULT_PES_RESTRICCIO_PROHIBITIU,
    DEFAULT_PES_ZONA_EXAMEN,
)
from scheduler_engine.generators.base import GeneradorSessionsExamensBase
from scheduler_engine.estadistiques import aplicar_estadistiques
from scheduler_engine.domain.models import Sessio, Item, Slot
from scheduler_engine.core.restriction_engine import RestrictionEngine


@dataclass
class Restriccio:
    tipus: str
    pes: int  
    dades: Dict = field(default_factory=dict)

    @property
    def es_dura(self) -> bool: return self.pes >= 100


@dataclass
class Solucio:
    assignacions: Dict[str, Slot]  # item_id -> Slot
    cost: float = 0.0
    violacions: List[Dict] = field(default_factory=list)
    cost_per_slot: Dict[str, float] = field(default_factory=dict)  # slot_key -> cost
    cost_global: float = 0.0  # cost de restriccions globals (pref_mateix_slot, no_mateix_dia...)


# =============================================================================
# MOTOR PRINCIPAL
# =============================================================================

class GeneradorV3SA(GeneradorSessionsExamensBase):
    """Motor de generació d'horaris d'exàmens amb Simulated Annealing"""

    def __init__(self, config_examens_path: str, horari_xml_path: str,
                 restriccions_path: str = None, ultim_professor: str = "",
                 nivells_actius: List[str] = None, hores_examen: List[str] = None,
                 hores_per_nivell: dict = None,
                 durada_titular: int = 1, no_substituir: set = None,
                 alliberaments_per_nivell: dict = None,
                 durades_per_sessio: dict = None,
                 durades_examen_per_sessio: dict = None):

        super().__init__(config_examens_path, horari_xml_path, restriccions_path,
                         ultim_professor, nivells_actius, hores_examen,
                         hores_per_nivell, durada_titular, no_substituir,
                         alliberaments_per_nivell, durades_per_sessio,
                         durades_examen_per_sessio)

        self.restriccions_raw = {}
        self.sessions: List[Sessio] = []
        self.sessions_per_id: Dict[str, Sessio] = {}
        self.slots: List[Slot] = []
        self.items: List[Item] = []
        self.items_per_id: Dict[str, Item] = {}
        self.sessio_item_map: Dict[str, Dict[str, str]] = {}
        self.restriccions_obj: List[Restriccio] = []
        self.no_substituir_norm = {normalitzar_text(a) for a in self.no_substituir if a}
        self._sessio_dict_cache: Dict[str, Dict] = {}

        self.temperatura_inicial = DEFAULT_SA_PARAMS["temperatura_inicial"]
        self.temperatura_final = DEFAULT_SA_PARAMS["temperatura_final"]
        self.factor_refredament = DEFAULT_SA_PARAMS["factor_refredament"]
        self.iteracions_per_temperatura = DEFAULT_SA_PARAMS["iteracions_per_temperatura"]
        self.max_iteracions = DEFAULT_SA_PARAMS["max_iteracions"]
        self.intents_solucio_inicial = DEFAULT_SA_PARAMS.get("intents_solucio_inicial", 50)

    def _check_fixos_viables(self) -> List[str]:
        """Comprova que les assignatures amb dia/hora fix tenen algun slot disponible."""
        restriccions = self.get_restriccions()
        dures = restriccions.get('restriccions_dures', {})
        dia_fix = dures.get('assignatures_dia_fix', {}) or {}
        hora_fix = dures.get('assignatures_hora_fix', {}) or {}
        if not dia_fix and not hora_fix:
            return []

        import re as _re
        _re_iso = _re.compile(r'^\d{4}-\d{2}-\d{2}$')
        slots_set_dia = {(normalitzar_dia(s.dia), s.hora) for s in self.slots}
        slots_set_iso = {(s.data, s.hora) for s in self.slots if s.data}
        days_set = {normalitzar_dia(s.dia) for s in self.slots}
        iso_set = {s.data for s in self.slots if s.data}
        hours_set = {s.hora for s in self.slots}

        missing: List[str] = []
        for s in self.sessions:
            s_dict = self._sessio_to_dict(s)
            d = get_restriccio_val(dia_fix, s_dict)
            h = get_restriccio_val(hora_fix, s_dict)
            if d:
                is_iso = bool(_re_iso.match(str(d)))
                if is_iso:
                    if d not in iso_set:
                        missing.append(f"{s_dict.get('nom')} -> data {d} no disponible")
                        continue
                    if h and (d, h) not in slots_set_iso:
                        missing.append(f"{s_dict.get('nom')} -> {d} {h} no és un slot disponible")
                else:
                    d_norm = normalitzar_dia(d)
                    if d_norm not in days_set:
                        missing.append(f"{s_dict.get('nom')} -> dia {d_norm} no disponible")
                        continue
                    if h and (d_norm, h) not in slots_set_dia:
                        missing.append(f"{s_dict.get('nom')} -> {d_norm} {h} no és un slot disponible")
            elif h and h not in hours_set:
                missing.append(f"{s_dict.get('nom')} -> hora {h} no disponible")
        return missing

    def carregar_dades(self):
        self._carregar_config()
        for curs in self.nivells_actius:
            for assignatura_nom, dades in self.config.get('assignatures', {}).items():
                examens = [a for a in dades.get('assignacions', []) if curs in a['grup']]
                if examens:
                    sid = f"{assignatura_nom}_{curs}"
                    s = Sessio(id=sid, nom=f"{assignatura_nom} ({curs})", nom_base=assignatura_nom, curs=curs, examens=examens)
                    self.sessions.append(s); self.sessions_per_id[sid] = s
                    sessio_dict = {
                        'id': sid,
                        'nom': f"{assignatura_nom} ({curs})",
                        'nom_base': assignatura_nom,
                        'curs': curs,
                        'examens': examens,
                    }
                    self.sessions_per_nivell.setdefault(curs, []).append(sessio_dict)
        self.restriccions_raw = self._carregar_restriccions_raw()
        self._processar_restriccions()

    def _processar_restriccions(self):
        self.restriccions_obj = []
        dures = self.restriccions_raw.get('restriccions_dures', {})
        prefs = self.restriccions_raw.get('preferencies', {})
        pesos = self.restriccions_raw.get('pesos_percentatge', {})
        costos_profs = self.restriccions_raw.get('costos_professors', {})

        # Mapejat a objectes Restriccio per al SA
        for grup in dures.get('mateix_slot', []):
            p = grup.get('pes', 100) if isinstance(grup, dict) else 100
            a = grup.get('assignatures', []) if isinstance(grup, dict) else grup
            self.restriccions_obj.append(Restriccio('mateix_slot', p, {'assignatures': a}))
            
        for key, grup in dures.get('no_mateix_slot', {}).items():
            if not key.startswith('_'):
                self.restriccions_obj.append(Restriccio('no_mateix_slot', dures.get(f'_pes_{key}', 100), {'assignatures': grup}))
                
        for grup in dures.get('no_mateix_dia', []):
            self.restriccions_obj.append(Restriccio('no_mateix_dia', 100, {'assignatures': grup}))
        
        for assig, dia in dures.get('assignatures_dia_fix', {}).items():
            if not assig.startswith('_'):
                self.restriccions_obj.append(Restriccio('dia_fix', 100, {'assignatura': assig, 'dia': normalitzar_dia(dia)}))
        
        for assig, hora in dures.get('assignatures_hora_fix', {}).items():
            if not assig.startswith('_'):
                self.restriccions_obj.append(Restriccio('hora_fix', 100, {'assignatura': assig, 'hora': hora}))

        for grup in prefs.get('dies_diferents', []):
            p = grup.get('pes', 75) if isinstance(grup, dict) else 75
            self.restriccions_obj.append(Restriccio('dies_diferents', p, {'assignatures': grup.get('assignatures', []) if isinstance(grup, dict) else grup}))
        
        for grup in prefs.get('mateix_dia', []):
            p = grup.get('pes', 50) if isinstance(grup, dict) else 50
            self.restriccions_obj.append(Restriccio('pref_mateix_dia', p, {'assignatures': grup.get('assignatures', []) if isinstance(grup, dict) else grup}))

        for grup in prefs.get('mateix_slot', []):
            p = grup.get('pes', 75) if isinstance(grup, dict) else 75
            self.restriccions_obj.append(Restriccio('pref_mateix_slot', p, {'assignatures': grup.get('assignatures', []) if isinstance(grup, dict) else grup}))

        # Combinacions i restriccions especials
        combs = dures.get('combinacions_permeses', [])
        combinacions = [c.get('assignatures', []) if isinstance(c, dict) else c for c in combs]
        # Restricció crítica: Combinacions Permeses / Un sol slot per nivell
        # Si no hi ha combinacions, enforce_single=True per defecte
        enforce_single = True 
        if combinacions:
            enforce_single = True # També volem que si no estan a la llista, no es puguin ajuntar
            
        self.restriccions_obj.append(Restriccio('combinacions_permeses', 100, {'combinacions': combinacions, 'enforce_single': enforce_single}))

        pe = dures.get('professors_horari_estricte', [])
        self.professors_estrictes = list(pe.keys()) if isinstance(pe, dict) else pe

        limits = dures.get('professors_limit_dies_especifics', {})
        if isinstance(limits, dict):
            for prof, cfg in limits.items():
                if not str(prof).startswith('_') and cfg.get('max_examens') is not None:
                    self.restriccions_obj.append(Restriccio(tipus='limit_dies_prof', pes=int(cfg.get('pes_penalitzacio', 50)),
                        dades={'professor': prof, 'assignatures': cfg.get('assignatures', []), 'dies': cfg.get('dies_restringits', []), 'max_examens': int(cfg['max_examens'])}))

        cp = costos_profs.get('globals', {}) if costos_profs else pesos
        self.pes_substitucio_global = cp.get('substitucio', DEFAULT_COST_PROFESSORS["substitucio"])
        self.pes_abans_jornada_global = cp.get('abans_jornada', DEFAULT_COST_PROFESSORS["abans_jornada"])
        self.pes_despres_jornada_global = cp.get('despres_jornada', DEFAULT_COST_PROFESSORS["despres_jornada"])
        self.pes_no_treballa_global = cp.get('no_treballa_dia', DEFAULT_COST_PROFESSORS["no_treballa_dia"])
        self.costos_professors_individuals = costos_profs.get('individuals', {}) if costos_profs else {}

    def crear_slots(self, dies_utilitzar: List[str]):
        from datetime import datetime as _dt
        self.slots = []
        bloq = {r.dades['slot'] for r in self.restriccions_obj if r.tipus == 'slot_bloquejat'}
        selected = getattr(self, 'selected_dates', None) or []
        if selected:
            for data_iso in selected:
                try:
                    dia_nom = _DIES_CAT[_dt.strptime(data_iso, "%Y-%m-%d").weekday()]
                except (ValueError, IndexError):
                    continue
                for hora in self.hores_examen:
                    if f"{dia_nom}-{hora}" not in bloq:
                        self.slots.append(Slot(dia=dia_nom, hora=hora, data=data_iso))
        else:
            for dia in dies_utilitzar:
                for hora in self.hores_examen:
                    if f"{dia}-{hora}" not in bloq:
                        self.slots.append(Slot(dia=dia, hora=hora))

    def _pre_agrupar_sessions(self):
        """Agrupa sessions en items usant la lògica unificada de la base."""
        print("🔗 Pre-agrupant sessions (SA)...")
        sessions_per_nivell = {}
        id_to_sessio = {}
        for s in self.sessions:
            d = {'id': s.id, 'nom': s.nom, 'nom_base': s.nom_base, 'curs': s.curs, 'examens': s.examens}
            sessions_per_nivell.setdefault(s.curs, []).append(d)
            id_to_sessio[s.id] = s

        items_dict = []
        counts_per_nivell = {}
        grups_amb_noms = self._get_mateix_slot_grups_amb_noms()
        grups_ms_amb_noms = [
            (g.get('nom', ''), {normalitzar_text(n) for n in g.get('assignatures', [])})
            for g in grups_amb_noms if g.get('assignatures')
        ]
        def _strip_count(label: str) -> str:
            if not label:
                return label
            return re.sub(r"\s*\(\d+\s*assig.*\)$", "", label, flags=re.IGNORECASE).strip()
        def _label_from_group(sessions: List[Dict]) -> Optional[str]:
            if not sessions or not grups_ms_amb_noms:
                return None
            for nom_grup, grup_set in grups_ms_amb_noms:
                if not nom_grup:
                    continue
                if all(
                    normalitzar_text(s.get('nom', '')) in grup_set
                    or normalitzar_text(s.get('nom_base', '')) in grup_set
                    for s in sessions
                ):
                    return nom_grup
            return None

        for nivell, sessions_dict in sessions_per_nivell.items():
            items_nivell = self._construir_items_mateix_slot(sessions_dict)
            counts_per_nivell[nivell] = len(items_nivell)
            items_dict.extend(items_nivell)

        self.sessio_item_map = {}
        for it_d in items_dict:
            label_from_group = _label_from_group(it_d.get('sessions', []))
            if label_from_group:
                it_d['nom'] = label_from_group
                it_d['item_label'] = label_from_group
            else:
                it_d['nom'] = _strip_count(it_d.get('nom', ''))
                it_d['item_label'] = _strip_count(it_d.get('item_label', it_d.get('nom', '')))
            item_id = it_d.get('item_id') or it_d.get('nom')
            item_label = it_d.get('item_label') or it_d.get('nom')
            for s in it_d.get('sessions', []):
                sid = s.get('id')
                if sid and item_id:
                    self.sessio_item_map[sid] = {
                        'item_id': item_id,
                        'item_label': item_label,
                    }

        self.items = []
        for it_d in items_dict:
            sessions_obj = [id_to_sessio[s['id']] for s in it_d['sessions']]
            self.items.append(Item(id=it_d.get('nom', f"group_{len(self.items)}"), sessions=sessions_obj))
        self.items_per_id = {it.id: it for it in self.items}

        # Pre-computar tots els dicts de sessió (evita reconstruir-los milions de vegades)
        self._sessio_dict_cache: Dict[str, Dict] = {}
        for s in self.sessions:
            item_info = self.sessio_item_map.get(s.id, {})
            self._sessio_dict_cache[s.id] = {
                'id': s.id,
                'nom': s.nom,
                'nom_base': s.nom_base,
                'curs': s.curs,
                'examens': s.examens,
                'item_id': item_info.get('item_id'),
                'item_label': item_info.get('item_label'),
            }

        # Viabilitat per nivell: cada nivell ha de cabre en els slots disponibles
        return all(count <= len(self.slots) for count in counts_per_nivell.values())

    def _sessio_to_dict(self, s: Sessio) -> Dict:
        return self._sessio_dict_cache.get(s.id) or {
            'id': s.id,
            'nom': s.nom,
            'nom_base': s.nom_base,
            'curs': s.curs,
            'examens': s.examens,
        }

    def _item_to_dict(self, item: Item) -> Dict:
        return {
            'sessions': [self._sessio_to_dict(s) for s in item.sessions]
        }

    def _build_compat_precomp(self, sol: Solucio, exclude_item_id: str) -> Dict:
        """Pre-computa les taules de lookup per a _slot_compatible (O(N) una vegada)."""
        slot_sessions: Dict[str, List] = defaultdict(list)     # slot_key → [{'sessio': dict}]
        dia_sessions: Dict[str, List] = defaultdict(list)      # dia_key → [dict]  (totes les sessions del dia)
        for iid, sl in sol.assignacions.items():
            if iid == exclude_item_id:
                continue
            it = self.items_per_id[iid]
            dia_key = sl.data if sl.data else normalitzar_dia(sl.dia)
            for s in it.sessions:
                sd = self._sessio_to_dict(s)
                slot_sessions[sl.key].append({'sessio': sd})
                dia_sessions[dia_key].append(sd)
        return {'slot_sessions': slot_sessions, 'dia_sessions': dia_sessions}

    def _slot_compatible(self, sol: Solucio, item: Item, slot: Slot,
                         _precomp: Optional[Dict] = None) -> bool:
        """Respecta la regla d'or: un sol ítem per nivell al mateix slot.
        Si _precomp és present, usa les taules pre-computades (evita O(N) per crida)."""
        if _precomp is not None:
            slot_date_id = slot.data if slot.data else normalitzar_dia(slot.dia)
            sessions_al_slot = _precomp['slot_sessions'].get(slot.key, [])
            # sessions_dia inclou TOTES les sessions del dia (incloses les del slot candidat).
            # Necessari per a no_mateix_dia: si dues assignatures del grup estan al mateix slot,
            # viola igualment (el slot implica el mateix dia).
            sessions_dia = _precomp['dia_sessions'].get(slot_date_id, [])
            sessions_per_dia = _precomp['dia_sessions']
        else:
            sessions_al_slot = []
            sessions_dia = []
            sessions_per_dia = defaultdict(list)
            for iid, sl in sol.assignacions.items():
                if iid == item.id:
                    continue
                if sl.key != slot.key:
                    sl_date_id = sl.data if sl.data else normalitzar_dia(sl.dia)
                    slot_date_id = slot.data if slot.data else normalitzar_dia(slot.dia)
                    if sl_date_id == slot_date_id:
                        it_dia = self.items_per_id[iid]
                        for s in it_dia.sessions:
                            sessions_dia.append(self._sessio_to_dict(s))
                    it_pd = self.items_per_id[iid]
                    _dia_key_sl = sl.data if sl.data else normalitzar_dia(sl.dia)
                    for s in it_pd.sessions:
                        sessions_per_dia[_dia_key_sl].append(self._sessio_to_dict(s))
                    continue
                it = self.items_per_id[iid]
                for s in it.sessions:
                    sessions_al_slot.append({'sessio': self._sessio_to_dict(s)})
            # Les sessions del slot candidat (d'altri) compten per a no_mateix_dia i limit_dies.
            dia_key_slot = slot.data if slot.data else normalitzar_dia(slot.dia)
            for s_info in sessions_al_slot:
                sd = s_info['sessio']
                sessions_dia.append(sd)
                sessions_per_dia[dia_key_slot].append(sd)
        restriccions = self.get_restriccions()
        ok, _ = es_item_compatible_amb_slot(self._item_to_dict(item), sessions_al_slot, restriccions)
        if not ok:
            return False

        # Restriccions dures: dia/hora fixos, no_mateix_dia, combinacions_permeses,
        # limit_dies_professor, preferencia_dia, professors_estrictes
        engine = getattr(self, 'engine', None) or RestrictionEngine(self.get_restriccions(), self.nivells_actius)
        sessions_slot_dicts = [x['sessio'] for x in sessions_al_slot]
        prefix = slot.data or slot.dia

        for s in item.sessions:
            s_dict = self._sessio_to_dict(s)
            analisi = None
            if engine.professors_estrictes:
                _dates = getattr(self, 'dia_a_data_iso', {}).get(normalitzar_dia(slot.dia))
                data_iso = slot.data or (_dates[0] if isinstance(_dates, list) else _dates)
                durada_sessio = self.get_durada_per_sessio_key(s_dict.get('nom'), s_dict.get('curs'))
                analisi = analitzar_disponibilitat_sessio(
                    sessio=s_dict,
                    dia=slot.dia,
                    hora=slot.hora,
                    horaris_professors=self.horaris_professors,
                    totes_hores=self.totes_hores,
                    nivells_actius=self.nivells_actius,
                    durada_titular=durada_sessio,
                    no_substituir_norm=self.no_substituir_norm,
                    sessions_al_slot=sessions_al_slot,
                    alliberaments_per_nivell=self.alliberaments_per_nivell,
                    data_iso=data_iso,
                    horaris_professors_norm=getattr(self, '_horaris_norm', None),
                )
            if engine.check_hard(
                s_dict, slot.dia, slot.hora, prefix,
                sessions_dia, sessions_slot_dicts,
                sessions_per_dia, analisi
            ):
                return False
        return True

    def _calcular_cost_slot_unic(self, slot_key: str, items_al_slot: List[Item],
                                   sessions_per_dia: Dict[str, List[Dict]]) -> Tuple[float, List[Dict]]:
        """Calcula el cost d'un únic slot. Retorna (cost, violacions)."""
        if not items_al_slot:
            return 0.0, []

        from datetime import datetime as _dt
        restriccions = self.get_restriccions()
        prefix, hora = slot_key.split('_', 1)
        # El prefix pot ser data ISO ("2026-02-03") o nom de dia ("Dilluns")
        try:
            dia_nom = _DIES_CAT[_dt.strptime(prefix, "%Y-%m-%d").weekday()]
            data_iso = prefix
        except ValueError:
            dia_nom = prefix
            _dates = getattr(self, 'dia_a_data_iso', {}).get(normalitzar_dia(prefix))
            data_iso = _dates[0] if isinstance(_dates, list) else _dates
        dia_norm = normalitzar_dia(dia_nom)
        # Clau consistent amb calcular_cost: data ISO si disponible
        dia_key = data_iso if data_iso else dia_norm
        sessions_dia = sessions_per_dia.get(dia_key, [])

        # Construir llista de sessions al slot
        sess_list = []
        for it in items_al_slot:
            for s in it.sessions:
                sess_list.append(self._sessio_to_dict(s))

        cost_slot = 0.0
        violacions_slot = []

        for sessio in sess_list:
            altres = [s for s in sess_list if s is not sessio]
            # data_iso ja derivat del prefix
            nom = sessio.get('nom')
            curs = sessio.get('curs')
            durada_supervisio = self.get_durada_per_sessio_key(nom, curs)
            durada_exam = self.get_durada_examen_per_sessio_key(nom, curs)
            # Calcular finestres de supervisió i examen
            hora_norm = hora
            if hora_norm in self.totes_hores:
                idx = self.totes_hores.index(hora_norm)
                hores_sup = self.totes_hores[idx:min(idx + durada_supervisio, len(self.totes_hores))]
                hores_exam = self.totes_hores[idx:min(idx + durada_exam, len(self.totes_hores))]
            else:
                hores_sup = [hora_norm]
                hores_exam = [hora_norm]
            analisi = analitzar_disponibilitat_sessio(
                sessio=sessio,
                dia=dia_nom,
                hora=hora,
                horaris_professors=self.horaris_professors,
                totes_hores=self.totes_hores,
                nivells_actius=self.nivells_actius,
                durada_titular=durada_supervisio,
                no_substituir_norm=self.no_substituir_norm,
                sessions_al_slot=[{'sessio': s} for s in altres],
                hores_override=hores_exam,
                hores_supervisio=hores_sup,
                alliberaments_per_nivell=self.alliberaments_per_nivell,
                data_iso=data_iso,
                horaris_professors_norm=getattr(self, '_horaris_norm', None),
            )
            resultat = calcular_cost_slot(
                sessio=sessio,
                dia=dia_nom,
                hora=hora,
                analisi=analisi,
                restriccions=restriccions,
                sessions_dia=sessions_dia,
                sessions_slot=altres,
                data_iso=data_iso,
            )
            cost_slot += resultat.get('cost_total', 0)
            # Soft cost per conflictes a zona examen (guia SA cap a slots nets)
            zona_examen_pairs = {(i['professor'], i.get('hora', hora)) for i in analisi.get('zona_examen', [])}
            zona_examen_count = len(zona_examen_pairs)
            cost_slot += zona_examen_count * DEFAULT_PES_ZONA_EXAMEN
            for p in resultat.get('professors_estrictes_violats', []):
                violacions_slot.append({
                    'tipus': 'professor_estricte',
                    'pes': resultat.get('cost_total', 0),
                    'missatge': f"{p} horari estricte violat"
                })

        return cost_slot, violacions_slot

    def calcular_cost(self, sol: Solucio) -> Tuple[float, List[Dict]]:
        """Calcula el cost total usant el scoring unificat del core."""
        cost_total = 0.0
        violacions: List[Dict] = []
        sol.cost_per_slot = {}

        # Agrupar items per slot i sessions per dia
        # Clau de dia: data ISO si disponible (evita confondre dos dimarts de setmanes diferents)
        items_per_slot: Dict[str, List[Item]] = defaultdict(list)
        sessions_per_dia: Dict[str, List[Dict]] = defaultdict(list)
        for iid, slot in sol.assignacions.items():
            it = self.items_per_id[iid]
            items_per_slot[slot.key].append(it)
            dia_key = slot.data if slot.data else normalitzar_dia(slot.dia)
            for s in it.sessions:
                sessions_per_dia[dia_key].append(self._sessio_to_dict(s))

        for slot_key, items_slot in items_per_slot.items():
            cost_slot, viols_slot = self._calcular_cost_slot_unic(slot_key, items_slot, sessions_per_dia)
            sol.cost_per_slot[slot_key] = cost_slot
            cost_total += cost_slot
            violacions.extend(viols_slot)

        # Restriccions globals (no per slot): pref_mateix_slot
        # Nota: no_mateix_dia i combinacions_permeses ja es compten al cost per slot
        cost_global = 0.0
        for r in self.restriccions_obj:
            if r.tipus == 'pref_mateix_slot':
                c, v = self._avaluar_restriccio(sol, r)
                cost_global += c
                violacions.extend(v)
        sol.cost_global = cost_global
        cost_total += cost_global

        return cost_total, violacions

    def _avaluar_restriccio(self, sol: Solucio, r: Restriccio) -> Tuple[float, List[Dict]]:
        if r.tipus == 'dia_fix':
            for iid, sl in sol.assignacions.items():
                it = self.items_per_id[iid]
                if any(sessio_matches(r.dades['assignatura'], s) for s in it.sessions):
                    if normalitzar_dia(sl.dia) != r.dades['dia']:
                        return float(DEFAULT_PES_RESTRICCIO_DURA), [{'tipus': 'dia_fix', 'pes': 100, 'missatge': f"{r.dades['assignatura']} vol {r.dades['dia']}"}]
        
        if r.tipus == 'hora_fix':
            for iid, sl in sol.assignacions.items():
                it = self.items_per_id[iid]
                if any(sessio_matches(r.dades['assignatura'], s) for s in it.sessions):
                    if sl.hora != r.dades['hora']:
                        return float(DEFAULT_PES_RESTRICCIO_DURA), [{'tipus': 'hora_fix', 'pes': 100, 'missatge': f"{r.dades['assignatura']} vol {r.dades['hora']}"}]

        if r.tipus == 'no_mateix_dia':
            cost = 0.0; viols = []
            per_dia = defaultdict(list)
            for iid, sl in sol.assignacions.items(): per_dia[normalitzar_dia(sl.dia)].append(self.items_per_id[iid])
            for d, its in per_dia.items():
                sessions_d = [s for it in its for s in it.sessions]
                for s in sessions_d:
                    if sessio_in_group(s, r.dades['assignatures']):
                        altres = [x for x in sessions_d if x != s and sessio_in_group(x, r.dades['assignatures'])]
                        if altres:
                            cost += float(DEFAULT_PES_RESTRICCIO_DURA); viols.append({'tipus': 'no_mateix_dia', 'pes': 100, 'missatge': f"MATEIX DIA PROHIBIT: {s.nom}"})
            return cost / 2, viols # Deduplicar parelles

        if r.tipus == 'combinacions_permeses':
            return self._avaluar_combinacions_permeses(sol, r)

        if r.tipus == 'mateix_slot':
            return 0.0, []

        if r.tipus == 'pref_mateix_slot':
            assignatures_norm = {normalitzar_text(a) for a in r.dades.get('assignatures', [])}
            # Recollir els slots on estan els ítems del grup
            slots_grup = set()
            for it in self.items:
                if any(
                    normalitzar_text(s.nom) in assignatures_norm
                    or normalitzar_text(s.nom_base) in assignatures_norm
                    for s in it.sessions
                ):
                    if it.id in sol.assignacions:
                        slots_grup.add(sol.assignacions[it.id].key)
            if len(slots_grup) > 1:
                pes = r.pes
                n_viols = len(slots_grup) - 1
                if pes >= 100:
                    cost = float(DEFAULT_PES_RESTRICCIO_PROHIBITIU) * n_viols
                else:
                    cost = float(_percent_penalty(DEFAULT_PES_RESTRICCIO_DURA, pes)) * n_viols
                return cost, [{'tipus': 'pref_mateix_slot', 'pes': pes, 'missatge': f"Slots separats: {r.dades.get('assignatures')}"}]
            return 0.0, []

        return 0.0, []

    def _avaluar_combinacions_permeses(self, sol, r):
        cost, viols = 0.0, []
        
        # Agrupar items assignats per slot
        items_per_slot = defaultdict(list)
        for iid, s in sol.assignacions.items():
            items_per_slot[s.key].append(self.items_per_id[iid])
            
        for slot_key, its_in_slot in items_per_slot.items():
            # Per cada ítem al slot, comprovar si és compatible amb la resta
            for i, it in enumerate(its_in_slot):
                altres = its_in_slot[:i] + its_in_slot[i+1:]
                # Convertir llista d'items a llista de sessions_info compatible amb el helper
                # (El helper espera List[Dict] amb clau 'sessio' o directament sessions)
                # Creem una versió mínima que el helper entengui
                sessions_al_slot = []
                for other_it in altres:
                    for s in other_it.sessions:
                        sessions_al_slot.append({'sessio': s, 'curs': s.curs})
                
                # RESTRICCIÓ MANDATÒRIA via helper
                # Convertim el nostre Item (objecte) a format Dict per al helper
                it_dict = {'sessions': [{'curs': s.curs} for s in it.sessions]}
                compatible, msg = es_item_compatible_amb_slot(it_dict, sessions_al_slot, self.restriccions_raw)
                
                if not compatible:
                    cost += float(DEFAULT_PES_RESTRICCIO_PROHIBITIU) # Cost prohibitiu (mandatori, no negociable)
                    viols.append({'tipus': 'conflict_alumnes', 'pes': 1000, 'missatge': f"CONFLICTE ALUMNES: {it.sessions[0].curs} duplicat a {slot_key}"})
                    break # Ja hem detectat el conflicte en aquest slot
                        
        return cost, viols

    def _avaluar_costos_professors(self, sol: Solucio) -> Tuple[float, List[Dict]]:
        cost, violacions = 0.0, []
        seen = set() # Evitar duplicats
        
        for iid, slot in sol.assignacions.items():
            it = self.items_per_id[iid]
            for s in it.sessions:
                dn, hr = normalitzar_dia(slot.dia), slot.hora
                # slot.data té la data ISO concreta; fallback al mapa (List[str])
                if slot.data:
                    data_iso = slot.data
                else:
                    _dates = getattr(self, 'dia_a_data_iso', {}).get(dn)
                    data_iso = _dates[0] if isinstance(_dates, list) else _dates
                # Construir objecte sessió dict compatible amb core
                s_dict = {'nom': s.nom, 'nom_base': s.nom_base, 'examens': s.examens}
                durada_sessio = self.get_durada_per_sessio_key(s.nom, s.curs)
                an = analitzar_disponibilitat_sessio(
                    sessio=s_dict, dia=dn, hora=hr,
                    horaris_professors=self.horaris_professors,
                    totes_hores=self.totes_hores,
                    nivells_actius=self.nivells_actius,
                    durada_titular=durada_sessio,
                    no_substituir_norm=self.no_substituir_norm,
                    alliberaments_per_nivell=self.alliberaments_per_nivell,
                    data_iso=data_iso
                )
                
                # Mapejar resultats core a costos SA
                # No treballa
                for x in an['no_treballa_dia']:
                    k = (x['professor'], dn, 'nt')
                    if k not in seen:
                        seen.add(k); p = self._get_cost_professor(x['professor'], 'no_treballa_dia'); cost += p
                        violacions.append({'tipus': 'nt', 'pes': p, 'missatge': f"{x['professor']} NT {dn}"})
                # Sub
                for x in an['substitucions']:
                    k = (x['professor'], dn, x['hora'], 'sub')
                    if k not in seen:
                        seen.add(k); p = self._get_cost_professor(x['professor'], 'substitucio'); cost += p
                        violacions.append({'tipus': 'sub', 'pes': p, 'missatge': f"{x['professor']} SUB {x['hora']}"})
                # Abans
                for x in an['abans_jornada']:
                    k = (x['professor'], dn, 'ab')
                    if k not in seen:
                        seen.add(k); p = self._get_cost_professor(x['professor'], 'abans_jornada'); cost += p
                        violacions.append({'tipus': 'ab', 'pes': p, 'missatge': f"{x['professor']} ABANS"})
                # Despres
                for x in an['despres_jornada']:
                    k = (x['professor'], dn, 'de')
                    if k not in seen:
                        seen.add(k); p = self._get_cost_professor(x['professor'], 'despres_jornada'); cost += p
                        violacions.append({'tipus': 'de', 'pes': p, 'missatge': f"{x['professor']} DESPRES"})
                        
        return cost, violacions

    def _get_cost_professor(self, prof, t):
        if prof in self.costos_professors_individuals and t in self.costos_professors_individuals[prof]: return self.costos_professors_individuals[prof][t]
        m = {'substitucio': self.pes_substitucio_global, 'abans_jornada': self.pes_abans_jornada_global, 'despres_jornada': self.pes_despres_jornada_global, 'no_treballa_dia': self.pes_no_treballa_global}
        return m.get(t, 50)

    def _detectar_items_congelats(self):
        """Pre-computa els ítems que tenen exactament 1 slot compatible (fixats per restricció).
        Guarda l'únic slot per als ítems congelats per evitar recalcular-lo després."""
        sol_buida = Solucio(assignacions={})
        self.items_mobils = []
        self.items_congelats_ids = set()
        self._slot_congelat_per_item: Dict[str, Optional[Slot]] = {}
        for it in self.items:
            compat = [s for s in self.slots if self._slot_compatible(sol_buida, it, s)]
            if len(compat) <= 1:
                self.items_congelats_ids.add(it.id)
                self._slot_congelat_per_item[it.id] = compat[0] if compat else None
            else:
                self.items_mobils.append(it)

    def _precalcular_slots_candidats(self):
        """Pre-filtra els slots estàticament vàlids per a cada ítem mòbil (s'executa una vegada)."""
        restriccions = self.get_restriccions()
        self._slots_candidats_per_item = {}
        items_per_pre = self.items_mobils if hasattr(self, 'items_mobils') and self.items_mobils else self.items
        for it in items_per_pre:
            candidats = []
            for s in self.slots:
                passes = True
                for sess in it.sessions:
                    s_dict = self._sessio_to_dict(sess)
                    if not es_slot_valid_per_nivell(
                        s_dict.get('nom', ''), s.dia, s.hora, restriccions,
                        self.nivells_actius, curs=s_dict.get('curs', ''), data_iso=s.data or ''
                    ):
                        passes = False; break
                    if viola_restriccio_dia_hora_fixos(
                        s_dict, s.dia, s.hora, restriccions, self.nivells_actius, s.data or ''
                    ):
                        passes = False; break
                if passes:
                    candidats.append(s)
            self._slots_candidats_per_item[it.id] = candidats if candidats else self.slots

    def executar_simulated_annealing(self, verbose=True, reinicis=3):
        """Executa l'algorisme de Simulated Annealing amb múltiples reinicis."""
        self._detectar_items_congelats()
        n_con = len(self.items_congelats_ids)
        n_mob = len(self.items_mobils)
        if verbose:
            print(f"🔥 Iniciant Simulated Annealing ({reinicis} reinicis)... [{n_con} fixats, {n_mob} mòbils]")

        # Cas ràpid: sense ítems mòbils → construir solució directament dels slots ja calculats
        if n_mob == 0:
            if verbose:
                print("   ⚡ Tot fixat: construint solució directament (sense SA)")
            sol = Solucio(assignacions={})
            for it in self.items:
                slot = self._slot_congelat_per_item.get(it.id)
                if slot is None:
                    if verbose:
                        print(f"   ✗ Infactible: cap slot per a '{it.id}'")
                    self._item_infactible = it
                    return None
                # Comprovar restriccions dures contra els ítems ja assignats
                if not self._slot_compatible(sol, it, slot):
                    if verbose:
                        print(f"   ✗ Infactible: '{it.id}' a {slot.key} viola restricció dura")
                    self._item_infactible = it
                    return None
                sol.assignacions[it.id] = slot
            sol.cost, sol.violacions = self.calcular_cost(sol)
            return sol

        millor_global = None

        # Pre-filtrar slots vàlids per a cada ítem (evita escanar tots els slots cada iteració)
        self._precalcular_slots_candidats()

        # Adaptar paràmetres a la mida del problema
        if n_mob <= 2:
            _iter_per_t = min(self.iteracions_per_temperatura, 30)
            _max_iter   = min(self.max_iteracions, 8000)
            reinicis    = 1
        elif n_mob <= 5:
            _iter_per_t = min(self.iteracions_per_temperatura, 80)
            _max_iter   = min(self.max_iteracions, 30000)
        else:
            _iter_per_t = self.iteracions_per_temperatura
            _max_iter   = self.max_iteracions

        for reinici in range(reinicis):
            if reinici > 0 and verbose:
                print(f"\n🔄 Reinici {reinici + 1}/{reinicis}...")

            # Solució inicial
            sa = self._generar_solucio_inicial()
            if sa is None:
                if verbose:
                    print(f"   ⚠️ No s'ha pogut generar solució inicial")
                continue

            ms = deepcopy(sa)

            violacions_dures = len([v for v in ms.violacions if v.get('pes', 0) >= 100])
            if verbose:
                print(f"   Solució inicial: cost={sa.cost:.2f}, {violacions_dures} violacions dures")

            # Si ja és viable i hi ha poques sessions mòbils, podem acabar aviat
            if violacions_dures == 0 and n_mob <= 1:
                if verbose:
                    print(f"   ✨ Solució inicial viable amb {n_mob} mòbil(s), saltant SA")
                millor_global = ms
                break

            t, it = self.temperatura_inicial, 0
            sense_millora = 0

            while t > self.temperatura_final and it < _max_iter:
                for _ in range(_iter_per_t):
                    sv = self._generar_veí(sa)

                    # Probabilitat d'acceptació
                    if sv.cost < sa.cost:
                        prob = 1.0
                    elif t > 0:
                        prob = math.exp(-(sv.cost - sa.cost) / t)
                    else:
                        prob = 0.0

                    if random.random() < prob:
                        sa = sv
                        if sa.cost < ms.cost:
                            ms = deepcopy(sa)
                            sense_millora = 0
                            if verbose:
                                print(f"   ✅ Nova millor: cost={ms.cost:.2f} (T={t:.2f})")
                        else:
                            sense_millora += 1
                    else:
                        sense_millora += 1

                    it += 1

                t *= self.factor_refredament

                # Early stopping: només si estem a temperatura baixa (explotació) i cost raonable
                # Condició t < 100 evita tallar l'exploració a T alta (on la solució no ha convergit)
                if sense_millora > 10000 and ms.cost < 100000 and t < 100:
                    if verbose:
                        print(f"   ⚡ Early stopping: {sense_millora} iter sense millora, T={t:.2f}")
                    break

            if verbose:
                print(f"   Reinici {reinici + 1}: {it} iteracions, cost={ms.cost:.2f}")

            # Actualitzar millor global
            if millor_global is None or ms.cost < millor_global.cost:
                millor_global = deepcopy(ms)

            # Si ja és viable, podem acabar
            violacions_dures = len([v for v in millor_global.violacions if v.get('pes', 0) >= 100])
            if violacions_dures == 0:
                if verbose:
                    print(f"   ✨ Solució viable trobada!")
                break

        if verbose and millor_global:
            print(f"✅ SA completat. Millor cost: {millor_global.cost:.2f}")

        return millor_global

    def _generar_solucio_inicial(self):
        # Heurística: prioritzar ítems amb menys slots compatibles
        base_sol = Solucio(assignacions={})
        compat_counts = {}
        for it in self.items:
            compat_counts[it.id] = len([s for s in self.slots if self._slot_compatible(base_sol, it, s)])
            if compat_counts[it.id] == 0:
                self._item_infactible = it
                return None

        items_sorted = sorted(self.items, key=lambda it: compat_counts.get(it.id, 0))
        for _ in range(self.intents_solucio_inicial):
            sol = Solucio(assignacions={})
            # Aleatorietat controlada dins el mateix nombre de compatibilitats
            grouped = defaultdict(list)
            for it in items_sorted:
                grouped[compat_counts[it.id]].append(it)
            ordered = []
            for k in sorted(grouped.keys()):
                group = grouped[k]
                random.shuffle(group)
                ordered.extend(group)

            ok = True
            for it in ordered:
                compat = [s for s in self.slots if self._slot_compatible(sol, it, s)]
                if compat:
                    sol.assignacions[it.id] = random.choice(compat)
                else:
                    self._item_infactible = it
                    ok = False
                    break
            if ok:
                sol.cost, sol.violacions = self.calcular_cost(sol)
                return sol
        return None

    def _generar_veí(self, sol):
        """Genera una solució veïna movent o intercanviant items.
        IMPORTANT: Mai viola la restricció de nivell (dos items del mateix nivell al mateix slot).
        Usa DELTA COST: només recalcula els slots afectats pel moviment.
        """
        nv = Solucio(
            assignacions=dict(sol.assignacions),
            cost=sol.cost,
            cost_per_slot=dict(sol.cost_per_slot),
            cost_global=sol.cost_global,
            violacions=[]  # Es reconstruiran
        )
        if not self.items:
            return nv

        slots_afectats = set()  # Slots que cal recalcular
        moviment_fet = False

        # Tipus de moviment aleatori: moure (70%) o intercanviar (30%)
        moviment = random.choice(['moure', 'moure', 'moure', 'moure', 'moure', 'moure', 'moure', 'intercanviar', 'intercanviar', 'intercanviar'])

        items_per_moviment = (self.items_mobils if hasattr(self, 'items_mobils') and self.items_mobils else self.items)
        if moviment == 'intercanviar' and len(items_per_moviment) >= 2:
            item1, item2 = random.sample(items_per_moviment, 2)
            slot1 = nv.assignacions.get(item1.id)
            slot2 = nv.assignacions.get(item2.id)

            if slot1 and slot2 and slot1 != slot2:
                nv.assignacions[item1.id] = slot2
                nv.assignacions[item2.id] = slot1
                precomp1 = self._build_compat_precomp(nv, item1.id)
                precomp2 = self._build_compat_precomp(nv, item2.id)
                if not self._slot_compatible(nv, item1, slot2, _precomp=precomp1) or not self._slot_compatible(nv, item2, slot1, _precomp=precomp2):
                    nv.assignacions[item1.id] = slot1
                    nv.assignacions[item2.id] = slot2
                    moviment = 'moure'
                else:
                    slots_afectats.add(slot1.key)
                    slots_afectats.add(slot2.key)
                    moviment_fet = True
            else:
                moviment = 'moure'

        if moviment == 'moure' and not moviment_fet:
            it = random.choice(items_per_moviment)
            slot_origen = sol.assignacions.get(it.id)
            candidats = self._slots_candidats_per_item.get(it.id, self.slots)
            precomp = self._build_compat_precomp(nv, it.id)
            compat = [s for s in candidats if self._slot_compatible(nv, it, s, _precomp=precomp)]
            if compat:
                slot_desti = random.choice(compat)
                nv.assignacions[it.id] = slot_desti
                if slot_origen:
                    slots_afectats.add(slot_origen.key)
                slots_afectats.add(slot_desti.key)
                moviment_fet = True

        # DELTA COST: només recalcular slots afectats
        if moviment_fet and slots_afectats:
            # Construir sessions_per_dia (necessari per scoring)
            sessions_per_dia: Dict[str, List[Dict]] = defaultdict(list)
            for iid, slot in nv.assignacions.items():
                it = self.items_per_id[iid]
                dia_key = slot.data if slot.data else normalitzar_dia(slot.dia)
                for s in it.sessions:
                    sessions_per_dia[dia_key].append(self._sessio_to_dict(s))

            # Construir items_per_slot per als slots afectats
            items_per_slot: Dict[str, List[Item]] = defaultdict(list)
            for iid, slot in nv.assignacions.items():
                if slot.key in slots_afectats:
                    items_per_slot[slot.key].append(self.items_per_id[iid])

            # Recalcular només els slots afectats
            for slot_key in slots_afectats:
                cost_antic = nv.cost_per_slot.get(slot_key, 0.0)
                items_slot = items_per_slot.get(slot_key, [])
                cost_nou, viols = self._calcular_cost_slot_unic(slot_key, items_slot, sessions_per_dia)
                nv.cost_per_slot[slot_key] = cost_nou
                nv.cost = nv.cost - cost_antic + cost_nou
                nv.violacions.extend(viols)

            # Recalcular restriccions globals (afectades per qualsevol moviment)
            cost_global_antic = nv.cost_global
            cost_global_nou = 0.0
            for r in self.restriccions_obj:
                if r.tipus == 'pref_mateix_slot':
                    c, v = self._avaluar_restriccio(nv, r)
                    cost_global_nou += c
                    nv.violacions.extend(v)
            nv.cost_global = cost_global_nou
            nv.cost = nv.cost - cost_global_antic + cost_global_nou
        else:
            # Cap moviment: mantenir cost original
            nv.violacions = list(sol.violacions)

        return nv

    def generar_horari_optimitzat(self, data_inici=None, data_inici_iso=None, max_dies=5, dies_utilitzar=None, dia_a_data_iso=None, verbose=True, **kwargs):
        if dies_utilitzar is None: dies_utilitzar = ["Dilluns", "Dimarts", "Dimecres", "Dijous", "Divendres"][:max_dies]

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

        self._horaris_norm = self._pre_normalitzar_horaris()
        self.engine = RestrictionEngine(self.get_restriccions(), self.nivells_actius)
        self.crear_slots(dies_utilitzar)
        if not self.slots or not self.sessions: return {'dies': [], 'metadata': {'cost_total': 999999, 'error': "No dades"}}
        missing_fixos = self._check_fixos_viables()
        if missing_fixos:
            return {
                'dies': [],
                'metadata': {
                    'viable': False,
                    'error': "No hi ha slots per assignatures amb dia/hora fix",
                    'detalls': missing_fixos[:10],
                    'motor': 'v3-sa'
                }
            }
        viable = self._pre_agrupar_sessions()
        if not viable:
            return {
                'dies': [],
                'metadata': {
                    'viable': False,
                    'error': "No és possible col·locar tots els exàmens (items > slots per nivell)",
                    'motor': 'v3-sa'
                }
            }
        self._item_infactible = None
        ms = self.executar_simulated_annealing(verbose=verbose)
        if ms is None:
            infactible = getattr(self, '_item_infactible', None)
            incompat_motor = []
            if infactible:
                item_nom = getattr(infactible, 'id', None) or str(infactible)
                motiu = self._detectar_motiu_item_infactible(infactible)
                msg = f"Cap slot per a '{item_nom}'"
                if motiu:
                    msg += f" — {motiu}"
                incompat_motor = [msg]
            return {
                'dies': [],
                'metadata': {
                    'viable': False,
                    'error': "No és possible col·locar tots els exàmens (cap slot compatible per algun ítem)",
                    'incompatibilitats': incompat_motor,
                    'motor': 'v3-sa'
                }
            }
        return self._solucio_a_horari(ms, dies_utilitzar, data_inici)

    def _detectar_motiu_item_infactible(self, item) -> Optional[str]:
        """Retorna la restricció principal que bloqueja l'ítem en tots els slots individuals."""
        from collections import Counter as _Counter
        engine = getattr(self, 'engine', None) or RestrictionEngine(self.get_restriccions(), self.nivells_actius)
        raons: _Counter = _Counter()
        for slot in self.slots:
            for s in item.sessions:
                s_dict = self._sessio_to_dict(s)
                violation = engine.check_hard(
                    s_dict, slot.dia, slot.hora, slot.data or slot.dia, [], [], {}
                )
                if violation:
                    raons[violation.label] += 1
                    break
        if raons:
            return raons.most_common(1)[0][0]
        return None

    def _solucio_a_horari(self, sol, du, di):
        from datetime import datetime as _dt
        s2s = defaultdict(list)
        for iid, sl in sol.assignacions.items():
            for s in self.items_per_id[iid].sessions: s2s[sl.key].append(s)

        # Construir llista (dia_nom, data_iso, sk_prefix) per iterar
        selected = getattr(self, 'selected_dates', None) or []
        if selected:
            dies_iter = []
            for data_iso in selected:
                try:
                    dia_nom = _DIES_CAT[_dt.strptime(data_iso, "%Y-%m-%d").weekday()]
                    dies_iter.append((dia_nom, data_iso, data_iso))
                except (ValueError, IndexError):
                    continue
        else:
            dies_iter = []
            for d in du:
                d_norm = normalitzar_dia(d)
                dates = (getattr(self, 'dia_a_data_iso', {}) or {}).get(d_norm) or []
                data_iso = dates[0] if dates else None
                dies_iter.append((d, data_iso, d))

        res_dies = []
        for dia_nom, data_iso, sk_prefix in dies_iter:
            di_info = {'dia': dia_nom, 'sessions': []}
            if data_iso:
                di_info['data'] = data_iso
            for h in self.hores_examen:
                sk = f"{sk_prefix}_{h}"
                if sk in s2s:
                    sessions_sim = []
                    for x in s2s[sk]:
                        sessio_dict = self._sessio_to_dict(x)
                        nom_s = sessio_dict.get('nom')
                        curs_s = sessio_dict.get('curs')
                        durada_supervisio = self.get_durada_per_sessio_key(nom_s, curs_s)
                        durada_exam_s = self.get_durada_examen_per_sessio_key(nom_s, curs_s)
                        if h in self.totes_hores:
                            idx_s = self.totes_hores.index(h)
                            hores_sup_s = self.totes_hores[idx_s:min(idx_s + durada_supervisio, len(self.totes_hores))]
                            hores_exam_s = self.totes_hores[idx_s:min(idx_s + durada_exam_s, len(self.totes_hores))]
                        else:
                            hores_sup_s = [h]
                            hores_exam_s = [h]
                        analisi = analitzar_disponibilitat_sessio(
                            sessio=sessio_dict,
                            dia=dia_nom, hora=h,
                            horaris_professors=self.horaris_professors,
                            totes_hores=self.totes_hores,
                            nivells_actius=self.nivells_actius,
                            durada_titular=durada_supervisio,
                            no_substituir_norm=self.no_substituir_norm,
                            hores_override=hores_exam_s,
                            hores_supervisio=hores_sup_s,
                            alliberaments_per_nivell=self.alliberaments_per_nivell,
                            data_iso=data_iso,
                            horaris_professors_norm=getattr(self, '_horaris_norm', None),
                        )
                        sessions_sim.append({
                            'tipus': 'examen',
                            **sessio_dict,
                            'analisi': analisi
                        })
                    di_info['sessions'].append({'hora': h, 'sessions_simultanees': sessions_sim})
            res_dies.append(di_info)
        final = {'dies': res_dies, 'metadata': {'total_sessions': len(self.sessions), 'cost_total': sol.cost, 'motor': 'v3-sa', 'logs': [v['missatge'] for v in sol.violacions]}}
        aplicar_estadistiques(final); return final
