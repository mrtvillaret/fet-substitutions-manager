"""
Servei de governança de dades (RGPD).

Operacions transversals que toquen diverses taules i fitxers i que, per la seva
naturalesa (esborrat i anonimització), s'agrupen aquí per facilitar-ne
l'auditoria en un únic lloc.

Purga per interval de dates: "purgar" vol dir eliminar TOT rastre de dades
d'un interval — registres de BD, PDF exportats, versions d'XML i baixes.
Per seguretat es fa en dos passos:

1. analitzar_purga()  → només lectura: retorna un MANIFEST de tot el que
   s'esborraria, marcant el que és delicat (XML actiu, XML que s'estén fora de
   l'interval, PDF que no es poden datar pel nom).
2. executar_purga()   → (pendent) esborra segons el manifest confirmat.
"""
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

# Nom persistit dels PDF operatius: {YYMMDD}_{tipus}_{YYMMDD}_{HHMMSS}.pdf
# La primera data és la del CONTINGUT (el dia al qual es refereix el document).
_PDF_DATAT_RE = re.compile(
    r'^(\d{6})_(substitucions_vigilancies|substitucions|vigilancies|document_buit)'
    r'_\d{6}_\d{6}\.pdf$'
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
    from models import Professor
    profs = db.query(Professor).order_by(
        Professor.actiu.desc(), Professor.nom).all()
    return [{"nom": p.nom, "actiu": bool(p.actiu)} for p in profs]


def reanomena_professor(db: Session, nom_actual: str, nom_nou: str) -> Dict[str, int]:
    """
    Reanomena (anonimitza) un professor a TOTES les taules on apareix el nom.

    Només es permet per a professors INACTIUS (que ja no són a l'XML actual):
    si es reanomenés un professor actiu, la propera sincronització amb l'XML
    tornaria a crear el nom original i partiria el seu històric.

    Conserva els registres (i la càrrega de treball dels altres professors
    implicats); només substitueix la identitat.
    """
    from models import (
        Professor, Substitucio, Vigilancia, ProfessorBaixa, ExamCostProfessor
    )

    nom_actual = (nom_actual or "").strip()
    nom_nou = (nom_nou or "").strip()

    if not nom_actual or not nom_nou:
        raise ValueError("Cal indicar el nom actual i el nom nou.")
    if nom_actual == nom_nou:
        raise ValueError("El nom nou ha de ser diferent de l'actual.")

    prof = db.query(Professor).filter(Professor.nom == nom_actual).first()
    if not prof:
        raise ValueError(f"No existeix cap professor amb el nom «{nom_actual}».")
    if prof.actiu:
        raise ValueError(
            "Només es poden reanomenar professors inactius (que ja no són a "
            "l'horari actual). Per canviar el nom d'un professor actiu, "
            "modifica'l a FET i reimporta l'XML."
        )
    if db.query(Professor).filter(Professor.nom == nom_nou).first():
        raise ValueError(f"Ja existeix un professor amb el nom «{nom_nou}».")

    counts = {
        "substitucions_absent": db.query(Substitucio)
            .filter(Substitucio.professor_absent == nom_actual)
            .update({Substitucio.professor_absent: nom_nou}, synchronize_session=False),
        "substitucions_substitut": db.query(Substitucio)
            .filter(Substitucio.substitut == nom_actual)
            .update({Substitucio.substitut: nom_nou}, synchronize_session=False),
        "vigilancies": db.query(Vigilancia)
            .filter(Vigilancia.vigilant == nom_actual)
            .update({Vigilancia.vigilant: nom_nou}, synchronize_session=False),
        "baixes": db.query(ProfessorBaixa)
            .filter(ProfessorBaixa.professor == nom_actual)
            .update({ProfessorBaixa.professor: nom_nou}, synchronize_session=False),
        "costos_examens": db.query(ExamCostProfessor)
            .filter(ExamCostProfessor.professor == nom_actual)
            .update({ExamCostProfessor.professor: nom_nou}, synchronize_session=False),
    }
    prof.nom = nom_nou
    counts["professor"] = 1
    db.commit()
    return counts


def analitzar_purga(db: Session, institucio: Optional[str],
                    data_inici: date, data_final: date) -> Dict:
    """
    MANIFEST (només lectura) de tot el que eliminaria una purga de l'interval
    [data_inici, data_final] (inclòs). No esborra res.
    """
    from models import Substitucio, Vigilancia, GrupAlliberat, ProfessorBaixa, XMLVersion

    if data_inici > data_final:
        raise ValueError("La data d'inici no pot ser posterior a la data final.")

    # --- Registres de BD (per columna 'data') ---
    bd = {
        "substitucions": db.query(Substitucio).filter(
            Substitucio.data >= data_inici, Substitucio.data <= data_final).count(),
        "vigilancies": db.query(Vigilancia).filter(
            Vigilancia.data >= data_inici, Vigilancia.data <= data_final).count(),
        "grups_alliberats": db.query(GrupAlliberat).filter(
            GrupAlliberat.data >= data_inici, GrupAlliberat.data <= data_final).count(),
        # Baixes: se solapen amb l'interval (toquen alguna data del rang)
        "baixes": db.query(ProfessorBaixa).filter(
            ProfessorBaixa.data_inici <= data_final,
            ProfessorBaixa.data_final >= data_inici).count(),
    }

    # --- PDF exportats ---
    pdfs_a_esborrar: List[Dict] = []
    pdfs_revisio_manual: List[str] = []
    export_dir = None
    try:
        from database import get_export_dir_for_institucio
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
    for v in db.query(XMLVersion).order_by(XMLVersion.data_inici).all():
        v_fi = v.data_fi  # None = versió oberta/activa
        solapa = (v.data_inici <= data_final) and (v_fi is None or v_fi >= data_inici)
        if not solapa:
            continue
        activa = v_fi is None
        s_esten_fora = activa or (v.data_inici < data_inici) or (
            v_fi is not None and v_fi > data_final)
        # Només s'esborren automàticament les versions 100% contingudes dins
        # l'interval. Les que s'estenen fora (o l'activa) es mantenen bloquejades
        # per no afectar dates de fora de l'interval ni deixar l'app sense horari.
        xml_versions.append({
            "id": v.id,
            "path": v.path,
            "data_inici": v.data_inici.isoformat(),
            "data_fi": v_fi.isoformat() if v_fi else None,
            "activa": activa,
            "s_esten_fora": s_esten_fora,
            "bloquejat": s_esten_fora,
        })

    total_bd = sum(bd.values())
    return {
        "interval": {"inici": data_inici.isoformat(), "final": data_final.isoformat()},
        "bd": bd,
        "total_bd": total_bd,
        "pdfs_a_esborrar": pdfs_a_esborrar,
        "pdfs_revisio_manual": pdfs_revisio_manual,
        "xml_versions": xml_versions,
    }


def executar_purga(db: Session, institucio: Optional[str],
                   data_inici: date, data_final: date) -> Dict:
    """
    Executa la purga de l'interval [data_inici, data_final] (inclòs).

    Esborra:
    - Registres de BD: substitucions, vigilàncies i grups alliberats amb data
      dins l'interval, i baixes que hi solapin.
    - PDF datats amb contingut dins l'interval.
    - Versions d'XML 100% contingudes dins l'interval (fila + fitxer al disc).

    NO toca: PDF sense data al nom (revisió manual) ni versions d'XML bloquejades
    (l'activa o les que s'estenen fora de l'interval).

    Retorna un informe del que s'ha esborrat realment.
    """
    from models import Substitucio, Vigilancia, GrupAlliberat, ProfessorBaixa, XMLVersion

    # El manifest és la font de veritat: es recalcula al servidor, no es fia del
    # client, i determina quins PDF i quines versions d'XML es toquen.
    manifest = analitzar_purga(db, institucio, data_inici, data_final)

    # --- Registres de BD ---
    bd_esborrat = {
        "substitucions": db.query(Substitucio).filter(
            Substitucio.data >= data_inici, Substitucio.data <= data_final
        ).delete(synchronize_session=False),
        "vigilancies": db.query(Vigilancia).filter(
            Vigilancia.data >= data_inici, Vigilancia.data <= data_final
        ).delete(synchronize_session=False),
        "grups_alliberats": db.query(GrupAlliberat).filter(
            GrupAlliberat.data >= data_inici, GrupAlliberat.data <= data_final
        ).delete(synchronize_session=False),
        "baixes": db.query(ProfessorBaixa).filter(
            ProfessorBaixa.data_inici <= data_final,
            ProfessorBaixa.data_final >= data_inici
        ).delete(synchronize_session=False),
    }

    errors: List[str] = []

    # --- Versions d'XML no bloquejades: fila + fitxer al disc ---
    data_dir = None
    export_dir = None
    try:
        from database import get_data_dir_for_institucio, get_export_dir_for_institucio
        if institucio:
            data_dir = get_data_dir_for_institucio(institucio)
            export_dir = get_export_dir_for_institucio(institucio)
    except Exception as e:
        errors.append(f"No s'han pogut resoldre les carpetes de la institució: {e}")

    ids_esborrar = [v["id"] for v in manifest["xml_versions"] if not v["bloquejat"]]
    xml_esborrats: List[Dict] = []
    if ids_esborrar:
        # Paths que es conserven (per no esborrar un fitxer compartit amb una
        # versió que es manté).
        paths_conservats = {
            p.path for p in db.query(XMLVersion).filter(
                ~XMLVersion.id.in_(ids_esborrar)).all()
        }
        for v in db.query(XMLVersion).filter(XMLVersion.id.in_(ids_esborrar)).all():
            if data_dir is not None and v.path and v.path not in paths_conservats:
                fpath = Path(v.path)
                if not fpath.is_absolute():
                    fpath = data_dir / v.path
                try:
                    if fpath.exists():
                        fpath.unlink()
                except OSError as e:
                    errors.append(f"XML {v.path}: {e}")
            xml_esborrats.append({
                "id": v.id,
                "data_inici": v.data_inici.isoformat(),
                "data_fi": v.data_fi.isoformat() if v.data_fi else None,
            })
            db.delete(v)

    # --- PDF datats dins l'interval ---
    pdfs_esborrats: List[str] = []
    if export_dir:
        for item in manifest["pdfs_a_esborrar"]:
            fpath = Path(export_dir) / item["fitxer"]
            try:
                if fpath.exists():
                    fpath.unlink()
                pdfs_esborrats.append(item["fitxer"])
            except OSError as e:
                errors.append(f"PDF {item['fitxer']}: {e}")

    db.commit()

    return {
        "interval": manifest["interval"],
        "bd": bd_esborrat,
        "total_bd": sum(bd_esborrat.values()),
        "pdfs_esborrats": pdfs_esborrats,
        "pdfs_revisio_manual": manifest["pdfs_revisio_manual"],
        "xml_esborrats": xml_esborrats,
        "xml_bloquejats": [v for v in manifest["xml_versions"] if v["bloquejat"]],
        "errors": errors,
    }
