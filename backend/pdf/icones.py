"""Icones dels avisos del PDF: els emojis del text es canvien per imatges
PNG (els visors de PDF no tenen els emojis)."""

from pathlib import Path

_CARPETA = Path(__file__).with_name("icones")
_ICONES = {"🕐": "clock.png", "🏫": "building.png", "⚠️": "warning.png", "❌": "error.png"}


def amb_icones(text: str) -> str:
    """El text amb cada emoji conegut canviat per la seva icona (etiqueta <img>
    d'un Paragraph de ReportLab)."""
    for emoji, fitxer in _ICONES.items():
        if emoji in text:
            text = text.replace(emoji, f'<img src="{_CARPETA / fitxer}" width="12" height="12" valign="middle"/>')
    return text
