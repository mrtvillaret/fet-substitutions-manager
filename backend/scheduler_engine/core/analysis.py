"""
Anàlisi de disponibilitat per a l'scheduler.
Lògica compartida i independent del motor.
"""

import re as _re
from typing import List, Dict, Set

from scheduler_engine.core.context import SchedulerContext

from scheduler_engine.core.normalitzacio import normalitzar_dia, normalitzar_text, dia_nom_per_horari, format_dia_label
from scheduler_engine.core.availability import analitzar_disponibilitat_sessio
from scheduler_engine.core.durada import get_durada_per_nivell
from scheduler_engine.core.scoring import calcular_cost_slot
from scheduler_engine.core.constraints import es_slot_valid_per_nivell


def _get_hores_ocupades(totes_hores: List[str], durada_titular: int, hora_inici: str) -> List[str]:
    if hora_inici not in totes_hores:
        return [hora_inici]
    idx = totes_hores.index(hora_inici)
    return totes_hores[idx:min(idx + durada_titular, len(totes_hores))]


def _slot_bloquejat(restriccions: Dict, dia: str, hora: str,
                    totes_hores: List[str], durada_titular: int) -> bool:
    if durada_titular > 1:
        hores = _get_hores_ocupades(totes_hores, durada_titular, hora)
        if len(hores) < durada_titular:
            return True
    return False


def _construir_items_mateix_slot(sessions_pendents: List[Dict], restriccions: Dict) -> List[Dict]:
    grups_raw = restriccions.get('restriccions_dures', {}).get('mateix_slot', [])
    if not grups_raw:
        return [{'sessions': [s], 'nom': s.get('nom'), 'examens_count': len(s.get('examens', []))} for s in sessions_pendents]

    grups_norm = []
    for grup in grups_raw:
        assignatures = grup.get('assignatures', []) if isinstance(grup, dict) else grup
        if isinstance(assignatures, list) and assignatures:
            grups_norm.append({
                'nom': (grup.get('nom', '') if isinstance(grup, dict) else ''),
                'assignatures': [normalitzar_text(n) for n in assignatures]
            })

    nom_a_grup = {}
    for idx, grup in enumerate(grups_norm):
        for nom_norm in grup['assignatures']:
            nom_a_grup[nom_norm] = idx

    sessions_per_nom_norm: Dict[str, List[Dict]] = {}
    for s in sessions_pendents:
        sessions_per_nom_norm.setdefault(normalitzar_text(s.get('nom', '')), []).append(s)
        sessions_per_nom_norm.setdefault(normalitzar_text(s.get('nom_base', '')), []).append(s)

    visitats = set()
    items = []

    def key(s: Dict) -> str:
        return f"{s.get('nom')}|{s.get('curs')}"

    for sessio in sessions_pendents:
        if key(sessio) in visitats:
            continue
        s_nom_norm = normalitzar_text(sessio.get('nom', ''))
        s_base_norm = normalitzar_text(sessio.get('nom_base', ''))
        g_idx = nom_a_grup.get(s_nom_norm, nom_a_grup.get(s_base_norm))

        if g_idx is not None:
            membres = []
            for n_norm in grups_norm[g_idx]['assignatures']:
                for s_match in sessions_per_nom_norm.get(n_norm, []):
                    if key(s_match) not in visitats:
                        membres.append(s_match)
                        visitats.add(key(s_match))
            if membres:
                grup_nom = (grups_norm[g_idx].get('nom') or '').strip()
                items.append({
                    'sessions': membres,
                    'nom': grup_nom if grup_nom else f"grup_{g_idx} ({len(membres)} assig)",
                    'examens_count': sum(len(s.get('examens', [])) for s in membres)
                })
        else:
            visitats.add(key(sessio))
            items.append({
                'sessions': [sessio],
                'nom': sessio.get('nom'),
                'examens_count': len(sessio.get('examens', []))
            })
    return items


def _format_item_label(item: Dict) -> str:
    sessions = item.get('sessions', [])
    noms = [s.get('nom') for s in sessions if s.get('nom')]
    if noms:
        return " + ".join(noms)
    return item.get('nom', '(sense nom)')


def analitzar_tots_slots(sessions_per_nivell: Dict[str, List[Dict]],
                         restriccions: Dict,
                         horaris_professors: Dict,
                         hores_examen: List[str],
                         durada_titular: int,
                         no_substituir_norm: Set[str],
                         totes_hores: List[str],
                         nivells_actius: List[str],
                         dies_utilitzar: List[str],
                         dia_a_data_iso: Dict[str, List[str]] = None,
                         alliberaments_per_nivell: Dict = None) -> Dict:
    totes_items = []
    for nivell in nivells_actius:
        items = _construir_items_mateix_slot(sessions_per_nivell.get(nivell, []), restriccions)
        for i, item in enumerate(items):
            label = _format_item_label(item)
            totes_items.append((nivell, i, item, label))

    matriu_costos: Dict[str, Dict] = {}
    for curs, idx, item, label in totes_items:
        durada_item = get_durada_per_nivell(curs, alliberaments_per_nivell, durada_titular)
        nom_item = f"{curs}_{idx}_{label}"
        matriu_costos[nom_item] = {
            'item': item,
            'label': label,
            'curs': curs,
            'idx': idx,
            'slots': {}
        }

        for dia in dies_utilitzar:
            # Suport multi-setmana: dia pot ser ISO (YYYY-MM-DD) o nom de dia
            is_iso = bool(_re.match(r'^\d{4}-\d{2}-\d{2}$', dia))
            dia_horari = dia_nom_per_horari(dia)  # nom de dia per lookup horaris
            dia_norm = normalitzar_dia(dia_horari)
            if is_iso:
                data_iso = dia
            else:
                _dates = (dia_a_data_iso or {}).get(dia_norm)
                _mapped = _dates[0] if isinstance(_dates, list) else _dates
                data_iso = _mapped
            for hora in hores_examen:
                if _slot_bloquejat(restriccions, dia_horari, hora, totes_hores, durada_item):
                    continue
                if any(
                    not es_slot_valid_per_nivell(s.get('nom', ''), dia_horari, hora, restriccions, nivells_actius, curs=s.get('curs', ''), data_iso=data_iso)
                    for s in item.get('sessions', [])
                ):
                    continue
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
                hores_slot = _get_hores_ocupades(totes_hores, durada_item, hora)
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
                        analisi = analitzar_disponibilitat_sessio(
                            sessio=sessio,
                            dia=dia_horari,
                            hora=hora_real,
                            horaris_professors=horaris_professors,
                            totes_hores=totes_hores,
                            nivells_actius=nivells_actius,
                            durada_titular=durada_item,
                            no_substituir_norm=no_substituir_norm,
                            sessions_al_slot=None,
                            hores_override=[hora_real],
                            alliberaments_per_nivell=alliberaments_per_nivell,
                            data_iso=data_iso
                        )
                        resultat_scoring = calcular_cost_slot(
                            sessio=sessio,
                            dia=dia_horari,
                            hora=hora_real,
                            analisi=analisi,
                            restriccions=restriccions,
                            sessions_dia=None,
                            sessions_slot=None,
                            data_iso=data_iso or ""
                        )
                        breakdown = resultat_scoring.get('breakdown', {})

                        subs_professors = [i['professor'] for i in analisi.get('substitucions', []) if i.get('professor')]
                        abans_professors = [i['professor'] for i in analisi.get('abans_jornada', []) if i.get('professor')]
                        despres_professors = [i['professor'] for i in analisi.get('despres_jornada', []) if i.get('professor')]
                        no_treballa_professors = [i['professor'] for i in analisi.get('no_treballa_dia', []) if i.get('professor')]

                        subs_detalls = []
                        for item_sub in analisi.get('substitucions', []):
                            prof = item_sub.get('professor', '').strip()
                            act = item_sub.get('activitat', {}) or {}
                            assig = act.get('assignatura', '').strip()
                            grup = act.get('grup', '').strip()
                            if not prof:
                                continue
                            label_sub = f"{prof} → {assig}" if assig else prof
                            if grup:
                                label_sub = f"{label_sub} ({grup})"
                            subs_detalls.append(label_sub)

                        def _cnt(lst):
                            return len({(i['professor'], i.get('hora', hora_real)) for i in lst})

                        cost_info = {
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
                            'cost_total': resultat_scoring['cost_total']
                        }

                        for key in ['cost_substitucions', 'cost_abans', 'cost_despres', 'cost_no_treballa', 'cost_preferencies', 'cost_total']:
                            total[key] += cost_info.get(key, 0)
                        total['subs_professors'].extend(cost_info.get('subs_professors', []))
                        total['subs_detalls'].extend(cost_info.get('subs_detalls', []))
                        total['abans_professors'].extend(cost_info.get('abans_professors', []))
                        total['despres_professors'].extend(cost_info.get('despres_professors', []))
                        total['no_treballa_professors'].extend(cost_info.get('no_treballa_professors', []))

                        hora_bucket = per_hour[hora_real]
                        for key in ['cost_substitucions', 'cost_abans', 'cost_despres', 'cost_no_treballa', 'cost_preferencies', 'cost_total']:
                            hora_bucket[key] += cost_info.get(key, 0)
                        hora_bucket['subs_professors'].extend(cost_info.get('subs_professors', []))
                        hora_bucket['subs_detalls'].extend(cost_info.get('subs_detalls', []))
                        hora_bucket['abans_professors'].extend(cost_info.get('abans_professors', []))
                        hora_bucket['despres_professors'].extend(cost_info.get('despres_professors', []))
                        hora_bucket['no_treballa_professors'].extend(cost_info.get('no_treballa_professors', []))

                total['per_hour'] = per_hour
                matriu_costos[nom_item]['slots'][slot_key] = total

    return matriu_costos


def analitzar_tots_slots_ctx(ctx: SchedulerContext) -> Dict:
    return analitzar_tots_slots(
        sessions_per_nivell=ctx.sessions_per_nivell,
        restriccions=ctx.restriccions,
        horaris_professors=ctx.horaris_professors,
        hores_examen=ctx.hores_examen,
        durada_titular=ctx.durada_titular,
        no_substituir_norm=ctx.no_substituir_norm,
        totes_hores=ctx.totes_hores,
        nivells_actius=ctx.nivells_actius,
        dies_utilitzar=ctx.dies_utilitzar,
        dia_a_data_iso=ctx.dia_a_data_iso,
        alliberaments_per_nivell=ctx.alliberaments_per_nivell,
    )


def generar_informe_per_slots(matriu_costos: Dict, dies_utilitzar: List[str],
                              hores_examen: List[str], durada_titular: int,
                              nivells_actius: List[str]) -> str:
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
    for hora in hores_examen:
        for hora_real in _get_hores_ocupades(hores_examen, durada_titular, hora):
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
            for nivell in nivells_actius:
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


def generar_informe_disponibilitat(matriu_costos: Dict, dies_utilitzar: List[str],
                                   hores_examen: List[str], durada_titular: int) -> str:
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

    for _, info in sorted(matriu_costos.items(), key=lambda x: x[1].get('label', '')):
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
            for hora in hores_examen:
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


def generar_informe_professors_per_slot(horaris_professors: Dict, dies_utilitzar: List[str],
                                        hores_examen: List[str], durada_titular: int,
                                        nivells_actius: List[str], totes_hores: List[str],
                                        restriccions: Dict) -> str:
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
        linies.append(f"📅 {dia}")
        linies.append("")
        for hora in hores_examen:
            if _slot_bloquejat(restriccions, dia, hora, totes_hores, durada_titular):
                continue
            hores_slot = _get_hores_ocupades(totes_hores, durada_titular, hora)
            for hora_real in hores_slot:
                linies.append(f"⏰ {hora_real}")
                disponibles = []
                alliberats = []
                for prof, horari in horaris_professors.items():
                    dia_rec = horari.get(normalitzar_dia(dia), {})
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
                    if any(n in grup for n in nivells_actius):
                        # Els slots vàlids es defineixen per hora d'inici (🟦), no per hora interna.
                        # Si el bloc comença a les 09:15 i dura 2h, la 10:15 ha de mantenir el mateix filtre.
                        if not es_slot_valid_per_nivell(grup, dia, hora, restriccions, nivells_actius):
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
