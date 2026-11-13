"""
Validació post-generació d'horaris d'exàmens.
Detecta conflictes, violations de restriccions i genera logs d'incidències.
Extret de l'antic routes/scheduler.py (ara planificador/) per millorar mantenibilitat i testabilitat.

Les incidències que costen punts porten «(punt: N)» i surten del mateix càlcul
que el cost final (`estadistiques.incidencies_restriccions` i el cost de cada
professor): la suma dels punts del registre és el cost total. Les que no
sumen cap punt (enllaços, zona d'examen, conflictes de nivell, «mateix_slot»
obligatori) no en porten o porten «(punt: 0)».
"""

from scheduler_engine.core.scoring import TIPUS_COST_PROFESSOR, pes_professor
from scheduler_engine.estadistiques import incidencies_restriccions


def _nom_base_assignatura(nom: str) -> str:
    if not nom:
        return ""
    if " (" in nom:
        return nom.split(" (")[0].strip()
    return nom.strip()


def _mateix_slot_groups(raw) -> list[list[str]]:
    groups = []
    for g in raw or []:
        if isinstance(g, dict):
            assignatures = g.get("assignatures", [])
        else:
            assignatures = g
        if isinstance(assignatures, list) and assignatures:
            groups.append(assignatures)
    return groups


def _assig_in_group(assig: str, grup: list[str]) -> bool:
    base = _nom_base_assignatura(assig)
    return assig in grup or (base and base in grup)


def _log_with_score(msg: str, score: int | None) -> str:
    if score is None:
        return msg
    return f"{msg} (punt: {score})"


def etiqueta_dia(nom_dia: str, data_iso: str | None) -> str:
    """«Dilluns 20/04»: amb la data, dues setmanes no es confonen (i dues
    incidències del mateix dia de la setmana no queden en una sola línia)."""
    if data_iso and len(data_iso) >= 10:
        return f"{nom_dia} {data_iso[8:10]}/{data_iso[5:7]}"
    return nom_dia


def text_incidencia(inc) -> str:
    """La línia del registre d'una incidència de restriccions (sense els punts)."""
    dia = etiqueta_dia(inc.dia, inc.data)
    amb = ", ".join(a for a in inc.amb if a)
    textos = {
        "limit_dies_professor": lambda: f"🚨 LÍMIT DIES: {inc.professor} → {inc.detall}",
        "combinacio_no_permesa": lambda: (
            f"🚫 COMBINACIÓ NO PERMESA: {inc.curs} → {inc.hora} el {dia}: {inc.nom} amb {amb}"
        ),
        "no_mateix_slot": lambda: f"⚠️ NO AL MATEIX MOMENT: {inc.nom} → coincideix amb {amb} a {inc.hora} el {dia}",
        "no_mateix_dia": lambda: f"⚠️ DIES DISTINTS: {inc.nom} → coincideix amb {amb} el {dia}",
        "dia_hora_fix": lambda: (
            f"⚠️ DIA/HORA FIXAT: {inc.nom} → a {inc.hora} el {dia}, fora del dia, l'hora o les franges permeses"
        ),
        "preferencia_dies_diferents": lambda: f"⚠️ DIES DIFERENTS: {inc.nom} → el mateix dia que {amb} (el {dia})",
        "preferencia_mateix_dia": lambda: f"⚠️ MATEIX DIA: {inc.nom} → el mateix dia que {amb} (el {dia})",
        "preferencia_mateix_slot": lambda: (
            f"⚠️ MATEIXA FRANJA: {inc.nom} → {amb} el mateix dia (el {dia}) però no a {inc.hora}"
        ),
        "assignatures_dies_exclosos": lambda: f"⚠️ DIA EXCLÒS: {inc.nom} → el {dia} és un dia exclòs",
    }
    if inc.concepte in textos:
        return textos[inc.concepte]()
    return f"⚠️ {inc.concepte.upper()}: {inc.nom} → a {inc.hora} el {dia}"


class ValidadorHorari:
    """
    Valida un horari generat contra les restriccions configurades.
    Genera logs d'incidències per mostrar a l'usuari.

    dia_a_data_iso: per als dies sense data (la mateixa que fa servir el cost final).
    """

    def __init__(self, horari: dict, restriccions: dict, no_subst: set[str], dia_a_data_iso: dict | None = None):
        self.horari = horari
        self.restriccions = restriccions
        self.no_subst = no_subst or set()
        self.dia_a_data_iso = dia_a_data_iso
        # Ordre d'aparició (no un `set`): la llista no depèn de PYTHONHASHSEED
        self.logs: dict[str, None] = {}
        # Punts de les línies amb cost; dues incidències amb el mateix text sumen
        self._punts: dict[str, int] = {}

        # Pre-calcular estructures
        self.mateix_slot_grups = _mateix_slot_groups(restriccions.get("restriccions_dures", {}).get("mateix_slot", []))
        self.combinacions_sets = []
        for c in restriccions.get("restriccions_dures", {}).get("combinacions_permeses", []):
            assigs = c.get("assignatures", []) if isinstance(c, dict) else c
            self.combinacions_sets.append({_nom_base_assignatura(a) for a in assigs})

        self.assignatures_ubicacio: dict[str, list] = {}

    def validar(self) -> dict:
        """
        Executa totes les validacions i retorna els logs generats.

        Returns:
            {"logs": list[str]} — llista de missatges d'incidències
        """
        self._escanejar_ubicacions()
        self._detectar_conflictes_professors()
        self._detectar_conflictes_alumnes()
        self._comprovar_mateix_slot()
        self._incidencies_restriccions()
        self._generar_logs_incidencies()
        return {
            "logs": [
                _log_with_score(linia, self._punts[linia]) if linia in self._punts else linia for linia in self.logs
            ]
        }

    def _registra(self, linia: str) -> None:
        self.logs[linia] = None

    def _registra_cost(self, linia: str, punts: int) -> None:
        """Una incidència que suma `punts` al cost total."""
        self.logs[linia] = None
        self._punts[linia] = self._punts.get(linia, 0) + punts

    def _dia(self, dia: dict) -> str:
        return etiqueta_dia(dia.get("dia", ""), dia.get("data"))

    def _escanejar_ubicacions(self):
        """Crea el mapa assignatura -> [(dia, hora)] per al «mateix_slot» obligatori."""
        if not self.mateix_slot_grups:
            return
        for dia in self.horari.get("dies", []):
            dia_clau = self._dia(dia)
            for slot in dia.get("sessions", []):
                for sessio in slot.get("sessions_simultanees", []):
                    for nom in (sessio.get("nom"), sessio.get("nom_base")):
                        if nom:
                            self.assignatures_ubicacio.setdefault(nom, []).append((dia_clau, slot["hora"]))

    def _detectar_conflictes_professors(self):
        """Detecta professors amb múltiples exàmens al mateix slot. No costen
        punts per si mateixos: si hi ha un «no al mateix moment», el cost és a
        la seva línia."""
        for dia in self.horari.get("dies", []):
            for slot in dia.get("sessions", []):
                professors_slot: dict[str, list] = {}
                for sessio in slot.get("sessions_simultanees", []):
                    nivell = sessio.get("curs", "")
                    assignatura_base = sessio.get("nom_base") or sessio.get("nom")
                    for examen in sessio.get("examens", []):
                        prof = examen.get("titular")
                        if prof and prof != "":
                            professors_slot.setdefault(prof, []).append(
                                {"assignatura": assignatura_base, "nivell": nivell}
                            )

                for prof, examens_prof in professors_slot.items():
                    if len(examens_prof) <= 1:
                        continue
                    parelles = {(e["assignatura"], e["nivell"]) for e in examens_prof}
                    assignatures_uniques = sorted({a for a, _ in parelles})
                    nivells_unics = sorted({n for _, n in parelles})

                    if len(nivells_unics) == 1:
                        msg = f"🔗 ENLLAÇ: {prof} → gestiona {len(assignatures_uniques)} exàmens de {nivells_unics[0]} a {slot.get('hora')} el {self._dia(dia)}: {', '.join(assignatures_uniques)}"
                        self._registra(_log_with_score(msg, 0))
                    else:
                        detalls = ", ".join(sorted({f"{a} ({n})" for a, n in parelles}))
                        msg = f"⚠️ AVÍS: {prof} → té exàmens de nivells diferents a {slot.get('hora')} el {self._dia(dia)}: {detalls}"
                        self._registra(msg)
                        # Un examen per assignatura i nivell (Filosofia de 1r i de 2n en són dos)
                        msg_enllac = f"🔗 ENLLAÇ: {prof} → gestiona {len(parelles)} exàmens de nivells diferents a {slot.get('hora')} el {self._dia(dia)}: {detalls}"
                        self._registra(_log_with_score(msg_enllac, 0))

    def _detectar_conflictes_alumnes(self):
        """Detecta alumnes amb múltiples exàmens simultanis (excloent optatives
        i combinacions permeses). No suma punts: el cost no el compta (l'horari
        deixa de ser vàlid); si hi ha combinacions definides, la combinació no
        permesa sí que en suma, a la seva línia."""
        for dia in self.horari.get("dies", []):
            for slot in dia.get("sessions", []):
                cursos_slot: dict[str, list] = {}
                for sessio in slot.get("sessions_simultanees", []):
                    curs = sessio.get("curs")
                    if curs:
                        cursos_slot.setdefault(curs, []).append(sessio.get("nom"))

                for curs, assignatures in cursos_slot.items():
                    if len(assignatures) <= 1:
                        continue

                    totes_mateix_grup = any(
                        all(_assig_in_group(assig, grup) for assig in assignatures) for grup in self.mateix_slot_grups
                    )

                    es_combinacio_permesa = False
                    if not totes_mateix_grup and self.combinacions_sets:
                        assig_noms = {_nom_base_assignatura(a) for a in assignatures}
                        es_combinacio_permesa = any(
                            assig_noms.issubset(comb_set) for comb_set in self.combinacions_sets
                        )

                    if not totes_mateix_grup and not es_combinacio_permesa:
                        msg = f"⚠️ CONFLICTE ALUMNES: {curs} → {len(assignatures)} exàmens simultanis a {slot.get('hora')} el {self._dia(dia)}: {', '.join(assignatures)}"
                        self._registra(msg)

    def _comprovar_mateix_slot(self):
        """Comprova que assignatures agrupades estiguin al mateix slot. Els
        motors les col·loquen juntes (un sol ítem); només es poden separar a mà,
        i el cost no ho compta: la línia no porta punts."""
        for grup in self.mateix_slot_grups:
            ubicacions: dict[tuple, list] = {}
            for assig in grup:
                for loc in self.assignatures_ubicacio.get(assig, []):
                    ubicacions.setdefault(loc, []).append(assig)

            if len(ubicacions) > 1:
                msg = f"⚠️ VIOLACIÓ 'mateix_slot': {', '.join(grup)} haurien d'estar juntes però estan separades:"
                self._registra(msg)
                for (dia, hora), assigs in ubicacions.items():
                    self._registra(f"   • {', '.join(assigs)} → {dia} a les {hora}")

    def _incidencies_restriccions(self):
        """Restriccions i preferències amb cost (no al mateix moment, dies
        distints, dia/hora fixat, preferències, combinacions, dies exclosos i
        límit per professor): les mateixes incidències i punts que el cost final."""
        for inc in incidencies_restriccions(self.horari, self.restriccions, self.dia_a_data_iso):
            self._registra_cost(text_incidencia(inc), inc.punts)

    def _generar_logs_incidencies(self):
        """Genera logs d'incidències de professors (abans/després jornada,
        substitucions, no treballa aquest dia).

        Una sola línia per professor, dia i hora, amb tots els exàmens que la
        provoquen: un professor que vigila dos exàmens alhora deixa una sola
        classe. La puntuació és el cost del professor (individual o global),
        la mateixa que compten els motors i el cost final (un cop per franja).
        """

        incidencies = {}  # (tipus, prof, dia, franja, hora) -> {'item', 'dia', 'contextos'}
        for dia in self.horari.get("dies", []):
            clau_dia = dia.get("data") or dia["dia"]
            for slot in dia.get("sessions", []):
                for sessio in slot.get("sessions_simultanees", []):
                    an = sessio.get("analisi", {})
                    sessio_nom = sessio.get("nom", "")
                    sessio_curs = sessio.get("curs", "")
                    examen_ctx = (
                        f"({sessio_nom})->{sessio_curs}"
                        if sessio_nom and sessio_curs
                        else f"({sessio_nom})"
                        if sessio_nom
                        else f"->{sessio_curs}"
                        if sessio_curs
                        else ""
                    )
                    for camp, tipus in TIPUS_COST_PROFESSOR.items():
                        for item in an.get(camp, []):
                            if not isinstance(item, dict) or not item.get("professor"):
                                continue
                            prof = item["professor"]
                            hora_item = item.get("hora", slot["hora"])
                            # Per franja, com el cost (costos_professors_analisi)
                            entrada = incidencies.setdefault(
                                (tipus, prof, clau_dia, slot["hora"], hora_item),
                                {"item": item, "dia": self._dia(dia), "contextos": []},
                            )
                            if examen_ctx and examen_ctx not in entrada["contextos"]:
                                entrada["contextos"].append(examen_ctx)

        for (tipus, prof, _, _, hora_item), entrada in incidencies.items():
            item, nom_dia = entrada["item"], entrada["dia"]
            ctx = f" {', '.join(sorted(entrada['contextos']))}" if entrada["contextos"] else ""
            punts = pes_professor(self.restriccions, prof, tipus)
            if tipus == "abans_jornada":
                msg = f"🕐 {prof}{ctx} → arriba abans a {hora_item} el {nom_dia} (primera hora: {item.get('primera_hora', '?')})"
            elif tipus == "despres_jornada":
                msg = f"🕐 {prof}{ctx} → queda més estona a {hora_item} el {nom_dia} (última hora: {item.get('ultima_hora', '?')})"
            elif tipus == "no_treballa_dia":
                msg = f"🚫 {prof}{ctx} → no treballa aquest dia a les {hora_item} el {nom_dia}"
            else:
                act = item.get("activitat", {})
                assig = act.get("assignatura", "Assignatura")
                if assig in self.no_subst:
                    continue
                msg = f"🚨 {prof}{ctx} → ha de ser SUBSTITUÏT a {assig} amb {act.get('grup', 'un grup')} a les {hora_item} el {nom_dia}"
            self._registra_cost(msg, punts)

        for dia in self.horari.get("dies", []):
            for slot in dia.get("sessions", []):
                for sessio in slot.get("sessions_simultanees", []):
                    an = sessio.get("analisi", {})
                    sessio_nom = sessio.get("nom", "")
                    sessio_curs = sessio.get("curs", "")
                    examen_ctx = (
                        f" ({sessio_nom})->{sessio_curs}"
                        if sessio_nom and sessio_curs
                        else f" ({sessio_nom})"
                        if sessio_nom
                        else f" ->{sessio_curs}"
                        if sessio_curs
                        else ""
                    )
                    vistos_zona = set()
                    for item in an.get("zona_examen", []):
                        prof = item.get("professor", "Desconegut")
                        act = item.get("activitat", {})
                        assig = act.get("assignatura", "Assignatura")
                        grp = act.get("grup", "un grup")
                        hora_item = item.get("hora", slot["hora"])
                        key = (prof, dia["dia"], hora_item, sessio_nom)
                        if key in vistos_zona:
                            continue
                        vistos_zona.add(key)
                        msg = f"👁️ {prof}{examen_ctx} → en zona examen a {assig} amb {grp} a les {hora_item} el {self._dia(dia)}"
                        self._registra(_log_with_score(msg, 0))
