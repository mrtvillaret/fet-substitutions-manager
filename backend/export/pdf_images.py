"""
Gestió d'imatges per PDFs - Substitueix emojis per icones visuals
"""

import os
from reportlab.platypus import Image
from reportlab.lib.units import inch

try:
    from i18n_setup import translate as _
except ImportError:
    def _(text):
        return text

class PDFImageManager:
    """Gestiona les imatges per usar als PDFs en lloc d'emojis"""
    
    def __init__(self):
        """Inicialitza el gestor d'imatges"""
        self.images_dir = os.path.join(os.path.dirname(__file__), "images")
        self.image_size = 0.15 * inch  # Mida petita per alinear amb text
        
        # Mapatge emoji -> fitxer imatge PNG
        self.emoji_map = {
            '🕐': 'clock.png',
            '🏫': 'building.png', 
            '⚠️': 'warning.png',
            '❌': 'error.png'
        }
    
    def get_image_path(self, emoji: str) -> str:
        """Obté el path complet d'una imatge per emoji"""
        if emoji in self.emoji_map:
            return os.path.join(self.images_dir, self.emoji_map[emoji])
        return None
    
    def create_image_object(self, emoji: str) -> Image:
        """Crea un objecte Image de ReportLab per l'emoji donat"""
        image_path = self.get_image_path(emoji)
        if image_path and os.path.exists(image_path):
            return Image(image_path, width=self.image_size, height=self.image_size)
        return None
    
    def replace_emojis_with_images(self, text: str) -> list:
        """
        Converteix text amb emojis en una llista d'elements (text + imatges)
        
        Args:
            text: Text que pot contenir emojis
            
        Returns:
            list: Llista d'elements per afegir al PDF (strings i Images)
        """
        elements = []
        current_text = ""
        
        i = 0
        while i < len(text):
            char = text[i]
            
            # Comprova si és un emoji que tenim mapejat
            emoji_found = None
            for emoji in self.emoji_map:
                if text[i:].startswith(emoji):
                    emoji_found = emoji
                    break
            
            if emoji_found:
                # Afegeix el text acumulat abans de l'emoji
                if current_text:
                    elements.append(current_text)
                    current_text = ""
                
                # Afegeix la imatge
                image = self.create_image_object(emoji_found)
                if image:
                    elements.append(image)
                else:
                    # Si no es pot carregar la imatge, usa text alternatiu
                    alt_text = {
                        '🕐': '[HORA]',
                        '🏫': '[AULA]', 
                        '⚠️': '[AVÍS]',
                        '❌': '[ERROR]'
                    }.get(emoji_found, emoji_found)
                    elements.append(alt_text)
                
                # Avança l'índex segons la longitud de l'emoji
                i += len(emoji_found)
            else:
                # Caràcter normal, afegeix al text actual
                current_text += char
                i += 1
        
        # Afegeix qualsevol text final
        if current_text:
            elements.append(current_text)
        
        return elements
    
    def format_conflict_text(self, conflict_text: str) -> str:
        """
        Formata text de conflicte substituint emojis per imatges inline
        o fallback a caràcters Unicode si les imatges fallen
        """
        # Intent d'usar imatges per als PDFs
        for emoji in self.emoji_map:
            if emoji in conflict_text:
                image_path = self.get_image_path(emoji)
                if image_path and os.path.exists(image_path):
                    # ReportLab suporta imatges dins paragraphs amb tags especials
                    img_tag = f'<img src="{image_path}" width="12" height="12" valign="middle"/>'
                    conflict_text = conflict_text.replace(emoji, img_tag)
                else:
                    # Fallback a símbols Unicode si la imatge no existeix
                    fallback_symbols = {
                        '🕐': '●',   # Bullet per hora
                        '🏫': '■',   # Black square per aula  
                        '⚠️': '▲',   # Triangle per avís
                        '❌': '✖'    # Heavy multiplication X per error
                    }
                    if emoji in fallback_symbols:
                        conflict_text = conflict_text.replace(emoji, fallback_symbols[emoji])
        
        return conflict_text

# Instància global per usar al codi
pdf_images = PDFImageManager()
