"""Els recomptes de les substitucions, en un sol lloc: els fan servir els
informes PDF (pdf/services.py), les Estadístiques i el «(n/total)» del
desplegable de substituts (substitucions/_consultes.py).

Les absències i la cobertura compten les files que es veuen a la pantalla
Substitucions (`substitucions_reals`, amb la regla de la pantalla:
`es_visible_a_substitucions`); les substitucions fetes, totes les files amb
substitut (`substitucions_fetes`). Cada apartat (resum, per mes, per
professor, per dia i hora, per grup i nivell) és una funció que rep aquesta
llista i es pot provar sense BD.
"""

from collections import Counter, defaultdict
from collections.abc import Collection
from datetime import date, datetime

from sqlalchemy.orm import Session

from grups.repositories import GrupsAlliberatsRepository
from helpers import MissingXmlError
from noms import ordre_alfabetic
from prioritats.repositories import NoSubstituirRepository
from recomptes.domain import IntervalNoValid
from recomptes.repositories import RecomptesRepository
from repositories import CursRepository, XMLVersionRepository
from routes.parametres import data_iso
from serveis.dia import Dia
from substitucions.visibilitat import es_visible_a_substitucions
from utils.hores import normalitzar_hora

# Nivell dels grups que no són de cap nivell de la configuració d'exàmens
ALTRES = "Altres"


def valida_interval(data_inici: str, data_final: str) -> None:
    if data_iso(data_inici) > data_iso(data_final):
        raise IntervalNoValid("La data inicial ha de ser anterior o igual a la final", codi="interval_invertit")


# ===== Les substitucions que compten =====


class AlliberatsPerData(dict):
    """Alliberats efectius de cada data (els del dia més els per període),
    calculats només per a les dates que es consulten."""

    def __init__(self, db: Session):
        super().__init__()
        self.db = db

    def __missing__(self, data):
        valor = GrupsAlliberatsRepository.get_by_date(self.db, data) if data else {}
        self[data] = valor
        return valor


def a_les_hores(hora: str, hores: Collection[str] | None) -> bool:
    """Si la fila és d'una de les `hores` (franges de l'horari, normalitzades);
    sense `hores`, totes."""
    return hores is None or normalitzar_hora((hora or "").strip()) in hores


def substitucions_reals(
    db: Session, data_inici: str, data_final: str, hores: Collection[str] | None = None
) -> list[dict]:
    """Les files de l'interval que es veuen a la pantalla Substitucions
    (es_visible_a_substitucions, la mateixa regla que la pantalla), de tots
    els tipus, per data i per ordre de creació: d'aquí surten les absències i
    la cobertura. Amb `hores`, només les d'aquestes franges."""
    no_sub = set(NoSubstituirRepository.get_all(db))
    alliberats_per_data = AlliberatsPerData(db)
    return [
        s
        for s in RecomptesRepository.substitucions_entre(db, data_inici, data_final)
        if a_les_hores(s["hora"], hores)
        and es_visible_a_substitucions(s, no_sub, alliberats_per_data[s.get("data", "")].get(s.get("hora", ""), []))
    ]


# Les absències (i la cobertura) només compten les hores en què falta un
# professor amb classe: les marcades com a absència o servei. La vigilància
# de vigilant absent es pot resoldre reassignant-la (sense substitució), i a
# les encadenades i les vigilàncies no falta ningú (FUNCIONAMENT.md, apartat 6).
TIPUS_D_ABSENCIA = ("ABSENCIA", "SERVEI")


def substitucions_fetes(
    db: Session, data_inici: str | None, data_final: str | None, hores: Collection[str] | None = None
) -> list[dict]:
    """Les substitucions fetes de l'interval: totes les files amb substitut,
    de qualsevol tipus (també encadenades i vigilàncies), sense els filtres
    de «No substituir» ni d'alliberats: si té substitut, algú hi ha anat.
    Mesuren la feina de cada professor; no són la cobertura (FUNCIONAMENT.md,
    apartat 6). Amb `hores`, només les d'aquestes franges."""
    return [
        s for s in RecomptesRepository.amb_substitut_entre(db, data_inici, data_final) if a_les_hores(s["hora"], hores)
    ]


def es_absencia_o_servei(s: dict) -> bool:
    return s["tipus_absencia"] in TIPUS_D_ABSENCIA


def absencies_i_serveis(subs_reals: list[dict]) -> list[dict]:
    """Les absències i els serveis: el que compta a les absències i a la
    cobertura."""
    return [s for s in subs_reals if es_absencia_o_servei(s)]


def nom_absent(s: dict) -> str:
    return (s.get("professor_absent") or "").strip()


def nom_substitut(s: dict) -> str:
    return (s.get("substitut") or "").strip()


def _nom_mes(s: dict, mesos_nom: dict) -> str:
    d = datetime.strptime(s["data"], "%Y-%m-%d")
    return f"{mesos_nom[d.month]} {d.year}"


# ===== Un apartat per funció =====


def cobertura(subs_reals: list[dict]) -> dict:
    """Absències, serveis, quantes s'havien de cobrir i quantes tenen
    substitut (de les absències i els serveis: absencies_i_serveis)."""
    cobertes = sum(1 for s in subs_reals if nom_substitut(s))
    return {
        "absencies": sum(1 for s in subs_reals if s["tipus_absencia"] == "ABSENCIA"),
        "serveis": sum(1 for s in subs_reals if s["tipus_absencia"] == "SERVEI"),
        "a_cobrir": len(subs_reals),
        "cobertes": cobertes,
        "percentatge": cobertes / len(subs_reals) * 100 if subs_reals else 0,
        "dies": len({s["data"] for s in subs_reals}),
    }


def resum(subs_reals: list[dict], total_baixes: int) -> dict:
    """Els totals de la portada de l'informe de direcció."""
    c = cobertura(subs_reals)
    return {
        "total_absencies": c["absencies"],
        "total_serveis": c["serveis"],
        "total_baixes": total_baixes,
        "total_substitucions": c["cobertes"],
        "total_necessiten": c["a_cobrir"],
        "cobertura_pct": c["percentatge"],
        "dies_actius": c["dies"],
    }


def per_mes(subs_reals: list[dict], mesos_nom: dict) -> list[dict]:
    """Absències, serveis i substitucions fetes de cada mes, per ordre. Un mes
    només hi surt si té alguna absència o algun servei. La cobertura es
    calcula com la global: fetes / absències + serveis."""
    per_mes_raw = defaultdict(lambda: {"absencies": 0, "serveis": 0, "substitucions": 0})
    for s in subs_reals:
        d = datetime.strptime(s["data"], "%Y-%m-%d")
        clau = (d.year, d.month)
        if s["tipus_absencia"] == "ABSENCIA":
            per_mes_raw[clau]["absencies"] += 1
        elif s["tipus_absencia"] == "SERVEI":
            per_mes_raw[clau]["serveis"] += 1
        if nom_substitut(s):
            per_mes_raw[clau]["substitucions"] += 1

    mesos = []
    for (any_, mes), v in sorted(per_mes_raw.items()):
        total_m = v["absencies"] + v["serveis"]
        mesos.append(
            {
                "mes": f"{mesos_nom[mes]} {any_}",
                "absencies": v["absencies"],
                "serveis": v["serveis"],
                "substitucions": v["substitucions"],
                "cobertura": v["substitucions"] / total_m * 100 if total_m else 0,
            }
        )
    return mesos


def per_comptador(comptador: str = "total"):
    """La clau d'ordre dels rànquings: de més a menys `comptador` i, en
    empat, per ordre alfabètic natural del nom, a la web i als PDF."""
    return lambda x: (-x[comptador], ordre_alfabetic(x["nom"]))


def professors_absencies(subs_reals: list[dict]) -> list[dict]:
    """Absències i serveis de cada professor absent, de més a menys (els
    empats, per ordre alfabètic)."""
    per_professor = defaultdict(lambda: {"absencies": 0, "serveis": 0})
    for s in subs_reals:
        prof = nom_absent(s)
        if not prof:
            continue
        if s["tipus_absencia"] == "ABSENCIA":
            per_professor[prof]["absencies"] += 1
        elif s["tipus_absencia"] == "SERVEI":
            per_professor[prof]["serveis"] += 1
    return sorted(
        [{"nom": p, **v, "total": v["absencies"] + v["serveis"]} for p, v in per_professor.items()],
        key=per_comptador(),
    )


def professors_substitucions(fetes: list[dict]) -> list[dict]:
    """Substitucions fetes (substitucions_fetes) per cada professor, de més a
    menys (els empats, per ordre alfabètic)."""
    per_professor = defaultdict(int)
    for s in fetes:
        sub = nom_substitut(s)
        if sub:
            per_professor[sub] += 1
    return sorted([{"nom": p, "total": n} for p, n in per_professor.items()], key=per_comptador())


def vigilancies_per_resultat(vigilancies: list[dict], substitucions: list[dict]) -> dict:
    """Les vigilàncies d'examen per resultat (FUNCIONAMENT.md, apartat 5).
    Cada vigilància és coberta si hi va el vigilant (assignat i no falta) o
    si la seva fila de vigilant absent té substitut; si no, descoberta. El
    vigilant falta si té una absència, un servei o una fila de vigilant absent
    a aquella hora (`substitucions`: totes les de l'interval, sense filtres).
    Les vigilàncies fetes per professor són només les del vigilant que hi va:
    qui cobreix la fila de vigilant absent ho té a les substitucions fetes."""

    def clau(data, hora, professor):
        return data, normalitzar_hora((hora or "").strip()), (professor or "").strip()

    falta, coberta = set(), set()
    for s in substitucions:
        c = clau(s["data"], s["hora"], s["professor_absent"])
        if s["tipus_absencia"] in (*TIPUS_D_ABSENCIA, "VIGILANCIA_ABSENT"):
            falta.add(c)
        if s["tipus_absencia"] == "VIGILANCIA_ABSENT" and nom_substitut(s):
            coberta.add(c)

    resultat = {"total": 0, "vigilant": 0, "substitut": 0, "descobertes": 0}
    fetes = defaultdict(int)
    for v in vigilancies:
        c = clau(v["data"], v["hora"], v["vigilant"])
        resultat["total"] += 1
        if c[2] and c not in falta:
            resultat["vigilant"] += 1
            fetes[c[2]] += 1
        elif c[2] and c in coberta:
            resultat["substitut"] += 1
        else:
            resultat["descobertes"] += 1
    cobertes = resultat["vigilant"] + resultat["substitut"]
    return {
        **resultat,
        "cobertes": cobertes,
        "percentatge": cobertes / resultat["total"] * 100 if resultat["total"] else 0,
        "dies": len({v["data"] for v in vigilancies}),
        "fetes_per_professor": dict(fetes),
    }


def vigilancies_entre(
    db: Session, data_inici: str, data_final: str, hores: Collection[str] | None = None
) -> tuple[list[dict], dict]:
    """Les vigilàncies de l'interval (amb `hores`, només les d'aquestes
    franges) i el seu resultat (vigilancies_per_resultat)."""
    vigilancies = [
        v for v in RecomptesRepository.vigilancies_entre(db, data_inici, data_final) if a_les_hores(v["hora"], hores)
    ]
    substitucions = RecomptesRepository.substitucions_entre(db, data_inici, data_final)
    return vigilancies, vigilancies_per_resultat(vigilancies, substitucions)


def balanc_per_professor(
    absencies_reals: list[dict], fetes: list[dict], vigilancies_fetes: dict[str, int] | None = None
) -> list[dict]:
    """Per a cada professor: absències i serveis, substitucions fetes,
    vigilàncies fetes (vigilancies_per_resultat) i el balanç = substitucions
    fetes − absències (els serveis no resten, són feina per al centre). Cada
    hora compta igual (cap franja, com el pati, no hi té un pes diferent). Per
    balanç i, en empat, per ordre alfabètic."""
    files = defaultdict(lambda: {"absencies": 0, "serveis": 0, "substitucions_fetes": 0, "vigilancies_fetes": 0})
    for s in absencies_reals:
        if prof := nom_absent(s):
            files[prof]["absencies" if s["tipus_absencia"] == "ABSENCIA" else "serveis"] += 1
    for s in fetes:
        files[nom_substitut(s)]["substitucions_fetes"] += 1
    for prof, n in (vigilancies_fetes or {}).items():
        files[prof]["vigilancies_fetes"] += n
    return sorted(
        [
            {
                "nom": p,
                **v,
                "total_absencies": v["absencies"] + v["serveis"],
                "balanc": v["substitucions_fetes"] - v["absencies"],
            }
            for p, v in files.items()
        ],
        key=lambda x: (-x["balanc"], ordre_alfabetic(x["nom"])),
    )


def per_dia_i_hora(subs_reals: list[dict]) -> tuple[dict, dict]:
    """Substitucions («absencies») i cobertes («substitucions») per hora i per
    dia de la setmana i hora. El dia és l'índex (0 = dilluns): el nom el posa
    el PDF en el seu idioma."""
    per_hora = defaultdict(lambda: {"absencies": 0, "substitucions": 0})
    per_dia_hora = defaultdict(lambda: {"absencies": 0, "substitucions": 0})
    for s in subs_reals:
        dia = datetime.strptime(s["data"], "%Y-%m-%d").weekday()
        hora = normalitzar_hora(s.get("hora", "") or "") or "Desconeguda"
        cobert = bool(nom_substitut(s))
        for comptador in (per_hora[hora], per_dia_hora[(dia, hora)]):
            comptador["absencies"] += 1
            if cobert:
                comptador["substitucions"] += 1
    return dict(per_hora), dict(per_dia_hora)


def mesos_de(subs: list[dict], mesos_nom: dict) -> list[str]:
    """Els mesos (nom i any) de les files, per ordre."""
    claus = sorted({(int(s["data"][:4]), int(s["data"][5:7])) for s in subs})
    return [f"{mesos_nom[mes]} {any_}" for any_, mes in claus]


def per_professor_i_mes(
    absencies_reals: list[dict],
    fetes: list[dict],
    absents: list[str],
    substituts: list[str],
    mesos: list[str],
    mesos_nom: dict,
) -> tuple[dict, dict, dict]:
    """Les taules professor × mes: absències i serveis dels `absents` (de
    `absencies_reals`), i substitucions fetes pels `substituts` (de `fetes`).
    Els mesos de totes aquestes files són a `mesos` (mesos_de)."""
    absencies = {p: {m: 0 for m in mesos} for p in absents}
    serveis = {p: {m: 0 for m in mesos} for p in absents}
    substitucions = {p: {m: 0 for m in mesos} for p in substituts}
    for s in absencies_reals:
        prof = nom_absent(s)
        if prof in absencies:
            if s["tipus_absencia"] == "ABSENCIA":
                absencies[prof][_nom_mes(s, mesos_nom)] += 1
            elif s["tipus_absencia"] == "SERVEI":
                serveis[prof][_nom_mes(s, mesos_nom)] += 1
    for s in fetes:
        sub = nom_substitut(s)
        if sub in substitucions:
            substitucions[sub][_nom_mes(s, mesos_nom)] += 1
    return absencies, serveis, substitucions


def percentatge(cobertes: int, absencies: int) -> int:
    return round(cobertes / absencies * 100) if absencies else 0


def grup_de(s: dict) -> str:
    """El grup de la fila; buit si no en té («-» o buit)."""
    grup = (s.get("grup") or "").strip()
    return "" if grup == "-" else grup


def per_grup(subs_reals: list[dict]) -> dict[str, dict]:
    """Substitucions i cobertes de cada grup, en l'ordre en què surten. Les
    substitucions sense grup no hi compten."""
    grups = defaultdict(lambda: {"absencies": 0, "cobertes": 0})
    for s in subs_reals:
        if grup := grup_de(s):
            grups[grup]["absencies"] += 1
            if nom_substitut(s):
                grups[grup]["cobertes"] += 1
    return dict(grups)


def per_grup_i_nivell(
    subs_reals: list[dict],
    ordre_nivells: list[str],
    grup2nivell: dict[str, str],
    mesos: list[str],
    mesos_nom: dict,
) -> dict:
    """Substitucions i cobertes per grup (i per grup i mes) i per nivell. Les
    substitucions sense grup («-» o buit) no hi compten."""

    def nivell(grup):
        return grup2nivell.get(grup, ALTRES)

    grups = per_grup(subs_reals)
    per_grup_mes = {}
    for s in subs_reals:
        grup = grup_de(s)
        if not grup:
            continue
        if grup not in per_grup_mes:
            per_grup_mes[grup] = {m: 0 for m in mesos}
        mes = _nom_mes(s, mesos_nom)
        if mes in mesos:  # un mes sense absències, serveis ni cobertes no hi és
            per_grup_mes[grup][mes] += 1

    per_nivell = defaultdict(lambda: {"absencies": 0, "cobertes": 0, "grups": set()})
    for grup, v in grups.items():
        niv = nivell(grup)
        per_nivell[niv]["absencies"] += v["absencies"]
        per_nivell[niv]["cobertes"] += v["cobertes"]
        per_nivell[niv]["grups"].add(grup)

    return {
        "per_nivell": {
            niv: {
                "absencies": v["absencies"],
                "cobertes": v["cobertes"],
                "pendents": v["absencies"] - v["cobertes"],
                "pct": percentatge(v["cobertes"], v["absencies"]),
                "n_grups": len(v["grups"]),
            }
            for niv, v in per_nivell.items()
        },
        "ordre_nivells": ordre_nivells,
        "per_grup_mes": per_grup_mes,
        "mesos": mesos,
        "grups_ordenats": sorted(
            [
                {
                    "nom": g,
                    **v,
                    "pendents": v["absencies"] - v["cobertes"],
                    "pct": percentatge(v["cobertes"], v["absencies"]),
                    "nivell": nivell(g),
                }
                for g, v in grups.items()
            ],
            key=lambda x: (ordre_nivells.index(x["nivell"]) if x["nivell"] in ordre_nivells else 99, x["nom"]),
        ),
    }


def dades_professors(
    db: Session, data_inici: str, data_final: str, professor: str = None, hores: Collection[str] | None = None
) -> list[dict]:
    """Per a cada professor (per ordre alfabètic), les seves absències i les
    substitucions que ha fet. Amb `professor`, només aquell professor (el nom
    sencer, sense distingir majúscules ni comptar els espais dels extrems).
    Les absències i els serveis (absencies_i_serveis) i les substitucions
    fetes de tots els tipus (substitucions_fetes), com a l'informe de
    direcció. Amb `hores`, només les d'aquestes franges."""
    per_absent = defaultdict(list)
    per_substitut = defaultdict(list)
    for s in absencies_i_serveis(substitucions_reals(db, data_inici, data_final, hores)):
        if prof := nom_absent(s):
            per_absent[prof].append(s)
    for s in substitucions_fetes(db, data_inici, data_final, hores):
        per_substitut[nom_substitut(s)].append(s)

    tots = sorted(set(per_absent.keys()) | set(per_substitut.keys()), key=ordre_alfabetic)
    if professor:
        professor = professor.strip().lower()
        tots = [p for p in tots if p.lower() == professor]

    return [
        {"nom": p, "absencies": per_absent.get(p, []), "substitucions_fetes": per_substitut.get(p, [])} for p in tots
    ]


def franges_de_l_horari(db: Session, institucio: str, data_inici: str, data_final: str) -> list[str]:
    """Les franges (hores) de l'horari a l'interval: la unió, pel nom i en
    l'ordre de cada horari, de les versions de l'XML vigents a l'interval
    (la de la data inicial i les que hi comencen)."""
    dates = [data_inici] + [
        v.data_inici.isoformat()
        for v in XMLVersionRepository.list_all(db)
        if v.data_inici and data_inici < v.data_inici.isoformat() <= data_final
    ]
    franges = []
    for data in dates:
        try:
            hores = Dia.de_text(data, institucio).horari.hores
        except MissingXmlError:
            continue
        for hora in hores:
            hora = normalitzar_hora((hora or "").strip())
            if hora and hora not in franges:
                franges.append(hora)
    return franges


def en_ordre_de_franges(hores, franges: list[str]) -> list[str]:
    """Les `hores` en l'ordre de les `franges`; les que no hi són, al final
    per ordre de text."""
    return sorted(hores, key=lambda h: (franges.index(h), "") if h in franges else (len(franges), h))


# ===== El desplegable de substituts =====


def fetes_per_substitut(fetes: list[dict]) -> tuple[Counter, Counter]:
    """(per franja, total): les substitucions fetes de cada substitut a cada
    franja de la setmana, amb clau (substitut, dia de la setmana 0-6, hora),
    i en total, amb clau el substitut."""
    per_franja, total = Counter(), Counter()
    for s in fetes:
        substitut = nom_substitut(s)
        per_franja[(substitut, date.fromisoformat(s["data"]).weekday(), (s.get("hora") or "").strip())] += 1
        total[substitut] += 1
    return per_franja, total


def fetes_del_curs_per_substitut(db: Session, data: str) -> tuple[Counter, Counter]:
    """El «(n/total)» del desplegable de substituts: les substitucions fetes
    (totes les files amb substitut) del curs de `data`, per franja i en total
    (fetes_per_substitut). Sense curs, de tot l'històric."""
    curs = CursRepository.get_for_date(db, data)
    inici = curs.data_inici.isoformat() if curs else None
    final = curs.data_fi.isoformat() if curs and curs.data_fi else None
    return fetes_per_substitut(RecomptesRepository.franges_amb_substitut_entre(db, inici, final))
