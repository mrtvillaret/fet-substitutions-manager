"""
Cost mostrat i primitives de cost per als camins de cerca.
"""

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from planificador.compartit.constants import DEFAULT_COST_PROFESSORS, ETIQUETES_CAUSES, ETIQUETES_RESTRICCIONS
from planificador.compartit.normalitzacio import normalitzar_dia
from planificador.compartit.punts import (
    CLAU_BREAKDOWN,
    IncidenciaCost,
    desglossament,
    punts_horari_estricte,
    punts_obligatoria_incomplerta,
    punts_restriccio,
)
from planificador.compartit.punts import pes_restriccio_dura as pes_dura
from planificador.compartit.punts import pes_restriccio_violada as pes_violada
from planificador.motor.compatibilitat import BACKTRACKING, Estricte, Politiques
from planificador.motor.disponibilitat import Disponibilitat
from planificador.motor.durades import hores_ocupades, vigilancia
from planificador.motor.model import HorariEditable, Problema, congela, descongela
from planificador.motor.regles import (
    _pes_obligatori,
    _punts_percentatge,
    calcular_penalitzacio_professors_dies,
    causa_dia_hora_fix,
    coincideix_exacte,
    incidencies_limit_professors,
    percentatge_dia_hora_fix,
    sessio_al_grup,
    viola_limit_dies_professor_obligatori,
    viola_preferencia_dia_obligatoria,
    viola_restriccio_dura,
    violacio_no_mateix_dia,
    violacio_no_mateix_slot,
)
from textos import normalitzar_hora

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


def costos_professors_no_negatius(restriccions: dict) -> bool:
    """Cap cost de professor (global o individual) és negatiu: afegir un
    examen a una franja no pot abaratir el cost dels professors."""
    costos = restriccions.get("costos_professors") or {}
    valors = list({**DEFAULT_COST_PROFESSORS, **(costos.get("globals") or {})}.values())
    for individual in (costos.get("individuals") or {}).values():
        valors += list((individual or {}).values())
    return all(v >= 0 for v in valors if isinstance(v, (int, float)))


def professors_horari_estricte(restriccions: dict) -> list[str]:
    """Els professors amb horari estricte de les restriccions."""
    estrictes = (restriccions.get("restriccions_dures") or {}).get("professors_horari_estricte", [])
    if isinstance(estrictes, dict):
        return [k for k in estrictes if not k.startswith("_")]
    return list(estrictes) if isinstance(estrictes, list) else []


def estrictes_afectats(analisi: dict, estrictes: set) -> set:
    """Els professors amb horari estricte que l'anàlisi deixa fora del seu horari."""
    if not estrictes:
        return set()
    return {
        i["professor"]
        for clau in ("abans_jornada", "despres_jornada", "no_treballa_dia")
        for i in analisi.get(clau, [])
    } & estrictes


def costos_professors_analisi(
    analisi: dict, hora: str, restriccions: dict, ja_comptats: set[tuple] | None = None
) -> dict[tuple, int]:
    """{(tipus, professor, hora): cost} de les incidències dels professors, una
    sola vegada per professor i hora.

    ja_comptats: claus ja comptades per altres exàmens de la mateixa data. Un
    professor que vigila dos exàmens alhora deixa una sola classe, i una hora
    d'espera és una sola hora: no es tornen a comptar. Les claus noves s'hi afegeixen.
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


def cost_sessio(
    sessio: dict | Any,
    dia: str,
    hora: str,
    analisi: dict,
    restriccions: dict,
    sessions_dia: list[dict | Any] | None = None,
    sessions_slot: list[dict | Any] | None = None,
    inclou_limit_dies: bool = True,
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
    professors_estrictes_afectats = estrictes_afectats(analisi, set(professors_horari_estricte(restriccions)))

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

    # 4. Calcular preferències d’alumnes (mateix dia, dies diferents i mateixa franja)
    cost_preferencies = 0

    prefs = restriccions.get("preferencies", {})

    if sessions_dia:

        def _companyes(assignatures, sessions):
            """Les assignatures del grup (menys la pròpia) que tenen alguna sessió a `sessions`, pel
            nom complet o sense nivell, com la sessió pròpia."""
            return [
                a
                for a in assignatures
                if not coincideix_exacte(a, sessio) and any(coincideix_exacte(a, s) for s in sessions)
            ]

        # Mateix dia (percentatge)
        for pref in prefs.get("mateix_dia", []):
            assignatures = pref.get("assignatures", []) if isinstance(pref, dict) else pref
            if sessio_al_grup(sessio, assignatures):
                altres_al_dia = _companyes(assignatures, sessions_dia)
                if altres_al_dia:
                    percent = pref.get("pes", 0) if isinstance(pref, dict) else 0
                    base = pesos_opt.get("preferencia_mateix_dia", 0)
                    val = _punts_percentatge(abs(base), percent) * len(altres_al_dia)
                    val = -val if base >= 0 else val
                    cost_preferencies += val
                    _apunta("preferencia_mateix_dia", val, altres_al_dia)

        # Dies diferents (percentatge)
        for pref in prefs.get("dies_diferents", []):
            assignatures = pref.get("assignatures", []) if isinstance(pref, dict) else pref
            if sessio_al_grup(sessio, assignatures):
                altres_al_dia = _companyes(assignatures, sessions_dia)
                if altres_al_dia:
                    percent = pref.get("pes", 0) if isinstance(pref, dict) else 0
                    base = pesos_opt.get("preferencia_dies_diferents", 0)
                    val = _punts_percentatge(abs(base), percent) * len(altres_al_dia)
                    val = val if base >= 0 else -val
                    cost_preferencies += val
                    _apunta("preferencia_dies_diferents", val, altres_al_dia)

        # Mateix slot: penalitza si companyes del grup estan al mateix dia però hora diferent
        if sessions_slot is not None:
            for pref in prefs.get("mateix_slot", []):
                assignatures = pref.get("assignatures", []) if isinstance(pref, dict) else pref
                if sessio_al_grup(sessio, assignatures):
                    percent = pref.get("pes", 0) if isinstance(pref, dict) else 0
                    # Companyes al mateix dia però en hora diferent (no al slot actual)
                    al_slot = set(_companyes(assignatures, sessions_slot))
                    altres_dia_no_slot = [a for a in _companyes(assignatures, sessions_dia) if a not in al_slot]
                    if altres_dia_no_slot:
                        if percent >= 100:
                            val = pes_restriccio_violada
                        else:
                            val = _punts_percentatge(pes_restriccio_dura, percent) * len(altres_dia_no_slot)
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

    # Dia/Hora fixos
    # Els nivells són les claus del dict analisi que comencen per 'classe_'
    nivells = [k.replace("classe_", "") for k in analisi.keys() if k.startswith("classe_")]

    pct_fix = percentatge_dia_hora_fix(sessio, dia, hora, restriccions, nivells, data_iso)
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
    # Adaptem el mapa temporal de les sessions del dia
    clau_dia = data_iso or dia  # el límit pot portar dates
    sess_map = {clau_dia: sessions_dia} if sessions_dia else {}
    if inclou_limit_dies:
        p_prof_dies = calcular_penalitzacio_professors_dies(sessio, clau_dia, sess_map, restriccions)
        cost_restriccions += p_prof_dies
        if p_prof_dies:
            breakdown["professors_limit_dies"] = breakdown.get("professors_limit_dies", 0) + p_prof_dies
            _apunta("limit_dies_professor", p_prof_dies)

    return {
        "cost_total": cost_base + cost_preferencies + cost_restriccions,
        "breakdown": breakdown,
        "costos_professors": costos_prof,
    }


def clau_de_data(dia: dict) -> str:
    """La clau sota la qual es desen els exàmens d'un dia de l'horari: la
    seva data ISO o, si no en porta, el nom del dia normalitzat."""
    return dia.get("data", "") or normalitzar_dia(dia.get("dia", ""))


def _sessions_per_dia_i_data(horari: dict) -> tuple[dict, dict]:
    """sessions_per_dia: per nom de dia normalitzat (límit per professor);
    sessions_per_data: per data ISO o nom de dia (no confondre setmanes)."""
    sessions_per_dia = defaultdict(list)
    sessions_per_data = defaultdict(list)
    for dia in horari.get("dies", []):
        dia_norm = normalitzar_dia(dia.get("dia", ""))
        data_key = clau_de_data(dia)
        for slot in dia.get("sessions", []):
            for sessio in slot.get("sessions_simultanees", []):
                sessions_per_dia[dia_norm].append(sessio)
                sessions_per_data[data_key].append(sessio)
    return sessions_per_dia, sessions_per_data


def _data_iso(dia: dict, dia_a_data_iso: dict | None):
    _dates = (dia_a_data_iso or {}).get(normalitzar_dia(dia.get("dia", "")))
    return dia.get("data") or (_dates[0] if isinstance(_dates, list) else _dates)


def incidencies_restriccions_dia(
    dia: dict, sessions_per_data: dict, restriccions: dict, dia_a_data_iso: dict | None = None, nomes=None
) -> list:
    """Les incidències de restriccions i preferències dels exàmens d'un dia de
    l'horari, amb els punts que sumen al cost final. `sessions_per_data`: els
    exàmens de cada data (claus de `clau_de_data`), per saber quins
    coincideixen de dia. No hi ha el límit per professor, que es compta amb
    tot l'horari. `nomes`: si es passa, només les incidències d'aquests
    exàmens (`id`); els altres hi són com a context.

    És l'únic lloc on es calculen: el cost final, el validador i la cerca del
    backtracking (que les suma dia a dia mentre col·loca exàmens) passen per aquí."""
    dia_nom = dia.get("dia", "")
    data_iso = _data_iso(dia, dia_a_data_iso)
    data_key = data_iso if data_iso else normalitzar_dia(dia_nom)
    incidencies = []
    for slot in dia.get("sessions", []):
        hora = slot.get("hora", "")
        sessions_slot = slot.get("sessions_simultanees", [])
        for sessio in sessions_slot:
            if nomes is not None and id(sessio) not in nomes:
                continue
            de_la_sessio = []
            cost_sessio(
                sessio=sessio,
                dia=dia_nom,
                hora=hora,
                analisi={"substitucions": [], "abans_jornada": [], "despres_jornada": [], "no_treballa_dia": []},
                restriccions=restriccions,
                sessions_dia=sessions_per_data.get(data_key, []),
                sessions_slot=sessions_slot,
                inclou_limit_dies=False,
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
    return incidencies


def incidencies_restriccions(horari: dict, restriccions: dict, dia_a_data_iso: dict | None = None) -> list:
    """Les incidències de restriccions i preferències de l'horari (tot el cost
    llevat del dels professors, que depèn del seu horari), amb els punts que
    sumen al cost final. La fan servir el cost final i el validador."""
    sessions_per_dia, sessions_per_data = _sessions_per_dia_i_data(horari)
    incidencies = []
    for dia in horari.get("dies", []):
        incidencies += incidencies_restriccions_dia(dia, sessions_per_data, restriccions, dia_a_data_iso)
    # El límit per professor, un sol càlcul global, per data (les regles poden portar dates)
    incidencies += incidencies_limit_professors(sessions_per_data, restriccions)
    incidencies += incidencies_mateix_dia_obligatori(sessions_per_data, restriccions)
    return incidencies


def incidencies_mateix_dia_obligatori(sessions_per_data: dict, restriccions: dict) -> list:
    """Una «mateixa data» obligatòria amb els exàmens en dates diferents. Els motors
    no la trenquen mai; editant a mà sí, i suma `restriccio_dura_violada` un cop per regla
    (com l'horari estricte). Les dates són les claus de `sessions_per_data`."""
    incidencies = []
    for pref in (restriccions.get("preferencies") or {}).get("mateix_dia", []):
        grup = pref.get("assignatures", []) if isinstance(pref, dict) else pref
        if not _pes_obligatori(pref.get("pes", 0) if isinstance(pref, dict) else 0):
            continue
        per_data = {
            data: sorted({s.get("nom", "") for s in sessions if sessio_al_grup(s, grup)})
            for data, sessions in sessions_per_data.items()
        }
        per_data = {data: noms for data, noms in per_data.items() if noms}
        if len(per_data) > 1:
            noms = sorted({nom for llista in per_data.values() for nom in llista})
            incidencies.append(
                IncidenciaCost(
                    "mateix_dia_obligatori",
                    punts_obligatoria_incomplerta(restriccions),
                    nom=", ".join(noms),
                    amb=tuple(sorted(per_data)),
                )
            )
    return incidencies


@dataclass(frozen=True, slots=True)
class Cost:
    total: float
    incidencies: tuple[IncidenciaCost, ...]
    resum: Mapping
    recomptes: Mapping

    def a_info(self) -> dict:
        return {
            "cost_total": self.total,
            "cost_breakdown": descongela(self.resum),
            "cost_desglossament": desglossament(self.incidencies),
            "incidencies": list(self.incidencies),
            **descongela(self.recomptes),
        }


def cost(horari: HorariEditable | dict, problema: Problema, disponibilitat: Disponibilitat | None = None) -> Cost:
    """Cost mostrat: cada hora d'un professor un sol cop per data, i totes les ocurrències.

    Un professor amb horari estricte que en queda fora (arriba abans, es queda
    més o no treballa aquell dia) suma `restriccio_dura_violada` un cop per
    franja: els motors no ho fan mai, però a mà sí que es pot.
    La regla d'or i les agrupacions separades no sumen punts.
    Només llegeix el document: la cerca pot passar el seu horari sense copiar-lo.
    """
    document = horari.document if isinstance(horari, HorariEditable) else horari
    disponible = disponibilitat or Disponibilitat(problema)
    restriccions = problema.regles.a_diccionari()
    resum = defaultdict(int)
    incidencies = []
    recomptes = dict(total_substitucions=0, professors_abans=0, professors_despres=0, professors_no_treballa=0)
    tipus_recompte = {
        "substitucio": "total_substitucions",
        "abans_jornada": "professors_abans",
        "despres_jornada": "professors_despres",
        "no_treballa_dia": "professors_no_treballa",
    }
    graella = [normalitzar_hora(h) for h in problema.graella]
    estrictes = set(professors_horari_estricte(restriccions))
    punts_estricte = punts_horari_estricte(restriccions)
    hi_ha_sessions = False
    mapa_dies = descongela(problema.mapa_dies)
    for dia in document.get("dies", []):
        dia_nom = dia.get("dia", "")
        data_iso = _data_iso(dia, mapa_dies)
        # Cada hora d'un professor (substitució, espera abans o després, no treballa)
        # compta un sol cop per data, encara que surti en exàmens de franges diferents.
        comptats_data = set()
        for franja in dia.get("sessions", []):
            hora = franja.get("hora", "")
            hora_normalitzada = normalitzar_hora(hora)
            sessions = franja.get("sessions_simultanees", [])
            hi_ha_sessions = hi_ha_sessions or bool(sessions)
            costos_franja, estrictes_franja = {}, set()
            for index, sessio in enumerate(sessions):
                altres = [s for i, s in enumerate(sessions) if i != index]
                durada = vigilancia(sessio.get("nom"), problema.durades_vigilancia, problema.durada_titular)
                hores = hores_ocupades(hora_normalitzada, graella, durada)
                analisi = disponible.consulta(sessio, dia_nom, hora_normalitzada, data_iso, hores, hores, altres)
                costos_franja.update(costos_professors_analisi(analisi, hora, restriccions, comptats_data))
                for professor in sorted(estrictes_afectats(analisi, estrictes) - estrictes_franja):
                    estrictes_franja.add(professor)
                    incidencies.append(
                        IncidenciaCost(
                            "professor_estricte", punts_estricte, dia=dia_nom, hora=hora, professor=professor
                        )
                    )
                    resum["professor_estricte"] += punts_estricte
            for (tipus, professor, hora_prof), punts in costos_franja.items():
                incidencies.append(IncidenciaCost(tipus, punts, dia=dia_nom, hora=hora_prof, professor=professor))
                resum[tipus] += punts
            for tipus in TIPUS_COST_PROFESSOR.values():
                resum.setdefault(tipus, 0)
            for tipus, clau in tipus_recompte.items():
                recomptes[clau] += sum(1 for t, _, _ in costos_franja if t == tipus)
    if hi_ha_sessions:
        resum.setdefault("preferencies", 0)
    for incidencia in incidencies_restriccions(document, restriccions, mapa_dies):
        incidencies.append(incidencia)
        resum[CLAU_BREAKDOWN.get(incidencia.concepte, incidencia.concepte)] += incidencia.punts
    for clau in ETIQUETES_RESTRICCIONS:
        resum.setdefault(clau, 0)
    return Cost(float(sum(i.punts for i in incidencies)), tuple(incidencies), congela(resum), congela(recomptes))


@dataclass(frozen=True, slots=True)
class CausaDura:
    clau: str
    etiqueta: str
    detall: str


def causa_dura(
    sessio: dict,
    franja,
    regles,
    nivells,
    sessions_dia=(),
    sessions_franja=(),
    sessions_per_dia=None,
    analisi=None,
    politiques: Politiques = BACKTRACKING,
    *,
    restriccions: dict | None = None,
    sessions_per_data=None,
) -> CausaDura | None:
    """Primera causa obligatòria, amb l'ordre actual i el context del camí.

    `sessions_per_dia` (per nom de dia) serveix al límit per professor;
    `sessions_per_data` (per data, o per nom de dia sense dates), a les
    preferències de dia obligatòries. Sense `sessions_per_data`, aquestes miren
    `sessions_per_dia`."""
    if restriccions is None:
        restriccions = regles.a_diccionari()
    dia, hora, prefix = franja.dia, franja.hora, franja.prefix
    nom = sessio.get("nom", "")

    def resultat(clau, detall):
        return CausaDura(clau, ETIQUETES_CAUSES[clau], detall)

    causa, percent = causa_dia_hora_fix(sessio, dia, hora, restriccions, list(nivells), franja.data_iso or "")
    if percent >= 100:
        return resultat(causa, f"{nom} — slot {dia} {hora} no permès")
    if viola_restriccio_dura(sessio, list(sessions_dia), restriccions):
        return resultat("no_mateix_dia", f"{nom} — conflicte amb sessió al dia {prefix or dia}")
    if sessions_per_dia is not None:
        per_data = sessions_per_dia if sessions_per_data is None else sessions_per_data
        # Per data (les regles poden portar dates; un nom de dia compta totes les seves dates)
        if viola_limit_dies_professor_obligatori(sessio, prefix or dia, per_data, restriccions):
            return resultat("limit_dies_professor", f"{nom} — professor supera límit el {dia}")
        if viola_preferencia_dia_obligatoria(sessio, prefix or dia, per_data, restriccions):
            return resultat("preferencia_dia", f"{nom} — viola preferència de dia obligatòria el {dia}")
    if politiques.estricte == Estricte.DURA and analisi:
        afectats = estrictes_afectats(analisi, set(professors_horari_estricte(restriccions)))
        if afectats:
            return resultat("professors_estrictes", f"Professors {', '.join(sorted(afectats))} amb horari estricte")
    return None
