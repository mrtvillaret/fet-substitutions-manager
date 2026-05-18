"""
Utilitat per gestionar fonts multiplataforma
"""
import sys
from pathlib import Path
from PySide6.QtGui import QFont, QFontDatabase

def get_monospace_font(size=10):
    """
    Retorna una font monospace robusta per a la plataforma actual
    """
    font = QFont()
    
    # Prioritats per plataforma
    if sys.platform == "win32":
        # Windows: Consolas és la millor, Courier New com fallback
        font.setFamily("Consolas")
        if not font.exactMatch():
            font.setFamily("Courier New")
    elif sys.platform == "darwin":
        # macOS: SF Mono és la millor, Menlo com fallback
        font.setFamily("SF Mono")
        if not font.exactMatch():
            font.setFamily("Menlo")
        if not font.exactMatch():
            font.setFamily("Monaco")
    else:
        # Linux: DejaVu Sans Mono és la que ja funciona
        font.setFamily("DejaVu Sans Mono")
        if not font.exactMatch():
            font.setFamily("Liberation Mono")
        if not font.exactMatch():
            font.setFamily("Courier New")
    
    # Configuració robusta
    font.setPointSize(size)
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setFixedPitch(True)
    
    return font

def get_ui_font(size=9, bold=False):
    """
    Retorna una font UI robusta per a la plataforma actual
    """
    font = QFont()
    
    # Prioritats per plataforma
    if sys.platform == "win32":
        font.setFamily("Segoe UI")
    elif sys.platform == "darwin":
        font.setFamily("SF Pro Display")
        if not font.exactMatch():
            font.setFamily("Helvetica Neue")
    else:
        # Linux: DejaVu Sans és estàndard
        font.setFamily("DejaVu Sans")
        if not font.exactMatch():
            font.setFamily("Liberation Sans")
        if not font.exactMatch():
            font.setFamily("Arial")
    
    font.setPointSize(size)
    if bold:
        font.setBold(True)
    
    return font