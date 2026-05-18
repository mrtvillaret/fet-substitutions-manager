"""
Factory d'estils PDF consolidats per eliminar duplicació
Centralitza configuració d'estils ReportLab usats en tots els exportadors PDF
"""
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import json
from pathlib import Path

# Try to import hyphenation support
try:
    import pyphen
    HYPHEN_AVAILABLE = True
except ImportError:
    HYPHEN_AVAILABLE = False
    pyphen = None


class PDFStyleFactory:
    """Factory per generar estils PDF estandarditzats"""
    
    _config_cache = None
    _config_last_modified = None
    
    @staticmethod
    def _load_pdf_config():
        """Carrega configuració PDF completa des del pdf.json amb cache intelligent"""
        import os
        
        try:
            # Try multiple possible paths
            possible_paths = [
                Path('config/pdf.json'),
                Path('../config/pdf.json'),
                Path(__file__).parent.parent / 'config/pdf.json'
            ]
            
            config_path = None
            for path in possible_paths:
                if path.exists():
                    config_path = path
                    break
            
            if config_path:
                # Check if file has been modified
                current_mtime = os.path.getmtime(config_path)
                
                if (PDFStyleFactory._config_cache is not None and 
                    PDFStyleFactory._config_last_modified == current_mtime):
                    return PDFStyleFactory._config_cache
                
                # Load and cache config
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    PDFStyleFactory._config_cache = config
                    PDFStyleFactory._config_last_modified = current_mtime
                    return config
                        
        except Exception as e:
            print(f"Error loading PDF config: {e}")
        
        print("Using fallback PDF config")
        # Fallback per defecte
        return {
            "font_sizes": {
                "title": 18,
                "hora": 12,
                "conflicte": 10,
                "table_header": 11,
                "table_body": 12
            },
            "hyphenation": {"enabled": False, "language": "ca"},
            "print_profile": "screen",
            "print_profiles": {
                "screen": {
                    "name": "Pantalla/Digital",
                    "substitutions_header_bg": "#2c3e50",
                    "substitutions_header_text": "#ffffff",
                    "vigilances_header_bg": "#17a2b8", 
                    "vigilances_header_text": "#ffffff",
                    "content_bg": "#f8f9fa",
                    "grid_color": "#dee2e6",
                    "grid_width": 0.5,
                    "use_header_line": False,
                    "conflict_color": "#c0392b",
                    "hour_color": "#c0392b"
                }
            }
        }
    
    @staticmethod
    def get_current_profile_colors():
        """Retorna els colors del perfil PDF actiu"""
        pdf_config = PDFStyleFactory._load_pdf_config()
        current_profile = pdf_config.get('print_profile', 'screen')
        profiles = pdf_config.get('print_profiles', {})
        
        if current_profile in profiles:
            return profiles[current_profile]
        
        # Fallback hardcoded si no hi ha cap perfil
        fallback_profile = {
            "substitutions_header_bg": "#2c3e50",
            "substitutions_header_text": "#ffffff",
            "vigilances_header_bg": "#17a2b8", 
            "vigilances_header_text": "#ffffff",
            "content_bg": "#f8f9fa",
            "grid_color": "#dee2e6",
            "grid_width": 0.5,
            "use_header_line": False,
            "conflict_color": "#c0392b",
            "hour_color": "#c0392b"
        }
        
        return profiles.get('screen', fallback_profile)
    
    @staticmethod
    def get_standard_styles():
        """Retorna estils estandarditzats per tots els PDFs"""
        base_styles = getSampleStyleSheet()
        pdf_config = PDFStyleFactory._load_pdf_config()
        fonts = pdf_config.get('font_sizes', {})
        config = pdf_config
        
        # Get colors from current profile
        profile_colors = PDFStyleFactory.get_current_profile_colors()
        
        # Setup hyphenation if available and enabled
        hyphen_lang = None
        hyphenation_config = config.get('hyphenation', {})
        if (HYPHEN_AVAILABLE and 
            hyphenation_config.get('enabled', False) and 
            pyphen):
            try:
                # Use pyphen - much simpler and works with Catalan
                hyphen_lang = pyphen.Pyphen(lang=hyphenation_config.get('language', 'ca'))
            except Exception as e:
                print(f"Warning: Could not load hyphenation for {hyphenation_config.get('language', 'ca')}: {e}")
                hyphen_lang = None
        
        # Estils personalitzats comuns
        custom_styles = {
            'title': ParagraphStyle(
                'CustomTitle',
                parent=base_styles['Heading1'],
                fontSize=fonts.get('title', 18),
                spaceAfter=20,
                alignment=1,
                textColor=colors.HexColor('#2c3e50'),  # Blau fosc professional
                fontName='Helvetica-Bold',
                hyphenationLang=hyphenation_config.get('language', 'ca') if hyphen_lang else None,
                embeddedHyphenation=1 if hyphen_lang else 0
            ),
            
            'hora': ParagraphStyle(
                'HoraTitle',
                parent=base_styles['Heading2'],
                fontSize=fonts.get('hora', 12),
                spaceAfter=5,
                spaceBefore=15,
                textColor=colors.HexColor(profile_colors.get('hour_color', '#c0392b')),
                fontName='Helvetica-Bold',
                hyphenationLang=hyphenation_config.get('language', 'ca') if hyphen_lang else None,
                embeddedHyphenation=1 if hyphen_lang else 0
            ),
            
            'conflicte': ParagraphStyle(
                'Conflicte',
                parent=base_styles['Normal'],
                fontSize=fonts.get('conflicte', 10),
                textColor=colors.HexColor(profile_colors.get('conflict_color', '#e74c3c')),
                leftIndent=30,
                fontName='Helvetica',
                hyphenationLang=hyphenation_config.get('language', 'ca') if hyphen_lang else None,
                embeddedHyphenation=1 if hyphen_lang else 0
            ),
            
            'normal': base_styles['Normal'],
            'heading1': base_styles['Heading1'],
            'heading2': base_styles['Heading2']
        }
        
        return custom_styles
    
    @staticmethod
    def get_table_styles():
        """Retorna estils estandarditzats per taules"""
        from reportlab.platypus import TableStyle
        pdf_config = PDFStyleFactory._load_pdf_config()
        fonts = pdf_config.get('font_sizes', {})
        config = pdf_config
        
        # Estil estàndard per taules
        standard_table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),  # Header fosc
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), fonts.get('table_header', 11)),
            ('FONTSIZE', (0, 1), (-1, -1), fonts.get('table_body', 9)),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),  # Files clares
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7'))
        ])
        
        return {
            'standard': standard_table_style
        }