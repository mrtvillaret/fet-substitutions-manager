"""Configuració i XML a problema immutable, sense fitxers JSON intermedis."""

import hashlib
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from copy import deepcopy
from dataclasses import replace

from planificador.alliberaments import _hores_lectives_des_de_xml
from planificador.compartit.dates import construir_mapa_dia_data_iso
from planificador.compartit.franja import franja
from planificador.compartit.horaris_xml import horaris_professors
from planificador.compartit.normalitzacio import normalitzar_text
from planificador.config import aplica_restriccions_derivades
from planificador.motor.compatibilitat import Graella, Particio, Politiques
from planificador.motor.durades import examen, vigilancia
from planificador.motor.model import DataAmbOrigen, Examen, Item, Problema, congela, descongela
from planificador.motor.regles import Regles, coincideix_normalitzat, construeix_regles
from textos import normalitzar_hora


def graella_motor(arrel) -> list[str]:
    """Ordre d'aparició i text cru de l'XML, inclosos els formats sense zero."""
    hores = []
    for dia in arrel.findall(".//Day"):
        for elem in dia.findall("Hour"):
            text = elem.get("name")
            if text and text not in hores:
                hores.append(text)
    return hores


def graella_cost(arrel, hores_examen) -> list[str]:
    """Normalitza; només reordena si afegeix hores d'inici absents de l'XML."""

    return graella_cost_de_hores(graella_motor(arrel), hores_examen)


def graella_cost_de_hores(hores_motor, hores_examen) -> list[str]:
    """Projecció de la graella ja llegida, sense tornar a obrir l'XML."""

    def minuts(hora):
        try:
            hh, mm = hora.split(":")[:2]
            return int(hh) * 60 + int(mm)
        except (ValueError, TypeError, IndexError):
            return 0

    hores = [normalitzar_hora(h) for h in hores_motor if h]
    if not hores:
        return [normalitzar_hora(h) for h in (hores_examen or [])]
    falten = [h for h in (normalitzar_hora(h) for h in (hores_examen or [])) if h and h not in hores]
    return sorted({*hores, *falten}, key=minuts) if falten else hores


def graella_derivada(xml_path, hores_examen) -> list[str]:
    """La tercera graella, normalitzada i ordenada, usada pels alliberaments."""
    return _hores_lectives_des_de_xml(xml_path, fallback=hores_examen)


def mapa_dies(dies, dates, data_inici=None) -> dict:
    return construir_mapa_dia_data_iso(dies, dates, data_inici)


def franges(dies, dates, hores) -> tuple:
    # Les dates de candidats no es filtren pel mapa de noms de dia.
    return tuple(franja(f"{prefix}_{hora}") for prefix in (dates or dies) for hora in hores)


def _examen(dades, cfg, politiques) -> Examen:
    nom = dades.get("nom")
    return Examen(
        id=dades.get("id"),
        nom=nom,
        nom_base=dades.get("nom_base"),
        curs=dades.get("curs"),
        hores_vigilancia=vigilancia(nom, cfg.durades_per_sessio, cfg.durada_titular),
        hores_examen=examen(
            nom,
            cfg.durades_examen_per_sessio,
            cfg.durades_per_sessio,
            cfg.durada_examen,
            cfg.durada_titular,
        ),
        dades=congela(dades),
    )


def construeix_problema(
    cfg,
    xml_path,
    nivells,
    dies,
    dates,
    dia_a_data_iso,
    hores_examen,
    politiques: Politiques,
    *,
    restriccions_resoltes=None,
) -> Problema:
    arrel = ET.parse(xml_path).getroot()
    if politiques.graella == Graella.COST:
        graella = graella_cost(arrel, hores_examen)
    elif politiques.graella == Graella.DERIVADA:
        graella = graella_derivada(xml_path, hores_examen)
    else:
        graella = graella_motor(arrel)
    # La funció compartida modifica també els contenidors de dins: còpia profunda.
    restriccions = deepcopy(cfg.restriccions if restriccions_resoltes is None else restriccions_resoltes)
    if restriccions_resoltes is None:
        aplica_restriccions_derivades(restriccions, cfg.alliberaments, nivells, dies, dia_a_data_iso, graella)
    examens = []
    for nivell in nivells:
        for nom, dades in cfg.config.get("assignatures", {}).items():
            assignacions = [
                a for a in dades.get("assignacions", []) if nivell in cfg.nivells_dels_grups.nivells(a["grup"])
            ]
            if assignacions:
                examens.append(
                    _examen(
                        {
                            "id": f"{nom}_{nivell}",
                            "nom": f"{nom} ({nivell})",
                            "nom_base": nom,
                            "curs": nivell,
                            "examens": assignacions,
                        },
                        cfg,
                        politiques,
                    )
                )
    procedencia = [DataAmbOrigen.de_text(d, "dates_resoltes") for d in dates]
    for nivell, dades in (cfg.alliberaments or {}).items():
        if isinstance(dades, dict):
            procedencia.extend(
                DataAmbOrigen.de_text(d, f"alliberaments.{nivell}.dates") for d in dades.get("dates", [])
            )
            procedencia.extend(
                DataAmbOrigen.de_text(d, f"alliberaments.{nivell}.config") for d in (dades.get("config") or {})
            )
    return Problema(
        examens=tuple(examens),
        franges=franges(dies, dates, hores_examen),
        graella=tuple(graella),
        hores_inici=tuple(hores_examen),
        horaris_professors=congela(
            horaris_professors(arrel, cfg.ultim_professor, normalitza_hores=politiques.hora_normalitzada)
        ),
        nivells=tuple(nivells),
        dies=tuple(dies),
        dates=tuple(procedencia),
        mapa_dies=congela(dia_a_data_iso),
        regles=construeix_regles(restriccions, examens),
        alliberaments=congela(cfg.alliberaments),
        durades_vigilancia=congela(cfg.durades_per_sessio),
        durades_examen=congela(cfg.durades_examen_per_sessio),
        durada_titular=cfg.durada_titular,
        durada_examen=cfg.durada_examen,
        no_substituir=frozenset(cfg.no_substituir),
        taules_grups=congela(cfg.nivells_dels_grups.a_config()),
    )


def _agrupacions(regles: Regles) -> list[dict]:
    return [{"nom": regla.nom, "assignatures": list(regla.noms)} for regla in regles.agrupacions if regla.noms]


def _items_tipats(items, originals: tuple[Examen, ...]) -> tuple[Item, ...]:
    per_id = {(e.id, e.curs): e for e in originals}
    return tuple(
        Item(
            it.get("item_id"),
            it.get("nom"),
            tuple(replace(per_id[(s["id"], s.get("curs"))], dades=congela(s)) for s in it["sessions"]),
            congela(it),
        )
        for it in items
    )


def particio_antiga(examens: tuple[Examen, ...], regles: Regles) -> tuple[Item, ...]:
    nivells = dict.fromkeys(e.curs for e in examens)
    items = []
    for nivell in nivells:
        sessions = [e.a_diccionari() for e in examens if e.curs == nivell]
        items.extend(_particio_antiga(sessions, _agrupacions(regles)))
    return _items_tipats(items, examens)


def particio_nova(examens: tuple[Examen, ...], regles: Regles, nivells) -> tuple[Item, ...]:
    sessions_per_nivell = {n: [e.a_diccionari() for e in examens if e.curs == n] for n in nivells}
    return _items_tipats(
        _particio_nova(sessions_per_nivell, nivells, regles.a_diccionari(), _agrupacions(regles)), examens
    )


def particio(problema: Problema, politiques: Politiques) -> tuple[Item, ...]:
    if politiques.particio == Particio.ANTIGA:
        items = particio_antiga(problema.examens, problema.regles)
        if politiques.clau_item_nom:
            return _items_recuit(items, problema.regles)
        return items
    return particio_nova(problema.examens, problema.regles, problema.nivells)


def _particio_antiga(sessions_pendents: list[dict], grups_raw: list[dict]) -> list[dict]:
    """
    Agrupa sessions que han d'anar a la mateixa franja (mateix_slot) usant normalització robusta.
    """
    if not grups_raw:
        return [
            {"sessions": [s], "nom": s.get("nom"), "examens_count": len(s.get("examens", []))}
            for s in sessions_pendents
        ]

    # Normalitzar grups per comparació robusta i conservar el nom
    grups_norm = []
    for grup in grups_raw:
        assignatures = grup.get("assignatures", []) if isinstance(grup, dict) else grup
        if isinstance(assignatures, list) and assignatures:
            grups_norm.append(
                {
                    "nom": (grup.get("nom", "") if isinstance(grup, dict) else ""),
                    "assignatures": [normalitzar_text(n) for n in assignatures],
                }
            )

    # Mapa de nom_normalitzat -> índex del grup
    nom_a_grup = {}
    for idx, grup in enumerate(grups_norm):
        for nom_norm in grup["assignatures"]:
            nom_a_grup[nom_norm] = idx

    # Mapa de sessions per nom normalitzat per a cerca ràpida
    sessions_per_nom_norm = defaultdict(list)
    for s in sessions_pendents:
        sessions_per_nom_norm[normalitzar_text(s.get("nom", ""))].append(s)
        sessions_per_nom_norm[normalitzar_text(s.get("nom_base", ""))].append(s)

    visitats, items = set(), []

    def clau(s):
        return f"{s.get('nom')}|{s.get('curs')}"

    for sessio in sessions_pendents:
        if clau(sessio) in visitats:
            continue

        s_nom_norm = normalitzar_text(sessio.get("nom", ""))
        s_base_norm = normalitzar_text(sessio.get("nom_base", ""))

        index_grup = nom_a_grup.get(s_nom_norm)
        if index_grup is None:
            index_grup = nom_a_grup.get(s_base_norm)

        if index_grup is not None:
            membres = []
            # Recollir TOTES les sessions que coincideixin amb qualsevol nom del grup
            for n_norm in grups_norm[index_grup]["assignatures"]:
                for sessio_trobada in sessions_per_nom_norm.get(n_norm, []):
                    if clau(sessio_trobada) not in visitats:
                        membres.append(sessio_trobada)
                        visitats.add(clau(sessio_trobada))

            if membres:
                grup_nom = (grups_norm[index_grup].get("nom") or "").strip()
                item = {
                    "sessions": membres,
                    "nom": grup_nom if grup_nom else f"grup_{index_grup} ({len(membres)} assig)",
                    "examens_count": sum(len(s.get("examens", [])) for s in membres),
                }
                _assigna_id(item)
                items.append(item)
        else:
            visitats.add(clau(sessio))
            item = {"sessions": [sessio], "nom": sessio.get("nom"), "examens_count": len(sessio.get("examens", []))}
            _assigna_id(item)
            items.append(item)
    return items


def _assigna_id(item: dict) -> None:
    """Assigna un item_id estable i el propaga a les sessions de l'ítem."""
    sessions = item.get("sessions", [])
    base = "|".join(sorted(f"{s.get('id') or s.get('nom')}::{s.get('curs') or ''}" for s in sessions))
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]
    item_id = f"item_{digest}"
    item["item_id"] = item_id
    item["item_label"] = item.get("nom") or item_id
    for s in sessions:
        s["item_id"] = item_id
        s["item_label"] = item.get("nom") or item_id


def _particio_nova(sessions_per_nivell, nivells_actius, restriccions, grups_amb_noms) -> list[dict]:
    """Garanteix que cada nivell té els seus exàmens agrupats en 'paquets' únics (sense fusionar forçat)."""
    tots_els_items = []

    # 1. Obtenir agrupacions configurades (normalitzades) amb els seus noms
    # Crear estructura: [(nom, [assignatures_normalitzades]), ...]
    grups_ms_amb_noms = [
        (g.get("nom", ""), [normalitzar_text(n) for n in g.get("assignatures", [])])
        for g in grups_amb_noms
        if g.get("assignatures")
    ]

    for nivell in nivells_actius:
        sessions_pendents = sessions_per_nivell.get(nivell, [])
        if not sessions_pendents:
            continue

        # Crear mapa de ID -> Sessio per evitar duplicats
        sessio_per_id = {s["id"]: s for s in sessions_pendents}
        visitats = set()
        items_nivell = []

        # A. Agrupar per mateix_slot (Mandatori)
        for grup_nom, grup_n in grups_ms_amb_noms:
            membres = []
            for sid, s in sessio_per_id.items():
                if sid in visitats:
                    continue
                if normalitzar_text(s["nom"]) in grup_n or normalitzar_text(s["nom_base"]) in grup_n:
                    membres.append(s)
                    visitats.add(sid)
            if membres:
                # Usar el nom definit per l'usuari, o generar un per defecte
                nom_agrupacio = grup_nom if grup_nom else membres[0]["nom_base"] + " (G)"
                item = {"sessions": membres, "nom": nom_agrupacio, "curs": nivell}
                _assigna_id(item)
                items_nivell.append(item)

        # B. Afegir sessions restants com items individuals
        for sid, s in sessio_per_id.items():
            if sid not in visitats:
                item = {"sessions": [s], "nom": s["nom"], "curs": nivell}
                _assigna_id(item)
                items_nivell.append(item)
                visitats.add(sid)

        # C. Treure ítems repetits exactes
        uniques = []
        vistos = set()
        for it in items_nivell:
            sess_ids = sorted([s.get("id") or s.get("nom") for s in it.get("sessions", [])])
            key = (it.get("curs"), tuple(sess_ids))
            if key in vistos:
                continue
            vistos.add(key)
            uniques.append(it)
        items_nivell = uniques

        tots_els_items.extend(items_nivell)

    return tots_els_items


def _items_recuit(items: tuple[Item, ...], regles: Regles) -> tuple[Item, ...]:
    """Clau interna pel nom i identificadors públics segons les agrupacions."""
    resultat = []
    for item in items:
        dades = descongela(item.dades)
        etiqueta = None
        for grup in regles.agrupacions:
            if grup.nom and all(
                any(coincideix_normalitzat(nom, e.a_diccionari()) for nom in grup.noms) for e in item.examens
            ):
                etiqueta = grup.nom
                break

        def sense_recompte(text):
            return re.sub(r"\s*\(\d+\s*assig.*\)$", "", text, flags=re.IGNORECASE).strip() if text else text

        dades["nom"] = etiqueta or sense_recompte(dades.get("nom", ""))
        dades["item_label"] = etiqueta or sense_recompte(dades.get("item_label", dades.get("nom", "")))
        identificador = dades.get("item_id") or dades.get("nom")
        etiqueta_publica = dades.get("item_label") or dades.get("nom")
        examens = []
        for e in item.examens:
            sessio = e.a_diccionari()
            sessio.update(item_id=identificador, item_label=etiqueta_publica)
            examens.append(replace(e, dades=congela(sessio)))
        resultat.append(Item(dades["nom"], dades["nom"], tuple(examens), congela(dades)))
    return tuple(resultat)
