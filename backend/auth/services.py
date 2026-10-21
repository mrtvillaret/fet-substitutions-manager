"""Regles d'identitat: entrar, canviar la contrasenya, tancar les altres
sessions, canviar d'institució, els usuaris inicials, la contrasenya mínima i
els usuaris protegits."""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from auth.domain import Rol, UsuariActual
from auth.repositories import UserRepository
from auth.security import hash_fictici, hash_password, verify_password
from config.auth import (
    ADMIN_INSTITUCIO,
    ADMIN_PASSWORD,
    ADMIN_PASSWORD_RECUPERACIO,
    ADMIN_USERNAME,
    DEFAULT_USERS,
    LOGIN_DELEGACIO_URL,
    LOGIN_DELEGACIO_USUARIS,
    USUARIS_PROTEGITS,
)
from config.settings import config
from database import get_auth_db_session, get_data_db_session
from errors_domini import NoPermes, NoTrobat, NoValid
from models import User
from repositories import ConfiguracioRepository

LONGITUD_MINIMA_CONTRASENYA = 8

# El de uvicorn: en arrencar, l'avís de la recuperació ha de sortir al registre
log = logging.getLogger("uvicorn.error")


def comprova_no_protegit(username: str, current_user: UsuariActual) -> None:
    """Els usuaris de USUARIS_PROTEGITS (els d'una demo pública) només els
    modifica el superadmin."""
    if username in USUARIS_PROTEGITS and not current_user.es_super_admin:
        raise NoPermes("Aquest usuari no es pot modificar", codi="usuari_protegit")


def valida_contrasenya(contrasenya: str) -> None:
    if len(contrasenya or "") < LONGITUD_MINIMA_CONTRASENYA:
        raise NoValid(
            f"La contrasenya ha de tenir almenys {LONGITUD_MINIMA_CONTRASENYA} caràcters",
            codi="contrasenya_curta",
            params={"minim": LONGITUD_MINIMA_CONTRASENYA},
        )


def delegacio_de_login(username: str) -> Optional[str]:
    """L'adreça on s'ha d'entrar si l'usuari és d'una altra instal·lació del
    mateix domini; aquí no se'n valida res i el frontend hi reenvia les
    credencials."""
    return LOGIN_DELEGACIO_URL if username in LOGIN_DELEGACIO_USUARIS else None


def autentica(db: Session, username: str, contrasenya: str) -> Optional[User]:
    """L'usuari, si existeix, és actiu i la contrasenya és bona. Si no, None:
    qui crida no ha de saber quina de les tres ha fallat."""
    user = UserRepository.get_by_username(db, username)
    # Sempre es comprova una contrasenya, també sense usuari: si no, el login
    # d'un usuari inexistent respondria abans i el temps delataria qui existeix.
    correcta = verify_password(contrasenya, user.password_hash if user else hash_fictici())
    if not user or not user.active or not correcta:
        return None
    return user


def perfil(current_user: UsuariActual) -> dict:
    # De la BD de la institució de l'usuari: config.institucio_data és de la
    # institució amb què va arrencar el servidor, no necessàriament la seva.
    with get_data_db_session(current_user.institucio) as data_db:
        idioma = ConfiguracioRepository.get(data_db, "idioma") or "ca"
        display_name = ConfiguracioRepository.nom_visible_institucio(data_db, current_user.institucio)
    return {
        "username": current_user.username,
        "role": current_user.role,
        "institucio": current_user.institucio,
        "institucio_display_name": display_name,
        "idioma": idioma,
    }


def _usuari_propi(db: Session, current_user: UsuariActual) -> User:
    user = UserRepository.get_by_username(db, current_user.username)
    if not user:
        raise NoTrobat("Usuari no trobat", codi="usuari_no_trobat")
    comprova_no_protegit(user.username, current_user)
    return user


def _nova_versio_de_sessio(user: User) -> int:
    # Els testimonis amb una versió anterior deixen de valer (dependencies.py)
    return (user.versio_sessio or 0) + 1


def canvia_contrasenya(db: Session, current_user: UsuariActual, actual: str, nova: str) -> User:
    """Una contrasenya nova tanca les altres sessions; qui crida ha de renovar
    el testimoni de la sessió actual amb l'usuari que es retorna."""
    user = _usuari_propi(db, current_user)
    if not verify_password(actual, user.password_hash):
        raise NoValid("Contrasenya actual incorrecta", codi="contrasenya_actual_incorrecta")
    valida_contrasenya(nova)
    UserRepository.update(db, user, password_hash=hash_password(nova), versio_sessio=_nova_versio_de_sessio(user))
    db.commit()
    return user


def tanca_altres_sessions(db: Session, current_user: UsuariActual) -> User:
    """Com canvia_contrasenya, però sense canviar-la."""
    user = _usuari_propi(db, current_user)
    UserRepository.update(db, user, versio_sessio=_nova_versio_de_sessio(user))
    db.commit()
    return user


def comprova_institucio_accessible(institucio: str) -> None:
    """El superadmin pot treballar amb qualsevol institució activa."""
    if institucio not in config.get_institucions_disponibles(include_inactive=True):
        raise NoValid("Institució inexistent", codi="institucio_inexistent")
    if not config.is_institucio_activa(institucio):
        raise NoPermes("Institució inactiva", codi="institucio_inactiva")


def crea_usuaris_inicials() -> None:
    """En arrencar: els usuaris inicials d'una instal·lació nova i, si es
    demana, la recuperació del superadmin.

    - Taula d'usuaris buida: es creen el superadmin (ADMIN_PASSWORD, obligatòria:
      sense, l'aplicació s'atura) i els usuaris de mostra que tinguin la
      contrasenya definida.
    - Amb usuaris: no es toca cap usuari. Si des de la web se n'ha desactivat o
      modificat un d'inicial, així es queda.
    - ADMIN_PASSWORD_RECUPERACIO, si està definida: el superadmin es crea o es
      reactiva amb aquesta contrasenya (_recupera_superadmin). Sense, mai no se
      li sobreescriu la contrasenya.
    """
    with get_auth_db_session() as db:
        if UserRepository.count(db) == 0:
            _crea_usuaris_d_instal_lacio_nova(db)
        if ADMIN_PASSWORD_RECUPERACIO:
            _recupera_superadmin(db, ADMIN_PASSWORD_RECUPERACIO)
        db.commit()


def _crea_usuaris_d_instal_lacio_nova(db: Session) -> None:
    if not ADMIN_PASSWORD:
        raise SystemExit(
            f"\nERROR: cal definir ADMIN_PASSWORD per crear l'usuari '{ADMIN_USERNAME}'.\n"
            f"Afegeix-la al fitxer .env i torna a arrencar.\n"
        )
    inicials = [
        {
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD,
            "institucio": ADMIN_INSTITUCIO,
            "role": Rol.SUPER_ADMIN,
        }
    ]
    # Els usuaris de mostra són opcionals: sense contrasenya definida, no es creen
    inicials += [u for u in DEFAULT_USERS if u["password"]]
    for usuari in inicials:
        UserRepository.create(
            db=db,
            username=usuari["username"],
            password_hash=hash_password(usuari["password"]),
            institucio=usuari["institucio"],
            role=usuari["role"],
            active=True,
        )


def _recupera_superadmin(db: Session, contrasenya: str) -> None:
    valida_contrasenya_o_atura("ADMIN_PASSWORD_RECUPERACIO", contrasenya)
    user = UserRepository.get_by_username(db, ADMIN_USERNAME)
    if user is None:
        UserRepository.create(
            db=db,
            username=ADMIN_USERNAME,
            password_hash=hash_password(contrasenya),
            institucio=ADMIN_INSTITUCIO,
            role=Rol.SUPER_ADMIN,
            active=True,
        )
    else:
        # Les sessions que tenia (potser d'algú que no n'hauria de tenir) es tanquen
        UserRepository.update(
            db,
            user,
            role=Rol.SUPER_ADMIN,
            active=True,
            password_hash=hash_password(contrasenya),
            versio_sessio=_nova_versio_de_sessio(user),
        )
    log.warning(
        "ADMIN_PASSWORD_RECUPERACIO: s'ha recuperat el superadmin '%s' amb aquesta contrasenya. "
        "CAL TREURE LA VARIABLE ADMIN_PASSWORD_RECUPERACIO DE L'ENTORN (.env) i reiniciar: "
        "si no, cada reinici hi tornarà a posar la mateixa contrasenya.",
        ADMIN_USERNAME,
    )


def valida_contrasenya_o_atura(nom: str, contrasenya: str) -> None:
    """valida_contrasenya per a una contrasenya de l'entorn: en arrencar no hi ha
    ningú a qui respondre un 400, així que s'atura l'aplicació."""
    try:
        valida_contrasenya(contrasenya)
    except NoValid as exc:
        raise SystemExit(f"\nERROR: {nom}: {exc.missatge}.\n") from exc
