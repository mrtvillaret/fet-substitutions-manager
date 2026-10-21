"""Regles de la gestió d'usuaris: qui pot veure, crear, editar, desactivar i
esborrar quins usuaris."""

from typing import Optional

from sqlalchemy.orm import Session

from auth.domain import Rol, UsuariActual
from auth.repositories import UserRepository
from auth.security import hash_password
from auth.services import comprova_no_protegit, valida_contrasenya
from config.settings import config
from database import get_data_db_session
from errors_domini import Conflicte, NoPermes, NoTrobat, NoValid
from models import User
from repositories import ConfiguracioRepository


def _noms_visibles(institucions) -> dict[str, str]:
    noms = {}
    for institucio in institucions:
        with get_data_db_session(institucio) as data_db:
            noms[institucio] = ConfiguracioRepository.nom_visible_institucio(data_db, institucio)
    return noms


def fitxa(user: User, nom_visible: Optional[str] = None) -> dict:
    """L'usuari tal com el veu la pantalla d'usuaris."""
    if nom_visible is None:
        nom_visible = _noms_visibles([user.institucio])[user.institucio]
    return {
        "id": user.id,
        "username": user.username,
        "institucio": user.institucio,
        "institucio_display_name": nom_visible,
        "role": user.role,
        "active": user.active,
    }


def llista_usuaris(db: Session, current_user: UsuariActual) -> list[dict]:
    """El superadmin els veu tots; l'admin, els del seu centre menys el superadmin."""
    if current_user.es_super_admin:
        users = UserRepository.list_all(db)
    else:
        users = [u for u in UserRepository.list_by_institucio(db, current_user.institucio) if u.role != Rol.SUPER_ADMIN]
    noms = _noms_visibles({u.institucio for u in users})
    return [fitxa(u, noms.get(u.institucio, u.institucio)) for u in users]


def _comprova_rol(role: str) -> None:
    if role not in tuple(Rol):
        raise NoValid("Rol invàlid", codi="rol_invalid")


def _comprova_institucio_existeix(institucio: str) -> None:
    if institucio not in config.get_institucions_disponibles():
        raise NoValid("Institució inexistent", codi="institucio_inexistent")


def _usuari_a_gestionar(db: Session, user_id: int) -> User:
    user = UserRepository.get_by_id(db, user_id)
    if not user:
        raise NoTrobat("Usuari no trobat", codi="usuari_no_trobat")
    return user


def _comprova_mateixa_institucio(user: User, current_user: UsuariActual) -> None:
    """Un admin només gestiona els usuaris del seu centre."""
    if not current_user.es_super_admin and user.institucio != current_user.institucio:
        raise NoPermes("No pots editar usuaris d'una altra institució", codi="usuari_d_una_altra_institucio")


def _comprova_nom_lliure(db: Session, username: str, excepte: Optional[User] = None) -> None:
    altre = UserRepository.get_by_username(db, username)
    if altre and altre is not excepte:
        raise Conflicte("Ja existeix un usuari amb aquest nom", codi="nom_d_usuari_repetit")


def _comprova_que_no_es_treu_a_si_mateix(user: User, current_user: UsuariActual, accio: str) -> None:
    """Ningú no es pot desactivar ni esborrar a si mateix: es quedaria fora."""
    if user.id == current_user.id:
        raise NoPermes(f"No et pots {accio} a tu mateix", codi=f"{accio}_se")


def _comprova_que_el_centre_conserva_un_admin(db: Session, user: User, despres: Optional[dict]) -> None:
    """Regla única: cap operació pot deixar un centre sense cap admin actiu.

    `despres` és com quedarà l'usuari ({"active", "role", "institucio"}), o
    None si s'esborra. Si ara és un admin actiu del seu centre i deixarà de
    ser-ho (es desactiva, s'esborra, se li treu el rol o canvia de centre), cal
    que al centre hi quedi un altre admin actiu. El superadmin no compta: no és
    de cap centre."""
    if not (user.active and user.role == Rol.ADMIN):
        return
    continua_sent_admin = (
        despres is not None
        and despres["active"]
        and despres["role"] == Rol.ADMIN
        and despres["institucio"] == user.institucio
    )
    if continua_sent_admin:
        return
    altres = [
        u
        for u in UserRepository.list_by_institucio(db, user.institucio)
        if u.id != user.id and u.active and u.role == Rol.ADMIN
    ]
    if not altres:
        raise NoPermes(
            "El centre es quedaria sense cap admin actiu",
            codi="centre_sense_admin",
            params={"institucio": user.institucio},
        )


def crea_usuari(
    db: Session, current_user: UsuariActual, username: str, password: str, institucio: Optional[str], role: str
) -> User:
    role = role or Rol.USER
    _comprova_rol(role)
    institucio = institucio or current_user.institucio
    _comprova_institucio_existeix(institucio)
    if not current_user.es_super_admin:
        if institucio != current_user.institucio:
            raise NoPermes("No pots crear usuaris d'una altra institució", codi="crear_a_una_altra_institucio")
        if role == Rol.SUPER_ADMIN:
            raise NoPermes("No pots crear superadmins", codi="crear_superadmin")
    _comprova_nom_lliure(db, username)
    valida_contrasenya(password)

    user = UserRepository.create(
        db=db, username=username, password_hash=hash_password(password), institucio=institucio, role=role, active=True
    )
    db.commit()
    return user


def edita_usuari(db: Session, current_user: UsuariActual, user_id: int, canvis: dict) -> tuple[User, bool]:
    """Aplica `canvis` (username, role, active, institucio, password; els que
    siguin None no es toquen). Retorna l'usuari i si cal renovar el testimoni
    de qui fa la petició: l'admin que es canvia la seva contrasenya no surt de
    la sessió (les altres, sí: una contrasenya nova les tanca totes)."""
    user = _usuari_a_gestionar(db, user_id)
    if user.role == Rol.SUPER_ADMIN:
        raise NoPermes("No es pot editar el superadmin", codi="superadmin_intocable")
    comprova_no_protegit(user.username, current_user)
    _comprova_mateixa_institucio(user, current_user)
    if not current_user.es_super_admin:
        if canvis.get("institucio") and canvis["institucio"] != current_user.institucio:
            raise NoPermes("No pots canviar la institució", codi="canviar_institucio")
        if canvis.get("role") == Rol.SUPER_ADMIN:
            raise NoPermes("No pots assignar el rol superadmin", codi="assignar_superadmin")
    if canvis.get("role"):
        _comprova_rol(canvis["role"])

    if canvis.get("username") is not None:
        _comprova_nom_lliure(db, canvis["username"], excepte=user)

    updates = {camp: canvis[camp] for camp in ("username", "role", "active") if canvis.get(camp) is not None}
    if canvis.get("institucio") is not None:
        _comprova_institucio_existeix(canvis["institucio"])
        updates["institucio"] = canvis["institucio"]
    if canvis.get("active") is False:
        _comprova_que_no_es_treu_a_si_mateix(user, current_user, "desactivar")
    _comprova_que_el_centre_conserva_un_admin(
        db,
        user,
        {
            camp: canvis[camp] if canvis.get(camp) is not None else getattr(user, camp)
            for camp in ("active", "role", "institucio")
        },
    )
    password = canvis.get("password")
    if password:
        valida_contrasenya(password)
        updates["password_hash"] = hash_password(password)
        # Una contrasenya nova tanca totes les sessions obertes de l'usuari
        updates["versio_sessio"] = (user.versio_sessio or 0) + 1

    UserRepository.update(db, user, **updates)
    db.commit()
    # Per l'id: si alhora s'ha canviat el nom, el de la sessió encara és l'antic
    return user, bool(password) and user.id == current_user.id


def desactiva_usuari(db: Session, current_user: UsuariActual, user_id: int) -> None:
    user = _usuari_a_gestionar(db, user_id)
    if user.role == Rol.SUPER_ADMIN:
        raise NoPermes("No es pot desactivar el superadmin", codi="superadmin_intocable")
    comprova_no_protegit(user.username, current_user)
    _comprova_mateixa_institucio(user, current_user)
    _comprova_que_no_es_treu_a_si_mateix(user, current_user, "desactivar")
    _comprova_que_el_centre_conserva_un_admin(
        db, user, {"active": False, "role": user.role, "institucio": user.institucio}
    )
    UserRepository.update(db, user, active=False)
    db.commit()


def elimina_usuari(db: Session, current_user: UsuariActual, user_id: int) -> None:
    """Només el superadmin (la ruta ho exigeix)."""
    user = _usuari_a_gestionar(db, user_id)
    if user.role == Rol.SUPER_ADMIN:
        raise NoPermes("No es pot eliminar el superadmin", codi="superadmin_intocable")
    _comprova_que_no_es_treu_a_si_mateix(user, current_user, "esborrar")
    _comprova_que_el_centre_conserva_un_admin(db, user, None)
    UserRepository.delete(db, user)
    db.commit()
