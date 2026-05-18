"""
Validació post-generació d'horaris d'exàmens.
Detecta conflictes, violations de restriccions i genera logs d'incidències.
Extret de routes/scheduler.py per millorar mantenibilitat i testabilitat.
"""

from typing import Dict, List, Set, Optional

from scheduler_engine.defaults import DEFAULT_COST_PROFESSORS
from scheduler_engine.core.constraints import _percent_penalty, _percent_value, percent_no_mateix_slot


def _nom_base_assignatura(nom: str) -> str:
    if not nom:
        return ""
    if " (" in nom:
        return nom.split(" (")[0].strip()
    return nom.strip()


def _mateix_slot_groups(raw) -> List[List[str]]:
    groups = []
    for g in raw or []:
        if isinstance(g, dict):
            assignatures = g.get("assignatures", [])
        else:
            assignatures = g
        if isinstance(assignatures, list) and assignatures:
            groups.append(assignatures)
    return groups


def _assig_in_group(assig: str, grup: List[str]) -> bool:
    base = _nom_base_assignatura(assig)
    return assig in grup or (base and base in grup)


def _log_with_score(msg: str, score: Optional[int]) -> str:
    if score is None:
        return msg
    return f"{msg} (punt: {score})"


class ValidadorHorari:
    """
    Valida un horari generat contra les restriccions configurades.
    Genera logs d'incidències per mostrar a l'usuari.
    """

    def __init__(self, horari: Dict, restriccions: Dict, no_subst: Set[str]):
        self.horari = horari
        self.restriccions = restriccions
        self.no_subst = no_subst or set()
        self.logs: Set[str] = set()

        # Extreure pesos amb el mateix criteri que el cost final (només costos_professors + pesos_optimitzacio)
        pesos_opt = restriccions.get('pesos_optimitzacio', {})
        costos_globals = (restriccions.get('costos_professors', {}) or {}).get('globals', {})
        self.pes_sub = costos_globals.get('substitucio', DEFAULT_COST_PROFESSORS["substitucio"])
        self.pes_abans = costos_globals.get('abans_jornada', DEFAULT_COST_PROFESSORS["abans_jornada"])
        self.pes_despres = costos_globals.get('despres_jornada', DEFAULT_COST_PROFESSORS["despres_jornada"])
        self.pes_restriccio_dura = pesos_opt.get('restriccio_dura', 1000)
        self.pes_restriccio_dura_violada = pesos_opt.get(
            'restriccio_dura_violada',
            self.pes_restriccio_dura
        )
        self.pes_dies_diferents = pesos_opt.get('preferencia_dies_diferents', 500)

        # Pre-calcular estructures
        self.mateix_slot_grups = _mateix_slot_groups(
            restriccions.get('restriccions_dures', {}).get('mateix_slot', [])
        )
        _nms_raw = restriccions.get('restriccions_dures', {}).get('no_mateix_slot', {})
        self.no_mateix_slot_grups: Dict[str, list] = {
            k: v for k, v in (_nms_raw.items() if isinstance(_nms_raw, dict) else {}.items())
            if not k.startswith('_') and isinstance(v, list)
        }
        _nmd_raw = restriccions.get('restriccions_dures', {}).get('no_mateix_dia', [])
        self.no_mateix_dia_grups: List[dict] = []
        for r in (_nmd_raw if isinstance(_nmd_raw, list) else []):
            if isinstance(r, dict):
                assigs = r.get('assignatures', [])
                pes = r.get('pes', 100)
            else:
                assigs = list(r)
                pes = 100
            if assigs:
                self.no_mateix_dia_grups.append({'assignatures': assigs, 'pes': pes})

        self.combinacions_permeses = restriccions.get('restriccions_dures', {}).get('combinacions_permeses', [])
        self.combinacions_sets = []
        for c in self.combinacions_permeses:
            assigs = c.get('assignatures', []) if isinstance(c, dict) else c
            self.combinacions_sets.append({_nom_base_assignatura(a) for a in assigs})

        self.assignatures_ubicacio: Dict[str, list] = {}
        self.assignatures_per_dia: Dict[str, set] = {}

    def validar(self) -> Dict:
        """
        Executa totes les validacions i retorna els logs generats.

        Returns:
            {"logs": list[str]} — llista de missatges d'incidències
        """
        self._escanejar_ubicacions()
        self._detectar_conflictes_professors()
        self._detectar_conflictes_alumnes()
        self._detectar_combinacions_no_permeses()
        self._comprovar_mateix_slot()
        self._comprovar_no_mateix_slot()
        self._comprovar_no_mateix_dia()
        self._comprovar_limits_dies()
        self._comprovar_dies_diferents()
        self._generar_logs_incidencies()
        return {"logs": list(self.logs)}

    def _escanejar_ubicacions(self):
        """Crea mapes: assignatura -> [(dia, hora)] i assignatura -> {dia} per validació."""
        if not self.mateix_slot_grups and not self.no_mateix_slot_grups and not self.no_mateix_dia_grups:
            return
        for dia in self.horari.get('dies', []):
            dia_clau = dia.get('data') or dia.get('dia', '')
            for slot in dia.get('sessions', []):
                for sessio in slot.get('sessions_simultanees', []):
                    nom = sessio.get('nom')
                    nom_base = sessio.get('nom_base')
                    if nom:
                        self.assignatures_ubicacio.setdefault(nom, []).append(
                            (dia_clau, slot['hora'])
                        )
                        self.assignatures_per_dia.setdefault(nom, set()).add(dia_clau)
                    if nom_base:
                        self.assignatures_ubicacio.setdefault(nom_base, []).append(
                            (dia_clau, slot['hora'])
                        )
                        self.assignatures_per_dia.setdefault(nom_base, set()).add(dia_clau)

    def _detectar_conflictes_professors(self):
        """Detecta professors amb múltiples exàmens al mateix slot."""
        for dia in self.horari.get('dies', []):
            for slot in dia.get('sessions', []):
                professors_slot: Dict[str, list] = {}
                for sessio in slot.get('sessions_simultanees', []):
                    nivell = sessio.get('curs', '')
                    assignatura_base = sessio.get('nom_base') or sessio.get('nom')
                    for examen in sessio.get('examens', []):
                        prof = examen.get('titular')
                        if prof and prof != "":
                            professors_slot.setdefault(prof, []).append({
                                'assignatura': assignatura_base,
                                'nivell': nivell
                            })

                for prof, examens_prof in professors_slot.items():
                    if len(examens_prof) <= 1:
                        continue
                    parelles = {(e['assignatura'], e['nivell']) for e in examens_prof}
                    assignatures_uniques = list({a for a, _ in parelles})
                    nivells_unics = list({n for _, n in parelles})

                    if len(nivells_unics) == 1:
                        msg = f"🔗 ENLLAÇ: {prof} → gestiona {len(assignatures_uniques)} exàmens de {nivells_unics[0]} a {slot.get('hora')} el {dia.get('dia')}: {', '.join(assignatures_uniques)}"
                        self.logs.add(_log_with_score(msg, 0))
                    else:
                        detalls = ', '.join(sorted({f"{a} ({n})" for a, n in parelles}))
                        msg = f"⚠️ AVÍS: {prof} → té exàmens de nivells diferents a {slot.get('hora')} el {dia.get('dia')}: {detalls}"
                        # Calcular cost real si hi ha restricció no_mateix_slot per alguna parella
                        score_avis = 0
                        assigs_amb_nivell = list({f"{a} ({n})" for a, n in parelles})
                        for nom_grup, grup_assigs in self.no_mateix_slot_grups.items():
                            matching = [a for a in assigs_amb_nivell
                                        if a in grup_assigs or _nom_base_assignatura(a) in grup_assigs]
                            if len(matching) >= 2:
                                pct = percent_no_mateix_slot(self.restriccions, nom_grup)
                                score_avis = max(score_avis, _percent_penalty(self.pes_restriccio_dura, pct))
                        self.logs.add(_log_with_score(msg, score_avis if score_avis else None))
                        msg_enllac = f"🔗 ENLLAÇ: {prof} → gestiona {len(assignatures_uniques)} exàmens de nivells diferents a {slot.get('hora')} el {dia.get('dia')}: {', '.join(assignatures_uniques)}"
                        self.logs.add(_log_with_score(msg_enllac, 0))

    def _detectar_conflictes_alumnes(self):
        """Detecta alumnes amb múltiples exàmens simultanis (excloent optatives i combinacions permeses)."""
        for dia in self.horari.get('dies', []):
            for slot in dia.get('sessions', []):
                cursos_slot: Dict[str, list] = {}
                for sessio in slot.get('sessions_simultanees', []):
                    curs = sessio.get('curs')
                    if curs:
                        cursos_slot.setdefault(curs, []).append(sessio.get('nom'))

                for curs, assignatures in cursos_slot.items():
                    if len(assignatures) <= 1:
                        continue

                    totes_mateix_grup = any(
                        all(_assig_in_group(assig, grup) for assig in assignatures)
                        for grup in self.mateix_slot_grups
                    )

                    es_combinacio_permesa = False
                    if not totes_mateix_grup and self.combinacions_sets:
                        assig_noms = {_nom_base_assignatura(a) for a in assignatures}
                        es_combinacio_permesa = any(
                            assig_noms.issubset(comb_set)
                            for comb_set in self.combinacions_sets
                        )

                    if not totes_mateix_grup and not es_combinacio_permesa:
                        msg = f"⚠️ CONFLICTE ALUMNES: {curs} → {len(assignatures)} exàmens simultanis a {slot.get('hora')} el {dia.get('dia')}: {', '.join(assignatures)}"
                        self.logs.add(_log_with_score(msg, self.pes_restriccio_dura))

    def _detectar_combinacions_no_permeses(self):
        """Detecta combinacions de matèries no permeses al mateix slot."""
        if not self.combinacions_sets:
            return
        mateix_slot_sets = []
        for grup in self.mateix_slot_grups:
            noms = {_nom_base_assignatura(a) for a in grup if a}
            if noms:
                mateix_slot_sets.append(noms)

        for dia in self.horari.get('dies', []):
            for slot in dia.get('sessions', []):
                per_nivell: Dict[str, list] = {}
                for sessio in slot.get('sessions_simultanees', []):
                    curs = sessio.get('curs', '')
                    if curs:
                        per_nivell.setdefault(curs, []).append(sessio)

                for curs, sess_list in per_nivell.items():
                    if len(sess_list) <= 1:
                        continue
                    noms_slot = {
                        _nom_base_assignatura(s.get('nom_base') or s.get('nom', ''))
                        for s in sess_list if s
                    }
                    if not noms_slot:
                        continue
                    if any(noms_slot.issubset(grup) for grup in mateix_slot_sets):
                        continue
                    if any(noms_slot.issubset(comb) for comb in self.combinacions_sets):
                        continue
                    noms_txt = ', '.join(sorted(noms_slot))
                    for sessio in sess_list:
                        sessio_nom = sessio.get('nom_base') or sessio.get('nom', '')
                        msg = f"🚫 COMBINACIÓ NO PERMESA: {curs} → {slot.get('hora')} el {dia.get('dia')}: {sessio_nom} amb {noms_txt}"
                        self.logs.add(_log_with_score(msg, self.pes_restriccio_dura))

    def _comprovar_mateix_slot(self):
        """Comprova que assignatures agrupades estiguin al mateix slot."""
        for grup in self.mateix_slot_grups:
            ubicacions: Dict[tuple, list] = {}
            for assig in grup:
                for loc in self.assignatures_ubicacio.get(assig, []):
                    ubicacions.setdefault(loc, []).append(assig)

            if len(ubicacions) > 1:
                percent = 100
                for g in self.restriccions.get('restriccions_dures', {}).get('mateix_slot', []):
                    if isinstance(g, dict) and set(g.get('assignatures', [])) == set(grup):
                        percent = _percent_value(g.get('pes', 100))
                        break
                score = _percent_penalty(self.pes_restriccio_dura, percent)
                msg = f"⚠️ VIOLACIÓ 'mateix_slot': {', '.join(grup)} haurien d'estar juntes però estan separades:"
                self.logs.add(_log_with_score(msg, score))
                for (dia, hora), assigs in ubicacions.items():
                    submsg = f"   • {', '.join(assigs)} → {dia} a les {hora}"
                    self.logs.add(_log_with_score(submsg, score))

    def _comprovar_no_mateix_slot(self):
        """Comprova que assignatures amb no_mateix_slot no coincideixin al mateix slot."""
        for nom_grup, assignatures in self.no_mateix_slot_grups.items():
            percent = percent_no_mateix_slot(self.restriccions, nom_grup)
            score = _percent_penalty(self.pes_restriccio_dura, percent)

            assigs_list = [(a, self.assignatures_ubicacio.get(a, [])) for a in assignatures]
            for i in range(len(assigs_list)):
                assig_a, slots_a = assigs_list[i]
                if not slots_a:
                    continue
                for j in range(i + 1, len(assigs_list)):
                    assig_b, slots_b = assigs_list[j]
                    if not slots_b:
                        continue
                    collisions = set(slots_a).intersection(slots_b)
                    for (dia, hora) in collisions:
                        msg = (f"⚠️ VIOLACIÓ 'no_mateix_slot': {assig_a} i {assig_b} "
                               f"coincideixen a {hora} el {dia}")
                        self.logs.add(_log_with_score(msg, score))

    def _comprovar_no_mateix_dia(self):
        """Comprova que assignatures amb no_mateix_dia no coincideixin al mateix dia."""
        for grup in self.no_mateix_dia_grups:
            assignatures = grup['assignatures']
            pes = grup['pes']
            score = _percent_penalty(self.pes_restriccio_dura, pes)

            assigs_list = [(a, self.assignatures_per_dia.get(a) or
                            self.assignatures_per_dia.get(_nom_base_assignatura(a), set()))
                           for a in assignatures]
            for i in range(len(assigs_list)):
                assig_a, dies_a = assigs_list[i]
                if not dies_a:
                    continue
                for j in range(i + 1, len(assigs_list)):
                    assig_b, dies_b = assigs_list[j]
                    if not dies_b:
                        continue
                    for dia in dies_a & dies_b:
                        msg = (f"⚠️ VIOLACIÓ 'no_mateix_dia': {assig_a} i {assig_b} "
                               f"coincideixen el {dia}")
                        self.logs.add(_log_with_score(msg, score))

    def _comprovar_limits_dies(self):
        """Comprova límits d'exàmens per professor en dies específics."""
        if any("LÍMIT DIES:" in l for l in self.horari.get("metadata", {}).get("logs", [])):
            return  # El motor ja ha generat aquests logs

        professors_limits = self.restriccions.get('restriccions_dures', {}).get(
            'professors_limit_dies_especifics', {}
        )
        if isinstance(professors_limits, dict):
            professors_limits = {k: v for k, v in professors_limits.items() if not k.startswith('_')}
        else:
            professors_limits = {}

        if not professors_limits:
            return

        sessions_per_dia: Dict[str, list] = {}
        for dia in self.horari.get('dies', []):
            sessions = []
            for slot in dia.get('sessions', []):
                sessions.extend(slot.get('sessions_simultanees', []))
            sessions_per_dia[dia.get('dia')] = sessions

        for prof, config_prof in professors_limits.items():
            assignatures_restringides = config_prof.get('assignatures', [])
            dies_restringits = config_prof.get('dies_restringits', [])
            max_examens = config_prof.get('max_examens')
            if max_examens is None:
                continue
            max_examens = int(max_examens)
            _v = config_prof.get('pes_penalitzacio')
            pes_penalitzacio = int(_v) if _v is not None else 50
            if not assignatures_restringides or not dies_restringits:
                continue

            count_examens = 0
            per_day: Dict[str, int] = {}
            for dia_check in dies_restringits:
                for sessio in sessions_per_dia.get(dia_check, []):
                    profs = {e.get('titular') for e in sessio.get('examens', []) if e.get('titular')}
                    if prof not in profs:
                        continue
                    nom_sessio = sessio.get('nom', '')
                    if _assig_in_group(nom_sessio, assignatures_restringides):
                        count_examens += 1
                        per_day[dia_check] = per_day.get(dia_check, 0) + 1

            excedent = count_examens - max_examens
            if excedent > 0:
                score = _percent_penalty(self.pes_restriccio_dura_violada, pes_penalitzacio) * excedent
                dies_txt = ", ".join([f"{d}({per_day[d]})" for d in per_day]) if per_day else ", ".join(dies_restringits)
                msg = f"🚨 LÍMIT DIES: {prof} → {count_examens} exàmens en {dies_txt} (màx {max_examens}, pes {pes_penalitzacio}%)"
                self.logs.add(_log_with_score(msg, score))

    def _comprovar_dies_diferents(self):
        """Comprova preferència que assignatures estiguin en dies diferents."""
        dies_diferents_grups = self.restriccions.get('preferencies', {}).get('dies_diferents', [])
        if not dies_diferents_grups:
            return

        for grup in dies_diferents_grups:
            assignatures = grup.get('assignatures', []) if isinstance(grup, dict) else grup
            if not assignatures or len(assignatures) < 2:
                continue
            percent = grup.get('pes', 0) if isinstance(grup, dict) else 0
            score = _percent_penalty(self.pes_dies_diferents, percent)

            ubicacions_dia: Dict[str, list] = {}
            for assig in assignatures:
                for loc in self.assignatures_ubicacio.get(assig, []):
                    dia_loc, _ = loc
                    ubicacions_dia.setdefault(dia_loc, [])
                    if assig not in ubicacions_dia[dia_loc]:
                        ubicacions_dia[dia_loc].append(assig)

            for dia_check, assigs_dia in ubicacions_dia.items():
                if len(assigs_dia) > 1:
                    msg = f"⚠️ DIES DIFERENTS: {', '.join(assigs_dia)} haurien d'estar en dies diferents però estan juntes el {dia_check}"
                    self.logs.add(_log_with_score(msg, score))

    def _generar_logs_incidencies(self):
        """Genera logs d'incidències de professors (abans/després jornada, substitucions)."""
        vistos_subs = set()
        vistos_abans = set()
        vistos_despres = set()
        for dia in self.horari.get('dies', []):
            for slot in dia.get('sessions', []):
                for sessio in slot.get('sessions_simultanees', []):
                    an = sessio.get('analisi', {})
                    sessio_nom = sessio.get('nom', '')
                    sessio_curs = sessio.get('curs', '')
                    examen_ctx = (
                        f" ({sessio_nom})->{sessio_curs}" if sessio_nom and sessio_curs
                        else f" ({sessio_nom})" if sessio_nom
                        else f" ->{sessio_curs}" if sessio_curs
                        else ""
                    )

                    for item in an.get('abans_jornada', []):
                        hora_item = item.get('hora', slot['hora'])
                        key = (item.get('professor'), dia['dia'], hora_item, sessio_nom)
                        if key in vistos_abans:
                            continue
                        vistos_abans.add(key)
                        msg = f"🕐 {item['professor']}{examen_ctx} → arriba abans a {hora_item} el {dia['dia']} (primera hora: {item.get('primera_hora', '?')})"
                        self.logs.add(_log_with_score(msg, self.pes_abans))

                    for item in an.get('despres_jornada', []):
                        hora_item = item.get('hora', slot['hora'])
                        key = (item.get('professor'), dia['dia'], hora_item, sessio_nom)
                        if key in vistos_despres:
                            continue
                        vistos_despres.add(key)
                        msg = f"🕐 {item['professor']}{examen_ctx} → queda més estona a {hora_item} el {dia['dia']} (última hora: {item.get('ultima_hora', '?')})"
                        self.logs.add(_log_with_score(msg, self.pes_despres))

                    for item in an.get('substitucions', []):
                        prof = item.get('professor', 'Desconegut')
                        act = item.get('activitat', {})
                        assig = act.get('assignatura', 'Assignatura')
                        grp = act.get('grup', 'un grup')
                        hora_item = item.get('hora', slot['hora'])
                        key = (prof, dia['dia'], hora_item, sessio_nom)
                        if key in vistos_subs:
                            continue
                        vistos_subs.add(key)
                        if assig not in self.no_subst:
                            msg = f"🚨 {prof}{examen_ctx} → ha de ser SUBSTITUÏT a {assig} amb {grp} a les {hora_item} el {dia['dia']}"
                            self.logs.add(_log_with_score(msg, self.pes_sub))

                    vistos_zona = set()
                    for item in an.get('zona_examen', []):
                        prof = item.get('professor', 'Desconegut')
                        act = item.get('activitat', {})
                        assig = act.get('assignatura', 'Assignatura')
                        grp = act.get('grup', 'un grup')
                        hora_item = item.get('hora', slot['hora'])
                        key = (prof, dia['dia'], hora_item, sessio_nom)
                        if key in vistos_zona:
                            continue
                        vistos_zona.add(key)
                        msg = f"👁️ {prof}{examen_ctx} → en zona examen a {assig} amb {grp} a les {hora_item} el {dia['dia']}"
                        self.logs.add(_log_with_score(msg, 0))
