"""
Càlcul centralitzat d'estadístiques i costos per a horaris generats.
Usat per tots els motors (V2 greedy, V2 backtrack, V3 SA).
"""

from typing import Dict
from collections import defaultdict

from utils.hores import normalitzar_hora as _normalitzar_hora
from scheduler_engine.core.availability import analitzar_disponibilitat_sessio
from scheduler_engine.core.durada import get_durada_per_sessio_key, detectar_nivell_sessio
from scheduler_engine.core.scoring import calcular_cost_slot
from scheduler_engine.core.constraints import calcular_penalitzacio_total_professors
from scheduler_engine.core.normalitzacio import normalitzar_dia
from scheduler_engine.core.context import SchedulerContext
from scheduler_engine.defaults import DEFAULT_COST_PROFESSORS


def calcular_estadistiques_horari(horari: Dict) -> Dict:
    """
    Calcula les estadístiques d'un horari generat.
    Compta substitucions, professors abans/després de jornada, etc.
    Usa tuples (professor, hora) per evitar deduplicar el mateix professor
    a hores diferents dins del mateix slot (important amb durada_titular > 1).

    Args:
        horari: Dict amb estructura {'dies': [...], 'metadata': {...}}

    Returns:
        Dict amb les estadístiques calculades:
        - total_substitucions
        - professors_abans
        - professors_despres
        - professors_no_treballa
        - dies_necessaris
        - total_sessions
    """
    total_subs = 0
    total_abans = 0
    total_despres = 0
    total_no_treballa = 0

    for dia in horari.get('dies', []):
        for sessio_hora in dia.get('sessions', []):
            hora_slot = sessio_hora.get('hora', '')
            seen_subs = set()
            seen_abans = set()
            seen_despres = set()
            seen_no_treballa = set()

            for sessio in sessio_hora.get('sessions_simultanees', []):
                analisi = sessio.get('analisi', {})

                for item in analisi.get('substitucions', []):
                    if isinstance(item, dict) and item.get('professor'):
                        key = (item['professor'], item.get('hora', hora_slot))
                        seen_subs.add(key)

                for item in analisi.get('abans_jornada', []):
                    if isinstance(item, dict) and item.get('professor'):
                        key = (item['professor'], item.get('hora', hora_slot))
                        seen_abans.add(key)

                for item in analisi.get('despres_jornada', []):
                    if isinstance(item, dict) and item.get('professor'):
                        key = (item['professor'], item.get('hora', hora_slot))
                        seen_despres.add(key)

                for item in analisi.get('no_treballa_dia', []):
                    if isinstance(item, dict) and item.get('professor'):
                        key = (item['professor'], item.get('hora', hora_slot))
                        seen_no_treballa.add(key)

            total_subs += len(seen_subs)
            total_abans += len(seen_abans)
            total_despres += len(seen_despres)
            total_no_treballa += len(seen_no_treballa)

    total_sessions = sum(
        len(sh.get('sessions_simultanees', []))
        for dia in horari.get('dies', [])
        for sh in dia.get('sessions', [])
    )

    return {
        'total_substitucions': total_subs,
        'professors_abans': total_abans,
        'professors_despres': total_despres,
        'professors_no_treballa': total_no_treballa,
        'dies_necessaris': len(horari.get('dies', [])),
        'total_sessions': total_sessions,
    }


def aplicar_estadistiques(horari: Dict) -> None:
    """
    Calcula i aplica estadístiques directament al metadata de l'horari.
    Modifica l'horari in-place.
    """
    stats = calcular_estadistiques_horari(horari)
    metadata = horari.setdefault('metadata', {})
    metadata.update(stats)


def recalcular_cost_i_breakdown(horari: Dict, ctx: SchedulerContext) -> Dict:
    """
    Recalcula el cost total i el breakdown a partir del resultat final (independent del motor).
    Torna un dict: {cost_total, cost_breakdown}.
    """
    restriccions = ctx.restriccions
    costos_globals = (restriccions.get('costos_professors', {}) or {}).get('globals', {})

    pes_sub = costos_globals.get('substitucio', DEFAULT_COST_PROFESSORS["substitucio"])
    pes_abans = costos_globals.get('abans_jornada', DEFAULT_COST_PROFESSORS["abans_jornada"])
    pes_despres = costos_globals.get('despres_jornada', DEFAULT_COST_PROFESSORS["despres_jornada"])
    pes_no_treballa = costos_globals.get('no_treballa_dia', DEFAULT_COST_PROFESSORS["no_treballa_dia"])

    cost_total = 0.0
    breakdown = defaultdict(int)
    total_subs = 0
    total_abans = 0
    total_despres = 0
    total_no_treballa = 0

    # Pre-computar sessions per dia
    # sessions_per_dia: keyed per dia-nom normalitzat (per calcular_penalitzacio_total_professors)
    # sessions_per_data: keyed per data ISO o dia-nom (per no_mateix_dia: evita confondre setmanes)
    sessions_per_dia = defaultdict(list)
    sessions_per_data = defaultdict(list)
    for dia in horari.get('dies', []):
        dia_nom = dia.get('dia', '')
        data_iso_d = dia.get('data', '')
        dia_norm = normalitzar_dia(dia_nom)
        data_key = data_iso_d if data_iso_d else dia_norm
        for slot in dia.get('sessions', []):
            for sessio in slot.get('sessions_simultanees', []):
                sessions_per_dia[dia_norm].append(sessio)
                sessions_per_data[data_key].append(sessio)


    # Normalitzar hores de context per assegurar consistència amb els horaris dels professors
    ctx.totes_hores = [_normalitzar_hora(h) for h in (ctx.totes_hores or [])]

    for dia in horari.get('dies', []):
        dia_nom = dia.get('dia', '')
        dia_norm = normalitzar_dia(dia_nom)
        _dates = (ctx.dia_a_data_iso or {}).get(dia_norm)
        data_iso = dia.get('data') or (_dates[0] if isinstance(_dates, list) else _dates)
        data_key = data_iso if data_iso else dia_norm
        for slot in dia.get('sessions', []):
            hora = slot.get('hora', '')
            hora_norm = _normalitzar_hora(hora)
            sessions_slot = slot.get('sessions_simultanees', [])

            # Costos de professors (dedup per (professor,hora))
            seen_subs = set()
            seen_abans = set()
            seen_despres = set()
            seen_no_treballa = set()

            for idx, sessio in enumerate(sessions_slot):
                altres = [s for i, s in enumerate(sessions_slot) if i != idx]
                nivell_sessio = detectar_nivell_sessio(sessio, ctx.nivells_actius or [])
                sessio_nom = sessio.get('nom') if isinstance(sessio, dict) else getattr(sessio, 'nom', None)
                durades_per_sessio_ctx = getattr(ctx, 'durades_per_sessio', None)
                durada_sessio = get_durada_per_sessio_key(
                    sessio_nom, nivell_sessio,
                    durades_per_sessio_ctx,
                    ctx.alliberaments_per_nivell,
                    ctx.durada_titular
                )
                if hora_norm in ctx.totes_hores:
                    idx_inici = ctx.totes_hores.index(hora_norm)
                    idx_fi = min(idx_inici + max(1, durada_sessio), len(ctx.totes_hores))
                    hores_ocupades = ctx.totes_hores[idx_inici:idx_fi]
                else:
                    hores_ocupades = [hora_norm]
                analisi = analitzar_disponibilitat_sessio(
                    sessio=sessio,
                    dia=dia_nom,
                    hora=hora_norm,
                    horaris_professors=ctx.horaris_professors,
                    totes_hores=ctx.totes_hores,
                    nivells_actius=ctx.nivells_actius,
                    durada_titular=durada_sessio,
                    no_substituir_norm=ctx.no_substituir_norm,
                    sessions_al_slot=altres,
                    # Comptar incidències per cada hora ocupada
                    hores_override=hores_ocupades,
                    alliberaments_per_nivell=ctx.alliberaments_per_nivell,
                    data_iso=data_iso,
                )
                for item in analisi.get('substitucions', []):
                    if isinstance(item, dict) and item.get('professor'):
                        seen_subs.add((item['professor'], item.get('hora', hora)))
                for item in analisi.get('abans_jornada', []):
                    if isinstance(item, dict) and item.get('professor'):
                        seen_abans.add((item['professor'], item.get('hora', hora)))
                for item in analisi.get('despres_jornada', []):
                    if isinstance(item, dict) and item.get('professor'):
                        seen_despres.add((item['professor'], item.get('hora', hora)))
                for item in analisi.get('no_treballa_dia', []):
                    if isinstance(item, dict) and item.get('professor'):
                        seen_no_treballa.add((item['professor'], item.get('hora', hora)))

            subs_count = len(seen_subs)
            abans_count = len(seen_abans)
            despres_count = len(seen_despres)
            nt_count = len(seen_no_treballa)

            total_subs += subs_count
            total_abans += abans_count
            total_despres += despres_count
            total_no_treballa += nt_count

            cost_total += subs_count * pes_sub
            cost_total += abans_count * pes_abans
            cost_total += despres_count * pes_despres
            cost_total += nt_count * pes_no_treballa

            breakdown['substitucio'] += subs_count * pes_sub
            breakdown['abans_jornada'] += abans_count * pes_abans
            breakdown['despres_jornada'] += despres_count * pes_despres
            breakdown['no_treballa_dia'] += nt_count * pes_no_treballa

            # Penalitzacions de restriccions i preferències (sense costos de professors)
            pesos_opt = restriccions.get('pesos_optimitzacio', {})
            from scheduler_engine.defaults import DEFAULT_PES_RESTRICCIO_DURA, DEFAULT_PES_RESTRICCIO_VIOLADA
            _pes_dura = pesos_opt.get('restriccio_dura', DEFAULT_PES_RESTRICCIO_DURA)
            _pes_violada = pesos_opt.get('restriccio_dura_violada', DEFAULT_PES_RESTRICCIO_VIOLADA)
            for sessio in sessions_slot:
                analisi_empty = {
                    'substitucions': [],
                    'abans_jornada': [],
                    'despres_jornada': [],
                    'no_treballa_dia': [],
                }
                res_c = calcular_cost_slot(
                    sessio=sessio,
                    dia=dia_nom,
                    hora=hora,
                    analisi=analisi_empty,
                    restriccions=restriccions,
                    sessions_dia=sessions_per_data.get(data_key, []),
                    sessions_slot=sessions_slot,
                    include_limit_dies=False,
                    data_iso=data_iso,
                )
                _bd = res_c.get('breakdown') or {}
                cost_total += res_c.get('cost_total', 0)
                for k, v in _bd.items():
                    if k in ('substitucio', 'abans_jornada', 'despres_jornada', 'no_treballa', 'professors_limit_dies'):
                        continue
                    breakdown[k] += v

    # Penalització total per límits de dies (un sol càlcul global)
    p_prof_dies_total = calcular_penalitzacio_total_professors(sessions_per_dia, restriccions)
    if p_prof_dies_total:
        cost_total += p_prof_dies_total
        breakdown['limit_dies_professor'] += p_prof_dies_total

    # Assegurar que totes les claus estàndard estan presents (valor 0 si no hi ha cost)
    from scheduler_engine.defaults import ETIQUETES_RESTRICCIONS
    for clau in ETIQUETES_RESTRICCIONS:
        breakdown.setdefault(clau, 0)

    return {
        'cost_total': float(cost_total),
        'cost_breakdown': dict(breakdown),
        'total_substitucions': total_subs,
        'professors_abans': total_abans,
        'professors_despres': total_despres,
        'professors_no_treballa': total_no_treballa,
    }
