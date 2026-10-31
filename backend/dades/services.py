"""
Servei de governança de dades (RGPD).

Operacions transversals que toquen diverses taules i fitxers i que, per la seva
naturalesa (esborrat i anonimització), s'agrupen aquí per facilitar-ne
l'auditoria en un únic lloc.

Purga per interval de dates: "purgar" vol dir eliminar TOT rastre de dades
d'un interval — registres de BD, PDF exportats, versions d'XML, baixes i el
que en recorda el planificador d'exàmens (dates triades i últim horari).
Per seguretat es fa en dos passos:

1. analitzar_purga()  → només lectura: retorna un MANIFEST de tot el que
   s'esborraria, marcant el que és delicat (XML actiu, XML que s'estén fora de
   l'interval, PDF que no es poden datar pel nom).
2. executar_purga()   → esborra segons el manifest, que es recalcula al servidor.
"""

import json
import logging
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from dades.repositories import ProfessorsRepository, PurgaRepository
from database import get_data_dir_for_institucio, get_export_dir_for_institucio
from errors_domini import NoValid
from horari.repositories import XMLVersionRepository
from repositories import ConfiguracioRepository

log = logging.getLogger(__name__)

# Nom persistit dels PDF operatius: {YYMMDD}_{tipus}_{YYMMDD}_{HHMMSS}.pdf
# La primera data és la del CONTINGUT (el dia al qual es refereix el document).
_PDF_DATAT_RE = re.compile(
    r"^(\d{6})_(substitucions_vigilancies|substitucions|vigilancies|document_buit)"
    r"_\d{6}_\d{6}\.pdf$"
)


def _pdf_content_date(filename: str) -> Optional[date]:
    """Retorna la data de contingut d'un PDF operatiu a partir del nom, o None
    si el nom no segueix el patró datat (p. ex. informes sense data al nom)."""
    m = _PDF_DATAT_RE.match(filename)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%y%m%d").date()
    except ValueError:
        return None


def llista_professors_db(db: Session) -> List[Dict]:
    """Professors de la BD (històric) amb el flag actiu, ordenats: actius primer."""
    return [{"nom": p.nom, "actiu": bool(p.actiu)} for p in ProfessorsRepository.llista(db)]


def reanomena_professor(db: Session, nom_actual: str, nom_nou: str) -> Dict[str, int]:
    """
    Reanomena (anonimitza) un professor a TOTES les taules on apareix el nom.

    Només es permet per a professors INACTIUS (que ja no són a l'XML actual):
    si es reanomenés un professor actiu, la propera sincronització amb l'XML
    tornaria a crear el nom original i partiria el seu històric.

    Conserva els registres (i la càrrega de treball dels altres professors
    implicats); només substitueix la identitat.
    """
    nom_actual = (nom_actual or "").strip()
    nom_nou = (nom_nou or "").strip()

    if not nom_actual or not nom_nou:
        raise NoValid("Cal indicar el nom actual i el nom nou.", codi="noms_buits")
    if nom_actual == nom_nou:
        raise NoValid("El nom nou ha de ser diferent de l'actual.", codi="mateix_nom")

    prof = ProfessorsRepository.get_by_nom(db, nom_actual)
    if not prof:
        raise NoValid(f"No existeix cap professor amb el nom «{nom_actual}».", codi="professor_inexistent")
    if prof.actiu:
        raise NoValid(
            "Només es poden reanomenar professors inactius (que ja no són a "
            "l'horari actual). Per canviar el nom d'un professor actiu, "
            "modifica'l a FET i reimporta l'XML.",
            codi="professor_actiu",
        )
    if ProfessorsRepository.get_by_nom(db, nom_nou):
        raise NoValid(f"Ja existeix un professor amb el nom «{nom_nou}».", codi="nom_existent")

    counts = ProfessorsRepository.reanomena_registres(db, nom_actual, nom_nou)
    prof.nom = nom_nou
    counts["professor"] = 1
    db.commit()
    return counts


CLAU_DATES_PLANIFICADOR = "scheduler_selected_dates"
CLAU_ULTIM_HORARI = "scheduler_ultim_resultat"


def _json_config(db: Session, clau: str):
    try:
        return json.loads(ConfiguracioRepository.get(db, clau) or "null")
    except ValueError:
        return None


def _dates_iso(valors) -> List[date]:
    dates = []
    for v in valors or []:
        try:
            dates.append(date.fromisoformat(str(v)[:10]))
        except ValueError:
            pass
    return dates


def _planificador(db: Session, data_inici: date, data_final: date) -> Dict:
    """El que el planificador recorda de l'interval: les dates triades que hi
    cauen i l'últim horari desat si en toca alguna data (s'esborra sencer)."""

    def dins(d):
        return data_inici <= d <= data_final

    dates = _dates_iso(_json_config(db, CLAU_DATES_PLANIFICADOR))

    ultim = _json_config(db, CLAU_ULTIM_HORARI)
    ultim_horari = None
    if isinstance(ultim, dict):
        horari = (ultim.get("resultat") or {}).get("horari") or {}
        # Cada dia porta la seva data (el planificador només genera amb dates)
        dates_horari = _dates_iso(dia.get("data") for dia in horari.get("dies") or [] if isinstance(dia, dict))
        if any(dins(d) for d in dates_horari):
            ultim_horari = {
                "desat": ultim.get("desat"),
                "dates": [d.isoformat() for d in sorted(dates_horari)],
                "s_esten_fora": not all(dins(d) for d in dates_horari),
            }
    return {
        "dates_seleccionades": sum(1 for d in dates if dins(d)),
        "ultim_horari": ultim_horari,
    }


def analitzar_purga(db: Session, institucio: Optional[str], data_inici: date, data_final: date) -> Dict:
    """
    MANIFEST (només lectura) de tot el que eliminaria una purga de l'interval
    [data_inici, data_final] (inclòs). No esborra res.
    """
    if data_inici > data_final:
        raise NoValid("La data d'inici no pot ser posterior a la data final.", codi="interval_invertit")

    # --- Registres de BD (per columna 'data'; absències cobertes que se solapen) ---
    bd = PurgaRepository.compta(db, data_inici, data_final)

    # --- PDF exportats ---
    pdfs_a_esborrar: List[Dict] = []
    pdfs_revisio_manual: List[str] = []
    export_dir = None
    try:
        export_dir = get_export_dir_for_institucio(institucio) if institucio else None
    except Exception:
        export_dir = None

    if export_dir and Path(export_dir).is_dir():
        for f in sorted(os.listdir(export_dir)):
            if not f.lower().endswith(".pdf"):
                continue
            d = _pdf_content_date(f)
            if d is None:
                # informes i altres PDF sense data de contingut al nom
                pdfs_revisio_manual.append(f)
            elif data_inici <= d <= data_final:
                pdfs_a_esborrar.append({"fitxer": f, "data": d.isoformat()})

    # --- Versions d'XML que se solapen amb l'interval ---
    # Es retornen dades estructurades (flags); la presentació dels avisos la fa
    # el frontend a partir d'aquests flags (i18n).
    xml_versions: List[Dict] = []
    for v in XMLVersionRepository.list_all(db):
        v_fi = v.data_fi  # None = versió oberta/activa
        solapa = (v.data_inici <= data_final) and (v_fi is None or v_fi >= data_inici)
        if not solapa:
            continue
        activa = v_fi is None
        s_esten_fora = activa or (v.data_inici < data_inici) or (v_fi is not None and v_fi > data_final)
        # Només s'esborren automàticament les versions 100% contingudes dins
        # l'interval. Les que s'estenen fora (o l'activa) es mantenen bloquejades
        # per no afectar dates de fora de l'interval ni deixar l'app sense horari.
        xml_versions.append(
            {
                "id": v.id,
                "path": v.path,
                "data_inici": v.data_inici.isoformat(),
                "data_fi": v_fi.isoformat() if v_fi else None,
                "activa": activa,
                "s_esten_fora": s_esten_fora,
                "bloquejat": s_esten_fora,
            }
        )

    # Les baixes que toquen l'interval s'esborren senceres: el detall permet
    # avisar de les que s'estenen fora.
    baixes = [
        {
            "professor": b.professor,
            "data_inici": b.data_inici.isoformat(),
            "data_final": b.data_final.isoformat(),
            "s_esten_fora": b.data_inici < data_inici or b.data_final > data_final,
        }
        for b in PurgaRepository.absencies_cobertes(db, data_inici, data_final)
    ]

    total_bd = sum(bd.values())
    return {
        "interval": {"inici": data_inici.isoformat(), "final": data_final.isoformat()},
        "bd": bd,
        "total_bd": total_bd,
        "baixes": baixes,
        "planificador": _planificador(db, data_inici, data_final),
        "pdfs_a_esborrar": pdfs_a_esborrar,
        "pdfs_revisio_manual": pdfs_revisio_manual,
        "xml_versions": xml_versions,
    }


def executar_purga(
    db: Session, institucio: Optional[str], data_inici: date, data_final: date, confirmar: bool = False
) -> Dict:
    """
    Executa la purga de l'interval [data_inici, data_final] (inclòs). És
    irreversible: cal `confirmar`.

    Esborra:
    - Registres de BD: substitucions, vigilàncies i grups alliberats amb data
      dins l'interval, i baixes que hi solapin.
    - PDF datats amb contingut dins l'interval.
    - Versions d'XML 100% contingudes dins l'interval (fila + fitxer al disc).
    - Planificador: les dates triades de dins l'interval i l'últim horari desat
      si en toca alguna (sencer).

    NO toca: PDF sense data al nom (revisió manual) ni versions d'XML bloquejades
    (l'activa o les que s'estenen fora de l'interval).

    Retorna un informe del que s'ha esborrat realment.
    """
    if not confirmar:
        raise NoValid("Cal confirmar l'operació (confirmar=true). És irreversible.", codi="purga_sense_confirmar")

    # El manifest és la font de veritat: es recalcula al servidor, no es fia del
    # client, i determina quins PDF i quines versions d'XML es toquen.
    manifest = analitzar_purga(db, institucio, data_inici, data_final)

    # --- Registres de BD ---
    bd_esborrat = PurgaRepository.esborra(db, data_inici, data_final)

    errors: List[str] = []

    # --- Versions d'XML no bloquejades: fila + fitxer al disc ---
    data_dir = None
    export_dir = None
    try:
        if institucio:
            data_dir = get_data_dir_for_institucio(institucio)
            export_dir = get_export_dir_for_institucio(institucio)
    except Exception:
        # A la resposta, només el missatge; el detall (pot portar camins del servidor), al registre
        log.warning("Purga: no s'han pogut resoldre les carpetes del centre", exc_info=True)
        errors.append("No s'han pogut resoldre les carpetes de la institució")

    # Els fitxers s'esborren després del commit: si la BD fallés, les versions
    # i els fitxers hi serien tots dos
    fitxers_xml: List[tuple] = []  # (camí, path de la versió)

    ids_esborrar = [v["id"] for v in manifest["xml_versions"] if not v["bloquejat"]]
    xml_esborrats: List[Dict] = []
    if ids_esborrar:
        # Paths que es conserven (per no esborrar un fitxer compartit amb una
        # versió que es manté).
        paths_conservats = PurgaRepository.paths_xml_excepte(db, ids_esborrar)
        for v in PurgaRepository.versions_xml(db, ids_esborrar):
            if data_dir is not None and v.path and v.path not in paths_conservats:
                carpeta = data_dir.resolve()
                fpath = (carpeta / v.path).resolve()
                if not fpath.is_relative_to(carpeta):
                    # Només els fitxers del centre (com a helpers._resolve_xml_path)
                    errors.append(f"XML {v.path}: fora de la carpeta del centre, no s'esborra")
                else:
                    fitxers_xml.append((fpath, v.path))
            xml_esborrats.append(
                {
                    "id": v.id,
                    "data_inici": v.data_inici.isoformat(),
                    "data_fi": v.data_fi.isoformat() if v.data_fi else None,
                }
            )
            db.delete(v)
        # Les que queden s'encadenen de nou: sense forats on hi havia les esborrades
        XMLVersionRepository.encadena(db)

    # --- Planificador d'exàmens ---
    planificador = manifest["planificador"]
    if planificador["dates_seleccionades"]:
        queden = [
            d.isoformat()
            for d in _dates_iso(_json_config(db, CLAU_DATES_PLANIFICADOR))
            if not data_inici <= d <= data_final
        ]
        PurgaRepository.canvia_configuracio(db, CLAU_DATES_PLANIFICADOR, json.dumps(queden))
    if planificador["ultim_horari"]:
        PurgaRepository.esborra_configuracio(db, CLAU_ULTIM_HORARI)

    db.commit()

    for fpath, path in fitxers_xml:
        try:
            if fpath.exists():
                fpath.unlink()
        except OSError:
            log.warning("Purga: no s'ha pogut esborrar un XML", exc_info=True)
            errors.append(f"XML {path}: no s'ha pogut esborrar")

    # --- PDF datats dins l'interval ---
    pdfs_esborrats: List[str] = []
    if export_dir:
        for item in manifest["pdfs_a_esborrar"]:
            fpath = Path(export_dir) / item["fitxer"]
            try:
                if fpath.exists():
                    fpath.unlink()
                pdfs_esborrats.append(item["fitxer"])
            except OSError:
                log.warning("Purga: no s'ha pogut esborrar un PDF", exc_info=True)
                errors.append(f"PDF {item['fitxer']}: no s'ha pogut esborrar")

    return {
        "interval": manifest["interval"],
        "planificador": {
            "dates_tretes": planificador["dates_seleccionades"],
            "ultim_horari_esborrat": planificador["ultim_horari"] is not None,
        },
        "bd": bd_esborrat,
        "total_bd": sum(bd_esborrat.values()),
        "pdfs_esborrats": pdfs_esborrats,
        "pdfs_revisio_manual": manifest["pdfs_revisio_manual"],
        "xml_esborrats": xml_esborrats,
        "xml_bloquejats": [v for v in manifest["xml_versions"] if v["bloquejat"]],
        "errors": errors,
    }
