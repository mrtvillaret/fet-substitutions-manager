"""
Models de dades bàsics
"""
from dataclasses import dataclass
from typing import List, Dict, Optional, Union
from datetime import datetime

try:
    from i18n_setup import translate as _
except ImportError:
    def _(text):
        return text

@dataclass
class Substitucio:
    """Model per una substitució"""
    data: str
    hora: str
    professor_absent: str
    assignatura: str
    grup: str
    substitut: str = ""
    tipus_substitut: str = ""
    comentaris: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "data": self.data,
            "hora": self.hora,
            "professor_absent": self.professor_absent,
            "assignatura": self.assignatura,
            "grup": self.grup,
            "substitut": self.substitut,
            "tipus_substitut": self.tipus_substitut,
            "comentaris": self.comentaris
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Substitucio":
        return cls(**data)

@dataclass
class ConfiguracioDia:
    """Configuració per un dia específic"""
    data: str
    grups_sense_classe: Union[List[str], Dict[str, List[str]]]  # Suporta antiga (List) i nova (Dict per hora)
    notes: str = ""
    creat: Optional[datetime] = None

    def to_dict(self) -> Dict:
        return {
            "data": self.data,
            "grups_sense_classe": self.grups_sense_classe,
            "notes": self.notes,
            "creat": self.creat.isoformat() if self.creat else None
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ConfiguracioDia":
        creat = None
        if data.get("creat"):
            creat = datetime.fromisoformat(data["creat"])

        # Normalitzar grups_sense_classe a Dict[str, List[str]] per compatibilitat
        grups_raw = data.get("grups_sense_classe", {})
        if isinstance(grups_raw, list):
            # Versió antiga: List[str] -> Convertir a Dict amb totes les hores de classe
            # Assumeix que si és llista, aplica a totes les hores (sense Pati)
            hores_classe = ["08:00", "09:00", "10:00", "11:30", "12:30", "13:25", "14:20", "15:00", "16:00"]
            grups_dict = {hora: grups_raw for hora in hores_classe} if grups_raw else {}
        else:
            # Versió nova: ja és Dict[str, List[str]]
            grups_dict = grups_raw

        return cls(
            data=data["data"],
            grups_sense_classe=grups_dict,
            notes=data.get("notes", ""),
            creat=creat
        )
