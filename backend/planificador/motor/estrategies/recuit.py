"""Recuit amb la trajectòria històrica, l'atzar global i el rellotge injectable."""

import math
import re
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass

from planificador.compartit.constants import DEFAULT_SA_PARAMS
from planificador.compartit.missatges import missatge
from planificador.compartit.normalitzacio import normalitzar_dia
from planificador.motor.construccio import particio
from planificador.motor.cost_cerca import SolucioRecuit
from planificador.motor.estrategies.base import ResultatCerca
from planificador.motor.regles import (
    es_slot_valid_per_nivell,
    valor_restriccio,
    viola_restriccio_dia_hora_fixos,
)

SOLUCIONS_INICIALS_A_COMPARAR = 10
REINICIS = 12
ITERACIONS_SENSE_MILLORA = 2000


@dataclass
class ResultatRecuit(ResultatCerca):
    error: dict | None = None
    violacions: list | None = None


class Recuit:
    id = "v3"

    def cerca(self, problema, politiques, cost_cerca, parametres, pressupost, rng):
        self.problema, self.politiques = problema, politiques
        self.cost_cerca, self.pressupost, self.rng = cost_cerca, pressupost, rng
        # El termini compta des de l'entrada, amb la preparació dins (com al backtracking).
        pressupost.inicia()
        self.registre = []
        self.franges = list(problema.franges)
        self.items = particio(problema, politiques)
        self.item_infactible = None
        self.aturat_pel_temps = False
        self.error = None
        for nom, defecte in DEFAULT_SA_PARAMS.items():
            setattr(self, nom, parametres.get(nom, defecte))
        if not self.franges or not problema.examens:
            self.error = {"cost_total": 999999, "error": missatge("sense_dades")}
            return self._resultat(None)
        detalls = self._fixos_sense_hores()
        if detalls:
            self.error = {
                "viable": False,
                "error": missatge("fixos_sense_hores"),
                "detalls": detalls[:10],
                "motor": "v3-sa",
            }
            return self._resultat(None)
        self.registre.append("🔗 Pre-agrupant sessions (SA)...")
        # El recompte és per nivell de partició, abans de les col·lisions de noms.
        if any(n > len(self.franges) for n in Counter(it.examens[0].curs for it in self.items).values()):
            self.error = {"viable": False, "error": missatge("capacitat_exhaurida"), "motor": "v3-sa"}
            return self._resultat(None)
        cost_cerca.prepara(self.items, politiques)
        solucio = self._executa(reinicis=parametres.get("reinicis"))
        if solucio is None and self.aturat_pel_temps:
            # Tallada pel temps: cap causa demostrada, com al backtracking.
            self.error = {
                "viable": False,
                "error": missatge("cerca_tallada_temps", segons=pressupost.segons),
                "motiu_aturada": "temps",
                "motor": "v3-sa",
            }
        elif solucio is None:
            incompatibilitats = []
            if self.item_infactible:
                nom = self.item_infactible.id or str(self.item_infactible)
                causa = cost_cerca.causa_infactible(self.item_infactible)
                incompatibilitats = [
                    missatge("examen_sense_hora_causa", nom=nom, causa=causa)
                    if causa
                    else missatge("examen_sense_hora_motor", nom=nom)
                ]
            self.error = {
                "viable": False,
                "error": missatge("sense_hora_compatible"),
                "incompatibilitats": incompatibilitats,
                "motor": "v3-sa",
            }
        return self._resultat(solucio)

    def _resultat(self, solucio):
        # Trobar una solució del recuit no garanteix col·locar totes les
        # sessions: els noms d'ítem repetits encara es trepitgen, com al motor antic.
        per_id = {item.id: item for item in self.items}
        complet = solucio is not None and sum(
            len(per_id[identificador].examens) for identificador in solucio.assignacions
        ) == len(self.problema.examens)
        resultat = ResultatCerca(
            solucio.assignacions if solucio else None,
            complet,
            "temps" if self.aturat_pel_temps else None,
            registre=self.registre,
            cost=solucio.cost if solucio else None,
            items=self.items,
        )
        return ResultatRecuit(**vars(resultat), error=self.error, violacions=solucio.violacions if solucio else [])

    def _fixos_sense_hores(self):
        dures = self.cost_cerca.restriccions.get("restriccions_dures", {})
        dies_fixos = dures.get("assignatures_dia_fix", {}) or {}
        hores_fixes = dures.get("assignatures_hora_fix", {}) or {}
        franges_dia = {(normalitzar_dia(f.dia), f.hora) for f in self.franges}
        franges_iso = {(f.data_iso, f.hora) for f in self.franges if f.data_iso}
        dies = {normalitzar_dia(f.dia) for f in self.franges}
        dates = {f.data_iso for f in self.franges if f.data_iso}
        hores = {f.hora for f in self.franges}
        detalls = []
        for examen in self.problema.examens:
            sessio = examen.a_diccionari()
            dia, hora = valor_restriccio(dies_fixos, sessio), valor_restriccio(hores_fixes, sessio)
            if dia:
                es_iso = bool(re.match(r"^\d{4}-\d{2}-\d{2}$", str(dia)))
                dia = dia if es_iso else normalitzar_dia(dia)
                if dia not in (dates if es_iso else dies):
                    detalls.append(missatge("fixat_dia_no_disponible", nom=examen.nom, dia=dia))
                    continue
                if hora and (dia, hora) not in (franges_iso if es_iso else franges_dia):
                    detalls.append(missatge("fixat_slot_no_disponible", nom=examen.nom, dia=dia, hora=hora))
            elif hora and hora not in hores:
                detalls.append(missatge("fixat_hora_no_disponible", nom=examen.nom, hora=hora))
        return detalls

    def _compatible(self, solucio, item, franja, precalcul=None):
        return self.cost_cerca.compatible(solucio, item, franja, precalcul)

    def _precomputa(self, solucio, exclou):
        return self.cost_cerca.precomputa(solucio, exclou)

    def calcular_cost(self, solucio):
        return self.cost_cerca.total(solucio)

    def _detecta_congelats(self):
        """Pre-computa els ítems que tenen exactament 1 slot compatible (fixats per restricció).
        Guarda l'únic slot per als ítems congelats per evitar recalcular-lo després."""
        sol_buida = SolucioRecuit(assignacions={})
        self.items_mobils = []
        self.items_congelats_ids = set()
        self.franja_congelada: dict = {}
        for it in self.items:
            compat = [s for s in self.franges if self._compatible(sol_buida, it, s)]
            if len(compat) <= 1:
                self.items_congelats_ids.add(it.id)
                self.franja_congelada[it.id] = compat[0] if compat else None
            else:
                self.items_mobils.append(it)

    def _precalcula_candidates(self):
        """Pre-filtra els slots estàticament vàlids per a cada ítem mòbil (s'executa una vegada)."""
        restriccions = self.cost_cerca.restriccions
        self.candidates = {}
        per_preparar = self.items_mobils or self.items
        for it in per_preparar:
            candidats = []
            for s in self.franges:
                passes = True
                for sess in it.examens:
                    s_dict = self.cost_cerca.examens[sess.id]
                    if not es_slot_valid_per_nivell(
                        s_dict.get("curs", ""), s.dia, s.hora, restriccions, data_iso=s.data_iso or ""
                    ):
                        passes = False
                        break
                    if viola_restriccio_dia_hora_fixos(s_dict, s.dia, s.hora, restriccions, s.data_iso or ""):
                        passes = False
                        break
                if passes:
                    candidats.append(s)
            self.candidates[it.id] = candidats if candidats else self.franges

    def _executa(self, amb_registre=True, reinicis=None):
        """Executa l'algorisme de Simulated Annealing amb múltiples reinicis."""
        if reinicis is None:
            reinicis = REINICIS
        self._detecta_congelats()
        n_con = len(self.items_congelats_ids)
        n_mob = len(self.items_mobils)
        if amb_registre:
            self.registre.append(
                f"🔥 Iniciant Simulated Annealing ({reinicis} reinicis)... [{n_con} fixats, {n_mob} mòbils]"
            )

        # Cas ràpid: sense ítems mòbils → construir solució directament dels slots ja calculats
        if n_mob == 0:
            if amb_registre:
                self.registre.append("   ⚡ Tot fixat: construint solució directament (sense SA)")
            sol = SolucioRecuit(assignacions={})
            for it in self.items:
                franja = self.franja_congelada.get(it.id)
                if franja is None:
                    if amb_registre:
                        self.registre.append(f"   ✗ Infactible: cap slot per a '{it.id}'")
                    self.item_infactible = it
                    return None
                # Comprovar restriccions dures contra els ítems ja assignats
                if not self._compatible(sol, it, franja):
                    if amb_registre:
                        self.registre.append(f"   ✗ Infactible: '{it.id}' a {franja.clau} viola restricció dura")
                    self.item_infactible = it
                    return None
                sol.assignacions[it.id] = franja
            sol.cost, sol.violacions = self.calcular_cost(sol)
            return sol

        millor_global = None

        # Pre-filtrar slots vàlids per a cada ítem (evita escanar tots els slots cada iteració)
        self._precalcula_candidates()

        # Adaptar paràmetres a la mida del problema
        if n_mob <= 2:
            iteracions_per_temperatura = min(self.iteracions_per_temperatura, 30)
            maxim_iteracions = min(self.max_iteracions, 8000)
            reinicis = 1
        elif n_mob <= 5:
            iteracions_per_temperatura = min(self.iteracions_per_temperatura, 80)
            maxim_iteracions = min(self.max_iteracions, 30000)
        else:
            iteracions_per_temperatura = self.iteracions_per_temperatura
            maxim_iteracions = self.max_iteracions

        self.aturat_pel_temps = False
        for reinici in range(reinicis):
            if reinici > 0 and self.pressupost.temps_transcorregut_esgotat():
                self.aturat_pel_temps = True
                if amb_registre:
                    self.registre.append(f"   ⏱️ Temps esgotat després de {reinici} reinicis")
                break
            if reinici > 0 and amb_registre:
                self.registre.append(f"\n🔄 Reinici {reinici + 1}/{reinicis}...")

            # Solució inicial
            sa = self._solucio_inicial()
            if sa is None:
                if amb_registre:
                    self.registre.append("   ⚠️ No s'ha pogut generar solució inicial")
                continue

            ms = deepcopy(sa)

            if amb_registre:
                self.registre.append(f"   Solució inicial: cost={sa.cost:.2f}")

            # Amb un sol ítem mòbil no cal recuit: es proven totes les seves franges
            # (abans es quedava la millor de les solucions inicials, triades a l'atzar).
            if n_mob <= 1:
                millor_global = self._millor_franja_de_l_unic_mobil(ms)
                if amb_registre:
                    self.registre.append(
                        f"   ✨ {n_mob} mòbil: totes les franges provades, cost={millor_global.cost:.2f}, saltant SA"
                    )
                break

            t, it = self.temperatura_inicial, 0
            sense_millora = 0

            while (
                t > self.temperatura_final
                and it < maxim_iteracions
                and not self.pressupost.temps_transcorregut_esgotat()
            ):
                for _ in range(iteracions_per_temperatura):
                    if self.pressupost.temps_transcorregut_esgotat():
                        self.aturat_pel_temps = True
                        break
                    sv = self._vei(sa)

                    # Probabilitat d'acceptació
                    if sv.cost < sa.cost:
                        prob = 1.0
                    elif t > 0:
                        prob = math.exp(-(sv.cost - sa.cost) / t)
                    else:
                        prob = 0.0

                    if self.rng.random() < prob:
                        sa = sv
                        if sa.cost < ms.cost:
                            ms = deepcopy(sa)
                            sense_millora = 0
                            if amb_registre:
                                self.registre.append(f"   ✅ Nova millor: cost={ms.cost:.2f} (T={t:.2f})")
                        else:
                            sense_millora += 1
                    else:
                        sense_millora += 1

                    it += 1

                t *= self.factor_refredament

                # Early stopping: només si estem a temperatura baixa (explotació) i cost raonable
                # Condició t < 100 evita tallar l'exploració a T alta (on la solució no ha convergit)
                if sense_millora > ITERACIONS_SENSE_MILLORA and ms.cost < 100000 and t < 100:
                    if amb_registre:
                        self.registre.append(f"   ⚡ Early stopping: {sense_millora} iter sense millora, T={t:.2f}")
                    break

            if amb_registre:
                self.registre.append(f"   Reinici {reinici + 1}: {it} iteracions, cost={ms.cost:.2f}")

            # Actualitzar millor global. Es fan tots els reinicis, encara que
            # el primer ja sigui viable: cada reinici parteix d'una solució
            # diferent i és la manera d'escapar d'un mínim local.
            if millor_global is None or ms.cost < millor_global.cost:
                millor_global = deepcopy(ms)

        if amb_registre and millor_global:
            self.registre.append(f"✅ SA completat. Millor cost: {millor_global.cost:.2f}")

        return millor_global

    def _millor_franja_de_l_unic_mobil(self, solucio):
        """La solució més barata movent només l'únic ítem mòbil per totes les franges
        compatibles; en cas d'empat, es queda la de partida."""
        if len(self.items_mobils) != 1:
            return solucio
        item = self.items_mobils[0]
        base = SolucioRecuit({k: v for k, v in solucio.assignacions.items() if k != item.id})
        millor = solucio
        for franja in self.franges:
            if self._compatible(base, item, franja):
                candidata = SolucioRecuit({**base.assignacions, item.id: franja})
                candidata.cost, candidata.violacions = self.calcular_cost(candidata)
                if candidata.cost < millor.cost:
                    millor = candidata
        return millor

    def _solucio_inicial(self):
        # Heurística: prioritzar ítems amb menys slots compatibles
        base = SolucioRecuit(assignacions={})
        recomptes = {}
        for it in self.items:
            recomptes[it.id] = len([s for s in self.franges if self._compatible(base, it, s)])
            if recomptes[it.id] == 0:
                self.item_infactible = it
                return None

        ordenats = sorted(self.items, key=lambda it: recomptes.get(it.id, 0))
        # Es parteix de la més barata d'unes quantes solucions viables (no de la
        # primera que surt): en un problema ajustat, el recuit difícilment surt
        # d'un mal punt de partida.
        millor = None
        viables = 0
        for _ in range(self.intents_solucio_inicial):
            if viables >= SOLUCIONS_INICIALS_A_COMPARAR:
                break
            sol = SolucioRecuit(assignacions={})
            # Aleatorietat controlada dins el mateix nombre de compatibilitats
            grups = defaultdict(list)
            for it in ordenats:
                grups[recomptes[it.id]].append(it)
            ordre = []
            for k in sorted(grups.keys()):
                grup = grups[k]
                self.rng.shuffle(grup)
                ordre.extend(grup)

            ok = True
            for it in ordre:
                compat = [s for s in self.franges if self._compatible(sol, it, s)]
                if compat:
                    sol.assignacions[it.id] = self.rng.choice(compat)
                else:
                    self.item_infactible = it
                    ok = False
                    break
            if ok:
                sol.cost, sol.violacions = self.calcular_cost(sol)
                viables += 1
                if millor is None or sol.cost < millor.cost:
                    millor = sol
        return millor

    def _vei(self, sol):
        """Genera una solució veïna movent o intercanviant items.
        IMPORTANT: Mai viola la restricció de nivell (dos items del mateix nivell al mateix slot).
        Usa DELTA COST: només recalcula els slots afectats pel moviment.
        """
        nv = SolucioRecuit(
            assignacions=dict(sol.assignacions),
            cost=sol.cost,
            cost_per_franja=dict(sol.cost_per_franja),
            cost_global=sol.cost_global,
            violacions=[],  # Es reconstruiran
        )
        if not self.items:
            return nv

        franges_afectades = set()  # Slots que cal recalcular
        moviment_fet = False

        # Tipus de moviment aleatori: moure (70%) o intercanviar (30%)
        moviment = self.rng.choice(
            [
                "moure",
                "moure",
                "moure",
                "moure",
                "moure",
                "moure",
                "moure",
                "intercanviar",
                "intercanviar",
                "intercanviar",
            ]
        )

        per_moviment = self.items_mobils or self.items
        if moviment == "intercanviar" and len(per_moviment) >= 2:
            # S'intercanvien dos ítems dels mateixos nivells: amb nivells
            # diferents, quasi sempre quedarien dos exàmens del mateix nivell
            # a la mateixa franja i el moviment es descartaria.
            item1 = self.rng.choice(per_moviment)
            nivells1 = {s.curs for s in item1.examens}
            parelles = [it for it in per_moviment if it is not item1 and {s.curs for s in it.examens} == nivells1]
            item2 = (
                self.rng.choice(parelles)
                if parelles
                else self.rng.choice([it for it in per_moviment if it is not item1])
            )
            franja1 = nv.assignacions.get(item1.id)
            franja2 = nv.assignacions.get(item2.id)

            if franja1 and franja2 and franja1 != franja2:
                nv.assignacions[item1.id] = franja2
                nv.assignacions[item2.id] = franja1
                precalcul1 = self._precomputa(nv, item1.id)
                precalcul2 = self._precomputa(nv, item2.id)
                if not self._compatible(nv, item1, franja2, precalcul=precalcul1) or not self._compatible(
                    nv, item2, franja1, precalcul=precalcul2
                ):
                    nv.assignacions[item1.id] = franja1
                    nv.assignacions[item2.id] = franja2
                    moviment = "moure"
                else:
                    franges_afectades.add(franja1.clau)
                    franges_afectades.add(franja2.clau)
                    moviment_fet = True
            else:
                moviment = "moure"

        if moviment == "moure" and not moviment_fet:
            it = self.rng.choice(per_moviment)
            franja_origen = sol.assignacions.get(it.id)
            candidats = self.candidates.get(it.id, self.franges)
            precalcul = self._precomputa(nv, it.id)
            compat = [s for s in candidats if self._compatible(nv, it, s, precalcul=precalcul)]
            if compat:
                franja_desti = self.rng.choice(compat)
                nv.assignacions[it.id] = franja_desti
                if franja_origen:
                    franges_afectades.add(franja_origen.clau)
                franges_afectades.add(franja_desti.clau)
                moviment_fet = True

        return self.cost_cerca.delta(sol, nv, franges_afectades if moviment_fet else set())
