"""Els recomptes de la pantalla Estadístiques, sense HTTP.

Les substitucions es llegeixen amb el repositori dels recomptes
(recomptes/repositories.py), com els informes.
"""

from collections.abc import Collection
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from errors_domini import NoValid
from noms import ordre_alfabetic
from recomptes.services import (
    absencies_i_serveis,
    balanc_per_professor,
    cobertura,
    dades_professors,
    en_ordre_de_franges,
    franges_de_l_horari,
    grup_de,
    nom_absent,
    nom_substitut,
    per_dia_i_hora,
    per_grup,
    percentatge,
    professors_absencies,
    professors_substitucions,
    substitucions_fetes,
    substitucions_reals,
    valida_interval,
    vigilancies_entre,
)
from utils.hores import normalitzar_hora

# Les franges de l'horari triades al filtre per hores (normalitzades); None: totes
Hores = Collection[str] | None

DIES_SETMANA = ["Dilluns", "Dimarts", "Dimecres", "Dijous", "Divendres", "Dissabte", "Diumenge"]


class SenseGrups(NoValid):
    pass


class DiaNoValid(NoValid):
    pass


class HoraNoValida(NoValid):
    pass


def interval(data_inici: Optional[str], data_final: Optional[str]) -> tuple[str, str]:
    """L'interval demanat; sense dates, els últims 30 dies fins avui."""
    if not data_final:
        data_final = datetime.now().strftime("%Y-%m-%d")
    if not data_inici:
        data_inici = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    valida_interval(data_inici, data_final)  # 400, com els informes
    return data_inici, data_final


def _data(s: dict) -> date:
    return date.fromisoformat(s["data"])


def _dia_setmana(data: date) -> str:
    dia_idx = data.weekday()
    return DIES_SETMANA[dia_idx] if dia_idx < len(DIES_SETMANA) else "Altres"


def _normalitzar_dia(dia: str) -> Optional[str]:
    if not dia:
        return None
    dia_clean = dia.strip().lower()
    for nom in DIES_SETMANA:
        if nom.lower() == dia_clean:
            return nom
    return None


def _reals(db: Session, data_inici: str, data_final: str, hores: Hores = None) -> list[dict]:
    """Les substitucions de l'interval amb els filtres de tots els recomptes
    («No substituir» i qui té classe), com els informes."""
    return substitucions_reals(db, data_inici, data_final, hores)


def resum(db: Session, data_inici: str, data_final: str, hores: Hores = None) -> dict:
    """La cobertura de les absències i els serveis (com la portada de
    l'informe de direcció) i les vigilàncies."""
    c = cobertura(absencies_i_serveis(_reals(db, data_inici, data_final, hores)))

    _, v = vigilancies_entre(db, data_inici, data_final, hores)

    return {
        "periode": {"data_inici": data_inici, "data_final": data_final},
        "cobertura": {
            "absencies": c["absencies"],
            "serveis": c["serveis"],
            "a_cobrir": c["a_cobrir"],
            "cobertes": c["cobertes"],
            "pendents": c["a_cobrir"] - c["cobertes"],
            "percentatge": round(c["percentatge"], 1),
        },
        "vigilancies": {
            "total": v["total"],
            "vigilant": v["vigilant"],
            "substitut": v["substitut"],
            "cobertes": v["cobertes"],
            "descobertes": v["descobertes"],
            "percentatge": round(v["percentatge"], 1),
        },
        "activitat": {
            "dies_amb_absencies": c["dies"],
            "dies_amb_vigilancies": v["dies"],
        },
    }


def professors(db: Session, data_inici: str, data_final: str, hores: Hores = None) -> dict:
    """Els rànquings: absències i serveis (com l'informe de direcció) i
    substitucions fetes."""
    reals = _reals(db, data_inici, data_final, hores)

    return {
        "periode": {"data_inici": data_inici, "data_final": data_final},
        "professors_absents": [
            {"professor": p["nom"], "absencies": p["absencies"], "serveis": p["serveis"], "total": p["total"]}
            for p in professors_absencies(absencies_i_serveis(reals))[:10]
        ],
        "top_substituts": [
            {"professor": p["nom"], "total": p["total"]}
            for p in professors_substitucions(substitucions_fetes(db, data_inici, data_final, hores))[:10]
        ],
    }


def temporal(db: Session, institucio: str, data_inici: str, data_final: str, hores: Hores = None) -> dict:
    """Per dia de la setmana i per hora: les hores a cobrir i les cobertes (de
    les absències i els serveis, com la taula dia × hora de l'informe) i les
    vigilàncies."""
    per_hora, per_dia_hora = per_dia_i_hora(absencies_i_serveis(_reals(db, data_inici, data_final, hores)))
    per_dia = {i: {"a_cobrir": 0, "cobertes": 0} for i in range(len(DIES_SETMANA))}
    for (dia, _hora), v in per_dia_hora.items():
        per_dia[dia]["a_cobrir"] += v["absencies"]
        per_dia[dia]["cobertes"] += v["substitucions"]

    vigs_per_dia = {dia: 0 for dia in DIES_SETMANA}
    vigs_per_hora = {}
    for vig in vigilancies_entre(db, data_inici, data_final, hores)[0]:
        hora = normalitzar_hora((vig["hora"] or "").strip())
        vigs_per_dia[_dia_setmana(_data(vig))] += 1
        if hora:
            vigs_per_hora[hora] = vigs_per_hora.get(hora, 0) + 1

    def _hora(hora: str) -> dict:
        v = per_hora.get(hora, {"absencies": 0, "substitucions": 0})
        return {
            "hora": hora,
            "a_cobrir": v["absencies"],
            "cobertes": v["substitucions"],
            "vigilancies": vigs_per_hora.get(hora, 0),
        }

    return {
        "periode": {"data_inici": data_inici, "data_final": data_final},
        "dies": [
            {
                "dia": dia,
                "a_cobrir": per_dia[i]["a_cobrir"],
                "cobertes": per_dia[i]["cobertes"],
                "vigilancies": vigs_per_dia[dia],
            }
            for i, dia in enumerate(DIES_SETMANA)
        ],
        "hores": [
            _hora(hora)
            for hora in en_ordre_de_franges(
                set(per_hora) | set(vigs_per_hora), franges_de_l_horari(db, institucio, data_inici, data_final)
            )
        ],
        "totals": {
            "a_cobrir": sum(v["a_cobrir"] for v in per_dia.values()),
            "cobertes": sum(v["cobertes"] for v in per_dia.values()),
            "vigilancies": sum(vigs_per_dia.values()),
        },
    }


def _top(comptadors: dict) -> tuple[str, int] | None:
    """El més repetit; en empat, el primer per ordre alfabètic."""
    return min(comptadors.items(), key=lambda x: (-x[1], ordre_alfabetic(x[0]))) if comptadors else None


def _absencies_per_grup(
    db: Session, data_inici: str, data_final: str, grups: set | None = None, hores: Hores = None
) -> list[dict]:
    """Les absències i els serveis amb grup (`grups`: només aquests)."""
    return [
        s
        for s in absencies_i_serveis(_reals(db, data_inici, data_final, hores))
        if grup_de(s) and (grups is None or grup_de(s) in grups)
    ]


def classes(db: Session, data_inici: str, data_final: str, hores: Hores = None) -> dict:
    """Per grup: hores a cobrir, cobertes i percentatge (com l'informe de
    direcció), l'assignatura més afectada i el professor més absent."""
    absencies = _absencies_per_grup(db, data_inici, data_final, hores=hores)
    assignatures, professors = {}, {}
    for s in absencies:
        grup = grup_de(s)
        for comptadors, nom in ((assignatures, (s["assignatura"] or "").strip()), (professors, nom_absent(s))):
            if nom:
                del_grup = comptadors.setdefault(grup, {})
                del_grup[nom] = del_grup.get(nom, 0) + 1

    def _text(top) -> str:
        return f"{top[0]} ({top[1]})" if top else "-"

    files = [
        {
            "grup": grup,
            "a_cobrir": v["absencies"],
            "cobertes": v["cobertes"],
            "percentatge": percentatge(v["cobertes"], v["absencies"]),
            "assignatura_top": _text(_top(assignatures.get(grup, {}))),
            "professor_top": _text(_top(professors.get(grup, {}))),
        }
        for grup, v in per_grup(absencies).items()
    ]
    files.sort(key=lambda x: (-x["a_cobrir"], ordre_alfabetic(x["grup"])))
    return {"periode": {"data_inici": data_inici, "data_final": data_final}, "classes": files}


def classes_detall(db: Session, data_inici: str, data_final: str, grups: list[str], hores: Hores = None) -> dict:
    if not grups:
        raise SenseGrups("Cal indicar almenys un grup", codi="sense_grups")
    data_inici, data_final = interval(data_inici, data_final)
    grups_set = {g.strip() for g in grups if g and g.strip()}

    resultats = []
    per_assignatura, per_professor, per_substitut, per_grup = {}, {}, {}, {}
    files = sorted(
        _absencies_per_grup(db, data_inici, data_final, grups_set, hores), key=lambda f: (f["data"], f["hora"])
    )
    for s in files:
        hora = (s["hora"] or "").strip()
        grup = grup_de(s)
        assignatura = (s["assignatura"] or "").strip()
        professor = (s["professor_absent"] or "").strip()
        substitut = (s["substitut"] or "").strip()
        resultats.append(
            {
                "data": s["data"],
                "dia_setmana": _dia_setmana(_data(s)),
                "hora": hora,
                "grup": grup,
                "assignatura": assignatura,
                "professor_absent": professor,
                "substitut": substitut,
                "tipus_substitut": (s["tipus_substitut"] or "").strip(),
            }
        )
        if assignatura:
            per_assignatura[assignatura] = per_assignatura.get(assignatura, 0) + 1
        if professor:
            per_professor[professor] = per_professor.get(professor, 0) + 1
        if substitut:
            per_substitut[substitut] = per_substitut.get(substitut, 0) + 1
        per_grup[grup] = per_grup.get(grup, 0) + 1

    def _nom_i_total(comptadors: dict) -> dict | None:
        top = _top(comptadors)
        return {"nom": top[0], "total": top[1]} if top else None

    return {
        "periode": {"data_inici": data_inici, "data_final": data_final},
        "grups": sorted(grups_set),
        "resultats": resultats,
        "resum": {
            "total": len(resultats),
            "per_grup": [
                {"grup": g, "total": c}
                for g, c in sorted(per_grup.items(), key=lambda x: (-x[1], ordre_alfabetic(x[0])))
            ],
            "top_assignatura": _nom_i_total(per_assignatura),
            "top_professor": _nom_i_total(per_professor),
            "top_substitut": _nom_i_total(per_substitut),
        },
    }


def taula_professors(db: Session, data_inici: str, data_final: str, hores: Hores = None) -> dict:
    """Per professor: absències, serveis, substitucions fetes, vigilàncies
    fetes i balanç."""
    reals = _reals(db, data_inici, data_final, hores)
    _, vigilancies = vigilancies_entre(db, data_inici, data_final, hores)
    return {
        "periode": {"data_inici": data_inici, "data_final": data_final},
        "professors": [
            {"professor": p.pop("nom"), **p}
            for p in balanc_per_professor(
                absencies_i_serveis(reals),
                substitucions_fetes(db, data_inici, data_final, hores),
                vigilancies["fetes_per_professor"],
            )
        ],
    }


def detall_professor(db: Session, professor: str, data_inici: str, data_final: str, hores: Hores = None) -> dict:
    """Les absències i els serveis d'un professor i les substitucions que ha
    fet: el mateix que l'informe PDF per professor (dades_professors)."""
    trobat = dades_professors(db, data_inici, data_final, professor, hores)
    absencies = trobat[0]["absencies"] if trobat else []
    fetes = trobat[0]["substitucions_fetes"] if trobat else []

    def _fila(s: dict) -> dict:
        return {
            "data": s["data"],
            "dia_setmana": _dia_setmana(_data(s)),
            "hora": (s["hora"] or "").strip(),
            "grup": s["grup"] or "",
            "assignatura": s["assignatura"] or "",
            "tipus_absencia": s["tipus_absencia"] or "",
        }

    def _per_data(files: list[dict]) -> list[dict]:
        return sorted(files, key=lambda x: (x["data"], x["hora"]))

    return {
        "periode": {"data_inici": data_inici, "data_final": data_final},
        "professor": professor,
        "absencies": _per_data([{**_fila(s), "substitut": s["substitut"] or ""} for s in absencies]),
        "substitucions": _per_data(
            [
                {
                    **_fila(s),
                    "professor_absent": s["professor_absent"] or "",
                    "tipus_substitut": s["tipus_substitut"] or "",
                }
                for s in fetes
            ]
        ),
    }


def hores_de_l_horari(db: Session, institucio: str, data_inici: str, data_final: str) -> dict:
    """Les franges de l'horari a l'interval, per al filtre per hores."""
    return {
        "periode": {"data_inici": data_inici, "data_final": data_final},
        "hores": franges_de_l_horari(db, institucio, data_inici, data_final),
    }


def franges(db: Session, dia: str, hora: str, data_inici: str, data_final: str, hores: Hores = None) -> dict:
    """Per a una hora d'un dia de la setmana: quantes substitucions fetes
    (substitucions_fetes) hi va haver alhora a cada data i qui les va fer."""
    dia_normalitzat = _normalitzar_dia(dia)
    if not dia_normalitzat:
        raise DiaNoValid("Dia invàlid", codi="dia_no_valid")
    if not hora:
        raise HoraNoValida("Hora invàlida", codi="hora_no_valida")

    slots = {}
    for s in substitucions_fetes(db, data_inici, data_final, hores):
        if _dia_setmana(_data(s)) == dia_normalitzat and (s["hora"] or "").strip() == hora:
            slots.setdefault(f"{s['data']}|{hora}", []).append(nom_substitut(s))

    per_nombre = {}
    total_subs = 0
    for subs in slots.values():
        total_subs += len(subs)
        for prof in subs:
            per_nombre.setdefault(len(subs), {})
            per_nombre[len(subs)][prof] = per_nombre[len(subs)].get(prof, 0) + 1

    return {
        "periode": {"data_inici": data_inici, "data_final": data_final},
        "dia": dia_normalitzat,
        "hora": hora,
        "total_slots": len(slots),
        "total_substitucions": total_subs,
        "franges": [
            {
                "num_substitucions": n,
                "professors": [
                    {"professor": prof, "total": count}
                    for prof, count in sorted(per_nombre[n].items(), key=lambda x: (-x[1], ordre_alfabetic(x[0])))
                ],
            }
            for n in sorted(per_nombre)
        ],
    }
