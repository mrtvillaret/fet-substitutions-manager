"""
Rutes de la configuració d'exàmens (/api/config/*, només admins): només HTTP;
la lògica, a services.py (configuració mestra i assignacions) i a
importacio.py (importació i exportació).

Nivells, assignatures i grups per nivell, aules, les assignacions (assignatura,
grup, titular, aula), la importació de propostes des de l'XML o d'un CSV i
l'exportació a CSV. Les abreviatures de grups són a grups/ i les afinitats
de vigilàncies a vigilancies/ (les mateixes URL).
"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from auth.dependencies import require_admin
from configuracio_examens import importacio, services
from configuracio_examens.schemas import (
    AssignacionsObsoletesResponse,
    AssignacionsQueHoFanServirResponse,
    AssignacionsResponse,
    AssignacioRequest,
    AssignaturesResponse,
    AulesResponse,
    CreacioResponse,
    EdicioAssignacioRequest,
    EliminadesResponse,
    EsborrarAssignacionsRequest,
    EsborratAmbAssignacionsResponse,
    EsborratResponse,
    GrupsResponse,
    ImpacteRequest,
    ImpacteResponse,
    ImportacioRequest,
    ImportacioResponse,
    MissatgeResponse,
    NivellsResponse,
    NouGrupRequest,
    NouNivellRequest,
    NouNomRequest,
    NovaAssignaturaRequest,
    NovaAulaRequest,
    PropostesResponse,
    RenameRequest,
)
from dependencies import dia_de_la_planificacio, get_db
from errors_domini import MissingXmlError
from serveis.dia import Dia

router = APIRouter(prefix="/api/config", tags=["Configuració Exàmens"])


# ===== NIVELLS =====


@router.get("/nivells", response_model=NivellsResponse)
def get_nivells(db: Session = Depends(get_db)):
    """Retorna tots els nivells disponibles"""
    return {"nivells": services.nivells(db)}


@router.post("/nivells", response_model=MissatgeResponse)
def add_nivell(nivell: NouNivellRequest, db: Session = Depends(get_db)):
    """Afegeix un nou nivell"""
    codi = nivell.codi
    services.afegeix_nivell(db, codi, nivell.nom)
    return {"success": True, "message": f"Nivell '{codi}' afegit"}


@router.get("/nivells/{codi}/assignacions", response_model=AssignacionsQueHoFanServirResponse)
def get_assignacions_del_nivell(codi: str, db: Session = Depends(get_db)):
    """Quantes assignacions fan servir el nivell (les dels seus grups)"""
    return {"assignacions": services.assignacions_del_nivell(db, codi)}


@router.delete("/nivells/{codi}", response_model=EsborratAmbAssignacionsResponse)
def delete_nivell(codi: str, amb_assignacions: bool = False, db: Session = Depends(get_db)):
    """Elimina un nivell; amb `amb_assignacions`, també les assignacions dels seus grups"""
    assignacions = services.esborra_nivell(db, codi, amb_assignacions)
    return {
        "success": True,
        "message": f"Nivell '{codi}' eliminat",
        "assignacions": assignacions,
        "assignacions_esborrades": amb_assignacions,
    }


# ===== ASSIGNATURES =====


@router.get("/assignatures/{nivell}", response_model=AssignaturesResponse)
def get_assignatures(nivell: str, db: Session = Depends(get_db)):
    """Retorna assignatures d'un nivell"""
    return {"assignatures": services.assignatures(db, nivell)}


@router.post("/assignatures/{nivell}", response_model=MissatgeResponse)
def add_assignatura(nivell: str, assignatura: NovaAssignaturaRequest, db: Session = Depends(get_db)):
    """Afegeix una assignatura a un nivell"""
    nom = assignatura.nom
    services.afegeix_assignatura(db, nivell, nom)
    return {"success": True, "message": f"Assignatura '{nom}' afegida a {nivell}"}


@router.put("/assignatures/{nivell}/{nom}", response_model=MissatgeResponse)
def rename_assignatura(nivell: str, nom: str, rename: NouNomRequest, db: Session = Depends(get_db)):
    """Reanomena una assignatura i propaga el canvi"""
    services.reanomena_assignatura(db, nivell, nom, rename.nou_nom)
    return {"success": True, "message": f"Assignatura '{nom}' reanomenada a '{rename.nou_nom}'"}


@router.delete("/assignatures/{nivell}/{nom}", response_model=MissatgeResponse)
def delete_assignatura(nivell: str, nom: str, db: Session = Depends(get_db)):
    """Elimina una assignatura d'un nivell"""
    services.esborra_assignatura(db, nivell, nom)
    return {"success": True, "message": f"Assignatura '{nom}' eliminada"}


# ===== GRUPS =====


@router.get("/grups/{nivell}", response_model=GrupsResponse)
def get_grups(nivell: str, db: Session = Depends(get_db)):
    """Retorna grups d'un nivell"""
    return {"grups": services.grups(db, nivell)}


@router.post("/grups/{nivell}", response_model=MissatgeResponse)
def add_grup(nivell: str, grup: NouGrupRequest, db: Session = Depends(get_db)):
    """Afegeix un grup a un nivell"""
    codi = grup.codi
    services.afegeix_grup(db, nivell, codi)
    return {"success": True, "message": f"Grup '{codi}' afegit a {nivell}"}


@router.put("/grups/{codi}", response_model=MissatgeResponse)
def rename_grup(codi: str, rename: RenameRequest, db: Session = Depends(get_db)):
    """Reanomena un grup i propaga el canvi"""
    services.reanomena_grup(db, codi, rename.nou_nom)
    return {"success": True, "message": f"Grup '{codi}' reanomenat a '{rename.nou_nom}'"}


@router.get("/grups/{codi}/assignacions", response_model=AssignacionsQueHoFanServirResponse)
def get_assignacions_del_grup(codi: str, db: Session = Depends(get_db)):
    """Quantes assignacions fan servir el grup"""
    return {"assignacions": services.assignacions_del_grup(db, codi)}


@router.delete("/grups/{codi}", response_model=EsborratAmbAssignacionsResponse)
def delete_grup(codi: str, amb_assignacions: bool = False, db: Session = Depends(get_db)):
    """Elimina un grup; amb `amb_assignacions`, també les seves assignacions"""
    assignacions = services.esborra_grup(db, codi, amb_assignacions)
    return {
        "success": True,
        "message": f"Grup '{codi}' eliminat",
        "assignacions": assignacions,
        "assignacions_esborrades": amb_assignacions,
    }


# ===== AULES =====


@router.get("/aules", response_model=AulesResponse)
def get_aules(db: Session = Depends(get_db)):
    """Retorna totes les aules"""
    return {"aules": services.aules(db)}


@router.post("/aules", response_model=MissatgeResponse)
def add_aula(aula: NovaAulaRequest, db: Session = Depends(get_db)):
    """Afegeix una aula"""
    codi = services.afegeix_aula(db, aula.codi)
    return {"success": True, "message": f"Aula '{codi}' afegida"}


@router.put("/aules/{codi}", response_model=MissatgeResponse)
def rename_aula(codi: str, rename: NouNomRequest, db: Session = Depends(get_db)):
    """Reanomena una aula i propaga el canvi"""
    services.reanomena_aula(db, codi, rename.nou_nom)
    return {"success": True, "message": f"Aula '{codi}' reanomenada a '{rename.nou_nom}'"}


@router.delete("/aules/{codi}", response_model=EsborratResponse)
def delete_aula(codi: str, db: Session = Depends(get_db)):
    """Elimina una aula"""
    assignacions = services.esborra_aula(db, codi)
    return {"success": True, "message": f"Aula '{codi}' eliminada", "assignacions": assignacions}


# ===== ASSIGNACIONS PROFESSOR-TITULAR =====


@router.get("/assignacions", response_model=AssignacionsResponse)
def get_assignacions(db: Session = Depends(get_db)):
    """Retorna totes les assignacions professor-titular"""
    return {"assignacions": services.assignacions(db)}


@router.get("/assignacions-obsoletes", response_model=AssignacionsObsoletesResponse)
def get_assignacions_obsoletes(
    db: Session = Depends(get_db), current_user=Depends(require_admin), dia: Dia = Depends(dia_de_la_planificacio)
):
    """Assignacions amb un grup o un titular que no són a l'horari del
    planificador (el vigent a la primera data planificada; sense dates, avui):
    p.ex. d'un curs anterior. El nom de l'assignatura no es té en compte: es
    pot haver canviat a mà (p.ex. "1.1 Prof 7" per a una franja d'optatives).
    Un grup dels nivells de la configuració d'exàmens també és vàlid, encara
    que no sigui a l'XML (p.ex. «4-ESO-AB», d'un professor que fa d'enllaç de
    dos grups): si es treu de la configuració, torna a sortir.
    Per treure-les: DELETE /assignacions amb els ids."""
    try:
        horari = dia.horari
    except MissingXmlError:
        return {"assignacions": []}
    return {"assignacions": services.assignacions_obsoletes(db, horari)}


@router.post("/assignacions", response_model=CreacioResponse)
def create_assignacio(assignacio: AssignacioRequest, db: Session = Depends(get_db)):
    """Crea una nova assignació professor-titular"""
    assignacio_id, assignatura, grup = services.crea_assignacio(db, assignacio.model_dump())
    return {"success": True, "id": assignacio_id, "message": f"Assignació creada: {assignatura} - {grup}"}


@router.put("/assignacions/{assignacio_id}", response_model=MissatgeResponse)
def update_assignacio(assignacio_id: int, assignacio: EdicioAssignacioRequest, db: Session = Depends(get_db)):
    """Actualitza una assignació existent"""
    services.edita_assignacio(db, assignacio_id, assignacio.model_dump())
    return {"success": True, "message": "Assignació actualitzada"}


@router.delete("/assignacions/{assignacio_id}", response_model=MissatgeResponse)
def delete_assignacio(assignacio_id: int, db: Session = Depends(get_db)):
    """Elimina una assignació"""
    services.esborra_assignacio(db, assignacio_id)
    return {"success": True, "message": "Assignació eliminada"}


@router.delete("/assignacions", response_model=EliminadesResponse)
def eliminar_assignacions_massiu(
    payload: EsborrarAssignacionsRequest, db: Session = Depends(get_db), current_user=Depends(require_admin)
):
    """Elimina diverses assignacions de cop (per net a fons abans de re-importar
    des d'un XML nou). `ids`: llista d'ids a esborrar; `tot: true` ho esborra tot."""
    return {"success": True, "eliminades": services.esborra_assignacions(db, payload.model_dump())}


# ===== IMPORTAR DES DE L'HORARI =====


@router.get("/importar-assignacions/preview", response_model=PropostesResponse)
def importar_assignacions_preview(
    db: Session = Depends(get_db), current_user=Depends(require_admin), dia: Dia = Depends(dia_de_la_planificacio)
):
    """Genera propostes d'assignacions (assignatura/grup/titular/aula) a partir
    de l'horari del planificador (el vigent a la primera data planificada;
    sense dates, avui), sense escriure res a la BD."""
    try:
        # Amb tothom: les classes d'un titular amb una absència coberta aquell
        # dia també són del curs
        horari = dia.horari_amb_tothom
    except MissingXmlError as e:
        raise HTTPException(status_code=400, detail={"xml_missing": True, "message": str(e)}) from e
    return importacio.propostes_de_l_horari(db, horari)


@router.post("/importar-assignacions/dry-run", response_model=ImpacteResponse)
def importar_assignacions_dry_run(
    payload: ImpacteRequest, db: Session = Depends(get_db), current_user=Depends(require_admin)
):
    """Calcula què faria una importació (nivells/grups/assignatures/aules/
    assignacions que es crearien) SENSE escriure res, perquè es pugui mostrar
    un resum previ abans de confirmar."""
    return importacio.impacte_propostes(db, [p.model_dump() for p in payload.propostes], payload.overwrite)


@router.post("/importar-assignacions", response_model=ImportacioResponse)
def importar_assignacions(
    payload: ImportacioRequest, db: Session = Depends(get_db), current_user=Depends(require_admin)
):
    """Aplica una llista de propostes: crea nivell/assignatura/grup/aula mestres si
    calen, i l'assignació (evitant duplicats exactes assignatura+grup+titular).
    Amb `overwrite: true` s'esborra TOTA la configuració d'exàmens abans.
    `descartades`: propostes que l'usuari ha desmarcat expressament (no
    existeixen encara), perquè no es tornin a proposar marcades la propera
    vegada que s'obri el diàleg d'importació."""
    return importacio.importa_propostes(
        db,
        [p.model_dump() for p in payload.propostes],
        [d.model_dump() for d in payload.descartades],
        payload.overwrite,
    )


# ===== EXPORTAR / IMPORTAR ASSIGNACIONS EN CSV (per reutilitzar entre cursos/centres) =====


@router.get("/exportar-assignacions-csv")
def exportar_assignacions_csv(db: Session = Depends(get_db), current_user=Depends(require_admin)):
    """Exporta totes les assignacions actuals a un fitxer CSV descarregable,
    incloent-hi el nivell real de cada grup (des de la taula mestra) perquè
    el fitxer es pugui reimportar sense ambigüitat."""
    return StreamingResponse(
        iter([importacio.exporta_csv(db)]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=assignacions_{current_user.institucio}.csv"},
    )


@router.post("/importar-assignacions-csv/dry-run", response_model=ImpacteResponse)
def importar_assignacions_csv_dry_run(
    file: UploadFile = File(...),
    overwrite: bool = Form(False),
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Calcula què faria una importació CSV (mateixa lògica que l'endpoint
    real) SENSE escriure res, perquè es pugui mostrar un resum previ."""
    files_rows = importacio.llegeix_csv(file.filename, file.file.read())
    return importacio.impacte_csv(db, files_rows, overwrite)


@router.post("/importar-assignacions-csv", response_model=ImportacioResponse)
def importar_assignacions_csv(
    file: UploadFile = File(...),
    overwrite: bool = Form(False),
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Importa des d'un CSV (columnes: nivell,assignatura,grup,titular,aula).
    nivell, assignatura i grup són obligatoris (cap valor es dedueix ni
    s'inventa): si en falta algun, la fila es descarta sencera amb un avís.
    titular i aula són opcionals, però si es dona un titular que no existeix
    a la BD, la fila també es descarta sencera (no es crea a mitges sense
    titular). Una fila totalment buida s'ignora.
    Amb `overwrite=true` s'esborra TOTA la configuració d'exàmens abans."""
    files_rows = importacio.llegeix_csv(file.filename, file.file.read())
    return importacio.importa_csv(db, files_rows, overwrite)
