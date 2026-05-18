"""Serveis compartits per a les rutes del scheduler."""

from datetime import datetime, timedelta
import json

from models import ExamRestriccio, ExamCostProfessor
from scheduler_engine.defaults import DIES_SETMANA, DEFAULT_COST_PROFESSORS

SCHEDULER_DATES_KEY = "scheduler_selected_dates"
SCHEDULER_NIVELLS_KEY = "scheduler_selected_nivells"
SCHEDULER_ALLIBERAMENTS_KEY = "scheduler_alliberaments_per_nivell"
SCHEDULER_DURADA_KEY = "scheduler_durada_titular"
SCHEDULER_DURADA_EXAMEN_KEY = "scheduler_durada_examen"
SCHEDULER_DURADES_SESSIO_KEY = "scheduler_durades_per_sessio"
SCHEDULER_DURADES_GRUPS_KEY = "scheduler_durades_grups"


def _load_json(text: str, default):
    if not text:
        return default
    try:
        return json.loads(text)
    except Exception:
        return default


def _dies_entre_dates(data_inici: str, data_final: str) -> list[str]:
    try:
        inici = datetime.strptime(data_inici, "%Y-%m-%d").date()
        final = datetime.strptime(data_final, "%Y-%m-%d").date()
        if final < inici:
            return []
        dies = []
        actual = inici
        while actual <= final:
            dia_nom = DIES_SETMANA[actual.weekday()]
            if dia_nom not in dies:
                dies.append(dia_nom)
            actual += timedelta(days=1)
        return dies
    except Exception:
        return []


def _build_config_from_db(assignacions):
    config = {"assignatures": {}}
    for a in assignacions:
        nom = a.get("assignatura") if isinstance(a, dict) else a.assignatura
        if nom not in config["assignatures"]:
            config["assignatures"][nom] = {"assignacions": []}
        config["assignatures"][nom]["assignacions"].append(
            {
                "grup": a.get("grup") if isinstance(a, dict) else a.grup,
                "titular": a.get("titular") if isinstance(a, dict) else a.titular or "",
                "aula": a.get("aula") if isinstance(a, dict) else a.aula or "",
            }
        )
    return config


def _build_restriccions_from_db(db):
    """
    Construeix l'estructura de restriccions des de la BD.
    Nova estructura unificada: cada restricció té el seu propi pes (0-100%).
    """
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
    rows = db.query(ExamRestriccio).filter(ExamRestriccio.activa == True).all()
    for r in rows:
        t, val = r.tipus, _load_json(r.configuracio, None)
        pes = r.pes if hasattr(r, "pes") and r.pes is not None else 100

        # Tipus que van a restriccions_dures
        if t in data["restriccions_dures"]:
            if isinstance(data["restriccions_dures"][t], list):
                if t in ("mateix_slot", "combinacions_permeses"):
                    if isinstance(val, list):
                        data["restriccions_dures"][t].append(
                            {"nom": r.clau or "", "assignatures": val, "pes": pes}
                        )
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
            assignatures = val if isinstance(val, list) else _load_json(val, [])
            data["preferencies"][real_t].append({"assignatures": assignatures, "pes": pes})

        # Pesos d'optimització (migrats de ExamPesOptimitzacio)
        elif t == "pes_optimitzacio" and r.clau:
            data["pesos_optimitzacio"][r.clau] = pes

    # Llegir costos de professors de ExamCostProfessor
    try:
        costos_professors = {"globals": {}, "individuals": {}}
        for cp in db.query(ExamCostProfessor).all():
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
            "substitucio": costos_professors["globals"].get(
                "substitucio", DEFAULT_COST_PROFESSORS["substitucio"]
            ),
            "professor_abans": costos_professors["globals"].get(
                "abans_jornada", DEFAULT_COST_PROFESSORS["abans_jornada"]
            ),
            "professor_despres": costos_professors["globals"].get(
                "despres_jornada", DEFAULT_COST_PROFESSORS["despres_jornada"]
            ),
            "professor_no_treballa": costos_professors["globals"].get(
                "no_treballa_dia", DEFAULT_COST_PROFESSORS["no_treballa_dia"]
            ),
        }
        data["costos_professors"] = costos_professors
    except Exception:
        # Si la taula no existeix encara, usar defaults centralitzats
        data["pesos_percentatge"] = {
            "substitucio": DEFAULT_COST_PROFESSORS["substitucio"],
            "professor_abans": DEFAULT_COST_PROFESSORS["abans_jornada"],
            "professor_despres": DEFAULT_COST_PROFESSORS["despres_jornada"],
            "professor_no_treballa": DEFAULT_COST_PROFESSORS["no_treballa_dia"],
        }
        data["costos_professors"] = {
            "globals": dict(DEFAULT_COST_PROFESSORS),
            "individuals": {},
        }

    return data


def _save_restriccions_to_db(db, payload: dict):
    """
    Guarda restriccions a la BD amb pes individual.
    """
    try:
        def _coerce_pes(value, default=100):
            if isinstance(value, list):
                value = value[0] if value else default
            try:
                return int(value)
            except (TypeError, ValueError):
                return default

        db.query(ExamRestriccio).delete()

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
                    db.add(
                        ExamRestriccio(
                            tipus=tipus,
                            clau=str(k),
                            configuracio=json.dumps(v, ensure_ascii=False),
                            pes=pes,
                        )
                    )
            elif isinstance(contingut, list):
                for item in contingut:
                    if tipus in ("mateix_slot", "combinacions_permeses") and isinstance(item, dict):
                        assignatures = item.get("assignatures", [])
                        pes = _coerce_pes(item.get("pes", 100))
                        db.add(
                            ExamRestriccio(
                                tipus=tipus,
                                clau=item.get("nom") or None,
                                configuracio=json.dumps(assignatures, ensure_ascii=False),
                                pes=pes,
                            )
                        )
                    elif tipus == "assignatures_dies_exclosos" and isinstance(item, dict):
                        pes = _coerce_pes(item.pop("pes", 100) if "pes" in item else 100)
                        db.add(
                            ExamRestriccio(
                                tipus=tipus,
                                configuracio=json.dumps(item, ensure_ascii=False),
                                pes=pes,
                            )
                        )
                    else:
                        db.add(
                            ExamRestriccio(
                                tipus=tipus,
                                configuracio=json.dumps(item, ensure_ascii=False),
                                pes=100,
                            )
                        )

        # Guardar preferències (dies_diferents, mateix_dia, mateix_slot) a ExamRestriccio amb pes
        # Nota: "mateix_slot" es desa com "pref_mateix_slot" per evitar col·lisió amb restriccions_dures
        pref = payload.get("preferencies", {})
        for t in ("mateix_dia", "dies_diferents", "mateix_slot"):
            for item in pref.get(t, []):
                assignatures = item.get("assignatures", [])
                pes = int(item.get("pes", 75))
                db_tipus = "pref_mateix_slot" if t == "mateix_slot" else t
                db.add(
                    ExamRestriccio(
                        tipus=db_tipus,
                        configuracio=json.dumps(assignatures, ensure_ascii=False),
                        pes=pes,
                    )
                )

        # Guardar pesos d'optimització a ExamRestriccio
        pesos = payload.get("pesos_optimitzacio", {})
        for k, v in pesos.items():
            try:
                db.add(
                    ExamRestriccio(
                        tipus="pes_optimitzacio",
                        clau=str(k),
                        configuracio=json.dumps(int(v)),
                        pes=int(v),
                    )
                )
            except Exception:
                continue

        # Guardar costos de professors
        costos = payload.get("costos_professors", {})
        if costos:
            db.query(ExamCostProfessor).delete()  # Esborrar anteriors

            # Costos globals
            for tipus, pes in costos.get("globals", {}).items():
                db.add(ExamCostProfessor(professor=None, tipus=tipus, pes=int(pes)))

            # Costos individuals
            for professor, tipus_dict in costos.get("individuals", {}).items():
                for tipus, pes in tipus_dict.items():
                    db.add(ExamCostProfessor(professor=professor, tipus=tipus, pes=int(pes)))

        # També acceptar pesos_percentatge directament (compatibilitat amb motor v3)
        pesos_pct = payload.get("pesos_percentatge", {})
        if pesos_pct and not costos:
            db.query(ExamCostProfessor).delete()
            mapping = {
                "substitucio": "substitucio",
                "professor_abans": "abans_jornada",
                "professor_despres": "despres_jornada",
                "professor_no_treballa": "no_treballa_dia",
            }
            for clau, pes in pesos_pct.items():
                tipus = mapping.get(clau, clau)
                db.add(ExamCostProfessor(professor=None, tipus=tipus, pes=int(pes)))

        db.commit()
    except Exception:
        db.rollback()
        raise
