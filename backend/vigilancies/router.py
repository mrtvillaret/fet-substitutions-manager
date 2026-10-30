"""
Rutes de /api/vigilancies (vigilàncies d'examen de cada dia):
- Configuració de la pantalla (nivells, professors, hores, grups, aules)
- Crear, llistar, editar i esborrar
- Professors disponibles per vigilar (d'un en un i en bloc), i l'ajuda del vigilant
- Assignació automàtica (titulars, pendents)
- Netejar i ordenar
(Els PDF de vigilàncies són a pdf/router.py, /api/pdf/vigilancies/...)
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from dependencies import dia_de_la_peticio, dia_del_calendari, get_db
from noms import NomNet
from routes.parametres import DataISO
from serveis.dia import Dia
from vigilancies import services
from vigilancies.schemas import (
    AjudaVigilantResponse,
    AssignacioResponse,
    AssignacioTitularsResponse,
    DisponiblesEnBlocRequest,
    EdicioVigilanciaRequest,
    OrdreManualResponse,
    OrdreRequest,
    VigilanciaRequest,
)

router = APIRouter(prefix="/api/vigilancies", tags=["Vigilàncies"])


def _conflicte(exc: services.ConflicteVigilancia) -> HTTPException:
    """La pantalla espera, amb el 409, la versió actual de la vigilància."""
    return HTTPException(
        status_code=409,
        detail={"error": "conflict", "message": exc.missatge, "current_data": exc.vigilancia},
    )


@router.get("/config")
def obtenir_config_vigilancies(db: Session = Depends(get_db), dia: Dia = Depends(dia_del_calendari)):
    """Configuració per gestionar vigilàncies: nivells, professors i hores de
    l'horari vigent a `data` (o, sense, avui), grups, aules i tipus d'examen."""
    return services.config(db, dia)


@router.get("/{data}/{hora}/disponibles")
def obtenir_disponibles_vigilancia(
    data: DataISO,
    hora: str,
    tipus: str = None,
    grups: str = None,
    aula: NomNet = None,
    db: Session = Depends(get_db),
    dia: Dia = Depends(dia_de_la_peticio),
):
    """
    Professors disponibles per a una vigilància, amb el que fan a l'hora.
    `tipus`, `grups` i `aula` (opcionals) serveixen per detectar el titular.
    """
    return services.disponibles(db, dia, hora, tipus=tipus, grups=grups, aula=aula)


@router.get("/{data}/{hora}/professor", response_model=AjudaVigilantResponse)
def obtenir_ajuda_vigilant(
    data: DataISO,
    hora: str,
    nom: NomNet,
    db: Session = Depends(get_db),
    dia: Dia = Depends(dia_de_la_peticio),
):
    """Tot el que té el professor `nom` a aquella hora (l'ajuda en passar per
    damunt del vigilant): activitat, estat, substitucions i vigilàncies."""
    return services.ajuda_vigilant(db, dia, hora, nom)


@router.post("/{data}/disponibles-batch")
def obtenir_disponibles_vigilancia_batch(
    data: DataISO,
    payload: DisponiblesEnBlocRequest,
    db: Session = Depends(get_db),
    dia: Dia = Depends(dia_de_la_peticio),
):
    """Disponibles per a moltes consultes en una sola crida."""
    return {"results": services.disponibles_en_bloc(db, dia, payload.queries)}


@router.get("/{data}")
def obtenir_vigilancies(data: DataISO, db: Session = Depends(get_db)):
    """Les vigilàncies del dia: llista plana, amb l'id de la BD."""
    return services.llista(db, data)


@router.post("/{data}")
def crear_vigilancia(data: DataISO, vigilancia: VigilanciaRequest, db: Session = Depends(get_db)):
    """Afegeix una vigilància al dia."""
    return {
        "success": True,
        "message": "Vigilància creada correctament",
        "vigilancia": services.crea(db, data, vigilancia),
    }


@router.get("/{data}/ordre", response_model=OrdreManualResponse)
def obtenir_ordre_manual(data: DataISO, db: Session = Depends(get_db)):
    """Si l'ordre de les files del dia té retocs fets a mà (no és l'automàtic):
    «Ordena» els perdria."""
    return {"ordre_manual": services.ordre_manual(db, data)}


@router.put("/{data}/ordre")
def desar_ordre(data: DataISO, ordre: OrdreRequest, db: Session = Depends(get_db)):
    """Desa l'ordre de les files d'una hora (400 si n'hi ha d'una altra hora;
    409 si les files de l'hora han canviat mentrestant)."""
    services.desa_ordre(db, data, ordre.hora, ordre.ids)
    return {"success": True}


@router.put("/{data}/{vig_id}")
def actualitzar_vigilancia(data: DataISO, vig_id: str, update: EdicioVigilanciaRequest, db: Session = Depends(get_db)):
    """Actualitza una vigilància (id de la BD o, l'antic, «hora|nivell|posició»)."""
    try:
        updated_at = services.edita(db, data, vig_id, update)
    except services.ConflicteVigilancia as exc:
        raise _conflicte(exc) from None
    return {"success": True, "message": "Vigilància actualitzada correctament", "updated_at": updated_at}


@router.delete("/{data}/{vig_id}")
def eliminar_vigilancia(
    data: DataISO, vig_id: str, updated_at: str = None, force: bool = False, db: Session = Depends(get_db)
):
    """Elimina una vigilància (id de la BD o, l'antic, «hora|nivell|posició»)."""
    try:
        services.esborra(db, data, vig_id, updated_at=updated_at, force=force)
    except services.ConflicteVigilancia as exc:
        raise _conflicte(exc) from None
    return {"success": True, "message": "Vigilància eliminada correctament"}


# ===== Assignació automàtica =====


@router.post("/{data}/assign/titulars", response_model=AssignacioTitularsResponse)
def assignar_titulars(data: DataISO, db: Session = Depends(get_db), dia: Dia = Depends(dia_de_la_peticio)):
    """Assigna NOMÉS els titulars alliberats o disponibles."""
    return services.assigna_titulars(db, dia, data)


@router.post("/{data}/assign/pendents", response_model=AssignacioResponse)
def assignar_pendents(
    data: DataISO, disponibles: bool = False, db: Session = Depends(get_db), dia: Dia = Depends(dia_de_la_peticio)
):
    """
    Assigna les vigilàncies pendents.

    Args:
        disponibles: Si True, inclou professors disponibles (guàrdia, etc.)
                     Si False, només alliberats
    """
    return services.assigna_pendents(db, dia, data, disponibles=disponibles)


@router.post("/{data}/clear")
def netejar_assignacions(data: DataISO, db: Session = Depends(get_db)):
    """Treu tots els vigilants del dia (es queden tipus, grups i aules)."""
    cleared_count = services.buida_vigilants(db, data)
    return {
        "success": True,
        "cleared_count": cleared_count,
        "message": f"✅ S'han netejat {cleared_count} assignacions",
    }


@router.post("/{data}/sort")
def ordenar_per_hora(data: DataISO, db: Session = Depends(get_db)):
    """Desa l'ordre automàtic del dia (dins de cada hora: nivell, grup, aula).
    404 si el dia no té vigilàncies."""
    sorted_count = services.ordena(db, data)
    return {"success": True, "sorted_count": sorted_count, "message": "✅ Vigilàncies ordenades per hora"}
