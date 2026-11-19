"""Avisos de l'editor i format de resposta; preserva el document amb extres."""

from planificador.compartit.franja import dia_de_prefix
from planificador.compartit.franja import franja as de_clau
from planificador.compartit.missatges import missatge
from planificador.compartit.normalitzacio import normalitzar_dia
from planificador.motor.avaluador import Cost
from planificador.motor.disponibilitat import Disponibilitat, analitza_motor
from planificador.motor.durades import examen_recalcul, hores_ocupades, vigilancia
from planificador.motor.model import HorariEditable, Problema, descongela
from planificador.motor.registre import IncidenciesFranja, ValidadorHorari, excessos_limit_dies, incidencies
from textos import normalitzar_hora


def conflicte_de_nivell(sessions: list) -> bool:
    """Validesa de l'editor: només més d'un ítem del mateix nivell a la franja."""
    nivell_per_item = {}
    for sessio in sessions:
        item_id = sessio.get("item_id") or sessio.get("id") or f"{sessio.get('nom')}_{sessio.get('curs')}"
        curs = sessio.get("curs", "")
        if curs and item_id not in nivell_per_item:
            nivell_per_item[item_id] = curs
    nivells = list(nivell_per_item.values())
    return len(nivells) != len(set(nivells))


def franges_editor(horari: HorariEditable, problema: Problema, disponible: Disponibilitat) -> tuple[list, bool]:
    """Anàlisi de les dues finestres, avisos per ocurrència i validesa de nivell."""
    restriccions = problema.regles.a_diccionari()
    mapa = descongela(problema.mapa_dies)
    graella = list(problema.graella)
    resultat = []
    conflicte_global = False
    for dia in horari.document.get("dies", []):
        dia_nom = dia.get("dia", "")
        dates = mapa.get(normalitzar_dia(dia_nom))
        data_iso = dia.get("data") or (dates[0] if isinstance(dates, list) else dates)
        for franja in dia.get("sessions", []):
            hora = franja.get("hora", "")
            hora_normalitzada = normalitzar_hora(hora)
            sessions = franja.get("sessions_simultanees", [])
            conflicte = conflicte_de_nivell(sessions)
            conflicte_global = conflicte_global or conflicte
            incidencies_franja = IncidenciesFranja()
            avisos_per_item = {}
            for index, sessio in enumerate(sessions):
                altres = [s for i, s in enumerate(sessions) if i != index]
                nom = sessio.get("nom")
                durada_vigilancia = vigilancia(nom, problema.durades_vigilancia, problema.durada_titular)
                durada_examen = examen_recalcul(
                    nom, problema.durades_examen, problema.durades_vigilancia, problema.durada_titular
                )
                hores_vigilancia = hores_ocupades(hora_normalitzada, graella, durada_vigilancia)
                hores_examen = hores_ocupades(hora_normalitzada, graella, durada_examen)
                analisi = disponible.analitza(
                    sessio, dia_nom, hora_normalitzada, data_iso, hores_examen, hores_vigilancia, altres
                )
                sessio["analisi"] = analisi
                incidencies_sessio = list(incidencies(analisi, hora, dia_nom, restriccions))
                for incidencia in incidencies_sessio:
                    incidencies_franja.afegeix(*incidencia)
                if incidencies_sessio:
                    avisos = [avis for _, _, _, avis, _ in incidencies_sessio]
                    for clau in (sessio.get("_uid"), sessio.get("item_id")):
                        if clau:
                            # L'última sessió amb incidències sobreescriu la clau d'ítem.
                            avisos_per_item[clau] = avisos
            avisos = incidencies_franja.avisos
            if conflicte:
                avisos.insert(0, "⚠️ CONFLICTE: Múltiples exàmens del mateix nivell!")
            resultat.append(
                {
                    "slot_key": f"{data_iso or dia_nom}_{hora}",
                    "cost": incidencies_franja.cost,
                    "breakdown": {"sessions": len(sessions)},
                    "conflicte_nivell": conflicte,
                    "avisos": avisos,
                    "item_avisos": avisos_per_item,
                }
            )
    return resultat, not conflicte_global


def finalitza_recalcul(
    horari: HorariEditable, problema: Problema, cost: Cost, disponible: Disponibilitat, avisos_config
) -> tuple[dict, dict]:
    """(Horari a desar, resposta): les metadades antigues es conserven."""
    franges, valid_editor = franges_editor(horari, problema, disponible)
    document = horari.document
    if document.get("metadata", {}).get("logs"):
        document["metadata"]["logs"] = []
    restriccions = problema.regles.a_diccionari()
    validacio = ValidadorHorari(document, restriccions, problema.no_substituir, descongela(problema.mapa_dies))
    resultat_validacio = validacio.validar()
    logs = avisos_config() + resultat_validacio.get("logs", [])
    detalls = {}
    excessos = excessos_limit_dies(document, restriccions)
    if excessos:
        detalls["limit_dies_professor"] = excessos
    info = cost.a_info()
    stats = descongela(cost.recomptes)
    horari_desat = dict(
        document,
        metadata={
            **(document.get("metadata") or {}),
            "cost_total": info["cost_total"],
            "cost_desglossament": info["cost_desglossament"],
            "logs": logs,
            **stats,
        },
    )
    resposta = {
        "cost_total": info["cost_total"],
        "cost_breakdown": info["cost_breakdown"],
        "cost_breakdown_details": detalls,
        "cost_desglossament": info["cost_desglossament"],
        "slots": franges,
        "valid": valid_editor,
        "logs": logs,
        "stats": stats,
    }
    return horari_desat, resposta


def horari_backtracking(
    resultat, problema: Problema, politiques, disponible: Disponibilitat, segons, max_nodes
) -> dict:
    """Assignació d'ítems → ocurrències i resposta del motor backtracking.

    L'ordre d'assignació conserva el recorregut de la millor llavor. Els dies
    sense sessions hi són; sense solució no s'afegeix cost ni motor.
    """
    if resultat.assignacio is None:
        if resultat.motiu_aturada == "temps":
            error = missatge("cerca_tallada_temps", segons=segons)
        elif resultat.motiu_aturada == "nodes":
            error = missatge("cerca_tallada_nodes", nodes=max_nodes)
        else:
            return {"metadata": {"error": missatge("no_viable"), "viable": False}, "dies": []}
        return {"metadata": {"error": error, "viable": False, "motiu_aturada": resultat.motiu_aturada}, "dies": []}
    items = {it.id: it for it in resultat.items}
    per_franja = {}
    for identificador, franja in resultat.assignacio.items():
        per_franja.setdefault(franja.clau, []).extend(e.a_diccionari() for e in items[identificador].examens)
    # Les dates de candidats ja estan ordenades com les selected_dates del motor antic.
    dates = [d.original for d in problema.dates if d.origen == "dates_resoltes"]
    prefixos = dates or problema.dies
    dies = []
    for prefix in prefixos:
        dia_nom, data_iso = dia_de_prefix(prefix)
        if dates and not data_iso:
            continue
        dia = {"dia": dia_nom, "sessions": []}
        if data_iso:
            dia["data"] = data_iso
        for hora in problema.hores_inici:
            clau = f"{prefix}_{hora}"
            sessions = per_franja.get(clau, [])
            if not sessions:
                continue
            simultanies = []
            for sessio in sessions:
                copia = sessio.copy()
                copia["analisi"] = analitza_motor(
                    problema, disponible, sessio, de_clau(clau), [s for s in sessions if s != sessio]
                )
                simultanies.append(copia)
            dia["sessions"].append({"hora": hora, "sessions_simultanees": simultanies})
        dies.append(dia)
    document = {"dies": dies, "metadata": {"total_sessions": len(problema.examens), "data_inici": None}}
    document["metadata"].update(estadistiques_generacio(document), cost_total=resultat.cost, motor="v2-backtrack")
    if resultat.motiu_aturada:
        document["metadata"]["motiu_aturada"] = resultat.motiu_aturada
    return document


def estadistiques_generacio(document: dict) -> dict:
    """Recomptes de les anàlisis ja fetes, deduplicats dins de cada franja."""
    camps = {
        "substitucions": "total_substitucions",
        "abans_jornada": "professors_abans",
        "despres_jornada": "professors_despres",
        "no_treballa_dia": "professors_no_treballa",
    }
    resultat = dict.fromkeys(camps.values(), 0)
    total = 0
    for dia in document.get("dies", []):
        for franja in dia.get("sessions", []):
            sessions = franja.get("sessions_simultanees", [])
            total += len(sessions)
            for camp, clau in camps.items():
                resultat[clau] += len(
                    {
                        (entrada["professor"], entrada.get("hora", franja.get("hora", "")))
                        for sessio in sessions
                        for entrada in sessio.get("analisi", {}).get(camp, [])
                        if isinstance(entrada, dict) and entrada.get("professor")
                    }
                )
    return {**resultat, "dies_necessaris": len(document.get("dies", [])), "total_sessions": total}


def horari_intent_greedy(assignacio, items, problema, disponible, sessions_sortida=None):
    """Només dies ocupats, ordre físic i anàlisi amb les altres sessions.

    L'exclusió de companyes usa igualtat de contingut, com els embolcalls del
    motor antic, també quan dues ocurrències siguin idèntiques.
    """
    if sessions_sortida is None:
        sessions_sortida = {it.id: tuple(e.a_diccionari() for e in it.examens) for it in items}
    per_franja = {}
    for identificador, ubicacio in assignacio.items():
        per_franja.setdefault(ubicacio.clau, []).extend(sessions_sortida[identificador])
    dies, dia_map = [], {}
    for ubicacio in problema.franges:
        sessions = per_franja.get(ubicacio.clau, [])
        if not sessions:
            continue
        if ubicacio.prefix not in dia_map:
            dia = {"dia": ubicacio.dia, "sessions": []}
            if ubicacio.data_iso:
                dia["data"] = ubicacio.data_iso
            dia_map[ubicacio.prefix] = dia
            dies.append(dia)
        simultanies = []
        for sessio in sessions:
            copia = sessio.copy()
            copia["analisi"] = analitza_motor(
                problema, disponible, sessio, ubicacio, [s for s in sessions if s != sessio]
            )
            simultanies.append(copia)
        dia_map[ubicacio.prefix]["sessions"].append({"hora": ubicacio.hora, "sessions_simultanees": simultanies})
    document = {"dies": dies, "metadata": {}}
    document["metadata"].update(estadistiques_generacio(document))
    return document


def horari_greedy(resultat, segons, track_intents):
    """Metadades pròpies i retorn de l'últim intent si cap és complet."""
    document = resultat.horari
    if resultat.assignacio is None:
        return document
    meta = document["metadata"]
    if resultat.motiu_aturada == "temps":
        meta["motiu_aturada"] = "temps"
        if not resultat.complet:
            meta.update(viable=False, error=missatge("cerca_tallada_temps", segons=segons))
    if track_intents:
        meta["intents"] = resultat.traça
    meta["motor"] = "v2-intents"
    return document


def horari_recuit(resultat, problema, disponible):
    """Dies buits, anàlisi sense companyes i identificadors públics del recuit."""
    if resultat.error is not None:
        return {"dies": [], "metadata": resultat.error}
    per_id = {it.id: it for it in resultat.items}
    per_franja = {}
    for identificador, ubicacio in resultat.assignacio.items():
        per_franja.setdefault(ubicacio.clau, []).extend(e.a_diccionari() for e in per_id[identificador].examens)
    dates = [d.original for d in problema.dates if d.origen == "dates_resoltes"]
    dies = []
    for prefix in dates or problema.dies:
        dia_nom, data_iso = dia_de_prefix(prefix)
        if dates and not data_iso:
            continue
        if not dates:
            del_mapa = problema.mapa_dies.get(normalitzar_dia(dia_nom)) or []
            data_iso = del_mapa[0] if del_mapa else None
        dia = {"dia": dia_nom, "sessions": []}
        if data_iso:
            dia["data"] = data_iso
        for hora in problema.hores_inici:
            clau = f"{prefix}_{hora}"
            if clau not in per_franja:
                continue
            simultanies = []
            for sessio in per_franja[clau]:
                analisi = analitza_motor(problema, disponible, sessio, de_clau(f"{data_iso or dia_nom}_{hora}"))
                simultanies.append({"tipus": "examen", **sessio, "analisi": analisi})
            dia["sessions"].append({"hora": hora, "sessions_simultanees": simultanies})
        dies.append(dia)
    document = {
        "dies": dies,
        "metadata": {
            "total_sessions": len(problema.examens),
            "cost_total": resultat.cost,
            "motor": "v3-sa",
            "logs": [v["missatge"] for v in resultat.violacions],
        },
    }
    if resultat.motiu_aturada:
        document["metadata"]["motiu_aturada"] = resultat.motiu_aturada
    document["metadata"].update(estadistiques_generacio(document))
    return document
