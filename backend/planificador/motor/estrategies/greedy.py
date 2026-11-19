"""Greedy: intents amb barreja acumulada i atzar global injectable."""

from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass

from planificador.compartit.missatges import missatge
from planificador.motor.construccio import particio
from planificador.motor.estrategies.base import ResultatCerca
from planificador.motor.model import descongela
from planificador.motor.sortida import estadistiques_generacio, horari_intent_greedy


@dataclass
class ResultatGreedy(ResultatCerca):
    # Cada intent ja ha passat pel cost mostrat. Es conserva el document del
    # guanyador (o de l'últim fallit), amb les seves anàlisis i estadístiques.
    horari: dict | None = None


class Greedy:
    id = "v2"

    def cerca(self, problema, politiques, cost_cerca, parametres, pressupost, rng):
        items = particio(problema, politiques)
        ordre = [descongela(it.dades) for it in items]
        # Identitats estables entre intents; la sortida copia les sessions i l'anàlisi.
        sessions_sortida = {it.id: tuple(e.a_diccionari() for e in it.examens) for it in items}
        capacitat = len(problema.franges)
        for nivell, nombre in Counter(it.get("curs") for it in ordre).items():
            if nombre > capacitat:
                return ResultatGreedy(
                    None,
                    False,
                    None,
                    items=items,
                    horari={
                        "dies": [],
                        "metadata": {
                            "viable": False,
                            "error": missatge("capacitat_nivell", nivell=nivell, count=nombre, hores=capacitat),
                            "motor": "v2-intents",
                        },
                    },
                )
        maxim = parametres.get("max_intents_validacio", 250)
        estrategia = parametres.get("estrategia", "ponderada")
        seguiment = parametres.get("track_intents", False)
        millor, minim, intents, registre = None, float("inf"), [], []
        pressupost.inicia()
        aturada = None
        for i in range(maxim):
            if i > 0 and pressupost.temps_esgotat():
                aturada = "temps"
                registre.append(
                    f"⏱️ Límit de temps ({pressupost.segons} s): s'han fet {i} intents dels {maxim} demanats"
                )
                break
            assignacio = self._intent(problema, politiques, cost_cerca, ordre, estrategia, rng)
            horari = horari_intent_greedy(assignacio, items, problema, cost_cerca.disponibilitat, sessions_sortida)
            horari["metadata"].update(estadistiques_generacio(horari))
            info = cost_cerca.intent(horari)
            meta = horari["metadata"]
            meta.update(cost_total=info.get("cost_total", 0), cost_breakdown=info.get("cost_breakdown", {}))
            complet = meta["total_sessions"] == len(problema.examens)
            if complet and meta["cost_total"] < minim:
                minim = meta["cost_total"]
                millor = deepcopy((horari, assignacio))
                if minim == 0:
                    break
            if seguiment:
                intents.append(
                    {
                        "intent": i + 1,
                        "cost": meta.get("cost_total", 0),
                        "valid": complet,
                        **{
                            clau: meta.get(clau)
                            for clau in (
                                "total_sessions",
                                "total_substitucions",
                                "professors_abans",
                                "professors_despres",
                            )
                        },
                    }
                )
        horari, assignacio = millor or (horari, assignacio)
        return ResultatGreedy(
            assignacio,
            millor is not None,
            aturada,
            traça=intents,
            registre=registre,
            cost=horari["metadata"]["cost_total"],
            items=items,
            horari=horari,
        )

    def _intent(self, problema, politiques, cost_cerca, ordre, estrategia, rng):
        franges = {f.clau: f for f in problema.franges}
        sessions_franja = {clau: [] for clau in franges}
        rng.shuffle(ordre)
        dures = cost_cerca.restriccions.get("restriccions_dures", {})
        fixos, flexibles = [], []
        for item in ordre:
            # Cerca pel nom complet i presència de dia O hora, sense mirar-ne
            # el pes, exactament com feia el motor antic.
            fix = any(
                dures.get("assignatures_dia_fix", {}).get(s["nom"])
                or dures.get("assignatures_hora_fix", {}).get(s["nom"])
                for s in item["sessions"]
            )
            (fixos if fix else flexibles).append(item)
        comptats_franja = defaultdict(set)
        sessions_per_dia, sessions_per_data = defaultdict(list), defaultdict(list)
        assignacio = {}
        for item in fixos + flexibles:
            millor, minim, millors_comptats = None, float("inf"), None
            candidates = list(problema.franges)
            if estrategia != "greedy":
                rng.shuffle(candidates)
            ubicacions = [
                (entrada["sessio"], clau) for clau, sessions in sessions_franja.items() for entrada in sessions
            ]
            for ubicacio in candidates:
                resultat = cost_cerca.item(
                    item,
                    ubicacio,
                    sessions_per_data[ubicacio.prefix],
                    sessions_franja[ubicacio.clau],
                    sessions_per_dia,
                    ubicacions,
                    comptats_franja[ubicacio.clau],
                    politiques,
                )
                if resultat is not None and resultat[0] < minim:
                    minim, millors_comptats = resultat
                    millor = ubicacio
            if millor:
                assignacio[item["item_id"]] = millor
                comptats_franja[millor.clau] = millors_comptats
                for sessio in item["sessions"]:
                    sessions_franja[millor.clau].append(
                        {"sessio": sessio, "nom": sessio["nom"], "curs": sessio["curs"]}
                    )
                    sessions_per_dia[millor.dia].append(sessio)
                    sessions_per_data[millor.prefix].append(sessio)
        return assignacio
