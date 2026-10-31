"""
Rutes de l'horari (XML de FET): només HTTP; la lògica, a services.py.

`router` (qualsevol usuari): l'horari vigent a `data` (o, sense, avui)
- /api/config, /api/professors, /api/hores: estat de l'horari, professors
  (fins a l'últim configurat) i hores
- /api/horari/professors(/all), /api/horari/grups/detectar,
  /api/horari/assignatures/detectar: per als desplegables de configuració

`router_admin` (només admins; les URL de sempre):
- /api/files/upload-xml: puja i versiona un XML
- /api/settings/xml-versions: les versions de l'XML (llistar, canviar quan
  comencen, esborrar)
"""

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from auth.dependencies import require_admin
from dependencies import dia_del_calendari, get_db
from horari import services
from horari.schemas import (
    AssignaturesResponse,
    ConfigResponse,
    GrupsResponse,
    HoresResponse,
    ProfessorsDelDiaResponse,
    ProfessorsResponse,
    SuccessResponse,
    TotsElsProfessorsResponse,
    VersionsXmlResponse,
    XmlPujatResponse,
    XMLVersionUpdate,
)
from parametres import DataISO
from serveis.dia import Dia

router = APIRouter()
router_admin = APIRouter()


@router.get("/api/config", tags=["General"], response_model=ConfigResponse)
def get_config(dia: Dia = Depends(dia_del_calendari)):
    """Estat de l'horari vigent a `data` (o, sense, avui): professors i hores"""
    return services.estat(dia)


@router.get("/api/professors", tags=["General"], response_model=ProfessorsResponse, response_model_exclude_unset=True)
def get_professors(dia: Dia = Depends(dia_del_calendari)):
    """Professors de l'horari vigent a `data` (o, sense, avui), fins a l'últim configurat"""
    return services.professors(dia)


@router.get("/api/hores", tags=["General"], response_model=HoresResponse, response_model_exclude_unset=True)
def get_hores(dia: Dia = Depends(dia_del_calendari)):
    """Hores del dia en l'ordre de l'XML (no alfabètic), de l'horari vigent a
    `data` (AAAA-MM-DD) o, sense, avui."""
    return services.hores(dia)


@router.get(
    "/api/horari/professors/all",
    tags=["Horari"],
    response_model=TotsElsProfessorsResponse,
    response_model_exclude_unset=True,
)
def get_all_professors(dia: Dia = Depends(dia_del_calendari)):
    """
    Retorna TOTS els professors de l'XML vigent a `data` (o, sense, avui),
    sense aplicar límit ultim_professor_subs. Per als desplegables de configuració.
    """
    return services.tots_els_professors(dia)


@router.get(
    "/api/horari/professors",
    tags=["Horari"],
    response_model=ProfessorsDelDiaResponse,
    response_model_exclude_unset=True,
)
def get_professors_filtered(data: DataISO = None, dia: Dia = Depends(dia_del_calendari)):
    """
    Retorna professors amb el límit ultim_professor_subs aplicat. Amb `data`
    (AAAA-MM-DD), els de l'horari vigent aquell dia i, a part, els que hi
    tenen una absència coberta, amb la data de fi (no se'ls posen absències);
    sense, els de l'horari vigent avui.
    """
    return services.professors_del_dia(dia, data)


@router.get(
    "/api/horari/grups/detectar", tags=["Horari"], response_model=GrupsResponse, response_model_exclude_unset=True
)
def detectar_grups(dia: Dia = Depends(dia_del_calendari)):
    """
    Detecta tots els grups del XML vigent per una data (o l'actual si no se'n dóna).
    Usar la data fa que la configuració treballi sobre el MATEIX XML que veurà la
    vista de grups sense classe per aquella data (evita barreges entre cursos).

    Retorna:
    - grups_raw: Grups tal com apareixen al XML (ex: "1-BATX-A,1-BATX-B")
    - grups: Grups amb abreviatures aplicades (ex: "1-BATX-AB")
    - xml_data_inici: data d'inici de la versió d'XML carregada (per indicar-la)
    """
    return services.grups(dia)


@router.get(
    "/api/horari/assignatures/detectar",
    tags=["Horari"],
    response_model=AssignaturesResponse,
    response_model_exclude_unset=True,
)
def detectar_assignatures(dia: Dia = Depends(dia_del_calendari)):
    """
    Detecta totes les assignatures de l'XML vigent per una data (o l'actual si
    no se'n dóna). Igual que la detecció de grups, usar la data fa que la
    configuració treballi sobre el MATEIX XML vigent per aquella data.

    Retorna també:
    - te_buits: si hi ha hores amb Subject buit (que NO s'han de substituir)
    - xml_data_inici: data d'inici de la versió d'XML carregada (per indicar-la)
    """
    return services.assignatures(dia)


@router_admin.post(
    "/api/files/upload-xml", tags=["Fitxers"], response_model=XmlPujatResponse, response_model_exclude_unset=True
)
def upload_xml(
    file: UploadFile = File(...), data_inici: Optional[DataISO] = Form(None), current_user=Depends(require_admin)
):
    """
    Puja un fitxer XML de FET i el versiona a partir d'una data de vigència.

    `data_inici` (YYYY-MM-DD, per defecte avui) permet **preparar** l'horari d'un curs
    futur sense que passi a ser vigent immediatament: la versió anterior es tanca el dia
    abans, i el punter "actual" (`xml_horari_path`) només es mou si la nova versió ja és
    vigent avui.
    """
    return services.puja_xml(current_user.institucio, file.filename, file.file, data_inici)


@router_admin.get(
    "/api/settings/xml-versions",
    tags=["Configuració General"],
    response_model=VersionsXmlResponse,
    response_model_exclude_unset=True,
)
def get_xml_versions(db: Session = Depends(get_db)):
    """
    Retorna l'històric d'XMLs per la institució actual
    """
    return services.llista_versions(db)


@router_admin.put(
    "/api/settings/xml-versions/{version_id}",
    tags=["Configuració General"],
    response_model=SuccessResponse,
    response_model_exclude_unset=True,
)
def update_xml_version(version_id: int, payload: XMLVersionUpdate, db: Session = Depends(get_db)):
    """
    Canvia quan comença una versió d'XML. Les dates de fi es recalculen totes
    (el dia abans que comenci la següent): no es poden posar a mà.
    """
    services.canvia_inici(db, version_id, payload.data_inici)
    return {"success": True}


@router_admin.delete(
    "/api/settings/xml-versions/{version_id}",
    tags=["Configuració General"],
    response_model=SuccessResponse,
    response_model_exclude_unset=True,
)
def delete_xml_version(version_id: int, db: Session = Depends(get_db), current_user=Depends(require_admin)):
    """
    Elimina una versió d'XML i el seu fitxer; les altres s'encadenen de nou (sense forats).
    """
    services.esborra_versio(db, current_user.institucio, version_id)
    return {"success": True}
