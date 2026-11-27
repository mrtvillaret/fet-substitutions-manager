"""Les hores sense classe de cada nivell (alliberaments) marcades al
calendari del planificador: d'on surten les dates, les hores on pot començar
un examen i les franges vàlides de cada nivell."""

import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
from datetime import date

from planificador.compartit.dates import DIES_CAT, data_calendari
from planificador.compartit.normalitzacio import normalitzar_dia
from textos import normalitzar_hora as _normalitzar_hora


def _selected_dates_from_alliberaments(alliberaments_cfg: dict, nivells_actius: list[str] | None = None) -> list[date]:
    """Dates dels nivells actius. Només un camp «dates» absent fa servir les claus de «config»."""
    if not isinstance(alliberaments_cfg, dict):
        return []
    allowed = set(nivells_actius or [])
    dates: set[date] = set()
    for nivell, dades in alliberaments_cfg.items():
        if (allowed and nivell not in allowed) or not isinstance(dades, dict):
            continue
        if "dates" in dades:
            valors = dades["dates"] or []
        else:
            config = dades.get("config")
            valors = config if isinstance(config, dict) else []
        dates.update(data for valor in valors if (data := data_calendari(valor)))
    return sorted(dates)


def _hores_lectives_des_de_xml(xml_path: str, fallback: list[str] | None = None) -> list[str]:
    """Totes les hores lectives de l'XML, ordenades; si no en té cap, les del
    fallback."""
    fallback = fallback or []

    def _to_minutes(h: str) -> int:
        try:
            hh, mm = h.split(":")
            return int(hh) * 60 + int(mm)
        except (ValueError, TypeError, IndexError):
            return 10**9

    hores = []
    for day in ET.parse(xml_path).getroot().findall(".//Day"):
        for hour in day.findall("Hour"):
            h = _normalitzar_hora(hour.get("name"))
            if h and h not in hores:
                hores.append(h)

    if not hores:
        hores = [_normalitzar_hora(h) for h in fallback if h]

    hores = [h for h in hores if h]
    return sorted(hores, key=_to_minutes)


def extreure_hores_examen_des_alliberaments(alliberaments: dict) -> tuple[list[str], dict[str, list[str]]]:
    """
    Deriva les hores d'examen únicament de les marques ``i=true`` als alliberaments.

    Retorna ``(hores_globals, hores_per_nivell)`` on:
    - ``hores_globals``: unió ordenada de TOTES les hores amb ``i=true`` de tots els nivells
    - ``hores_per_nivell``: ``{ nivell: [hores_amb_i_true_ordenades] }``
    """

    def _to_minutes(h: str) -> int:
        try:
            hh, mm = h.split(":")
            return int(hh) * 60 + int(mm)
        except (ValueError, TypeError, IndexError):
            return 10**9

    hores_per_nivell: dict[str, list[str]] = {}
    totes: set[str] = set()

    if not isinstance(alliberaments, dict):
        return [], {}

    for nivell, data in alliberaments.items():
        if not isinstance(data, dict):
            continue
        cfg = data.get("config") or {}
        if not isinstance(cfg, dict):
            continue
        hores_nivell: set[str] = set()
        for slots in cfg.values():
            if not isinstance(slots, dict):
                continue
            for hora, flags in slots.items():
                if isinstance(flags, dict) and flags.get("i") is True:
                    h = _normalitzar_hora(hora)
                    if h:
                        hores_nivell.add(h)
        sorted_hores = sorted(hores_nivell, key=_to_minutes)
        hores_per_nivell[nivell] = sorted_hores
        totes.update(hores_nivell)

    hores_globals = sorted(totes, key=_to_minutes)
    return hores_globals, hores_per_nivell


def _build_slots_valids_from_alliberaments(
    alliberaments_cfg: dict,
    nivells_actius: list[str],
    dies_utilitzar: list[str],
    dia_a_data: Mapping[str, Sequence[date | str]],
    hores_disponibles: list[str],
) -> dict:
    """
    Construeix slots vàlids per nivell a partir de la marca 'i' (inici examen).
    Si un nivell té configuració però cap 'i', queda sense cap slot vàlid.
    Utilitza les dates seleccionades del propi nivell (camp 'dates') per construir
    el mapa dia→data, ja que cada nivell pot tenir exàmens en setmanes diferents.
    """

    if not isinstance(alliberaments_cfg, dict) or not alliberaments_cfg:
        return {}

    hores_ord = [_normalitzar_hora(h) for h in (hores_disponibles or [])]
    result = {}

    for nivell in nivells_actius or []:
        nivell_data = alliberaments_cfg.get(nivell)
        if not isinstance(nivell_data, dict):
            continue

        # Construir mapa dia→[dates] específic per aquest nivell (suporta dates repetides)
        nivell_dates = nivell_data.get("dates") or []
        dia_a_data_nivell: dict[str, list[date | str]] = {}
        for valor in nivell_dates:
            if data := data_calendari(valor):
                dia_norm = normalitzar_dia(DIES_CAT[data.weekday()])
                dia_a_data_nivell.setdefault(dia_norm, []).append(valor)

        cfg = nivell_data.get("config") or {}
        per_dia = {}
        for dia in dies_utilitzar or []:
            dia_norm = normalitzar_dia(dia)
            dates_dia = (dia_a_data_nivell or dia_a_data).get(dia_norm) or []
            if not dates_dia:
                continue
            # Recollir totes les hores d'inici de totes les dates d'aquest dia
            hores_inici = []
            for data_dia in dates_dia:
                cfg_dia = cfg.get(data_dia) or {}
                for h in hores_ord:
                    info = cfg_dia.get(h)
                    if isinstance(info, dict) and info.get("i") is True and h not in hores_inici:
                        hores_inici.append(h)
            per_dia[dia] = hores_inici

        # Si el nivell existeix a alliberaments, el considerem explícit.
        # Pot tenir llista buida (cap hora d'inici marcada) i això és vàlid.
        result[nivell] = per_dia

    return result


def _build_slots_valids_per_data(
    alliberaments_cfg: dict,
    nivells_actius: list[str],
    hores_disponibles: list[str],
) -> dict:
    """
    Retorna {nivell: {data: [hores_inici]}} per fer lookup exacte per data.
    Separat de slots_valids_per_nivell per no interferir amb _merge_slots_valids.
    """
    if not isinstance(alliberaments_cfg, dict) or not alliberaments_cfg:
        return {}

    hores_ord = [_normalitzar_hora(h) for h in (hores_disponibles or [])]
    result = {}

    for nivell in nivells_actius or []:
        nivell_data = alliberaments_cfg.get(nivell)
        if not isinstance(nivell_data, dict):
            continue
        cfg = nivell_data.get("config") or {}
        per_data = {}
        for data in nivell_data.get("dates") or []:
            if not isinstance(data, (date, str)):
                continue
            cfg_dia = cfg.get(data) or {}
            hores = [h for h in hores_ord if isinstance(cfg_dia.get(h), dict) and cfg_dia[h].get("i") is True]
            per_data[data] = hores  # llista buida = dia configurat però sense inici d'examen
        if per_data:
            result[nivell] = per_data

    return result


def _merge_slots_valids(existing: dict, derived: dict) -> dict:
    """
    Combina slots_valids manuals amb derivats d'alliberaments.
    Mateix nivell/dia => intersecció d'hores.
    """
    if not existing:
        return derived or {}
    if not derived:
        return existing or {}

    out = {}
    nivells = set(existing.keys()) | set(derived.keys())
    for nivell in nivells:
        e = existing.get(nivell)
        d = derived.get(nivell)
        if e is not None and not isinstance(e, dict):
            e = {}
        if d is not None and not isinstance(d, dict):
            d = {}
        if e is None:
            out[nivell] = d
            continue
        if d is None:
            out[nivell] = e
            continue

        per_dia = {}
        dies = set((e or {}).keys()) | set((d or {}).keys())
        for dia in dies:
            eh = set((e or {}).get(dia, []))
            dh = set((d or {}).get(dia, []))
            per_dia[dia] = sorted(eh & dh)
        out[nivell] = per_dia
    return out
