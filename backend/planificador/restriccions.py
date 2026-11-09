"""Les restriccions i preferències del planificador i els costos dels
professors: com es llegeixen de la BD i s'hi desen (amb l'estructura que fan
servir la pantalla i els motors), i els exàmens que hi surten."""

import copy
import json
import re

from sqlalchemy.orm import Session

from planificador.repositories import CostProfessorRepository, RestriccioRepository, carrega_json
from planificador.schemas import Restriccions
from scheduler_engine.defaults import DEFAULT_COST_PROFESSORS


def llegeix(db: Session) -> dict:
    """Les restriccions desades, amb l'estructura que fan servir la pantalla i
    els motors; cada restricció té el seu propi pes (0-100%)."""
    data = {
        "restriccions_dures": {
            "no_mateix_dia": [],
            "no_mateix_slot": {},
            "mateix_slot": [],
            "assignatures_dia_fix": {},
            "assignatures_hora_fix": {},
            "assignatures_slot_prohibit": [],
            "professors_horari_estricte": [],
            "professors_limit_dies_especifics": {},
            "slots_valids_per_nivell": {},
            "combinacions_permeses": [],
            "assignatures_dies_exclosos": [],
        },
        "preferencies": {"mateix_dia": [], "dies_diferents": [], "mateix_slot": []},
        "pesos_optimitzacio": {},
        "pesos_percentatge": {},  # Nova estructura per motor v3
    }

    # Llegir restriccions amb pes individual
    rows = RestriccioRepository.actives(db)
    for r in rows:
        t, val = r.tipus, carrega_json(r.configuracio, None)
        pes = r.pes if hasattr(r, "pes") and r.pes is not None else 100

        # Tipus que van a restriccions_dures
        if t in data["restriccions_dures"]:
            if isinstance(data["restriccions_dures"][t], list):
                if t in ("mateix_slot", "combinacions_permeses"):
                    if isinstance(val, list):
                        data["restriccions_dures"][t].append({"nom": r.clau or "", "assignatures": val, "pes": pes})
                    elif val:
                        data["restriccions_dures"][t].append(val)
                elif t == "assignatures_dies_exclosos":
                    if isinstance(val, dict) and val:
                        val["pes"] = pes
                        data["restriccions_dures"][t].append(val)
                else:
                    data["restriccions_dures"][t].append(val or r.clau)
            elif r.clau:
                # Per diccionaris (dia_fix, hora_fix), guardem pes separat
                data["restriccions_dures"][t][r.clau] = val
                # Guardar pes en clau especial
                pes_key = f"_pes_{r.clau}"
                data["restriccions_dures"][t][pes_key] = pes

        # Tipus que ara també es llegeixen directament (dies_diferents, mateix_dia, mateix_slot)
        # Nota: "pref_mateix_slot" s'usa per evitar col·lisió amb "mateix_slot" de restriccions_dures
        elif t in ("dies_diferents", "mateix_dia", "pref_mateix_slot"):
            real_t = "mateix_slot" if t == "pref_mateix_slot" else t
            assignatures = val if isinstance(val, list) else carrega_json(val, [])
            data["preferencies"][real_t].append({"assignatures": assignatures, "pes": pes})

        # Pesos d'optimització (migrats de ExamPesOptimitzacio)
        elif t == "pes_optimitzacio" and r.clau:
            data["pesos_optimitzacio"][r.clau] = pes

    # Costos de professors (exam_costos_professors)
    costos_professors = {"globals": {}, "individuals": {}}
    for cp in CostProfessorRepository.get_all(db):
        if cp.professor is None:
            # Cost global
            costos_professors["globals"][cp.tipus] = cp.pes
        else:
            # Cost individual
            if cp.professor not in costos_professors["individuals"]:
                costos_professors["individuals"][cp.professor] = {}
            costos_professors["individuals"][cp.professor][cp.tipus] = cp.pes

    # Mapejar a pesos_percentatge pel motor v3
    data["pesos_percentatge"] = {
        "substitucio": costos_professors["globals"].get("substitucio", DEFAULT_COST_PROFESSORS["substitucio"]),
        "professor_abans": costos_professors["globals"].get("abans_jornada", DEFAULT_COST_PROFESSORS["abans_jornada"]),
        "professor_despres": costos_professors["globals"].get(
            "despres_jornada", DEFAULT_COST_PROFESSORS["despres_jornada"]
        ),
        "professor_no_treballa": costos_professors["globals"].get(
            "no_treballa_dia", DEFAULT_COST_PROFESSORS["no_treballa_dia"]
        ),
    }
    data["costos_professors"] = costos_professors

    return data


def desa(db: Session, payload: dict) -> None:
    """Substitueix les restriccions desades per les de `payload` (sense
    commit), cadascuna amb el seu pes."""

    # Abans de cap esborrat, també per a les crides internes sense router.
    payload = Restriccions.model_validate(payload).model_dump(exclude_unset=True)

    def _coerce_pes(value, default=100):
        if isinstance(value, list):
            value = value[0] if value else default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    RestriccioRepository.esborra_totes(db)

    restr = payload.get("restriccions_dures", {})

    # Recollir pesos de claus especials (_pes_XXX)
    pesos_especials = {}
    for tipus, contingut in restr.items():
        if isinstance(contingut, dict):
            for k, v in contingut.items():
                if k.startswith("_pes_"):
                    clau_real = k[5:]  # Treure "_pes_"
                    pesos_especials[f"{tipus}_{clau_real}"] = _coerce_pes(v)

    # Tipus derivats automàticament dels alliberaments — no desar del frontend
    _SKIP_TIPUS = {"slots_valids_per_nivell"}

    for tipus, contingut in restr.items():
        if tipus in _SKIP_TIPUS:
            continue
        if isinstance(contingut, dict):
            for k, v in contingut.items():
                if k.startswith("_pes_"):
                    continue  # Saltar claus de pes
                pes = _coerce_pes(pesos_especials.get(f"{tipus}_{k}", 100))
                RestriccioRepository.afegeix(
                    db,
                    tipus=tipus,
                    clau=str(k),
                    configuracio=json.dumps(v, ensure_ascii=False),
                    pes=pes,
                )
        elif isinstance(contingut, list):
            for item in contingut:
                if tipus in ("mateix_slot", "combinacions_permeses") and isinstance(item, dict):
                    assignatures = item.get("assignatures", [])
                    pes = _coerce_pes(item.get("pes", 100))
                    RestriccioRepository.afegeix(
                        db,
                        tipus=tipus,
                        clau=item.get("nom") or None,
                        configuracio=json.dumps(assignatures, ensure_ascii=False),
                        pes=pes,
                    )
                elif tipus == "assignatures_dies_exclosos" and isinstance(item, dict):
                    pes = _coerce_pes(item.pop("pes", 100) if "pes" in item else 100)
                    RestriccioRepository.afegeix(
                        db,
                        tipus=tipus,
                        configuracio=json.dumps(item, ensure_ascii=False),
                        pes=pes,
                    )
                else:
                    RestriccioRepository.afegeix(
                        db,
                        tipus=tipus,
                        configuracio=json.dumps(item, ensure_ascii=False),
                        pes=100,
                    )

    # Guardar preferències (dies_diferents, mateix_dia, mateix_slot) a ExamRestriccio amb pes
    # Nota: "mateix_slot" es desa com "pref_mateix_slot" per evitar col·lisió amb restriccions_dures
    pref = payload.get("preferencies", {})
    for t in ("mateix_dia", "dies_diferents", "mateix_slot"):
        for item in pref.get(t, []):
            assignatures = item.get("assignatures", [])
            pes = int(item.get("pes", 75))
            db_tipus = "pref_mateix_slot" if t == "mateix_slot" else t
            RestriccioRepository.afegeix(
                db,
                tipus=db_tipus,
                configuracio=json.dumps(assignatures, ensure_ascii=False),
                pes=pes,
            )

    # Guardar pesos d'optimització a ExamRestriccio
    pesos = payload.get("pesos_optimitzacio", {})
    for k, v in pesos.items():
        try:
            RestriccioRepository.afegeix(
                db,
                tipus="pes_optimitzacio",
                clau=str(k),
                configuracio=json.dumps(int(v)),
                pes=int(v),
            )
        except (ValueError, TypeError):
            continue

    # Guardar costos de professors
    costos = payload.get("costos_professors", {})
    if costos:
        CostProfessorRepository.esborra_tots(db)  # Esborrar anteriors

        # Costos globals
        for tipus, pes in costos.get("globals", {}).items():
            CostProfessorRepository.afegeix(db, None, tipus, int(pes))

        # Costos individuals
        for professor, tipus_dict in costos.get("individuals", {}).items():
            for tipus, pes in tipus_dict.items():
                CostProfessorRepository.afegeix(db, professor, tipus, int(pes))

    # També acceptar pesos_percentatge directament (compatibilitat amb motor v3)
    pesos_pct = payload.get("pesos_percentatge", {})
    if pesos_pct and not costos:
        CostProfessorRepository.esborra_tots(db)
        mapping = {
            "substitucio": "substitucio",
            "professor_abans": "abans_jornada",
            "professor_despres": "despres_jornada",
            "professor_no_treballa": "no_treballa_dia",
        }
        for clau, pes in pesos_pct.items():
            tipus = mapping.get(clau, clau)
            CostProfessorRepository.afegeix(db, None, tipus, int(pes))


def assignatures_de(restr: dict) -> set[str]:
    """Els exàmens (noms de sessió) que surten a les restriccions."""
    resultat = set()
    dures = (restr or {}).get("restriccions_dures", {})
    preferencies = (restr or {}).get("preferencies", {})

    for item in dures.get("no_mateix_dia", []):
        if isinstance(item, list):
            resultat.update(item)
        elif item:
            resultat.add(item)

    for grup in (dures.get("no_mateix_slot") or {}).values():
        if isinstance(grup, list):
            resultat.update(grup)

    for grup in dures.get("mateix_slot", []):
        if isinstance(grup, dict):
            resultat.update(grup.get("assignatures", []) or [])
        elif isinstance(grup, list):
            resultat.update(grup)

    resultat.update({k for k in (dures.get("assignatures_dia_fix") or {}).keys() if not str(k).startswith("_pes_")})
    resultat.update({k for k in (dures.get("assignatures_hora_fix") or {}).keys() if not str(k).startswith("_pes_")})

    for cfg in (dures.get("professors_limit_dies_especifics") or {}).values():
        if isinstance(cfg, dict):
            resultat.update(cfg.get("assignatures", []) or [])

    for tipus in ("combinacions_permeses", "assignatures_dies_exclosos", "assignatures_slot_prohibit"):
        for item in dures.get(tipus, []) or []:
            if isinstance(item, dict):
                resultat.update(item.get("assignatures", []) or [])
            elif isinstance(item, list):
                resultat.update(item)

    for tipus in ("mateix_dia", "dies_diferents", "mateix_slot"):
        for item in preferencies.get(tipus, []):
            if isinstance(item, dict):
                resultat.update(item.get("assignatures", []) or [])

    return {a for a in resultat if a}


def treu_assignatures(restr: dict, fora: set[str]) -> dict:
    """Còpia de les restriccions sense les assignatures `fora` (p.ex. d'un curs
    anterior). Les restriccions que es queden sense sentit s'eliminen: una
    agrupació buida; una incompatibilitat, preferència o combinació amb menys
    de dos exàmens; un examen fixat o un límit de professor sense exàmens."""

    restr = copy.deepcopy(restr or {})
    dures = restr.setdefault("restriccions_dures", {})
    prefs = restr.setdefault("preferencies", {})

    def neta(llista):
        return [a for a in (llista or []) if a not in fora]

    def amb_llista(item, minim):
        """Item (dict amb 'assignatures' o llista) net, o None si queda massa curt."""
        if isinstance(item, dict):
            abans = item.get("assignatures", []) or []
            ara = neta(abans)
            if len(ara) < min(minim, len(abans)):
                return None
            return dict(item, assignatures=ara)
        if isinstance(item, list):
            ara = neta(item)
            return ara if len(ara) >= min(minim, len(item)) else None
        return None if item in fora else item

    if "mateix_slot" in dures:
        dures["mateix_slot"] = [i for i in (amb_llista(x, 1) for x in dures["mateix_slot"]) if i]
    if "no_mateix_dia" in dures:
        dures["no_mateix_dia"] = [i for i in (amb_llista(x, 2) for x in dures["no_mateix_dia"]) if i]
    for tipus, minim in (
        ("combinacions_permeses", 2),
        ("assignatures_dies_exclosos", 1),
        ("assignatures_slot_prohibit", 1),
    ):
        if tipus in dures:
            dures[tipus] = [i for i in (amb_llista(x, minim) for x in dures[tipus] or []) if i]

    if isinstance(dures.get("no_mateix_slot"), dict):
        nou = {}
        for nom, grup in dures["no_mateix_slot"].items():
            if nom.startswith("_") or not isinstance(grup, list):
                continue
            ara = neta(grup)
            if len(ara) >= min(2, len(grup)):
                nou[nom] = ara
                if f"_pes_{nom}" in dures["no_mateix_slot"]:
                    nou[f"_pes_{nom}"] = dures["no_mateix_slot"][f"_pes_{nom}"]
        dures["no_mateix_slot"] = nou

    for tipus in ("assignatures_dia_fix", "assignatures_hora_fix"):
        if isinstance(dures.get(tipus), dict):
            dures[tipus] = {
                k: v for k, v in dures[tipus].items() if (k[5:] if k.startswith("_pes_") else k) not in fora
            }

    if isinstance(dures.get("professors_limit_dies_especifics"), dict):
        nou = {}
        for prof, cfg in dures["professors_limit_dies_especifics"].items():
            if isinstance(cfg, dict) and cfg.get("assignatures"):
                ara = neta(cfg["assignatures"])
                if not ara:
                    continue
                cfg = dict(cfg, assignatures=ara)
            nou[prof] = cfg
        dures["professors_limit_dies_especifics"] = nou

    for tipus in ("mateix_dia", "dies_diferents", "mateix_slot"):
        if tipus in prefs:
            prefs[tipus] = [i for i in (amb_llista(x, 2) for x in prefs[tipus]) if i]
    return restr


def agrupacions_amb_diversos_nivells(restriccions: dict) -> list:
    """Noms de les agrupacions (mateix_slot) amb exàmens de més d'un nivell.

    Els motors col·loquen cada agrupació dins d'un nivell; per a exàmens de
    nivells diferents al mateix moment hi ha la preferència "Mateix dia i hora".
    El nivell és el sufix del nom de la sessió: "Anglès (1-BAT)" -> "1-BAT".
    """
    barrejades = []
    for grup in (restriccions.get("restriccions_dures") or {}).get("mateix_slot") or []:
        assignatures = grup.get("assignatures", []) if isinstance(grup, dict) else grup
        nivells = {
            m.group(1) for a in assignatures or [] if isinstance(a, str) and (m := re.search(r"\(([^()]+)\)\s*$", a))
        }
        if len(nivells) > 1:
            barrejades.append((grup.get("nom") if isinstance(grup, dict) else "") or ", ".join(assignatures))
    return barrejades
