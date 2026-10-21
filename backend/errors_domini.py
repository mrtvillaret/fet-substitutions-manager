"""
Errors del domini: el que llancen els serveis quan una regla no es compleix.

Els serveis no saben res d'HTTP: diuen de quina mena és l'error (no trobat,
no permès, no vàlid, conflicte). Quin status li correspon i com es respon ho
decideix errors_servidor.py.

Cada error porta el missatge per a l'usuari i un codi estable (p. ex.
"contrasenya_curta"), amb uns paràmetres opcionals ({"minim": 8}): són per
quan el frontend tradueixi els missatges (i18n) a partir del codi.
"""


class ErrorDeDomini(Exception):
    """Base comuna. No es llança directament: cal triar-ne la categoria."""

    def __init__(self, missatge: str, *, codi: str, params: dict | None = None):
        if type(self) is ErrorDeDomini:
            raise TypeError("Cal llançar una categoria: NoTrobat, NoPermes, NoValid o Conflicte")
        super().__init__(missatge)
        self.missatge = missatge
        self.codi = codi
        self.params = params or {}


class NoTrobat(ErrorDeDomini):
    """El que es demana no existeix."""


class NoPermes(ErrorDeDomini):
    """Existeix, però qui ho demana no hi té dret."""


class NoValid(ErrorDeDomini):
    """Les dades no compleixen una regla."""


class Conflicte(ErrorDeDomini):
    """Xoca amb el que ja hi ha (un nom repetit...)."""
