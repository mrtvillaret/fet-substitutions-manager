"""
Lògica de validació de restriccions dures i càlcul de penalitzacions.
Extret del GeneradorSessionsExamensV2 per ser reutilitzable.
"""

import re
from collections import defaultdict
from typing import List, Dict, Tuple, Set, Union, Any
from scheduler_engine.defaults import DEFAULT_PES_RESTRICCIO_DURA, DEFAULT_PES_RESTRICCIO_VIOLADA

_RE_ISO_DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')

# ==================================================================================================
# VALIDACIONS D'ÍTEMS (Motors)
# ==================================================================================================

def es_item_compatible_amb_slot(item: Dict, sessions_al_slot: List[Dict], restriccions: Dict) -> Tuple[bool, str]:
    """
    REGLA D'OR: Comprova si un ítem és compatible amb els que ja hi ha al slot.
    Garanteix que no hi hagi dos ítems del mateix nivell al mateix slot (mandatori).
    """
    if not sessions_al_slot:
        return True, ""

    # 1. Determinar el nivell de l'item actual (assumim homogeni per nivell)
    # Suport per a objecte Sessio (V3) i Dict (V2)
    s_primera = item['sessions'][0]
    nivell_it = s_primera.get('curs') if isinstance(s_primera, dict) else getattr(s_primera, 'curs', None)
    
    if not nivell_it:
        return True, "" # Si no té nivell, no podem validar (rar)

    # 2. Comprovar si ja hi ha el mateix nivell al slot
    for s_info in sessions_al_slot:
        s_exist = s_info.get('sessio', s_info)
        nivell_exist = s_exist.get('curs') if isinstance(s_exist, dict) else getattr(s_exist, 'curs', None)
        
        if nivell_exist == nivell_it:
            # Conflicte de nivell trobat!
            # Excepció: si estan en una combinació permesa explícita
            # Però com que hem agrupat primer a la base, aquí ja NO hauria d'haver-hi excepcions.
            # Dos ítems diferents del mateix nivell SEMPRE xoquen.
            return False, f"Conflicte de nivell {nivell_it}: ja n'hi ha un altre al slot."

    # 3. Restricció no_mateix_slot (només si és obligatòria, >=100)
    no_mateix_slot = restriccions.get('restriccions_dures', {}).get('no_mateix_slot', {})
    if isinstance(no_mateix_slot, dict) and no_mateix_slot:
        # Si qualsevol sessió de l'ítem és dins d'un grup incompatible,
        # no pot compartir slot amb cap altra sessió del mateix grup.
        for nom_grup, grup in no_mateix_slot.items():
            if nom_grup.startswith('_'):
                continue
            if not isinstance(grup, list):
                continue
            if percent_no_mateix_slot(restriccions, nom_grup) < 100:
                continue

            item_in_group = any(sessio_in_group(s, grup) for s in item['sessions'])
            if not item_in_group:
                continue

            for s_info in sessions_al_slot:
                s_exist = s_info.get('sessio', s_info)
                if sessio_in_group(s_exist, grup):
                    return False, f"Conflicte no_mateix_slot: {nom_grup}"

    return True, ""
from scheduler_engine.core.normalitzacio import normalitzar_dia, nom_base_assignatura, dia_nom_per_horari

# ==================================================================================================
# HELPERS BÀSICS
# ==================================================================================================

def sessio_matches(nom_restriccio: str, sessio: Union[Dict, Any]) -> bool:
    """Comprova si el nom de la restricció coincideix amb el nom o nom_base de la sessió."""
    if isinstance(sessio, dict):
        return nom_restriccio == sessio.get('nom') or nom_restriccio == sessio.get('nom_base')
    # Per a objectes (V3 Sessio)
    return nom_restriccio == getattr(sessio, 'nom', None) or nom_restriccio == getattr(sessio, 'nom_base', None)

def sessio_in_group(sessio: Dict, grup: List[str]) -> bool:
    """Comprova si la sessió està inclosa en un grup de noms (per nom o nom_base)."""
    return any(sessio_matches(nom, sessio) for nom in grup)

def get_restriccio_val(mapa: Dict, sessio: Dict):
    """Obté un valor d'un mapa de restriccions (ex: dia fix) per a una sessió."""
    nom = sessio.get('nom')
    nom_base = sessio.get('nom_base')
    if nom in mapa:
        return mapa[nom]
    if nom_base in mapa:
        return mapa[nom_base]
    return None

def detectar_nivell_grup(grup: str, nivells_actius: List[str]) -> str:
    """Detecta el nivell d'un grup de forma dinàmica."""
    if not grup:
        return 'altres'
    grup_upper = grup.upper()
    for nivell in nivells_actius:
        nivell_net = nivell.upper().replace('-', '').replace(' ', '')
        grup_net = grup_upper.replace('-', '').replace(' ', '')
        if nivell_net in grup_net or grup_net.startswith(nivell_net[:4]):
            return nivell
    return 'altres'

# ==================================================================================================
# RESTRICCIONS OBLIGATÒRIES (PES >= 100)
# ==================================================================================================

def _pes_obligatori(pes: Union[int, float, str, None]) -> bool:
    try:
        return int(pes or 0) >= 100
    except Exception:
        return False

def _percent_value(pes: Union[int, float, str, None]) -> int:
    try:
        val = int(float(pes or 0))
    except Exception:
        return 0
    return max(0, min(100, val))

def _percent_penalty(base_cost: int, percent: Union[int, float, str, None]) -> int:
    pct = _percent_value(percent)
    if pct <= 0:
        return 0
    return int(round(base_cost * (pct / 100.0)))

def _find_restriccio_key(mapa: Dict, sessio: Dict) -> str | None:
    nom = sessio.get('nom')
    nom_base = sessio.get('nom_base')
    if nom in mapa:
        return nom
    if nom_base in mapa:
        return nom_base
    return None

def percent_assignatura_fix(sessio: Dict, dures: Dict) -> int:
    """Retorna el percentatge de força per restricció dia/hora fix d'una sessió."""
    percent = 0
    for tipus in ("assignatures_dia_fix", "assignatures_hora_fix"):
        mapa = dures.get(tipus, {}) if isinstance(dures.get(tipus, {}), dict) else {}
        key = _find_restriccio_key(mapa, sessio)
        if key:
            raw = mapa.get(f"_pes_{key}", 100)
            percent = max(percent, _percent_value(raw if raw is not None else 100))
    return percent

def percent_no_mateix_slot(restriccions: Dict, group_name: str) -> int:
    """Retorna el percentatge de força per un grup de no_mateix_slot."""
    dures = restriccions.get('restriccions_dures', {})
    grups = dures.get('no_mateix_slot', {}) if isinstance(dures.get('no_mateix_slot', {}), dict) else {}
    raw = grups.get(f"_pes_{group_name}", None)
    if raw is None:
        val = grups.get(group_name)
        if isinstance(val, dict):
            raw = val.get('pes')
    return _percent_value(raw if raw is not None else 100)

def percent_no_mateix_dia(restriccio_item: Union[List[str], Dict[str, Any]]) -> int:
    if isinstance(restriccio_item, dict):
        return _percent_value(restriccio_item.get("pes", 100))
    return 100

def viola_limit_dies_professor_obligatori(
    sessio: Dict, dia: str, sessions_assignades: Dict, restriccions: Dict
) -> bool:
    """Si pes >= 100, el límit de dies per professor es tracta com a restricció dura."""
    restriccio = restriccions.get('restriccions_dures', {}).get('professors_limit_dies_especifics', {})
    restriccio = {k: v for k, v in restriccio.items() if not k.startswith('_')}
    if not restriccio:
        return False

    professors_sessio = {e.get('titular') for e in sessio.get('examens', []) if e.get('titular')}
    dia_norm = normalitzar_dia(dia)
    # Normalitzar claus del mapa de sessions per dia (ISO → nom-dia per lookup per dia-setmana)
    sessions_norm: Dict[str, List] = defaultdict(list)
    for d, lst in (sessions_assignades or {}).items():
        sessions_norm[dia_nom_per_horari(d)].extend(lst)

    for professor in professors_sessio:
        if professor not in restriccio:
            continue
        cfg = restriccio[professor]
        assignatures = cfg.get('assignatures', [])
        dies = [normalitzar_dia(d) for d in cfg.get('dies_restringits', [])]
        max_examens = int(cfg.get('max_examens', 999))
        pes = cfg.get('pes_penalitzacio', 0)

        if not _pes_obligatori(pes):
            continue
        if not sessio_in_group(sessio, assignatures):
            continue
        if dia_norm not in dies:
            continue

        count = 1
        for d in dies:
            for s in sessions_norm.get(d, []):
                profs_s = {e.get('titular') for e in s.get('examens', []) if e.get('titular')}
                if professor in profs_s and sessio_in_group(s, assignatures):
                    count += 1

        if count > max_examens:
            return True
    return False

def viola_preferencia_dia_obligatoria(
    sessio: Dict, dia: str, sessions_assignades: Dict, restriccions: Dict
) -> bool:
    """
    Si una preferència de dia té pes >= 100, es tracta com a restricció dura:
      - mateix_dia: totes les assignatures del grup han d'anar al mateix dia
      - dies_diferents: cap assignatura del grup pot compartir dia
    """
    prefs = restriccions.get('preferencies', {})
    dia_norm = normalitzar_dia(dia)

    # Helper: trobar assignatures d'un grup ja col·locades i els seus dies (com a nom-dia)
    def _dies_assignats(assignatures: List[str]) -> Set[str]:
        dies_set: Set[str] = set()
        for d, lst in sessions_assignades.items():
            for s in lst:
                if sessio_in_group(s, assignatures):
                    dies_set.add(dia_nom_per_horari(d))
        return dies_set

    # Mateix dia (obligatori)
    for pref in prefs.get('mateix_dia', []):
        assignatures = pref.get('assignatures', []) if isinstance(pref, dict) else pref
        pes = pref.get('pes', 0) if isinstance(pref, dict) else 0
        if not _pes_obligatori(pes):
            continue
        if not sessio_in_group(sessio, assignatures):
            continue
        dies_altres = _dies_assignats(assignatures)
        # Si ja hi ha assignatures del grup en un altre dia, no es pot col·locar aquí
        if dies_altres and any(d != dia_norm for d in dies_altres):
            return True

    # Dies diferents (obligatori)
    for pref in prefs.get('dies_diferents', []):
        assignatures = pref.get('assignatures', []) if isinstance(pref, dict) else pref
        pes = pref.get('pes', 0) if isinstance(pref, dict) else 0
        if not _pes_obligatori(pes):
            continue
        if not sessio_in_group(sessio, assignatures):
            continue
        dies_altres = _dies_assignats(assignatures)
        # Si ja hi ha una assignatura del grup en aquest dia, no es pot col·locar aquí
        if dia_norm in dies_altres:
            return True

    return False
# ==================================================================================================
# VALIDACIONS (Retornen Bool)
# ==================================================================================================

def viola_restriccio_dura(sessio: Dict, sessions_dia: List[Dict], restriccions: Dict) -> bool:
    """Comprova si col·locar aquesta sessió al dia viola restriccions dures 'no_mateix_dia' (pes >= 100)."""
    no_mateix_dia = restriccions.get('restriccions_dures', {}).get('no_mateix_dia', [])
    for restriccio in no_mateix_dia:
        if isinstance(restriccio, dict):
            assignatures = restriccio.get("assignatures", [])
            pes = restriccio.get("pes", 100)
        else:
            assignatures = restriccio
            pes = 100
        if not _pes_obligatori(pes):
            continue
        if sessio_in_group(sessio, assignatures):
            for altra in assignatures:
                if not sessio_matches(altra, sessio) and any(sessio_matches(altra, s) for s in sessions_dia):
                    return True
    return False

def percent_no_mateix_dia_violation(sessio: Dict, sessions_dia: List[Dict], restriccions: Dict) -> int:
    """Retorna el percentatge de la violació de no_mateix_dia (0 si no hi ha conflicte)."""
    no_mateix_dia = restriccions.get('restriccions_dures', {}).get('no_mateix_dia', [])
    for restriccio in no_mateix_dia:
        if isinstance(restriccio, dict):
            assignatures = restriccio.get("assignatures", [])
            pes = restriccio.get("pes", 100)
        else:
            assignatures = restriccio
            pes = 100
        if sessio_in_group(sessio, assignatures):
            for altra in assignatures:
                if not sessio_matches(altra, sessio) and any(sessio_matches(altra, s) for s in sessions_dia):
                    return _percent_value(pes)
    return 0

def percent_no_mateix_slot_violation(sessio: Dict, sessions_slot: List[Dict], restriccions: Dict) -> int:
    """Retorna el percentatge de la violació no_mateix_slot (0 si no hi ha conflicte)."""
    if not sessions_slot:
        return 0
    no_mateix_slot = restriccions.get('restriccions_dures', {}).get('no_mateix_slot', {})
    if not isinstance(no_mateix_slot, dict):
        return 0
    for nom_grup, grup in no_mateix_slot.items():
        if nom_grup.startswith('_') or not isinstance(grup, list):
            continue
        if not sessio_in_group(sessio, grup):
            continue
        for altra in sessions_slot:
            if sessio_in_group(altra, grup) and (altra.get('nom') != sessio.get('nom')):
                return percent_no_mateix_slot(restriccions, nom_grup)
    return 0

def percent_slot_prohibit_violation(sessio: Dict, dia: str, hora: str, restriccions: Dict) -> int:
    """Retorna 100 si la sessió cau en un slot prohibit per assignatures_slot_prohibit."""
    prohibits = restriccions.get('restriccions_dures', {}).get('assignatures_slot_prohibit', [])
    if not prohibits:
        return 0
    dia_norm = normalitzar_dia(dia)
    for p in prohibits:
        if not sessio_in_group(sessio, p.get('assignatures', [])):
            continue
        p_dia = normalitzar_dia(p['dia']) if p.get('dia') else None
        p_hora = p.get('hora') or None
        if p_dia and p_dia != dia_norm:
            continue
        if p_hora and p_hora != hora:
            continue
        return 100
    return 0


def percent_dia_hora_fix_violation(sessio: Dict, dia: str, hora: str, restriccions: Dict, nivells_actius: List[str], data_iso: str = "") -> int:
    """Retorna el percentatge de violació per dia/hora fix o slots prohibits (0 si no hi ha)."""
    dures = restriccions.get('restriccions_dures', {})
    dia_norm = normalitzar_dia(dia)

    dies_fixos = {k: v for k, v in dures.get('assignatures_dia_fix', {}).items() if not k.startswith('_')}
    hores_fixes = {k: v for k, v in dures.get('assignatures_hora_fix', {}).items() if not k.startswith('_')}

    dia_fix = get_restriccio_val(dies_fixos, sessio)
    hora_fix = get_restriccio_val(hores_fixes, sessio)
    percent = percent_assignatura_fix(sessio, dures)

    if dia_fix:
        if _RE_ISO_DATE.match(str(dia_fix)):
            # Pin amb data ISO: comparar directament contra data_iso del slot
            if not data_iso or data_iso != dia_fix:
                return percent or 100
        elif normalitzar_dia(dia_fix) != dia_norm:
            return percent or 100
    if hora_fix and hora != hora_fix:
        return percent or 100

    pct_prohibit = percent_slot_prohibit_violation(sessio, dia, hora, restriccions)
    if pct_prohibit:
        return pct_prohibit

    if not es_slot_valid_per_nivell(sessio.get('nom', ''), dia, hora, restriccions, nivells_actius, curs=sessio.get('curs', ''), data_iso=data_iso):
        return 100

    return 0

def viola_combinacions_permeses(sessio: Dict, sessions_slot: List[Dict], restriccions: Dict) -> bool:
    """
    Comprova si afegir aquesta sessió al slot viola les combinacions permeses.
    Si hi ha >= 2 sessions del mateix nivell, han de ser subconjunt d'una combinació o grup 'mateix_slot'.
    """
    combinacions = restriccions.get('restriccions_dures', {}).get('combinacions_permeses', [])
    if not combinacions:
        return False

    nivell_sessio = sessio.get('curs', '')
    sessions_mateix_nivell = [s for s in sessions_slot if s.get('curs', '') == nivell_sessio]

    if not sessions_mateix_nivell:
        return False

    def _nom_net(nom: str) -> str:
        return nom.split(' (')[0].strip() if ' (' in nom else nom.strip() if nom else ''

    noms_slot = set()
    for s in sessions_mateix_nivell:
        noms_slot.add(_nom_net(s.get('nom_base') or s.get('nom', '')))
    noms_slot.add(_nom_net(sessio.get('nom_base') or sessio.get('nom', '')))

    if len(noms_slot) <= 1:
        return False

    # Check combinacions
    combinacions_norm = []
    for comb in combinacions:
        assignatures = comb.get('assignatures', []) if isinstance(comb, dict) else comb
        comb_noms = set(_nom_net(c) for c in assignatures if c)
        if comb_noms:
            combinacions_norm.append(comb_noms)

    # Check mateix_slot groups
    grups_mateix_slot = restriccions.get('restriccions_dures', {}).get('mateix_slot', [])
    for grup in grups_mateix_slot:
        assignatures = grup.get('assignatures', []) if isinstance(grup, dict) else grup
        noms_grup = set(_nom_net(g) for g in assignatures if g)
        if noms_grup and noms_slot.issubset(noms_grup):
            return False

    if not combinacions_norm:
        return False

    for comb in combinacions_norm:
        if noms_slot.issubset(comb):
            return False

    return True

def es_slot_valid_per_nivell(nom_sessio: str, dia: str, hora: str, restriccions: Dict, nivells_actius: List[str], curs: str = "", data_iso: str = "") -> bool:
    """Comprova si un slot és vàlid per al nivell segons 'slots_valids_per_nivell'."""
    slots_valids = restriccions.get('restriccions_dures', {}).get('slots_valids_per_nivell', {})
    if not slots_valids:
        return True

    # Prioritzar curs directe per evitar falses deteccions per nom
    nivell_sessio = None
    if curs:
        if curs in slots_valids:
            nivell_sessio = curs
        else:
            for nivell in nivells_actius:
                if nivell == curs:
                    nivell_sessio = nivell
                    break

    if not nivell_sessio:
        for nivell in nivells_actius:
            if nivell in nom_sessio:
                nivell_sessio = nivell
                break

    if not nivell_sessio:
        nivell_sessio = detectar_nivell_grup(nom_sessio or curs, nivells_actius)
        if nivell_sessio == 'altres':
            nivell_sessio = None

    if not nivell_sessio or nivell_sessio not in slots_valids:
        return True

    # Prioritzar lookup per data ISO exacta (evita confusió entre dates del mateix dia de la setmana)
    if data_iso:
        slots_iso = restriccions.get('restriccions_dures', {}).get('slots_valids_iso_per_nivell', {})
        if slots_iso and nivell_sessio in slots_iso:
            iso_map = slots_iso[nivell_sessio]
            if data_iso in iso_map:
                return hora in iso_map[data_iso]
            # Data ISO del nivell no configurada → slot no vàlid
            return False

    # Fallback: lookup per dia-nom
    slots_nivell = slots_valids[nivell_sessio]
    dia_norm = normalitzar_dia(dia)
    for d, hores in slots_nivell.items():
        if normalitzar_dia(d) == dia_norm:
            return hora in hores
    return False

def viola_restriccio_dia_hora_fixos(sessio: Dict, dia: str, hora: str, restriccions: Dict, nivells_actius: List[str], data_iso: str = "") -> bool:
    """Comprova dia/hora fix, bloquejos i validesa per nivell (només si pes >= 100)."""
    percent = percent_dia_hora_fix_violation(sessio, dia, hora, restriccions, nivells_actius, data_iso)
    return percent >= 100

# ==================================================================================================
# PENALITZACIONS (Retornen Int)
# ==================================================================================================

def penalitzacio_conflicte_professor_nivell(sessio: Dict, sessions_slot: List[Dict], pes: int) -> int:
    """Penalitza professors amb exàmens de nivells diferents al mateix slot."""
    if not sessions_slot:
        return 0
    conflicte_profs = set()
    nom_actual = sessio.get('nom', '')
    curs_actual = sessio.get('curs', '')
    
    professors_sessio = {e.get('titular') for e in sessio.get('examens', []) if e.get('titular')}
    
    for prof in professors_sessio:
        for s_info in sessions_slot:
            other = s_info.get('sessio') if isinstance(s_info, dict) and 'sessio' in s_info else s_info
            if not other: continue
            if other.get('nom') == nom_actual: continue
            if other.get('curs') == curs_actual: continue # Mateix nivell no és conflicte aquí
            
            if any(e.get('titular') == prof for e in other.get('examens', [])):
                conflicte_profs.add(prof)
                break
    return len(conflicte_profs) * pes

def calcular_penalitzacio_professors_dies(sessio: Dict, dia: str, sessions_assignades: Dict, restriccions: Dict) -> int:
    """Penalització per límit d'exàmens en dies específics per professor."""
    restriccio = restriccions.get('restriccions_dures', {}).get('professors_limit_dies_especifics', {})
    restriccio = {k: v for k, v in restriccio.items() if not k.startswith('_')}
    if not restriccio:
        return 0

    professors_sessio = {e.get('titular') for e in sessio.get('examens', []) if e.get('titular')}
    penalitzacio_total = 0
    base_cost = restriccions.get('pesos_optimitzacio', {}).get('restriccio_dura', DEFAULT_PES_RESTRICCIO_DURA)
    hard_cost = restriccions.get('pesos_optimitzacio', {}).get('restriccio_dura_violada', DEFAULT_PES_RESTRICCIO_VIOLADA)
    dia_nom = dia_nom_per_horari(dia)
    sessions_norm_d: Dict[str, List] = defaultdict(list)
    for d, lst in (sessions_assignades or {}).items():
        sessions_norm_d[dia_nom_per_horari(d)].extend(lst)

    for professor in professors_sessio:
        if professor not in restriccio: continue

        config_prof = restriccio[professor]
        assignatures_restringides = config_prof.get('assignatures', [])
        dies_restringits = [normalitzar_dia(d) for d in config_prof.get('dies_restringits', [])]
        max_examens = int(config_prof.get('max_examens', 999))
        pes = config_prof.get('pes_penalitzacio', 50)

        if not sessio_in_group(sessio, assignatures_restringides): continue
        if dia_nom not in dies_restringits: continue

        count_examens = 0
        for dia_check in dies_restringits:
            for s in sessions_norm_d.get(dia_check, []):
                profs_s = {e.get('titular') for e in s.get('examens', []) if e.get('titular')}
                if professor in profs_s and sessio_in_group(s, assignatures_restringides):
                    count_examens += 1
        
        if count_examens > max_examens:
            excedent = count_examens - max_examens
            if _pes_obligatori(pes):
                penalitzacio_total += hard_cost * excedent
            else:
                penalitzacio_total += _percent_penalty(base_cost, pes) * excedent

    return penalitzacio_total

def calcular_penalitzacio_professors_dies_item(item: Dict, dia: str, sessions_assignades: Dict, restriccions: Dict) -> int:
    """
    Penalització per límit d'exàmens en dies específics (a nivell d'ítem).
    Evita comptar múltiples cops la mateixa violació quan un ítem té diverses sessions.
    """
    restriccio = restriccions.get('restriccions_dures', {}).get('professors_limit_dies_especifics', {})
    restriccio = {k: v for k, v in restriccio.items() if not k.startswith('_')}
    if not restriccio:
        return 0

    sessions_item = item.get('sessions', [])
    professors_item = {e.get('titular') for s in sessions_item for e in s.get('examens', []) if e.get('titular')}
    if not professors_item:
        return 0

    penalitzacio_total = 0
    base_cost = restriccions.get('pesos_optimitzacio', {}).get('restriccio_dura', DEFAULT_PES_RESTRICCIO_DURA)
    hard_cost = restriccions.get('pesos_optimitzacio', {}).get('restriccio_dura_violada', DEFAULT_PES_RESTRICCIO_VIOLADA)

    for professor in professors_item:
        if professor not in restriccio:
            continue

        config_prof = restriccio[professor]
        assignatures_restringides = config_prof.get('assignatures', [])
        dies_restringits = config_prof.get('dies_restringits', [])
        max_examens = int(config_prof.get('max_examens', 999))
        pes = config_prof.get('pes_penalitzacio', 50)

        # Només aplica si l'ítem té alguna sessió de les assignatures restringides
        if not any(sessio_in_group(s, assignatures_restringides) for s in sessions_item):
            continue
        dies_restringits = [normalitzar_dia(d) for d in dies_restringits]
        dia_nom = dia_nom_per_horari(dia)
        if dia_nom not in dies_restringits:
            continue

        sessions_norm_d: Dict[str, List] = defaultdict(list)
        for d, lst in (sessions_assignades or {}).items():
            sessions_norm_d[dia_nom_per_horari(d)].extend(lst)

        count_examens = 0
        for dia_check in dies_restringits:
            for s in sessions_norm_d.get(dia_check, []):
                profs_s = {e.get('titular') for e in s.get('examens', []) if e.get('titular')}
                if professor in profs_s and sessio_in_group(s, assignatures_restringides):
                    count_examens += 1

        if count_examens > max_examens:
            excedent = count_examens - max_examens
            if _pes_obligatori(pes):
                penalitzacio_total += hard_cost * excedent
            else:
                penalitzacio_total += _percent_penalty(base_cost, pes) * excedent

    return penalitzacio_total

def calcular_penalitzacio_total_professors(sessions_per_dia: Dict, restriccions: Dict) -> int:
    """Calcula penalització total per professors amb límits d'exàmens en dies específics."""
    restriccio = restriccions.get('restriccions_dures', {}).get('professors_limit_dies_especifics', {})
    restriccio = {k: v for k, v in restriccio.items() if not k.startswith('_')}
    if not restriccio:
        return 0

    penalitzacio_total = 0
    base_cost = restriccions.get('pesos_optimitzacio', {}).get('restriccio_dura', DEFAULT_PES_RESTRICCIO_DURA)
    hard_cost = restriccions.get('pesos_optimitzacio', {}).get('restriccio_dura_violada', DEFAULT_PES_RESTRICCIO_VIOLADA)

    for professor, config_prof in restriccio.items():
        assignatures_restringides = config_prof.get('assignatures', [])
        dies_restringits = config_prof.get('dies_restringits', [])
        max_examens = int(config_prof.get('max_examens', 999))
        _v = config_prof.get('pes_penalitzacio')
        pes = int(_v) if _v is not None else 50

        count_examens = 0
        for dia_check in dies_restringits:
            for s in sessions_per_dia.get(dia_check, []):
                # Usar self._professors_sessio si és motor, o helper si no
                profs_s = {e.get('titular') for e in s.get('examens', []) if e.get('titular')}
                if professor in profs_s and sessio_in_group(s, assignatures_restringides):
                    count_examens += 1

        if count_examens > max_examens:
            excedent = count_examens - max_examens
            if _pes_obligatori(pes):
                penalitzacio_total += hard_cost * excedent
            else:
                penalitzacio_total += _percent_penalty(base_cost, pes) * excedent

    return penalitzacio_total

def calcular_penalitzacio_assignatures_dies_exclosos(sessio: Dict, dia: str, restriccions: Dict) -> int:
    """Penalitza si una assignatura està en un dia exclòs."""
    restr_llista = restriccions.get('restriccions_dures', {}).get('assignatures_dies_exclosos', [])
    if not restr_llista:
        return 0

    penalitzacio_total = 0
    dia_norm = normalitzar_dia(dia)
    
    base_cost = restriccions.get('pesos_optimitzacio', {}).get('restriccio_dura', DEFAULT_PES_RESTRICCIO_DURA)
    for r in restr_llista:
        if not isinstance(r, dict): continue
        assigs = r.get('assignatures', [])
        dies = [normalitzar_dia(d) for d in r.get('dies', [])]
        pes = r.get('pes', DEFAULT_PES_RESTRICCIO_DURA)

        if sessio_in_group(sessio, assigs) and dia_norm in dies:
            penalitzacio_total += _percent_penalty(base_cost, pes)
            
    return penalitzacio_total
