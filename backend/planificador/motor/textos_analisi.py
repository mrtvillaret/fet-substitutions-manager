"""Matriu de disponibilitat i els tres informes d'Analitzar, com a dades: la pantalla
en tradueix les etiquetes i ja no interpreta cap text."""

import re as _re_iso

from planificador.compartit.normalitzacio import dia_nom_per_horari, normalitzar_dia
from planificador.motor.avaluador import cost_sessio
from planificador.motor.construccio import particio_antiga
from planificador.motor.disponibilitat import Disponibilitat
from planificador.motor.durades import examen_del_problema, examen_hi_cap, hores_ocupades, vigilancia
from planificador.motor.model import descongela
from planificador.motor.regles import calcular_penalitzacio_professors_dies_item, es_slot_valid_per_nivell
from textos import normalitzar_hora


def _text_professor(p: dict) -> str:
    """«Prof (assignatura, grup)»: l'ordre dels professors a l'informe."""
    entre = ", ".join(x for x in (p["assignatura"], p["grup"]) if x)
    return f"{p['professor']} ({entre})" if entre else p["professor"]


class TextosAnalisi:
    def __init__(self, problema):
        self.problema = problema
        self.nivells_actius = list(problema.nivells)
        self.hores_examen = list(problema.hores_inici)
        self.totes_hores = list(problema.graella)
        self.durada_titular = problema.durada_titular
        self.restriccions = problema.regles.a_diccionari()
        self.dia_a_data_iso = descongela(problema.mapa_dies)
        self.horaris_professors = descongela(problema.horaris_professors)
        self.nivells_dels_grups = problema.nivells_dels_grups()
        self.disponibilitat = Disponibilitat(problema)

    def get_durada_examen_per_sessio_key(self, nom):
        return examen_del_problema(nom, self.problema)

    def _get_hores_ocupades(self, hora):
        """Les hores de vigilància general (el titular) a partir de `hora`."""
        return hores_ocupades(hora, self.problema.graella, self.durada_titular)

    def analitzar_disponibilitat_sessio(
        self, sessio, dia, hora, sessions_slot=None, hores_override=None, data_iso=None
    ):
        # A la matriu, cada hora s'analitza separadament, per a examen i vigilància.
        return self.disponibilitat.analitza(
            sessio, dia, hora, data_iso, hores_override, hores_override, sessions_slot or ()
        )

    def matriu(self, dies):
        return self._analitzar_tots_slots(dies)

    def informes(self, dies, aplicar_abreviatura_grup):
        matriu = self.matriu(dies)
        return {
            "per_slots": self.informe_per_slots(matriu, dies),
            "per_sessio": self.informe_per_sessio(matriu, dies),
            "professors_slot": self.informe_professors_per_slot(
                dies, aplicar_abreviatura_grup=aplicar_abreviatura_grup
            ),
        }

    def _calcular_cost_sessio(
        self,
        sessio: dict,
        dia: str,
        hora: str,
        sessions_dia: list = None,
        sessions_slot: list = None,
        hores_override: list[str] | None = None,
        data_iso: str = None,
        ja_comptats: set | None = None,
    ) -> dict:
        analisi = self.analitzar_disponibilitat_sessio(
            sessio, dia, hora, sessions_slot, hores_override=hores_override, data_iso=data_iso
        )
        resultat_cost = cost_sessio(
            sessio=sessio,
            dia=dia,
            hora=hora,
            analisi=analisi,
            restriccions=self.restriccions,
            sessions_dia=sessions_dia,
            sessions_slot=sessions_slot,
            inclou_limit_dies=False,
            data_iso=data_iso or "",
            ja_comptats=ja_comptats,
        )
        desglossament = resultat_cost.get("breakdown", {})
        subs_professors = [i["professor"] for i in analisi.get("substitucions", []) if i.get("professor")]
        abans_professors = [i["professor"] for i in analisi.get("abans_jornada", []) if i.get("professor")]
        despres_professors = [i["professor"] for i in analisi.get("despres_jornada", []) if i.get("professor")]
        no_treballa_professors = [i["professor"] for i in analisi.get("no_treballa_dia", []) if i.get("professor")]

        subs_detalls = []
        for item in analisi.get("substitucions", []):
            prof = item.get("professor", "").strip()
            act = item.get("activitat", {}) or {}
            assig = act.get("assignatura", "").strip()
            grup = act.get("grup", "").strip()
            if not prof:
                continue
            etiqueta = f"{prof} → {assig}" if assig else prof
            if grup:
                etiqueta = f"{etiqueta} ({grup})"
            subs_detalls.append(etiqueta)

        def _compta(lst):
            return len({(i["professor"], i.get("hora", hora)) for i in lst})

        return {
            "analisi": analisi,
            "cost_substitucions": _compta(analisi.get("substitucions", [])),
            "cost_abans": _compta(analisi.get("abans_jornada", [])),
            "cost_despres": _compta(analisi.get("despres_jornada", [])),
            "cost_no_treballa": _compta(analisi.get("no_treballa_dia", [])),
            "subs_professors": subs_professors,
            "subs_detalls": subs_detalls,
            "abans_professors": abans_professors,
            "despres_professors": despres_professors,
            "no_treballa_professors": no_treballa_professors,
            "cost_preferencies": desglossament.get("preferencies", 0),
            "cost_total": resultat_cost["cost_total"],
            "professors_estrictes_violats": resultat_cost.get("professors_estrictes_violats", []),
        }

    def _slot_bloquejat(self, hora: str, sessions=None) -> bool:
        """True si a `hora` no hi cap sencer algun examen de `sessions` (la
        durada de cada examen); sense sessions, la vigilància general."""
        if sessions:
            return not all(examen_hi_cap(s.get("nom"), hora, self.problema) for s in sessions)
        return len(self._get_hores_ocupades(hora)) < self.durada_titular

    def _analitzar_tots_slots(self, dies_utilitzar: list[str]) -> dict:
        """Analitza el cost de cada agrupació a cada possible dia/hora."""
        totes_items = []
        for nivell in self.nivells_actius:
            items = [
                descongela(item.dades)
                for item in particio_antiga(
                    tuple(e for e in self.problema.examens if e.curs == nivell), self.problema.regles
                )
            ]
            for i, item in enumerate(items):
                etiqueta = self._etiqueta_item(item)
                totes_items.append((nivell, i, item, etiqueta))

        matriu_costos = {}
        for curs, idx, item, etiqueta in totes_items:
            nom_item = f"{curs}_{idx}_{etiqueta}"
            matriu_costos[nom_item] = {"item": item, "label": etiqueta, "curs": curs, "idx": idx, "slots": {}}

            for dia in dies_utilitzar:
                _is_iso = bool(_re_iso.match(r"^\d{4}-\d{2}-\d{2}$", dia))
                dia_horari = dia_nom_per_horari(dia)
                if _is_iso:
                    _data_iso_calc = dia
                else:
                    _d = self.dia_a_data_iso.get(normalitzar_dia(dia))
                    _data_iso_calc = _d[0] if isinstance(_d, list) else _d
                for hora in self.hores_examen:
                    if self._slot_bloquejat(hora, item.get("sessions", [])):
                        continue
                    # Respectar franges vàlids per nivell (alliberaments per dia/hora)
                    if any(
                        not es_slot_valid_per_nivell(
                            s.get("curs", ""), dia_horari, hora, self.restriccions, data_iso=_data_iso_calc
                        )
                        for s in item.get("sessions", [])
                    ):
                        continue
                    # En anàlisi només considerem subst/abans/després/no_treballa
                    slot_key = f"{dia}_{hora}"
                    total = {
                        "cost_substitucions": 0,
                        "cost_abans": 0,
                        "cost_despres": 0,
                        "cost_no_treballa": 0,
                        "cost_preferencies": 0,
                        "cost_total": 0,
                        "subs_professors": [],
                        "subs_detalls": [],
                        "abans_professors": [],
                        "despres_professors": [],
                        "no_treballa_professors": [],
                    }
                    hores_slot = self._get_hores_ocupades(hora)
                    # Un examen que dura més que la durada general s'analitza sencer
                    durada_item = max(
                        (
                            self.get_durada_examen_per_sessio_key(
                                s.get("nom"),
                            )
                            for s in item.get("sessions", [])
                        ),
                        default=0,
                    )
                    if durada_item > len(hores_slot) and hora in self.totes_hores:
                        idx = self.totes_hores.index(hora)
                        hores_slot = self.totes_hores[idx : min(idx + durada_item, len(self.totes_hores))]
                    per_hora = {
                        hora_real: {
                            "cost_substitucions": 0,
                            "cost_abans": 0,
                            "cost_despres": 0,
                            "cost_no_treballa": 0,
                            "cost_preferencies": 0,
                            "cost_total": 0,
                            "subs_professors": [],
                            "subs_detalls": [],
                            "abans_professors": [],
                            "despres_professors": [],
                            "no_treballa_professors": [],
                        }
                        for hora_real in hores_slot
                    }
                    for sessio in item.get("sessions", []):
                        # Regla única de durada: només les hores de vigilància compten; les altres
                        # hores de l'examen són zona d'examen, informatives i sense cost.
                        vigilades = set(
                            hores_ocupades(
                                hora,
                                self.totes_hores,
                                vigilancia(sessio.get("nom"), self.problema.durades_vigilancia, self.durada_titular),
                            )
                        )
                        for hora_real in hores_slot:
                            info_cost = self._calcular_cost_sessio(
                                sessio, dia_horari, hora_real, hores_override=[hora_real], data_iso=_data_iso_calc
                            )
                            if normalitzar_hora(hora_real) not in vigilades:
                                per_hora[hora_real].setdefault("zona_professors", []).extend(
                                    info_cost.get("subs_professors", [])
                                    + info_cost.get("abans_professors", [])
                                    + info_cost.get("despres_professors", [])
                                    + info_cost.get("no_treballa_professors", [])
                                )
                                continue
                            total["cost_substitucions"] += info_cost.get("cost_substitucions", 0)
                            total["cost_abans"] += info_cost.get("cost_abans", 0)
                            total["cost_despres"] += info_cost.get("cost_despres", 0)
                            total["cost_no_treballa"] += info_cost.get("cost_no_treballa", 0)
                            total["cost_preferencies"] += info_cost.get("cost_preferencies", 0)
                            total["cost_total"] += info_cost.get("cost_total", 0)
                            total["subs_professors"].extend(info_cost.get("subs_professors", []))
                            total["subs_detalls"].extend(info_cost.get("subs_detalls", []))
                            total["abans_professors"].extend(info_cost.get("abans_professors", []))
                            total["despres_professors"].extend(info_cost.get("despres_professors", []))
                            total["no_treballa_professors"].extend(info_cost.get("no_treballa_professors", []))

                            bloc_hora = per_hora[hora_real]
                            bloc_hora["cost_substitucions"] += info_cost.get("cost_substitucions", 0)
                            bloc_hora["cost_abans"] += info_cost.get("cost_abans", 0)
                            bloc_hora["cost_despres"] += info_cost.get("cost_despres", 0)
                            bloc_hora["cost_no_treballa"] += info_cost.get("cost_no_treballa", 0)
                            bloc_hora["cost_preferencies"] += info_cost.get("cost_preferencies", 0)
                            bloc_hora["cost_total"] += info_cost.get("cost_total", 0)
                            bloc_hora["subs_professors"].extend(info_cost.get("subs_professors", []))
                            bloc_hora["subs_detalls"].extend(info_cost.get("subs_detalls", []))
                            bloc_hora["abans_professors"].extend(info_cost.get("abans_professors", []))
                            bloc_hora["despres_professors"].extend(info_cost.get("despres_professors", []))
                            bloc_hora["no_treballa_professors"].extend(info_cost.get("no_treballa_professors", []))
                    # Penalització de límit dies (un sol cop per ítem)
                    clau_limit = _data_iso_calc or dia_horari  # el límit pot portar dates
                    p_limit = calcular_penalitzacio_professors_dies_item(
                        item, clau_limit, {clau_limit: item.get("sessions", [])}, self.restriccions
                    )
                    if p_limit:
                        total["cost_total"] += p_limit
                    total["per_hour"] = per_hora
                    matriu_costos[nom_item]["slots"][slot_key] = total

        return matriu_costos

    # ------------------------------------------------------------------ informes (com a dades)
    # Cada informe és una llista de dades; la pantalla en tradueix les etiquetes. Els dies van
    # tal com són a la planificació (data ISO o nom de dia).

    @staticmethod
    def _detalls(**llistes) -> list[dict]:
        """[{tipus, noms}] dels tipus amb algun professor, en l'ordre donat."""
        return [{"tipus": tipus, "noms": noms} for tipus, noms in llistes.items() if noms]

    def informe_per_slots(self, matriu_costos: dict, dies_utilitzar: list[str]) -> list[dict]:
        """Per cada dia i hora, les sessions òptimes, bones i acceptables de cada nivell."""
        sessions_problematiques = set()
        for _, info in matriu_costos.items():
            slots_viables = 0
            for info_cost in info["slots"].values():
                num_conflictes = (
                    info_cost.get("cost_substitucions", 0)
                    + info_cost.get("cost_abans", 0)
                    + info_cost.get("cost_despres", 0)
                )
                te_no_treballa = info_cost.get("cost_no_treballa", 0) > 0
                if info_cost["cost_total"] == 0 or (num_conflictes <= 2 and not te_no_treballa):
                    slots_viables += 1
            if slots_viables <= 2:
                sessions_problematiques.add(info.get("label", "(sense nom)"))

        hores_considerades = []
        for hora in self.hores_examen:
            for hora_real in self._get_hores_ocupades(hora):
                if hora_real not in hores_considerades:
                    hores_considerades.append(hora_real)

        slots_disponibilitat = {
            f"{dia}_{hora}": {"optimes": [], "bones": [], "acceptables": []}
            for dia in dies_utilitzar
            for hora in hores_considerades
        }

        for _, info in matriu_costos.items():
            nom_curt = info.get("label", "(sense nom)")
            for slot_key, info_cost in info["slots"].items():
                dia, _ = slot_key.split("_", 1)
                per_hora = info_cost.get("per_hour") or {}
                if not per_hora:
                    per_hora = {info_cost.get("hora"): info_cost}

                for hora_real, info_hora in per_hora.items():
                    dest_key = f"{dia}_{hora_real}"
                    if dest_key not in slots_disponibilitat:
                        continue
                    cost = info_hora["cost_total"]
                    entrada = {
                        "label": nom_curt,
                        "curs": info.get("curs"),
                        "details": self._detalls(
                            subst=sorted(set(info_hora.get("subs_detalls", []))),
                            abans=sorted(set(info_hora.get("abans_professors", []))),
                            despres=sorted(set(info_hora.get("despres_professors", []))),
                            no_treballa=sorted(set(info_hora.get("no_treballa_professors", []))),
                        ),
                    }
                    num_conflictes = (
                        info_hora.get("cost_substitucions", 0)
                        + info_hora.get("cost_abans", 0)
                        + info_hora.get("cost_despres", 0)
                    )
                    te_no_treballa = info_hora.get("cost_no_treballa", 0) > 0
                    if cost == 0:
                        slots_disponibilitat[dest_key]["optimes"].append(entrada)
                    elif num_conflictes <= 2 and not te_no_treballa:
                        slots_disponibilitat[dest_key]["bones"].append(entrada)
                    elif num_conflictes == 3 and not te_no_treballa and nom_curt in sessions_problematiques:
                        slots_disponibilitat[dest_key]["acceptables"].append(entrada)

        def del_nivell(llista, nivell):
            return [
                {"label": e["label"], "details": e["details"]}
                for e in sorted((e for e in llista if e["curs"] == nivell), key=lambda e: e["label"])
            ]

        informe = []
        for dia in dies_utilitzar:
            slots = []
            for hora in hores_considerades:
                franja = slots_disponibilitat[f"{dia}_{hora}"]
                nivells = []
                for nivell in self.nivells_actius:
                    grups = {categoria: del_nivell(franja[categoria], nivell) for categoria in franja}
                    if any(grups.values()):
                        nivells.append({"nivell": nivell, **grups})
                slots.append({"hora": hora, "nivells": nivells})
            informe.append({"dia": dia, "slots": slots})
        return informe

    def informe_per_sessio(self, matriu_costos: dict, dies_utilitzar: list[str]) -> list[dict]:
        """Per cada agrupació, totes les franges amb el cost i qui hi té conflicte."""

        def emoji(info_cost):
            num_conf = (
                info_cost.get("cost_substitucions", 0)
                + info_cost.get("cost_abans", 0)
                + info_cost.get("cost_despres", 0)
            )
            te_no_treballa = info_cost.get("cost_no_treballa", 0) > 0
            if te_no_treballa or num_conf > 3:
                return "🔴"
            if num_conf == 0:
                return "✅"
            if num_conf == 3:
                return "🔶"
            return "🟡"

        informe = []
        for _, info in matriu_costos.items():
            profs = sorted(
                {
                    ex.get("titular")
                    for s in info.get("item", {}).get("sessions", [])
                    for ex in s.get("examens", [])
                    if ex.get("titular")
                }
            )
            files = []
            for dia in dies_utilitzar:
                for hora in self.hores_examen:
                    if self._slot_bloquejat(hora):
                        continue
                    info_cost = info["slots"].get(f"{dia}_{hora}")
                    if not info_cost:
                        continue
                    for hora_real, info_hora in (info_cost.get("per_hour") or {}).items():
                        files.append(
                            {
                                "emoji": emoji(info_hora),
                                "dia": dia,
                                "hora": hora_real,
                                "cost": info_hora.get("cost_total", 0),
                                "subs": info_hora.get("cost_substitucions", 0),
                                "abans": info_hora.get("cost_abans", 0),
                                "despres": info_hora.get("cost_despres", 0),
                                "no_treballa": info_hora.get("cost_no_treballa", 0),
                                "detalls": self._detalls(
                                    subst=sorted(set(info_hora.get("subs_professors", []))),
                                    abans=sorted(set(info_hora.get("abans_professors", []))),
                                    despres=sorted(set(info_hora.get("despres_professors", []))),
                                    no_treballa=sorted(set(info_hora.get("no_treballa_professors", []))),
                                    zona=sorted(set(info_hora.get("zona_professors", []))),
                                ),
                            }
                        )
            informe.append({"titol": info.get("label"), "professors": profs, "files": files})
        return informe

    def informe_professors_per_slot(self, dies_utilitzar: list[str], *, aplicar_abreviatura_grup) -> list[dict]:
        """Per cada hora d'examen, els professors disponibles (activitat sense grup: guàrdia,
        CD, reunió...) i els alliberats (classe d'un nivell actiu). No hi surten els que tenen
        classe d'altres nivells ni els que no tenen activitat."""
        informe = []
        for dia in dies_utilitzar:
            dia_horari_prof = dia_nom_per_horari(dia)
            hores = []
            for hora in self.hores_examen:
                if self._slot_bloquejat(hora):
                    continue
                for hora_real in self._get_hores_ocupades(hora):
                    disponibles = []
                    alliberats = []
                    for prof, horari in self.horaris_professors.items():
                        dia_rec = horari.get(normalitzar_dia(dia_horari_prof), {})
                        act = dia_rec.get(hora_real) if dia_rec else None
                        if not act:
                            continue
                        grup = (act.get("grup") or "").strip()
                        assig = (act.get("assignatura") or "").strip()
                        nivell = self.nivells_dels_grups.nivell(grup, entre=self.nivells_actius)
                        if grup:
                            grup = aplicar_abreviatura_grup(grup)
                        if nivell:
                            # Els franges vàlids es defineixen per hora d'inici (🟦), no per hora interna.
                            # Si el bloc comença a les 09:15 i dura 2h, la 10:15 ha de mantenir el mateix filtre.
                            if not es_slot_valid_per_nivell(nivell, dia_horari_prof, hora, self.restriccions):
                                continue
                            alliberats.append({"professor": prof, "assignatura": assig, "grup": grup})
                        elif not grup and assig:
                            disponibles.append({"professor": prof, "assignatura": assig, "grup": ""})
                    hores.append(
                        {
                            "hora": hora_real,
                            "disponibles": sorted(disponibles, key=_text_professor),
                            "alliberats": sorted(alliberats, key=_text_professor),
                        }
                    )
            informe.append({"dia": dia, "hores": hores})
        return informe

    def _etiqueta_item(self, item: dict) -> str:
        return item.get("nom", "group")
