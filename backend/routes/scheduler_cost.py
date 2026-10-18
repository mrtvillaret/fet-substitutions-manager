"""
Cost i incidències d'un horari d'exàmens ja fet (POST /api/scheduler/recalcular-cost):
el que la pantalla mostra per a cada franja i per a cada examen quan l'horari
s'edita a mà.
"""
from collections import defaultdict

from scheduler_engine.core.constraints import sessio_in_group
from scheduler_engine.core.normalitzacio import normalitzar_dia
from scheduler_engine.core.scoring import pes_professor

from routes.scheduler_helpers import _normalitzar_hora


def _substitucio(prof, hora, dia, item):
    act = item.get('activitat', {})
    assig = act.get('assignatura', 'Assignatura')
    grp = act.get('grup', 'un grup')
    return f"🚨 {prof} → ha de ser SUBSTITUÏT a {assig} amb {grp} a les {hora} el {dia}"


def _abans(prof, hora, dia, item):
    return f"🕐 {prof} → arriba abans a {hora} el {dia} (primera hora: {item.get('primera_hora', '?')})"


def _despres(prof, hora, dia, item):
    return f"🕐 {prof} → queda més estona a {hora} el {dia} (última hora: {item.get('ultima_hora', '?')})"


def _no_treballa(prof, hora, dia, item):
    return f"🚫 {prof} → no treballa aquest dia a les {hora} el {dia}"


# (clau de l'anàlisi de disponibilitat i tipus de cost, missatge), en l'ordre en què surten
TIPUS_INCIDENCIA = (
    ('substitucions', 'substitucio', _substitucio),
    ('abans_jornada', 'abans_jornada', _abans),
    ('despres_jornada', 'despres_jornada', _despres),
    ('no_treballa_dia', 'no_treballa_dia', _no_treballa),
)


def incidencies(analisi: dict, hora: str, dia: str, restriccions: dict):
    """(tipus de cost, professor, hora, avís amb la puntuació, pes) de cada
    incidència de l'anàlisi d'una sessió, sense repetir-ne cap."""
    vistes = set()
    for clau, tipus, missatge in TIPUS_INCIDENCIA:
        for item in analisi.get(clau, []):
            prof = item.get('professor')
            if not prof:
                continue
            hora_item = item.get('hora', hora)
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
        item_id = sessio.get('item_id') or sessio.get('id') or f"{sessio.get('nom')}_{sessio.get('curs')}"
        curs = sessio.get('curs', '')
        if curs and item_id not in nivell_per_item:
            nivell_per_item[item_id] = curs
    nivells = list(nivell_per_item.values())
    return len(nivells) != len(set(nivells))


def _sessions_per_dia(horari: dict) -> dict:
    """Sessions de cada dia, pel nom tal com ve i pel nom normalitzat."""
    sessions = defaultdict(list)
    for dia_data in horari.get('dies', []):
        dia_nom = dia_data.get('dia', '')
        dia_norm = normalitzar_dia(dia_nom)
        for slot_data in dia_data.get('sessions', []):
            for sessio_data in slot_data.get('sessions_simultanees', []):
                sessions[dia_nom].append(sessio_data)
                if dia_norm and dia_norm != dia_nom:
                    sessions[dia_norm].append(sessio_data)
    return sessions


def excessos_limit_dies(horari: dict, restriccions: dict) -> list[str]:
    """"Professor +n" per a cada professor amb més exàmens dels permesos als
    dies restringits (restricció professors_limit_dies_especifics)."""
    limits = (restriccions.get('restriccions_dures') or {}).get('professors_limit_dies_especifics') or {}
    limits = {k: v for k, v in limits.items() if not k.startswith('_')}
    if not limits:
        return []
    sessions_per_dia = _sessions_per_dia(horari)
    excessos = []
    for professor, config_prof in limits.items():
        assignatures = config_prof.get('assignatures', [])
        max_examens = int(config_prof.get('max_examens', 999))
        examens = sum(
            1
            for dia in config_prof.get('dies_restringits', [])
            for s in sessions_per_dia.get(dia, [])
            if professor in {e.get('titular') for e in s.get('examens', []) if e.get('titular')}
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
            hh, mm = h.split(':')[:2]
            return int(hh) * 60 + int(mm)
        except (ValueError, TypeError, IndexError):
            return 0

    hores = []
    for day in root.findall('.//Day'):
        for hour in day.findall('Hour'):
            h = hour.get('name')
            if h and h not in hores:
                hores.append(h)
    hores = [_normalitzar_hora(h) for h in hores if h]
    if not hores:
        return [_normalitzar_hora(h) for h in (hores_examen or [])]
    falten = [h for h in (_normalitzar_hora(h) for h in (hores_examen or [])) if h and h not in hores]
    if falten:
        hores = sorted({*hores, *falten}, key=_minuts)
    return hores
