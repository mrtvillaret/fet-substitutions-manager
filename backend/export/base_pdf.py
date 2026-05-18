"""
Base PDF Exporter - Consolidates common PDF functionality
Eliminates 70% of duplicate code across export modules
"""
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from .pdf_images import pdf_images
from typing import List, Dict

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer, Paragraph

from config.constants import DIRECTORIS
from .pdf_styles import PDFStyleFactory

try:
    from i18n_setup import translate as _
except ImportError:
    def _(text):
        return text


class BasePDFExporter:
    """Base class for all PDF exporters with common functionality"""
    
    def __init__(self, export_dir: str = None, hores: List[str] = None):
        self.export_dir = Path(export_dir or DIRECTORIS["EXPORTS"])
        self.export_dir.mkdir(exist_ok=True)
        self.hores = hores if hores is not None else []
        self.styles = getSampleStyleSheet()
        self.custom_styles = PDFStyleFactory.get_standard_styles()
        self.table_styles = PDFStyleFactory.get_table_styles()
    
    # Mètode eliminat - estils ara venen de PDFStyleFactory
    
    def _create_document(self, filename: str, landscape_mode: bool = False) -> SimpleDocTemplate:
        """Creates a PDF document with standard settings"""
        pagesize = landscape(A4) if landscape_mode else A4
        return SimpleDocTemplate(
            str(filename),
            pagesize=pagesize,
            topMargin=30 if not landscape_mode else 1.5*cm,
            bottomMargin=30 if not landscape_mode else 1.5*cm,
            leftMargin=30 if not landscape_mode else 1.5*cm,
            rightMargin=30 if not landscape_mode else 1.5*cm
        )
    
    def _agrupar_per_hora(self, items: List[Dict], hora_key: str = "hora") -> Dict[str, List[Dict]]:
        """Groups items by hour using HORES order"""
        per_hora = defaultdict(list)
        
        for item in items:
            if item.get("separador"):  # Skip separators
                continue
            hora = item.get(hora_key, "")
            if hora:
                per_hora[hora].append(item)
        
        # Order according to XML hours
        per_hora_ordenat = {}
        for hora in self.hores:
            if hora in per_hora:
                per_hora_ordenat[hora] = per_hora[hora]
        
        # Add any hours not in HORES (safety)
        for hora in per_hora:
            if hora not in per_hora_ordenat:
                per_hora_ordenat[hora] = per_hora[hora]
        
        return per_hora_ordenat
    
    def _create_header_elements(self, title: str, data_text: str) -> List:
        """Creates standard header elements"""
        elements = []
        elements.append(Paragraph(f"<b>{title}</b>", self.styles['Title']))
        elements.append(Paragraph(f"<b>{data_text}</b>", self.styles['Heading2']))
        elements.append(Spacer(1, 20))
        return elements
    
    def _create_footer_elements(self) -> List:
        """Creates standard footer elements"""
        elements = []
        elements.append(Spacer(1, 20))
        timestamp_text = datetime.now().strftime("%d/%m/%Y %H:%M")
        elements.append(Paragraph(f"Generat: {timestamp_text}", self.styles['Normal']))
        return elements
    
    def _create_table_with_style(self, data: List[List], col_widths: List, 
                                header_color: str = '#3498db', 
                                content_color: str = '#d6eaf8',
                                grid_color: str = '#aed6f1') -> Table:
        """Creates a styled table with standard formatting"""
        table = Table(data, colWidths=col_widths)
        
        style = [
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(header_color)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            
            # Content
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor(content_color)),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor(grid_color)),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]
        
        table.setStyle(TableStyle(style))
        return table
    
    def _obrir_pdf(self, filename: str):
        """Opens PDF automatically across platforms"""
        try:
            if os.getenv("OPEN_PDF", "0") != "1":
                return
            if sys.platform == "win32":
                os.startfile(filename)
            elif sys.platform == "darwin":
                subprocess.run(["open", filename])
            else:
                subprocess.run(["xdg-open", filename])
                print(_("✅ S'ha obert el PDF amb xdg-open"))
        except Exception as e:
            print(_("⚠️ No s'ha pogut obrir automàticament: {error}").format(error=e))
    
    def _exportar_text(self, items: List[Dict], data_text: str, 
                      filename_prefix: str, headers: List[str],
                      format_row_func) -> str:
        """Generic text export fallback"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = self.export_dir / f"{filename_prefix}_{timestamp}.txt"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"{filename_prefix.upper().replace('_', ' ')}\n")
                f.write(f"{data_text}\n")
                f.write("=" * 80 + "\n\n")
                
                # Group by hour
                items_per_hora = self._agrupar_per_hora(items)
                
                for hora in items_per_hora.keys():
                    hora_text = pdf_images.format_conflict_text(f"🕐 {hora}")
                    f.write(f"{hora_text}\n")
                    f.write("-" * 70 + "\n")
                    
                    # Header
                    header_line = " | ".join(f"{h:<15}" for h in headers)
                    f.write(header_line + "\n")
                    f.write("-" * 80 + "\n")
                    
                    # Content
                    for item in items_per_hora[hora]:
                        row_line = format_row_func(item)
                        f.write(row_line + "\n")
                    
                    f.write("\n")
                
                # Statistics
                f.write(f"\n" + "=" * 80 + "\n")
                f.write(_("RESUM: {num} elements").format(num=len(items)) + "\n")
                f.write(f"\nGenerat: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n")

            print(_("✅ S'ha generat el fitxer de text: {filename}").format(filename=filename))
            return str(filename)

        except Exception as e:
            print(_("❌ Error en generar fitxer de text: {error}").format(error=e))
            return ""
    
    def _calculate_statistics(self, items: List[Dict], count_field: str = None) -> Dict:
        """Calculate basic statistics for items"""
        stats = {
            'total': len(items),
            'assigned': 0,
            'pending': 0,
            'by_type': defaultdict(int)
        }
        
        for item in items:
            if count_field and item.get(count_field):
                stats['assigned'] += 1
            elif count_field and not item.get(count_field):
                stats['pending'] += 1
            
            # Count by type if available
            type_field = item.get('tipus', '') or item.get('tipus_substitut', '')
            if type_field:
                stats['by_type'][type_field] += 1
        
        if count_field:
            stats['pending'] = stats['total'] - stats['assigned']
        
        return stats
