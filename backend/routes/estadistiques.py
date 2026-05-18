"""
Routes per estadístiques de substitucions i vigilàncies
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from typing import Optional, List
from dependencies import get_db
from models import Substitucio, Vigilancia
from repositories import GrupsAlliberatsRepository, NoSubstituirRepository

router = APIRouter(prefix="/api/estadistiques", tags=["Estadístiques"])

DIES_SETMANA = ["Dilluns", "Dimarts", "Dimecres", "Dijous", "Divendres", "Dissabte", "Diumenge"]


def _default_date_range(data_inici: Optional[str], data_final: Optional[str]) -> tuple[str, str]:
    if not data_final:
        data_final = datetime.now().strftime("%Y-%m-%d")
    if not data_inici:
        data_inici_date = datetime.now() - timedelta(days=30)
        data_inici = data_inici_date.strftime("%Y-%m-%d")
    return data_inici, data_final


def _get_dia_setmana(date_value) -> str:
    dia_idx = date_value.weekday()
    return DIES_SETMANA[dia_idx] if dia_idx < len(DIES_SETMANA) else "Altres"


def _is_absencia_real(tipus_absencia: Optional[str]) -> bool:
    """Defineix què compta com a absència del professor a les estadístiques"""
    tipus = (tipus_absencia or "").strip().upper()
    # Excloem les substitucions tècniques (VIGILANCIA) i els forats (ENCADENADA)
    return tipus not in ["ENCADENADA", "VIGILANCIA"]


def _get_absencia_categoria(hora: str, tipus_absencia: Optional[str]) -> str:
    """Categoritza l'absència segons el tipus (Normal, Pati, Altres)"""
    tipus = (tipus_absencia or "").strip().upper()
    hora_clean = (hora or "").strip()
    if hora_clean == "Pati":
        return "pati"
    # SERVEI i VIGILANCIA compten com a 'altres' (igual que al desktop)
    if tipus in ["SERVEI", "VIGILANCIA"]:
        return "altres"
    return "normal"


def _normalitzar_dia(dia: str) -> Optional[str]:
    if not dia:
        return None
    dia_clean = dia.strip().lower()
    for nom in DIES_SETMANA:
        if nom.lower() == dia_clean:
            return nom
    return None


def _has_valid_grup(grup: Optional[str]) -> bool:
    """Comprova si el grup és vàlid (no buit ni '-').
    Les substitucions de Pati (GP/VP) no tenen grup vàlid."""
    if not grup:
        return False
    grup_clean = grup.strip()
    return bool(grup_clean) and grup_clean != "-"


def _es_substitucio_real(sub, no_subst: set) -> bool:
    """
    Comprova si és una substitució que necessita cobertura real.
    Filtra les assignatures que estan a NO_SUBST (Guàrdia, P, GP, etc.)
    i les que tenen assignatura buida.
    """
    assignatura = (sub.assignatura or "").strip()

    # Si l'assignatura està a NO_SUBST, no compta
    if assignatura in no_subst:
        return False

    # Si assignatura buida, no compta (no té classe a aquella hora)
    if not assignatura:
        return False

    return True


@router.get("/resum")
async def get_resum_estadistiques(
    data_inici: Optional[str] = None,
    data_final: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Retorna resum general d'estadístiques
    """
    try:
        data_inici, data_final = _default_date_range(data_inici, data_final)

        # Carregar llista d'assignatures que NO necessiten substitució
        no_subst = set(NoSubstituirRepository.get_all(db))

        # Estadístiques de substitucions
        # IMPORTANT: Diferenciar entre absències i substitucions:
        # - Absències: tenen grup I el grup NO està alliberat (generen que el grup es quedi sense professor)
        # - Substitucions: absències amb substitut assignat
        # - VP (Vigilància Pati): necessita substitució (NO està a NO_SUBST)
        # - P, GP, Guàrdia, etc.: NO necessiten substitució (estan a NO_SUBST)

        # Carregar TOTES les substitucions del període
        substitucions = db.query(Substitucio).filter(
            Substitucio.data >= data_inici,
            Substitucio.data <= data_final
        ).all()

        total_substitucions = 0
        substitucions_assignades = 0

        # Cache de grups alliberats per data
        grups_alliberats_cache = {}

        for sub in substitucions:
            # Filtrar substitucions que no necessiten cobertura real
            if not _es_substitucio_real(sub, no_subst):
                continue

            data = sub.data
            hora = sub.hora
            grup = sub.grup

            # Si té grup vàlid, aplicar filtre de grups alliberats
            if _has_valid_grup(grup):
                if data not in grups_alliberats_cache:
                    grups_alliberats_cache[data] = GrupsAlliberatsRepository.get_by_date(db, data)

                grups_hora = grups_alliberats_cache[data].get(hora, [])

                # Si el grup està alliberat, no comptar
                if grup in grups_hora:
                    continue

            # Comptar substitucions reals
            total_substitucions += 1
            if sub.substitut and sub.substitut.strip():
                substitucions_assignades += 1

        # Absències pendents (sense substitut)
        substitucions_pendents = total_substitucions - substitucions_assignades

        # Estadístiques de vigilàncies
        total_vigilancies = db.query(Vigilancia).filter(
            Vigilancia.data >= data_inici,
            Vigilancia.data <= data_final
        ).count()

        vigilancies_assignades = db.query(Vigilancia).filter(
            Vigilancia.data >= data_inici,
            Vigilancia.data <= data_final,
            Vigilancia.vigilant != None,
            Vigilancia.vigilant != ""
        ).count()

        vigilancies_pendents = total_vigilancies - vigilancies_assignades

        # Dies amb activitat
        # Obtenir dies únics de les substitucions reals que hem comptat
        dies_amb_substitucions_set = set()
        for sub in substitucions:
            if not _es_substitucio_real(sub, no_subst):
                continue
            if _has_valid_grup(sub.grup):
                grups_hora = grups_alliberats_cache.get(sub.data, {}).get(sub.hora, [])
                if sub.grup in grups_hora:
                    continue
            dies_amb_substitucions_set.add(sub.data)
        dies_amb_substitucions = len(dies_amb_substitucions_set)

        dies_amb_vigilancies = db.query(Vigilancia.data).filter(
            Vigilancia.data >= data_inici,
            Vigilancia.data <= data_final
        ).distinct().count()

        return {
            "periode": {
                "data_inici": data_inici,
                "data_final": data_final
            },
            "substitucions": {
                "total": total_substitucions,
                "assignades": substitucions_assignades,
                "pendents": substitucions_pendents,
                "percentatge_assignat": round(substitucions_assignades / total_substitucions * 100, 1) if total_substitucions > 0 else 0
            },
            "vigilancies": {
                "total": total_vigilancies,
                "assignades": vigilancies_assignades,
                "pendents": vigilancies_pendents,
                "percentatge_assignat": round(vigilancies_assignades / total_vigilancies * 100, 1) if total_vigilancies > 0 else 0
            },
            "activitat": {
                "dies_amb_substitucions": dies_amb_substitucions,
                "dies_amb_vigilancies": dies_amb_vigilancies
            }
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en obtenir estadístiques: {str(e)}")


@router.get("/professors")
async def get_estadistiques_professors(
    data_inici: Optional[str] = None,
    data_final: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Retorna estadístiques per professor
    """
    try:
        data_inici, data_final = _default_date_range(data_inici, data_final)

        # Carregar llista d'assignatures que NO necessiten substitució
        no_subst = set(NoSubstituirRepository.get_all(db))

        # Top professors absents (incloent VP que necessita substitució)
        substitucions = db.query(Substitucio).filter(
            Substitucio.data >= data_inici,
            Substitucio.data <= data_final
        ).all()

        absencies_per_professor = {}
        substitucions_per_professor = {}
        grups_alliberats_cache = {}

        for sub in substitucions:
            # Filtrar substitucions que no necessiten cobertura real
            if not _es_substitucio_real(sub, no_subst):
                continue

            data = sub.data
            hora = sub.hora
            grup = sub.grup
            professor = sub.professor_absent
            substitut = sub.substitut

            # Si té grup vàlid, aplicar filtre de grups alliberats
            if _has_valid_grup(grup):
                if data not in grups_alliberats_cache:
                    grups_alliberats_cache[data] = GrupsAlliberatsRepository.get_by_date(db, data)

                grups_hora = grups_alliberats_cache[data].get(hora, [])

                # Si el grup està alliberat, no comptar
                if grup in grups_hora:
                    continue

            # Comptar absència si és real (no VIGILANCIA ni ENCADENADA)
            if professor and _is_absencia_real(sub.tipus_absencia):
                absencies_per_professor[professor] = absencies_per_professor.get(professor, 0) + 1

            # Comptar substitució si té substitut si és real (no VIGILANCIA)
            if substitut and substitut.strip() and sub.tipus_absencia != "VIGILANCIA":
                substitucions_per_professor[substitut] = substitucions_per_professor.get(substitut, 0) + 1

        # Ordenar i limitar a top 10
        professors_absents = sorted(
            [(prof, count) for prof, count in absencies_per_professor.items()],
            key=lambda x: x[1],
            reverse=True
        )[:10]

        substituts = sorted(
            [(prof, count) for prof, count in substitucions_per_professor.items()],
            key=lambda x: x[1],
            reverse=True
        )[:10]

        # Top vigilants
        vigilants = db.query(
            Vigilancia.vigilant,
            func.count(Vigilancia.id).label('total_vigilancies')
        ).filter(
            Vigilancia.data >= data_inici,
            Vigilancia.data <= data_final,
            Vigilancia.vigilant != None,
            Vigilancia.vigilant != ""
        ).group_by(
            Vigilancia.vigilant
        ).order_by(
            func.count(Vigilancia.id).desc()
        ).limit(10).all()

        return {
            "periode": {
                "data_inici": data_inici,
                "data_final": data_final
            },
            "professors_absents": [
                {"professor": prof, "total": count}
                for prof, count in professors_absents
            ],
            "top_substituts": [
                {"professor": prof, "total": count}
                for prof, count in substituts
            ],
            "top_vigilants": [
                {"professor": v[0], "total": v[1]}
                for v in vigilants
            ]
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en obtenir estadístiques de professors: {str(e)}")


@router.get("/temporal")
async def get_estadistiques_temporals(
    data_inici: Optional[str] = None,
    data_final: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Retorna distribució per dia de la setmana i per hora
    """
    try:
        data_inici, data_final = _default_date_range(data_inici, data_final)

        # Carregar llista d'assignatures que NO necessiten substitució
        no_subst = set(NoSubstituirRepository.get_all(db))

        substitucions = db.query(Substitucio).filter(
            Substitucio.data >= data_inici,
            Substitucio.data <= data_final
        ).all()

        vigilancies = db.query(Vigilancia).filter(
            Vigilancia.data >= data_inici,
            Vigilancia.data <= data_final
        ).all()

        grups_alliberats_cache = {}
        subs_per_dia = {dia: 0 for dia in DIES_SETMANA}
        subs_per_hora = {}

        for sub in substitucions:
            # Filtrar substitucions que no necessiten cobertura real
            if not _es_substitucio_real(sub, no_subst):
                continue

            data = sub.data
            hora = (sub.hora or "").strip()
            grup = sub.grup
            substitut = sub.substitut

            # Si té grup vàlid, aplicar filtre de grups alliberats
            if _has_valid_grup(grup):
                if data not in grups_alliberats_cache:
                    grups_alliberats_cache[data] = GrupsAlliberatsRepository.get_by_date(db, data)

                grups_hora = grups_alliberats_cache[data].get(hora, [])
                if grup in grups_hora:
                    continue

            if not substitut or not substitut.strip():
                continue

            dia_idx = data.weekday()
            dia_nom = DIES_SETMANA[dia_idx] if dia_idx < len(DIES_SETMANA) else "Altres"
            subs_per_dia[dia_nom] = subs_per_dia.get(dia_nom, 0) + 1
            if hora:
                subs_per_hora[hora] = subs_per_hora.get(hora, 0) + 1

        vigs_per_dia = {dia: 0 for dia in DIES_SETMANA}
        vigs_per_hora = {}
        for vig in vigilancies:
            data = vig.data
            hora = (vig.hora or "").strip()
            dia_idx = data.weekday()
            dia_nom = DIES_SETMANA[dia_idx] if dia_idx < len(DIES_SETMANA) else "Altres"
            vigs_per_dia[dia_nom] = vigs_per_dia.get(dia_nom, 0) + 1
            if hora:
                vigs_per_hora[hora] = vigs_per_hora.get(hora, 0) + 1

        dies = [
            {
                "dia": dia,
                "substitucions": subs_per_dia.get(dia, 0),
                "vigilancies": vigs_per_dia.get(dia, 0)
            }
            for dia in DIES_SETMANA
        ]

        hores_ordenades = sorted(set(list(subs_per_hora.keys()) + list(vigs_per_hora.keys())))
        hores = [
            {
                "hora": hora,
                "substitucions": subs_per_hora.get(hora, 0),
                "vigilancies": vigs_per_hora.get(hora, 0)
            }
            for hora in hores_ordenades
        ]

        return {
            "periode": {
                "data_inici": data_inici,
                "data_final": data_final
            },
            "dies": dies,
            "hores": hores,
            "totals": {
                "substitucions": sum(subs_per_dia.values()),
                "vigilancies": sum(vigs_per_dia.values())
            }
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en obtenir estadístiques temporals: {str(e)}")


@router.get("/classes")
async def get_estadistiques_classes(
    data_inici: Optional[str] = None,
    data_final: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Retorna estadístiques per classe/grup
    """
    try:
        data_inici, data_final = _default_date_range(data_inici, data_final)

        substitucions_amb_grup = db.query(Substitucio).filter(
            Substitucio.data >= data_inici,
            Substitucio.data <= data_final,
            Substitucio.grup != None,
            Substitucio.grup != ""
        ).all()

        stats_per_classe = {}
        grups_alliberats_cache = {}

        for sub in substitucions_amb_grup:
            data = sub.data
            hora = (sub.hora or "").strip()
            grup = (sub.grup or "").strip()

            if not grup:
                continue

            if data not in grups_alliberats_cache:
                grups_alliberats_cache[data] = GrupsAlliberatsRepository.get_by_date(db, data)

            grups_hora = grups_alliberats_cache[data].get(hora, [])
            if grup in grups_hora:
                continue

            if grup not in stats_per_classe:
                stats_per_classe[grup] = {
                    "total_subs": 0,
                    "assignatures": {},
                    "professors": {},
                    "hores": set()
                }

            if sub.substitut and sub.substitut.strip():
                stats_per_classe[grup]["total_subs"] += 1

            assignatura = (sub.assignatura or "").strip()
            if assignatura:
                stats_per_classe[grup]["assignatures"][assignatura] = (
                    stats_per_classe[grup]["assignatures"].get(assignatura, 0) + 1
                )

            professor = (sub.professor_absent or "").strip()
            # Només comptar professor si és absència real
            if professor and _is_absencia_real(sub.tipus_absencia):
                stats_per_classe[grup]["professors"][professor] = (
                    stats_per_classe[grup]["professors"].get(professor, 0) + 1
                )

            if hora:
                stats_per_classe[grup]["hores"].add(f"{data}|{hora}")

        classes = []
        for grup, stats in stats_per_classe.items():
            if stats["assignatures"]:
                top_assignatura = max(stats["assignatures"].items(), key=lambda x: x[1])
                assignatura_text = f"{top_assignatura[0]} ({top_assignatura[1]})"
            else:
                assignatura_text = "-"

            if stats["professors"]:
                top_professor = max(stats["professors"].items(), key=lambda x: x[1])
                professor_text = f"{top_professor[0]} ({top_professor[1]})"
            else:
                professor_text = "-"

            classes.append({
                "grup": grup,
                "total_subs": stats["total_subs"],
                "assignatura_top": assignatura_text,
                "professor_top": professor_text,
                "hores": len(stats["hores"])
            })

        classes.sort(key=lambda x: x["total_subs"], reverse=True)

        return {
            "periode": {
                "data_inici": data_inici,
                "data_final": data_final
            },
            "classes": classes
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en obtenir estadístiques per classe: {str(e)}")


@router.get("/classes/detall")
async def get_estadistiques_classes_detall(
    data_inici: Optional[str] = None,
    data_final: Optional[str] = None,
    grups: Optional[List[str]] = Query(None),
    grups_bracket: Optional[List[str]] = Query(None, alias="grups[]"),
    db: Session = Depends(get_db)
):
    """
    Retorna el detall de substitucions per classes seleccionades
    """
    try:
        grups_list = []
        if grups:
            grups_list.extend(grups)
        if grups_bracket:
            grups_list.extend(grups_bracket)

        if not grups_list:
            raise HTTPException(status_code=400, detail="Cal indicar almenys un grup")

        data_inici, data_final = _default_date_range(data_inici, data_final)
        grups_set = {g.strip() for g in grups_list if g and g.strip()}

        substitucions = db.query(Substitucio).filter(
            Substitucio.data >= data_inici,
            Substitucio.data <= data_final,
            Substitucio.grup != None,
            Substitucio.grup != "",
            Substitucio.grup.in_(grups_set)
        ).order_by(Substitucio.data, Substitucio.hora).all()

        resultats = []
        grups_alliberats_cache = {}
        per_assignatura = {}
        per_professor = {}
        per_substitut = {}
        per_grup = {}

        for sub in substitucions:
            data = sub.data
            hora = (sub.hora or "").strip()
            grup = (sub.grup or "").strip()

            if not grup:
                continue

            if data not in grups_alliberats_cache:
                grups_alliberats_cache[data] = GrupsAlliberatsRepository.get_by_date(db, data)

            grups_hora = grups_alliberats_cache[data].get(hora, [])
            if grup in grups_hora:
                continue

            assignatura = (sub.assignatura or "").strip()
            professor = (sub.professor_absent or "").strip()
            substitut = (sub.substitut or "").strip()
            tipus_substitut = (sub.tipus_substitut or "").strip()

            resultats.append({
                "data": str(data),
                "dia_setmana": _get_dia_setmana(data),
                "hora": hora,
                "grup": grup,
                "assignatura": assignatura,
                "professor_absent": professor,
                "substitut": substitut,
                "tipus_substitut": tipus_substitut
            })

            if assignatura:
                per_assignatura[assignatura] = per_assignatura.get(assignatura, 0) + 1
            if professor:
                per_professor[professor] = per_professor.get(professor, 0) + 1
            if substitut:
                per_substitut[substitut] = per_substitut.get(substitut, 0) + 1
            per_grup[grup] = per_grup.get(grup, 0) + 1

        top_assignatura = max(per_assignatura.items(), key=lambda x: x[1]) if per_assignatura else None
        top_professor = max(per_professor.items(), key=lambda x: x[1]) if per_professor else None
        top_substitut = max(per_substitut.items(), key=lambda x: x[1]) if per_substitut else None

        return {
            "periode": {
                "data_inici": data_inici,
                "data_final": data_final
            },
            "grups": sorted(grups_set),
            "resultats": resultats,
            "resum": {
                "total": len(resultats),
                "per_grup": [
                    {"grup": g, "total": c}
                    for g, c in sorted(per_grup.items(), key=lambda x: x[1], reverse=True)
                ],
                "top_assignatura": {"nom": top_assignatura[0], "total": top_assignatura[1]} if top_assignatura else None,
                "top_professor": {"nom": top_professor[0], "total": top_professor[1]} if top_professor else None,
                "top_substitut": {"nom": top_substitut[0], "total": top_substitut[1]} if top_substitut else None
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en obtenir detall per classes: {str(e)}")


@router.get("/taula")
async def get_estadistiques_taula_professors(
    data_inici: Optional[str] = None,
    data_final: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Retorna taula detallada per professor (absències/substitucions per tipus)
    Inclou VP (Vigilància Pati) que necessita substitució.
    Exclou P, GP, Guàrdia i altres que estan a NO_SUBST.
    """
    try:
        data_inici, data_final = _default_date_range(data_inici, data_final)

        # Carregar llista d'assignatures que NO necessiten substitució
        no_subst = set(NoSubstituirRepository.get_all(db))

        substitucions = db.query(Substitucio).filter(
            Substitucio.data >= data_inici,
            Substitucio.data <= data_final
        ).all()

        grups_alliberats_cache = {}
        stats = {}

        for sub in substitucions:
            # Filtrar substitucions que no necessiten cobertura real
            if not _es_substitucio_real(sub, no_subst):
                continue

            data = sub.data
            hora = (sub.hora or "").strip()
            grup = sub.grup

            # Si té grup vàlid, aplicar filtre de grups alliberats
            if _has_valid_grup(grup):
                if data not in grups_alliberats_cache:
                    grups_alliberats_cache[data] = GrupsAlliberatsRepository.get_by_date(db, data)

                grups_hora = grups_alliberats_cache[data].get(hora, [])
                if grup in grups_hora:
                    continue

            professor_absent = (sub.professor_absent or "").strip()
            substitut = (sub.substitut or "").strip()

            if professor_absent and _is_absencia_real(sub.tipus_absencia):
                categoria = _get_absencia_categoria(hora, sub.tipus_absencia)
                if professor_absent not in stats:
                    stats[professor_absent] = {
                        "abs_normals": 0,
                        "abs_pati": 0,
                        "abs_altres": 0,
                        "subs_normals": 0,
                        "subs_pati": 0
                    }
                if categoria == "pati":
                    stats[professor_absent]["abs_pati"] += 1
                elif categoria == "altres":
                    stats[professor_absent]["abs_altres"] += 1
                else:
                    stats[professor_absent]["abs_normals"] += 1

            if substitut:
                if substitut not in stats:
                    stats[substitut] = {
                        "abs_normals": 0,
                        "abs_pati": 0,
                        "abs_altres": 0,
                        "subs_normals": 0,
                        "subs_pati": 0
                    }
                if hora == "Pati":
                    stats[substitut]["subs_pati"] += 1
                else:
                    stats[substitut]["subs_normals"] += 1

        professors = []
        for professor, values in stats.items():
            total_abs = values["abs_normals"] + values["abs_pati"] + values["abs_altres"]
            total_subs = values["subs_normals"] + values["subs_pati"]
            ratio = round(total_subs / total_abs, 2) if total_abs > 0 else None
            ratio_text = "∞" if total_abs == 0 and total_subs > 0 else (f"{ratio:.2f}" if ratio is not None else "0")
            puntuacio = (
                values["subs_normals"] * 1.0 +
                values["subs_pati"] * 0.5 -
                values["abs_normals"] * 1.0 -
                values["abs_pati"] * 0.5 +
                values["abs_altres"] * 0.0
            )
            professors.append({
                "professor": professor,
                "abs_normals": values["abs_normals"],
                "abs_pati": values["abs_pati"],
                "abs_altres": values["abs_altres"],
                "total_abs": total_abs,
                "subs_normals": values["subs_normals"],
                "subs_pati": values["subs_pati"],
                "total_subs": total_subs,
                "ratio": ratio,
                "ratio_text": ratio_text,
                "puntuacio": round(puntuacio, 1)
            })

        professors.sort(key=lambda x: (x["puntuacio"], x["total_subs"]), reverse=True)

        return {
            "periode": {
                "data_inici": data_inici,
                "data_final": data_final
            },
            "professors": professors
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en obtenir taula d'estadístiques: {str(e)}")


@router.get("/professor/{professor}")
async def get_estadistiques_professor_detall(
    professor: str,
    data_inici: Optional[str] = None,
    data_final: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Retorna detall d'absències i substitucions per professor
    Inclou VP (Vigilància Pati) que necessita substitució.
    """
    try:
        data_inici, data_final = _default_date_range(data_inici, data_final)

        # Carregar llista d'assignatures que NO necessiten substitució
        no_subst = set(NoSubstituirRepository.get_all(db))

        substitucions_all = db.query(Substitucio).filter(
            Substitucio.data >= data_inici,
            Substitucio.data <= data_final
        ).all()

        grups_alliberats_cache = {}
        absencies = []
        substitucions = []

        for sub in substitucions_all:
            # Filtrar substitucions que no necessiten cobertura real
            if not _es_substitucio_real(sub, no_subst):
                continue

            data = sub.data
            hora = (sub.hora or "").strip()
            grup = sub.grup

            # Si té grup vàlid, aplicar filtre de grups alliberats
            if _has_valid_grup(grup):
                if data not in grups_alliberats_cache:
                    grups_alliberats_cache[data] = GrupsAlliberatsRepository.get_by_date(db, data)

                grups_hora = grups_alliberats_cache[data].get(hora, [])
                if grup in grups_hora:
                    continue

            if (sub.professor_absent or "").strip() == professor and _is_absencia_real(sub.tipus_absencia):
                absencies.append({
                    "data": data.isoformat(),
                    "dia_setmana": _get_dia_setmana(data),
                    "hora": hora,
                    "grup": sub.grup or "",
                    "assignatura": sub.assignatura or "",
                    "substitut": sub.substitut or "",
                    "tipus_absencia": sub.tipus_absencia or "",
                    "categoria": _get_absencia_categoria(hora, sub.tipus_absencia)
                })

            if (sub.substitut or "").strip() == professor:
                substitucions.append({
                    "data": data.isoformat(),
                    "dia_setmana": _get_dia_setmana(data),
                    "hora": hora,
                    "grup": sub.grup or "",
                    "assignatura": sub.assignatura or "",
                    "professor_absent": sub.professor_absent or "",
                    "tipus_substitut": sub.tipus_substitut or ""
                })

        absencies.sort(key=lambda x: (x["data"], x["hora"]))
        substitucions.sort(key=lambda x: (x["data"], x["hora"]))

        return {
            "periode": {
                "data_inici": data_inici,
                "data_final": data_final
            },
            "professor": professor,
            "absencies": absencies,
            "substitucions": substitucions
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en obtenir detall professor: {str(e)}")


@router.get("/franges")
async def get_resum_franges(
    dia: str,
    hora: str,
    data_inici: Optional[str] = None,
    data_final: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Retorna resum per franges d'una hora concreta d'un dia de la setmana
    """
    try:
        data_inici, data_final = _default_date_range(data_inici, data_final)
        dia_normalitzat = _normalitzar_dia(dia)
        if not dia_normalitzat:
            raise HTTPException(status_code=400, detail="Dia invàlid")
        if not hora:
            raise HTTPException(status_code=400, detail="Hora invàlida")

        # Carregar llista d'assignatures que NO necessiten substitució
        no_subst = set(NoSubstituirRepository.get_all(db))

        substitucions = db.query(Substitucio).filter(
            Substitucio.data >= data_inici,
            Substitucio.data <= data_final
        ).all()

        grups_alliberats_cache = {}
        slots = {}

        for sub in substitucions:
            # Filtrar substitucions que no necessiten cobertura real
            if not _es_substitucio_real(sub, no_subst):
                continue

            data = sub.data
            if _get_dia_setmana(data) != dia_normalitzat:
                continue

            hora_sub = (sub.hora or "").strip()
            if hora_sub != hora:
                continue

            grup = sub.grup

            # Si té grup vàlid, aplicar filtre de grups alliberats
            if _has_valid_grup(grup):
                if data not in grups_alliberats_cache:
                    grups_alliberats_cache[data] = GrupsAlliberatsRepository.get_by_date(db, data)

                grups_hora = grups_alliberats_cache[data].get(hora_sub, [])
                if grup in grups_hora:
                    continue

            substitut = (sub.substitut or "").strip()
            if not substitut:
                continue

            slot_key = f"{data.isoformat()}|{hora_sub}"
            if slot_key not in slots:
                slots[slot_key] = []
            slots[slot_key].append(substitut)

        franges = {}
        total_subs = 0
        for subs in slots.values():
            num_subs = len(subs)
            if num_subs <= 0:
                continue
            total_subs += num_subs
            if num_subs not in franges:
                franges[num_subs] = {}
            for prof in subs:
                franges[num_subs][prof] = franges[num_subs].get(prof, 0) + 1

        franges_result = []
        for num_subs in sorted(franges.keys()):
            professors = [
                {"professor": prof, "total": count}
                for prof, count in sorted(franges[num_subs].items(), key=lambda x: x[1], reverse=True)
            ]
            franges_result.append({
                "num_substitucions": num_subs,
                "professors": professors
            })

        return {
            "periode": {
                "data_inici": data_inici,
                "data_final": data_final
            },
            "dia": dia_normalitzat,
            "hora": hora,
            "total_slots": len(slots),
            "total_substitucions": total_subs,
            "franges": franges_result
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en obtenir resum per franges: {str(e)}")
