from abc import ABC, abstractmethod
import json
import os
import xml.etree.ElementTree as ET
from typing import List, Dict, Set, Any
from collections import defaultdict
import random
import hashlib

from scheduler_engine.core.normalitzacio import normalitzar_dia, normalitzar_text, nom_base_assignatura
from scheduler_engine.core.context import SchedulerContext
from scheduler_engine.core.constraints import sessio_in_group, get_restriccio_val
from scheduler_engine.core.durada import get_durada_per_nivell, get_durada_per_sessio_key
from scheduler_engine.defaults import (
    DEFAULT_NIVELLS_ACTIUS,
    DEFAULT_RESTRICCIONS,
)


class GeneradorSessionsExamensBase(ABC):
    """Classe base abstracta amb funcionalitat compartida pels motors."""

    def __init__(self, config_examens_path: str, horari_xml_path: str,
                 restriccions_path: str = None, ultim_professor: str = "",
                 nivells_actius: List[str] = None, hores_examen: List[str] = None,
                 hores_per_nivell: Dict[str, List[str]] = None,
                 durada_titular: int = 1, no_substituir: set = None,
                 alliberaments_per_nivell: Dict = None,
                 durades_per_sessio: Dict[str, int] = None,
                 durades_examen_per_sessio: Dict[str, int] = None):
        self.config_path = config_examens_path
        self.horari_xml_path = horari_xml_path
        self.restriccions_path = restriccions_path
        self.ultim_professor = ultim_professor
        self.nivells_actius = nivells_actius or list(DEFAULT_NIVELLS_ACTIUS)
        self.hores_examen = hores_examen or []
        self.hores_per_nivell = hores_per_nivell or {}  # Format: {"1-BATX": ["09:00", "11:30"], ...}
        self.durada_titular = durada_titular
        self.no_substituir = no_substituir or set()
        self.no_substituir_norm = {normalitzar_text(a) for a in self.no_substituir if a}
        # Alliberaments per nivell: { nivell: { dates: [], config: { "YYYY-MM-DD": { "HH:MM": { a: bool } } } } }
        self.alliberaments_per_nivell = alliberaments_per_nivell or {}
        # Durades específiques per sessió: { "Nom (NIVELL)": hores_supervisio }
        self.durades_per_sessio = durades_per_sessio or {}
        # Durades de l'examen per l'alumne: { "Nom (NIVELL)": hores_examen } (≥ durades_per_sessio)
        self.durades_examen_per_sessio = durades_examen_per_sessio or {}

        self.config = {}
        self.horaris_professors = {}
        self.totes_hores = []

        # Estructures compartides
        self.sessions_per_nivell = {nivell: [] for nivell in self.nivells_actius}
        self.sessions_per_id = {} 

    @abstractmethod
    def generar_horari_optimitzat(self, **kwargs) -> Dict:
        pass

    def get_hores_per_nivell(self, nivell: str) -> List[str]:
        """Retorna les hores d'examen per un nivell específic.
        Si el nivell té hores pròpies, les retorna; sinó, les globals.
        """
        if self.hores_per_nivell and nivell in self.hores_per_nivell:
            hores = self.hores_per_nivell[nivell]
            if hores:  # Només si no és llista buida
                return hores
        return self.hores_examen

    def _carregar_config(self):
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)

    def _carregar_restriccions_raw(self) -> dict:
        if self.restriccions_path and os.path.exists(self.restriccions_path):
            with open(self.restriccions_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return dict(DEFAULT_RESTRICCIONS)

    def _pre_normalitzar_horaris(self) -> dict:
        """Pre-normalitza les claus de dia i hora dels horaris dels professors (una sola vegada)."""
        norm = {}
        for prof, dies in (self.horaris_professors or {}).items():
            norm_prof = {}
            for dia_k, hores in dies.items():
                dia_n = normalitzar_dia(dia_k)
                norm_hores = {}
                for h_k, act in hores.items():
                    parts = str(h_k).split(':')
                    try:
                        h_n = f"{int(parts[0]):02d}:{int(parts[1]):02d}"
                        norm_hores[h_n] = act
                    except Exception:
                        norm_hores[h_k] = act
                norm_prof[dia_n] = norm_hores
            norm[prof] = norm_prof
        return norm

    def get_restriccions(self) -> dict:
        if hasattr(self, "restriccions") and self.restriccions:
            return self.restriccions
        if hasattr(self, "restriccions_raw") and self.restriccions_raw:
            return self.restriccions_raw
        return self._carregar_restriccions_raw()

    def build_context(self, dies_utilitzar: List[str]) -> SchedulerContext:
        return SchedulerContext(
            sessions_per_nivell=self.sessions_per_nivell,
            restriccions=self.get_restriccions(),
            horaris_professors=self.horaris_professors,
            hores_examen=self.hores_examen,
            durada_titular=self.durada_titular,
            no_substituir_norm=self.no_substituir_norm,
            totes_hores=self.totes_hores,
            nivells_actius=self.nivells_actius,
            dies_utilitzar=dies_utilitzar,
            dia_a_data_iso=getattr(self, "dia_a_data_iso", {}) or {},
            alliberaments_per_nivell=self.alliberaments_per_nivell,
            durades_per_sessio=self.durades_per_sessio,
        )

    def carregar_horaris_professors(self):
        tree = ET.parse(self.horari_xml_path)
        root = tree.getroot()
        ultim_prof = (self.ultim_professor or "").strip()
        hores = []
        for day in root.findall('.//Day'):
            for hour in day.findall('Hour'):
                h = hour.get('name')
                if h and h not in hores: hores.append(h)
        self.totes_hores = hores
        for teacher in root.findall('Teacher'):
            nom = teacher.get('name').strip()
            self.horaris_professors[nom] = {}
            for day in teacher.findall('Day'):
                d = normalitzar_dia(day.get('name'))
                self.horaris_professors[nom][d] = {}
                for hour in day.findall('Hour'):
                    h = hour.get('name')
                    sub = hour.find('Subject')
                    act = hour.find('Activity')
                    if (act is not None and act.get('id')) or sub is not None:
                        s = sub.get('name') if sub is not None else ''
                        g = hour.find('Students').get('name') if hour.find('Students') is not None else ''
                        self.horaris_professors[nom][d][h] = {'assignatura': s, 'grup': g}
            # El professor límit també s'ha d'incloure; parem després de processar-lo.
            if ultim_prof and nom == ultim_prof:
                break

    def get_durada_per_nivell(self, nivell: str | None) -> int:
        return get_durada_per_nivell(nivell, self.alliberaments_per_nivell, self.durada_titular)

    def get_durada_per_sessio_key(self, sessio_nom: str | None, nivell: str | None) -> int:
        return get_durada_per_sessio_key(
            sessio_nom, nivell,
            self.durades_per_sessio,
            self.alliberaments_per_nivell,
            self.durada_titular,
        )

    def get_durada_examen_per_sessio_key(self, sessio_nom: str | None, nivell: str | None) -> int:
        """Retorna la durada de l'examen per l'alumne (≥ durada supervisió).
        Prioritat: durades_examen_per_sessio > durades_per_sessio > durada_titular."""
        if sessio_nom and self.durades_examen_per_sessio:
            d = self.durades_examen_per_sessio.get(sessio_nom)
            if d is not None:
                try:
                    d_int = int(d)
                    if d_int > 0:
                        return d_int
                except (TypeError, ValueError):
                    pass
        # Fallback: almenys tan gran com la durada de supervisió
        return self.get_durada_per_sessio_key(sessio_nom, nivell)

    def _get_hores_ocupades(self, hora_inici: str, nivell: str | None = None, sessio_nom: str | None = None) -> List[str]:
        if hora_inici not in self.totes_hores:
            return [hora_inici]
        if sessio_nom:
            durada = self.get_durada_per_sessio_key(sessio_nom, nivell)
        elif nivell:
            durada = self.get_durada_per_nivell(nivell)
        else:
            durada = self.durada_titular
        idx = self.totes_hores.index(hora_inici)
        return self.totes_hores[idx : min(idx + durada, len(self.totes_hores))]

    def get_all_sessions(self) -> List[Dict]:
        res = []
        for n in self.nivells_actius: res.extend(self.sessions_per_nivell.get(n, []))
        return res

    def get_total_sessions_count(self) -> int:
        return len(self.get_all_sessions())

    def _get_mateix_slot_grups(self) -> List[List[str]]:
        """Extrau els grups que han d'anar al mateix slot des de les restriccions."""
        restriccions = self._carregar_restriccions_raw()
        grups_raw = restriccions.get('restriccions_dures', {}).get('mateix_slot', [])
        grups = []
        for grup in grups_raw:
            assignatures = grup.get('assignatures', []) if isinstance(grup, dict) else grup
            if isinstance(assignatures, list) and assignatures:
                grups.append(assignatures)
        return grups

    def _get_mateix_slot_grups_amb_noms(self) -> List[dict]:
        """Extrau els grups amb els seus noms definits per l'usuari."""
        restriccions = self._carregar_restriccions_raw()
        grups_raw = restriccions.get('restriccions_dures', {}).get('mateix_slot', [])
        grups = []
        for grup in grups_raw:
            if isinstance(grup, dict):
                assignatures = grup.get('assignatures', [])
                nom = grup.get('nom', '')
                if isinstance(assignatures, list) and assignatures:
                    grups.append({'nom': nom, 'assignatures': assignatures})
            elif isinstance(grup, list) and grup:
                grups.append({'nom': '', 'assignatures': grup})
        return grups

    def _get_combinacions_permeses(self) -> List[List[str]]:
        """Extrau les combinacions permeses (agrupacions opcionals)."""
        restriccions = self._carregar_restriccions_raw()
        combs_raw = restriccions.get('restriccions_dures', {}).get('combinacions_permeses', [])
        combs = []
        for comb in combs_raw:
            assignatures = comb.get('assignatures', []) if isinstance(comb, dict) else comb
            if isinstance(assignatures, list) and assignatures:
                combs.append(assignatures)
        return combs

    def _construir_items_mateix_slot(self, sessions_pendents: List[Dict]) -> List[Dict]:
        """
        Agrupa sessions que han d'anar al same slot (mateix_slot) usant normalització robusta.
        """
        grups_raw = self._get_mateix_slot_grups_amb_noms()
        if not grups_raw:
            return [{'sessions': [s], 'nom': s.get('nom'), 'examens_count': len(s.get('examens', []))} for s in sessions_pendents]

        # Normalitzar grups per comparació robusta i conservar el nom
        grups_norm = []
        for grup in grups_raw:
            assignatures = grup.get('assignatures', []) if isinstance(grup, dict) else grup
            if isinstance(assignatures, list) and assignatures:
                grups_norm.append({
                    'nom': (grup.get('nom', '') if isinstance(grup, dict) else ''),
                    'assignatures': [normalitzar_text(n) for n in assignatures]
                })
        
        # Mapa de nom_normalitzat -> índex del grup
        nom_a_grup = {}
        for idx, grup in enumerate(grups_norm):
            for nom_norm in grup['assignatures']:
                nom_a_grup[nom_norm] = idx

        # Mapa de sessions per nom normalitzat per a cerca ràpida
        sessions_per_nom_norm = defaultdict(list)
        for s in sessions_pendents:
            sessions_per_nom_norm[normalitzar_text(s.get('nom',''))].append(s)
            sessions_per_nom_norm[normalitzar_text(s.get('nom_base',''))].append(s)

        visitats, items = set(), []
        def key(s): return f"{s.get('nom')}|{s.get('curs')}"
        
        for sessio in sessions_pendents:
            if key(sessio) in visitats: continue
            
            s_nom_norm = normalitzar_text(sessio.get('nom', ''))
            s_base_norm = normalitzar_text(sessio.get('nom_base', ''))
            
            g_idx = nom_a_grup.get(s_nom_norm)
            if g_idx is None:
                g_idx = nom_a_grup.get(s_base_norm)
            
            if g_idx is not None:
                membres = []
                # Recollir TOTES les sessions que coincideixin amb qualsevol nom del grup
                for n_norm in grups_norm[g_idx]['assignatures']:
                    for s_match in sessions_per_nom_norm.get(n_norm, []):
                        if key(s_match) not in visitats:
                            membres.append(s_match)
                            visitats.add(key(s_match))
                
                if membres:
                    grup_nom = (grups_norm[g_idx].get('nom') or '').strip()
                    item = {
                        'sessions': membres,
                        'nom': grup_nom if grup_nom else f"grup_{g_idx} ({len(membres)} assig)",
                        'examens_count': sum(len(s.get('examens', [])) for s in membres)
                    }
                    self._assign_item_id(item)
                    items.append(item)
            else:
                visitats.add(key(sessio))
                item = {
                    'sessions': [sessio],
                    'nom': sessio.get('nom'),
                    'examens_count': len(sessio.get('examens', []))
                }
                self._assign_item_id(item)
                items.append(item)
        return items

    def _assign_item_id(self, item: Dict) -> None:
        """Assigna un item_id estable i el propaga a les sessions de l'ítem."""
        sessions = item.get('sessions', [])
        base = "|".join(
            sorted(f"{s.get('id') or s.get('nom')}::{s.get('curs') or ''}" for s in sessions)
        )
        digest = hashlib.sha1(base.encode('utf-8')).hexdigest()[:12]
        item_id = f"item_{digest}"
        item['item_id'] = item_id
        item['item_label'] = item.get('nom') or item_id
        for s in sessions:
            s['item_id'] = item_id
            s['item_label'] = item.get('nom') or item_id

    def preparar_particio_nivells(self, slots_disponibles: int) -> List[Dict]:
        """Garanteix que cada nivell té els seus exàmens agrupats en 'paquets' únics (sense fusionar forçat)."""
        tots_els_items = []
        restriccions = self._carregar_restriccions_raw()

        # 1. Obtenir agrupacions configurades (normalitzades) amb els seus noms
        grups_amb_noms = self._get_mateix_slot_grups_amb_noms()
        # Crear estructura: [(nom, [assignatures_normalitzades]), ...]
        grups_ms_amb_noms = [
            (g.get('nom', ''), [normalitzar_text(n) for n in g.get('assignatures', [])])
            for g in grups_amb_noms if g.get('assignatures')
        ]
        combs_raw = restriccions.get('restriccions_dures', {}).get('combinacions_permeses', [])
        combs_opt = []
        for c in combs_raw:
            assignatures = c.get('assignatures', []) if isinstance(c, dict) else c
            if isinstance(assignatures, list) and assignatures:
                combs_opt.append({normalitzar_text(n) for n in assignatures})

        for nivell in self.nivells_actius:
            sessions_pendents = self.sessions_per_nivell.get(nivell, [])
            if not sessions_pendents: continue
            
            # Crear mapa de ID -> Sessio per evitar duplicats
            sessio_by_id = {s['id']: s for s in sessions_pendents}
            visitats = set()
            items_nivell = []

            # A. Agrupar per mateix_slot (Mandatori)
            for grup_nom, grup_n in grups_ms_amb_noms:
                membres = []
                for sid, s in sessio_by_id.items():
                    if sid in visitats: continue
                    if normalitzar_text(s['nom']) in grup_n or normalitzar_text(s['nom_base']) in grup_n:
                        membres.append(s); visitats.add(sid)
                if membres:
                    # Usar el nom definit per l'usuari, o generar un per defecte
                    nom_agrupacio = grup_nom if grup_nom else membres[0]['nom_base'] + ' (G)'
                    item = {'sessions': membres, 'nom': nom_agrupacio, 'curs': nivell}
                    self._assign_item_id(item)
                    items_nivell.append(item)

            # B. Afegir sessions restants com items individuals
            for sid, s in sessio_by_id.items():
                if sid not in visitats:
                    item = {'sessions': [s], 'nom': s['nom'], 'curs': nivell}
                    self._assign_item_id(item)
                    items_nivell.append(item)
                    visitats.add(sid)

            # C. Fusionar per espai o per combinacions (Model demo)
            # Només fusionem si hi ha combinacions permeses
            if combs_opt:
                changed = True
                while changed:
                    changed = False
                    for c_set in sorted(combs_opt, key=len, reverse=True):
                        compat = []
                        for idx, it in enumerate(items_nivell):
                            it_noms = {normalitzar_text(s['nom_base']) for s in it['sessions']}
                            if it_noms.issubset(c_set): compat.append(idx)
                        
                        if len(compat) >= 2:
                            # Unir tot en el primer ítem i eliminar la resta
                            main_idx = compat[0]
                            for idx in sorted(compat[1:], reverse=True):
                                items_nivell[main_idx]['sessions'].extend(items_nivell.pop(idx)['sessions'])
                            items_nivell[main_idx]['nom'] = items_nivell[main_idx]['sessions'][0]['nom_base'] + " (+)"
                            self._assign_item_id(items_nivell[main_idx])
                            changed = True
                            break

            # D. Dedupejar ítems per evitar duplicats exactes
            uniques = []
            vistos = set()
            for it in items_nivell:
                sess_ids = sorted([s.get('id') or s.get('nom') for s in it.get('sessions', [])])
                key = (it.get('curs'), tuple(sess_ids))
                if key in vistos:
                    continue
                vistos.add(key)
                uniques.append(it)
            items_nivell = uniques

            tots_els_items.extend(items_nivell)
            
        return tots_els_items
