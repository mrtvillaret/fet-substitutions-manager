"""
Package d'exportació de PDFs
Arquitectura unificada per tots els tipus de PDFs del projecte
"""
from .engine import PDFCompletExporter, PDFConstants, open_pdf, pdf_complet_exporter

__all__ = ['PDFCompletExporter', 'PDFConstants', 'open_pdf', 'pdf_complet_exporter']
