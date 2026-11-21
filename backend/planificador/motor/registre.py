"""
Validació post-generació d'horaris d'exàmens.
Detecta conflictes, violacions de restriccions i genera les incidències.

Cada incidència és un missatge amb dades: {"codi", "params", "punts"}; la
pantalla les classifica pel codi i les tradueix (`scheduler.incidencies.<codi>`).
Les que costen punts porten `punts` i surten del mateix càlcul que el cost final
(`avaluador.incidencies_restriccions` i el cost de cada professor): la suma dels
punts del registre és el cost total. Les que no sumen cap punt (enllaços, zona
d'examen) porten `punts: 0`; els conflictes de nivell i la «mateix_slot»
obligatòria, cap.

Els dies porten el nom (`dia`) i la data ISO (`data`, si l'horari la té).
"""

import json
from collections import defaultdict

from planificador.compartit.normalitzacio import nom_base_assignatura as _nom_base_assignatura
from planificador.compartit.punts import punts_horari_estricte
from planificador.motor.avaluador import (
    TIPUS_COST_PROFESSOR,
    incidencies_restriccions,
    pes_professor,
    professors_horari_estricte,
)
from planificador.motor.regles import recompte_limit_professor

# Format de les incidències dels logs (metadata.format_incidencies): 2 = missatges amb dades
FORMAT_INCIDENCIES = 2


def _grups_mateix_slot(raw) -> list[list[str]]:
    groups = []
    for g in raw or []:
        if isinstance(g, dict):
            assignatures = g.get("assignatures", [])
        else:
            assignatures = g
        if isinstance(assignatures, list) and assignatures:
            groups.append(assignatures)
    return groups


def _assignatura_al_grup(assig: str, grup: list[str]) -> bool:
    base = _nom_base_assignatura(assig)
    return assig in grup or (base and base in grup)


def incidencia(codi: str, punts: int | None = None, **params) -> dict:
    """Un missatge d'incidència; sense `punts`, no en porta (no suma ni es mostra)."""
    missatge = {"codi": codi, "params": params}
    if punts is not None:
        missatge["punts"] = punts
    return missatge


def _dia_i_data(dia: str, data: str | None) -> dict:
    return {"dia": dia or "", "data": data or None}


def _examens_ctx(contextos) -> list[dict]:
    """Els exàmens on surt una incidència d'un professor, en ordre estable."""
    return sorted((dict(c) for c in contextos), key=lambda c: (f"({c['nom']})->{c['curs']}", c["nom"], c["curs"]))


# Els camps de cada concepte de restriccions: els que identifiquen la incidència (dues
# d'iguals sumen els punts en una sola línia)
CAMPS_RESTRICCIONS = {
    "no_mateix_slot": ("nom", "amb", "hora", "dia"),
    "no_mateix_dia": ("nom", "amb", "dia"),
    "dia_hora_fix": ("nom", "hora", "dia"),
    "preferencia_dies_diferents": ("nom", "amb", "dia"),
    "preferencia_mateix_dia": ("nom", "amb", "dia"),
    "preferencia_mateix_slot": ("nom", "amb", "hora", "dia"),
}


def missatge_incidencia(inc) -> dict:
    """El missatge d'una incidència de restriccions (sense els punts)."""
    if inc.concepte == "limit_dies_professor":
        return incidencia("inc_limit_dies_professor", professor=inc.professor, **dict(inc.dades))
    if inc.concepte == "mateix_dia_obligatori":
        return incidencia("inc_mateix_dia_obligatori", nom=inc.nom, dates=list(inc.amb))
    params = {}
    for camp in CAMPS_RESTRICCIONS.get(inc.concepte, ("nom", "hora", "dia")):
        if camp == "amb":
            params["amb"] = [a for a in inc.amb if a]
        elif camp == "dia":
            params.update(_dia_i_data(inc.dia, inc.data))
        else:
            params[camp] = getattr(inc, camp)
    return incidencia(f"inc_{inc.concepte}", **params)


class ValidadorHorari:
    """
    Valida un horari generat contra les restriccions configurades.
    Genera les incidències per mostrar a l'usuari.

    dia_a_data_iso: per als dies sense data (la mateixa que fa servir el cost final).
    """

    def __init__(self, horari: dict, restriccions: dict, no_subst: set[str], dia_a_data_iso: dict | None = None):
        self.horari = horari
        self.restriccions = restriccions
        self.no_subst = no_subst or set()
        self.dia_a_data_iso = dia_a_data_iso
        # Ordre d'aparició (no un `set`): la llista no depèn de PYTHONHASHSEED. Dues
        # incidències iguals (mateix codi i paràmetres) en fan una, i en sumen els punts.
        self.logs: dict[str, dict] = {}

        # Pre-calcular estructures
        self.mateix_slot_grups = _grups_mateix_slot(restriccions.get("restriccions_dures", {}).get("mateix_slot", []))

        self.assignatures_ubicacio: dict[str, list] = {}

    def validar(self) -> dict:
        """
        Executa totes les validacions i retorna les incidències.

        Retorna:
            {"logs": list[dict]} — missatges {codi, params, punts}
        """
        self._escanejar_ubicacions()
        self._detectar_conflictes_professors()
        self._detectar_conflictes_alumnes()
        self._comprovar_mateix_slot()
        self._incidencies_restriccions()
        self._generar_logs_incidencies()
        return {"logs": list(self.logs.values())}

    def _registra(self, missatge: dict, punts: int | None = None) -> None:
        """Una incidència; amb `punts`, en suma al cost total."""
        clau = json.dumps([missatge["codi"], missatge["params"]], sort_keys=True, ensure_ascii=False)
        if clau not in self.logs:
            self.logs[clau] = dict(missatge)
        if punts is not None:
            self.logs[clau]["punts"] = self.logs[clau].get("punts", 0) + punts

    def _dia(self, dia: dict) -> dict:
        return _dia_i_data(dia.get("dia", ""), dia.get("data"))

    def _escanejar_ubicacions(self):
        """Crea el mapa assignatura -> [(dia, data, hora)] per al «mateix_slot» obligatori."""
        if not self.mateix_slot_grups:
            return
        for dia in self.horari.get("dies", []):
            dia_clau = (dia.get("dia", ""), dia.get("data") or None)
            for slot in dia.get("sessions", []):
                for sessio in slot.get("sessions_simultanees", []):
                    for nom in (sessio.get("nom"), sessio.get("nom_base")):
                        if nom:
                            self.assignatures_ubicacio.setdefault(nom, []).append((*dia_clau, slot["hora"]))

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
                    lloc = {"hora": slot.get("hora"), **self._dia(dia)}

                    if len(nivells_unics) == 1:
                        self._registra(
                            incidencia(
                                "inc_enllac",
                                professor=prof,
                                count=len(assignatures_uniques),
                                nivell=nivells_unics[0],
                                assignatures=assignatures_uniques,
                                **lloc,
                            ),
                            0,
                        )
                    else:
                        detalls = sorted({f"{a} ({n})" for a, n in parelles})
                        self._registra(
                            incidencia("inc_nivells_diferents", professor=prof, examens_nivells=detalls, **lloc)
                        )
                        # Un examen per assignatura i nivell (Filosofia de 1r i de 2n en són dos)
                        self._registra(
                            incidencia(
                                "inc_enllac_nivells",
                                professor=prof,
                                count=len(parelles),
                                examens_nivells=detalls,
                                **lloc,
                            ),
                            0,
                        )

    def _detectar_conflictes_alumnes(self):
        """Detecta alumnes amb múltiples exàmens simultanis (excloent les
        agrupacions). No suma punts: el cost no el compta (l'horari deixa de ser
        vàlid)."""
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
                        all(_assignatura_al_grup(assig, grup) for assig in assignatures)
                        for grup in self.mateix_slot_grups
                    )

                    if not totes_mateix_grup:
                        self._registra(
                            incidencia(
                                "inc_conflicte_alumnes",
                                nivell=curs,
                                count=len(assignatures),
                                assignatures=assignatures,
                                hora=slot.get("hora"),
                                **self._dia(dia),
                            )
                        )

    def _comprovar_mateix_slot(self):
        """Comprova que assignatures agrupades estiguin al mateix slot. Els
        motors les col·loquen juntes (un sol ítem); només es poden separar a mà,
        i el cost no ho compta: no porta punts. Una sola incidència amb on és cada part."""
        for grup in self.mateix_slot_grups:
            ubicacions: dict[tuple, list] = {}
            for assig in grup:
                for loc in self.assignatures_ubicacio.get(assig, []):
                    ubicacions.setdefault(loc, []).append(assig)

            if len(ubicacions) > 1:
                self._registra(
                    incidencia(
                        "inc_agrupacio_separada",
                        assignatures=list(grup),
                        ubicacions=[
                            {"assignatures": assigs, "hora": hora, **_dia_i_data(dia, data)}
                            for (dia, data, hora), assigs in ubicacions.items()
                        ],
                    )
                )

    def _incidencies_restriccions(self):
        """Restriccions i preferències amb cost (no al mateix moment, dies
        distints, dia/hora fixat, preferències i
        límit per professor): les mateixes incidències i punts que el cost final."""
        for inc in incidencies_restriccions(self.horari, self.restriccions, self.dia_a_data_iso):
            self._registra(missatge_incidencia(inc), inc.punts)

    def _generar_logs_incidencies(self):
        """Genera les incidències de professors (abans/després jornada,
        substitucions, no treballa aquest dia).

        Una sola incidència per professor, dia i hora, amb tots els exàmens que la
        provoquen: un professor que vigila dos exàmens alhora deixa una sola
        classe. La puntuació és el cost del professor (individual o global),
        la mateixa que compten els motors i el cost final (un cop per data).
        """

        incidencies_prof = {}  # (tipus, prof, data, hora) -> {'item', 'dia', 'contextos'}
        estrictes = set(professors_horari_estricte(self.restriccions))
        fora_horari_estricte = {}  # (prof, dia, franja) -> dia per mostrar
        for dia in self.horari.get("dies", []):
            clau_dia = dia.get("data") or dia["dia"]
            for slot in dia.get("sessions", []):
                for sessio in slot.get("sessions_simultanees", []):
                    an = sessio.get("analisi", {})
                    examen = {"nom": sessio.get("nom", "") or "", "curs": sessio.get("curs", "") or ""}
                    for camp, tipus in TIPUS_COST_PROFESSOR.items():
                        for item in an.get(camp, []):
                            if not isinstance(item, dict) or not item.get("professor"):
                                continue
                            prof = item["professor"]
                            hora_item = item.get("hora", slot["hora"])
                            if prof in estrictes and camp in ("abans_jornada", "despres_jornada", "no_treballa_dia"):
                                fora_horari_estricte.setdefault((prof, clau_dia, slot["hora"]), self._dia(dia))
                            # Per data, com el cost (costos_professors_analisi)
                            entrada = incidencies_prof.setdefault(
                                (tipus, prof, clau_dia, hora_item),
                                {"item": item, "dia": self._dia(dia), "contextos": []},
                            )
                            if (examen["nom"] or examen["curs"]) and examen not in entrada["contextos"]:
                                entrada["contextos"].append(examen)

        for (tipus, prof, _, hora_item), entrada in incidencies_prof.items():
            item = entrada["item"]
            comu = {"professor": prof, "examens": _examens_ctx(entrada["contextos"]), "hora": hora_item}
            comu.update(entrada["dia"])
            punts = pes_professor(self.restriccions, prof, tipus)
            if tipus == "abans_jornada":
                missatge = incidencia("inc_abans", primera=item.get("primera_hora", "?"), **comu)
            elif tipus == "despres_jornada":
                missatge = incidencia("inc_despres", ultima=item.get("ultima_hora", "?"), **comu)
            elif tipus == "no_treballa_dia":
                missatge = incidencia("inc_no_treballa", **comu)
            else:
                act = item.get("activitat", {})
                assig = act.get("assignatura", "Assignatura")
                if assig in self.no_subst:
                    continue
                missatge = incidencia("inc_substitucio", assignatura=assig, grup=act.get("grup", ""), **comu)
            self._registra(missatge, punts)

        # Horari estricte: els motors no el trenquen mai; editant a mà sí (un cop per franja, com el cost).
        for (prof, _, hora), dia in fora_horari_estricte.items():
            self._registra(
                incidencia("inc_horari_estricte", professor=prof, hora=hora, **dia),
                punts_horari_estricte(self.restriccions),
            )

        for dia in self.horari.get("dies", []):
            for slot in dia.get("sessions", []):
                for sessio in slot.get("sessions_simultanees", []):
                    an = sessio.get("analisi", {})
                    examen = {"nom": sessio.get("nom", "") or "", "curs": sessio.get("curs", "") or ""}
                    examens = [examen] if examen["nom"] or examen["curs"] else []
                    for item in an.get("zona_examen", []):
                        act = item.get("activitat", {})
                        self._registra(
                            incidencia(
                                "inc_zona_examen",
                                professor=item.get("professor", ""),
                                examens=examens,
                                assignatura=act.get("assignatura", "Assignatura"),
                                grup=act.get("grup", ""),
                                hora=item.get("hora", slot["hora"]),
                                **self._dia(dia),
                            ),
                            0,
                        )


# (clau de l'anàlisi de disponibilitat, tipus de cost i codi), en l'ordre en què surten
TIPUS_INCIDENCIA = (
    ("substitucions", "substitucio", "inc_substitucio"),
    ("abans_jornada", "abans_jornada", "inc_abans"),
    ("despres_jornada", "despres_jornada", "inc_despres"),
    ("no_treballa_dia", "no_treballa_dia", "inc_no_treballa"),
)


def _missatge_franja(codi, prof, hora, dia, data, item, pes):
    params = {"professor": prof, "examens": [], "hora": hora, **_dia_i_data(dia, data)}
    if codi == "inc_substitucio":
        act = item.get("activitat", {})
        params.update(assignatura=act.get("assignatura", "Assignatura"), grup=act.get("grup", ""))
    elif codi == "inc_abans":
        params["primera"] = item.get("primera_hora", "?")
    elif codi == "inc_despres":
        params["ultima"] = item.get("ultima_hora", "?")
    return incidencia(codi, pes, **params)


def incidencies(analisi: dict, hora: str, dia: str, restriccions: dict, data: str | None = None):
    """(tipus de cost, professor, hora, avís amb la puntuació, pes) de cada
    incidència de l'anàlisi d'una sessió, sense repetir-ne cap."""
    vistes = set()
    for clau, tipus, codi in TIPUS_INCIDENCIA:
        for item in analisi.get(clau, []):
            prof = item.get("professor")
            if not prof:
                continue
            hora_item = item.get("hora", hora)
            if (tipus, prof, hora_item) in vistes:
                continue
            vistes.add((tipus, prof, hora_item))
            pes = pes_professor(restriccions, prof, tipus)
            yield tipus, prof, hora_item, _missatge_franja(codi, prof, hora_item, dia, data, item, pes), pes


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


def _sessions_per_dia(horari: dict) -> dict:
    """Sessions de cada dia, pel nom tal com ve a l'horari."""
    sessions = defaultdict(list)
    for dia_data in horari.get("dies", []):
        for slot_data in dia_data.get("sessions", []):
            # Per data (les regles del límit poden portar dates)
            sessions[dia_data.get("data") or dia_data.get("dia", "")].extend(slot_data.get("sessions_simultanees", []))
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
        excedent = recompte_limit_professor(professor, config_prof, sessions_per_dia).excedent
        if excedent:
            excessos.append(f"{professor} +{excedent}")
    return excessos
