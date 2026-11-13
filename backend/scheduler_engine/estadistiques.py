"""
Càlcul centralitzat d'estadístiques i costos per a horaris generats.
Usat per tots els motors (V2 greedy, V2 backtrack, V3 SA).
"""

from collections import defaultdict

from scheduler_engine.core.availability import analitzar_disponibilitat_sessio
from scheduler_engine.core.constraints import incidencies_limit_professors
from scheduler_engine.core.context import SchedulerContext
from scheduler_engine.core.durada import (
    detectar_nivell_sessio,
    get_durada_per_sessio_key,
)
from scheduler_engine.core.normalitzacio import normalitzar_dia
from scheduler_engine.core.punts import CLAU_BREAKDOWN, IncidenciaCost, desglossament
from scheduler_engine.core.scoring import TIPUS_COST_PROFESSOR, calcular_cost_slot, costos_professors_analisi
from scheduler_engine.defaults import ETIQUETES_RESTRICCIONS
from textos import normalitzar_hora as _normalitzar_hora


def calcular_estadistiques_horari(horari: dict) -> dict:
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

    for dia in horari.get("dies", []):
        for sessio_hora in dia.get("sessions", []):
            hora_slot = sessio_hora.get("hora", "")
            seen_subs = set()
            seen_abans = set()
            seen_despres = set()
            seen_no_treballa = set()

            for sessio in sessio_hora.get("sessions_simultanees", []):
                analisi = sessio.get("analisi", {})

                for item in analisi.get("substitucions", []):
                    if isinstance(item, dict) and item.get("professor"):
                        key = (item["professor"], item.get("hora", hora_slot))
                        seen_subs.add(key)

                for item in analisi.get("abans_jornada", []):
                    if isinstance(item, dict) and item.get("professor"):
                        key = (item["professor"], item.get("hora", hora_slot))
                        seen_abans.add(key)

                for item in analisi.get("despres_jornada", []):
                    if isinstance(item, dict) and item.get("professor"):
                        key = (item["professor"], item.get("hora", hora_slot))
                        seen_despres.add(key)

                for item in analisi.get("no_treballa_dia", []):
                    if isinstance(item, dict) and item.get("professor"):
                        key = (item["professor"], item.get("hora", hora_slot))
                        seen_no_treballa.add(key)

            total_subs += len(seen_subs)
            total_abans += len(seen_abans)
            total_despres += len(seen_despres)
            total_no_treballa += len(seen_no_treballa)

    total_sessions = sum(
        len(sh.get("sessions_simultanees", [])) for dia in horari.get("dies", []) for sh in dia.get("sessions", [])
    )

    return {
        "total_substitucions": total_subs,
        "professors_abans": total_abans,
        "professors_despres": total_despres,
        "professors_no_treballa": total_no_treballa,
        "dies_necessaris": len(horari.get("dies", [])),
        "total_sessions": total_sessions,
    }


def aplicar_estadistiques(horari: dict) -> None:
    """
    Calcula i aplica estadístiques directament al metadata de l'horari.
    Modifica l'horari in-place.
    """
    stats = calcular_estadistiques_horari(horari)
    metadata = horari.setdefault("metadata", {})
    metadata.update(stats)


def _sessions_per_dia_i_data(horari: dict) -> tuple[dict, dict]:
    """sessions_per_dia: per nom de dia normalitzat (límit per professor);
    sessions_per_data: per data ISO o nom de dia (no confondre setmanes)."""
    sessions_per_dia = defaultdict(list)
    sessions_per_data = defaultdict(list)
    for dia in horari.get("dies", []):
        dia_norm = normalitzar_dia(dia.get("dia", ""))
        data_key = dia.get("data", "") or dia_norm
        for slot in dia.get("sessions", []):
            for sessio in slot.get("sessions_simultanees", []):
                sessions_per_dia[dia_norm].append(sessio)
                sessions_per_data[data_key].append(sessio)
    return sessions_per_dia, sessions_per_data


def _data_iso(dia: dict, dia_a_data_iso: dict | None):
    _dates = (dia_a_data_iso or {}).get(normalitzar_dia(dia.get("dia", "")))
    return dia.get("data") or (_dates[0] if isinstance(_dates, list) else _dates)


def incidencies_restriccions(horari: dict, restriccions: dict, dia_a_data_iso: dict | None = None) -> list:
    """Les incidències de restriccions i preferències de l'horari (tot el cost
    llevat del dels professors, que depèn del seu horari), amb els punts que
    sumen al cost final. La fan servir el cost final i el validador."""
    sessions_per_dia, sessions_per_data = _sessions_per_dia_i_data(horari)
    incidencies = []
    for dia in horari.get("dies", []):
        dia_nom = dia.get("dia", "")
        data_iso = _data_iso(dia, dia_a_data_iso)
        data_key = data_iso if data_iso else normalitzar_dia(dia_nom)
        for slot in dia.get("sessions", []):
            hora = slot.get("hora", "")
            sessions_slot = slot.get("sessions_simultanees", [])
            for sessio in sessions_slot:
                de_la_sessio = []
                calcular_cost_slot(
                    sessio=sessio,
                    dia=dia_nom,
                    hora=hora,
                    analisi={"substitucions": [], "abans_jornada": [], "despres_jornada": [], "no_treballa_dia": []},
                    restriccions=restriccions,
                    sessions_dia=sessions_per_data.get(data_key, []),
                    sessions_slot=sessions_slot,
                    include_limit_dies=False,
                    data_iso=data_iso,
                    incidencies=de_la_sessio,
                )
                incidencies += [
                    inc._replace(
                        nom=sessio.get("nom", ""),
                        curs=sessio.get("curs", ""),
                        dia=dia_nom,
                        hora=hora,
                        data=dia.get("data") or "",
                    )
                    for inc in de_la_sessio
                ]
    # El límit per professor, un sol càlcul global
    incidencies += incidencies_limit_professors(sessions_per_dia, restriccions)
    return incidencies


def recalcular_cost_i_breakdown(horari: dict, ctx: SchedulerContext) -> dict:
    """
    Recalcula el cost total i el breakdown a partir del resultat final (independent del motor).
    Torna un dict: {cost_total, cost_breakdown, cost_desglossament, incidencies, ...}.

    El cost total és la suma dels punts de les incidències (professors,
    restriccions i preferències): les mateixes que el validador escriu amb
    la seva puntuació.
    """
    restriccions = ctx.restriccions
    breakdown = defaultdict(int)
    incidencies = []
    total_subs = 0
    total_abans = 0
    total_despres = 0
    total_no_treballa = 0

    # Normalitzar hores de context per assegurar consistència amb els horaris dels professors
    ctx.totes_hores = [_normalitzar_hora(h) for h in (ctx.totes_hores or [])]

    hi_ha_sessions = False
    for dia in horari.get("dies", []):
        dia_nom = dia.get("dia", "")
        data_iso = _data_iso(dia, ctx.dia_a_data_iso)
        for slot in dia.get("sessions", []):
            hora = slot.get("hora", "")
            hora_norm = _normalitzar_hora(hora)
            sessions_slot = slot.get("sessions_simultanees", [])
            hi_ha_sessions = hi_ha_sessions or bool(sessions_slot)

            # Costos de professors: un cop per professor i hora a la franja, amb
            # el cost individual si en té (el mateix càlcul que fan els motors)
            costos_slot = {}

            for idx, sessio in enumerate(sessions_slot):
                altres = [s for i, s in enumerate(sessions_slot) if i != idx]
                nivell_sessio = detectar_nivell_sessio(sessio)
                sessio_nom = sessio.get("nom") if isinstance(sessio, dict) else getattr(sessio, "nom", None)
                durades_per_sessio_ctx = getattr(ctx, "durades_per_sessio", None)
                durada_sessio = get_durada_per_sessio_key(
                    sessio_nom, nivell_sessio, durades_per_sessio_ctx, ctx.alliberaments_per_nivell, ctx.durada_titular
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
                    nivells_dels_grups=getattr(ctx, "nivells_dels_grups", None),
                )
                costos_slot.update(costos_professors_analisi(analisi, hora, restriccions, set(costos_slot)))

            for (tipus, professor, hora_prof), cost in costos_slot.items():
                incidencies.append(IncidenciaCost(tipus, cost, dia=dia_nom, hora=hora_prof, professor=professor))
                breakdown[tipus] += cost
            for tipus in TIPUS_COST_PROFESSOR.values():
                breakdown.setdefault(tipus, 0)
            total_subs += sum(1 for t, _, _ in costos_slot if t == "substitucio")
            total_abans += sum(1 for t, _, _ in costos_slot if t == "abans_jornada")
            total_despres += sum(1 for t, _, _ in costos_slot if t == "despres_jornada")
            total_no_treballa += sum(1 for t, _, _ in costos_slot if t == "no_treballa_dia")

    # Restriccions i preferències (sense costos de professors) i el límit per professor
    if hi_ha_sessions:
        breakdown.setdefault("preferencies", 0)
    for inc in incidencies_restriccions(horari, restriccions, ctx.dia_a_data_iso):
        incidencies.append(inc)
        breakdown[CLAU_BREAKDOWN.get(inc.concepte, inc.concepte)] += inc.punts

    # Assegurar que totes les claus estàndard estan presents (valor 0 si no hi ha cost)
    for clau in ETIQUETES_RESTRICCIONS:
        breakdown.setdefault(clau, 0)

    return {
        "cost_total": float(sum(inc.punts for inc in incidencies)),
        "cost_breakdown": dict(breakdown),
        "cost_desglossament": desglossament(incidencies),
        "incidencies": incidencies,
        "total_substitucions": total_subs,
        "professors_abans": total_abans,
        "professors_despres": total_despres,
        "professors_no_treballa": total_no_treballa,
    }
