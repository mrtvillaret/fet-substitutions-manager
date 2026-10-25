"""
Exportador de PDF combinat: Substitucions + Vigilàncies organitzat per hores
VERSIÓ OPTIMITZADA I AMB FORMAT DE CONFLICTES MILLORAT
"""

import html
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table

# import emoji
from i18n_setup import translate as _

from ..pdf_images import pdf_images
from ..pdf_styles import PDFStyleFactory
from .taula import SUBSTITUCIONS, VIGILANCIES, contingut_del_dia


def _text(valor) -> str:
    """Text de les dades (noms, aules, comentaris...) apte per a un Paragraph.

    ReportLab interpreta etiquetes dins dels Paragraph (<b>, <font>, <img
    src=...>): sense escapar, un "<" escrit per un usuari trencava el PDF i un
    <img> li feia llegir fitxers del servidor."""
    return html.escape(str(valor or ""), quote=False)


# PDF Constants
class PDFConstants:
    """Constants for PDF generation"""

    # Sizes
    TABLE_WIDTH = 16 * cm
    SPACER_NORMAL = 0.5 * cm
    SPACER_COMPACT = 0.2 * cm
    SPACER_TINY = 0.01 * cm
    SPACER_SMALL = 0.05 * cm
    SPACER_MEDIUM = 0.1 * cm
    SPACER_LARGE = 0.3 * cm

    # Margins
    MARGIN_NORMAL = 1 * cm
    MARGIN_COMPACT = 0.7 * cm
    MARGIN_COMPACT_SIDE = 0.8 * cm

    # Font reductions
    FONT_REDUCTION_DEFAULT = 0.85
    MIN_FONT_HEADER = 8
    MIN_FONT_BODY = 7
    MIN_FONT_HOUR = 10

    # Pagination thresholds
    THRESHOLD_MIN = 0.75
    THRESHOLD_MAX = 1.5


log = logging.getLogger(__name__)


class PDFCompletExporter:
    """Exportador de PDF combinat optimitzat"""

    def __init__(self, hores: List[str] = None, export_dir: str = "exports", horari_mgr=None):
        self.hores = hores if hores is not None else []
        self.export_dir = Path(export_dir)
        self.horari_mgr = horari_mgr
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self.styles = getSampleStyleSheet()
        self.custom_styles = PDFStyleFactory.get_standard_styles()
        self.table_styles = PDFStyleFactory.get_table_styles()

        # Load hyphenation configuration - profile colors loaded dynamically
        try:
            self.pdf_config = PDFStyleFactory._load_pdf_config()
            self.fonts = self.pdf_config.get("font_sizes", {})
            self.hyphenation_config = self.pdf_config.get("hyphenation", {})
        except Exception:
            self.fonts = {}
            self.hyphenation_config = {"enabled": False}

        # Setup hyphenation if available
        self.hyphen_lang = None
        self.hyphen_language_code = None
        try:
            import pyphen

            if self.hyphenation_config.get("enabled", False):
                self.hyphen_language_code = self.hyphenation_config.get("language", "ca")
                self.hyphen_lang = pyphen.Pyphen(lang=self.hyphen_language_code)
        except ImportError:
            pass
        except Exception as e:
            log.warning(_("Avís: No s'ha pogut carregar la partició de paraules: {error}").format(error=e))
            pass

        # Carregar preferències de columnes opcionals
        self.show_comments_column = self.pdf_config.get("show_comments_column", True)
        self.show_hours_column = self.pdf_config.get("show_hours_column", False)

        # Espai per escriure a mà substitucions d'última hora: totes les hores
        # surten, amb files en blanc a la taula de substitucions.
        self.espai_a_ma = False
        # Hores on hi pot haver alguna substitució (les calcula qui crida, a
        # partir de l'horari): són les que surten amb files en blanc. None = totes.
        self.hores_amb_classe = None
        # Format «taula del dia»: una sola taula, l'hora a la primera columna i
        # les vigilàncies dins de cada hora (en comptes d'una secció per hora)
        self.format_dia = False
        # Mida de la lletra de les taules (factor sobre la normal: 1, 1.2, 1.35)
        self.mida_lletra = 1.0
        # Interval: cada dia en una pàgina nova
        self.dia_per_pagina = False

    @staticmethod
    def _combinada(tipus_pdf: str, substitucions: List[Dict]) -> bool:
        """Substitucions i vigilàncies a la mateixa taula: el PDF complet, i el
        de vigilàncies quan porta les substitucions de vigilància."""
        if tipus_pdf == "complet":
            return True
        return tipus_pdf in ("vigilancies", "vigilancies_interval") and bool(substitucions)

    @staticmethod
    def _tipus_sol(tipus_pdf: str):
        return SUBSTITUCIONS if tipus_pdf == "substitucions" else VIGILANCIES

    def _get_profile_colors(self):
        """Obté colors del perfil actual - sempre actualitzat"""
        return PDFStyleFactory.get_current_profile_colors()

    def _setup_document_config(
        self,
        tipus_pdf: str,
        compact_mode: bool,
        substitucions: List[Dict],
        vigilancies: List[Dict],
        conflictes: List[str],
    ):
        """Setup document configuration"""
        self._pdf_type = tipus_pdf
        self.pdf_config = PDFStyleFactory._load_pdf_config()

        # Manual compression only - automatic logic removed
        # Compression is now controlled manually via the PDF dialog checkbox
        if not hasattr(self, "_auto_compression_active"):
            self._auto_compression_active = False

    def _generate_filename(self, data_iso: str, subs_reals: List[Dict], vigilancies_reals: List[Dict]) -> str:
        """Generate PDF filename"""
        return self.PDFTypeResolver.get_filename(data_iso, subs_reals, vigilancies_reals)

    def _create_document(self, filename: str, compact_mode: bool):
        """Create and configure PDF document"""
        from reportlab.lib.pagesizes import A4

        output_path = self.export_dir / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Marges adaptats segons mode compacte
        if compact_mode:
            top_margin = bottom_margin = PDFConstants.MARGIN_COMPACT
            left_margin = right_margin = PDFConstants.MARGIN_COMPACT_SIDE
        else:
            top_margin = bottom_margin = PDFConstants.MARGIN_NORMAL
            left_margin = right_margin = PDFConstants.MARGIN_NORMAL

        return SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            topMargin=top_margin,
            bottomMargin=bottom_margin,
            leftMargin=left_margin,
            rightMargin=right_margin,
        ), output_path

    def _generate_titles(self, tipus_pdf: str, data_text: str, subs_reals: List[Dict], vigilancies_reals: List[Dict]):
        """Generate PDF titles"""
        from reportlab.platypus import Paragraph

        # Títol principal
        titol_principal = self.PDFTypeResolver.get_title(tipus_pdf, subs_reals, vigilancies_reals)

        # Estil per al títol principal (12pt) - RESTAURAT ORIGINAL
        title_main_style = ParagraphStyle(
            "TitleMain",
            parent=self.custom_styles["title"],
            fontSize=12,
            alignment=1,  # Centrat
            spaceAfter=-25,  # Espai negatiu ajustat
        )

        # Estil per a la data (manté la mida original) - RESTAURAT ORIGINAL
        title_date_style = ParagraphStyle(
            "TitleDate",
            parent=self.custom_styles["title"],
            alignment=1,  # Centrat
            spaceBefore=-10,  # Espai negatiu ajustat abans
            spaceAfter=max(6, int(self.custom_styles["title"].spaceAfter * 0.6))
            if hasattr(self, "_auto_compression_active") and self._auto_compression_active
            else self.custom_styles["title"].spaceAfter,
        )

        return [Paragraph(titol_principal, title_main_style), Paragraph(data_text, title_date_style)]

    class PDFTypeResolver:
        """Resolves PDF type, filename and title"""

        @staticmethod
        def get_filename(data_iso: str, subs_reals: List[Dict], vigilancies_reals: List[Dict]) -> str:
            timestamp = datetime.now().strftime("%y%m%d_%H%M%S")

            if data_iso:
                from utils.date_context import DateContext

                date_ctx = DateContext.from_iso(data_iso)
                data_curta = date_ctx.datetime.strftime("%y%m%d")
            else:
                data_curta = datetime.now().strftime("%y%m%d")

            if subs_reals and vigilancies_reals:
                return f"{data_curta}_substitucions_vigilancies_{timestamp}.pdf"
            elif subs_reals:
                return f"{data_curta}_substitucions_{timestamp}.pdf"
            elif vigilancies_reals:
                return f"{data_curta}_vigilancies_{timestamp}.pdf"
            else:
                return f"{data_curta}_document_buit_{timestamp}.pdf"

        @staticmethod
        def get_title(tipus_pdf: str, subs_reals: List[Dict], vigilancies_reals: List[Dict]) -> str:
            if tipus_pdf == "substitucions":
                return _("SUBSTITUCIONS")
            elif tipus_pdf == "vigilancies":
                return _("VIGILÀNCIES")
            elif tipus_pdf == "vigilancies_interval":
                return _("VIGILÀNCIES")
            elif tipus_pdf == "complet":
                return _("SUBSTITUCIONS I VIGILÀNCIES")
            else:
                # Auto-detect
                if subs_reals and vigilancies_reals:
                    return _("SUBSTITUCIONS I VIGILÀNCIES")
                elif subs_reals:
                    return _("SUBSTITUCIONS")
                elif vigilancies_reals:
                    return _("VIGILÀNCIES")
                else:
                    return _("DOCUMENT BUIT")

    def exportar(
        self,
        substitucions: List[Dict],
        vigilancies: List[Dict],
        data_text: str,
        conflictes: List[str] = None,
        absents: Dict[str, List[str]] = None,
        data_iso: str = None,
        tipus_pdf: str = "auto",
    ) -> str:
        """Genera PDF combinat organitzat per hores"""
        try:
            # Setup configuration
            compact_mode = self.pdf_config.get("single_page_mode", False)
            if conflictes is None:
                if tipus_pdf == "vigilancies_interval":
                    conflictes = self._validar_conflictes_interval(substitucions, vigilancies)
                else:
                    conflictes = self._validar_conflictes_complets(substitucions, vigilancies, absents)

            self._setup_document_config(tipus_pdf, compact_mode, substitucions, vigilancies, conflictes)

            # Process data
            subs_reals = [s for s in substitucions if not s.get("separador")] if substitucions else []

            # Filtra encadenades si és PDF només de vigilàncies
            if tipus_pdf in ["vigilancies", "vigilancies_interval"]:
                # Elimina substitucions encadenades (grup buit + assignatura amb valor)
                subs_reals = [s for s in subs_reals if not (s.get("grup", "") == "" and s.get("assignatura", "") != "")]

            vigilancies_reals = vigilancies

            # Create document
            filename = self._generate_filename(data_iso, subs_reals, vigilancies_reals)
            doc, output_path = self._create_document(filename, compact_mode)

            # Generate content
            story = []
            titles = self._generate_titles(tipus_pdf, data_text, subs_reals, vigilancies_reals)
            story.extend(titles)

            # Les dades ja s'han filtrat abans

            # Format especial per interval de vigilàncies
            if tipus_pdf == "vigilancies_interval":
                story.extend(self._generar_contingut_interval_vigilancies(vigilancies_reals, subs_reals))
            else:
                # El format triat (taula del dia o una secció per hora), amb els
                # mateixos estils (export/pdf/taula.py)
                dades_per_hora = self._organitzar_dades_per_hora(subs_reals, vigilancies_reals)
                espai_a_ma = self.espai_a_ma and tipus_pdf != "vigilancies"
                story.extend(
                    contingut_del_dia(
                        self,
                        dades_per_hora,
                        espai_a_ma,
                        self._combinada(tipus_pdf, subs_reals),
                        self._tipus_sol(tipus_pdf),
                    )
                )

            # Resum simple amb compressió
            if hasattr(self, "_auto_compression_active") and self._auto_compression_active:
                story.append(Spacer(1, PDFConstants.SPACER_COMPACT))  # Espai reduït
            else:
                story.append(Spacer(1, PDFConstants.SPACER_NORMAL))
            # Resum coherent amb el tipus de PDF (no mostrar per intervals)
            if tipus_pdf != "vigilancies_interval":  # No mostrar resum per intervals
                if tipus_pdf == "substitucions":
                    resum = _("RESUM: {num} substitucions").format(num=len(subs_reals))
                elif tipus_pdf == "vigilancies":
                    resum = _("RESUM: {num} vigilàncies").format(num=len(vigilancies_reals))
                elif tipus_pdf == "complet":
                    resum = _("RESUM: {subs} substitucions, {vig} vigilàncies").format(
                        subs=len(subs_reals), vig=len(vigilancies_reals)
                    )
                else:
                    # Fallback: comportament antic
                    resum = _("RESUM: {subs} substitucions, {vig} vigilàncies").format(
                        subs=len(subs_reals), vig=len(vigilancies_reals)
                    )
                story.append(Paragraph(resum, self.styles["Normal"]))

            # Secció de conflictes - SEMPRE en salt de pàgina (no compten per al càlcul de compressió)
            if conflictes:
                from reportlab.platypus import PageBreak

                story.append(PageBreak())  # Salt de pàgina sempre per conflictes

                story.append(Paragraph(_("<b>CONFLICTES DETECTATS:</b>"), self.styles["Heading2"]))
                story.append(Spacer(1, 0.3 * cm))  # Espai normal (nova pàgina)
                story.append(self._crear_taula_conflictes(conflictes))

            # Peu de pàgina amb compressió
            if hasattr(self, "_auto_compression_active") and self._auto_compression_active:
                story.append(Spacer(1, PDFConstants.SPACER_COMPACT))  # Espai reduït abans del peu
            else:
                story.append(Spacer(1, PDFConstants.SPACER_NORMAL))
            footer = Paragraph(
                _("Generat el {data} a les {hora}").format(
                    data=datetime.now().strftime("%d/%m/%Y"), hora=datetime.now().strftime("%H:%M")
                ),
                self.styles["Normal"],
            )
            story.append(footer)

            # Genera PDF amb logo només a la primera pàgina
            doc.build(story, onFirstPage=self._add_logo_to_page)
            return filename

        except Exception as e:
            import traceback

            log.warning(_("❌ Error en generar PDF: {error}").format(error=e))
            traceback.print_exc()
            return ""

    def _add_logo_to_page(self, canvas, doc):
        """Afegeix logo al marge superior esquerre de cada pàgina si existeix"""
        try:
            from pathlib import Path

            from PIL import Image

            from database import get_data_db_session, get_data_dir_for_institucio
            from helpers import _get_institucio_actual
            from repositories import ConfiguracioRepository

            # Logo de la institució de la petició (no el de la institució amb
            # què va arrencar el servidor).
            institucio = _get_institucio_actual()
            with get_data_db_session(institucio) as db:
                configured_logo = ConfiguracioRepository.get(db, "logo_path")
            logo_path = None
            if configured_logo:
                candidate = Path(configured_logo)
                if candidate.exists():
                    logo_path = candidate

            if logo_path is None:
                data_dir = get_data_dir_for_institucio(institucio)
                for name in ("logo.png", "logo.jpg", "logo.jpeg"):
                    candidate = data_dir / name
                    if candidate.exists():
                        logo_path = candidate
                        break

            if logo_path and logo_path.exists():
                if logo_path.suffix.lower() == ".svg":
                    return
                # Carrega la imatge per obtenir les dimensions reals
                img = Image.open(logo_path)
                img_width_px, img_height_px = img.size

                # Converteix píxels a punts (72 DPI estàndard PDF)
                logo_width = img_width_px * 72 / img.info.get("dpi", (72, 72))[0]
                logo_height = img_height_px * 72 / img.info.get("dpi", (72, 72))[1]

                # Posició: 0.5cm del marge superior i esquerre
                x = 0.5 * cm
                y = A4[1] - logo_height - 0.5 * cm

                # Dibuixa el logo amb mida real
                canvas.drawImage(
                    str(logo_path), x, y, width=logo_width, height=logo_height, preserveAspectRatio=True, mask="auto"
                )
        except Exception as e:
            # Si hi ha error, simplement no mostra el logo
            log.warning(f"⚠️ No s'ha pogut carregar el logo: {e}")

    def _crear_taula_conflictes(self, conflictes: List[str]) -> Table:
        """Crea taula de conflictes amb millor format i text wrapping"""
        avisos_header = _("⚠️ AVÍS: Hi ha professors de major prioritat disponibles:")
        conflictes = [c for c in conflictes if c.strip() != avisos_header]
        from reportlab.platypus import Paragraph, Table, TableStyle

        # Get current colors dynamically
        profile_colors = self._get_profile_colors()

        # Style for conflict content
        conflict_style = ParagraphStyle(
            "ConflictStyle",
            parent=self.styles["Normal"],
            fontSize=9,
            alignment=0,  # Left alignment
            fontName="Helvetica",
            textColor=colors.HexColor(profile_colors.get("conflict_color", "#c0392b")),
            leftIndent=20,
            hyphenationLang=self.hyphen_language_code if self.hyphen_lang else None,
            embeddedHyphenation=1 if self.hyphen_lang else 0,
        )

        hour_style = ParagraphStyle(
            "HourStyle",
            parent=self.styles["Normal"],
            fontSize=10,
            alignment=0,
            fontName="Helvetica-Bold",
            textColor=colors.HexColor(profile_colors.get("hour_color", "#2c3e50")),
            hyphenationLang=self.hyphen_language_code if self.hyphen_lang else None,
            embeddedHyphenation=1 if self.hyphen_lang else 0,
        )

        # Per intervals, mantenir estructura original (ja agrupada per dies)
        if hasattr(self, "_pdf_type") and self._pdf_type == "vigilancies_interval":
            # Mantenir estructura original: no reagrupar per hora
            dades = []
            for conflicte in conflictes:
                if conflicte.endswith(":"):  # Títol del dia
                    day_style = ParagraphStyle(
                        "DayStyle",
                        parent=hour_style,
                        fontSize=11,
                        textColor=colors.HexColor("#2980b9"),
                        spaceBefore=8,
                        spaceAfter=4,
                    )
                    dades.append([Paragraph(conflicte, day_style)])
                else:  # Conflicte individual
                    dades.append([Paragraph(conflicte, conflict_style)])
        else:
            # Reagrupar per hora (comportament original)
            conflictes_per_hora = defaultdict(list)
            labels_per_hora = {}
            for conflicte in conflictes:
                # Extreure hora del conflicte amb regex per més robustesa
                import re

                hora_match = re.search(r"(\d{1,2}:\d{2}):", conflicte)
                if hora_match:
                    hora_text = hora_match.group(1)
                    hora = hora_text.replace(":", "").zfill(4)
                    labels_per_hora[hora] = hora_text
                    conflictes_per_hora[hora].append(conflicte)
                else:
                    # Fallback: try to find any time pattern
                    hora_match = re.search(r"\b(\d{1,2}:\d{2})\b", conflicte)
                    if hora_match:
                        hora_text = hora_match.group(1)
                        hora = hora_text.replace(":", "").zfill(4)
                        labels_per_hora[hora] = hora_text
                        conflictes_per_hora[hora].append(conflicte)
                    else:
                        # If no time found, group under "unknown"
                        conflictes_per_hora["9999"].append(conflicte)

            # Ordena hores cronològicament
            hores_ordenades = sorted(
                conflictes_per_hora.keys(), key=lambda h: (h == "9999", int(h[:2]) if h.isdigit() else 0)
            )

            # Prepara dades per a la taula amb Paragraph objects
            dades = []

            for hora in hores_ordenades:
                # Formata hora correctament (ex: "0800" -> "08:00")
                if hora != "9999":
                    hora_formatejada = labels_per_hora.get(hora, f"{hora[:2]}:{hora[2:]}")
                    # Afegeix fila d'hora amb gestió d'imatges millorada
                    hora_text = pdf_images.format_conflict_text(_("🕐 HORA {hora}:").format(hora=hora_formatejada))
                    dades.append([Paragraph(hora_text, hour_style)])

                # Afegeix conflictes d'aquesta hora (sense tornar a escriure l'hora,
                # que ja hi és al títol)
                for c in conflictes_per_hora[hora]:
                    if hora != "9999":
                        c = re.sub(rf"^(\W*?)\s*{re.escape(hora_formatejada)}:\s*", r"\1", c, count=1)
                    # Usa la nova gestió d'imatges per als conflictes
                    conflicte_net = pdf_images.format_conflict_text(c)
                    dades.append([Paragraph(conflicte_net, conflict_style)])

        # Crea taula amb millor amplada
        taula = Table(dades, colWidths=[PDFConstants.TABLE_WIDTH])

        # Aplica estils millorats
        estil = TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fdf2f2")),  # Light red background
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e74c3c")),  # Red grid
            ]
        )

        # Aplica estil especial per a les files d'hora
        for i, fila in enumerate(dades):
            if len(fila) > 0 and isinstance(fila[0], Paragraph):
                text_content = str(fila[0])
                if "HORA" in text_content:
                    estil.add("BACKGROUND", (0, i), (0, i), colors.HexColor("#fadbd8"))  # Slightly darker red
                    estil.add("BOTTOMPADDING", (0, i), (0, i), 8)
                    estil.add("TOPPADDING", (0, i), (0, i), 8)

        taula.setStyle(estil)
        return taula

    def _pot_tenir_substitucions(self, hora: str) -> bool:
        return self.hores_amb_classe is None or hora in self.hores_amb_classe

    def _organitzar_dades_per_hora(self, substitucions: List[Dict], vigilancies: List[Dict]) -> Dict:
        """Organitza substitucions i vigilàncies per hora"""
        dades_per_hora = defaultdict(lambda: {"substitucions": [], "vigilancies": []})

        for sub in substitucions:
            if hora := sub.get("hora", ""):
                dades_per_hora[hora]["substitucions"].append(sub)

        for vig in vigilancies:
            if hora := vig.get("hora", ""):
                dades_per_hora[hora]["vigilancies"].append(vig)

        return dades_per_hora

    def _validar_conflictes_interval(self, substitucions: List[Dict], vigilancies: List[Dict]) -> List[str]:
        """Valida conflictes per interval, agrupats per dia amb capçalera"""
        from collections import defaultdict

        dies_subs: Dict[str, List] = defaultdict(list)
        dies_vigs: Dict[str, List] = defaultdict(list)
        dia_iso_map: Dict[str, str] = {}

        for sub in substitucions:
            dia = sub.get("_dia_interval", "")
            if dia:
                dies_subs[dia].append(sub)
                iso = sub.get("_data_iso", "")
                if iso:
                    dia_iso_map[dia] = iso

        for vig in vigilancies:
            if vig.get("_empty_day"):
                continue
            dia = vig.get("_dia_interval", "")
            if dia:
                dies_vigs[dia].append(vig)
                iso = vig.get("_data_iso", "")
                if iso:
                    dia_iso_map[dia] = iso

        all_dies = sorted(set(dies_subs.keys()) | set(dies_vigs.keys()), key=lambda d: dia_iso_map.get(d, "9999-12-31"))

        conflictes = []
        for dia in all_dies:
            day_conflicts = self._validar_conflictes_complets(dies_subs.get(dia, []), dies_vigs.get(dia, []))
            day_jornada = self._avisos_fora_jornada_dia(
                dies_subs.get(dia, []), dies_vigs.get(dia, []), dia_iso_map.get(dia, "")
            )
            all_day = day_conflicts + day_jornada
            if all_day:
                conflictes.append(f"{dia}:")
                conflictes.extend(all_day)

        return conflictes

    def _avisos_fora_jornada_dia(self, substitucions: List[Dict], vigilancies: List[Dict], data_iso: str) -> List[str]:
        """Detecta professors assignats fora de la seva jornada habitual per un dia concret."""
        if not self.horari_mgr or not data_iso:
            return []

        from datetime import datetime as _dt

        try:
            date_obj = _dt.strptime(data_iso, "%Y-%m-%d")
            dia_name = self.horari_mgr.get_dia_name(date_obj.weekday())
        except (ValueError, TypeError):
            return []

        hores_ordenades = self.horari_mgr.hores
        if not hores_ordenades:
            return []
        index_map = {h: i for i, h in enumerate(hores_ordenades)}

        avisos = []
        vistos = set()

        def _comprova(professor: str, hora: str):
            key = (professor, hora)
            if key in vistos or not professor or not hora:
                return
            vistos.add(key)
            primera, ultima = self.horari_mgr.get_jornada_professor(dia_name, professor)
            if primera is None:
                return
            idx_h = index_map.get(hora)
            idx_primera = index_map.get(primera)
            idx_ultima = index_map.get(ultima)
            if idx_h is None or idx_primera is None or idx_ultima is None:
                return
            if idx_h < idx_primera:
                avisos.append(
                    _("🕐 {professor} → arriba abans a {hora} (primera hora: {primera})").format(
                        professor=professor, hora=hora, primera=primera
                    )
                )
            elif idx_h > idx_ultima:
                avisos.append(
                    _("🕐 {professor} → queda més estona a {hora} (última hora: {ultima})").format(
                        professor=professor, hora=hora, ultima=ultima
                    )
                )

        for vig in vigilancies:
            _comprova(vig.get("vigilant", ""), vig.get("hora", ""))

        for sub in substitucions:
            substitut = sub.get("substitut", "")
            if substitut and substitut not in ("---", "PENDENT"):
                _comprova(substitut, sub.get("hora", ""))

        return avisos

    def _validar_conflictes_complets(
        self, substitucions: List[Dict], vigilancies: List[Dict], absents: Dict[str, List[str]] = None
    ) -> List[str]:
        """Validate conflicts for both substitutions and vigilances - unified logic"""
        from collections import defaultdict

        if absents is None:
            absents = {}

        conflictes = []

        # Si un professor absent és-hi per servei (SERVEI) o no (ABSENCIA), segons les
        # seves pròpies files de substitució
        tipus_absencia = {
            (s.get("professor_absent", ""), s.get("hora", "")): s.get("tipus_absencia", "")
            for s in substitucions
            if s.get("tipus_absencia") in ("ABSENCIA", "SERVEI")
        }

        def text_absencia(professor, hora):
            if tipus_absencia.get((professor, hora)) == "SERVEI":
                return _("absent (servei)")
            return _("absent")

        # Group by hour
        per_hora = defaultdict(lambda: {"substitucions": [], "vigilancies": []})

        for sub in substitucions:
            hora = sub.get("hora", "")
            if hora:
                per_hora[hora]["substitucions"].append(sub)

        for vig in vigilancies:
            hora = vig.get("hora", "")
            if hora:
                per_hora[hora]["vigilancies"].append(vig)

        # Check conflicts for each hour
        for hora, data_hora in per_hora.items():
            vigilants_assignats = set()
            aules_assignades = set()

            # Validate substitutions
            for sub in data_hora["substitucions"]:
                substitut = sub.get("substitut", "")

                if substitut and substitut not in ["---", "PENDENT"]:
                    # Absent substitute
                    if substitut in absents and hora in absents[substitut]:
                        conflictes.append(
                            _("⚠️ {hora}: Substitut {substitut} {absence_text}").format(
                                hora=hora, substitut=substitut, absence_text=text_absencia(substitut, hora)
                            )
                        )

                    # Duplicate substitute
                    if substitut in vigilants_assignats:
                        conflictes.append(
                            _("🕐 {hora}: Substitut {substitut} duplicat").format(hora=hora, substitut=substitut)
                        )
                    else:
                        vigilants_assignats.add(substitut)

                # Missing substitute
                if not substitut or substitut in ["---", "PENDENT"]:
                    professor = sub.get("professor_absent", sub.get("professor", ""))
                    assignatura = sub.get("assignatura", "")
                    # Only add if we have valid professor and assignatura data
                    if professor and professor.strip() and assignatura and assignatura.strip():
                        conflictes.append(
                            _("❌ {hora}: {professor} - {assignatura} sense substitut assignat").format(
                                hora=hora, professor=professor, assignatura=assignatura
                            )
                        )

            # Validate vigilances (same logic as vigilancies_pdf.py)
            for vig in data_hora["vigilancies"]:
                vigilant = vig.get("vigilant", "")
                aula = vig.get("aula", "")

                if vigilant and not vigilant.startswith("-- selecciona"):
                    # Absent vigilant
                    if vigilant in absents and hora in absents[vigilant]:
                        conflictes.append(
                            _("⚠️ {hora}: Vigilant {vigilant} {absence_text}").format(
                                hora=hora, vigilant=vigilant, absence_text=text_absencia(vigilant, hora)
                            )
                        )

                    # Duplicate vigilant
                    if vigilant in vigilants_assignats:
                        conflictes.append(
                            _("🕐 {hora}: Vigilant {vigilant} duplicat").format(hora=hora, vigilant=vigilant)
                        )
                    else:
                        vigilants_assignats.add(vigilant)

                if aula and aula != "ENLLAÇ":
                    # Duplicate classroom
                    if aula in aules_assignades:
                        conflictes.append(_("🏫 {hora}: Aula {aula} duplicada").format(hora=hora, aula=aula))
                    else:
                        aules_assignades.add(aula)

                # Missing vigilant
                # El nom de l'assignatura és una dada del centre: no es tradueix;
                # només el valor fix «VIGILÀNCIA»
                if not vigilant or vigilant.startswith("-- selecciona"):
                    tipus = vig.get("tipus", "")
                    if tipus == "VIGILÀNCIA":
                        conflictes.append(
                            _("❌ {hora}: {tipus} sense vigilant assignat").format(hora=hora, tipus=_("VIGILÀNCIA"))
                        )
                    else:
                        conflictes.append(
                            _("❌ {hora}: Assignatura {tipus} sense vigilant assignat").format(hora=hora, tipus=tipus)
                        )

                # Missing classroom
                if not aula:
                    tipus = vig.get("tipus", "")
                    if tipus == "VIGILÀNCIA":
                        conflictes.append(
                            _("🏫 {hora}: {tipus} sense aula assignada").format(hora=hora, tipus=_("VIGILÀNCIA"))
                        )
                    else:
                        conflictes.append(
                            _("🏫 {hora}: Assignatura {tipus} sense aula assignada").format(hora=hora, tipus=tipus)
                        )

        # Detectar substitucions duplicades per mateix professor (absent + vigilant)
        professors_amb_substitucions = defaultdict(list)
        for sub in substitucions:
            if sub.get("separador"):
                continue
            professor_absent = sub.get("professor_absent", "")
            hora = sub.get("hora", "")
            substitut = sub.get("substitut", "")
            assignatura = sub.get("assignatura", "")

            if professor_absent and hora and substitut and not substitut.startswith("---"):
                professors_amb_substitucions[professor_absent].append(
                    {"hora": hora, "substitut": substitut, "assignatura": assignatura}
                )

        # Comprovar si hi ha professors amb múltiples substitucions a la mateixa hora
        for professor, substitucions_prof in professors_amb_substitucions.items():
            hores_substitucions = defaultdict(list)
            for sub in substitucions_prof:
                hores_substitucions[sub["hora"]].append(sub)

            for hora, subs_hora in hores_substitucions.items():
                if len(subs_hora) > 1:
                    # Hi ha múltiples substitucions pel mateix professor a la mateixa hora
                    substituts = [s["substitut"] for s in subs_hora]
                    assignatures = [s["assignatura"] for s in subs_hora]
                    conflictes.append(
                        _(
                            "🔄 {hora}: {professor} té {num} substitucions (Substituts: {substituts} | Assignatures: {assignatures})"
                        ).format(
                            hora=hora,
                            professor=professor,
                            num=len(subs_hora),
                            substituts=", ".join(substituts),
                            assignatures=", ".join(assignatures),
                        )
                    )

        return conflictes

    def _sort_vigilancies_by_date(self, vigilancies: List[Dict]) -> tuple:
        """Sort vigilancies by date and return organized data"""
        vigilancies_per_dia = defaultdict(lambda: defaultdict(list))
        dia_iso_map = {}

        for vig in vigilancies:
            dia = vig.get("_dia_interval", "Dia desconegut")
            data_iso = vig.get("_data_iso", "")
            hora = vig.get("hora", "")
            if vig.get("_empty_day"):
                if data_iso:
                    dia_iso_map[dia] = data_iso
                # Ensure day exists even without hours
                _ = vigilancies_per_dia[dia]
                continue

            if hora:
                vigilancies_per_dia[dia][hora].append(vig)
                if data_iso:
                    dia_iso_map[dia] = data_iso

        dies_ordenats = sorted(vigilancies_per_dia.keys(), key=lambda dia: dia_iso_map.get(dia, "9999-12-31"))

        return vigilancies_per_dia, dies_ordenats

    def _generate_day_section(self, dia: str, hores_dia: Dict, subs_dia: Dict = None) -> List:
        """Un dia de l'interval: el títol i, a sota, el format triat."""
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.platypus import Paragraph

        comprimit = bool(getattr(self, "_auto_compression_active", False))
        dia_style = ParagraphStyle(
            "DiaInterval",
            parent=self.custom_styles["hora"],
            fontSize=self.custom_styles["hora"].fontSize + (1 if comprimit else 2),
            spaceBefore=8 if comprimit else 20,
            spaceAfter=6 if comprimit else 15,
            textColor=self.custom_styles["title"].textColor,  # el blau fosc del títol del PDF
        )
        story = [Paragraph(_text(dia), dia_style)]
        subs_dia = subs_dia or {}
        dades_per_hora = {
            hora: {"substitucions": subs_dia.get(hora, []), "vigilancies": hores_dia.get(hora, [])}
            for hora in set(hores_dia) | set(subs_dia)
        }
        story.extend(contingut_del_dia(self, dades_per_hora, False, bool(subs_dia), VIGILANCIES))
        return story

    def _generar_contingut_interval_vigilancies(
        self, vigilancies: List[Dict], substitucions: List[Dict] = None
    ) -> List:
        """Genera contingut per interval de vigilàncies: dies consecutius + format exacte"""
        from collections import defaultdict

        story = []

        # Organize and sort vigilancies by date
        vigilancies_per_dia, dies_ordenats = self._sort_vigilancies_by_date(vigilancies)

        # Organize substitutions by date if provided
        substitucions_per_dia = {}
        if substitucions:
            subs_per_dia = defaultdict(lambda: defaultdict(list))
            for sub in substitucions:
                dia = sub.get("_dia_interval", "")
                hora = sub.get("hora", "")
                if dia and hora:
                    subs_per_dia[dia][hora].append(sub)
            substitucions_per_dia = dict(subs_per_dia)

        # Cada dia, amb el seu títol (i, si es demana, en una pàgina nova)
        from reportlab.platypus import PageBreak

        for n, dia in enumerate(dies_ordenats):
            if n and self.dia_per_pagina:
                story.append(PageBreak())
            subs_dia = substitucions_per_dia.get(dia, {})
            story.extend(self._generate_day_section(dia, vigilancies_per_dia[dia], subs_dia))

            # Espai entre dies - aplicar compressió només si està activada
            if hasattr(self, "_auto_compression_active") and self._auto_compression_active:
                story.append(Spacer(1, 0.2 * cm))  # Reduït de 0.6 a 0.2
            else:
                story.append(Spacer(1, 0.6 * cm))  # Espai normal

        return story
