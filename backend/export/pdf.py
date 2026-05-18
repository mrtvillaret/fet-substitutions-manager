"""
Exportació millorada a PDF amb comentaris
"""
import os
from pathlib import Path
from typing import List, Dict
from datetime import datetime

# Import per a internacionalització
try:
    from i18n_setup import translate as _
except ImportError:
    # Fallback per a entorns sense internacionalització
    def _(text):
        return text

class PDFExporter:
    """Exportador millorat a PDF amb comentaris"""
    
    def __init__(self, export_dir: str = "exports"):
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(exist_ok=True)
    
    def exportar(self, substitucions: List[Dict], data_text: str) -> str:
        """Exporta substitucions a PDF amb comentaris"""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet
            
            # Nom del fitxer
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            filename = self.export_dir / f"substitucions_{timestamp}.pdf"
            
            # Crear document
            doc = SimpleDocTemplate(
                str(filename), 
                pagesize=A4,
                topMargin=30,
                bottomMargin=30,
                leftMargin=30,
                rightMargin=30
            )
            
            styles = getSampleStyleSheet()
            elements = []
            
            # Títol
            elements.append(Paragraph(_("<b>Substitucions de Professors</b>"), styles['Title']))
            elements.append(Paragraph(f"<b>{data_text}</b>", styles['Heading2']))
            elements.append(Spacer(1, 12))

            # Preparar dades per la taula (amb comentaris)
            table_data = [[_("Hora"), _("Absent"), _("Assignatura"), _("Grup"), _("Substitut"), _("Comentaris")]]
            
            # Filtra i processa substitucions
            substitucions_reals = []
            for sub in substitucions:
                if sub.get("separador"):
                    continue  # Saltar separadors per PDF
                
                # Format grup amb aula: "Grup (Aula)"
                grup = sub.get("grup", "") or ""
                aula = sub.get("aula", "") or ""
                grup_display = f"{grup} ({aula})" if aula else grup

                substitucions_reals.append([
                    sub.get("hora", ""),
                    sub.get("professor_absent", sub.get("professor", "")),
                    sub.get("assignatura", ""),
                    grup_display,
                    sub.get("substitut", "---"),
                    sub.get("comentaris", "")  # Nova columna
                ])
            
            if substitucions_reals:
                table_data.extend(substitucions_reals)
                
                # Crear taula amb amplades ajustades
                col_widths = [60, 80, 100, 80, 90, 120]  # 6 columnes
                table = Table(table_data, colWidths=col_widths)
                
                # Estil de la taula
                table_style = [
                    # Capçalera
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    
                    # Contingut
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    
                    # Alineació específica
                    ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Hora centrada
                    ('ALIGN', (1, 1), (4, -1), 'LEFT'),    # Text esquerra
                    ('ALIGN', (5, 1), (5, -1), 'LEFT'),    # Comentaris esquerra
                ]
                
                # Colors específics per substituts
                for i, row_data in enumerate(substitucions_reals, 1):
                    substitut = row_data[4]  # Columna substitut
                    if not substitut or substitut == "---":
                        # Fila sense substitut - vermell clar
                        table_style.append(('BACKGROUND', (4, i), (4, i), colors.lightpink))
                    else:
                        # Fila amb substitut - verd clar
                        table_style.append(('BACKGROUND', (4, i), (4, i), colors.lightgreen))
                
                table.setStyle(TableStyle(table_style))
                elements.append(table)
                
            else:
                elements.append(Paragraph(_("No hi ha substitucions per aquest dia."), styles['Normal']))
            
            # Estadístiques
            if substitucions_reals:
                elements.append(Spacer(1, 20))
                
                total = len(substitucions_reals)
                assignades = len([s for s in substitucions_reals if s[4] and s[4] != "---"])
                pendents = total - assignades
                
                stats_text = _("<b>Resum:</b> {total} substitucions totals | {assignades} assignades | {pendents} pendents").format(
                    total=total, assignades=assignades, pendents=pendents
                )
                
                elements.append(Paragraph(stats_text, styles['Normal']))
            
            # Peu de pàgina
            elements.append(Spacer(1, 20))
            timestamp_text = datetime.now().strftime("%d/%m/%Y %H:%M")
            elements.append(Paragraph(f"Generat: {timestamp_text}", styles['Normal']))
            
            # Generar PDF
            doc.build(elements)

            print(_("✅ S'ha generat el PDF: {filename}").format(filename=filename))
            return str(filename)

        except ImportError:
            print(_("⚠️ ReportLab no disponible, es generarà un fitxer de text..."))
            # Si no hi ha reportlab, crear fitxer de text
            return self._exportar_text(substitucions, data_text)
        except Exception as e:
            print(_("❌ Error en exportar PDF: {error}").format(error=e))
            return ""
    
    def _exportar_text(self, substitucions: List[Dict], data_text: str) -> str:
        """Exporta a text si no hi ha reportlab"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = self.export_dir / f"substitucions_{timestamp}.txt"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(_("SUBSTITUCIONS DE PROFESSORS") + "\n")
                f.write(f"{data_text}\n")
                f.write("=" * 80 + "\n\n")
                
                # Capçalera
                f.write(f"{_('Hora'):<8} | {_('Absent'):<15} | {_('Assignatura'):<15} | {_('Grup'):<10} | {_('Substitut'):<15} | {_('Comentaris'):<20}\n")
                f.write("-" * 80 + "\n")
                
                # Contingut
                for sub in substitucions:
                    if sub.get("separador"):
                        f.write(f"\n--- {sub['hora']} ---\n")
                    else:
                        # Format grup amb aula: "Grup (Aula)"
                        grup = sub.get("grup", "") or ""
                        aula = sub.get("aula", "") or ""
                        grup_display = f"{grup} ({aula})" if aula else grup

                        f.write(f"{sub.get('hora', ''):<8} | ")
                        f.write(f"{sub.get('professor_absent', sub.get('professor', '')):<15} | ")
                        f.write(f"{sub.get('assignatura', ''):<15} | ")
                        f.write(f"{grup_display:<10} | ")
                        f.write(f"{sub.get('substitut', '---'):<15} | ")
                        f.write(f"{sub.get('comentaris', ''):<20}\n")
                
                # Estadístiques
                subs_reals = [s for s in substitucions if not s.get("separador")]
                if subs_reals:
                    f.write(f"\n" + "=" * 80 + "\n")
                    f.write(_("RESUM: {total} substitucions").format(total=len(subs_reals)) + "\n")
                    assignades = len([s for s in subs_reals if s.get("substitut") and s.get("substitut") != "---"])
                    f.write(_("Assignades: {assignades} | Pendents: {pendents}").format(
                        assignades=assignades, pendents=len(subs_reals) - assignades) + "\n")
                
                f.write(_("\nGenerat: {timestamp}").format(
                    timestamp=datetime.now().strftime('%d/%m/%Y %H:%M')) + "\n")

            print(_("✅ S'ha generat el fitxer de text: {filename}").format(filename=filename))
            return str(filename)

        except Exception as e:
            print(_("❌ Error en generar fitxer de text: {error}").format(error=e))
            return ""

# Instància global
pdf_exporter = PDFExporter()
