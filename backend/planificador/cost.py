"""
Cost i incidències d'un horari d'exàmens ja fet (POST /api/scheduler/recalcular-cost):
el que la pantalla mostra per a cada franja i per a cada examen quan l'horari
s'edita a mà.
"""

import xml.etree.ElementTree as ET
from collections import defaultdict
from types import SimpleNamespace

from errors_domini import NoValid
from horari.domain import Dia
from planificador.alliberaments import extreure_hores_examen_des_alliberaments
from planificador.config import aplica_restriccions_derivades, carrega_config
from planificador.planificacio import xml_del_dia
from planificador.services import desa_ultim_resultat
from scheduler_engine.core.availability import analitzar_disponibilitat_sessio
from scheduler_engine.core.constraints import sessio_in_group
from scheduler_engine.core.date_mapping import construir_mapa_dia_data_iso
from scheduler_engine.core.durada import detectar_nivell_sessio, get_durada_per_sessio_key
from scheduler_engine.core.horaris_xml import horaris_professors as llegeix_horaris_professors
from scheduler_engine.core.normalitzacio import normalitzar_dia, normalitzar_text
from scheduler_engine.core.scoring import pes_professor
from scheduler_engine.estadistiques import recalcular_cost_i_breakdown
from scheduler_engine.validacio import ValidadorHorari
from textos import normalitzar_hora as _normalitzar_hora


def _substitucio(prof, hora, dia, item):
    act = item.get("activitat", {})
    assig = act.get("assignatura", "Assignatura")
    grp = act.get("grup", "un grup")
    return f"🚨 {prof} → ha de ser SUBSTITUÏT a {assig} amb {grp} a les {hora} el {dia}"


def _abans(prof, hora, dia, item):
    return f"🕐 {prof} → arriba abans a {hora} el {dia} (primera hora: {item.get('primera_hora', '?')})"


def _despres(prof, hora, dia, item):
    return f"🕐 {prof} → queda més estona a {hora} el {dia} (última hora: {item.get('ultima_hora', '?')})"


def _no_treballa(prof, hora, dia, item):
    return f"🚫 {prof} → no treballa aquest dia a les {hora} el {dia}"


# (clau de l'anàlisi de disponibilitat i tipus de cost, missatge), en l'ordre en què surten
TIPUS_INCIDENCIA = (
    ("substitucions", "substitucio", _substitucio),
    ("abans_jornada", "abans_jornada", _abans),
    ("despres_jornada", "despres_jornada", _despres),
    ("no_treballa_dia", "no_treballa_dia", _no_treballa),
)


def incidencies(analisi: dict, hora: str, dia: str, restriccions: dict):
    """(tipus de cost, professor, hora, avís amb la puntuació, pes) de cada
    incidència de l'anàlisi d'una sessió, sense repetir-ne cap."""
    vistes = set()
    for clau, tipus, missatge in TIPUS_INCIDENCIA:
        for item in analisi.get(clau, []):
            prof = item.get("professor")
            if not prof:
                continue
            hora_item = item.get("hora", hora)
            if (tipus, prof, hora_item) in vistes:
                continue
            vistes.add((tipus, prof, hora_item))
            pes = pes_professor(restriccions, prof, tipus)
            yield tipus, prof, hora_item, f"{missatge(prof, hora_item, dia, item)} (punt: {pes})", pes


class IncidenciesFranja:
    """Cost i avisos d'una franja: cada incidència (tipus, professor, hora)
    compta una sola vegada encara que surti a més d'un examen."""

    def __init__(self):
        self.cost = 0
        self.avisos = []
        self._vistes = set()

    def afegeix(self, tipus, prof, hora, avis, pes):
        if (tipus, prof, hora) in self._vistes:
            return
        self._vistes.add((tipus, prof, hora))
        self.cost += pes
        self.avisos.append(avis)


def conflicte_de_nivell(sessions: list) -> bool:
    """Si a la franja hi ha més d'un examen del mateix nivell."""
    nivell_per_item = {}
    for sessio in sessions:
        item_id = sessio.get("item_id") or sessio.get("id") or f"{sessio.get('nom')}_{sessio.get('curs')}"
        curs = sessio.get("curs", "")
        if curs and item_id not in nivell_per_item:
            nivell_per_item[item_id] = curs
    nivells = list(nivell_per_item.values())
    return len(nivells) != len(set(nivells))


def _sessions_per_dia(horari: dict) -> dict:
    """Sessions de cada dia, pel nom tal com ve i pel nom normalitzat."""
    sessions = defaultdict(list)
    for dia_data in horari.get("dies", []):
        dia_nom = dia_data.get("dia", "")
        dia_norm = normalitzar_dia(dia_nom)
        for slot_data in dia_data.get("sessions", []):
            for sessio_data in slot_data.get("sessions_simultanees", []):
                sessions[dia_nom].append(sessio_data)
                if dia_norm and dia_norm != dia_nom:
                    sessions[dia_norm].append(sessio_data)
    return sessions


def excessos_limit_dies(horari: dict, restriccions: dict) -> list[str]:
    """ "Professor +n" per a cada professor amb més exàmens dels permesos als
    dies restringits (restricció professors_limit_dies_especifics)."""
    limits = (restriccions.get("restriccions_dures") or {}).get("professors_limit_dies_especifics") or {}
    limits = {k: v for k, v in limits.items() if not k.startswith("_")}
    if not limits:
        return []
    sessions_per_dia = _sessions_per_dia(horari)
    excessos = []
    for professor, config_prof in limits.items():
        assignatures = config_prof.get("assignatures", [])
        max_examens = int(config_prof.get("max_examens", 999))
        examens = sum(
            1
            for dia in config_prof.get("dies_restringits", [])
            for s in sessions_per_dia.get(dia, [])
            if professor in {e.get("titular") for e in s.get("examens", []) if e.get("titular")}
            and sessio_in_group(s, assignatures)
        )
        if examens > max_examens:
            excessos.append(f"{professor} +{examens - max_examens}")
    return excessos


def hores_lectives(root, hores_examen) -> list[str]:
    """Hores de l'XML (en l'ordre de l'XML) més les d'examen que no hi siguin;
    si se n'hi afegeix alguna, ordenades. Sense hores a l'XML, les d'examen."""

    def _minuts(h):
        try:
            hh, mm = h.split(":")[:2]
            return int(hh) * 60 + int(mm)
        except (ValueError, TypeError, IndexError):
            return 0

    hores = []
    for day in root.findall(".//Day"):
        for hour in day.findall("Hour"):
            h = hour.get("name")
            if h and h not in hores:
                hores.append(h)
    hores = [_normalitzar_hora(h) for h in hores if h]
    if not hores:
        return [_normalitzar_hora(h) for h in (hores_examen or [])]
    falten = [h for h in (_normalitzar_hora(h) for h in (hores_examen or [])) if h and h not in hores]
    if falten:
        hores = sorted({*hores, *falten}, key=_minuts)
    return hores


def recalcula(payload, institucio: str, dia_planificacio: Dia) -> dict:
    """El cost, els avisos i els conflictes d'un horari editat a mà (sense
    regenerar-lo); el desa com a últim horari. L'horari (XML) és el de la data
    de referència de la petició o, si no n'hi ha, la de l'horari; si tampoc,
    el del planificador (`dia_planificacio`)."""
    horari = payload.horari.model_dump(exclude_unset=True, by_alias=True)
    if not horari or not horari.get("dies"):
        raise NoValid("L'horari no conté dies", codi="horari_sense_dies")

    cfg = carrega_config(institucio)
    restriccions = cfg.restriccions
    nivells_actius = cfg.nivells_actius()
    selected_dates = cfg.dates(payload.selected_dates, nivells_actius)
    no_subst_norm = {normalitzar_text(a) for a in cfg.no_substituir if a}

    hores_examen, _ = extreure_hores_examen_des_alliberaments(cfg.alliberaments)

    data_ref = payload.data_referencia or (horari.get("metadata") or {}).get("data_inici")
    dia = Dia.de_text(data_ref, institucio) if data_ref else dia_planificacio
    data_ref = dia.iso

    dies_horari = [d.get("dia") for d in horari.get("dies", []) if d.get("dia")]
    dia_a_data_iso = construir_mapa_dia_data_iso(
        dies_utilitzar=dies_horari,
        selected_dates=selected_dates,
        data_inici_iso=data_ref,
    )

    xml_path = xml_del_dia(dia)

    # Carregar horaris professors
    tree = ET.parse(xml_path)
    root = tree.getroot()

    totes_hores = hores_lectives(root, hores_examen)

    # Aplicar també en recàlcul la restricció derivada de slots vàlids per nivell (marques 🟦).
    aplica_restriccions_derivades(
        restriccions, cfg.alliberaments, nivells_actius, dies_horari, dia_a_data_iso, totes_hores
    )

    horaris_professors = llegeix_horaris_professors(root, cfg.ultim_professor, normalitza_hores=True)

    # Recalcular cost amb el mòdul d'estadístiques
    ctx = SimpleNamespace(
        restriccions=restriccions,
        horaris_professors=horaris_professors,
        hores_examen=hores_examen,
        durada_titular=cfg.durada_titular,
        no_substituir_norm=no_subst_norm,
        totes_hores=totes_hores,
        nivells_actius=nivells_actius,
        dia_a_data_iso=dia_a_data_iso,
        alliberaments_per_nivell=cfg.alliberaments,
        durades_per_sessio=cfg.durades_per_sessio,
    )
    cost_info = recalcular_cost_i_breakdown(horari, ctx)

    # Cost, avisos i conflictes de cada franja
    slots_info = []
    conflicte_global = False
    for dia in horari.get("dies", []):
        dia_nom = dia.get("dia", "")
        _dates = dia_a_data_iso.get(normalitzar_dia(dia_nom))
        data_iso_slot = dia.get("data") or (_dates[0] if isinstance(_dates, list) else _dates)
        for slot in dia.get("sessions", []):
            hora = slot.get("hora", "")
            hora_norm = _normalitzar_hora(hora)
            sessions_sim = slot.get("sessions_simultanees", [])
            conflicte_nivell = conflicte_de_nivell(sessions_sim)
            conflicte_global = conflicte_global or conflicte_nivell

            franja = IncidenciesFranja()
            item_avisos = {}
            for idx, sessio in enumerate(sessions_sim):
                altres = [s for i, s in enumerate(sessions_sim) if i != idx]
                nivell_sessio = detectar_nivell_sessio(sessio, nivells_actius or [])
                sessio_nom_d = sessio.get("nom") if isinstance(sessio, dict) else None
                durada_sessio = get_durada_per_sessio_key(
                    sessio_nom_d, nivell_sessio, cfg.durades_per_sessio, cfg.alliberaments, cfg.durada_titular
                )
                durada_exam = get_durada_per_sessio_key(
                    sessio_nom_d, nivell_sessio, cfg.durades_examen_per_sessio, cfg.alliberaments, cfg.durada_titular
                )
                durada_exam = max(durada_exam, durada_sessio)
                if hora_norm in totes_hores:
                    idx_inici = totes_hores.index(hora_norm)
                    hores_ocupades = totes_hores[idx_inici : min(idx_inici + max(1, durada_sessio), len(totes_hores))]
                    hores_exam = totes_hores[idx_inici : min(idx_inici + max(1, durada_exam), len(totes_hores))]
                else:
                    hores_ocupades = [hora_norm]
                    hores_exam = [hora_norm]
                analisi = analitzar_disponibilitat_sessio(
                    sessio=sessio,
                    dia=dia_nom,
                    hora=hora_norm,
                    horaris_professors=horaris_professors,
                    totes_hores=totes_hores,
                    nivells_actius=nivells_actius,
                    durada_titular=durada_sessio,
                    no_substituir_norm=no_subst_norm,
                    sessions_al_slot=altres,
                    hores_override=hores_exam,
                    hores_supervisio=hores_ocupades,
                    alliberaments_per_nivell=cfg.alliberaments,
                    data_iso=data_iso_slot,
                )
                # El validador posterior fa servir l'anàlisi nova
                if isinstance(sessio, dict):
                    sessio["analisi"] = analisi

                incidencies_sessio = list(incidencies(analisi, hora, dia_nom, restriccions))
                for incidencia in incidencies_sessio:
                    franja.afegeix(*incidencia)
                # Els avisos de cada examen, per a l'editor (per _uid i per item_id)
                if isinstance(sessio, dict) and incidencies_sessio:
                    avisos_sessio = [avis for _, _, _, avis, _ in incidencies_sessio]
                    for clau in (sessio.get("_uid"), sessio.get("item_id")):
                        if clau:
                            item_avisos[clau] = avisos_sessio

            avisos = franja.avisos
            if conflicte_nivell:
                avisos.insert(0, "⚠️ CONFLICTE: Múltiples exàmens del mateix nivell!")

            slots_info.append(
                {
                    "slot_key": f"{data_iso_slot or dia_nom}_{hora}",
                    "cost": franja.cost,
                    "breakdown": {"sessions": len(sessions_sim)},
                    "conflicte_nivell": conflicte_nivell,
                    "avisos": avisos,
                    "item_avisos": item_avisos,
                }
            )

    # Netejar logs antics per evitar que el validador ometi avisos (p. ex. LÍMIT DIES)
    if horari.get("metadata", {}).get("logs"):
        horari["metadata"]["logs"] = []
    validation_result = ValidadorHorari(horari, restriccions, cfg.no_substituir).validar()

    breakdown_details = {}
    excessos = excessos_limit_dies(horari, restriccions)
    if excessos:
        breakdown_details["limit_dies_professor"] = excessos

    # L'horari editat a mà passa a ser l'últim, amb el cost i les incidències nous
    horari_desat = dict(
        horari,
        metadata={
            **(horari.get("metadata") or {}),
            "cost_total": cost_info.get("cost_total", 0),
            "logs": validation_result.get("logs", []),
            "total_substitucions": cost_info.get("total_substitucions", 0),
            "professors_abans": cost_info.get("professors_abans", 0),
            "professors_despres": cost_info.get("professors_despres", 0),
            "professors_no_treballa": cost_info.get("professors_no_treballa", 0),
        },
    )
    desa_ultim_resultat(institucio, horari_desat)

    return {
        "cost_total": cost_info.get("cost_total", 0),
        "cost_breakdown": cost_info.get("cost_breakdown", {}),
        "cost_breakdown_details": breakdown_details,
        "slots": slots_info,
        "valid": not conflicte_global,
        "logs": validation_result.get("logs", []),
        "stats": {
            "total_substitucions": cost_info.get("total_substitucions", 0),
            "professors_abans": cost_info.get("professors_abans", 0),
            "professors_despres": cost_info.get("professors_despres", 0),
            "professors_no_treballa": cost_info.get("professors_no_treballa", 0),
        },
    }
