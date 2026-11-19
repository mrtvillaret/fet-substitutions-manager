"""Matriu de disponibilitat i tres informes textuals compatibles amb la pantalla.

Els separadors, els salts, els emojis i l'ordre són part del contracte:
la pantalla interpreta aquests textos amb expressions regulars.
"""

import re as _re_iso

from planificador.compartit.normalitzacio import dia_nom_per_horari, format_dia_label, normalitzar_dia
from planificador.motor.avaluador import cost_sessio
from planificador.motor.compatibilitat import COST_ZONA_EXAMEN
from planificador.motor.construccio import particio_antiga
from planificador.motor.disponibilitat import Disponibilitat
from planificador.motor.durades import examen_motor, hores_ocupades, per_nivell
from planificador.motor.model import descongela
from planificador.motor.regles import calcular_penalitzacio_professors_dies_item, es_slot_valid_per_nivell


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

    def get_durada_per_nivell(self, nivell):
        return per_nivell(nivell, self.problema.alliberaments, self.durada_titular)

    def get_durada_examen_per_sessio_key(self, nom, nivell):
        return examen_motor(nom, self.problema.durades_examen, self.problema.durades_vigilancia, self.durada_titular)

    def _get_hores_ocupades(self, hora, nivell=None):
        return hores_ocupades(hora, self.problema.graella, self.get_durada_per_nivell(nivell))

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
            "per_slots": self.generar_informe_per_slots(matriu, dies),
            "per_sessio": self.generar_informe_disponibilitat(matriu, dies),
            "professors_slot": self.generar_informe_professors_per_slot(
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

        # Soft cost per conflictes a la zona examen (sense titular): guia el greedy cap a franges nets
        zona_examen_count = len({(i["professor"], i.get("hora", hora)) for i in analisi.get("zona_examen", [])})
        cost_zona_examen = zona_examen_count * COST_ZONA_EXAMEN
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
            "cost_total": resultat_cost["cost_total"] + cost_zona_examen,
            "professors_estrictes_violats": resultat_cost.get("professors_estrictes_violats", []),
        }

    def _slot_bloquejat(self, dia: str, hora: str, nivell: str | None = None) -> bool:
        """Retorna True si el slot no pot encabir la durada completa."""
        durada = self.get_durada_per_nivell(nivell) if nivell else self.durada_titular
        if durada > 1:
            hores = self._get_hores_ocupades(hora, nivell)
            if len(hores) < durada:
                return True
        return False

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
                    if self._slot_bloquejat(dia_horari, hora, curs):
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
                    hores_slot = self._get_hores_ocupades(hora, curs)
                    # Un examen que dura més que la durada general s'analitza sencer
                    durada_item = max(
                        (self.get_durada_examen_per_sessio_key(s.get("nom"), curs) for s in item.get("sessions", [])),
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
                        for hora_real in hores_slot:
                            info_cost = self._calcular_cost_sessio(
                                sessio, dia_horari, hora_real, hores_override=[hora_real], data_iso=_data_iso_calc
                            )
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
                    p_limit = calcular_penalitzacio_professors_dies_item(
                        item, dia_horari, {dia_horari: item.get("sessions", [])}, self.restriccions
                    )
                    if p_limit:
                        total["cost_total"] += p_limit
                    total["per_hour"] = per_hora
                    matriu_costos[nom_item]["slots"][slot_key] = total

        return matriu_costos

    def generar_informe_per_slots(self, matriu_costos: dict, dies_utilitzar: list[str]) -> str:
        """Genera informe invertit: per cada slot, quines sessions són viables."""
        linies = []
        linies.append("=" * 85)
        linies.append("🕐 INFORME DE SESSIONS DISPONIBLES PER SLOT")
        linies.append("=" * 85)
        linies.append("")
        linies.append("Aquest informe mostra per cada dia/hora:")
        linies.append("  • Òptimes: Cap conflicte (cost 0)")
        linies.append("  • Conflictes mínims: ≤2 conflictes")
        linies.append("  • Sessions problemàtiques: També mostra ≤3 conflictes")
        linies.append("")

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

        linies.append(
            f"⚠️  Sessions problemàtiques detectades ({len(sessions_problematiques)}): {', '.join(sorted(sessions_problematiques))}"
        )
        linies.append("")

        hores_considerades = []
        for hora in self.hores_examen:
            for hora_real in self._get_hores_ocupades(hora):
                if hora_real not in hores_considerades:
                    hores_considerades.append(hora_real)

        slots_disponibilitat = {}
        for dia in dies_utilitzar:
            for hora in hores_considerades:
                slot_key = f"{dia}_{hora}"
                slots_disponibilitat[slot_key] = {
                    "dia": dia,
                    "hora": hora,
                    "optimes": [],
                    "bones": [],
                    "acceptables": [],
                    "conflictes": [],
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
                        "nom": nom_curt,
                        "cost": cost,
                        "subs": info_hora.get("cost_substitucions", 0),
                        "abans": info_hora.get("cost_abans", 0),
                        "despres": info_hora.get("cost_despres", 0),
                        "no_treballa": info_hora.get("cost_no_treballa", 0),
                        "curs": info.get("curs"),
                        "subs_detalls": sorted(set(info_hora.get("subs_detalls", []))),
                        "abans_professors": info_hora.get("abans_professors", []),
                        "despres_professors": info_hora.get("despres_professors", []),
                        "no_treballa_professors": info_hora.get("no_treballa_professors", []),
                    }

                    num_conflictes = entrada["subs"] + entrada["abans"] + entrada["despres"]
                    te_no_treballa = entrada["no_treballa"] > 0
                    es_problematica = nom_curt in sessions_problematiques

                    if cost == 0:
                        slots_disponibilitat[dest_key]["optimes"].append(entrada)
                    elif num_conflictes <= 2 and not te_no_treballa:
                        slots_disponibilitat[dest_key]["bones"].append(entrada)
                    elif num_conflictes == 3 and not te_no_treballa and es_problematica:
                        slots_disponibilitat[dest_key]["acceptables"].append(entrada)

        def _formata_entrada(entrada: dict) -> str:
            parts = []
            subs_detalls = entrada.get("subs_detalls", [])
            if subs_detalls:
                parts.append(f"subst: {' | '.join(subs_detalls)}")
            abans = sorted(set(entrada.get("abans_professors", [])))
            if abans:
                parts.append(f"abans: {', '.join(abans)}")
            despres = sorted(set(entrada.get("despres_professors", [])))
            if despres:
                parts.append(f"despres: {', '.join(despres)}")
            no_treballa = sorted(set(entrada.get("no_treballa_professors", [])))
            if no_treballa:
                parts.append(f"no_treballa: {', '.join(no_treballa)}")
            if parts:
                return f"{entrada.get('nom')} [{'; '.join(parts)}]"
            return entrada.get("nom")

        for dia in dies_utilitzar:
            linies.append("=" * 85)
            linies.append(f"📅 {format_dia_label(dia).upper()}")
            linies.append("=" * 85)
            linies.append("")
            for hora in hores_considerades:
                slot_key = f"{dia}_{hora}"
                info_franja = slots_disponibilitat[slot_key]

                linies.append(f"⏰ {hora}")
                linies.append("─" * 85)

                sessions_per_curs = {}
                for nivell in self.nivells_actius:
                    sessions_per_curs[nivell] = {
                        "optimes": sorted(
                            [s for s in info_franja["optimes"] if s["curs"] == nivell], key=lambda x: x["nom"]
                        ),
                        "bones": sorted(
                            [s for s in info_franja["bones"] if s["curs"] == nivell], key=lambda x: x["nom"]
                        ),
                        "acceptables": sorted(
                            [s for s in info_franja["acceptables"] if s["curs"] == nivell], key=lambda x: x["nom"]
                        ),
                    }

                for nivell, grups in sessions_per_curs.items():
                    if grups["optimes"] or grups["bones"] or grups["acceptables"]:
                        linies.append(f"{nivell}:")
                        if grups["optimes"]:
                            noms = ", ".join([_formata_entrada(s) for s in grups["optimes"]])
                            linies.append(f"  ✅ Òptimes: {noms}")
                        if grups["bones"]:
                            noms = ", ".join([_formata_entrada(s) for s in grups["bones"]])
                            linies.append(f"  🟡 Bones: {noms}")
                        if grups["acceptables"]:
                            noms = ", ".join([_formata_entrada(s) for s in grups["acceptables"]])
                            linies.append(f"  🔶 Acceptables: {noms}")
                linies.append("")

        return "\n".join(linies)

    def generar_informe_disponibilitat(self, matriu_costos: dict, dies_utilitzar: list[str]) -> str:
        """Informe per sessió: tots els slots amb cost/detall."""
        linies = []
        linies.append("=" * 85)
        linies.append("📊 INFORME DE DISPONIBILITAT PER AGRUPACIONS")
        linies.append("=" * 85)
        linies.append("")
        linies.append("Per cada agrupació: tots els slots ordenats per dia")
        linies.append("Emojis: ✅=0 conflictes | 🟡≤2 | 🔶=3 | 🔴>3 o prof. no treballa")
        linies.append("")

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

        for _, info in matriu_costos.items():
            linies.append(f"📝 {info.get('label')}")
            profs = set()
            for s in info.get("item", {}).get("sessions", []):
                for ex in s.get("examens", []):
                    p = ex.get("titular")
                    if p:
                        profs.add(p)
            if profs:
                linies.append("👥 Professors: " + ", ".join(sorted(profs)))
            linies.append("")
            linies.append("Dia | Hora | Cost | Subs | Abans | Després | No treb | Detalls")
            linies.append("-" * 70)
            for dia in dies_utilitzar:
                dia_horari_inf = dia_nom_per_horari(dia)
                for hora in self.hores_examen:
                    if self._slot_bloquejat(dia_horari_inf, hora):
                        continue
                    slot_key = f"{dia}_{hora}"
                    info_cost = info["slots"].get(slot_key)
                    if not info_cost:
                        continue
                    per_hora = info_cost.get("per_hour") or {}
                    for hora_real, info_hora in per_hora.items():
                        detalls = []
                        subs = info_hora.get("subs_professors", [])
                        abans = info_hora.get("abans_professors", [])
                        despres = info_hora.get("despres_professors", [])
                        no_treballa = info_hora.get("no_treballa_professors", [])
                        if subs:
                            detalls.append("Subst: " + ", ".join(sorted(set(subs))))
                        if abans:
                            detalls.append("Abans: " + ", ".join(sorted(set(abans))))
                        if despres:
                            detalls.append("Després: " + ", ".join(sorted(set(despres))))
                        if no_treballa:
                            detalls.append("No treb: " + ", ".join(sorted(set(no_treballa))))
                        det_text = " | ".join(detalls) if detalls else "cap conflicte"
                        linies.append(
                            f"{emoji(info_hora)} {format_dia_label(dia)} | {hora_real} | {info_hora.get('cost_total', 0)} | {info_hora.get('cost_substitucions', 0)} | {info_hora.get('cost_abans', 0)} | {info_hora.get('cost_despres', 0)} | {info_hora.get('cost_no_treballa', 0)} | {det_text}"
                        )
            linies.append("")

        return "\n".join(linies)

    def generar_informe_professors_per_slot(self, dies_utilitzar: list[str], *, aplicar_abreviatura_grup) -> str:
        linies = []
        linies.append("=" * 85)
        linies.append("👥 INFORME DE PROFESSORS PER SLOT (Hores d'Exàmens)")
        linies.append("=" * 85)
        linies.append("")
        linies.append("Aquest informe mostra per cada hora d'examen:")
        linies.append("  ✅ DISPONIBLES: amb activitat sense grup (Guàrdia/CD/VP/E.D./Reforç/Reunió...)")
        linies.append("  📚 ALLIBERATS: amb classe dels nivells actius (alliberats perquè els alumnes fan exàmens)")
        linies.append("(No es mostren professors amb classe d'altres nivells ni professors sense activitat)")
        linies.append("")

        for dia in dies_utilitzar:
            dia_horari_prof = dia_nom_per_horari(dia)
            linies.append(f"📅 {format_dia_label(dia)}")
            linies.append("")
            for hora in self.hores_examen:
                if self._slot_bloquejat(dia_horari_prof, hora):
                    continue
                hores_slot = self._get_hores_ocupades(hora)
                for hora_real in hores_slot:
                    linies.append(f"⏰ {hora_real}")
                    disponibles = []
                    alliberats = []
                    for prof, horari in self.horaris_professors.items():
                        dia_rec = horari.get(normalitzar_dia(dia_horari_prof), {})
                        if not dia_rec:
                            continue
                        act = dia_rec.get(hora_real)
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
                            if grup and assig:
                                alliberats.append(f"{prof} ({assig}, {grup})")
                            elif grup:
                                alliberats.append(f"{prof} ({grup})")
                            elif assig:
                                alliberats.append(f"{prof} ({assig})")
                            else:
                                alliberats.append(prof)
                        elif not grup and assig:
                            disponibles.append(f"{prof} ({assig})")
                    if not disponibles and not alliberats:
                        linies.append("(Tots els professors tenen classe d'altres nivells o no tenen activitat)")
                    else:
                        if disponibles:
                            linies.append(f"✅ DISPONIBLES ({len(disponibles)}):")
                            for p in sorted(disponibles):
                                linies.append(f"• {p}")
                        if alliberats:
                            linies.append(f"📚 ALLIBERATS ({len(alliberats)}):")
                            for p in sorted(alliberats):
                                linies.append(f"• {p}")
                    linies.append("")

        return "\n".join(linies)

    def _etiqueta_item(self, item: dict) -> str:
        return item.get("nom", "group")
