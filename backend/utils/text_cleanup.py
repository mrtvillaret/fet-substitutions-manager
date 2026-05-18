# -*- coding: utf-8 -*-
"""
Text cleanup utilities - Consolidated from gui/widgets.py
Provides reusable text processing functions for emoji removal and professor name extraction
"""
import re


def extract_clean_professor_name(text_combo: str) -> str:
    """
    Extreu el nom net del professor del text formatat del combo
    Elimina emojis, sufixos i paràmetres extra

    Args:
        text_combo: Text del combo box amb formatació

    Returns:
        str: Nom net del professor
    """
    if text_combo.startswith("-- selecciona"):
        return ""

    # Extreu nom del professor del text (elimina emoji i paràmetres)
    text = text_combo.strip()

    # Elimina tots els emojis i caràcters Unicode de forma més agressiva
    # Patró més complet per eliminar tots els emojis i símbols Unicode
    emoji_pattern = r'[\U0001F000-\U0001FAFF\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\u2600-\u27BF\u2B00-\u2BFF\u2300-\u23FF\u2000-\u206F\uFE00-\uFE0F\u200D\u2190-\u21FF\u2700-\u27BF\U00002600-\U000026FF\U0001F900-\U0001F9FF]+'
    text = re.sub(emoji_pattern, '', text)

    # Elimina múltiples espais consecutius
    text = re.sub(r'\s+', ' ', text).strip()

    # Elimina sufixos de conservat
    if "[CONSERVAT]" in text:
        text = text.split("[CONSERVAT]")[0].strip()

    # Extreu nom fins el primer parèntesi
    if " (" in text:
        nom = text.split(" (")[0].strip()
    else:
        nom = text.strip()

    return nom


def clean_emoji_text(text: str) -> str:
    """
    Elimina emojis i caràcters Unicode especials de qualsevol text

    Args:
        text: Text amb possibles emojis

    Returns:
        str: Text sense emojis
    """
    # Patró complet per eliminar tots els emojis i símbols Unicode
    emoji_pattern = r'[\U0001F000-\U0001FAFF\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\u2600-\u27BF\u2B00-\u2BFF\u2300-\u23FF\u2000-\u206F\uFE00-\uFE0F\u200D\u2190-\u21FF\u2700-\u27BF\U00002600-\U000026FF\U0001F900-\U0001F9FF]+'
    text = re.sub(emoji_pattern, '', text)

    # Elimina múltiples espais consecutius
    text = re.sub(r'\s+', ' ', text).strip()

    return text