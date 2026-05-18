"""
Package d'exportació de PDFs
Arquitectura unificada per tots els tipus de PDFs del projecte
"""
from .engine import PDFCompletExporter, PDFConstants, open_pdf, pdf_complet_exporter

# GUI components are optional (only needed for desktop app)
try:
    from .combined_exporter import CombinedPDFExporter
    from .dialogs import mostrar_dialeg_opcions_pdf, mostrar_dialeg_compressio_pdf, mostrar_dialeg_pdf_combinat
    GUI_COMPONENTS_AVAILABLE = True
    __all__ = [
        'PDFCompletExporter', 'PDFConstants', 'open_pdf', 'pdf_complet_exporter',
        'CombinedPDFExporter',
        'mostrar_dialeg_opcions_pdf', 'mostrar_dialeg_compressio_pdf', 'mostrar_dialeg_pdf_combinat'
    ]
except ImportError:
    # Running in web backend without PySide6
    GUI_COMPONENTS_AVAILABLE = False
    CombinedPDFExporter = None
    mostrar_dialeg_opcions_pdf = None
    mostrar_dialeg_compressio_pdf = None
    mostrar_dialeg_pdf_combinat = None
    __all__ = [
        'PDFCompletExporter', 'PDFConstants', 'open_pdf', 'pdf_complet_exporter'
    ]
