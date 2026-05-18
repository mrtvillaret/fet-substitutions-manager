"""
Gestor de professors de baixa temporal
"""
from datetime import datetime, date
from typing import List, Dict, Optional

try:
    from i18n_setup import translate as _
except ImportError:
    def _(text):
        return text


class GestorBaixes:
    """Gestiona professors temporalment de baixa"""

    _instance = None
    _cache = None
    _cache_time = 0

    def __new__(cls):
        """Singleton per tenir una única instància amb cache compartida"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Inicialitza el gestor"""
        # No reinicialitzem si ja existeix (singleton)
        if not hasattr(self, '_initialized'):
            self._initialized = True

    def carregar_baixes(self, institucio: str) -> List[Dict]:
        """
        Carrega professors de baixa des de SQLite
        """
        try:
            from database import get_data_db_session
            from repositories import ProfessorBaixaRepository

            with get_data_db_session(institucio) as db:
                baixes = ProfessorBaixaRepository.get_all(db)
            return baixes or []
        except Exception as e:
            print(_("⚠️ Error en carregar baixes: {}").format(e))
            return []

    def esta_de_baixa(self, professor: str, data: date, institucio: str) -> bool:
        """
        Comprova si un professor està de baixa en una data concreta

        Args:
            professor: Nom del professor
            data: Data a comprovar
            institucio: Nom de la institució

        Returns:
            True si està de baixa, False si no
        """
        # Carrega baixes amb cache
        baixes = self._get_baixes_cached(institucio)

        for baixa in baixes:
            if baixa["professor"] != professor:
                continue

            try:
                # Converteix strings a dates
                data_inici = datetime.strptime(baixa["data_inici"], "%Y-%m-%d").date()
                data_final = datetime.strptime(baixa["data_final"], "%Y-%m-%d").date()

                # Comprova si la data està dins del rang (inclusiu)
                if data_inici <= data <= data_final:
                    return True

            except ValueError as e:
                print(_("⚠️ Error en parsear dates baixa {}: {}").format(professor, e))
                continue

        return False

    def get_professors_baixa(self, data: date, institucio: str) -> List[str]:
        """
        Retorna llista de professors de baixa en una data concreta

        Args:
            data: Data a comprovar
            institucio: Nom de la institució

        Returns:
            Llista amb noms dels professors de baixa
        """
        baixes = self._get_baixes_cached(institucio)
        professors_baixa = []

        for baixa in baixes:
            try:
                data_inici = datetime.strptime(baixa["data_inici"], "%Y-%m-%d").date()
                data_final = datetime.strptime(baixa["data_final"], "%Y-%m-%d").date()

                if data_inici <= data <= data_final:
                    professors_baixa.append(baixa["professor"])

            except ValueError:
                continue

        return professors_baixa

    def _get_baixes_cached(self, institucio: str) -> List[Dict]:
        """
        Obté baixes amb cache (evita llegir constantment la BD)

        Args:
            institucio: Nom de la institució

        Returns:
            Llista de baixes
        """
        import time

        # Temps de cache: 5 segons (prou per no llegir a cada crida)
        CACHE_DURATION = 5

        current_time = time.time()

        # Si no hi ha cache o ha expirat, recarrega
        if (GestorBaixes._cache is None or
            current_time - GestorBaixes._cache_time > CACHE_DURATION or
            GestorBaixes._cache.get("institucio") != institucio):

            GestorBaixes._cache = {
                "institucio": institucio,
                "baixes": self.carregar_baixes(institucio)
            }
            GestorBaixes._cache_time = current_time

        return GestorBaixes._cache.get("baixes", [])

    @staticmethod
    def invalidar_cache():
        """
        Invalida el cache forçant una recàrrega en la propera consulta
        Cridar després de modificar les baixes a la BD
        """
        GestorBaixes._cache = None
        GestorBaixes._cache_time = 0
        print(_("🔄 Cache de baixes invalidat"))


# Instància singleton global
gestor_baixes = GestorBaixes()
