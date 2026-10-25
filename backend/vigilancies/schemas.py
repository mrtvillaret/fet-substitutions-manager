"""Schemas d'entrada i de sortida de les rutes de vigilàncies."""

from typing import List, Optional

from pydantic import BaseModel

from noms import NomNet


class VigilanciaRequest(BaseModel):
    hora: str
    tipus: str
    grups: str
    aula: NomNet
    vigilant: Optional[NomNet] = ""
    comentaris: Optional[str] = ""
    nivell: str
    # L'id d'una fila de la mateixa hora: la nova va just a sota (el «+» de
    # cada fila, que la copia). Sense, va al final del bloc de la seva hora.
    despres_de: Optional[str] = None


class EdicioVigilanciaRequest(BaseModel):
    """Només els camps que es canvien. Sense `force`, cal l'`updated_at` que es
    va llegir (409 si algú l'ha modificat mentrestant)."""

    hora: Optional[str] = None
    tipus: Optional[str] = None
    grups: Optional[str] = None
    aula: Optional[NomNet] = None
    vigilant: Optional[NomNet] = None
    comentaris: Optional[str] = None
    nivell: Optional[str] = None
    updated_at: Optional[str] = None
    force: Optional[bool] = False


class ConsultaDisponibles(BaseModel):
    hora: str
    tipus: Optional[str] = None
    grups: Optional[str] = None
    aula: Optional[NomNet] = None


class DisponiblesEnBlocRequest(BaseModel):
    queries: List[ConsultaDisponibles]


class TitularHoraLliure(BaseModel):
    """Un titular que no s'ha posat perquè tenia l'hora lliure: ho decideix
    qui fa les vigilàncies."""

    vigilancia_id: str
    hora: str
    grups: str
    tipus: str
    titular: str


class AssignacioResponse(BaseModel):
    assigned_count: int
    remaining_count: int
    message: str


class VigilanciaSenseTitular(BaseModel):
    """Una vigilància que la configuració d'exàmens no deixa definida.
    motiu: "cap_fila_grup" (l'assignatura té files, però cap per al grup) o
    "diversos_titulars" (s'ha assignat igualment; cal l'aula de cada professor
    a la configuració perquè quedi definit)."""

    vigilancia_id: str
    hora: str
    grups: str
    tipus: str
    motiu: str


class AssignacioTitularsResponse(AssignacioResponse):
    titulars_hora_lliure: List[TitularHoraLliure] = []
    vigilancies_sense_titular: List[VigilanciaSenseTitular] = []


class OrdreRequest(BaseModel):
    """L'ordre de les files d'una hora: els ids, de la primera a l'última."""

    hora: str
    ids: List[str]


class OrdreManualResponse(BaseModel):
    ordre_manual: bool


class ActivitatHora(BaseModel):
    """El que diu l'horari d'un professor a una hora."""

    assignatura: str
    grup: str
    aula: str


class SubstitucioHora(BaseModel):
    professor_absent: str
    assignatura: str
    grup: str
    aula: str


class VigilanciaHora(BaseModel):
    id: str
    tipus: str
    grups: str
    aula: str


class AjudaVigilantResponse(BaseModel):
    """Tot el que té un professor a una hora, per a l'ajuda en passar per
    damunt del vigilant. `estat`: absencia_coberta, absent, alliberat,
    disponible, classe, lliure o fora_de_l_horari (no és a l'horari del dia)."""

    professor: str
    hora: str
    estat: str
    activitat: Optional[ActivitatHora] = None
    tipus_absencia: Optional[str] = None
    substitucions: List[SubstitucioHora]
    vigilancies_hora: List[VigilanciaHora]
    vigilancies_dia: int
