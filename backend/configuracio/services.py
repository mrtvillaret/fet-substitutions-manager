"""Regles de la configuració del centre: la configuració general (idioma,
nom visible, dates d'Estadístiques, últim professor), els idiomes i el logo."""

import io
import logging
import os
from datetime import date

from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

import i18n_setup
from auth.domain import Rol, UsuariActual
from configuracio.repositories import ConfiguracioRepository
from configuracio.schemas import SettingsUpdate
from database import get_data_dir_for_institucio
from errors_domini import NoPermes, NoTrobat, NoValid
from horari.context import invalidar_horari
from horari.domain import Dia

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


def _idioma(valor: str | None) -> str:
    return valor or i18n_setup.IDIOMA_PER_DEFECTE


def _data_desada(valor: str | None) -> date | str | None:
    if valor is None:
        return None
    try:
        dia = date.fromisoformat(valor)
    except ValueError:
        return valor
    # Les versions anteriors a la validació podien desar qualsevol text.
    # Es conserva la sortida que veien els clients per a aquests valors.
    return dia if dia.isoformat() == valor else valor


def configuracio_del_centre(db: Session, institucio: str) -> dict:
    """Tota la configuració del centre, tal com la mostra la pantalla."""
    config_db = ConfiguracioRepository.get_all_as_dict(db)
    logo = cami_logo(institucio)
    xml_path = Dia.avui(institucio).xml_path  # la versió vigent avui
    return {
        # Institució de la petició (la de l'usuari)
        "institucio": institucio,
        "idioma": _idioma(config_db.get("idioma")),
        # Configuració per institució (SQLite)
        "xml_horari_path": config_db.get("xml_horari_path"),
        "data_inici_estadistiques": _data_desada(config_db.get("data_inici_estadistiques")),
        "data_final_estadistiques": _data_desada(config_db.get("data_final_estadistiques")),
        "logo_path": logo,
        "te_logo": logo is not None,
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
    valors_desats = canvis.model_dump(mode="json", exclude_none=True)
    for camp, descripcio, text in _CAMPS:
        valor = valors_desats.get(camp)
        if valor is not None:
            ConfiguracioRepository.desa(db, camp, valor, tipus="string", descripcio=descripcio)
            changed.append(f"{text} → {valor}")
    db.commit()

    # El límit de professors canvia l'horari
    if canvis.ultim_professor_subs is not None:
        invalidar_horari(current_user.institucio)  # només la del centre que desa
        log.debug("✅ Cache del horari invalidada - configuració canviada")

    return changed


def idiomes(db: Session) -> dict:
    """Els idiomes de la web i el del centre."""
    return {"idiomes": IDIOMES, "actual": _idioma(ConfiguracioRepository.get(db, "idioma"))}


def desa_logo(institucio: str, nom_fitxer: str, contingut: bytes) -> str:
    """Desa el logo del centre com a logo.png; retorna on l'ha desat."""
    ext = os.path.splitext(nom_fitxer or "")[1].lower()
    if ext not in {".png", ".jpg", ".jpeg"}:
        raise NoValid("El logo ha de ser PNG o JPG", codi="logo_extensio")

    # No n'hi ha prou amb l'extensió: s'obre la imatge i se'n desa una còpia
    # nova en PNG. Així el que queda al servidor (i va als PDF) és sempre una
    # imatge vàlida, sense metadades ni res afegit al fitxer original.
    try:
        # Només els lectors de PNG i JPEG: Pillow no prova cap altre format.
        imatge: Image.Image = Image.open(io.BytesIO(contingut), formats=["PNG", "JPEG"])
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
    return file_path


def cami_logo(institucio: str) -> str | None:
    """El fitxer del logo del centre, o None si no en té: sempre el
    logo.png/.jpg/.jpeg de la carpeta de dades (desa_logo el desa com a
    logo.png). La clau logo_path de la configuració ja no es fa servir: era una
    ruta absoluta que es trencava en còpies i restauracions."""
    data_dir = get_data_dir_for_institucio(institucio)
    for ext in (".png", ".jpg", ".jpeg"):
        candidate = data_dir / f"logo{ext}"
        if candidate.exists():
            return str(candidate)
    return None


def logo_del_centre(institucio: str) -> tuple[str, str]:
    """El fitxer del logo i el seu tipus (image/png o image/jpeg)."""
    logo_path = cami_logo(institucio)
    if not logo_path:
        raise NoTrobat("Logo no trobat", codi="logo_no_trobat")

    media_type = "image/png"
    if os.path.splitext(logo_path)[1].lower() in [".jpg", ".jpeg"]:
        media_type = "image/jpeg"
    return logo_path, media_type
