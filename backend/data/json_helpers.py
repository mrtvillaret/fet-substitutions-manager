"""
Helpers per operacions JSON consolidades per eliminar duplicació
Centralitza patterns repetitius d'I/O amb gestió d'errors estandarditzada
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

try:
    from i18n_setup import translate as _
except ImportError:
    def _(text):
        return text


class JSONHelpers:
    """Helpers estàtics per operacions JSON segures"""
    
    @staticmethod
    def safe_load(file_path: Union[str, Path], default: Any = None, encoding: str = 'utf-8') -> Any:
        """Carrega JSON amb gestió d'errors segura"""
        try:
            path = Path(file_path)
            if path.exists():
                with open(path, 'r', encoding=encoding) as f:
                    return json.load(f)
            return default if default is not None else {}
        except Exception:
            return default if default is not None else {}
    
    @staticmethod
    def safe_save(file_path: Union[str, Path], data: Any, encoding: str = 'utf-8', 
                  indent: int = 2, ensure_ascii: bool = False) -> bool:
        """Desa JSON amb gestió d'errors segura"""
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, 'w', encoding=encoding) as f:
                json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)
            return True
        except Exception:
            return False
    
    @staticmethod
    def load_or_create(file_path: Union[str, Path], default_factory=dict, encoding: str = 'utf-8') -> Any:
        """Carrega JSON o crea amb factory si no existeix"""
        try:
            path = Path(file_path)
            if path.exists():
                with open(path, 'r', encoding=encoding) as f:
                    return json.load(f)
            return default_factory()
        except Exception:
            return default_factory()
    
    @staticmethod
    def update_nested(file_path: Union[str, Path], key: str, value: Any, 
                     encoding: str = 'utf-8') -> bool:
        """Actualitza una clau en JSON existent"""
        try:
            data = JSONHelpers.safe_load(file_path, {}, encoding)
            data[key] = value
            return JSONHelpers.safe_save(file_path, data, encoding)
        except Exception:
            return False
    
    @staticmethod
    def get_nested(file_path: Union[str, Path], key: str, default: Any = None,
                   encoding: str = 'utf-8') -> Any:
        """Obté valor d'una clau en JSON"""
        try:
            data = JSONHelpers.safe_load(file_path, {}, encoding)
            return data.get(key, default)
        except Exception:
            return default
