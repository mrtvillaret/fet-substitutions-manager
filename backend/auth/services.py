"""Regles d'identitat: entrar, canviar la contrasenya, tancar les altres
sessions, canviar d'institució, els usuaris inicials, la contrasenya mínima i
els usuaris protegits."""

import logging

from sqlalchemy.orm import Session

from auth.domain import Rol, UsuariActual
from auth.repositories import UserRepository
from auth.security import hash_fictici, hash_password, verify_password
from config.auth import get_config_auth
from config.settings import config
from configuracio.repositories import ConfiguracioRepository
from database import get_engine_for_institucio, inicia_escriptura
from errors_domini import NoPermes, NoTrobat, NoValid
from models import User

LONGITUD_MINIMA_CONTRASENYA = 8

# El de uvicorn: en arrencar, l'avís de la recuperació ha de sortir al registre
log = logging.getLogger("uvicorn.error")


def comprova_no_protegit(username: str, current_user: UsuariActual) -> None:
    """Els usuaris de USUARIS_PROTEGITS (els d'una demo pública) només els
    modifica el superadmin."""
    if username in get_config_auth().usuaris_protegits and not current_user.es_super_admin:
        raise NoPermes("Aquest usuari no es pot modificar", codi="usuari_protegit")


def valida_contrasenya(contrasenya: str) -> None:
    if len(contrasenya or "") < LONGITUD_MINIMA_CONTRASENYA:
        raise NoValid(
            f"La contrasenya ha de tenir almenys {LONGITUD_MINIMA_CONTRASENYA} caràcters",
            codi="contrasenya_curta",
            params={"minim": LONGITUD_MINIMA_CONTRASENYA},
        )


def delegacio_de_login(username: str) -> str | None:
    """L'adreça on s'ha d'entrar si l'usuari és d'una altra instal·lació del
    mateix domini; aquí no se'n valida res i el frontend hi reenvia les
    credencials."""
    return get_config_auth().login_delegacio_url if username in get_config_auth().login_delegacio_usuaris else None


def autentica(db: Session, username: str, contrasenya: str) -> User | None:
    """L'usuari, si existeix, és actiu i la contrasenya és bona. Si no, None:
    qui crida no ha de saber quina de les tres ha fallat."""
    user = UserRepository.get_by_username(db, username)
    # Sempre es comprova una contrasenya, també sense usuari: si no, el login
    # d'un usuari inexistent respondria abans i el temps delataria qui existeix.
    correcta = verify_password(contrasenya, user.password_hash if user else hash_fictici())
    if not user or not user.active or not correcta:
        return None
    # D'un centre desactivat no hi entra ningú (els usuaris continuen actius:
    # en reactivar-lo, tot torna a ser com abans). El superadmin sí, com sempre.
    if user.role != Rol.SUPER_ADMIN and not config.is_institucio_activa(user.institucio):
        return None
    return user


def perfil(data_db: Session, current_user: UsuariActual) -> dict:
    """`data_db`: la BD de la institució de l'usuari (la de la sessió), no la
    del centre per defecte del servidor."""
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
    inicia_escriptura(db)
    user = _usuari_propi(db, current_user)
    if not verify_password(actual, user.password_hash):
        raise NoValid("Contrasenya actual incorrecta", codi="contrasenya_actual_incorrecta")
    valida_contrasenya(nova)
    UserRepository.update(db, user, password_hash=hash_password(nova), versio_sessio=_nova_versio_de_sessio(user))
    db.commit()
    return user


def tanca_altres_sessions(db: Session, current_user: UsuariActual) -> User:
    """Com canvia_contrasenya, però sense canviar-la."""
    inicia_escriptura(db)
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


def crea_usuaris_inicials(db: Session) -> None:
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
    - Avisa al registre si hi ha usuaris actius de centres que no existeixen
      (una sessió d'un centre que no existeix rep un 409 a tot).

    `db`: una sessió de l'auth.db; el servei en fa el commit.
    """
    if UserRepository.count(db) == 0:
        _crea_usuaris_d_instal_lacio_nova(db)
    if get_config_auth().admin_password_recuperacio:
        _recupera_superadmin(db, get_config_auth().admin_password_recuperacio)
    db.commit()
    _avisa_usuaris_sense_centre(db)


def _avisa_usuaris_sense_centre(db: Session) -> None:
    # Només nombres: el registre no ha de tenir noms d'usuaris ni de centres
    sense_centre = [u for u in UserRepository.list_all(db) if u.active and not config.institucio_existeix(u.institucio)]
    if sense_centre:
        log.warning(
            "Usuaris actius de centres que no existeixen: %d usuaris, %d centres",
            len(sense_centre),
            len({u.institucio for u in sense_centre}),
        )


def _crea_usuaris_d_instal_lacio_nova(db: Session) -> None:
    if not get_config_auth().admin_password:
        raise SystemExit(
            f"\nERROR: cal definir ADMIN_PASSWORD per crear l'usuari '{get_config_auth().admin_username}'.\n"
            f"Afegeix-la al fitxer .env i torna a arrencar.\n"
        )
    inicials = [
        {
            "username": get_config_auth().admin_username,
            "password": get_config_auth().admin_password,
            "institucio": get_config_auth().admin_institucio,
            "role": Rol.SUPER_ADMIN,
        }
    ]
    # Els usuaris de mostra són opcionals: sense contrasenya definida, no es creen
    inicials += [u for u in get_config_auth().default_users if u["password"]]
    for usuari in inicials:
        # El centre, també: cap centre no es crea sol en la primera petició
        if not config.institucio_existeix(usuari["institucio"]):
            get_engine_for_institucio(usuari["institucio"])  # crea la carpeta i el gestor.db
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
    user = UserRepository.get_by_username(db, get_config_auth().admin_username)
    if user is None:
        UserRepository.create(
            db=db,
            username=get_config_auth().admin_username,
            password_hash=hash_password(contrasenya),
            institucio=get_config_auth().admin_institucio,
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
        get_config_auth().admin_username,
    )


def valida_contrasenya_o_atura(nom: str, contrasenya: str) -> None:
    """valida_contrasenya per a una contrasenya de l'entorn: en arrencar no hi ha
    ningú a qui respondre un 400, així que s'atura l'aplicació."""
    try:
        valida_contrasenya(contrasenya)
    except NoValid as exc:
        raise SystemExit(f"\nERROR: {nom}: {exc.missatge}.\n") from exc
