"""
Diagnòstic d'infactibilitat per al generador d'horaris.

Quan un motor no pot col·locar tots els ítems, InfeasibilityDiagnostic analitza
quines restriccions dures impedeixen la generació i retorna missatges concrets
per mostrar a l'usuari.

No depèn d'analitzar_tots_slots() (que pot retornar 0 slots per problemes de càlcul).
En lloc, calcula dates viables per ítem cridant directament RestrictionEngine.check_hard().
"""

import re as _re
from datetime import datetime as _dt
from typing import Dict, List, Optional, Set, Tuple

from scheduler_engine.core.restriction_engine import RestrictionEngine
from scheduler_engine.core.constraints import _pes_obligatori, sessio_in_group
from scheduler_engine.core.date_mapping import DIES_CAT
from scheduler_engine.core.normalitzacio import normalitzar_dia as _normalitzar_dia

_ISO_RE = _re.compile(r'^\d{4}-\d{2}-\d{2}$')


def _is_iso(s: str) -> bool:
    return bool(_ISO_RE.match(s)) if s else False


def _sessio_to_dict(sessio) -> dict:
    if isinstance(sessio, dict):
        return {"nom": sessio.get("nom", ""), "nom_base": sessio.get("nom_base", ""),
                "curs": sessio.get("curs"), "examens": sessio.get("examens", [])}
    return {"nom": getattr(sessio, "nom", ""), "nom_base": getattr(sessio, "nom_base", ""),
            "curs": getattr(sessio, "curs", None), "examens": getattr(sessio, "examens", [])}


def _item_label(item: dict) -> str:
    sessions = item.get("sessions") or []
    noms = [_sessio_to_dict(s).get("nom") for s in sessions]
    noms = [n for n in noms if n]
    return " + ".join(noms) if noms else item.get("nom") or "(sense nom)"


def _format_assignatures(assignatures: List[str], max_show: int = 4) -> str:
    """Formata una llista d'assignatures de manera concisa."""
    if not assignatures:
        return ""
    if len(assignatures) <= max_show:
        return ", ".join(assignatures)
    return ", ".join(assignatures[:max_show]) + f" i {len(assignatures) - max_show} més"


class InfeasibilityDiagnostic:
    """
    Analitza per què un motor no pot generar un horari complet.

    Ús:
        diag = InfeasibilityDiagnostic(
            restriccions, dies_efectius, hores_examen, nivells_actius
        )
        missatges = diag.run(items)
    """

    def __init__(
        self,
        restriccions: dict,
        dies_efectius: List[Tuple[str, str]],  # [(dia_nom, prefix_data)]
        hores_examen: List[str],
        nivells_actius: List[str],
    ):
        self.restriccions = restriccions
        self.dies_efectius = dies_efectius          # [(dia_nom, prefix)]
        self.hores_examen = list(hores_examen or [])
        self.nivells_actius = list(nivells_actius or [])
        self.engine = RestrictionEngine(restriccions, nivells_actius)

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def run(self, items: List[dict]) -> List[str]:
        """
        Retorna una llista de missatges d'incompatibilitat útils.

        `items` és la llista retornada per gen.preparar_particio_nivells().
        Cada item té: {'sessions': [...], 'nom': str, 'curs': str, ...}
        """
        if not items:
            return []

        # Calcular dates viables per ítem (sense context d'altres ítems)
        dates_per_item: Dict[str, Set[str]] = {}
        causa_per_item: Dict[str, str] = {}
        for item in items:
            label = _item_label(item)
            dates, causa = self._dates_viables(item)
            dates_per_item[label] = dates
            if not dates:
                causa_per_item[label] = causa

        msgs: List[str] = []
        seen: Set[str] = set()

        def add(msg: str):
            if msg not in seen:
                seen.add(msg)
                msgs.append(msg)

        # 1. Ítems sense cap slot viable — agrupar per nivell+causa (evita 19 línies iguals)
        from collections import defaultdict
        sense_slot_per_nivell_causa: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
        for item in items:
            label = _item_label(item)
            if not dates_per_item.get(label):
                causa = causa_per_item.get(label, "restricció desconeguda")
                sessions = item.get("sessions") or []
                nivell = item.get("curs") or (
                    _sessio_to_dict(sessions[0]).get("curs") if sessions else None
                ) or "desconegut"
                sense_slot_per_nivell_causa[nivell][causa].append(label)

        for nivell, per_causa in sorted(sense_slot_per_nivell_causa.items()):
            for causa, labels in sorted(per_causa.items()):
                n = len(labels)
                if n == 1:
                    add(f"'{labels[0]}' no té cap slot disponible — causa: {causa}")
                else:
                    exemple = labels[0].split(" + ")[0]  # Primer nom del primer ítem
                    add(
                        f"{nivell}: {n} ítems sense cap slot disponible — causa: {causa} "
                        f"(ex: '{exemple}', ...)"
                    )

        # 2. Restriccions no_mateix_dia: parelles atrapades i sobrecàrrega per grup
        self._check_no_mateix_dia(items, dates_per_item, add)

        # 3. Restriccions no_mateix_slot: ítems forçats al mateix slot
        self._check_no_mateix_slot(items, dates_per_item, add)

        # 4. Capacitat genèrica per nivell (sense restricció específica)
        self._check_capacitat(items, dates_per_item, add)

        return msgs

    # ------------------------------------------------------------------
    # Helpers privats
    # ------------------------------------------------------------------

    def _dates_viables(self, item: dict) -> Tuple[Set[str], str]:
        """
        Retorna (dates_on_hi_ha_slot_valid, causa_principal_si_cap_data).

        Comprova cada (dia, hora) cridant engine.check_hard() sense context
        d'altres ítems (sessions_dia=[], sessions_slot=[], dia_sessions=None).
        Retorna la causa MÉS FREQÜENT entre tots els slots bloquejats.
        """
        sessions = item.get("sessions") or []
        dates: Set[str] = set()
        causa_counts: Dict[str, int] = {}

        for dia_nom, prefix in self.dies_efectius:
            for hora in self.hores_examen:
                ok = True
                for sessio in sessions:
                    s_dict = _sessio_to_dict(sessio)
                    violation = self.engine.check_hard(
                        s_dict, dia_nom, hora, prefix,
                        sessions_dia=[], sessions_slot=[],
                        dia_sessions=None,  # evita checks de context (limit_dies, preferencia_dia)
                    )
                    if violation:
                        causa_counts[violation.label] = causa_counts.get(violation.label, 0) + 1
                        ok = False
                        break
                if ok:
                    dates.add(prefix)
                    break  # Una hora confirmada per aquesta data és suficient

        if dates:
            return dates, ""

        # Retornar la causa més freqüent
        causa = max(causa_counts, key=causa_counts.get) if causa_counts else "restricció desconeguda"
        return dates, causa

    def _check_no_mateix_dia(
        self, items: List[dict], dates_per_item: Dict[str, Set[str]], add
    ) -> None:
        """
        Detecta problemes amb restriccions 'no_mateix_dia':
        - Parelles d'ítems que no es poden separar en dies distints
        - Grups on el nombre d'ítems supera el nombre de dies disponibles
        """
        from collections import defaultdict as _dd
        dures = self.restriccions.get('restriccions_dures', {})
        no_mateix_dia_cfg = dures.get('no_mateix_dia', [])
        if not no_mateix_dia_cfg:
            return

        # Mapa dia_fix per assignatura (valor pot ser data ISO o nom de dia)
        dia_fix_cfg: Dict[str, str] = {}
        raw_dia_fix = (dures.get('assignatures_dia_fix') or {})
        if isinstance(raw_dia_fix, dict):
            for k, v in raw_dia_fix.items():
                if k.startswith('_'):
                    continue
                date_val = v.get('data') if isinstance(v, dict) else v
                if isinstance(date_val, str) and date_val:
                    dia_fix_cfg[k] = date_val

        n_dies = len(self.dies_efectius)

        for idx, restriccio in enumerate(no_mateix_dia_cfg, start=1):
            if isinstance(restriccio, dict):
                assignatures = restriccio.get('assignatures', [])
                pes = restriccio.get('pes', 100)
            else:
                assignatures = list(restriccio)
                pes = 100
            if not _pes_obligatori(pes):
                continue

            ref = f"Dies distints #{idx}"
            assigs_fmt = _format_assignatures(assignatures)

            # Trobar ítems del grup
            items_grup: List[Tuple[str, Set[str]]] = []
            for item in items:
                for s in (item.get('sessions') or []):
                    if sessio_in_group(_sessio_to_dict(s), assignatures):
                        label = _item_label(item)
                        items_grup.append((label, dates_per_item.get(label, set())))
                        break

            if len(items_grup) < 2:
                continue

            n_items_grup = len(items_grup)

            # Detecció directa: ítems del grup amb dia_fix al mateix dia
            # (funciona fins i tot quan dates_per_item és buit per alliberaments)
            fixes_per_label: Dict[str, str] = {}
            for item in items:
                for s in (item.get('sessions') or []):
                    s_dict = _sessio_to_dict(s)
                    if not sessio_in_group(s_dict, assignatures):
                        continue
                    nom = s_dict.get('nom') or s_dict.get('nom_base') or ''
                    nom_base = s_dict.get('nom_base') or ''
                    date_fix = dia_fix_cfg.get(nom) or dia_fix_cfg.get(nom_base)
                    if date_fix:
                        label = _item_label(item)
                        fixes_per_label[label] = date_fix
                    break

            per_data: Dict[str, List[str]] = _dd(list)
            for label, date_fix in fixes_per_label.items():
                per_data[date_fix].append(label)
            for date_fix, conflicting in per_data.items():
                if len(conflicting) >= 2:
                    noms_fmt = _format_assignatures(conflicting)
                    add(
                        f"⚠ Restricció '{ref}' [{assigs_fmt}]: "
                        f"{noms_fmt} han d'anar en dies distints "
                        f"però totes estan fixades al dia {date_fix}"
                    )

            # Detectar sobrecàrrega: grup té més ítems que dies disponibles
            if n_items_grup > n_dies:
                add(
                    f"⚠ Restricció '{ref}' [{assigs_fmt}]: "
                    f"{n_items_grup} assignatures han d'anar en dies distints "
                    f"però només hi ha {n_dies} dia(es) disponible(s) — "
                    f"cal reduir el grup o afegir més dies"
                )
                continue  # Les parelles ja no aporten informació addicional

            # Detectar parelles bloquejades (grup viable en teoria però parelles concretes no)
            for i in range(len(items_grup)):
                lbl_a, dates_a = items_grup[i]
                for j in range(i + 1, len(items_grup)):
                    lbl_b, dates_b = items_grup[j]
                    comunes = dates_a & dates_b
                    if not comunes:
                        continue
                    excl_a = dates_a - dates_b
                    excl_b = dates_b - dates_a

                    if not excl_a and not excl_b:
                        dates_fmt = ', '.join(sorted(comunes)[:3])
                        add(
                            f"⚠ Restricció '{ref}' [{assigs_fmt}]: "
                            f"'{lbl_a}' i '{lbl_b}' han d'anar en dies distints "
                            f"però ambdós limitats als mateixos dies: {dates_fmt}"
                        )
                    elif not excl_a:
                        dates_fmt = ', '.join(sorted(dates_a)[:3])
                        add(
                            f"⚠ Restricció '{ref}' [{assigs_fmt}]: "
                            f"'{lbl_a}' només pot anar a {dates_fmt}, "
                            f"que coincideix amb '{lbl_b}'"
                        )
                    elif not excl_b:
                        dates_fmt = ', '.join(sorted(dates_b)[:3])
                        add(
                            f"⚠ Restricció '{ref}' [{assigs_fmt}]: "
                            f"'{lbl_b}' només pot anar a {dates_fmt}, "
                            f"que coincideix amb '{lbl_a}'"
                        )

    def _check_no_mateix_slot(
        self, items: List[dict], dates_per_item: Dict[str, Set[str]], add
    ) -> None:
        """Detecta grups no_mateix_slot on tots els ítems estan forçats al mateix slot."""
        dures = self.restriccions.get('restriccions_dures', {})
        grups = dures.get('no_mateix_slot', {})
        if not grups or not isinstance(grups, dict):
            return

        # Construir slots viables per ítem (prefix + hora)
        slots_per_item: Dict[str, Set[str]] = {}
        for item in items:
            sessions = item.get("sessions") or []
            label = _item_label(item)
            slots: Set[str] = set()
            for dia_nom, prefix in self.dies_efectius:
                for hora in self.hores_examen:
                    ok = True
                    for sessio in sessions:
                        s_dict = _sessio_to_dict(sessio)
                        violation = self.engine.check_hard(
                            s_dict, dia_nom, hora, prefix,
                            sessions_dia=[], sessions_slot=[],
                            dia_sessions=None,  # evita checks de context
                        )
                        if violation:
                            ok = False
                            break
                    if ok:
                        slots.add(f"{prefix}_{hora}")
            slots_per_item[label] = slots

        for grup_nom, grup_val in grups.items():
            if grup_nom.startswith('_'):
                continue
            assignatures = grup_val if isinstance(grup_val, list) else grup_val.get('assignatures', [])
            pes = grup_val.get('pes', 100) if isinstance(grup_val, dict) else 100
            if not _pes_obligatori(pes):
                continue

            assigs_fmt = _format_assignatures(assignatures)
            ref = f"No al mateix moment '{grup_nom}'"

            items_grup: List[Tuple[str, Set[str]]] = []
            for item in items:
                for s in (item.get('sessions') or []):
                    if sessio_in_group(_sessio_to_dict(s), assignatures):
                        label = _item_label(item)
                        items_grup.append((label, slots_per_item.get(label, set())))
                        break

            if len(items_grup) < 2:
                continue

            for i in range(len(items_grup)):
                lbl_a, slots_a = items_grup[i]
                for j in range(i + 1, len(items_grup)):
                    lbl_b, slots_b = items_grup[j]
                    comunes = slots_a & slots_b
                    excl_a = slots_a - slots_b
                    excl_b = slots_b - slots_a
                    if comunes and not excl_a and not excl_b:
                        add(
                            f"⚠ Restricció '{ref}' [{assigs_fmt}]: "
                            f"'{lbl_a}' i '{lbl_b}' no poden coincidir "
                            f"però tots dos estan limitats als mateixos slots"
                        )

    def _check_capacitat(
        self, items: List[dict], dates_per_item: Dict[str, Set[str]], add
    ) -> None:
        """Detecta nivells on el nombre d'ítems amb slot vàlid supera els slots disponibles.
        Exclou ítems sense cap slot (ja reportats per separat) per evitar missatges redundants."""
        from collections import defaultdict
        items_per_nivell: Dict[str, int] = defaultdict(int)
        dates_per_nivell: Dict[str, Set[str]] = defaultdict(set)

        for item in items:
            sessions = item.get("sessions") or []
            nivell = item.get("curs") or (
                _sessio_to_dict(sessions[0]).get("curs") if sessions else None
            )
            if not nivell:
                continue
            label = _item_label(item)
            dates = dates_per_item.get(label, set())
            if not dates:
                continue  # Ja reportat com "sense cap slot" — no comptar aquí
            items_per_nivell[nivell] += 1
            dates_per_nivell[nivell].update(dates)

        n_hores = max(1, len(self.hores_examen))
        n_dies_total = len(self.dies_efectius)
        for nivell, count in items_per_nivell.items():
            n_dates = len(dates_per_nivell.get(nivell, set()))
            n_slots = (n_dates * n_hores) if n_dates else (n_dies_total * n_hores)
            if count > n_slots:
                add(
                    f"{nivell}: {count} ítems > {n_slots} slots disponibles "
                    f"({n_dates} dates × {n_hores} hores)"
                )


# ------------------------------------------------------------------
# Funció d'utilitat per construir dies_efectius des de dies_utilitzar
# ------------------------------------------------------------------

def construir_dies_efectius(
    dies_utilitzar: List[str],
    dia_a_data_iso: Optional[Dict] = None,
) -> List[Tuple[str, str]]:
    """
    Converteix la llista de dies_utilizzar en parelles (dia_nom, prefix).
    Suporta tant dates ISO com noms de dia.

    Per als noms de dia, expan la llista completa de dates ISO (dia_a_data_iso pot
    tenir llistes per suportar múltiples ocurrències del mateix dia de la setmana).
    Així el diagnòstic comprova TOTES les dates, igual que el motor.
    """
    result: List[Tuple[str, str]] = []
    for d in (dies_utilizzar or []):
        if _is_iso(d):
            try:
                dia_nom = DIES_CAT[_dt.strptime(d, "%Y-%m-%d").weekday()]
                result.append((dia_nom, d))
            except Exception:
                pass
        else:
            _map = dia_a_data_iso or {}
            iso = _map.get(_normalitzar_dia(d)) or _map.get(d)
            if isinstance(iso, list):
                # Expandir totes les dates (no agafar només la primera)
                for iso_date in iso:
                    if isinstance(iso_date, str) and iso_date:
                        result.append((d, iso_date))
                if not iso:
                    result.append((d, d))
            elif isinstance(iso, str) and iso:
                result.append((d, iso))
            else:
                result.append((d, d))
    return result
