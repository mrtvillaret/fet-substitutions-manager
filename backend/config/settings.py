"""Els centres del servidor: cada un és una carpeta amb gestor.db dins de
DATA_DIR (per defecte, data/ al costat del codi). Un centre desactivat té la
marca .inactive a la seva carpeta."""

import os
from pathlib import Path


def _carpeta_dels_centres() -> Path:
    data_env = os.getenv("DATA_DIR")
    if data_env:
        data_path = Path(data_env).resolve()
        # Si DATA_DIR apunta a un centre concret, el directori pare
        if (data_path / "gestor.db").exists():
            return data_path.parent
        return data_path
    return Path(__file__).resolve().parents[1] / "data"


def institucio_existeix(institucio: str) -> bool:
    """Com get_institucions_disponibles: una carpeta amb gestor.db."""
    return (_carpeta_dels_centres() / institucio / "gestor.db").is_file()


def is_institucio_activa(institucio: str) -> bool:
    return not (_carpeta_dels_centres() / institucio / ".inactive").exists()


def set_institucio_activa(institucio: str, active: bool) -> None:
    marca = _carpeta_dels_centres() / institucio / ".inactive"
    if active:
        marca.unlink(missing_ok=True)
    else:
        marca.parent.mkdir(parents=True, exist_ok=True)
        marca.touch(exist_ok=True)


def get_institucions_disponibles(include_inactive: bool = False) -> list[str]:
    """Els centres de DATA_DIR (ordenats); sense `include_inactive`, només els actius."""
    carpeta = _carpeta_dels_centres()
    if not carpeta.exists():
        return []
    return sorted(
        item.name
        for item in carpeta.iterdir()
        if item.is_dir()
        and not item.name.startswith("__")
        and (item / "gestor.db").exists()
        and (include_inactive or is_institucio_activa(item.name))
    )
