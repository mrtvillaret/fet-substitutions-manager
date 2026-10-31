"""
Rutes dels cursos acadèmics (/api/cursos): només HTTP; la lògica, a services.py.

Els cursos formen una seqüència CONTÍGUA de períodes (mateix patró que `xml_versions`):
només es defineix `data_inici`; `data_fi` la manté el sistema (= inici del curs següent
− 1 dia) i l'últim curs queda obert. Per tant tota data pertany exactament a un curs i
no cal cap flag d'"actiu": el curs es resol per la data on es treballa.

Llegir-los, qualsevol usuari; crear-los, editar-los i esborrar-los, només admins.
"""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user, require_admin
from cursos import services
from cursos.schemas import AvisXmlCursResponse, CursEsborratResponse, CursInput, CursResponse
from dependencies import get_db

router = APIRouter(prefix="/api/cursos", tags=["cursos"])


@router.get("", response_model=List[CursResponse], response_model_exclude_unset=True)
def llistar_cursos(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Llista de cursos (més recent primer), amb la data_fi ja derivada."""
    return services.llista(db)


@router.get("/validacio-xml", response_model=List[AvisXmlCursResponse], response_model_exclude_unset=True)
def validacio_xml(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Cursos que arrencarien amb l'horari d'un curs anterior.

    Un curs hauria de començar amb un XML que entra en vigor el mateix dia. Si l'XML
    vigent a la seva data d'inici va començar abans, el curs hereta l'horari de l'any
    anterior — típicament perquè encara no s'ha pujat el nou.

    Només es revisen el curs vigent i els futurs (els passats ja no són accionables).
    """
    return services.avisos_xml(db)


@router.post("", response_model=CursResponse, response_model_exclude_unset=True)
def crear_curs(payload: CursInput, db: Session = Depends(get_db), current_user=Depends(require_admin)):
    return services.crea(db, payload.nom, payload.data_inici)


@router.put("/{curs_id}", response_model=CursResponse, response_model_exclude_unset=True)
def editar_curs(curs_id: int, payload: CursInput, db: Session = Depends(get_db), current_user=Depends(require_admin)):
    return services.edita(db, curs_id, payload.nom, payload.data_inici)


@router.delete("/{curs_id}", response_model=CursEsborratResponse, response_model_exclude_unset=True)
def eliminar_curs(curs_id: int, db: Session = Depends(get_db), current_user=Depends(require_admin)):
    """Elimina només la metadada del curs; no toca substitucions ni vigilàncies."""
    services.esborra(db, curs_id)
    return {"success": True, "message": "Curs eliminat"}
