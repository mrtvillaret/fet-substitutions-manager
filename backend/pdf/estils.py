"""
Estils comuns dels PDF (ReportLab), a partir de config/pdf.json
(estils de paràgraf i colors del perfil actiu).
"""

import json
import logging
import os
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

log = logging.getLogger(__name__)


class PDFStyleFactory:
    """Factory per generar estils PDF estandarditzats"""

    _config_cache = None
    _config_last_modified = None

    @staticmethod
    def _load_pdf_config():
        """Carrega configuració PDF completa des del pdf.json amb cache intelligent"""

        try:
            # Al costat del codi, no segons la carpeta des d'on s'arrenca
            config_path = Path(__file__).parent.parent / "config/pdf.json"
            if config_path.exists():
                # Check if file has been modified
                current_mtime = os.path.getmtime(config_path)

                if PDFStyleFactory._config_cache is not None and PDFStyleFactory._config_last_modified == current_mtime:
                    return PDFStyleFactory._config_cache

                # Load and cache config
                with open(config_path, encoding="utf-8") as f:
                    config = json.load(f)
                    PDFStyleFactory._config_cache = config
                    PDFStyleFactory._config_last_modified = current_mtime
                    return config

        except Exception as e:
            log.warning(f"Error loading PDF config: {e}")

        log.warning("Using fallback PDF config")
        # Fallback per defecte
        return {
            "font_sizes": {"title": 18, "hora": 12, "conflicte": 10, "table_header": 11, "table_body": 12},
            "print_profile": "screen",
            "print_profiles": {
                "screen": {
                    "name": "Pantalla/Digital",
                    "substitutions_header_bg": "#2c3e50",
                    "substitutions_header_text": "#ffffff",
                    "content_bg": "#ffffff",
                    "grid_color": "#808080",
                    "grid_width": 0.6,
                    "use_header_line": False,
                    "conflict_color": "#c0392b",
                    "hour_color": "#c0392b",
                }
            },
        }

    @staticmethod
    def get_current_profile_colors():
        """Retorna els colors del perfil PDF actiu"""
        pdf_config = PDFStyleFactory._load_pdf_config()
        current_profile = pdf_config.get("print_profile", "screen")
        profiles = pdf_config.get("print_profiles", {})

        if current_profile in profiles:
            return profiles[current_profile]

        # Fallback hardcoded si no hi ha cap perfil
        fallback_profile = {
            "substitutions_header_bg": "#2c3e50",
            "substitutions_header_text": "#ffffff",
            "content_bg": "#ffffff",
            "grid_color": "#808080",
            "grid_width": 0.6,
            "use_header_line": False,
            "conflict_color": "#c0392b",
            "hour_color": "#c0392b",
        }

        return profiles.get("screen", fallback_profile)

    @staticmethod
    def get_standard_styles():
        """Retorna estils estandarditzats per tots els PDFs"""
        base_styles = getSampleStyleSheet()
        pdf_config = PDFStyleFactory._load_pdf_config()
        fonts = pdf_config.get("font_sizes", {})

        # Get colors from current profile
        profile_colors = PDFStyleFactory.get_current_profile_colors()

        # Estils personalitzats comuns
        custom_styles = {
            "title": ParagraphStyle(
                "CustomTitle",
                parent=base_styles["Heading1"],
                fontSize=fonts.get("title", 18),
                spaceAfter=20,
                alignment=1,
                textColor=colors.HexColor("#2c3e50"),  # Blau fosc professional
                fontName="Helvetica-Bold",
            ),
            "hora": ParagraphStyle(
                "HoraTitle",
                parent=base_styles["Heading2"],
                fontSize=fonts.get("hora", 12),
                spaceAfter=5,
                spaceBefore=15,
                textColor=colors.HexColor(profile_colors.get("hour_color", "#c0392b")),
                fontName="Helvetica-Bold",
            ),
            "conflicte": ParagraphStyle(
                "Conflicte",
                parent=base_styles["Normal"],
                fontSize=fonts.get("conflicte", 10),
                textColor=colors.HexColor(profile_colors.get("conflict_color", "#e74c3c")),
                leftIndent=30,
                fontName="Helvetica",
            ),
            "normal": base_styles["Normal"],
            "heading1": base_styles["Heading1"],
            "heading2": base_styles["Heading2"],
        }

        return custom_styles
