"""
Configuració bàsica del sistema
"""

import json
import locale
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)


class Config:
    """Configuració global i localització dels centres del backend web"""

    def __init__(self, *, legacy_config_file=None, desa_si_falta=True):
        # ===== CONFIG GLOBAL =====
        base_dir = Path(__file__).resolve().parents[1]
        data_root = Path(os.getenv("DATA_DIR", base_dir.parent / "data"))
        self.global_config_file = Path(os.getenv("APP_CONFIG_PATH", data_root / "config.json"))
        # Compatibilitat de lectura mentre es trasllada la configuració antiga.
        self.legacy_global_config_file = (
            Path(legacy_config_file) if legacy_config_file is not None else base_dir / "config" / "config.json"
        )

        self.global_defaults = {
            "institucio": None,  # None = auto-detectar o mostrar diàleg
            "idioma": self._detect_system_language(),
        }
        self.global_data = {}
        self.load_global(desa_si_falta=desa_si_falta)

        # ===== ENV VARIABLES OVERRIDE (per al backend web) =====
        # Si hi ha variables d'entorn definides, prioritzar-les sobre el JSON
        if os.getenv("APP_INSTITUCIO"):
            self.global_data["institucio"] = os.getenv("APP_INSTITUCIO")
            log.debug(f"🌐 Institucio override des d'ENV: {os.getenv('APP_INSTITUCIO')}")

    def load_global(self, *, desa_si_falta=True):
        """Carrega configuració global"""
        source = self.global_config_file if self.global_config_file.exists() else self.legacy_global_config_file
        if source.exists():
            with open(source, encoding="utf-8") as f:
                data = json.load(f)
            self.global_data = {**self.global_defaults, **data}
        else:
            self.global_data = self.global_defaults.copy()
            if desa_si_falta:
                self.save_global()

    def inicialitza_fitxer(self):
        """En arrencar: el fitxer inicial, amb els valors previs als overrides."""
        if not self.global_config_file.exists() and not self.legacy_global_config_file.exists():
            self._desa_global(self.global_defaults)

    def save_global(self):
        """Desa configuració global"""
        self._desa_global(self.global_data)

    def _desa_global(self, dades):
        self.global_config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.global_config_file, "w", encoding="utf-8") as f:
            json.dump(dades, f, indent=2, ensure_ascii=False)

    def __getattr__(self, key):
        """Les claus de la configuració global, com a atributs"""
        return self.global_data.get(key)

    def __setattr__(self, key, value):
        """Les claus de la configuració global van a global_data"""
        if (
            key in {"global_config_file", "legacy_global_config_file", "global_defaults", "global_data"}
            or key not in self.global_defaults
        ):
            object.__setattr__(self, key, value)
        else:
            self.global_data[key] = value

    def _detect_system_language(self):
        """Detecta l'idioma del sistema i retorna ca/es/en"""
        try:
            system_locale = locale.getdefaultlocale()[0]
            if system_locale:
                lang_code = system_locale[:2].lower()
                # Només acceptem ca, es, en
                if lang_code in ["ca", "es", "en"]:
                    return lang_code
        except (ValueError, TypeError):
            pass
        # Fallback a català
        return "ca"

    @staticmethod
    def _institucions_base_path() -> Path:
        data_env = os.getenv("DATA_DIR")
        if data_env:
            data_path = Path(data_env).resolve()
            # Si DATA_DIR apunta a una institució concreta, usem el directori pare
            if (data_path / "gestor.db").exists():
                return data_path.parent
            return data_path
        return Path(__file__).resolve().parents[1] / "data"

    @staticmethod
    def institucio_existeix(institucio: str) -> bool:
        """Com get_institucions_disponibles: una carpeta amb gestor.db."""
        return (Config._institucions_base_path() / institucio / "gestor.db").is_file()

    @staticmethod
    def is_institucio_activa(institucio: str) -> bool:
        data_path = Config._institucions_base_path()
        marker = data_path / institucio / ".inactive"
        return not marker.exists()

    @staticmethod
    def set_institucio_activa(institucio: str, active: bool):
        data_path = Config._institucions_base_path()
        marker = data_path / institucio / ".inactive"
        if active:
            if marker.exists():
                marker.unlink()
        else:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.touch(exist_ok=True)

    @staticmethod
    def get_institucions_disponibles(include_inactive: bool = False) -> list:
        """
        Detecta totes les institucions (subcarpetes) disponibles a data/

        Returns:
            Llista de noms d'institucions (ex: ["demo", "centre1"])
        """
        data_path = Config._institucions_base_path()
        if not data_path.exists():
            return []

        institucions = []
        for item in data_path.iterdir():
            # Només carpetes (excloure fitxers Python i __pycache__)
            # Una institució vàlida ha de tenir gestor.db
            if item.is_dir() and not item.name.startswith("__"):
                if (item / "gestor.db").exists():
                    if include_inactive or Config.is_institucio_activa(item.name):
                        institucions.append(item.name)

        return sorted(institucions)


# Instància global
config = Config(desa_si_falta=False)
