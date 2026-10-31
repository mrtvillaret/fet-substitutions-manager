"""
Rutes del mòdul de grups: només HTTP; la lògica, a services.py.

`router` (/api/grups, per a qualsevol usuari: la gestió de cada dia):
- GET /{data}: el que s'ha marcat aquell dia, el que ve d'alliberaments per període,
  i les dades per mostrar la taula
- PUT /{data}: desar el que es marca aquell dia
- /periode: canvis d'estat que duren fins al canvi següent (cada setmana)

`router_admin` (configuració, només admins; les URL de sempre):
- /api/grups-amagats: els grups que el centre amaga
- /api/prioritats/activitats-alliberables: les activitats sense grup que es
  poden alliberar
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from dependencies import dia_de_la_peticio, dia_del_calendari, get_db
from grups import services
from grups.schemas import (
    ActivitatsAlliberables,
    ActivitatsAlliberablesDesadesResponse,
    ActivitatsAlliberablesResponse,
    AlliberatsDia,
    CanviPeriode,
    CanviPeriodeResponse,
    DiaDesatResponse,
    DiaResponse,
    GrupsAmagatsDesatsResponse,
    GrupsAmagatsRequest,
    GrupsAmagatsResponse,
    ReforcResponse,
)
from noms import NomNet
from parametres import DataISO
from serveis.dia import Dia

router = APIRouter(prefix="/api/grups", tags=["Grups Sense Classe"])
router_admin = APIRouter()


# ===== Alliberaments per període (definides abans de /{data}) =====


@router.post("/periode", response_model=CanviPeriodeResponse, response_model_exclude_unset=True)
def afegeix_canvi_periode(canvi: CanviPeriode, db: Session = Depends(get_db)):
    """A partir de `data`, cada setmana el mateix dia, a les `hores` indicades,
    el professor queda alliberat (o deixa de ser-ho): els reforços."""
    resultat = services.afegeix_canvi_periode(
        db, canvi.tipus, canvi.clau, canvi.hores, canvi.data, canvi.alliberat, canvi.dia_setmana
    )
    return {"success": True, **resultat}


@router.get("/reforcos/{activitat}", response_model=ReforcResponse)
def franges_activitat_per_defecte(
    activitat: NomNet, data: DataISO, db: Session = Depends(get_db), dia_peticio: Dia = Depends(dia_de_la_peticio)
):
    """Per a una activitat «alliberada fins que tingui alumnes» (p.ex. Reforç):
    les franges de la setmana de cada professor que la fa, i si en aquella data
    ja tenen alumnes."""
    return services.franges_reforc(db, dia_peticio.horari, activitat, data)


# ===== La taula d'un dia =====


@router.get("/{data}", response_model=DiaResponse)
def obtenir_grups_sense_classe(
    data: DataISO, db: Session = Depends(get_db), dia_peticio: Dia = Depends(dia_de_la_peticio)
):
    """Grups sense classe, professors i activitats alliberats d'una data, i el
    que cal per mostrar la taula (GrupsView.vue)."""
    return services.dades_del_dia(db, dia_peticio, data)


@router.put("/{data}", response_model=DiaDesatResponse, response_model_exclude_unset=True)
def desar_grups_sense_classe(data: DataISO, payload: AlliberatsDia, db: Session = Depends(get_db)):
    """Desa el que es marca aquell dia i reconcilia les substitucions (treu
    els substituts que ja no poden fer-les; no n'assigna de nous)."""
    resultat = services.desa_dia(db, data, payload.grups, payload.professors, payload.activitats, payload.ocupats)
    return {
        "success": True,
        "substituts_trets": resultat["substituts_trets"],
        "message": f"Grups sense classe actualitzats per {data}",
        "total_hores": resultat["total_hores"],
        "total_grups": resultat["total_grups"],
        "total_professors": resultat["total_professors"],
    }


# ===== Grups amagats (configuració de grups del centre) =====
#
# Llista d'EXCLUSIÓ: sense classe i la resta mostren tots els grups detectats
# excepte els amagats. Independent dels exàmens i dels nivells.


@router_admin.get("/api/grups-amagats", tags=["Grups amagats"], response_model=GrupsAmagatsResponse)
def obtenir_grups_amagats(db: Session = Depends(get_db)):
    """Retorna la llista de grups amagats."""
    return {"grups": services.grups_amagats(db)}


@router_admin.put("/api/grups-amagats", tags=["Grups amagats"], response_model=GrupsAmagatsDesatsResponse)
def desar_grups_amagats(payload: GrupsAmagatsRequest, db: Session = Depends(get_db)):
    """Desa la llista de grups amagats (reemplaça la llista sencera)."""
    return {"success": True, "total": services.desa_grups_amagats(db, payload.grups)}


# ===== Activitats alliberables (es configuren a Prioritats) =====


@router_admin.get(
    "/api/prioritats/activitats-alliberables",
    tags=["Prioritats i Professors"],
    response_model=ActivitatsAlliberablesResponse,
)
def get_activitats_alliberables(db: Session = Depends(get_db), dia_calendari: Dia = Depends(dia_del_calendari)):
    """Activitats sense grup que es poden alliberar i les que hi ha a l'horari
    vigent a `data` (o, sense, avui) per triar-les."""
    return services.configuracio_activitats_alliberables(db, dia_calendari)


@router_admin.put(
    "/api/prioritats/activitats-alliberables",
    tags=["Prioritats i Professors"],
    response_model=ActivitatsAlliberablesDesadesResponse,
)
def set_activitats_alliberables(dades: ActivitatsAlliberables, db: Session = Depends(get_db)):
    return {"success": True, **services.desa_activitats_alliberables(db, dades.activitats, dades.per_defecte)}
