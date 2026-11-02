"""Regles dels centres (institucions): cada centre és una carpeta de dades
amb la seva BD; un centre desactivat té un fitxer `.inactive`."""

import shutil
from typing import Optional

from sqlalchemy.orm import Session

from auth.domain import Rol, UsuariActual
from auth.repositories import UserRepository
from config.settings import config
from database import get_data_db_session, get_data_dir_for_institucio
from errors_domini import Conflicte, NoTrobat, NoValid
from repositories import ConfiguracioRepository

# Només en crear-lo: un nom més llarg pot fallar al sistema de fitxers
LLARGADA_MAXIMA_NOM = 64


def _nom_visible(slug: str) -> str:
    with get_data_db_session(slug) as db:
        return ConfiguracioRepository.nom_visible_institucio(db, slug)


def _desa_nom_visible(slug: str, nom_visible: str) -> None:
    with get_data_db_session(slug) as db:
        ConfiguracioRepository.set(
            db, "institucio_display_name", nom_visible, tipus="string", descripcio="Nom visible de la institució"
        )


def _comprova_existeix(slug: str, include_inactive: bool) -> None:
    if slug not in config.get_institucions_disponibles(include_inactive=include_inactive):
        raise NoTrobat("Institució no trobada", codi="institucio_no_trobada")


def llista(current_user: UsuariActual) -> dict:
    """El superadmin els veu tots, també els inactius; l'admin, només el seu."""
    institucions = config.get_institucions_disponibles(include_inactive=current_user.es_super_admin)
    if current_user.role != Rol.SUPER_ADMIN:
        institucions = [inst for inst in institucions if inst == current_user.institucio]
    return {
        "institucions": [
            {"slug": inst, "display_name": _nom_visible(inst), "active": config.is_institucio_activa(inst)}
            for inst in institucions
        ],
        "actual": current_user.institucio,
    }


def crea(nom: str, nom_visible: Optional[str]) -> None:
    """La carpeta i la BD buida del centre. El nom és el de la carpeta:
    minúscules, xifres, «_», «.» i «-», comença per una lletra o una xifra i
    té com a molt LLARGADA_MAXIMA_NOM caràcters."""
    if len(nom) > LLARGADA_MAXIMA_NOM:
        raise NoValid(
            f"El nom del centre pot tenir com a molt {LLARGADA_MAXIMA_NOM} caràcters", codi="nom_centre_massa_llarg"
        )
    try:
        carpeta = get_data_dir_for_institucio(nom)
    except ValueError:
        raise NoValid("Nom de centre no vàlid", codi="nom_centre_no_valid") from None
    if carpeta.exists():
        raise Conflicte("La institució ja existeix", codi="institucio_existent")
    with get_data_db_session(nom):  # crea la carpeta i el gestor.db
        pass
    if nom_visible:
        _desa_nom_visible(nom, nom_visible)


def canvia_nom_visible(slug: str, nom_visible: str) -> None:
    # També d'un centre desactivat (el superadmin el veu a la llista)
    _comprova_existeix(slug, include_inactive=True)
    _desa_nom_visible(slug, nom_visible)


def canvia_estat(slug: str, actiu: bool) -> None:
    """Activa o desactiva el centre. Els usuaris no es toquen: d'un centre
    desactivat no hi pot entrar ningú (autentica) ni fer cap petició
    (get_current_user), i en reactivar-lo tot torna a ser com abans."""
    _comprova_existeix(slug, include_inactive=True)
    config.set_institucio_activa(slug, actiu)


def esborra(slug: str, mode: str, confirmacio: str) -> str:
    """Des de la web, només `soft`: el desactiva, com canvia_estat, sense
    tocar els usuaris (confirmació: el nom del centre). L'esborrat definitiu
    (`hard`) es fa des del servidor, amb còpia: scripts/esborra_centre.py.
    Retorna el mode."""
    _comprova_existeix(slug, include_inactive=True)

    mode = mode or "soft"
    if mode == "hard":
        raise NoValid("L'esborrat definitiu d'un centre es fa des del servidor", codi="esborrat_definitiu_al_servidor")
    if mode != "soft":
        raise NoValid("Mode invàlid", codi="mode_invalid")
    if confirmacio != slug:
        raise NoValid("Confirmació incorrecta", codi="confirmacio_incorrecta")

    canvia_estat(slug, False)
    return mode


def comprova_es_pot_esborrar_definitivament(auth_db: Session, slug: str) -> None:
    """El centre existeix i no és el centre propi de cap superadmin (en
    tornar a entrar, la sessió hi apuntaria): abans cal canviar-li el centre."""
    try:
        get_data_dir_for_institucio(slug)
    except ValueError:
        raise NoTrobat("Institució no trobada", codi="institucio_no_trobada") from None
    _comprova_existeix(slug, include_inactive=True)
    if any(u.role == Rol.SUPER_ADMIN for u in UserRepository.list_by_institucio(auth_db, slug)):
        raise Conflicte(
            "És el centre propi d'un superadmin: canvia-li el centre abans d'esborrar-lo",
            codi="centre_d_un_superadmin",
        )


def esborra_definitivament(auth_db: Session, slug: str) -> None:
    """Esborra la carpeta del centre i els seus usuaris. Només des del
    servidor, després de fer-ne la còpia (scripts/esborra_centre.py)."""
    comprova_es_pot_esborrar_definitivament(auth_db, slug)
    for user in UserRepository.list_by_institucio(auth_db, slug):
        UserRepository.delete(auth_db, user)
    auth_db.flush()
    # Si la carpeta no es pot esborrar, els usuaris es queden (no hi ha commit)
    shutil.rmtree(get_data_dir_for_institucio(slug))
    auth_db.commit()
