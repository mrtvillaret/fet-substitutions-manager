"""
Motor de generació d'horaris V2 - Greedy amb Epsilon.
"""

import random
import copy
from typing import List, Dict, Tuple
from collections import defaultdict

from scheduler_engine.core.normalitzacio import normalitzar_text, normalitzar_dia, nom_base_assignatura, dia_nom_per_horari, format_dia_label
from scheduler_engine.core.date_mapping import construir_mapa_dia_data_iso, DIES_CAT as _DIES_CAT
from scheduler_engine.core.availability import analitzar_disponibilitat_sessio
from scheduler_engine.core.scoring import calcular_cost_slot
from scheduler_engine.core.constraints import (
    sessio_matches, sessio_in_group, get_restriccio_val, detectar_nivell_grup,
    viola_restriccio_dura, viola_combinacions_permeses, viola_restriccio_dia_hora_fixos,
    es_slot_valid_per_nivell, penalitzacio_conflicte_professor_nivell,
    calcular_penalitzacio_professors_dies, calcular_penalitzacio_assignatures_dies_exclosos,
    calcular_penalitzacio_total_professors, es_item_compatible_amb_slot,
    viola_limit_dies_professor_obligatori, viola_preferencia_dia_obligatoria,
    calcular_penalitzacio_professors_dies_item
)
from scheduler_engine.generators.base import GeneradorSessionsExamensBase
from scheduler_engine.estadistiques import aplicar_estadistiques, recalcular_cost_i_breakdown
from scheduler_engine.defaults import DEFAULT_PES_RESTRICCIO_DURA, DEFAULT_PES_ZONA_EXAMEN


class GeneradorV2Intents(GeneradorSessionsExamensBase):
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
        self.restriccions = {}
        self.dia_a_data_iso = {}  # Mapa dia -> data_iso per als alliberaments

    def carregar_dades(self):
        self._carregar_config()
        for curs in self.nivells_actius:
            self.sessions_per_nivell[curs] = []
            for assignatura_nom, dades in self.config.get('assignatures', {}).items():
                examens = [a for a in dades.get('assignacions', []) if curs in a['grup']]
                if examens:
                    sid = f"{assignatura_nom}_{curs}"
                    s = {'id': sid, 'nom': f"{assignatura_nom} ({curs})", 'nom_base': assignatura_nom, 'curs': curs, 'examens': examens}
                    self.sessions_per_nivell[curs].append(s)
        self.restriccions = self._carregar_restriccions_raw()

    def analitzar_disponibilitat_sessio(self, sessio: Dict, dia: str, hora: str,
                                       sessions_al_slot: List[Dict] = None,
                                       hores_override: List[str] | None = None,
                                       data_iso: str = None) -> Dict:
        from scheduler_engine.core.normalitzacio import normalitzar_dia
        dia_norm = normalitzar_dia(dia)
        if data_iso is None:
            dates = self.dia_a_data_iso.get(dia_norm)
            data_iso = dates[0] if isinstance(dates, list) else dates
        nom = sessio.get('nom')
        curs = sessio.get('curs')
        durada_supervisio = self.get_durada_per_sessio_key(nom, curs)
        durada_exam = self.get_durada_examen_per_sessio_key(nom, curs)

        if hores_override is not None:
            # Quan s'especifica override (ex. anàlisi d'una hora concreta), usar-la per a tot
            hores_exam_final = hores_override
            hores_sup_final = hores_override
        else:
            # Calcular finestres des de la posició d'hora
            hora_norm = hora
            if hora_norm in self.totes_hores:
                idx = self.totes_hores.index(hora_norm)
                hores_sup_final = self.totes_hores[idx:min(idx + durada_supervisio, len(self.totes_hores))]
                hores_exam_final = self.totes_hores[idx:min(idx + durada_exam, len(self.totes_hores))]
            else:
                hores_sup_final = [hora_norm]
                hores_exam_final = [hora_norm]

        return analitzar_disponibilitat_sessio(
            sessio=sessio, dia=dia, hora=hora, horaris_professors=self.horaris_professors,
            totes_hores=self.totes_hores, nivells_actius=self.nivells_actius,
            durada_titular=durada_supervisio, no_substituir_norm=self.no_substituir_norm,
            sessions_al_slot=sessions_al_slot,
            hores_override=hores_exam_final,
            hores_supervisio=hores_sup_final,
            alliberaments_per_nivell=self.alliberaments_per_nivell,
            data_iso=data_iso,
            horaris_professors_norm=getattr(self, '_horaris_norm', None),
        )

    def _calcular_cost_sessio(self, sessio: Dict, dia: str, hora: str,
                              sessions_dia: List = None, sessions_slot: List = None,
                              hores_override: List[str] | None = None,
                              data_iso: str = None) -> Dict:
        analisi = self.analitzar_disponibilitat_sessio(sessio, dia, hora, sessions_slot, hores_override=hores_override, data_iso=data_iso)
        resultat_scoring = calcular_cost_slot(
            sessio=sessio, dia=dia, hora=hora, analisi=analisi, restriccions=self.restriccions,
            sessions_dia=sessions_dia, sessions_slot=sessions_slot, include_limit_dies=False,
            data_iso=data_iso or ""
        )
        breakdown = resultat_scoring.get('breakdown', {})
        subs_professors = [i['professor'] for i in analisi.get('substitucions', []) if i.get('professor')]
        abans_professors = [i['professor'] for i in analisi.get('abans_jornada', []) if i.get('professor')]
        despres_professors = [i['professor'] for i in analisi.get('despres_jornada', []) if i.get('professor')]
        no_treballa_professors = [i['professor'] for i in analisi.get('no_treballa_dia', []) if i.get('professor')]

        subs_detalls = []
        for item in analisi.get('substitucions', []):
            prof = item.get('professor', '').strip()
            act = item.get('activitat', {}) or {}
            assig = act.get('assignatura', '').strip()
            grup = act.get('grup', '').strip()
            if not prof:
                continue
            label = f"{prof} → {assig}" if assig else prof
            if grup:
                label = f"{label} ({grup})"
            subs_detalls.append(label)

        def _cnt(lst):
            return len({(i['professor'], i.get('hora', hora)) for i in lst})
        # Soft cost per conflictes a la zona examen (sense titular): guia el greedy cap a slots nets
        zona_examen_count = len({(i['professor'], i.get('hora', hora)) for i in analisi.get('zona_examen', [])})
        cost_zona_examen = zona_examen_count * DEFAULT_PES_ZONA_EXAMEN
        return {
            'analisi': analisi,
            'cost_substitucions': _cnt(analisi.get('substitucions', [])),
            'cost_abans': _cnt(analisi.get('abans_jornada', [])),
            'cost_despres': _cnt(analisi.get('despres_jornada', [])),
            'cost_no_treballa': _cnt(analisi.get('no_treballa_dia', [])),
            'subs_professors': subs_professors,
            'subs_detalls': subs_detalls,
            'abans_professors': abans_professors,
            'despres_professors': despres_professors,
            'no_treballa_professors': no_treballa_professors,
            'cost_preferencies': breakdown.get('preferencies', 0),
            'cost_total': resultat_scoring['cost_total'] + cost_zona_examen,
            'professors_estrictes_violats': resultat_scoring.get('professors_estrictes_violats', [])
        }

    def _te_restriccio_dia_hora_fix(self, nom_sessio: str) -> Tuple[str, str]:
        dures = self.restriccions.get('restriccions_dures', {})
        return dures.get('assignatures_dia_fix', {}).get(nom_sessio), dures.get('assignatures_hora_fix', {}).get(nom_sessio)

    def _viola_restriccio_dura(self, sessio: Dict, sessions_dia: List[Dict]) -> bool:
        return viola_restriccio_dura(sessio, sessions_dia, self.restriccions)

    def _viola_restriccio_dia_hora_fixos(self, sessio: Dict, dia: str, hora: str, data_iso: str = None) -> bool:
        return viola_restriccio_dia_hora_fixos(sessio, dia, hora, self.restriccions, self.nivells_actius, data_iso or "")

    def _calcular_penalitzacio_professors_dies(self, sessio: Dict, dia: str, sessions_assignades: Dict) -> int:
        return calcular_penalitzacio_professors_dies(sessio, dia, sessions_assignades, self.restriccions)

    def _slot_bloquejat(self, dia: str, hora: str, nivell: str | None = None) -> bool:
        """Retorna True si el slot no pot encabir la durada completa."""
        durada = self.get_durada_per_nivell(nivell) if nivell else self.durada_titular
        if durada > 1:
            hores = self._get_hores_ocupades(hora, nivell)
            if len(hores) < durada:
                return True
        return False

    def _analitzar_tots_slots(self, dies_utilitzar: List[str]) -> Dict:
        """Analitza el cost de cada agrupació a cada possible dia/hora."""
        totes_items = []
        for nivell in self.nivells_actius:
            items = self._construir_items_mateix_slot(self.sessions_per_nivell.get(nivell, []))
            for i, item in enumerate(items):
                label = self._format_item_label(item)
                totes_items.append((nivell, i, item, label))

        matriu_costos = {}
        for curs, idx, item, label in totes_items:
            nom_item = f"{curs}_{idx}_{label}"
            matriu_costos[nom_item] = {
                'item': item,
                'label': label,
                'curs': curs,
                'idx': idx,
                'slots': {}
            }

            for dia in dies_utilitzar:
                import re as _re_iso
                _is_iso = bool(_re_iso.match(r'^\d{4}-\d{2}-\d{2}$', dia))
                dia_horari = dia_nom_per_horari(dia)
                if _is_iso:
                    _data_iso_calc = dia
                else:
                    _d = (getattr(self, 'dia_a_data_iso', {}) or {}).get(normalitzar_dia(dia))
                    _data_iso_calc = (_d[0] if isinstance(_d, list) else _d)
                for hora in self.hores_examen:
                    if self._slot_bloquejat(dia_horari, hora, curs):
                        continue
                    # Respectar slots vàlids per nivell (alliberaments per dia/hora)
                    if any(
                        not es_slot_valid_per_nivell(s.get('nom', ''), dia_horari, hora, self.restriccions, self.nivells_actius, curs=s.get('curs', ''), data_iso=_data_iso_calc)
                        for s in item.get('sessions', [])
                    ):
                        continue
                    # En anàlisi només considerem subst/abans/després/no_treballa
                    slot_key = f"{dia}_{hora}"
                    total = {
                        'cost_substitucions': 0,
                        'cost_abans': 0,
                        'cost_despres': 0,
                        'cost_no_treballa': 0,
                        'cost_preferencies': 0,
                        'cost_total': 0,
                        'subs_professors': [],
                        'subs_detalls': [],
                        'abans_professors': [],
                        'despres_professors': [],
                        'no_treballa_professors': []
                    }
                    hores_slot = self._get_hores_ocupades(hora, curs)
                    per_hour = {
                        hora_real: {
                            'cost_substitucions': 0,
                            'cost_abans': 0,
                            'cost_despres': 0,
                            'cost_no_treballa': 0,
                            'cost_preferencies': 0,
                            'cost_total': 0,
                            'subs_professors': [],
                            'subs_detalls': [],
                            'abans_professors': [],
                            'despres_professors': [],
                            'no_treballa_professors': []
                        }
                        for hora_real in hores_slot
                    }
                    for sessio in item.get('sessions', []):
                        for hora_real in hores_slot:
                            cost_info = self._calcular_cost_sessio(sessio, dia_horari, hora_real, hores_override=[hora_real], data_iso=_data_iso_calc)
                            total['cost_substitucions'] += cost_info.get('cost_substitucions', 0)
                            total['cost_abans'] += cost_info.get('cost_abans', 0)
                            total['cost_despres'] += cost_info.get('cost_despres', 0)
                            total['cost_no_treballa'] += cost_info.get('cost_no_treballa', 0)
                            total['cost_preferencies'] += cost_info.get('cost_preferencies', 0)
                            total['cost_total'] += cost_info.get('cost_total', 0)
                            total['subs_professors'].extend(cost_info.get('subs_professors', []))
                            total['subs_detalls'].extend(cost_info.get('subs_detalls', []))
                            total['abans_professors'].extend(cost_info.get('abans_professors', []))
                            total['despres_professors'].extend(cost_info.get('despres_professors', []))
                            total['no_treballa_professors'].extend(cost_info.get('no_treballa_professors', []))

                            hora_bucket = per_hour[hora_real]
                            hora_bucket['cost_substitucions'] += cost_info.get('cost_substitucions', 0)
                            hora_bucket['cost_abans'] += cost_info.get('cost_abans', 0)
                            hora_bucket['cost_despres'] += cost_info.get('cost_despres', 0)
                            hora_bucket['cost_no_treballa'] += cost_info.get('cost_no_treballa', 0)
                            hora_bucket['cost_preferencies'] += cost_info.get('cost_preferencies', 0)
                            hora_bucket['cost_total'] += cost_info.get('cost_total', 0)
                            hora_bucket['subs_professors'].extend(cost_info.get('subs_professors', []))
                            hora_bucket['subs_detalls'].extend(cost_info.get('subs_detalls', []))
                            hora_bucket['abans_professors'].extend(cost_info.get('abans_professors', []))
                            hora_bucket['despres_professors'].extend(cost_info.get('despres_professors', []))
                            hora_bucket['no_treballa_professors'].extend(cost_info.get('no_treballa_professors', []))
                    # Penalització de límit dies (un sol cop per ítem)
                    p_limit = calcular_penalitzacio_professors_dies_item(
                        item, dia_horari, {dia_horari: item.get('sessions', [])}, self.restriccions
                    )
                    if p_limit:
                        total['cost_total'] += p_limit
                    total['per_hour'] = per_hour
                    matriu_costos[nom_item]['slots'][slot_key] = total

        return matriu_costos

    def generar_informe_per_slots(self, matriu_costos: Dict, dies_utilitzar: List[str]) -> str:
        """Genera informe invertit: per cada slot, quines sessions són viables."""
        linies = []
        linies.append("=" * 85)
        linies.append("🕐 INFORME DE SESSIONS DISPONIBLES PER SLOT")
        linies.append("=" * 85)
        linies.append("")
        linies.append("Aquest informe mostra per cada dia/hora:")
        linies.append("  • Òptimes: Cap conflicte (cost 0)")
        linies.append("  • Conflictes mínims: ≤2 conflictes")
        linies.append("  • Sessions problemàtiques: També mostra ≤3 conflictes")
        linies.append("")

        sessions_problematiques = set()
        for _, info in matriu_costos.items():
            slots_viables = 0
            for cost_info in info['slots'].values():
                num_conflictes = (cost_info.get('cost_substitucions', 0) +
                                  cost_info.get('cost_abans', 0) +
                                  cost_info.get('cost_despres', 0))
                te_no_treballa = cost_info.get('cost_no_treballa', 0) > 0
                if cost_info['cost_total'] == 0 or (num_conflictes <= 2 and not te_no_treballa):
                    slots_viables += 1
            if slots_viables <= 2:
                sessions_problematiques.add(info.get('label', '(sense nom)'))

        linies.append(f"⚠️  Sessions problemàtiques detectades ({len(sessions_problematiques)}): {', '.join(sorted(sessions_problematiques))}")
        linies.append("")

        hores_considerades = []
        for hora in self.hores_examen:
            for hora_real in self._get_hores_ocupades(hora):
                if hora_real not in hores_considerades:
                    hores_considerades.append(hora_real)

        slots_disponibilitat = {}
        for dia in dies_utilitzar:
            for hora in hores_considerades:
                slot_key = f"{dia}_{hora}"
                slots_disponibilitat[slot_key] = {
                    'dia': dia,
                    'hora': hora,
                    'optimes': [],
                    'bones': [],
                    'acceptables': [],
                    'conflictes': []
                }

        for _, info in matriu_costos.items():
            nom_curt = info.get('label', '(sense nom)')
            for slot_key, cost_info in info['slots'].items():
                dia, _ = slot_key.split('_', 1)
                per_hour = cost_info.get('per_hour') or {}
                if not per_hour:
                    per_hour = {cost_info.get('hora'): cost_info}

                for hora_real, hora_info in per_hour.items():
                    dest_key = f"{dia}_{hora_real}"
                    if dest_key not in slots_disponibilitat:
                        continue
                    cost = hora_info['cost_total']
                    entrada = {
                        'nom': nom_curt,
                        'cost': cost,
                        'subs': hora_info.get('cost_substitucions', 0),
                        'abans': hora_info.get('cost_abans', 0),
                        'despres': hora_info.get('cost_despres', 0),
                        'no_treballa': hora_info.get('cost_no_treballa', 0),
                        'curs': info.get('curs'),
                        'subs_detalls': sorted(set(hora_info.get('subs_detalls', []))),
                        'abans_professors': hora_info.get('abans_professors', []),
                        'despres_professors': hora_info.get('despres_professors', []),
                        'no_treballa_professors': hora_info.get('no_treballa_professors', [])
                    }

                    num_conflictes = entrada['subs'] + entrada['abans'] + entrada['despres']
                    te_no_treballa = entrada['no_treballa'] > 0
                    es_problematica = nom_curt in sessions_problematiques

                    if cost == 0:
                        slots_disponibilitat[dest_key]['optimes'].append(entrada)
                    elif num_conflictes <= 2 and not te_no_treballa:
                        slots_disponibilitat[dest_key]['bones'].append(entrada)
                    elif num_conflictes == 3 and not te_no_treballa and es_problematica:
                        slots_disponibilitat[dest_key]['acceptables'].append(entrada)
        def _format_entry(entry: Dict) -> str:
            parts = []
            subs_detalls = entry.get('subs_detalls', [])
            if subs_detalls:
                parts.append(f"subst: {' | '.join(subs_detalls)}")
            abans = sorted(set(entry.get('abans_professors', [])))
            if abans:
                parts.append(f"abans: {', '.join(abans)}")
            despres = sorted(set(entry.get('despres_professors', [])))
            if despres:
                parts.append(f"despres: {', '.join(despres)}")
            no_treballa = sorted(set(entry.get('no_treballa_professors', [])))
            if no_treballa:
                parts.append(f"no_treballa: {', '.join(no_treballa)}")
            if parts:
                return f"{entry.get('nom')} [{'; '.join(parts)}]"
            return entry.get('nom')

        for dia in dies_utilitzar:
            linies.append("=" * 85)
            linies.append(f"📅 {format_dia_label(dia).upper()}")
            linies.append("=" * 85)
            linies.append("")
            for hora in hores_considerades:
                slot_key = f"{dia}_{hora}"
                slot_info = slots_disponibilitat[slot_key]

                linies.append(f"⏰ {hora}")
                linies.append("─" * 85)

                sessions_per_curs = {}
                for nivell in self.nivells_actius:
                    sessions_per_curs[nivell] = {
                        'optimes': sorted([s for s in slot_info['optimes'] if s['curs'] == nivell], key=lambda x: x['nom']),
                        'bones': sorted([s for s in slot_info['bones'] if s['curs'] == nivell], key=lambda x: x['nom']),
                        'acceptables': sorted([s for s in slot_info['acceptables'] if s['curs'] == nivell], key=lambda x: x['nom'])
                    }

                for nivell, grups in sessions_per_curs.items():
                    if grups['optimes'] or grups['bones'] or grups['acceptables']:
                        linies.append(f"{nivell}:")
                        if grups['optimes']:
                            noms = ', '.join([_format_entry(s) for s in grups['optimes']])
                            linies.append(f"  ✅ Òptimes: {noms}")
                        if grups['bones']:
                            noms = ', '.join([_format_entry(s) for s in grups['bones']])
                            linies.append(f"  🟡 Bones: {noms}")
                        if grups['acceptables']:
                            noms = ', '.join([_format_entry(s) for s in grups['acceptables']])
                            linies.append(f"  🔶 Acceptables: {noms}")
                linies.append("")

        return "\n".join(linies)

    def generar_informe_disponibilitat(self, matriu_costos: Dict, dies_utilitzar: List[str]) -> str:
        """Informe per sessió: tots els slots amb cost/detall."""
        linies = []
        linies.append("=" * 85)
        linies.append("📊 INFORME DE DISPONIBILITAT PER AGRUPACIONS")
        linies.append("=" * 85)
        linies.append("")
        linies.append("Per cada agrupació: tots els slots ordenats per dia")
        linies.append("Emojis: ✅=0 conflictes | 🟡≤2 | 🔶=3 | 🔴>3 o prof. no treballa")
        linies.append("")

        def emoji(cost_info):
            num_conf = cost_info.get('cost_substitucions', 0) + cost_info.get('cost_abans', 0) + cost_info.get('cost_despres', 0)
            te_no_treballa = cost_info.get('cost_no_treballa', 0) > 0
            if te_no_treballa or num_conf > 3:
                return "🔴"
            if num_conf == 0:
                return "✅"
            if num_conf == 3:
                return "🔶"
            return "🟡"

        for _, info in matriu_costos.items():
            linies.append(f"📝 {info.get('label')}")
            profs = set()
            for s in info.get('item', {}).get('sessions', []):
                for ex in s.get('examens', []):
                    p = ex.get('titular')
                    if p:
                        profs.add(p)
            if profs:
                linies.append("👥 Professors: " + ", ".join(sorted(profs)))
            linies.append("")
            linies.append("Dia | Hora | Cost | Subs | Abans | Després | No treb | Detalls")
            linies.append("-" * 70)
            for dia in dies_utilitzar:
                dia_horari_inf = dia_nom_per_horari(dia)
                for hora in self.hores_examen:
                    if self._slot_bloquejat(dia_horari_inf, hora):
                        continue
                    slot_key = f"{dia}_{hora}"
                    cost_info = info['slots'].get(slot_key)
                    if not cost_info:
                        continue
                    per_hour = cost_info.get('per_hour') or {}
                    for hora_real, hora_info in per_hour.items():
                        detalls = []
                        subs = hora_info.get('subs_professors', [])
                        abans = hora_info.get('abans_professors', [])
                        despres = hora_info.get('despres_professors', [])
                        no_treballa = hora_info.get('no_treballa_professors', [])
                        if subs:
                            detalls.append("Subst: " + ", ".join(sorted(set(subs))))
                        if abans:
                            detalls.append("Abans: " + ", ".join(sorted(set(abans))))
                        if despres:
                            detalls.append("Després: " + ", ".join(sorted(set(despres))))
                        if no_treballa:
                            detalls.append("No treb: " + ", ".join(sorted(set(no_treballa))))
                        det_text = " | ".join(detalls) if detalls else "cap conflicte"
                        linies.append(f"{emoji(hora_info)} {format_dia_label(dia)} | {hora_real} | {hora_info.get('cost_total', 0)} | {hora_info.get('cost_substitucions', 0)} | {hora_info.get('cost_abans', 0)} | {hora_info.get('cost_despres', 0)} | {hora_info.get('cost_no_treballa', 0)} | {det_text}")
            linies.append("")

        return "\n".join(linies)

    def generar_informe_professors_per_slot(self, dies_utilitzar: List[str]) -> str:
        linies = []
        linies.append("=" * 85)
        linies.append("👥 INFORME DE PROFESSORS PER SLOT (Hores d'Exàmens)")
        linies.append("=" * 85)
        linies.append("")
        linies.append("Aquest informe mostra per cada hora d'examen:")
        linies.append("  ✅ DISPONIBLES: amb activitat sense grup (Guàrdia/CD/VP/E.D./Reforç/Reunió...)")
        linies.append("  📚 ALLIBERATS: amb classe dels nivells actius (alliberats perquè els alumnes fan exàmens)")
        linies.append("(No es mostren professors amb classe d'altres nivells ni professors sense activitat)")
        linies.append("")

        for dia in dies_utilitzar:
            dia_horari_prof = dia_nom_per_horari(dia)
            linies.append(f"📅 {format_dia_label(dia)}")
            linies.append("")
            for hora in self.hores_examen:
                if self._slot_bloquejat(dia_horari_prof, hora):
                    continue
                hores_slot = self._get_hores_ocupades(hora)
                for hora_real in hores_slot:
                    linies.append(f"⏰ {hora_real}")
                    disponibles = []
                    alliberats = []
                    for prof, horari in self.horaris_professors.items():
                        dia_rec = horari.get(normalitzar_dia(dia_horari_prof), {})
                        if not dia_rec:
                            continue
                        act = dia_rec.get(hora_real)
                        if not act:
                            continue
                        grup = (act.get('grup') or '').strip()
                        assig = (act.get('assignatura') or '').strip()
                        if grup:
                            from utils.grups_utils import aplicar_abreviatura_grup
                            grup = aplicar_abreviatura_grup(grup)
                        if any(n in grup for n in self.nivells_actius):
                            # Els slots vàlids es defineixen per hora d'inici (🟦), no per hora interna.
                            # Si el bloc comença a les 09:15 i dura 2h, la 10:15 ha de mantenir el mateix filtre.
                            if not es_slot_valid_per_nivell(grup, dia_horari_prof, hora, self.restriccions, self.nivells_actius):
                                continue
                            if grup and assig:
                                alliberats.append(f"{prof} ({assig}, {grup})")
                            elif grup:
                                alliberats.append(f"{prof} ({grup})")
                            elif assig:
                                alliberats.append(f"{prof} ({assig})")
                            else:
                                alliberats.append(prof)
                        elif not grup and assig:
                            disponibles.append(f"{prof} ({assig})")
                    if not disponibles and not alliberats:
                        linies.append("(Tots els professors tenen classe d'altres nivells o no tenen activitat)")
                    else:
                        if disponibles:
                            linies.append(f"✅ DISPONIBLES ({len(disponibles)}):")
                            for p in sorted(disponibles):
                                linies.append(f"• {p}")
                        if alliberats:
                            linies.append(f"📚 ALLIBERATS ({len(alliberats)}):")
                            for p in sorted(alliberats):
                                linies.append(f"• {p}")
                    linies.append("")

        return "\n".join(linies)

    def _format_item_label(self, item: Dict) -> str:
        return item.get('nom', 'group')

    def generar_horari_optimitzat(self, data_inici: str = None, data_inici_iso: str = None, max_dies: int = 5, dies_utilitzar: List[str] = None,
                                  dia_a_data_iso: Dict[str, List[str]] = None,
                                  max_intents_validacio: int = 250, estrategia: str = "ponderada",
                                  epsilon: float = 0.2, track_intents: bool = False, **kwargs) -> Dict:
        from datetime import datetime as _dt
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

        self._horaris_norm = self._pre_normalitzar_horaris()

        # 1. Preparar slots disponibles (usa dates reals si disponibles)
        if self.selected_dates:
            physical_slots = [f"{data}_{h}" for data in self.selected_dates for h in self.hores_examen]
        else:
            physical_slots = [f"{d}_{h}" for d in dies_utilitzar for h in self.hores_examen]
        
        # 2. Obtenir partició atòmica de la base (UN SOL ÍTEM PER NIVELL I SLOT)
        items = self.preparar_particio_nivells(slots_disponibles=len(physical_slots))
        # Viabilitat per nivell
        counts = {}
        for it in items:
            counts[it.get('curs')] = counts.get(it.get('curs'), 0) + 1
        for nivell, count in counts.items():
            if count > len(physical_slots):
                return {
                    'dies': [],
                    'metadata': {
                        'viable': False,
                        'error': f"No és possible col·locar tots els exàmens ({nivell}: {count} items > {len(physical_slots)} slots)",
                        'motor': 'v2-intents'
                    }
                }
        
        total_sessions = self.get_total_sessions_count()
        ctx = self.build_context(dies_utilitzar)
        millor, minim, intents = None, float('inf'), []
        
        for i in range(max_intents_validacio):
            horari = self._generar_un_intent_horari(physical_slots, items, estrategia, epsilon)
            # Garantir estadístiques a cada intent
            aplicar_estadistiques(horari)
            cost_info = recalcular_cost_i_breakdown(horari, ctx)
            horari.setdefault('metadata', {})
            horari['metadata']['cost_total'] = cost_info.get('cost_total', 0)
            horari['metadata']['cost_breakdown'] = cost_info.get('cost_breakdown', {})
            valid = horari['metadata']['total_sessions'] == total_sessions
            if valid and horari['metadata']['cost_total'] < minim:
                minim = horari['metadata']['cost_total']
                millor = copy.deepcopy(horari)
                if minim == 0:
                    break  # Solució perfecta: no cal continuar
            if track_intents:
                meta = horari.get('metadata', {})
                intents.append({
                    'intent': i + 1,
                    'cost': meta.get('cost_total', 0),
                    'valid': valid,
                    'total_sessions': meta.get('total_sessions'),
                    'total_substitucions': meta.get('total_substitucions'),
                    'professors_abans': meta.get('professors_abans'),
                    'professors_despres': meta.get('professors_despres'),
                })
        
        res = millor or horari
        if track_intents: res['metadata']['intents'] = intents
        res['metadata']['motor'] = 'v2-intents'
        return res

    def _generar_un_intent_horari(self, physical_slots, items, estrategia, epsilon):
        from scheduler_engine.core.restriction_engine import RestrictionEngine
        engine = RestrictionEngine(self.restriccions, self.nivells_actius)

        slots = {sk: [] for sk in physical_slots}
        random.shuffle(items) # Per varietat

        # Separar fixes de flexibles
        items_fixes = []
        items_flex = []
        for it in items:
            is_fix = any(self._te_restriccio_dia_hora_fix(s['nom'])[0] or self._te_restriccio_dia_hora_fix(s['nom'])[1] for s in it['sessions'])
            if is_fix: items_fixes.append(it)
            else: items_flex.append(it)

        # Helper: (dia_nom, data_iso_or_none) des del prefix d'un slot key
        def _parse_prefix(prefix: str):
            try:
                from datetime import datetime as _dt2
                dt = _dt2.strptime(prefix, "%Y-%m-%d")
                return _DIES_CAT[dt.weekday()], prefix
            except ValueError:
                return prefix, None

        sessions_per_dia = defaultdict(list)   # keyed per dia-nom: per professor limit functions
        data_sessions = defaultdict(list)       # keyed per data ISO o dia-nom: per no_mateix_dia
        total_assignades, cost_total = 0, 0

        for it in items_fixes + items_flex:
            millor_s, min_p = None, float('inf')
            llista_slots = list(physical_slots)
            if estrategia != "greedy": random.shuffle(llista_slots)

            nivell_it = it['curs']
            for sk in llista_slots:
                _idx = sk.rfind('_')
                prefix, hora = sk[:_idx], sk[_idx + 1:]
                dia, data_iso_sk = _parse_prefix(prefix)
                # Restriccions dures compartides (nivell + no_mateix_slot obligatori)
                compatible, _ = es_item_compatible_amb_slot(it, slots[sk], self.restriccions)
                if not compatible:
                    continue

                p, possible = 0, True
                for s in it['sessions']:
                    if engine.check_hard(
                        s, dia, hora, prefix,
                        data_sessions[prefix], slots[sk], sessions_per_dia
                    ):
                        possible = False; break
                    res_c = self._calcular_cost_sessio(s, dia, hora, sessions_dia=data_sessions[prefix], sessions_slot=slots[sk], data_iso=data_iso_sk)
                    if res_c['cost_total'] >= DEFAULT_PES_RESTRICCIO_DURA: possible = False; break
                    p += res_c['cost_total']
                if possible:
                    p += calcular_penalitzacio_professors_dies_item(it, dia, sessions_per_dia, self.restriccions)

                if possible and p < min_p: min_p = p; millor_s = sk

            if millor_s:
                _idx_s = millor_s.rfind('_')
                prefix_s = millor_s[:_idx_s]
                dia_s, _ = _parse_prefix(prefix_s)
                for s in it['sessions']:
                    slots[millor_s].append({'sessio': s, 'nom': s['nom'], 'curs': s['curs']})
                    sessions_per_dia[dia_s].append(s)
                    data_sessions[prefix_s].append(s)
                    total_assignades += 1
                cost_total += min_p

        res_dies = []
        dia_map = {}  # prefix -> índex a res_dies
        for sk in physical_slots:
            if not slots[sk]: continue
            _idx2 = sk.rfind('_')
            prefix, h = sk[:_idx2], sk[_idx2 + 1:]
            dia_nom, data_iso_out = _parse_prefix(prefix)
            if prefix not in dia_map:
                di = {'dia': dia_nom, 'sessions': []}
                if data_iso_out:
                    di['data'] = data_iso_out
                dia_map[prefix] = len(res_dies)
                res_dies.append(di)
            dia_info = res_dies[dia_map[prefix]]
            sim = []
            for s_info in slots[sk]:
                s = s_info['sessio'].copy()
                s['analisi'] = self.analitzar_disponibilitat_sessio(
                    s, dia_nom, h,
                    [x['sessio'] for x in slots[sk] if x != s_info],
                    data_iso=data_iso_out
                )
                sim.append(s)
            dia_info['sessions'].append({'hora': h, 'sessions_simultanees': sim})

        final_res = {'dies': res_dies, 'metadata': {'total_sessions': total_assignades, 'cost_total': cost_total}}
        aplicar_estadistiques(final_res); return final_res
