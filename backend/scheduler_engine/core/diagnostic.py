"""
Diagnòstic d'infactibilitat per al generador d'horaris.

Quan un motor no pot col·locar tots els ítems, InfeasibilityDiagnostic analitza
quines restriccions dures impedeixen la generació i retorna missatges concrets
per mostrar a l'usuari.

No depèn d'analitzar_tots_slots() (que pot retornar 0 slots per problemes de càlcul).
En lloc, calcula dates viables per ítem cridant directament RestrictionEngine.check_hard().
"""

import re as _re
from collections import Counter, defaultdict

from scheduler_engine.core.constraints import (
    _pes_obligatori,
    get_restriccio_val,
    percent_assignatura_fix,
    recompte_limit_professor,
    sessio_in_group,
)
from scheduler_engine.core.franja import dia_de_prefix
from scheduler_engine.core.missatges import missatge
from scheduler_engine.core.normalitzacio import dia_nom_per_horari
from scheduler_engine.core.normalitzacio import normalitzar_dia as _normalitzar_dia
from scheduler_engine.core.restriction_engine import RestrictionEngine, causa_principal
from scheduler_engine.defaults import ETIQUETES_CAUSES

_ISO_RE = _re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Missatge propi d'un examen fixat (dia i/o hora obligatoris) que no té cap
# franja, segons què passa a la franja fixada (revisió 5.1)
MISSATGE_FIXAT = {
    "examen_fixat": "fixat_fora_de_dates",  # la franja fixada no és entre les planificades
    "franja_prohibida": "fixat_a_franja_prohibida",
    "nivell_sense_inici": "fixat_a_hora_sense_inici",
}


def _is_iso(s: str) -> bool:
    return bool(_ISO_RE.match(s)) if s else False


def _sessio_to_dict(sessio) -> dict:
    if isinstance(sessio, dict):
        return {
            "nom": sessio.get("nom", ""),
            "nom_base": sessio.get("nom_base", ""),
            "curs": sessio.get("curs"),
            "examens": sessio.get("examens", []),
        }
    return {
        "nom": getattr(sessio, "nom", ""),
        "nom_base": getattr(sessio, "nom_base", ""),
        "curs": getattr(sessio, "curs", None),
        "examens": getattr(sessio, "examens", []),
    }


def _item_label(item: dict) -> str:
    sessions = item.get("sessions") or []
    noms = [_sessio_to_dict(s).get("nom") for s in sessions]
    noms = [n for n in noms if n]
    return " + ".join(noms) if noms else item.get("nom") or ""


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
        dies_efectius: list[tuple[str, str]],  # [(dia_nom, prefix_data)]
        hores_examen: list[str],
        nivells_actius: list[str],
        analitza=None,
    ):
        """`analitza(sessio, dia, hora, data_iso)` és l'anàlisi de disponibilitat
        del motor: només es fa servir si hi ha professors amb horari estricte,
        perquè el motor de restriccions els pugui comprovar (revisió B2)."""
        self.analitza = analitza
        self.restriccions = restriccions
        self.dies_efectius = dies_efectius  # [(dia_nom, prefix)]
        self.hores_examen = list(hores_examen or [])
        self.nivells_actius = list(nivells_actius or [])
        self.engine = RestrictionEngine(restriccions, nivells_actius)

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def run(self, items: list[dict]) -> list[dict]:
        """
        Retorna una llista de missatges d'incompatibilitat útils.

        `items` és la llista retornada per gen.preparar_particio_nivells().
        Cada item té: {'sessions': [...], 'nom': str, 'curs': str, ...}
        """
        if not items:
            return []

        # Calcular dates viables per ítem (sense context d'altres ítems)
        # Per examen (id de l'ítem), no per nom: dos exàmens amb el mateix nom
        # es trepitjaven i el que quedava fora podia no sortir
        dates_per_item: dict[int, set[str]] = {}
        causa_per_item: dict[int, str] = {}
        for item in items:
            dates, causa = self._dates_viables(item)
            dates_per_item[id(item)] = dates
            if not dates:
                causa_per_item[id(item)] = causa

        msgs: list[dict] = []

        def add(msg: dict):
            if msg not in msgs:
                msgs.append(msg)

        # 1. Ítems sense cap slot viable — agrupar per nivell+causa (evita 19 línies iguals)

        sense_slot_per_nivell_causa: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
        for item in items:
            label = _item_label(item)
            if not dates_per_item[id(item)]:
                causa = causa_per_item.get(id(item), "desconeguda")
                fixat = self._missatge_fixat(item, causa)
                if fixat:
                    add(fixat)
                    continue
                sessions = item.get("sessions") or []
                nivell = item.get("curs") or (_sessio_to_dict(sessions[0]).get("curs") if sessions else None) or ""
                sense_slot_per_nivell_causa[nivell][causa].append(label)

        for nivell, per_causa in sorted(sense_slot_per_nivell_causa.items()):
            for causa, labels in sorted(per_causa.items(), key=lambda item: ETIQUETES_CAUSES.get(item[0], item[0])):
                n = len(labels)
                if n == 1:
                    add(missatge("examen_sense_hora_causa", nom=labels[0], causa=causa))
                else:
                    exemple = labels[0].split(" + ")[0]  # Primer nom del primer ítem
                    add(missatge("examens_sense_hora_causa", nivell=nivell, count=n, causa=causa, nom=exemple))

        # 2. Restriccions no_mateix_dia: parelles atrapades i sobrecàrrega per grup
        self._check_no_mateix_dia(items, dates_per_item, add)

        # 3. Límit d'exàmens per professor obligatori: més exàmens que no poden
        # anar fora dels dies restringits que el màxim
        self._check_limit_professor(items, dates_per_item, add)

        slots_per_item = {id(item): self._slots_viables(item) for item in items}

        # 4. Restriccions no_mateix_slot: més ítems incompatibles que hores possibles
        self._check_no_mateix_slot(items, slots_per_item, add)

        # 5. Capacitat genèrica per nivell (sense restricció específica)
        self._check_capacitat(items, slots_per_item, add)

        return msgs

    # ------------------------------------------------------------------
    # Helpers privats
    # ------------------------------------------------------------------

    def _viola(self, sessio, dia_nom: str, hora: str, prefix: str):
        """La restricció dura que impedeix posar la sessió a la franja, sense
        context d'altres exàmens (dia_sessions=None: ni el límit per
        professor ni la preferència de dia, que es comproven a part). Amb
        professors d'horari estricte, també els seus (cal l'anàlisi)."""
        s_dict = _sessio_to_dict(sessio)
        analisi = None
        if self.analitza and self.engine.professors_estrictes:
            analisi = self.analitza(
                sessio if isinstance(sessio, dict) else s_dict, dia_nom, hora, prefix if _is_iso(prefix) else None
            )
        return self.engine.check_hard(
            s_dict, dia_nom, hora, prefix, sessions_dia=[], sessions_slot=[], dia_sessions=None, analisi=analisi
        )

    def _slots_viables(self, item: dict) -> set[str]:
        """Les hores (prefix_hora) on l'ítem es pot col·locar sense context
        d'altres ítems."""
        sessions = item.get("sessions") or []
        slots: set[str] = set()
        for dia_nom, prefix in self.dies_efectius:
            for hora in self.hores_examen:
                if not any(self._viola(s, dia_nom, hora, prefix) for s in sessions):
                    slots.add(f"{prefix}_{hora}")
        return slots

    def _dates_viables(self, item: dict) -> tuple[set[str], str]:
        """
        Retorna (dates_on_hi_ha_slot_valid, causa_principal_si_cap_data).

        Comprova cada (dia, hora) cridant engine.check_hard() sense context
        d'altres ítems (sessions_dia=[], sessions_slot=[], dia_sessions=None).
        La causa és la que bloqueja més franges, i «examen fixat» només si no
        n'hi ha cap altra (`causa_principal`): d'un examen fixat interessa què
        passa a la seva franja.
        """
        sessions = item.get("sessions") or []
        dates: set[str] = set()
        causa_counts: Counter = Counter()

        for dia_nom, prefix in self.dies_efectius:
            for hora in self.hores_examen:
                ok = True
                for sessio in sessions:
                    violation = self._viola(sessio, dia_nom, hora, prefix)
                    if violation:
                        causa_counts[violation.restriction] += 1
                        ok = False
                        break
                if ok:
                    dates.add(prefix)
                    break  # Una hora confirmada per aquesta data és suficient

        if dates:
            return dates, ""

        return dates, causa_principal(causa_counts) or "desconeguda"

    def _missatge_fixat(self, item: dict, causa: str) -> dict | None:
        """Per a un examen amb dia i/o hora fixats (obligatoris) que no té cap
        franja: què passa a la franja fixada. Sense pin, o amb una altra
        causa (p. ex. l'horari estricte d'un professor), None: surt el
        missatge general amb la causa."""
        codi = MISSATGE_FIXAT.get(causa)
        if not codi:
            return None
        dures = self.restriccions.get("restriccions_dures", {})
        dies_fixos = {k: v for k, v in (dures.get("assignatures_dia_fix") or {}).items() if not k.startswith("_")}
        hores_fixes = {k: v for k, v in (dures.get("assignatures_hora_fix") or {}).items() if not k.startswith("_")}
        for sessio in item.get("sessions") or []:
            s_dict = _sessio_to_dict(sessio)
            dia = get_restriccio_val(dies_fixos, s_dict)
            dia = dia.get("data") if isinstance(dia, dict) else dia  # com a _check_no_mateix_dia
            hora = get_restriccio_val(hores_fixes, s_dict)
            if not (dia or hora) or percent_assignatura_fix(s_dict, dures) < 100:
                continue
            params = {"nom": s_dict.get("nom") or _item_label(item), "dia": str(dia or ""), "hora": str(hora or "")}
            if causa == "nivell_sense_inici":
                params["nivell"] = s_dict.get("curs") or item.get("curs") or ""
            return missatge(codi, **params)
        return None

    def _check_no_mateix_dia(self, items: list[dict], dates_per_item: dict[int, set[str]], add) -> None:
        """
        Detecta problemes amb restriccions 'no_mateix_dia':
        - Parelles d'ítems que no es poden separar en dies distints
        - Grups on el nombre d'ítems supera el nombre de dies disponibles
        """

        dures = self.restriccions.get("restriccions_dures", {})
        no_mateix_dia_cfg = dures.get("no_mateix_dia", [])
        if not no_mateix_dia_cfg:
            return

        # Mapa dia_fix per assignatura (valor pot ser data ISO o nom de dia)
        dia_fix_cfg: dict[str, str] = {}
        raw_dia_fix = dures.get("assignatures_dia_fix") or {}
        if isinstance(raw_dia_fix, dict):
            for k, v in raw_dia_fix.items():
                if k.startswith("_"):
                    continue
                date_val = v.get("data") if isinstance(v, dict) else v
                if isinstance(date_val, str) and date_val:
                    dia_fix_cfg[k] = date_val

        n_dies = len(self.dies_efectius)

        for idx, restriccio in enumerate(no_mateix_dia_cfg, start=1):
            if isinstance(restriccio, dict):
                assignatures = restriccio.get("assignatures", [])
                pes = restriccio.get("pes", 100)
            else:
                assignatures = list(restriccio)
                pes = 100
            if not _pes_obligatori(pes):
                continue

            referencia = {"index": idx, "assignatures": assignatures}

            # Trobar ítems del grup
            items_grup: list[tuple[str, set[str]]] = []
            for item in items:
                for s in item.get("sessions") or []:
                    if sessio_in_group(_sessio_to_dict(s), assignatures):
                        items_grup.append((_item_label(item), dates_per_item[id(item)]))
                        break

            if len(items_grup) < 2:
                continue

            n_items_grup = len(items_grup)

            # Detecció directa: ítems del grup amb dia_fix al mateix dia
            # (funciona fins i tot quan dates_per_item és buit per alliberaments)
            fixes_per_label: dict[str, str] = {}
            for item in items:
                for s in item.get("sessions") or []:
                    s_dict = _sessio_to_dict(s)
                    if not sessio_in_group(s_dict, assignatures):
                        continue
                    nom = s_dict.get("nom") or s_dict.get("nom_base") or ""
                    nom_base = s_dict.get("nom_base") or ""
                    date_fix = dia_fix_cfg.get(nom) or dia_fix_cfg.get(nom_base)
                    if date_fix:
                        label = _item_label(item)
                        fixes_per_label[label] = date_fix
                    break

            per_data: dict[str, list[str]] = defaultdict(list)
            for label, date_fix in fixes_per_label.items():
                per_data[date_fix].append(label)
            for date_fix, conflicting in per_data.items():
                if len(conflicting) >= 2:
                    add(missatge("fixats_mateix_dia", **referencia, noms=conflicting, dia=date_fix))

            # Detectar sobrecàrrega: grup té més ítems que dies disponibles
            if n_items_grup > n_dies:
                add(missatge("dies_insuficients", **referencia, count=n_items_grup, dies=n_dies))
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
                        dates_fmt = ", ".join(sorted(comunes)[:3])
                        add(missatge("parella_mateixos_dies", **referencia, nom=lbl_a, altre=lbl_b, dies=dates_fmt))
                    elif not excl_a:
                        dates_fmt = ", ".join(sorted(dates_a)[:3])
                        add(missatge("examen_dies_solapats", **referencia, nom=lbl_a, altre=lbl_b, dies=dates_fmt))
                    elif not excl_b:
                        dates_fmt = ", ".join(sorted(dates_b)[:3])
                        add(missatge("examen_dies_solapats", **referencia, nom=lbl_b, altre=lbl_a, dies=dates_fmt))

    def _check_limit_professor(self, items: list[dict], dates_per_item: dict[int, set[str]], add) -> None:
        """Límit d'exàmens per professor obligatori (pes >= 100, revisió 5.2):
        els exàmens del professor (de les assignatures del límit) que només
        tenen dates possibles en dies restringits hi aniran per força; si en
        són més que el màxim, no hi ha horari. Es compten amb la mateixa regla
        que el motor i el cost (`recompte_limit_professor`). El check_hard del
        diagnòstic no ho pot veure: va sense context d'altres exàmens."""
        limits = self.restriccions.get("restriccions_dures", {}).get("professors_limit_dies_especifics") or {}
        if not isinstance(limits, dict):
            return
        dia_de = {prefix: dia for dia, prefix in self.dies_efectius}
        for professor, cfg in limits.items():
            if str(professor).startswith("_") or not isinstance(cfg, dict) or cfg.get("max_examens") is None:
                continue
            if not _pes_obligatori(cfg.get("pes_penalitzacio", 0)):
                continue
            restringits = {_normalitzar_dia(d) for d in cfg.get("dies_restringits", [])}
            forcades: dict[str, list[dict]] = defaultdict(list)  # data → sessions que hi aniran per força
            noms: list[str] = []
            for item in items:
                dates = dates_per_item[id(item)]
                if not dates:
                    continue  # sense cap data ja surt com a «sense cap hora»
                if any(dia_nom_per_horari(dia_de.get(p, p)) not in restringits for p in dates):
                    continue  # té alguna data fora dels dies restringits
                sessions = [_sessio_to_dict(s) for s in item.get("sessions") or []]
                if not recompte_limit_professor(professor, cfg, {}, sessions).examens:
                    continue  # no és del professor (o no és de les assignatures del límit)
                forcades[min(dates)].extend(sessions)
                noms.append(_item_label(item))
            recompte = recompte_limit_professor(professor, cfg, forcades)
            if recompte.excedent:
                add(
                    missatge(
                        "limit_professor_insuficient",
                        professor=professor,
                        max=int(cfg["max_examens"]),
                        count=recompte.examens,
                        noms=noms,
                        dies=", ".join(cfg.get("dies_restringits", [])),
                    )
                )

    def _check_no_mateix_slot(self, items: list[dict], slots_per_item: dict[int, set[str]], add) -> None:
        """Detecta grups no_mateix_slot que no hi caben: dos ítems limitats a
        la mateixa hora única, o més ítems que hores possibles entre tots."""
        dures = self.restriccions.get("restriccions_dures", {})
        grups = dures.get("no_mateix_slot", {})
        if not grups or not isinstance(grups, dict):
            return

        for grup_nom, grup_val in grups.items():
            if grup_nom.startswith("_"):
                continue
            assignatures = grup_val if isinstance(grup_val, list) else grup_val.get("assignatures", [])
            pes = grup_val.get("pes", 100) if isinstance(grup_val, dict) else 100
            if not _pes_obligatori(pes):
                continue

            referencia = {"grup": grup_nom, "assignatures": assignatures}

            # Els ítems sense cap hora possible ja surten com a «sense cap slot»
            items_grup: list[tuple[str, set[str]]] = []
            for item in items:
                if any(sessio_in_group(_sessio_to_dict(s), assignatures) for s in (item.get("sessions") or [])):
                    slots = slots_per_item[id(item)]
                    if slots:
                        items_grup.append((_item_label(item), slots))

            if len(items_grup) < 2:
                continue

            parelles = False
            for i in range(len(items_grup)):
                lbl_a, slots_a = items_grup[i]
                for j in range(i + 1, len(items_grup)):
                    lbl_b, slots_b = items_grup[j]
                    if len(slots_a) == 1 and slots_a == slots_b:
                        parelles = True
                        add(missatge("parella_mateixa_hora", **referencia, nom=lbl_a, altre=lbl_b))

            # Si no hi ha cap parella atrapada, pot ser que no hi càpiguen tots
            hores_conjunt = set().union(*(slots for _, slots in items_grup))
            if not parelles and len(items_grup) > len(hores_conjunt):
                add(missatge("hores_insuficients", **referencia, count=len(items_grup), hores=len(hores_conjunt)))

    def _check_capacitat(self, items: list[dict], slots_per_item: dict[int, set[str]], add) -> None:
        """Detecta nivells amb més ítems que hores possibles (la unió de les
        de tots els ítems del nivell). Exclou els ítems sense cap hora, que ja
        surten per separat."""

        items_per_nivell: dict[str, int] = defaultdict(int)
        slots_per_nivell: dict[str, set[str]] = defaultdict(set)

        for item in items:
            sessions = item.get("sessions") or []
            nivell = item.get("curs") or (_sessio_to_dict(sessions[0]).get("curs") if sessions else None)
            if not nivell:
                continue
            slots = slots_per_item[id(item)]
            if not slots:
                continue  # Ja reportat com "sense cap slot" — no comptar aquí
            items_per_nivell[nivell] += 1
            slots_per_nivell[nivell].update(slots)

        for nivell, count in items_per_nivell.items():
            slots = slots_per_nivell[nivell]
            if count > len(slots):
                n_dates = len({slot.rsplit("_", 1)[0] for slot in slots})
                add(missatge("capacitat_nivell_dates", nivell=nivell, count=count, hores=len(slots), dies=n_dates))


# ------------------------------------------------------------------
# Funció d'utilitat per construir dies_efectius des de dies_utilitzar
# ------------------------------------------------------------------


def construir_dies_efectius(
    dies_utilitzar: list[str],
    dia_a_data_iso: dict | None = None,
) -> list[tuple[str, str]]:
    """
    Converteix la llista de dies_utilitzar en parelles (dia_nom, prefix).
    Suporta tant dates ISO com noms de dia.

    Per als noms de dia, expan la llista completa de dates ISO (dia_a_data_iso pot
    tenir llistes per suportar múltiples ocurrències del mateix dia de la setmana).
    Així el diagnòstic comprova TOTES les dates, igual que el motor.
    """
    result: list[tuple[str, str]] = []
    for d in dies_utilitzar or []:
        if _is_iso(d):
            dia_nom, iso = dia_de_prefix(d)
            if iso:
                result.append((dia_nom, iso))
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
