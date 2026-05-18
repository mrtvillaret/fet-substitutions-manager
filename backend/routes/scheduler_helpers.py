"""Helpers de domini per a les rutes del scheduler."""

from datetime import datetime
import xml.etree.ElementTree as ET

from repositories import MasterConfigRepository
from scheduler_engine.core.normalitzacio import normalitzar_dia
from utils.hores import normalitzar_hora as _normalitzar_hora


def _nivells_master(db) -> list[str]:
    master = MasterConfigRepository.get_master_config(db)
    nivells = list((master or {}).get("nivells", {}).keys())
    return sorted([n for n in nivells if n], key=len, reverse=True)


def _detectar_nivell(grup: str, nivells: list[str]) -> str | None:
    if not grup:
        return None
    for nivell in nivells:
        if nivell in grup:
            return nivell
    return None


def _extract_assignatures_from_restriccions(restr: dict) -> set[str]:
    resultat = set()
    dures = (restr or {}).get("restriccions_dures", {})
    preferencies = (restr or {}).get("preferencies", {})

    for item in dures.get("no_mateix_dia", []):
        if isinstance(item, list):
            resultat.update(item)
        elif item:
            resultat.add(item)

    for grup in (dures.get("no_mateix_slot") or {}).values():
        if isinstance(grup, list):
            resultat.update(grup)

    for grup in dures.get("mateix_slot", []):
        if isinstance(grup, dict):
            resultat.update(grup.get("assignatures", []) or [])
        elif isinstance(grup, list):
            resultat.update(grup)

    resultat.update(
        {
            k
            for k in (dures.get("assignatures_dia_fix") or {}).keys()
            if not str(k).startswith("_pes_")
        }
    )
    resultat.update(
        {
            k
            for k in (dures.get("assignatures_hora_fix") or {}).keys()
            if not str(k).startswith("_pes_")
        }
    )

    for cfg in (dures.get("professors_limit_dies_especifics") or {}).values():
        if isinstance(cfg, dict):
            resultat.update(cfg.get("assignatures", []) or [])

    for item in preferencies.get("mateix_dia", []):
        if isinstance(item, dict):
            resultat.update(item.get("assignatures", []) or [])
    for item in preferencies.get("dies_diferents", []):
        if isinstance(item, dict):
            resultat.update(item.get("assignatures", []) or [])

    return {a for a in resultat if a}


def _selected_dates_from_alliberaments(
    alliberaments_cfg: dict, nivells_actius: list[str] | None = None
) -> list[str]:
    """
    Extreu les dates ISO (YYYY-MM-DD) des de scheduler_alliberaments_per_nivell.
    Prioritza `dates`; si no n'hi ha, usa claus de `config`.
    """
    if not isinstance(alliberaments_cfg, dict) or not alliberaments_cfg:
        return []

    allowed = set(nivells_actius or [])
    out = set()

    for nivell, data in alliberaments_cfg.items():
        if allowed and nivell not in allowed:
            continue
        if not isinstance(data, dict):
            continue

        has_dates_field = "dates" in data
        raw_dates = data.get("dates") or []
        parsed = []
        for d in raw_dates:
            if not isinstance(d, str):
                continue
            try:
                parsed.append(datetime.strptime(d, "%Y-%m-%d").strftime("%Y-%m-%d"))
            except ValueError:
                continue

        # Si la clau `dates` existeix (encara que sigui buida), és la font de veritat.
        # Només fem fallback a `config` per compatibilitat amb dades antigues sense `dates`.
        if has_dates_field:
            if parsed:
                out.update(parsed)
            continue

        if parsed:
            out.update(parsed)
            continue

        cfg = data.get("config") or {}
        if isinstance(cfg, dict):
            for d in cfg.keys():
                if not isinstance(d, str):
                    continue
                try:
                    out.add(datetime.strptime(d, "%Y-%m-%d").strftime("%Y-%m-%d"))
                except ValueError:
                    continue

    return sorted(out)




def _hores_lectives_des_de_xml(xml_path: str, fallback: list[str] | None = None) -> list[str]:
    """
    Extreu totes les hores lectives (ordenades) des de l'XML.
    Si falla, retorna el fallback normalitzat.
    """
    fallback = fallback or []

    def _to_minutes(h: str) -> int:
        try:
            hh, mm = h.split(":")
            return int(hh) * 60 + int(mm)
        except Exception:
            return 10**9

    hores = []
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for day in root.findall(".//Day"):
            for hour in day.findall("Hour"):
                h = _normalitzar_hora(hour.get("name"))
                if h and h not in hores:
                    hores.append(h)
    except Exception:
        hores = []

    if not hores:
        hores = [_normalitzar_hora(h) for h in fallback if h]

    hores = [h for h in hores if h]
    return sorted(hores, key=_to_minutes)


def extreure_hores_examen_des_alliberaments(alliberaments: dict) -> tuple[list, dict]:
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
        except Exception:
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
        for dia_iso, slots in cfg.items():
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
    dia_a_data_iso: dict[str, list[str]],
    hores_disponibles: list[str],
) -> dict:
    """
    Construeix slots vàlids per nivell a partir de la marca 'i' (inici examen).
    Si un nivell té configuració però cap 'i', queda sense cap slot vàlid.
    Utilitza les dates seleccionades del propi nivell (camp 'dates') per construir
    el mapa dia→data, ja que cada nivell pot tenir exàmens en setmanes diferents.
    """
    from datetime import datetime as _dt

    _DIES_CAT = ["Dilluns", "Dimarts", "Dimecres", "Dijous", "Divendres", "Dissabte", "Diumenge"]

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
        dia_a_data_nivell: dict[str, list[str]] = {}
        for d_str in nivell_dates:
            try:
                dt = _dt.strptime(d_str, "%Y-%m-%d")
                dia_norm = normalitzar_dia(_DIES_CAT[dt.weekday()])
                dia_a_data_nivell.setdefault(dia_norm, []).append(d_str)
            except (ValueError, IndexError):
                continue

        # Fallback al mapa global si el nivell no té dates pròpies
        if not dia_a_data_nivell:
            dia_a_data_nivell = dia_a_data_iso

        cfg = nivell_data.get("config") or {}
        per_dia = {}
        for dia in dies_utilitzar or []:
            dia_norm = normalitzar_dia(dia)
            dates_dia = dia_a_data_nivell.get(dia_norm) or []
            if isinstance(dates_dia, str):
                dates_dia = [dates_dia]
            if not dates_dia:
                continue
            # Recollir totes les hores d'inici de totes les dates d'aquest dia
            hores_inici = []
            for data_iso in dates_dia:
                cfg_dia = cfg.get(data_iso) or {}
                for h in hores_ord:
                    info = cfg_dia.get(h)
                    if isinstance(info, dict) and info.get("i") is True and h not in hores_inici:
                        hores_inici.append(h)
            per_dia[dia] = hores_inici

        # Si el nivell existeix a alliberaments, el considerem explícit.
        # Pot tenir llista buida (cap hora d'inici marcada) i això és vàlid.
        result[nivell] = per_dia

    return result


def _build_slots_valids_iso_from_alliberaments(
    alliberaments_cfg: dict,
    nivells_actius: list[str],
    hores_disponibles: list[str],
) -> dict:
    """
    Retorna {nivell: {data_iso: [hores_inici]}} per fer lookup exacte per data.
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
        for d_str in (nivell_data.get("dates") or []):
            if not isinstance(d_str, str):
                continue
            cfg_dia = cfg.get(d_str) or {}
            hores = [h for h in hores_ord if isinstance(cfg_dia.get(h), dict) and cfg_dia[h].get("i") is True]
            per_data[d_str] = hores  # llista buida = dia configurat però sense inici d'examen
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


def _build_assignatures_options(
    assignacions,
    nivells: list[str],
    only_nivells: list[str] | None = None,
    extra: set[str] | None = None,
) -> list[str]:
    options = set()
    for a in assignacions:
        nom = a.get("assignatura") if isinstance(a, dict) else a.assignatura
        grup = a.get("grup") if isinstance(a, dict) else a.grup
        if not nom:
            continue
        nivell = _detectar_nivell(grup, nivells)
        if nivell:
            if not only_nivells or nivell in only_nivells:
                options.add(f"{nom} ({nivell})")
        else:
            if not only_nivells:
                options.add(nom)

    if extra:
        options.update(extra)

    return sorted(options)
