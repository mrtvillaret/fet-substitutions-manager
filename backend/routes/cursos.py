"""
Routes per cursos acadèmics.

Els cursos formen una seqüència CONTÍGUA de períodes (mateix patró que `xml_versions`):
només es defineix `data_inici`; `data_fi` la manté el sistema (= inici del curs següent
− 1 dia) i l'últim curs queda obert. Per tant tota data pertany exactament a un curs i
no cal cap flag d'"actiu": el curs es resol per la data on es treballa.

Cap dada de substitucions o vigilàncies es toca en crear, editar o eliminar un curs.
"""
from datetime import date

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from dependencies import get_db
from auth_utils import require_admin, get_current_user
from repositories import CursRepository

router = APIRouter(prefix="/api/cursos", tags=["cursos"])


class CursInput(BaseModel):
    nom: str
    data_inici: date


def _serialize(c) -> dict:
    return {
        "id": c.id,
        "nom": c.nom,
        "data_inici": c.data_inici.isoformat() if c.data_inici else None,
        # derivada pel sistema; None = últim curs (obert)
        "data_fi": c.data_fi.isoformat() if c.data_fi else None,
    }


@router.get("")
async def llistar_cursos(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Llista de cursos (més recent primer), amb la data_fi ja derivada."""
    return [_serialize(c) for c in CursRepository.list_all(db)]


@router.get("/validacio-xml")
async def validacio_xml(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Cursos que arrencarien amb l'horari d'un curs anterior.

    Un curs hauria de començar amb un XML que entra en vigor el mateix dia. Si l'XML
    vigent a la seva data d'inici va començar abans, el curs hereta l'horari de l'any
    anterior — típicament perquè encara no s'ha pujat el nou.

    Només es revisen el curs vigent i els futurs (els passats ja no són accionables).
    """
    from repositories import XMLVersionRepository

    cursos = CursRepository.list_all(db)
    if not cursos:
        return []

    avui = date.today()
    primer_inici = min(c.data_inici for c in cursos)
    avisos = []

    for c in cursos:
        if c.data_fi is not None and c.data_fi < avui:
            continue                       # curs ja tancat: no accionable
        if c.data_inici == primer_inici:
            continue                       # el primer curs no té cap anterior
        versio = XMLVersionRepository.get_for_date(db, c.data_inici.isoformat())
        if not versio:
            continue                       # sense historial d'XML per aquella data
        if versio.data_inici < c.data_inici:
            avisos.append({
                "curs_id": c.id,
                "curs_nom": c.nom,
                "curs_inici": c.data_inici.isoformat(),
                "xml_inici": versio.data_inici.isoformat(),
                "xml_path": versio.path,
            })

    return avisos


@router.get("/per-data/{data}")
async def curs_per_data(data: str, db: Session = Depends(get_db),
                        current_user=Depends(get_current_user)):
    """Curs al qual pertany una data (None si és anterior al primer curs definit)."""
    try:
        date.fromisoformat(data)
    except ValueError:
        raise HTTPException(status_code=400, detail="Format de data invàlid. Usa YYYY-MM-DD")
    c = CursRepository.get_for_date(db, data)
    return _serialize(c) if c else None


@router.post("")
async def crear_curs(payload: CursInput, db: Session = Depends(get_db),
                     current_user=Depends(require_admin)):
    c = CursRepository.create(db, payload.nom, payload.data_inici)
    return _serialize(c)


@router.put("/{curs_id}")
async def editar_curs(curs_id: int, payload: CursInput, db: Session = Depends(get_db),
                      current_user=Depends(require_admin)):
    c = CursRepository.update(db, curs_id, payload.nom, payload.data_inici)
    if not c:
        raise HTTPException(status_code=404, detail="Curs no trobat")
    return _serialize(c)


@router.delete("/{curs_id}")
async def eliminar_curs(curs_id: int, db: Session = Depends(get_db),
                        current_user=Depends(require_admin)):
    """Elimina només la metadada del curs; no toca substitucions ni vigilàncies."""
    ok = CursRepository.delete(db, curs_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Curs no trobat")
    return {"success": True, "message": "Curs eliminat"}
