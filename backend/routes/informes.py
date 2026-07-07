"""
Endpoints per generar informes PDF de direcció i per professor.
"""
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from auth_utils import require_admin, get_current_user
from database import get_data_dir_for_institucio, get_export_dir_for_institucio
from repositories import ConfiguracioRepository, MasterConfigRepository
from utils.hores import normalitzar_hora as _normalitzar_hora

sys.path.insert(0, str(Path(__file__).parent.parent))
from export.pdf.informe_direccio import generar_informe_pdf
from export.pdf.informe_professors import generar_informe_professors_pdf

router = APIRouter(prefix="/api/informes", tags=["informes"])

# Noms de mes per idioma. El render del PDF no re-tradueix: mostra aquestes etiquetes
# tal qual i n'abreuja els 3 primers caràcters (Novembre→Nov, Noviembre→Nov, November→Nov).
MESOS = {
    "ca": {1: "Gener", 2: "Febrer", 3: "Març", 4: "Abril",
           5: "Maig", 6: "Juny", 7: "Juliol", 8: "Agost",
           9: "Setembre", 10: "Octubre", 11: "Novembre", 12: "Desembre"},
    "es": {1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
           5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
           9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"},
    "en": {1: "January", 2: "February", 3: "March", 4: "April",
           5: "May", 6: "June", 7: "July", 8: "August",
           9: "September", 10: "October", 11: "November", 12: "December"},
}




def _get_db_and_helpers(institucio: str):
    """Retorna connexió SQLite i dades auxiliars per a la institució donada"""
    import sqlite3

    data_dir = get_data_dir_for_institucio(institucio)
    db_path = data_dir / "gestor.db"
    if not db_path.exists():
        raise FileNotFoundError(f"No s'ha trobat gestor.db per a {institucio}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    cur = conn.cursor()
    cur.execute("SELECT assignatura FROM no_substituir")
    no_sub = {r[0] for r in cur.fetchall()}

    cur.execute("SELECT data, hora, grups FROM grups_alliberats")
    grups_all = defaultdict(lambda: defaultdict(list))
    for r in cur.fetchall():
        grups_all[r[0]][r[1]].append(r[2])

    return conn, no_sub, dict(grups_all)


def _es_substitucio_real(s: dict, no_sub: set, grups_all: dict) -> bool:
    assignatura = (s.get("assignatura") or "").strip()
    if not assignatura or assignatura in no_sub:
        return False
    if s["tipus_absencia"] in ("ENCADENADA", "VIGILANCIA"):
        return False
    grup = (s.get("grup") or "").strip()
    if grup:
        grups_hora = grups_all.get(s.get("data", ""), {}).get(s.get("hora", ""), [])
        if grup in grups_hora:
            return False
    return True


def _carregar_nivells_grups(institucio: str) -> tuple:
    """Mapa grup -> nivell i ordre de nivells segons la configuració d'exàmens del centre.

    Font de veritat: el master config (nivells/grups/abreviatures), el mateix que gestiona
    la configuració d'exàmens. Cada centre anomena nivells i grups a la seva manera, així que
    no s'infereix res del nom del grup.

    Retorna (ordre_nivells, grup2nivell):
      - ordre_nivells: nivells en l'ordre configurat + "Altres" al final
      - grup2nivell: codi de grup -> nivell ("Altres" per GENERAL/RECERCA i desconeguts)
    """
    from database import get_data_db_session
    ALTRES = "Altres"
    EXCLOSOS = {"GENERAL", "RECERCA"}
    try:
        with get_data_db_session(institucio) as db:
            master = MasterConfigRepository.get_master_config(db)
    except Exception:
        return [ALTRES], {}

    nivells = master.get("nivells", {})  # {codi: {"grups": [...], ...}}, ja ordenat
    grup2nivell = {}
    ordre_nivells = []
    for codi, data in nivells.items():
        if codi in EXCLOSOS:
            nom_niv = ALTRES
        else:
            nom_niv = codi
            ordre_nivells.append(codi)
        for g in data.get("grups", []):
            grup2nivell[g] = nom_niv

    # Grups combinats (abreviatures): hereten el nivell del primer grup original conegut.
    for originals, abreviatura in master.get("abreviatures", {}).items():
        if abreviatura in grup2nivell:
            continue
        for og in (originals or "").split(","):
            og = og.strip()
            if og in grup2nivell:
                grup2nivell[abreviatura] = grup2nivell[og]
                break

    ordre_nivells.append(ALTRES)
    return ordre_nivells, grup2nivell


def _calcular_dades_direccio(data_inici: str, data_final: str, hores_xml: list, institucio: str,
                             lang: str = "ca") -> dict:
    conn, no_sub, grups_all = _get_db_and_helpers(institucio)
    cur = conn.cursor()
    mesos_nom = MESOS.get(lang, MESOS["ca"])

    cur.execute("SELECT * FROM substitucions WHERE data >= ? AND data <= ?",
                (data_inici, data_final))
    subs = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT * FROM professors_baixa ORDER BY data_inici")
    baixes = [dict(r) for r in cur.fetchall()]

    conn.close()

    subs_reals     = [s for s in subs if _es_substitucio_real(s, no_sub, grups_all)]
    subs_assignades = [s for s in subs_reals if (s.get("substitut") or "").strip()]

    absencies = [s for s in subs_reals if s["tipus_absencia"] == "ABSENCIA"]
    serveis   = [s for s in subs_reals if s["tipus_absencia"] == "SERVEI"]
    profs_baixa = {b["professor"] for b in baixes}

    cobertura = len(subs_assignades) / len(subs_reals) * 100 if subs_reals else 0

    stats = {
        "total_absencies":     len(absencies),
        "total_serveis":       len(serveis),
        "total_baixes":        len(baixes),
        "total_substitucions": len(subs_assignades),
        "total_necessiten":    len(subs_reals),
        "cobertura_pct":       cobertura,
        "dies_actius":         len({s["data"] for s in subs_reals}),
    }

    # Per mes
    per_mes_raw = defaultdict(lambda: {"absencies": 0, "serveis": 0, "substitucions": 0})
    for s in subs_reals:
        try:
            d = datetime.strptime(s["data"], "%Y-%m-%d")
            clau = (d.year, d.month)
        except Exception:
            continue
        if s["tipus_absencia"] == "ABSENCIA":
            per_mes_raw[clau]["absencies"] += 1
        elif s["tipus_absencia"] == "SERVEI":
            per_mes_raw[clau]["serveis"] += 1
        if (s.get("substitut") or "").strip():
            per_mes_raw[clau]["substitucions"] += 1

    per_mes = []
    for (any_, mes), v in sorted(per_mes_raw.items()):
        total_m = v["absencies"] + v["serveis"]
        per_mes.append({
            "mes": f"{mesos_nom[mes]} {any_}",
            "absencies":     v["absencies"],
            "serveis":       v["serveis"],
            "substitucions": v["substitucions"],
            "cobertura":     v["substitucions"] / total_m * 100 if total_m else 0,
        })

    mesos_ordenats = [m["mes"] for m in per_mes]

    # Professors
    prof_abs = defaultdict(lambda: {"absencies": 0, "serveis": 0})
    for s in subs_reals:
        prof = (s.get("professor_absent") or "").strip()
        if not prof:
            continue
        if s["tipus_absencia"] == "ABSENCIA":
            prof_abs[prof]["absencies"] += 1
        elif s["tipus_absencia"] == "SERVEI":
            prof_abs[prof]["serveis"] += 1

    professors_absencies = sorted([
        {"nom": p, **v, "total": v["absencies"] + v["serveis"]}
        for p, v in prof_abs.items()
    ], key=lambda x: x["total"], reverse=True)

    prof_subs = defaultdict(int)
    for s in subs_reals:
        sub = (s.get("substitut") or "").strip()
        if sub:
            prof_subs[sub] += 1

    professors_substitucions = sorted([
        {"nom": p, "total": n} for p, n in prof_subs.items()
    ], key=lambda x: x["total"], reverse=True)

    # Per dia/hora
    per_dia = defaultdict(lambda: {"absencies": 0, "substitucions": 0})
    per_hora = defaultdict(lambda: {"absencies": 0, "substitucions": 0})
    per_dia_hora = defaultdict(lambda: {"absencies": 0, "substitucions": 0})
    for s in subs_reals:
        try:
            # Clau canònica neutra d'idioma: índex del dia de la setmana (0=dilluns).
            # La traducció a nom de dia es fa només al render del PDF.
            dia = datetime.strptime(s["data"], "%Y-%m-%d").weekday()
        except Exception:
            continue
        hora = _normalitzar_hora(s.get("hora", "") or "") or "Desconeguda"
        cobert = bool((s.get("substitut") or "").strip())
        per_dia[dia]["absencies"] += 1
        per_hora[hora]["absencies"] += 1
        per_dia_hora[(dia, hora)]["absencies"] += 1
        if cobert:
            per_dia[dia]["substitucions"] += 1
            per_hora[hora]["substitucions"] += 1
            per_dia_hora[(dia, hora)]["substitucions"] += 1

    # Matrius professor × mes
    top_profs = [p["nom"] for p in professors_absencies[:20]]
    top_subs  = [p["nom"] for p in professors_substitucions[:20]]
    per_professor_mes_abs  = {p: {m: 0 for m in mesos_ordenats} for p in top_profs}
    per_professor_mes_serv = {p: {m: 0 for m in mesos_ordenats} for p in top_profs}
    per_substitut_mes      = {p: {m: 0 for m in mesos_ordenats} for p in top_subs}

    for s in subs_reals:
        prof = (s.get("professor_absent") or "").strip()
        if prof not in per_professor_mes_abs:
            continue
        try:
            d = datetime.strptime(s["data"], "%Y-%m-%d")
            mes_str = f"{mesos_nom[d.month]} {d.year}"
        except Exception:
            continue
        if mes_str not in mesos_ordenats:
            continue
        if s["tipus_absencia"] == "ABSENCIA":
            per_professor_mes_abs[prof][mes_str] += 1
        elif s["tipus_absencia"] == "SERVEI":
            per_professor_mes_serv[prof][mes_str] += 1

    for s in subs_reals:
        sub = (s.get("substitut") or "").strip()
        if sub not in per_substitut_mes:
            continue
        try:
            d = datetime.strptime(s["data"], "%Y-%m-%d")
            mes_str = f"{mesos_nom[d.month]} {d.year}"
        except Exception:
            continue
        if mes_str in mesos_ordenats:
            per_substitut_mes[sub][mes_str] += 1

    # Grups — nivell segons la configuració d'exàmens del centre (no s'infereix del nom)
    ORDRE_NIVELLS, grup2nivell = _carregar_nivells_grups(institucio)

    def _nivell(g):
        return grup2nivell.get(g, "Altres")
    per_grup = defaultdict(lambda: {"absencies": 0, "cobertes": 0})
    per_grup_mes = {}
    for s in subs_reals:
        grup = (s.get("grup") or "").strip()
        if not grup or grup == "-":
            continue
        per_grup[grup]["absencies"] += 1
        if (s.get("substitut") or "").strip():
            per_grup[grup]["cobertes"] += 1
        try:
            d = datetime.strptime(s["data"], "%Y-%m-%d")
            mes_str = f"{mesos_nom[d.month]} {d.year}"
        except Exception:
            continue
        if grup not in per_grup_mes:
            per_grup_mes[grup] = {m: 0 for m in mesos_ordenats}
        if mes_str in mesos_ordenats:
            per_grup_mes[grup][mes_str] += 1

    per_nivell = defaultdict(lambda: {"absencies": 0, "cobertes": 0, "grups": set()})
    for grup, v in per_grup.items():
        niv = _nivell(grup)
        per_nivell[niv]["absencies"] += v["absencies"]
        per_nivell[niv]["cobertes"]  += v["cobertes"]
        per_nivell[niv]["grups"].add(grup)

    grups_data = {
        "per_nivell": {
            niv: {
                "absencies": v["absencies"], "cobertes": v["cobertes"],
                "pendents": v["absencies"] - v["cobertes"],
                "pct": round(v["cobertes"] / v["absencies"] * 100) if v["absencies"] else 0,
                "n_grups": len(v["grups"]),
            } for niv, v in per_nivell.items()
        },
        "ordre_nivells": ORDRE_NIVELLS,
        "per_grup_mes": per_grup_mes,
        "mesos": mesos_ordenats,
        "grups_ordenats": sorted(
            [{"nom": g, **v, "pendents": v["absencies"] - v["cobertes"],
              "pct": round(v["cobertes"] / v["absencies"] * 100) if v["absencies"] else 0,
              "nivell": _nivell(g)}
             for g, v in per_grup.items()],
            key=lambda x: (ORDRE_NIVELLS.index(x["nivell"])
                           if x["nivell"] in ORDRE_NIVELLS else 99, x["nom"])
        ),
    }

    return {
        "stats": stats,
        "per_mes": per_mes,
        "professors_absencies": professors_absencies,
        "professors_substitucions": professors_substitucions,
        "per_dia": dict(per_dia),
        "per_hora": dict(per_hora),
        "per_dia_hora": dict(per_dia_hora),
        "per_professor_mes_abs": per_professor_mes_abs,
        "per_professor_mes_serv": per_professor_mes_serv,
        "per_substitut_mes": per_substitut_mes,
        "mesos_ordenats": mesos_ordenats,
        "hores_ordre": hores_xml,
        "grups_data": grups_data,
    }


def _calcular_dades_professors(data_inici: str, data_final: str,
                                institucio: str, professor: str = None) -> list:
    conn, no_sub, grups_all = _get_db_and_helpers(institucio)
    cur = conn.cursor()
    cur.execute("SELECT * FROM substitucions WHERE data >= ? AND data <= ?",
                (data_inici, data_final))
    subs = [dict(r) for r in cur.fetchall()]
    conn.close()

    subs_reals = [s for s in subs if _es_substitucio_real(s, no_sub, grups_all)]

    per_absent = defaultdict(list)
    per_substitut = defaultdict(list)
    for s in subs_reals:
        prof = (s.get("professor_absent") or "").strip()
        if prof:
            per_absent[prof].append(s)
        sub = (s.get("substitut") or "").strip()
        if sub:
            per_substitut[sub].append(s)

    tots = sorted(set(per_absent.keys()) | set(per_substitut.keys()))
    if professor:
        tots = [p for p in tots if professor.lower() in p.lower()]

    return [
        {"nom": p,
         "absencies": per_absent.get(p, []),
         "substitucions_fetes": per_substitut.get(p, [])}
        for p in tots
    ]


def _get_idioma(institucio: str) -> str:
    from database import get_data_db_session
    try:
        with get_data_db_session(institucio) as db:
            return ConfiguracioRepository.get(db, "idioma") or "ca"
    except Exception:
        return "ca"


def _get_nom_centre(institucio: str) -> str:
    """Retorna el nom visible de la institució des de la config, o el slug si no hi ha."""
    from database import get_data_db_session
    try:
        with get_data_db_session(institucio) as db:
            name = ConfiguracioRepository.get(db, "institucio_display_name")
            return name or institucio
    except Exception:
        return institucio


def _get_hores_xml(institucio: str) -> list:
    """Retorna les hores en l'ordre original del XML actiu per a la institució."""
    import xml.etree.ElementTree as ET
    from helpers import get_xml_path_for_date
    xml_path = get_xml_path_for_date(institucio)
    if not xml_path or not Path(xml_path).exists():
        return []
    hores = []
    try:
        for teacher in ET.parse(xml_path).getroot().findall("Teacher"):
            for day in teacher.findall("Day"):
                for hour in day.findall("Hour"):
                    h = _normalitzar_hora(hour.get("name", "").strip())
                    if h and h not in hores:
                        hores.append(h)
            if hores:
                break  # Un professor n'hi ha prou per l'ordre
    except Exception:
        pass
    return hores


@router.get("/direccio")
async def informe_direccio(
    data_inici: str = Query(...),
    data_final: str = Query(...),
    current_user=Depends(require_admin),
):
    institucio = current_user.institucio
    nom_centre = _get_nom_centre(institucio)
    lang = _get_idioma(institucio)
    hores_xml = _get_hores_xml(institucio)
    dades = _calcular_dades_direccio(data_inici, data_final, hores_xml, institucio, lang)
    export_dir = str(get_export_dir_for_institucio(institucio))
    data_dir = get_data_dir_for_institucio(institucio)
    logo_path = data_dir / "logo.png"
    pdf_path = generar_informe_pdf(
        dades=dades,
        nom_centre=nom_centre,
        data_inici=data_inici,
        data_final=data_final,
        export_dir=export_dir,
        logo_path=str(logo_path) if logo_path.exists() else None,
        lang=lang,
    )
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"informe_direccio_{data_inici}_{data_final}.pdf",
    )


@router.get("/professor")
async def informe_professor(
    data_inici: str = Query(...),
    data_final: str = Query(...),
    professor: str = Query(default=None),
    mostrar_taules: bool = Query(default=False),
    current_user=Depends(require_admin),
):
    institucio = current_user.institucio
    nom_centre = _get_nom_centre(institucio)
    lang = _get_idioma(institucio)
    hores_xml = _get_hores_xml(institucio)
    professors_data = _calcular_dades_professors(data_inici, data_final, institucio, professor)
    if not professors_data:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Cap professor trobat")

    export_dir = str(get_export_dir_for_institucio(institucio))
    pdf_path = generar_informe_professors_pdf(
        professors_data=professors_data,
        nom_centre=nom_centre,
        data_inici=data_inici,
        data_final=data_final,
        hores_xml=hores_xml,
        mostrar_taules=mostrar_taules,
        export_dir=export_dir,
        lang=lang,
    )
    nom_fitxer = (
        f"informe_{professor}_{data_inici}_{data_final}.pdf"
        if professor else
        f"informe_professors_{data_inici}_{data_final}.pdf"
    )
    return FileResponse(pdf_path, media_type="application/pdf", filename=nom_fitxer)


@router.get("/professors-llista")
async def llista_professors(
    data_inici: str = Query(...),
    data_final: str = Query(...),
    current_user=Depends(require_admin),
):
    """Retorna la llista de professors amb activitat al període"""
    professors_data = _calcular_dades_professors(data_inici, data_final, current_user.institucio)
    return {"professors": [p["nom"] for p in professors_data]}
