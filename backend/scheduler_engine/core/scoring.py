"""
Lògica unificada per al càlcul de costos i penalitzacions.
"""

from typing import Any

from scheduler_engine.core.constraints import (
    _percent_penalty,
    calcular_penalitzacio_assignatures_dies_exclosos,
    calcular_penalitzacio_professors_dies,
    percent_dia_hora_fix_violation,
    sessio_in_group,
    viola_combinacions_permeses,
    violacio_no_mateix_dia,
    violacio_no_mateix_slot,
)
from scheduler_engine.core.punts import IncidenciaCost, punts_restriccio
from scheduler_engine.core.punts import pes_restriccio_dura as pes_dura
from scheduler_engine.core.punts import pes_restriccio_violada as pes_violada
from scheduler_engine.defaults import DEFAULT_COST_PROFESSORS

# Camp de l'anàlisi de disponibilitat -> tipus de cost del professor
TIPUS_COST_PROFESSOR = {
    "substitucions": "substitucio",
    "abans_jornada": "abans_jornada",
    "despres_jornada": "despres_jornada",
    "no_treballa_dia": "no_treballa_dia",
}


def pes_professor(restriccions: dict, professor: str, tipus: str) -> int:
    """Cost d'una incidència d'un professor: el seu cost individual si en té,
    si no el global del centre."""
    costos = restriccions.get("costos_professors") or {}
    individual = (costos.get("individuals") or {}).get(professor) or {}
    if tipus in individual:
        return individual[tipus]
    return (costos.get("globals") or {}).get(tipus, DEFAULT_COST_PROFESSORS[tipus])


def costos_professors_analisi(
    analisi: dict, hora: str, restriccions: dict, ja_comptats: set[tuple] | None = None
) -> dict[tuple, int]:
    """{(tipus, professor, hora): cost} de les incidències dels professors, una
    sola vegada per professor i hora.

    ja_comptats: claus ja comptades per altres exàmens de la mateixa franja. Un
    professor que vigila dos exàmens alhora deixa una sola classe: no es torna
    a comptar. Les claus noves s'hi afegeixen.
    """
    costos = {}
    for camp, tipus in TIPUS_COST_PROFESSOR.items():
        for item in analisi.get(camp, []):
            if not isinstance(item, dict) or not item.get("professor"):
                continue
            clau = (tipus, item["professor"], item.get("hora", hora))
            if clau in costos or (ja_comptats is not None and clau in ja_comptats):
                continue
            costos[clau] = pes_professor(restriccions, item["professor"], tipus)
    if ja_comptats is not None:
        ja_comptats.update(costos)
    return costos


def calcular_cost_slot(
    sessio: dict | Any,
    dia: str,
    hora: str,
    analisi: dict,
    restriccions: dict,
    sessions_dia: list[dict | Any] | None = None,
    sessions_slot: list[dict | Any] | None = None,
    include_limit_dies: bool = True,
    data_iso: str = "",
    ja_comptats: set[tuple] | None = None,
    incidencies: list[IncidenciaCost] | None = None,
) -> dict:
    """
    Calcula el cost total i el desglossament de penalitzacions per col·locar
    una sessió en un dia i hora concrets.

    ja_comptats: veure costos_professors_analisi (per no comptar dues vegades
    el mateix professor en exàmens de la mateixa franja).
    incidencies: si es passa una llista, s'hi afegeix cada part del cost amb
    punts (IncidenciaCost); la suma dels seus punts és `cost_total`. És el que
    fan servir el cost final i el validador per dir quant costa cada incidència.
    """

    def _apunta(concepte, punts, amb=(), **camps):
        if incidencies is not None and punts:
            incidencies.append(IncidenciaCost(concepte, punts, amb=tuple(amb), **camps))

    pesos_opt = restriccions.get("pesos_optimitzacio", {})

    pes_restriccio_dura = pes_dura(restriccions)
    pes_restriccio_violada = pes_violada(restriccions)

    # 2. Verificar professors amb horari estricte
    professors_estrictes = restriccions.get("restriccions_dures", {}).get("professors_horari_estricte", [])
    if isinstance(professors_estrictes, dict):
        professors_estrictes = [k for k in professors_estrictes.keys() if not k.startswith("_")]
    elif not isinstance(professors_estrictes, list):
        professors_estrictes = []

    professors_estrictes_afectats = (
        {i["professor"] for i in analisi.get("abans_jornada", [])}
        | {i["professor"] for i in analisi.get("despres_jornada", [])}
        | {i["professor"] for i in analisi.get("no_treballa_dia", [])}
    ) & set(professors_estrictes)

    # Si es viola un horari estricte, el cost és el màxim permès
    if professors_estrictes_afectats:
        _apunta("professor_estricte", pes_restriccio_violada, sorted(professors_estrictes_afectats))
        return {
            "cost_total": pes_restriccio_violada,
            "breakdown": {"professor_estricte": pes_restriccio_violada},
            "professors_estrictes_violats": list(professors_estrictes_afectats),
        }

    # 3. Cost dels professors (individual o global; un cop per professor i hora)
    costos_prof = costos_professors_analisi(analisi, hora, restriccions, ja_comptats)
    for (tipus, professor, hora_prof), cost in costos_prof.items():
        _apunta(tipus, cost, professor=professor, hora=hora_prof)

    def _suma(tipus):
        return sum(c for (t, _, _), c in costos_prof.items() if t == tipus)

    breakdown = {
        "substitucio": _suma("substitucio"),
        "abans_jornada": _suma("abans_jornada"),
        "despres_jornada": _suma("despres_jornada"),
        "no_treballa": _suma("no_treballa_dia"),
    }
    cost_base = sum(breakdown.values())

    # 4. Calcular preferències d'alumnes (Mateix dia / Dies diferents / Mateix slot)
    cost_preferencies = 0

    def _get_nom(s):
        return s.get("nom") if isinstance(s, dict) else getattr(s, "nom", None)

    nom_actual = _get_nom(sessio)
    prefs = restriccions.get("preferencies", {})

    if sessions_dia:
        noms_dia = [_get_nom(s) for s in sessions_dia if _get_nom(s)]

        # Mateix dia (percentatge)
        for pref in prefs.get("mateix_dia", []):
            assignatures = pref.get("assignatures", []) if isinstance(pref, dict) else pref
            if sessio_in_group(sessio, assignatures):
                altres_al_dia = [a for a in assignatures if a != nom_actual and a in noms_dia]
                if altres_al_dia:
                    percent = pref.get("pes", 0) if isinstance(pref, dict) else 0
                    base = pesos_opt.get("preferencia_mateix_dia", 0)
                    val = _percent_penalty(abs(base), percent) * len(altres_al_dia)
                    val = -val if base >= 0 else val
                    cost_preferencies += val
                    _apunta("preferencia_mateix_dia", val, altres_al_dia)

        # Dies diferents (percentatge)
        for pref in prefs.get("dies_diferents", []):
            assignatures = pref.get("assignatures", []) if isinstance(pref, dict) else pref
            if sessio_in_group(sessio, assignatures):
                altres_al_dia = [a for a in assignatures if a != nom_actual and a in noms_dia]
                if altres_al_dia:
                    percent = pref.get("pes", 0) if isinstance(pref, dict) else 0
                    base = pesos_opt.get("preferencia_dies_diferents", 0)
                    val = _percent_penalty(abs(base), percent) * len(altres_al_dia)
                    val = val if base >= 0 else -val
                    cost_preferencies += val
                    _apunta("preferencia_dies_diferents", val, altres_al_dia)

        # Mateix slot: penalitza si companyes del grup estan al mateix dia però hora diferent
        if sessions_slot is not None:
            noms_slot = [_get_nom(s) for s in sessions_slot if _get_nom(s)]
            for pref in prefs.get("mateix_slot", []):
                assignatures = pref.get("assignatures", []) if isinstance(pref, dict) else pref
                if sessio_in_group(sessio, assignatures):
                    percent = pref.get("pes", 0) if isinstance(pref, dict) else 0
                    # Companyes al mateix dia però en hora diferent (no al slot actual)
                    altres_dia_no_slot = [
                        a for a in assignatures if a != nom_actual and a in noms_dia and a not in noms_slot
                    ]
                    if altres_dia_no_slot:
                        if percent >= 100:
                            val = pes_restriccio_violada
                        else:
                            val = _percent_penalty(pes_restriccio_dura, percent) * len(altres_dia_no_slot)
                        cost_preferencies += val
                        _apunta("preferencia_mateix_slot", val, altres_dia_no_slot)

    breakdown["preferencies"] = cost_preferencies

    # 5. Restriccions dures i de slot
    cost_restriccions = 0

    if sessions_slot:
        # No mateix slot (percentatge)
        pct_no_slot, amb_no_slot = violacio_no_mateix_slot(sessio, sessions_slot, restriccions)
        if pct_no_slot:
            pen = punts_restriccio(restriccions, pct_no_slot)
            cost_restriccions += pen
            breakdown["no_mateix_slot"] = breakdown.get("no_mateix_slot", 0) + pen
            _apunta("no_mateix_slot", pen, amb_no_slot)

        # Combinacions permeses (hard)
        if viola_combinacions_permeses(sessio, sessions_slot, restriccions):
            cost_restriccions += pes_restriccio_dura
            breakdown["combinacio_no_permesa"] = pes_restriccio_dura
            if incidencies is not None:
                curs = sessio.get("curs", "")
                mateix_nivell = [s.get("nom") for s in sessions_slot if s is not sessio and s.get("curs", "") == curs]
                _apunta("combinacio_no_permesa", pes_restriccio_dura, mateix_nivell)

    # Dia/Hora fixos
    # Els nivells són les claus del dict analisi que comencen per 'classe_'
    nivells = [k.replace("classe_", "") for k in analisi.keys() if k.startswith("classe_")]

    pct_fix = percent_dia_hora_fix_violation(sessio, dia, hora, restriccions, nivells, data_iso)
    if pct_fix:
        pen = punts_restriccio(restriccions, pct_fix)
        cost_restriccions += pen
        breakdown["dia_hora_fix"] = breakdown.get("dia_hora_fix", 0) + pen
        _apunta("dia_hora_fix", pen)

    # No mateix dia
    if sessions_dia:
        pct_no_dia, amb_no_dia = violacio_no_mateix_dia(sessio, sessions_dia, restriccions)
        if pct_no_dia:
            pen = punts_restriccio(restriccions, pct_no_dia)
            cost_restriccions += pen
            breakdown["restriccio_dura"] = breakdown.get("restriccio_dura", 0) + pen
            _apunta("no_mateix_dia", pen, amb_no_dia)

    # Penalitzacions de professors (dies límit)
    # Nota: sessions_dia a V2 és List[Sessio], calcular_penalitzacio espera Dict[dia, List[Sessio]]
    # Fem un wrapper temporal o adaptem l'entrada
    sess_map = {dia: sessions_dia} if sessions_dia else {}
    if include_limit_dies:
        p_prof_dies = calcular_penalitzacio_professors_dies(sessio, dia, sess_map, restriccions)
        cost_restriccions += p_prof_dies
        if p_prof_dies:
            breakdown["professors_limit_dies"] = breakdown.get("professors_limit_dies", 0) + p_prof_dies
            _apunta("limit_dies_professor", p_prof_dies)

    # Assignatures dies exclosos
    p_exclosos = calcular_penalitzacio_assignatures_dies_exclosos(sessio, dia, restriccions)
    cost_restriccions += p_exclosos
    if p_exclosos:
        breakdown["assignatures_dies_exclosos"] = p_exclosos
        _apunta("assignatures_dies_exclosos", p_exclosos)

    return {
        "cost_total": cost_base + cost_preferencies + cost_restriccions,
        "breakdown": breakdown,
        "costos_professors": costos_prof,
    }
