"""Esquemes de les rutes de l'horari."""

from datetime import date

from pydantic import BaseModel


class ConfigResponse(BaseModel):
    data_actual: date
    horari_carregat: bool
    num_professors: int
    num_hores: int
    xml_missing: bool | None = False


class XMLVersionUpdate(BaseModel):
    # Es valida a la ruta un cop trobada la versió. El text buit equival a ometre-la.
    data_inici: str | None = None


class ProfessorsResponse(BaseModel):
    professors: list[str]
    xml_missing: bool | None = None


class HoresResponse(BaseModel):
    hores: list[str]
    xml_missing: bool | None = None


class ProfessorDeLXml(BaseModel):
    nom: str
    nom_cru: str  # tal com és a l'XML (els espais del davant ordenen per nivells a FET)


class TotsElsProfessorsResponse(BaseModel):
    professors: list[str]
    professors_ordenats: list[ProfessorDeLXml] | None = None
    total: int
    xml_missing: bool | None = None


class AbsenciaCobertaDelDia(BaseModel):
    professor: str
    data_final: date | None


class ProfessorsDelDiaResponse(BaseModel):
    professors: list[str]
    total: int
    absencies_cobertes: list[AbsenciaCobertaDelDia] | None = None
    xml_missing: bool | None = None


class GrupsResponse(BaseModel):
    grups_raw: list[str]
    grups: list[str]
    total_raw: int
    total_abreviats: int
    xml_data_inici: date | None = None
    xml_missing: bool | None = None


class AssignaturesResponse(BaseModel):
    assignatures: list[str]
    total: int
    te_buits: bool | None = None
    amb_grup: list[str] | None = None
    xml_data_inici: date | None = None
    xml_missing: bool | None = None


class AvisXml(BaseModel):
    data: str
    hora: str
    professor: str
    motiu: str | None = None
    grup: str | None = None
    tipus: str | None = None
    missatge: str | None = None


class RecomptesAvisosXml(BaseModel):
    dies: int
    substitucions: int
    vigilancies: int


class XmlPujatResponse(BaseModel):
    success: bool
    filename: str
    path: str
    message: str
    data_inici: date | None = None  # no hi és si l'XML és idèntic i no s'ha creat cap versió
    vigent_avui: bool | None = None
    avisos: list[AvisXml]
    recomptes: RecomptesAvisosXml


class VersioXml(BaseModel):
    id: int
    path: str
    data_inici: date
    data_fi: date | None
    hash_contingut: str | None


class VersionsXmlResponse(BaseModel):
    versions: list[VersioXml]


class SuccessResponse(BaseModel):
    success: bool
