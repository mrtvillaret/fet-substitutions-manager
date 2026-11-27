"""PDF de professors disponibles: un full per dia laborable, amb els
professors que podrien fer una substitució a cada hora (per categoria i
tipus) i, ratllats i amb el motiu, els que són absents o ja estan ocupats."""

import logging
import unicodedata
from collections import defaultdict
from datetime import date, timedelta

from babel.dates import format_date
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer
from sqlalchemy.orm import Session

import i18n_setup
from config import constants
from configuracio.repositories import ConfiguracioRepository
from horari.domain import Dia
from i18n_setup import setup_translation, translate
from pdf.estils import PDFStyleFactory
from pdf.taula import PER_DEFECTE
from prioritats.memoria import categoria_de_prioritat
from substitucions.assignacio import pes_de
from substitucions.domain import DiaEscolar

log = logging.getLogger(__name__)

_DIES_PER_INDEX = (
    {"dilluns", "lunes", "monday", "lundi", "lunedi"},
    {"dimarts", "martes", "tuesday", "mardi", "martedi"},
    {"dimecres", "miercoles", "wednesday", "mercredi", "mercoledi"},
    {"dijous", "jueves", "thursday", "jeudi", "giovedi"},
    {"divendres", "viernes", "friday", "vendredi", "venerdi"},
    {"dissabte", "sabado", "saturday", "samedi", "sabato"},
    {"diumenge", "domingo", "sunday", "dimanche", "domenica"},
)


class DiaNoGenerat(Exception):
    """No s'ha pogut preparar el full d'un dia (el motiu, a la traça)."""

    def __init__(self, dia: date):
        super().__init__(dia)
        self.dia = dia


def _nom_normalitzat(nom: str) -> str:
    sense_accents = unicodedata.normalize("NFKD", nom.casefold())
    return "".join(c for c in sense_accents if not unicodedata.combining(c)).strip()


def nom_dia_xml(horari, data: date) -> str:
    """Nom del dia tal com apareix a l'XML, independentment de la posició."""
    noms_valids = _DIES_PER_INDEX[data.weekday()]
    for nom in horari.dies:
        if _nom_normalitzat(nom) in noms_valids:
            return nom
    raise ValueError(f"L'horari no conté el dia de la setmana de {data.isoformat()}")


def dies_laborables(institucio: str, primer_dia: date) -> list[date]:
    """Tants dies laborables consecutius (des de `primer_dia`, sense caps de
    setmana) com dies té l'horari; si no se'n poden saber, 5."""
    try:
        horari = Dia(primer_dia, institucio).horari
        dies_xml = horari.dies if hasattr(horari, "dies") else []
    except Exception:
        log.warning("No s'ha pogut carregar l'horari per als dies del PDF", exc_info=True)
        dies_xml = []
    num_dies = len(dies_xml) if dies_xml else 5

    dies = []
    actual = primer_dia
    while len(dies) < num_dies:
        if actual.weekday() < 5:  # 0=Dl, 4=Dv
            dies.append(actual)
        actual += timedelta(days=1)
    return dies


def motius_del_dia(dia: DiaEscolar) -> dict[str, dict[str, list[str]]]:
    """Per hora, per què cada professor no està disponible, en aquest ordre:
    «absent» (DiaEscolar.absents_per_hora), «substitueix» i «vigila»."""
    motius: dict[str, dict[str, list[str]]] = defaultdict(dict)

    def afegeix(hora: str, professor: str, motiu: str) -> None:
        del_professor = motius[hora].setdefault(professor, [])
        if motiu not in del_professor:
            del_professor.append(motiu)

    for hora, absents in dia.absents_per_hora.items():
        for professor in absents:
            afegeix(hora, professor, "absent")
    for sub in dia.files:
        hora, substitut = (sub.hora or "").strip(), (sub.substitut or "").strip()
        if hora and substitut:
            afegeix(hora, substitut, "substitueix")
    for hora, vigilants in dia.vigilants_per_hora.items():
        for professor in vigilants:
            afegeix(hora, professor, "vigila")
    return dict(motius)


def linies_de_l_hora(disponibles: list, motius: dict[str, list[str]]) -> list[str]:
    """Una línia per categoria i tipus (per ordre), amb els professors per
    ordre alfabètic: els que no estan disponibles, ratllats i amb el motiu
    (els absents en taronja; els que substitueixen o vigilen, en gris)."""
    perfil = {**PER_DEFECTE, **PDFStyleFactory.get_current_profile_colors()}
    textos = {"absent": translate("absent"), "substitueix": translate("substitueix"), "vigila": translate("vigila")}
    per_categoria_tipus = defaultdict(lambda: defaultdict(list))
    for prof, tipus, _detall in disponibles:
        per_categoria_tipus[categoria_de_prioritat(tipus)][tipus].append(prof)

    linies = []
    for categoria_idx in sorted(per_categoria_tipus.keys()):
        cat_label = f"Cat.{categoria_idx}" if categoria_idx < len(constants.ORDRE_PRIORITATS) else "Cat.99"
        for tipus in sorted(per_categoria_tipus[categoria_idx].keys()):
            pes = pes_de(tipus)
            parts = []
            for prof in sorted(per_categoria_tipus[categoria_idx][tipus]):
                del_professor = motius.get(prof)
                if not del_professor:
                    parts.append(prof)
                    continue
                color = perfil["absent_color"] if "absent" in del_professor else perfil["busy_color"]
                motiu = ", ".join(textos[m] for m in del_professor)
                parts.append(
                    f'<strike><font color="{color}">{prof}</font></strike> <font color="{color}">({motiu})</font>'
                )
            meta = f'<font color="#94a3b8">  - {cat_label}:</font>'
            suffix = f'<font color="#94a3b8"> ({tipus} [{pes}])</font>'
            linies.append(f"{meta} {', '.join(parts)}{suffix}")
    return linies


class _Estils:
    def __init__(self):
        styles = getSampleStyleSheet()
        self.normal = styles["Normal"]
        self.titol = ParagraphStyle(
            "CustomTitle",
            parent=styles["Normal"],
            fontSize=11,
            textColor=colors.HexColor("#64748b"),
            spaceAfter=4,
            alignment=TA_CENTER,
        )
        self.data = ParagraphStyle(
            "CustomDate",
            parent=styles["Heading1"],
            fontSize=20,
            textColor=colors.HexColor("#1e40af"),
            spaceAfter=16,
            leading=24,
            alignment=TA_CENTER,
        )
        self.hora = ParagraphStyle(
            "HoraHeader",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            fontName="Courier-Bold",
            leftIndent=10,
            spaceAfter=2,
        )
        self.contingut = ParagraphStyle(
            "Content",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            fontName="Courier",
            leftIndent=10,
            spaceAfter=6,
        )


def _full_del_dia(db: Session, institucio: str, dia: date, estils: _Estils) -> list:
    """Els blocs de cada hora del dia (cada un, sencer a la mateixa pàgina)."""
    dia_del_centre = Dia.del_centre(dia, institucio)
    _, horari_mgr, alliberats_mgr, _ = dia_del_centre.gestors()
    dia_name_xml = nom_dia_xml(horari_mgr, dia)
    dia_escolar = DiaEscolar(db, dia_del_centre)
    motius = motius_del_dia(dia_escolar)

    blocs = []
    for hora in horari_mgr.hores:
        # Llista completa (sense filtrar) per mostrar tots amb estat
        disponibles = alliberats_mgr.get_tots_disponibles(dia_name_xml, hora, dia_escolar.alliberats.get(hora, []))
        if not disponibles:
            continue
        linies = linies_de_l_hora(disponibles, motius.get(hora, {}))
        blocs.append(KeepTogether([Paragraph(hora, estils.hora), Paragraph("<br/>".join(linies), estils.contingut)]))
    if not blocs:
        blocs.append(Paragraph("<i>No hi ha professors disponibles</i>", estils.normal))
    return blocs


def genera_pdf_disponibles(db: Session, institucio: str, primer_dia: date, pdf_path: str) -> None:
    """Escriu a `pdf_path` un full per a cada dia laborable des de
    `primer_dia`. Si falla un dia, DiaNoGenerat."""
    setup_translation(ConfiguracioRepository.get_all_as_dict(db).get("idioma", "ca"))
    dies = dies_laborables(institucio, primer_dia)

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1 * cm,
        bottomMargin=2 * cm,
    )
    estils = _Estils()
    idioma = i18n_setup.idioma_actual()

    story = []
    for idx, dia in enumerate(dies):
        # Capçalera: label petit + data del dia destacada
        titol = translate("📋 Llistat de Professors Substituts").replace("📋 ", "")
        data_dia = format_date(dia, "full", locale=idioma)
        data_dia = data_dia[:1].upper() + data_dia[1:]
        story.append(Paragraph(titol, estils.titol))
        story.append(Paragraph(f"<b>{data_dia}</b>", estils.data))
        story.append(Spacer(1, 0.5 * cm))
        try:
            story.extend(_full_del_dia(db, institucio, dia, estils))
        except Exception as exc:
            log.warning("Error processant el dia %s del PDF de disponibles", dia, exc_info=True)
            raise DiaNoGenerat(dia) from exc
        if idx < len(dies) - 1:  # cada dia en una pàgina
            story.append(PageBreak())

    doc.build(story)
