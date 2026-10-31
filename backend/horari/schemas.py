"""Esquemes de les rutes de l'horari."""

from typing import List, Optional

from pydantic import BaseModel


class ConfigResponse(BaseModel):
    data_actual: str
    horari_carregat: bool
    num_professors: int
    num_hores: int
    xml_missing: Optional[bool] = False


class XMLVersionUpdate(BaseModel):
    data_inici: Optional[str] = None  # la data de fi es calcula (no s'accepta)


class ProfessorsResponse(BaseModel):
    professors: List[str]
    xml_missing: Optional[bool] = None


class HoresResponse(BaseModel):
    hores: List[str]
    xml_missing: Optional[bool] = None


class ProfessorDeLXml(BaseModel):
    nom: str
    nom_cru: str  # tal com és a l'XML (els espais del davant ordenen per nivells a FET)


class TotsElsProfessorsResponse(BaseModel):
    professors: List[str]
    professors_ordenats: Optional[List[ProfessorDeLXml]] = None
    total: int
    xml_missing: Optional[bool] = None


class AbsenciaCobertaDelDia(BaseModel):
    professor: str
    data_final: Optional[str]


class ProfessorsDelDiaResponse(BaseModel):
    professors: List[str]
    total: int
    absencies_cobertes: Optional[List[AbsenciaCobertaDelDia]] = None
    xml_missing: Optional[bool] = None


class GrupsResponse(BaseModel):
    grups_raw: List[str]
    grups: List[str]
    total_raw: int
    total_abreviats: int
    xml_data_inici: Optional[str] = None
    xml_missing: Optional[bool] = None


class AssignaturesResponse(BaseModel):
    assignatures: List[str]
    total: int
    te_buits: Optional[bool] = None
    amb_grup: Optional[List[str]] = None
    xml_data_inici: Optional[str] = None
    xml_missing: Optional[bool] = None


class XmlPujatResponse(BaseModel):
    success: bool
    filename: str
    path: str
    message: str
    data_inici: Optional[str] = None  # no hi és si l'XML és idèntic i no s'ha creat cap versió
    vigent_avui: Optional[bool] = None


class VersioXml(BaseModel):
    id: int
    path: str
    data_inici: str
    data_fi: Optional[str]
    hash_contingut: Optional[str]


class VersionsXmlResponse(BaseModel):
    versions: List[VersioXml]


class SuccessResponse(BaseModel):
    success: bool
