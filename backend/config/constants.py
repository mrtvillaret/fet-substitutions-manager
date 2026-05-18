"""
Constants globals del sistema
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

try:
    from i18n_setup import translate as _
except ImportError:
    def _(text):
        return text

# Dies de la setmana (adaptats al nou teachers.xml de demo - en castellà)
# DEPRECATED: Utilitza horari.dies de l'XML carregat
DIES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

PRIORITATS = {}
NO_SUBST = set()
ORDRE_PRIORITATS = []
CATEGORIES_ACTIVES = []
PROFESSORS_BAIXA = []

# Assignatures que generen substitucions encadenades (estan a PRIORITATS però NO a NO_SUBST)
GENERA_ENCADENADES = [tipus for tipus in PRIORITATS if tipus not in NO_SUBST]

# Colors per la interfície
COLORS = {
    "SEPARADOR": (210, 210, 210),
    "DISPONIBLE": (150, 250, 150),
    "ALLIBERAT": (100, 200, 255),
    "OCUPAT": (250, 150, 150),
    "ABSENT": (255, 255, 150)
}
# Ordre personalitzat de grups
ORDRE_GRUPS = [
    "BAC2A", "BAC2B",
    "BAC1A", "BAC1B",
    "ESO4A", "ESO4B", "ESO4C",
    "ESO3A", "ESO3B", "ESO3C", "ESO3D",
    "ESO2A", "ESO2B", "ESO2C", "ESO2D",
    "ESO1A", "ESO1B", "ESO1C", "ESO1D",
]

# Directoris del sistema
DIRECTORIS = {
    "DATA": "data",
    "EXPORTS": "exports",
    "THEMES": "gui/themes",
}

# Versió de l'aplicació
VERSION = "3.0.0"

# Configuració del sistema
def get_adaptive_window_sizes():
    """Retorna mides adaptades a la resolució de pantalla"""
    try:
        from PySide6.QtGui import QGuiApplication
        app = QGuiApplication.instance()
        if app:
            screen = app.primaryScreen()
            if screen:
                size = screen.availableSize()  # Exclou barra de tasques
                width, height = size.width(), size.height()
                
                # Per portàtils petits (≤1400x800) - més generós
                if width <= 1400:
                    return {
                        "MIN_WINDOW_WIDTH": min(1050, width - 150),  # 1368-150=1218, però limitem a 1050
                        "MIN_WINDOW_HEIGHT": min(650, height - 118), # 768-118=650
                        "TABLE_WIDTH": min(950, width - 250)
                    }
                # Per pantalles grans
                else:
                    return {
                        "MIN_WINDOW_WIDTH": 1200,
                        "MIN_WINDOW_HEIGHT": 800,
                        "TABLE_WIDTH": 1200
                    }
    except:
        pass
    
    # Fallback segur per portàtils (ultra conservador)
    return {
        "MIN_WINDOW_WIDTH": 950,   # Ultra conservador per 1368x768
        "MIN_WINDOW_HEIGHT": 600,  
        "TABLE_WIDTH": 850
    }

def should_auto_maximize():
    """Retorna True si la resolució és baixa i s'ha de maximitzar automàticament"""
    try:
        from PySide6.QtGui import QGuiApplication
        app = QGuiApplication.instance()
        if app and app.primaryScreen():
            size = app.primaryScreen().availableSize()
            width, height = size.width(), size.height()
            # Auto-maximitzar si resolució ≤ 1400x900 (portàtils petits)
            return width <= 1400 or height <= 900
    except:
        pass
    return False

# EMOJI MAPPING FOR PROFESSOR TYPES
# Consolidated from gui/widgets.py to reduce duplication
PROFESSOR_TYPE_EMOJIS = {
    # Categoria 0 - Prioritat màxima
    'reforç': '⭐',
    'alliberat': '✅',

    # Categoria 1 - Guàrdies
    'guàrdia': '🛡️',
    'guàrdia-r': '🔁',  # Guàrdia de reforç
    'guàrdia-t': '📚',  # Guàrdia de tutoria
    'guàrdia-p': '⛪',  # Guàrdia pastoral

    # Categoria 2 - Activitats específiques
    'web': '💻',
    'informàtica': '🖥️',
    'correcció': '✏️',
    'bat dual': '🎓',

    # Categoria 3
    'reforç-a': '⭐',  # Reforç avançat

    # Categoria 4
    'cd': '👨‍💼',  # Cap de departament

    # Categoria 5
    'alumnes': '👥',
    'alumnes-batx': '👨‍🎓',

    # Categoria 6
    'orientació': '🧭',

    # Categoria 7
    'gp': '🌳',  # Guàrdia pati

    # Altres possibles
    'disponible': '🟢',
    'lliure': '⚪'
}

def get_professor_emoji(tipus: str) -> str:
    """Retorna emoji per tipus de professor (consolidated helper)"""
    tipus_lower = tipus.lower()
    for key, emoji in PROFESSOR_TYPE_EMOJIS.items():
        if key in tipus_lower:
            return emoji
    return '🟢'  # Emoji per defecte per disponibles genèrics

def apply_safe_window_size(window):
    """Aplica mides segures a una finestra després del tema amb DEBUG"""
    try:
        from PySide6.QtGui import QGuiApplication
        
        # Info de pantalla
        app = QGuiApplication.instance()
        if app and app.primaryScreen():
            screen_size = app.primaryScreen().availableSize()
            print(f"🖥️  Pantalla disponible: {screen_size.width()}x{screen_size.height()}")
        
        adaptive_sizes = get_adaptive_window_sizes()
        min_w = adaptive_sizes["MIN_WINDOW_WIDTH"]
        min_h = adaptive_sizes["MIN_WINDOW_HEIGHT"]
        print(f"📏 Mides objectives: {min_w}x{min_h}")
        
        # Mida actual ABANS
        current_size = window.size()
        print(f"📐 Mida actual finestra: {current_size.width()}x{current_size.height()}")
        
        # Mida mínima dels widgets interns
        size_hint = window.sizeHint()
        minimum_size = window.minimumSizeHint()
        print(f"💡 sizeHint: {size_hint.width()}x{size_hint.height()}")
        print(f"⚠️  minimumSizeHint: {minimum_size.width()}x{minimum_size.height()}")
        
        # Aplicar mides amb marge de seguretat
        window.setMinimumSize(min_w, min_h)
        
        # Auto-maximitzar en resolucions baixes
        if should_auto_maximize():
            print(f"🔍 Resolució baixa detectada - maximitzant finestra automàticament")
            window.showMaximized()
        else:
            # Forçar ajust si és massa gran
            if current_size.width() > min_w * 1.5 or current_size.height() > min_h * 1.5:
                print(f"🔧 Reduint finestra de {current_size.width()}x{current_size.height()} a {min_w}x{min_h}")
                window.resize(min_w, min_h)
            
        # Mida DESPRÉS
        final_size = window.size()
        print(f"✅ Mida final: {final_size.width()}x{final_size.height()}")
        
        # Verificar si cap a la pantalla
        if app and app.primaryScreen():
            screen_size = app.primaryScreen().availableSize()
            if final_size.width() > screen_size.width() or final_size.height() > screen_size.height():
                print(f"❌ PROBLEMA: Finestra ({final_size.width()}x{final_size.height()}) no cap a pantalla ({screen_size.width()}x{screen_size.height()})")
            else:
                print(f"✅ Finestra cap correctament a pantalla")
            
    except Exception as e:
        print(f"❌ Error en apply_safe_window_size: {e}")
        # Fallback ultra-segur
        window.setMinimumSize(1000, 600)
        window.resize(1000, 600)

CONFIG_SISTEMA = {
    "LOG_FILE": "substitucions.log",
    "ENCODING": "utf-8",
    "MIN_WINDOW_WIDTH": 1100,  # Reduït per compatibilitat
    "MIN_WINDOW_HEIGHT": 650,  # Reduït per compatibilitat
    "TABLE_FONT_SIZE": 10,
}

# Nivells educatius - DINÀMICS (carregats de SQLite)
def get_nivells():
    """
    Llegeix nivells dinàmicament de la BD de la institució actual.
    """
    from config.settings import config
    from database import get_data_db_session
    from repositories import MasterConfigRepository

    instit = config.global_data.get("institucio") or os.getenv("APP_INSTITUCIO") or config.detectar_institucio()
    if not instit:
        return ["GENERAL"]

    try:
        with get_data_db_session(instit) as db:
            data = MasterConfigRepository.get_master_config(db)
            nivells = list(data.get("nivells", {}).keys())
            if "GENERAL" not in nivells:
                nivells.append("GENERAL")
            return nivells
    except Exception as e:
        print(f"⚠️ Error carregant nivells de BD: {e}")

    # Fallback si no hi ha master_configuracio.json (primera execució)
    return ["GENERAL"]

# Variable global (es carrega dinàmicament)
NIVELLS = get_nivells()

# Mapping entre noms d'interfície (UI) i noms de dades (JSON)
# DEPRECATED: Els nivells ara es llegeixen directament de grups.json
# Aquest mapping només es manté per compatibilitat amb codi antic
NIVELLS_UI_TO_DATA = {nivell: nivell for nivell in NIVELLS}

# Mapping invers per convertir de dades a UI
NIVELLS_DATA_TO_UI = {v: k for k, v in NIVELLS_UI_TO_DATA.items()}

# Opcions de vigilància
TIPUS_VIGILANCIA = ["VIGILÀNCIA", "ENLLAÇ"]

# HORES, HORES_ORDRE, HORES_MAPPING i normalitzar_hora() han estat eliminats
# Les hores es carreguen dinàmicament des de l'XML via horari.hores
