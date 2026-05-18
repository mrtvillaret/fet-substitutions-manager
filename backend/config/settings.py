"""
Configuració bàsica del sistema
"""
import json
import locale
from pathlib import Path
import os

try:
    from i18n_setup import translate as _
except ImportError:
    def _(text):
        return text


class Config:
    """Configuració en dos nivells: global i per institució"""

    def __init__(self):
        # ===== CONFIG GLOBAL =====
        base_dir = Path(__file__).resolve().parents[1]
        self.global_config_file = base_dir / "config" / "config.json"
        self.global_config_file.parent.mkdir(exist_ok=True)

        self.global_defaults = {
            "institucio": None,  # None = auto-detectar o mostrar diàleg
            "idioma": self._detect_system_language()
        }
        self.global_data = {}
        self.load_global()

        # ===== ENV VARIABLES OVERRIDE (per al backend web) =====
        # Si hi ha variables d'entorn definides, prioritzar-les sobre el JSON
        if os.getenv("APP_INSTITUCIO"):
            self.global_data["institucio"] = os.getenv("APP_INSTITUCIO")
            print(f"🌐 Institucio override des d'ENV: {os.getenv('APP_INSTITUCIO')}")

        # ===== CONFIG PER INSTITUCIÓ (SQLite) =====
        self.institucio_defaults = {
            "xml_horari_path": "horari.xml",
            "ultim_professor_subs": "",
            "export_dir": "exports",
            "data_inici_estadistiques": "2024-07-01",
            "logo_path": "",
            "idioma": self._detect_system_language()
        }
        self.institucio_data = {}
        self.load_institucio()

        # Aplicar override de xml_horari_path si existeix a ENV
        if os.getenv("APP_XML_PATH"):
            self.institucio_data["xml_horari_path"] = os.getenv("APP_XML_PATH")
            print(f"🌐 XML path override des d'ENV: {os.getenv('APP_XML_PATH')}")
            self.save_institucio()

    def load_global(self):
        """Carrega configuració global"""
        if self.global_config_file.exists():
            with open(self.global_config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.global_data = {**self.global_defaults, **data}
        else:
            self.global_data = self.global_defaults.copy()
            self.save_global()

    def _default_language_for_institucio(self, institucio: str) -> str:
        return self._detect_system_language()

    def _get_institucio_defaults(self, institucio: str) -> dict:
        defaults = self.institucio_defaults.copy()
        defaults["idioma"] = self._default_language_for_institucio(institucio)
        return defaults

    def load_institucio(self):
        """Carrega configuració de la institució actual des de SQLite"""
        instit = self.global_data.get("institucio") or os.getenv("APP_INSTITUCIO") or self.detectar_institucio()
        if not instit:
            return

        self.institucio_defaults = self._get_institucio_defaults(instit)

        try:
            from database import get_data_db_session
            from repositories import ConfiguracioRepository

            with get_data_db_session(instit) as db:
                existing = ConfiguracioRepository.get_all_as_dict(db)

                # Assegurar defaults si falten
                for key, value in self.institucio_defaults.items():
                    if key not in existing:
                        ConfiguracioRepository.set(db, key, str(value), 'string')
                        existing[key] = str(value)

                self.institucio_data = {**self.institucio_defaults, **existing}
        except Exception:
            # Fallback sense DB
            self.institucio_data = self.institucio_defaults.copy()

    def save_global(self):
        """Desa configuració global"""
        with open(self.global_config_file, 'w', encoding='utf-8') as f:
            json.dump(self.global_data, f, indent=2, ensure_ascii=False)

    def save_institucio(self):
        """Desa configuració de la institució (SQLite)"""
        instit = self.global_data.get("institucio") or os.getenv("APP_INSTITUCIO") or self.detectar_institucio()
        if not instit:
            return

        try:
            from database import get_data_db_session
            from repositories import ConfiguracioRepository

            with get_data_db_session(instit) as db:
                for key, value in self.institucio_data.items():
                    ConfiguracioRepository.set(db, key, str(value), 'string')
        except Exception:
            return

    def save(self):
        """Desa tant configuració global com d'institució"""
        self.save_global()
        self.save_institucio()

    def __getattr__(self, key):
        """Busca primer a institucio_data, després a global_data"""
        if key in self.institucio_data:
            return self.institucio_data[key]
        return self.global_data.get(key)

    def __setattr__(self, key, value):
        """Intercepta canvis per desar-los al diccionari correcte"""
        # Atributs interns de la classe
        internal_attrs = {
            'global_config_file', 'global_defaults', 'global_data',
            'institucio_defaults', 'institucio_data'
        }

        if key in internal_attrs:
            # Desar com atribut normal de l'objecte
            object.__setattr__(self, key, value)
        else:
            # Desar al diccionari correcte
            if key in self.institucio_defaults:
                self.institucio_data[key] = value
            elif key in self.global_defaults:
                self.global_data[key] = value
            else:
                # Clau desconeguda: afegir a institucio_data (més específic)
                if hasattr(self, 'institucio_data'):
                    self.institucio_data[key] = value
                else:
                    object.__setattr__(self, key, value)

    @property
    def data(self):
        """Compatibilitat: retorna diccionari combinat"""
        return {**self.global_data, **self.institucio_data}

    def _detect_system_language(self):
        """Detecta l'idioma del sistema i retorna ca/es/en"""
        try:
            system_locale = locale.getdefaultlocale()[0]
            if system_locale:
                lang_code = system_locale[:2].lower()
                # Només acceptem ca, es, en
                if lang_code in ['ca', 'es', 'en']:
                    return lang_code
        except:
            pass
        # Fallback a català
        return 'ca'

    def detectar_institucio(self, xml_path: str = None) -> str:
        """
        Detecta la institució del nom del fitxer XML.

        Estratègies:
        1. Si xml_path conté "_": teachers_demo.xml → "demo"
        2. Si no, usar el nom del directori on està l'XML
        3. Fallback: "default"

        Args:
            xml_path: Path del fitxer XML. Si None, usa self.xml_horari_path

        Returns:
            Nom de la institució (ex: "demo", "demo")
        """
        if xml_path is None:
            xml_path = self.xml_horari_path

        # Si encara és None (primera execució sense XML), retornar None
        # El data_dir ho gestionarà seleccionant la primera institució disponible
        if xml_path is None:
            return None

        # Obtenir nom del fitxer sense extensió
        basename = os.path.basename(xml_path)
        nom_sense_ext = os.path.splitext(basename)[0]

        # Estratègia 1: Nom amb guió baix (teachers_demo → demo)
        if "_" in nom_sense_ext:
            parts = nom_sense_ext.split("_")
            # Retornar la part després de l'últim guió baix
            return parts[-1].lower()

        # Estratègia 2: Nom del directori pare
        parent_dir = os.path.basename(os.path.dirname(os.path.abspath(xml_path)))
        if parent_dir and parent_dir != ".":
            return parent_dir.lower()

        # Fallback
        return "default"

    @property
    def data_dir(self) -> str:
        """
        Retorna el directori de dades segons la institució.

        Priority:
        1. Variable d'entorn DATA_DIR (per al backend web)
        2. config["institucio"] si està definit
        3. Auto-detecta del nom del XML
        4. Primera institució disponible
        5. Fallback: "data/default"

        Returns:
            Path del directori de dades (ex: "data/demo" o "../../data/demo")
        """
        # 1. Prioritat màxima: variable d'entorn DATA_DIR
        env_data_dir = os.getenv("DATA_DIR")
        if env_data_dir:
            return env_data_dir

        # 2. Configuració JSON
        institucio = self.global_data.get("institucio")

        # Si no està definit a config, auto-detectar
        if institucio is None:
            institucio = self.detectar_institucio()

        # Si encara no es pot detectar, agafar la primera disponible
        if institucio is None:
            disponibles = self.get_institucions_disponibles()
            if disponibles:
                institucio = disponibles[0]
            else:
                # Fallback si no hi ha cap institució
                institucio = "default"

        base_dir = Path(__file__).resolve().parents[1]
        return str(base_dir / "data" / institucio)

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
            Llista de noms d'institucions (ex: ["demo", "demo"])
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

    def set_institucio(self, institucio: str):
        """
        Estableix la institució actual i desa la configuració

        Args:
            institucio: Nom de la institució (ex: "demo")
        """
        self.global_data["institucio"] = institucio
        self.save_global()
        self.load_institucio()  # Recarregar config de la nova institució

        # 🔧 IMPORTANT: Recarregar prioritats quan canvia la institució
        # Les prioritats són globals i s'han de recalcular des de BD
        self._reload_prioritats()

        print(f"✅ Institució seleccionada: {institucio}")
        print(f"📁 Directori de dades: {self.data_dir}")

    def _reload_prioritats(self):
        """Recalcula les prioritats, nivells i abreviatures globals després de canviar d'institució"""
        try:
            from routes.prioritats import _recarregar_prioritats_desde_bd
            from database import get_data_db_session
            from utils.grups_utils import invalidar_cache_abreviatures

            instit = self.global_data.get("institucio") or os.getenv("APP_INSTITUCIO") or self.detectar_institucio()
            if instit:
                with get_data_db_session(instit) as db:
                    _recarregar_prioritats_desde_bd(db)

            # Invalidar cache d'abreviatures per forçar nova lectura
            invalidar_cache_abreviatures()
            print(f"✅ Cache d'abreviatures invalidat")
        except Exception as e:
            print(f"⚠️ Error recarregant prioritats/nivells: {e}")

    # ====== PATHS CENTRALITZATS DE FITXERS JSON ======
    # Propietats per accés unificat a tots els fitxers JSON del sistema

    @property
    def vigilancies_path(self) -> Path:
        """Path del fitxer de vigilàncies d'exàmens"""
        return Path(self.data_dir) / "vigilancies_examens.json"

    @property
    def substitucions_path(self) -> Path:
        """Path del fitxer de substitucions"""
        return Path(self.data_dir) / "substitucions.json"

    @property
    def configuracions_path(self) -> Path:
        """Path del fitxer de configuracions generals"""
        return Path(self.data_dir) / "configuracions.json"

    @property
    def theme_settings_path(self) -> Path:
        """Path del fitxer de configuració de tema visual"""
        return Path(self.data_dir) / "theme_settings.json"

    @property
    def grups_path(self) -> Path:
        """Path del fitxer de grups per nivell (auto-generat)"""
        return Path(self.data_dir) / "grups.json"

    @property
    def assignatures_path(self) -> Path:
        """Path del fitxer d'assignatures per nivell"""
        return Path(self.data_dir) / "assignatures.json"

    @property
    def aules_path(self) -> Path:
        """Path del fitxer d'aules"""
        return Path(self.data_dir) / "aules.json"

    @property
    def configuracio_examens_path(self) -> Path:
        """Path del fitxer de configuració d'exàmens"""
        return Path(self.data_dir) / "configuracio_examens.json"

    @property
    def master_configuracio_path(self) -> Path:
        """Path del fitxer unificat de configuració (assignatures, grups, aules)"""
        return Path(self.data_dir) / "master_configuracio.json"

    @property
    def google_credentials_path(self) -> Path:
        """Path del fitxer de credencials de Google"""
        return Path(self.data_dir) / "google_credentials.json"

    @property
    def prioritats_path(self) -> Path:
        """Path del fitxer de prioritats de substitucions"""
        return Path(self.data_dir) / "prioritats_substitucions.json"

# Instància global
config = Config()
