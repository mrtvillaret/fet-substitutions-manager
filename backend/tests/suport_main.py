"""
L'app sencera (main.app) dins del procés dels tests, amb els permisos de cada
router tal com són a main.py. En importar-se, main.py carrega el .env i crea
els usuaris inicials si la taula és buida: aquí el .env no es llegeix (els
tests tenen el seu entorn, conftest.py) i abans ja hi ha un usuari.
"""

from unittest import mock

from suport_api import crea_usuari


def app_sencera():
    import sys

    if "main" not in sys.modules:
        crea_usuari("usuari_d_abans_de_main", "centre_d_abans_de_main")
        with mock.patch("dotenv.load_dotenv"):
            import main  # noqa: F401
    return sys.modules["main"].app
