"""Objectes del domini d'auth: els rols i l'usuari que fa la petició."""

from dataclasses import dataclass
from enum import StrEnum


class Rol(StrEnum):
    # StrEnum: es desa a la BD i viatja al testimoni com el text de sempre
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    USER = "user"


@dataclass(frozen=True)
class UsuariActual:
    """L'usuari autenticat de la petició, tal com el veuen les rutes i els
    serveis. No és l'objecte de la BD: no es pot desar per error, i per al
    superadmin `institucio` és la institució amb què treballa en aquesta
    sessió, no la seva."""

    id: int
    username: str
    role: str
    institucio: str
    versio_sessio: int

    @property
    def es_super_admin(self) -> bool:
        return self.role == Rol.SUPER_ADMIN

    @property
    def es_admin(self) -> bool:
        """Admin del centre o superadmin."""
        return self.role in (Rol.ADMIN, Rol.SUPER_ADMIN)
