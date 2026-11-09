"""Escapat del text de les dades abans de passar-lo a ReportLab."""

import html


def _text(valor) -> str:
    """Text de les dades (noms, aules, comentaris...) apte per a un Paragraph.

    ReportLab interpreta etiquetes dins dels Paragraph (<b>, <font>, <img
    src=...>): sense escapar, un "<" escrit per un usuari trencava el PDF i un
    <img> li feia llegir fitxers del servidor."""
    return html.escape(str(valor or ""), quote=False)
