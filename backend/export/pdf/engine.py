"""
Exportador de PDF combinat: Substitucions + Vigilàncies organitzat per hores
VERSIÓ OPTIMITZADA I AMB FORMAT DE CONFLICTES MILLORAT
"""
import os
import html
import subprocess
import platform
from typing import List, Dict
from pathlib import Path
from datetime import datetime
from collections import defaultdict
#import emoji
from i18n_setup import translate as _
from ..pdf_images import pdf_images
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm

# PDF Constants
class PDFConstants:
    """Constants for PDF generation"""
    # Sizes
    TABLE_WIDTH = 16*cm
    SPACER_NORMAL = 0.5*cm
    SPACER_COMPACT = 0.2*cm
    SPACER_TINY = 0.01*cm
    SPACER_SMALL = 0.05*cm
    SPACER_MEDIUM = 0.1*cm
    SPACER_LARGE = 0.3*cm

    # Margins
    MARGIN_NORMAL = 1*cm
    MARGIN_COMPACT = 0.7*cm
    MARGIN_COMPACT_SIDE = 0.8*cm

    # Font reductions
    FONT_REDUCTION_DEFAULT = 0.85
    MIN_FONT_HEADER = 8
    MIN_FONT_BODY = 7
    MIN_FONT_HOUR = 10

    # Pagination thresholds
    THRESHOLD_MIN = 0.75
    THRESHOLD_MAX = 1.5
from reportlab.lib import colors
from ..pdf_styles import PDFStyleFactory


def open_pdf(filepath: str):
    """Obre PDF de forma no bloquejant amb subprocess.Popen"""
    if os.getenv("OPEN_PDF", "0") != "1":
        return
    try:
        if platform.system() == "Windows":
            subprocess.Popen([filepath], shell=True, start_new_session=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif platform.system() == "Darwin":  # macOS
            subprocess.Popen(["open", filepath], start_new_session=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:  # Linux
            subprocess.Popen(["xdg-open", filepath], start_new_session=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(_("📖 S'ha obert el PDF amb xdg-open: {filepath}").format(filepath=filepath))

    except Exception as e:
        print(_("⚠️ No s'ha pogut obrir automàticament: {error}").format(error=e))
        print(_("📁 Fitxer disponible a: {filepath}").format(filepath=filepath))


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
            self.fonts = self.pdf_config.get('font_sizes', {})
            self.hyphenation_config = self.pdf_config.get('hyphenation', {})
        except Exception:
            self.fonts = {}
            self.hyphenation_config = {'enabled': False}
        
        # Setup hyphenation if available
        self.hyphen_lang = None
        self.hyphen_language_code = None
        try:
            import pyphen
            if (self.hyphenation_config.get('enabled', False)):
                self.hyphen_language_code = self.hyphenation_config.get('language', 'ca')
                self.hyphen_lang = pyphen.Pyphen(lang=self.hyphen_language_code)
        except ImportError:
            pass
        except Exception as e:
            print(_("Avís: No s'ha pogut carregar la partició de paraules: {error}").format(error=e))
            pass

        # Carregar preferències de columnes opcionals
        self.show_comments_column = self.pdf_config.get('show_comments_column', True)
        self.show_hours_column = self.pdf_config.get('show_hours_column', False)

    def _get_profile_colors(self):
        """Obté colors del perfil actual - sempre actualitzat"""
        return PDFStyleFactory.get_current_profile_colors()
    

    def _setup_document_config(self, tipus_pdf: str, compact_mode: bool, substitucions: List[Dict], vigilancies: List[Dict], conflictes: List[str]):
        """Setup document configuration"""
        self._pdf_type = tipus_pdf
        self.pdf_config = PDFStyleFactory._load_pdf_config()

        # Manual compression only - automatic logic removed
        # Compression is now controlled manually via the PDF dialog checkbox
        if not hasattr(self, '_auto_compression_active'):
            self._auto_compression_active = False

        if self._auto_compression_active:
            print(_("📄 Compressió activada manualment per l'usuari"))
        else:
            print(_("📄 PDF normal sense compressió"))

    def _generate_filename(self, data_iso: str, subs_reals: List[Dict], vigilancies_reals: List[Dict]) -> str:
        """Generate PDF filename"""
        return self.PDFTypeResolver.get_filename(data_iso, subs_reals, vigilancies_reals)

    def _create_document(self, filename: str, compact_mode: bool):
        """Create and configure PDF document"""
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate

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
            rightMargin=right_margin
        ), output_path

    def _generate_titles(self, tipus_pdf: str, data_text: str, subs_reals: List[Dict], vigilancies_reals: List[Dict]):
        """Generate PDF titles"""
        from reportlab.platypus import Paragraph
        from reportlab.lib.styles import ParagraphStyle

        # Títol principal
        titol_principal = self.PDFTypeResolver.get_title(tipus_pdf, subs_reals, vigilancies_reals)

        # Estil per al títol principal (12pt) - RESTAURAT ORIGINAL
        title_main_style = ParagraphStyle(
            'TitleMain',
            parent=self.custom_styles['title'],
            fontSize=12,
            alignment=1,  # Centrat
            spaceAfter=-25  # Espai negatiu ajustat
        )

        # Estil per a la data (manté la mida original) - RESTAURAT ORIGINAL
        title_date_style = ParagraphStyle(
            'TitleDate',
            parent=self.custom_styles['title'],
            alignment=1,  # Centrat
            spaceBefore=-10,  # Espai negatiu ajustat abans
            spaceAfter=max(6, int(self.custom_styles['title'].spaceAfter * 0.6)) if hasattr(self, '_auto_compression_active') and self._auto_compression_active else self.custom_styles['title'].spaceAfter
        )

        return [
            Paragraph(titol_principal, title_main_style),
            Paragraph(data_text, title_date_style)
        ]

    def _create_styled_paragraph(self, text: str, base_style_name: str, overrides: Dict = None) -> 'Paragraph':
        """Create styled paragraph with consistent compression handling"""
        from reportlab.platypus import Paragraph
        from reportlab.lib.styles import ParagraphStyle

        overrides = overrides or {}
        base_style = getattr(self.custom_styles, base_style_name, self.styles['Normal'])

        # Apply auto-compression if active
        if hasattr(self, '_auto_compression_active') and self._auto_compression_active:
            auto_config = self.pdf_config.get('auto_compression', {})
            font_reduction = auto_config.get('font_reduction', {})
            min_sizes = auto_config.get('min_font_sizes', {})

            reduction_key = overrides.get('compression_key', base_style_name.lower())
            font_reduction_factor = font_reduction.get(reduction_key, PDFConstants.FONT_REDUCTION_DEFAULT)
            min_font_size = min_sizes.get(reduction_key, 8)

            # Apply compression
            if 'fontSize' not in overrides:
                overrides['fontSize'] = max(min_font_size, int(base_style.fontSize * font_reduction_factor))
            if 'spaceAfter' not in overrides and hasattr(base_style, 'spaceAfter'):
                overrides['spaceAfter'] = max(2, int(base_style.spaceAfter * 0.6))
            if 'spaceBefore' not in overrides and hasattr(base_style, 'spaceBefore'):
                overrides['spaceBefore'] = max(1, int(base_style.spaceBefore * 0.6))

        # Create custom style
        custom_style = ParagraphStyle(
            f'Custom{base_style_name}',
            parent=base_style,
            **overrides
        )

        return Paragraph(text, custom_style)

    class PDFTypeResolver:
        """Resolves PDF type, filename and title"""
        @staticmethod
        def get_filename(data_iso: str, subs_reals: List[Dict], vigilancies_reals: List[Dict]) -> str:
            timestamp = datetime.now().strftime("%y%m%d_%H%M%S")

            if data_iso:
                from utils.date_context import DateContext
                date_ctx = DateContext.from_iso(data_iso)
                data_curta = date_ctx._date.strftime("%y%m%d")
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

    def exportar(self, substitucions: List[Dict], vigilancies: List[Dict],
                data_text: str, conflictes: List[str] = None,
                absents: Dict[str, List[str]] = None, data_iso: str = None, tipus_pdf: str = "auto") -> str:
        """Genera PDF combinat organitzat per hores"""
        try:
            # Setup configuration
            compact_mode = self.pdf_config.get('single_page_mode', False)
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
                subs_reals = [s for s in subs_reals
                             if not (s.get("grup", "") == "" and s.get("assignatura", "") != "")]

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
                # Organitza per hores (format normal)
                dades_per_hora = self._organitzar_dades_per_hora(subs_reals, vigilancies_reals)

                # Genera secció per cada hora que tingui dades
                for hora in self.hores:
                    if hora in dades_per_hora:
                        data_hora = dades_per_hora[hora]
                    else:
                        # Saltar hores buides
                        continue

                    # Títol de l'hora amb compressió si cal
                    hora_style = self.custom_styles['hora']
                    if hasattr(self, '_auto_compression_active') and self._auto_compression_active:
                        from reportlab.lib.styles import ParagraphStyle
                        auto_config = self.pdf_config.get('auto_compression', {})
                        font_reduction = auto_config.get('font_reduction', {})
                        min_sizes = auto_config.get('min_font_sizes', {})
                        
                        hour_reduction = font_reduction.get('hour', 0.85)
                        min_hour_size = min_sizes.get('hour', 10)
                        
                        hora_style = ParagraphStyle(
                            'CompactHora',
                            parent=hora_style,
                            fontSize=max(min_hour_size, int(hora_style.fontSize * hour_reduction)),
                            spaceAfter=max(2, int(hora_style.spaceAfter * 0.4)),  # Reduir més l'espai després
                            spaceBefore=max(1, int(hora_style.spaceBefore * 0.4))  # Reduir més l'espai abans
                        )
                    story.append(Paragraph(_("Hora {hora}").format(hora=hora), hora_style))
                    
                    # SUBSTITUCIONS
                    if data_hora['substitucions']:
                        story.append(self._crear_taula_substitucions(data_hora['substitucions']))
                        
                        if data_hora['vigilancies']:  # Espai entre taules adaptat al mode
                            if hasattr(self, '_auto_compression_active') and self._auto_compression_active:
                                spacer_size = 0.01*cm  # Espai mínim amb compressió automàtica
                            else:
                                spacer_size = 0.05*cm if compact_mode else 0.1*cm
                            story.append(Spacer(1, spacer_size))
                    
                    # VIGILÀNCIES
                    if data_hora['vigilancies']:
                        story.append(self._crear_taula_vigilancies(data_hora['vigilancies']))
                    
                    # Espai entre hores - molt reduït amb compressió automàtica
                    if hasattr(self, '_auto_compression_active') and self._auto_compression_active:
                        story.append(Spacer(1, 0.08*cm))  # Espai mínim entre hores
                    else:
                        story.append(Spacer(1, 0.3*cm))
            
            # Resum simple amb compressió
            if hasattr(self, '_auto_compression_active') and self._auto_compression_active:
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
                        subs=len(subs_reals), vig=len(vigilancies_reals))
                else:
                    # Fallback: comportament antic
                    resum = _("RESUM: {subs} substitucions, {vig} vigilàncies").format(
                        subs=len(subs_reals), vig=len(vigilancies_reals))
                story.append(Paragraph(resum, self.styles['Normal']))
            
            # Secció de conflictes - SEMPRE en salt de pàgina (no compten per al càlcul de compressió)
            if conflictes:
                from reportlab.platypus import PageBreak
                story.append(PageBreak())  # Salt de pàgina sempre per conflictes

                story.append(Paragraph(_("<b>CONFLICTES DETECTATS:</b>"), self.styles['Heading2']))
                story.append(Spacer(1, 0.3*cm))  # Espai normal (nova pàgina)
                story.append(self._crear_taula_conflictes(conflictes))
            
            # Peu de pàgina amb compressió
            if hasattr(self, '_auto_compression_active') and self._auto_compression_active:
                story.append(Spacer(1, PDFConstants.SPACER_COMPACT))  # Espai reduït abans del peu
            else:
                story.append(Spacer(1, PDFConstants.SPACER_NORMAL))
            footer = Paragraph(
                _("Generat el {data} a les {hora}").format(
                    data=datetime.now().strftime('%d/%m/%Y'),
                    hora=datetime.now().strftime('%H:%M')
                ),
                self.styles['Normal']
            )
            story.append(footer)

            # Genera PDF amb logo només a la primera pàgina
            doc.build(story, onFirstPage=self._add_logo_to_page)
            print(_("✅ S'ha generat el PDF combinat: {output_path}").format(output_path=output_path))
            self._obrir_pdf(str(output_path))
            return filename

        except Exception as e:
            import traceback
            print(_("❌ Error en generar PDF: {error}").format(error=e))
            traceback.print_exc()
            return ""

    def _add_logo_to_page(self, canvas, doc):
        """Afegeix logo al marge superior esquerre de cada pàgina si existeix"""
        try:
            from PIL import Image
            from pathlib import Path
            from config.settings import config

            logo_path = None
            configured_logo = config.institucio_data.get("logo_path")
            if configured_logo:
                candidate = Path(configured_logo)
                if candidate.exists():
                    logo_path = candidate

            if logo_path is None:
                data_dir = Path(config.data_dir)
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
                logo_width = img_width_px * 72 / img.info.get('dpi', (72, 72))[0]
                logo_height = img_height_px * 72 / img.info.get('dpi', (72, 72))[1]

                # Posició: 0.5cm del marge superior i esquerre
                x = 0.5 * cm
                y = A4[1] - logo_height - 0.5 * cm

                # Dibuixa el logo amb mida real
                canvas.drawImage(
                    str(logo_path),
                    x, y,
                    width=logo_width,
                    height=logo_height,
                    preserveAspectRatio=True,
                    mask='auto'
                )
        except Exception as e:
            # Si hi ha error, simplement no mostra el logo
            print(f"⚠️ No s'ha pogut carregar el logo: {e}")

    def _crear_taula_conflictes(self, conflictes: List[str]) -> Table:
        """Crea taula de conflictes amb millor format i text wrapping"""
        avisos_header = _("⚠️ AVÍS: Hi ha professors de major prioritat disponibles:")
        conflictes = [c for c in conflictes if c.strip() != avisos_header]
        from reportlab.platypus import Table, TableStyle, Paragraph
        from reportlab.lib.styles import ParagraphStyle

        # Get current colors dynamically
        profile_colors = self._get_profile_colors()

        # Style for conflict content
        conflict_style = ParagraphStyle(
            'ConflictStyle',
            parent=self.styles['Normal'],
            fontSize=9,
            alignment=0,  # Left alignment
            fontName='Helvetica',
            textColor=colors.HexColor(profile_colors.get('conflict_color', '#c0392b')),
            leftIndent=20,
            hyphenationLang=self.hyphen_language_code if self.hyphen_lang else None,
            embeddedHyphenation=1 if self.hyphen_lang else 0
        )

        hour_style = ParagraphStyle(
            'HourStyle',
            parent=self.styles['Normal'],
            fontSize=10,
            alignment=0,
            fontName='Helvetica-Bold',
            textColor=colors.HexColor(profile_colors.get('hour_color', '#2c3e50')),
            hyphenationLang=self.hyphen_language_code if self.hyphen_lang else None,
            embeddedHyphenation=1 if self.hyphen_lang else 0
        )

        # Per intervals, mantenir estructura original (ja agrupada per dies)
        if hasattr(self, '_pdf_type') and self._pdf_type == "vigilancies_interval":
            # Mantenir estructura original: no reagrupar per hora
            dades = []
            for conflicte in conflictes:
                if conflicte.endswith(':'):  # Títol del dia
                    day_style = ParagraphStyle(
                        'DayStyle',
                        parent=hour_style,
                        fontSize=11,
                        textColor=colors.HexColor('#2980b9'),
                        spaceBefore=8,
                        spaceAfter=4
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
                hora_match = re.search(r'(\d{1,2}:\d{2}):', conflicte)
                if hora_match:
                    hora_text = hora_match.group(1)
                    hora = hora_text.replace(':', '').zfill(4)
                    labels_per_hora[hora] = hora_text
                    conflictes_per_hora[hora].append(conflicte)
                else:
                    # Fallback: try to find any time pattern
                    hora_match = re.search(r'\b(\d{1,2}:\d{2})\b', conflicte)
                    if hora_match:
                        hora_text = hora_match.group(1)
                        hora = hora_text.replace(':', '').zfill(4)
                        labels_per_hora[hora] = hora_text
                        conflictes_per_hora[hora].append(conflicte)
                    else:
                        # If no time found, group under "unknown"
                        conflictes_per_hora['9999'].append(conflicte)

            # Ordena hores cronològicament
            hores_ordenades = sorted(
                conflictes_per_hora.keys(),
                key=lambda h: (h == '9999', int(h[:2]) if h.isdigit() else 0)
            )

            # Prepara dades per a la taula amb Paragraph objects
            dades = []

            for hora in hores_ordenades:
                # Formata hora correctament (ex: "0800" -> "08:00")
                if hora != '9999':
                    hora_formatejada = labels_per_hora.get(hora, f"{hora[:2]}:{hora[2:]}")
                    # Afegeix fila d'hora amb gestió d'imatges millorada
                    hora_text = pdf_images.format_conflict_text(_("🕐 HORA {hora}:").format(hora=hora_formatejada))
                    dades.append([Paragraph(hora_text, hour_style)])

                # Afegeix conflictes d'aquesta hora
                for c in conflictes_per_hora[hora]:
                    # Usa la nova gestió d'imatges per als conflictes
                    conflicte_net = pdf_images.format_conflict_text(c)
                    dades.append([Paragraph(conflicte_net, conflict_style)])
        
        # Crea taula amb millor amplada
        taula = Table(dades, colWidths=[PDFConstants.TABLE_WIDTH])
        
        # Aplica estils millorats
        estil = TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fdf2f2')),  # Light red background
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e74c3c')),  # Red grid
        ])
        
        # Aplica estil especial per a les files d'hora
        for i, fila in enumerate(dades):
            if len(fila) > 0 and isinstance(fila[0], Paragraph):
                text_content = str(fila[0])
                if "HORA" in text_content:
                    estil.add('BACKGROUND', (0, i), (0, i), colors.HexColor('#fadbd8'))  # Slightly darker red
                    estil.add('BOTTOMPADDING', (0, i), (0, i), 8)
                    estil.add('TOPPADDING', (0, i), (0, i), 8)
        
        taula.setStyle(estil)
        return taula
    
    def _organitzar_dades_per_hora(self, substitucions: List[Dict], vigilancies: List[Dict]) -> Dict:
        """Organitza substitucions i vigilàncies per hora"""
        dades_per_hora = defaultdict(lambda: {'substitucions': [], 'vigilancies': []})
        
        for sub in substitucions:
            if hora := sub.get("hora", ""):
                dades_per_hora[hora]['substitucions'].append(sub)
        
        for vig in vigilancies:
            if hora := vig.get("hora", ""):
                dades_per_hora[hora]['vigilancies'].append(vig)
        
        return dades_per_hora

    def _calcular_amplades_columnes(self, tipus: str, show_comments: bool, show_hours: bool):
        """Calcula headers i amplades segons configuració

        Args:
            tipus: "substitucions" o "vigilancies"
            show_comments: Mostrar columna comentaris
            show_hours: Mostrar columna hores

        Returns:
            tuple: (headers_list, colWidths_list)
        """
        from reportlab.lib.units import cm

        if tipus == "substitucions":
            if show_comments and not show_hours:
                # Cas 1: Configuració actual (comentaris SÍ, hores NO) - Absent i Substitut iguals
                headers = [_("Absent"), _("Assignatura"), _("Grup"), _("Substitut"), _("Observacions")]
                widths = [3.4*cm, 3.2*cm, 3.2*cm, 3.4*cm, 5.8*cm]
            elif not show_comments and not show_hours:
                # Cas 2: Sense comentaris ni hores - Absent i Substitut més amples i iguals
                headers = [_("Absent"), _("Assignatura"), _("Grup"), _("Substitut")]
                widths = [6.0*cm, 3.0*cm, 3.0*cm, 6.0*cm]
            elif show_comments and show_hours:
                # Cas 3: Amb comentaris i hores - Hora | Absent | Grup | Assignatura | Substitut | Observacions
                headers = [_("Hora"), _("Absent"), _("Grup"), _("Assignatura"), _("Substitut"), _("Observacions")]
                widths = [1.8*cm, 3.2*cm, 2.9*cm, 2.9*cm, 3.2*cm, 5.0*cm]
            else:  # not show_comments and show_hours
                # Cas 4: Sense comentaris però amb hores - Hora | Absent | Grup | Assignatura | Substitut
                headers = [_("Hora"), _("Absent"), _("Grup"), _("Assignatura"), _("Substitut")]
                widths = [1.8*cm, 5.0*cm, 3.6*cm, 3.6*cm, 5.0*cm]

        else:  # vigilancies
            if show_comments and not show_hours:
                # Cas 1: Configuració actual - Curs i Vigilant iguals
                headers = [_("Curs"), _("Assignatura"), _("Aula"), _("Vigilant"), _("Observacions")]
                widths = [3.4*cm, 3.2*cm, 3.2*cm, 3.4*cm, 5.8*cm]
            elif not show_comments and not show_hours:
                # Cas 2: Sense comentaris ni hores - Curs i Vigilant més amples i iguals
                headers = [_("Curs"), _("Assignatura"), _("Aula"), _("Vigilant")]
                widths = [6.0*cm, 3.0*cm, 3.0*cm, 6.0*cm]
            elif show_comments and show_hours:
                # Cas 3: Amb comentaris i hores - Hora | Curs | Aula | Assignatura | Vigilant | Observacions
                headers = [_("Hora"), _("Curs"), _("Aula"), _("Assignatura"), _("Vigilant"), _("Observacions")]
                widths = [1.8*cm, 3.2*cm, 2.9*cm, 2.9*cm, 3.2*cm, 5.0*cm]
            else:  # not show_comments and show_hours
                # Cas 4: Sense comentaris però amb hores - Hora | Curs | Aula | Assignatura | Vigilant
                headers = [_("Hora"), _("Curs"), _("Aula"), _("Assignatura"), _("Vigilant")]
                widths = [1.8*cm, 5.0*cm, 3.6*cm, 3.6*cm, 5.0*cm]

        return headers, widths

    def _crear_taula_substitucions(self, substitucions: List[Dict]) -> Table:
        """Crea taula de substitucions optimitzada amb text wrapping"""
        from reportlab.platypus import Table, TableStyle, Paragraph
        from reportlab.lib.styles import ParagraphStyle
        
        # Get font sizes from current configuration (already reloaded)
        fonts = self.pdf_config.get('font_sizes', {})
        
        # Get current profile colors
        profile_colors = self._get_profile_colors()
        
        # Get font sizes with auto-compression reduction
        header_size = fonts.get('table_header', 11)
        body_size = fonts.get('table_body', 12)
        
        # Apply auto-compression font reduction if active (configurable)
        if hasattr(self, '_auto_compression_active') and self._auto_compression_active:
            auto_config = self.pdf_config.get('auto_compression', {})
            font_reduction = auto_config.get('font_reduction', {})
            min_sizes = auto_config.get('min_font_sizes', {})
            
            header_reduction = font_reduction.get('table_header', 0.85)
            body_reduction = font_reduction.get('table_body', 0.85)
            min_header_size = min_sizes.get('table_header', 8)
            min_body_size = min_sizes.get('table_body', 7)
            
            header_size = max(min_header_size, int(header_size * header_reduction))
            body_size = max(min_body_size, int(body_size * body_reduction))
            print(_("🔍 Compressió automàtica: fonts reduïdes a H:{header} B:{body}").format(header=header_size, body=body_size))
        
        # Style for cell content with wrapping
        cell_style = ParagraphStyle(
            'CellStyle',
            parent=self.styles['Normal'],
            fontSize=body_size,
            alignment=1,  # Center
            fontName='Helvetica',
            hyphenationLang=self.hyphen_language_code if self.hyphen_lang else None,
            embeddedHyphenation=1 if self.hyphen_lang else 0
        )
        
        header_style = ParagraphStyle(
            'HeaderStyle', 
            parent=self.styles['Normal'],
            fontSize=header_size,
            alignment=1,
            fontName='Helvetica-Bold',
            textColor=colors.HexColor(profile_colors.get('substitutions_header_text', '#ffffff')),
            hyphenationLang=self.hyphen_language_code if self.hyphen_lang else None,
            embeddedHyphenation=1 if self.hyphen_lang else 0
        )
        
        # Create header with Paragraph objects - dinàmic segons configuració
        header_texts, col_widths = self._calcular_amplades_columnes(
            "substitucions",
            self.show_comments_column,
            self.show_hours_column
        )
        headers = [Paragraph(text, header_style) for text in header_texts]
        dades = [headers]
        
        # Create data rows with Paragraph objects for text wrapping
        for sub in substitucions:
            # Highlight substitute with bold font if assigned, hide pending ones
            substitut_text = sub.get("substitut", "") or ""
            if substitut_text and substitut_text not in ["---", "PENDENT"]:
                substitut_style = ParagraphStyle(
                    'SubstitutStyle',
                    parent=cell_style,
                    fontName='Helvetica-Bold',
                    textColor=colors.HexColor('#2c3e50'),  # Dark blue for emphasis
                    hyphenationLang=self.hyphen_language_code if self.hyphen_lang else None,
                )
            else:
                # Hide pending substitutes
                substitut_text = ""
                substitut_style = cell_style
            
            # Format grup amb aula: "Grup (Aula)"
            grup = sub.get("grup", "") or ""
            aula = sub.get("aula", "") or ""
            grup_display = f"{grup} ({aula})" if aula else grup

            # Construcció dinàmica de fila segons ordre de columnes
            # Escape HTML characters in comments to avoid ReportLab parsing errors
            comentaris_text = sub.get("comentaris", "") or ""
            if comentaris_text:
                comentaris_text = html.escape(comentaris_text)

            if self.show_hours_column:
                # ORDRE: Hora | Absent | Grup | Assignatura | Substitut | [Observacions]
                hora_text = sub.get("hora", "") or ""
                fila = [
                    Paragraph(hora_text, cell_style),
                    Paragraph(sub.get("professor_absent", sub.get("professor", "")) or "", cell_style),
                    Paragraph(grup_display, cell_style),
                    Paragraph(sub.get("assignatura", "") or "", cell_style),
                    Paragraph(substitut_text, substitut_style)
                ]
                if self.show_comments_column:
                    fila.append(Paragraph(comentaris_text, cell_style))
            else:
                # ORDRE ORIGINAL: Absent | Assignatura | Grup | Substitut | [Observacions]
                fila = [
                    Paragraph(sub.get("professor_absent", sub.get("professor", "")) or "", cell_style),
                    Paragraph(sub.get("assignatura", "") or "", cell_style),
                    Paragraph(grup_display, cell_style),
                    Paragraph(substitut_text, substitut_style)
                ]
                if self.show_comments_column:
                    fila.append(Paragraph(comentaris_text, cell_style))

            dades.append(fila)
        
        # Get font sizes for table styling
        header_size = fonts.get('table_header', 11)
        body_size = fonts.get('table_body', 12)

        # Amplades dinàmiques segons configuració
        taula = Table(dades, colWidths=col_widths)
        # Build table style based on current profile - SUBSTITUTIONS
        profile_colors = self._get_profile_colors()
        table_style_commands = [
            # Header styling based on profile
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(profile_colors.get('substitutions_header_bg', '#2c3e50'))),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor(profile_colors.get('substitutions_header_text', '#ffffff'))),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), header_size),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10 if not (hasattr(self, '_auto_compression_active') and self._auto_compression_active) else 6),
            ('TOPPADDING', (0, 0), (-1, 0), 6 if not (hasattr(self, '_auto_compression_active') and self._auto_compression_active) else 3),
            
            # Content styling based on profile
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor(profile_colors.get('content_bg', '#f8f9fa'))),
            ('FONTSIZE', (0, 1), (-1, -1), body_size),
            ('GRID', (0, 0), (-1, -1), profile_colors.get('grid_width', 0.5), colors.HexColor(profile_colors.get('grid_color', '#dee2e6')))]
        
        # Add header line if profile specifies it (e.g., B&W ink saver)
        if profile_colors.get('use_header_line', False):
            table_style_commands.append(('LINEBELOW', (0, 0), (-1, 0), 1.5, colors.HexColor(profile_colors.get('grid_color', '#000000'))))
        
        taula.setStyle(TableStyle(table_style_commands + [
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # Middle alignment for wrapped text
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            
            # Padding adaptat a compressió
            ('LEFTPADDING', (0, 1), (-1, -1), 4 if not (hasattr(self, '_auto_compression_active') and self._auto_compression_active) else 2),
            ('RIGHTPADDING', (0, 1), (-1, -1), 4 if not (hasattr(self, '_auto_compression_active') and self._auto_compression_active) else 2),
            ('TOPPADDING', (0, 1), (-1, -1), 6 if not (hasattr(self, '_auto_compression_active') and self._auto_compression_active) else 2),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6 if not (hasattr(self, '_auto_compression_active') and self._auto_compression_active) else 2),
        ]))
        
        return taula
    
    def _crear_taula_vigilancies(self, vigilancies: List[Dict]) -> Table:
        """Crea taula de vigilàncies optimitzada amb text wrapping"""
        from reportlab.platypus import Table, TableStyle, Paragraph
        from reportlab.lib.styles import ParagraphStyle
        
        # Get font sizes from current configuration (already reloaded)
        fonts = self.pdf_config.get('font_sizes', {})
        
        # Get current profile colors
        profile_colors = self._get_profile_colors()
        
        # Get font sizes with auto-compression reduction
        header_size = fonts.get('table_header', 11)
        body_size = fonts.get('table_body', 12)
        
        # Apply auto-compression font reduction if active (configurable)
        if hasattr(self, '_auto_compression_active') and self._auto_compression_active:
            auto_config = self.pdf_config.get('auto_compression', {})
            font_reduction = auto_config.get('font_reduction', {})
            min_sizes = auto_config.get('min_font_sizes', {})
            
            header_reduction = font_reduction.get('table_header', 0.85)
            body_reduction = font_reduction.get('table_body', 0.85)
            min_header_size = min_sizes.get('table_header', 8)
            min_body_size = min_sizes.get('table_body', 7)
            
            header_size = max(min_header_size, int(header_size * header_reduction))
            body_size = max(min_body_size, int(body_size * body_reduction))
            print(_("🔍 Compressió automàtica: fonts reduïdes a H:{header} B:{body}").format(header=header_size, body=body_size))
        
        # Style for cell content with wrapping
        cell_style = ParagraphStyle(
            'CellStyle',
            parent=self.styles['Normal'],
            fontSize=body_size,
            alignment=1,  # Center
            fontName='Helvetica',
            hyphenationLang=self.hyphen_language_code if self.hyphen_lang else None,
            embeddedHyphenation=1 if self.hyphen_lang else 0
        )
        
        header_style = ParagraphStyle(
            'HeaderStyle',
            parent=self.styles['Normal'],
            fontSize=header_size,
            alignment=1,
            fontName='Helvetica-Bold',
            textColor=colors.HexColor(profile_colors.get('vigilances_header_text', '#ffffff'))
        )
        
        # Create header with Paragraph objects - dinàmic segons configuració
        header_texts, col_widths = self._calcular_amplades_columnes(
            "vigilancies",
            self.show_comments_column,
            self.show_hours_column
        )
        headers = [Paragraph(text, header_style) for text in header_texts]
        dades = [headers]
        
        # Create data rows with Paragraph objects for text wrapping
        for vig in vigilancies:
            tipus = vig.get("tipus", "")
            
            # Extract course/level from vigilance data
            nivell = vig.get("nivell", "")

            # Don't show "GENERAL" as course - it's for special vigilances
            if nivell == "GENERAL":
                nivell = ""
            # Only show level if there's an explicit group selection
            if not nivell:
                grup = vig.get("grups", "") or vig.get("grup", "")
                # ONLY extract level from explicit group selection, NOT from aula
                if grup and "-" in grup:
                    parts = grup.split("-")
                    if len(parts) >= 2:
                        if parts[1] == "ESO":
                            nivell = f"{parts[0]}{'r' if parts[0] in ['1', '3'] else 't'} ESO"
                        elif parts[1] == "BATX":
                            nivell = f"{parts[0]}{'r' if parts[0] == '1' else 'n'} BATX"
                # NOTE: No longer extract level from aula automatically to avoid unwanted course inference
                
            # Allow showing course derived from group/aula like v2.4.0 behavior
            
            # Show vigilant text, but hide placeholders
            vigilant_text = vig.get("vigilant", "") or ""
            
            # Highlight assigned vigilants, hide pending ones
            if vigilant_text and not vigilant_text.startswith("-- selecciona"):
                # Assigned vigilant - bold and colored
                vigilant_style = ParagraphStyle(
                    'VigilantStyle',
                    parent=cell_style,
                    fontName='Helvetica-Bold',
                    textColor=colors.HexColor('#17a2b8'),  # Teal for emphasis
                    hyphenationLang=self.hyphen_language_code if self.hyphen_lang else None,
                )
            else:
                # Empty or placeholder - show as empty
                vigilant_text = ""  # Leave blank instead of showing PENDENT
                vigilant_style = cell_style
            
            # Escape HTML characters in comments to avoid ReportLab parsing errors
            comentaris_text = vig.get("comentaris", "") or ""
            if comentaris_text:
                import html
                comentaris_text = html.escape(comentaris_text)

            # Construcció dinàmica de fila segons ordre de columnes
            if self.show_hours_column:
                # ORDRE: Hora | Curs | Aula | Assignatura (tipus) | Vigilant | [Observacions]
                hora_text = vig.get("hora", "") or ""
                fila = [
                    Paragraph(hora_text, cell_style),
                    Paragraph(nivell or "", cell_style),
                    Paragraph(vig.get("aula", "") or "", cell_style),
                    Paragraph(tipus or "", cell_style),
                    Paragraph(vigilant_text, vigilant_style)
                ]
                if self.show_comments_column:
                    fila.append(Paragraph(comentaris_text, cell_style))
            else:
                # ORDRE ORIGINAL: Curs | Assignatura (tipus) | Aula | Vigilant | [Observacions]
                fila = [
                    Paragraph(nivell or "", cell_style),
                    Paragraph(tipus or "", cell_style),
                    Paragraph(vig.get("aula", "") or "", cell_style),
                    Paragraph(vigilant_text, vigilant_style)
                ]
                if self.show_comments_column:
                    fila.append(Paragraph(comentaris_text, cell_style))

            dades.append(fila)

        # Amplades dinàmiques segons configuració
        taula = Table(dades, colWidths=col_widths)
        
        # Build vigilance table style based on current profile - VIGILANCES
        profile_colors = self._get_profile_colors()
        vigilance_style_commands = [
            # Header styling based on profile
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(profile_colors.get('vigilances_header_bg', '#17a2b8'))),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor(profile_colors.get('vigilances_header_text', '#ffffff'))),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), fonts.get('table_header', 11)),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10 if not (hasattr(self, '_auto_compression_active') and self._auto_compression_active) else 6),
            ('TOPPADDING', (0, 0), (-1, 0), 6 if not (hasattr(self, '_auto_compression_active') and self._auto_compression_active) else 3),
            
            # Content styling based on profile
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor(profile_colors.get('content_bg', '#f1f8f8'))),
            ('FONTSIZE', (0, 1), (-1, -1), fonts.get('table_body', 12)),
            ('GRID', (0, 0), (-1, -1), profile_colors.get('grid_width', 0.5), colors.HexColor(profile_colors.get('grid_color', '#d1ecf1')))]
        
        # Add header line if profile specifies it
        if profile_colors.get('use_header_line', False):
            vigilance_style_commands.append(('LINEBELOW', (0, 0), (-1, 0), 1.5, colors.HexColor(profile_colors.get('grid_color', '#000000'))))
        
        taula.setStyle(TableStyle(vigilance_style_commands + [
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # Middle alignment for wrapped text
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            
            # Padding adaptat a compressió
            ('LEFTPADDING', (0, 1), (-1, -1), 4 if not (hasattr(self, '_auto_compression_active') and self._auto_compression_active) else 2),
            ('RIGHTPADDING', (0, 1), (-1, -1), 4 if not (hasattr(self, '_auto_compression_active') and self._auto_compression_active) else 2),
            ('TOPPADDING', (0, 1), (-1, -1), 6 if not (hasattr(self, '_auto_compression_active') and self._auto_compression_active) else 2),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6 if not (hasattr(self, '_auto_compression_active') and self._auto_compression_active) else 2),
        ]))
        
        return taula
    
    def _obrir_pdf(self, filepath: str):
        """Obre PDF automàticament de forma no bloquejant"""
        open_pdf(filepath)
    
    def _validar_conflictes_interval(self, substitucions: List[Dict], vigilancies: List[Dict]) -> List[str]:
        """Valida conflictes per interval, agrupats per dia amb capçalera"""
        from collections import defaultdict

        dies_subs: Dict[str, List] = defaultdict(list)
        dies_vigs: Dict[str, List] = defaultdict(list)
        dia_iso_map: Dict[str, str] = {}

        for sub in substitucions:
            dia = sub.get('_dia_interval', '')
            if dia:
                dies_subs[dia].append(sub)
                iso = sub.get('_data_iso', '')
                if iso:
                    dia_iso_map[dia] = iso

        for vig in vigilancies:
            if vig.get('_empty_day'):
                continue
            dia = vig.get('_dia_interval', '')
            if dia:
                dies_vigs[dia].append(vig)
                iso = vig.get('_data_iso', '')
                if iso:
                    dia_iso_map[dia] = iso

        all_dies = sorted(
            set(dies_subs.keys()) | set(dies_vigs.keys()),
            key=lambda d: dia_iso_map.get(d, '9999-12-31')
        )

        conflictes = []
        for dia in all_dies:
            day_conflicts = self._validar_conflictes_complets(
                dies_subs.get(dia, []), dies_vigs.get(dia, [])
            )
            day_jornada = self._avisos_fora_jornada_dia(
                dies_subs.get(dia, []), dies_vigs.get(dia, []),
                dia_iso_map.get(dia, '')
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
        except Exception:
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
                        professor=professor, hora=hora, primera=primera)
                )
            elif idx_h > idx_ultima:
                avisos.append(
                    _("🕐 {professor} → queda més estona a {hora} (última hora: {ultima})").format(
                        professor=professor, hora=hora, ultima=ultima)
                )

        for vig in vigilancies:
            _comprova(vig.get('vigilant', ''), vig.get('hora', ''))

        for sub in substitucions:
            substitut = sub.get('substitut', '')
            if substitut and substitut not in ('---', 'PENDENT'):
                _comprova(substitut, sub.get('hora', ''))

        return avisos

    def _validar_conflictes_complets(self, substitucions: List[Dict], vigilancies: List[Dict],
                                   absents: Dict[str, List[str]] = None) -> List[str]:
        """Validate conflicts for both substitutions and vigilances - unified logic"""
        from collections import defaultdict
        if absents is None:
            absents = {}
            
        conflictes = []
        
        # Group by hour
        per_hora = defaultdict(lambda: {'substitucions': [], 'vigilancies': []})
        
        for sub in substitucions:
            hora = sub.get("hora", "")
            if hora:
                per_hora[hora]['substitucions'].append(sub)
                
        for vig in vigilancies:
            hora = vig.get("hora", "")
            if hora:
                per_hora[hora]['vigilancies'].append(vig)
        
        # Check conflicts for each hour
        for hora, data_hora in per_hora.items():
            vigilants_assignats = set()
            aules_assignades = set()
            
            # Validate substitutions
            for sub in data_hora['substitucions']:
                substitut = sub.get('substitut', '')
                
                if substitut and substitut not in ["---", "PENDENT"]:
                    # Absent substitute
                    if substitut in absents and hora in absents[substitut]:
                        from utils.absence_utils import get_professor_absence_text
                        absence_text = get_professor_absence_text(substitut, hora)
                        conflictes.append(_("⚠️ {hora}: Substitut {substitut} {absence_text}").format(
                            hora=hora, substitut=substitut, absence_text=absence_text.lower()))

                    # Duplicate substitute
                    if substitut in vigilants_assignats:
                        conflictes.append(_("🕐 {hora}: Substitut {substitut} duplicat").format(
                            hora=hora, substitut=substitut))
                    else:
                        vigilants_assignats.add(substitut)
                
                # Missing substitute
                if not substitut or substitut in ["---", "PENDENT"]:
                    professor = sub.get('professor_absent', sub.get('professor', ''))
                    assignatura = sub.get('assignatura', '')
                    # Only add if we have valid professor and assignatura data
                    if professor and professor.strip() and assignatura and assignatura.strip():
                        conflictes.append(_("❌ {hora}: {professor} - {assignatura} sense substitut assignat").format(
                            hora=hora, professor=professor, assignatura=assignatura))
            
            # Validate vigilances (same logic as vigilancies_pdf.py)
            for vig in data_hora['vigilancies']:
                vigilant = vig.get('vigilant', '')
                aula = vig.get('aula', '')
                
                if vigilant and not vigilant.startswith("-- selecciona"):
                    # Absent vigilant
                    if vigilant in absents and hora in absents[vigilant]:
                        from utils.absence_utils import get_professor_absence_text
                        absence_text = get_professor_absence_text(vigilant, hora)
                        conflictes.append(_("⚠️ {hora}: Vigilant {vigilant} {absence_text}").format(
                            hora=hora, vigilant=vigilant, absence_text=absence_text.lower()))

                    # Duplicate vigilant
                    if vigilant in vigilants_assignats:
                        conflictes.append(_("🕐 {hora}: Vigilant {vigilant} duplicat").format(
                            hora=hora, vigilant=vigilant))
                    else:
                        vigilants_assignats.add(vigilant)
                
                if aula and aula != "ENLLAÇ":
                    # Duplicate classroom
                    if aula in aules_assignades:
                        conflictes.append(_("🏫 {hora}: Aula {aula} duplicada").format(
                            hora=hora, aula=aula))
                    else:
                        aules_assignades.add(aula)

                # Missing vigilant
                if not vigilant or vigilant.startswith("-- selecciona"):
                    tipus = vig.get('tipus', '')
                    tipus_traduit = _(tipus) if tipus else tipus
                    if tipus in ['VIGILÀNCIA', 'EXAMEN']:
                        conflictes.append(_("❌ {hora}: {tipus} sense vigilant assignat").format(
                            hora=hora, tipus=tipus_traduit))
                    else:
                        conflictes.append(_("❌ {hora}: Assignatura {tipus} sense vigilant assignat").format(
                            hora=hora, tipus=tipus_traduit))

                # Missing classroom
                if not aula:
                    tipus = vig.get('tipus', '')
                    tipus_traduit = _(tipus) if tipus else tipus
                    if tipus in ['VIGILÀNCIA', 'EXAMEN']:
                        conflictes.append(_("🏫 {hora}: {tipus} sense aula assignada").format(
                            hora=hora, tipus=tipus_traduit))
                    else:
                        conflictes.append(_("🏫 {hora}: Assignatura {tipus} sense aula assignada").format(
                            hora=hora, tipus=tipus_traduit))
        
        # NOVA VALIDACIÓ: Detectar substitucions duplicades per mateix professor (absent + vigilant)
        professors_amb_substitucions = defaultdict(list)
        for sub in substitucions:
            if sub.get("separador"):
                continue
            professor_absent = sub.get("professor_absent", "")
            hora = sub.get("hora", "")
            substitut = sub.get("substitut", "")
            assignatura = sub.get("assignatura", "")
            
            if professor_absent and hora and substitut and not substitut.startswith("---"):
                professors_amb_substitucions[professor_absent].append({
                    'hora': hora,
                    'substitut': substitut,
                    'assignatura': assignatura
                })
        
        # Comprovar si hi ha professors amb múltiples substitucions a la mateixa hora
        for professor, substitucions_prof in professors_amb_substitucions.items():
            hores_substitucions = defaultdict(list)
            for sub in substitucions_prof:
                hores_substitucions[sub['hora']].append(sub)
            
            for hora, subs_hora in hores_substitucions.items():
                if len(subs_hora) > 1:
                    # Hi ha múltiples substitucions pel mateix professor a la mateixa hora
                    substituts = [s['substitut'] for s in subs_hora]
                    assignatures = [s['assignatura'] for s in subs_hora]
                    conflictes.append(_("🔄 {hora}: {professor} té {num} substitucions (Substituts: {substituts} | Assignatures: {assignatures})").format(
                        hora=hora, professor=professor, num=len(subs_hora),
                        substituts=', '.join(substituts), assignatures=', '.join(assignatures)))
        
        return conflictes

    def _sort_vigilancies_by_date(self, vigilancies: List[Dict]) -> tuple:
        """Sort vigilancies by date and return organized data"""
        vigilancies_per_dia = defaultdict(lambda: defaultdict(list))
        dia_iso_map = {}

        for vig in vigilancies:
            dia = vig.get('_dia_interval', 'Dia desconegut')
            data_iso = vig.get('_data_iso', '')
            hora = vig.get('hora', '')
            if vig.get('_empty_day'):
                if data_iso:
                    dia_iso_map[dia] = data_iso
                # Ensure day exists even without hours
                _ = vigilancies_per_dia[dia]
                continue

            if hora:
                vigilancies_per_dia[dia][hora].append(vig)
                if data_iso:
                    dia_iso_map[dia] = data_iso

        dies_ordenats = sorted(vigilancies_per_dia.keys(),
                              key=lambda dia: dia_iso_map.get(dia, '9999-12-31'))

        return vigilancies_per_dia, dies_ordenats

    def _generate_day_section(self, dia: str, hores_dia: Dict, subs_dia: Dict = None) -> List:
        """Generate content for a single day section"""
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.platypus import Paragraph, Spacer

        story = []

        # Day title - aplicar compressió només si està activada
        if hasattr(self, '_auto_compression_active') and self._auto_compression_active:
            dia_style = ParagraphStyle(
                'DiaInterval',
                parent=self.custom_styles['hora'],
                fontSize=self.custom_styles['hora'].fontSize + 1,  # Reduït de +2 a +1
                spaceBefore=8,   # Reduït de 20 a 8
                spaceAfter=6,    # Reduït de 15 a 6
                textColor=colors.navy
            )
        else:
            dia_style = ParagraphStyle(
                'DiaInterval',
                parent=self.custom_styles['hora'],
                fontSize=self.custom_styles['hora'].fontSize + 2,
                spaceBefore=20,
                spaceAfter=15,
                textColor=colors.navy
            )
        story.append(Paragraph(_("📅 {dia}").format(dia=dia), dia_style))

        # Generate content for each hour
        for hora in self.hores:
            vigilancies_hora = hores_dia.get(hora, [])
            subs_hora = subs_dia.get(hora, []) if subs_dia else []

            if vigilancies_hora or subs_hora:
                # Hour title - aplicar compressió només si està activada
                if hasattr(self, '_auto_compression_active') and self._auto_compression_active:
                    hora_style = ParagraphStyle(
                        'HoraCompacte',
                        parent=self.custom_styles['hora'],
                        spaceBefore=4,   # Reduït espai abans
                        spaceAfter=2,    # Reduït espai després
                    )
                else:
                    hora_style = self.custom_styles['hora']

                story.append(Paragraph(_("🕐 {hora}").format(hora=hora), hora_style))

                # Substitutions table (if any)
                if subs_hora:
                    story.append(self._crear_taula_substitucions(subs_hora))
                    story.append(Spacer(1, PDFConstants.SPACER_SMALL))

                # Vigilance table (if any)
                if vigilancies_hora:
                    story.append(self._crear_taula_vigilancies(vigilancies_hora))

                # Space between hours - aplicar compressió només si està activada
                if hasattr(self, '_auto_compression_active') and self._auto_compression_active:
                    story.append(Spacer(1, PDFConstants.SPACER_SMALL))  # Més compacte
                else:
                    story.append(Spacer(1, PDFConstants.SPACER_LARGE))   # Normal

        return story

    def _generar_contingut_interval_vigilancies(self, vigilancies: List[Dict], substitucions: List[Dict] = None) -> List:
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
                dia = sub.get('_dia_interval', '')
                hora = sub.get('hora', '')
                if dia and hora:
                    subs_per_dia[dia][hora].append(sub)
            substitucions_per_dia = dict(subs_per_dia)

        # Generate content for each day
        for dia in dies_ordenats:
            subs_dia = substitucions_per_dia.get(dia, {})
            story.extend(self._generate_day_section(dia, vigilancies_per_dia[dia], subs_dia))

            # Espai entre dies - aplicar compressió només si està activada
            if hasattr(self, '_auto_compression_active') and self._auto_compression_active:
                story.append(Spacer(1, 0.2*cm))  # Reduït de 0.6 a 0.2
            else:
                story.append(Spacer(1, 0.6*cm))  # Espai normal

        return story


# Instància global per usar
pdf_complet_exporter = PDFCompletExporter()
