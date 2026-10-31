"""Regles de la configuració del centre: la configuració general (idioma,
nom visible, dates d'Estadístiques, últim professor), els idiomes i el logo."""

import io
import logging
import os
from typing import Optional

from PIL import Image, UnidentifiedImageError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from auth.domain import Rol, UsuariActual
from config.settings import config
from configuracio.schemas import SettingsUpdate
from database import get_data_db_session, get_data_dir_for_institucio
from errors_domini import NoPermes, NoTrobat, NoValid
from helpers import invalidar_horari
from repositories import ConfiguracioRepository
from serveis.dia import Dia

log = logging.getLogger(__name__)

# Logo: el PDF el mostra petit; se'n desa una còpia de com a molt 1000 px de costat.
LOGO_COSTAT_MAX = 1000
LOGO_MAX_PIXELS_ORIGINAL = 25_000_000

IDIOMES = [
    {"code": "ca", "name": "Català"},
    {"code": "es", "name": "Español"},
    {"code": "en", "name": "English"},
    {"code": "it", "name": "Italiano"},
]


def _idioma(config_db: dict) -> str:
    return config_db.get("idioma") or config.global_data.get("idioma", "ca")


def configuracio_del_centre(db: Session, institucio: str) -> dict:
    """Tota la configuració del centre, tal com la mostra la pantalla."""
    config_db = ConfiguracioRepository.get_all_as_dict(db)
    xml_path = Dia.avui(institucio).xml_path  # la versió vigent avui
    return {
        # Institució de la petició (la de l'usuari)
        "institucio": institucio,
        "idioma": _idioma(config_db),
        # Configuració per institució (SQLite)
        "xml_horari_path": config_db.get("xml_horari_path"),
        "data_inici_estadistiques": config_db.get("data_inici_estadistiques"),
        "data_final_estadistiques": config_db.get("data_final_estadistiques"),
        "logo_path": config_db.get("logo_path"),
        "te_logo": cami_logo(institucio, config_db.get("logo_path")) is not None,
        "institucio_display_name": config_db.get("institucio_display_name") or institucio,
        # Buit ('') = sense límit ("Tots"). None (mai desat) → també buit.
        "ultim_professor_subs": config_db.get("ultim_professor_subs") or "",
        "xml_missing": not xml_path or not os.path.exists(xml_path),
    }


# Els camps que es desen tal com arriben: (camp, descripció, text del canvi)
_CAMPS = (
    ("idioma", "Idioma per defecte de la institució", "Idioma"),
    ("institucio_display_name", "Nom visible de la institució", "Nom visible"),
    ("data_inici_estadistiques", "Data d'inici per estadístiques", "Data estadístiques"),
    ("data_final_estadistiques", "Data de fi per estadístiques", "Data fi estadístiques"),
    (
        "ultim_professor_subs",
        "Últim professor a considerar per substitucions (limita la llista de professors disponibles)",
        "Últim professor",
    ),
)


def desa_configuracio(db: Session, canvis: SettingsUpdate, current_user: UsuariActual) -> list[str]:
    """Desa els camps que porta la petició, tots o cap (un sol commit);
    retorna què ha canviat."""
    # El centre per defecte del servidor no es canvia d'aquí. La pantalla envia
    # el camp `institucio` (el centre de qui desa), i el superadmin que desava
    # des d'un altre centre el canviava sense voler-ho: s'ignora.
    # Les rutes de l'XML i dels PDF tampoc: l'XML es puja (/api/files/upload-xml)
    # i les carpetes són sempre les del centre. Una ruta escrita a mà podia
    # apuntar als fitxers d'un altre centre.

    if canvis.idioma is not None and canvis.idioma not in {i["code"] for i in IDIOMES}:
        raise NoValid("Idioma no vàlid", codi="idioma_no_valid")
    if canvis.institucio_display_name is not None and current_user.role != Rol.SUPER_ADMIN:
        raise NoPermes("Només el superadmin pot editar el nom visible", codi="nom_visible_superadmin")

    changed = []
    for camp, descripcio, text in _CAMPS:
        valor = getattr(canvis, camp)
        if valor is not None:
            ConfiguracioRepository.desa(db, camp, valor, tipus="string", descripcio=descripcio)
            changed.append(f"{text} → {valor}")
    db.commit()

    # Recarregar configuració d'institució si s'ha modificat
    if any(
        s is not None
        for s in [
            canvis.idioma,
            canvis.data_inici_estadistiques,
            canvis.data_final_estadistiques,
            canvis.ultim_professor_subs,
        ]
    ):
        config.load_institucio()

    # El límit de professors canvia l'horari
    if canvis.ultim_professor_subs is not None:
        invalidar_horari(current_user.institucio)  # només la del centre que desa
        log.debug("✅ Cache del horari invalidada - configuració canviada")

    return changed


def idiomes(db: Session) -> dict:
    """Els idiomes de la web i el del centre."""
    return {"idiomes": IDIOMES, "actual": _idioma({"idioma": ConfiguracioRepository.get(db, "idioma")})}


def desa_logo(institucio: str, nom_fitxer: str, contingut: bytes) -> str:
    """Desa el logo del centre com a logo.png; retorna on l'ha desat."""
    ext = os.path.splitext(nom_fitxer or "")[1].lower()
    if ext not in {".png", ".jpg", ".jpeg"}:
        raise NoValid("El logo ha de ser PNG o JPG", codi="logo_extensio")

    # No n'hi ha prou amb l'extensió: s'obre la imatge i se'n desa una còpia
    # nova en PNG. Així el que queda al servidor (i va als PDF) és sempre una
    # imatge vàlida, sense metadades ni res afegit al fitxer original.
    try:
        imatge = Image.open(io.BytesIO(contingut))
        if imatge.format not in ("PNG", "JPEG"):
            raise ValueError(imatge.format)
        # Abans de descomprimir-la: una imatge petita en bytes pot ocupar
        # gigues en memòria si declara unes dimensions enormes.
        if imatge.width * imatge.height > LOGO_MAX_PIXELS_ORIGINAL:
            raise NoValid("La imatge del logo és massa gran", codi="logo_massa_gran")
        imatge.load()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError):
        raise NoValid("El logo ha de ser una imatge PNG o JPG vàlida", codi="logo_no_valid") from None

    imatge.thumbnail((LOGO_COSTAT_MAX, LOGO_COSTAT_MAX))
    if imatge.mode not in ("RGB", "RGBA", "L", "LA"):
        imatge = imatge.convert("RGBA")

    data_dir = str(get_data_dir_for_institucio(institucio))
    os.makedirs(data_dir, exist_ok=True)

    file_path = os.path.join(data_dir, "logo.png")
    imatge.save(file_path, format="PNG")
    # Un logo anterior en JPG ja no es fa servir
    for antic in ("logo.jpg", "logo.jpeg"):
        if os.path.exists(os.path.join(data_dir, antic)):
            os.remove(os.path.join(data_dir, antic))

    with get_data_db_session(institucio) as db:
        ConfiguracioRepository.set(
            db, "logo_path", file_path, tipus="string", descripcio="Path del logo de la institució"
        )
    return file_path


def cami_logo(institucio: str, logo_configurat: Optional[str]) -> Optional[str]:
    """El fitxer del logo del centre, o None si no en té: el desat a la
    configuració (logo_path) o, si no n'hi ha cap, un logo.png/.jpg de la
    carpeta de dades."""
    logo_path = logo_configurat
    if not logo_path:
        data_dir = get_data_dir_for_institucio(institucio)
        for ext in (".png", ".jpg", ".jpeg"):
            candidate = data_dir / f"logo{ext}"
            if candidate.exists():
                logo_path = str(candidate)
                break
    return logo_path if logo_path and os.path.exists(logo_path) else None


def logo_del_centre(institucio: str) -> tuple[str, str]:
    """El fitxer del logo i el seu tipus (image/png o image/jpeg)."""
    # Si la BD del centre no es pot llegir, es busca el logo a la carpeta
    # (cami_logo); qualsevol altre error és del codi i no es calla
    logo_configurat = None
    try:
        with get_data_db_session(institucio) as db:
            logo_configurat = ConfiguracioRepository.get(db, "logo_path")
    except SQLAlchemyError:
        log.warning("No s'ha pogut llegir logo_path del centre; es busca el logo a la carpeta", exc_info=True)

    logo_path = cami_logo(institucio, logo_configurat)
    if not logo_path:
        raise NoTrobat("Logo no trobat", codi="logo_no_trobat")

    media_type = "image/png"
    if os.path.splitext(logo_path)[1].lower() in [".jpg", ".jpeg"]:
        media_type = "image/jpeg"
    return logo_path, media_type
