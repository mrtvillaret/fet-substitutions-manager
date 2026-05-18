import gettext
import os
import logging

# Dominis de traducció modular
DOMAINS = ["messages", "gui", "core", "export", "utils", "manual"]

# Camí al directori de traduccions
LOCALE_DIR = os.path.join(os.path.dirname(__file__), "locales")

# Variable global per a la funció de traducció
_ = gettext.gettext

# Variable global per l'idioma actual (usat per Babel i altres components)
CURRENT_LANGUAGE = 'ca'


def translate(text: str) -> str:
    """Wrapper per obtenir la traducció amb l'estat actual."""
    return _(text)


def setup_translation(language: str = 'ca'):
    """
    Configura gettext per carregar les traduccions de l'idioma especificat.
    Carrega múltiples dominis (gui, core, export, utils) i els combina.

    Args:
        language (str): El codi de l'idioma (p.ex., 'en', 'es', 'ca').
    """
    global _, CURRENT_LANGUAGE

    try:
        # Carrega tots els dominis i combina'ls
        translations = []
        for domain in DOMAINS:
            try:
                trans = gettext.translation(
                    domain,
                    localedir=LOCALE_DIR,
                    languages=[language],
                    fallback=True
                )
                translations.append(trans)
                logging.info(f"Domini '{domain}' carregat per a l'idioma '{language}'")
            except FileNotFoundError:
                logging.warning(f"No s'ha trobat el domini '{domain}' per a l'idioma '{language}'")

        # Si hem carregat algun domini, combinem les traduccions
        if translations:
            # Utilitzem el primer com a base
            combined_translation = translations[0]

            # Afegim els altres dominis
            for trans in translations[1:]:
                combined_translation.add_fallback(trans)

            combined_translation.install()
            _ = combined_translation.gettext

            logging.info(f"Traduccions per a l'idioma '{language}' carregades correctament des de {LOCALE_DIR}.")
        else:
            # Si no hem carregat cap domini, usem fallback
            _ = gettext.gettext
            logging.warning(f"No s'ha pogut carregar cap traducció per a '{language}'. S'utilitzarà el text original.")

        # Actualitza idioma actual per Babel
        CURRENT_LANGUAGE = language

    except Exception as e:
        logging.error(f"S'ha produït un error en carregar les traduccions: {e}")
        _ = gettext.gettext
        CURRENT_LANGUAGE = language
