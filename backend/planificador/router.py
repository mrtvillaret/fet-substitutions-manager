"""
Rutes del planificador d'exàmens (/api/scheduler/*, només admins): només
HTTP. La configuració, les restriccions, els costos i l'últim horari, a
services.py; generar i analitzar, a generacio.py; el cost d'un horari editat,
a cost.py; publicar-lo com a vigilàncies, a publicacio.py.

Les rutes són síncrones: FastAPI les atén en un fil a part i el backend
continua responent la resta de peticions mentre el motor treballa (segons).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user, require_admin
from dependencies import dia_d_avui, dia_de_la_planificacio, get_db
from horari.domain import Dia
from parametres import data_iso
from planificador import cost, generacio, publicacio, services
from planificador.config import horari_de_la_planificacio
from planificador.schemas import (
    AnalisiResponse,
    AssignaturesTretesResponse,
    ConfigPlanificadorRequest,
    ConfigPlanificadorResponse,
    CostosProfessorsRequest,
    CostosProfessorsResponse,
    CursDatesResponse,
    DatesResponse,
    ExitResponse,
    GeneracioResponse,
    HorariPlanificacioResponse,
    HorariRecalcularRequest,
    MotorsResponse,
    PublicacioResponse,
    RecalculResponse,
    RestriccionsResponse,
    SchedulerDatesRequest,
    SchedulerGenerateRequest,
    SchedulerPinRequest,
    SchedulerPublicarRequest,
    SchedulerRestriccionsRequest,
)

router = APIRouter(prefix="/api/scheduler", tags=["Scheduler"], dependencies=[Depends(require_admin)])


@router.get("/motors", response_model=MotorsResponse)
def scheduler_motors():
    """Retorna els motors disponibles amb paràmetres i defaults per al frontend."""
    return services.motors()


@router.get("/config", response_model=ConfigPlanificadorResponse)
def scheduler_config(db: Session = Depends(get_db)):
    return services.config(db)


@router.put("/config", response_model=ExitResponse)
def scheduler_config_update(payload: ConfigPlanificadorRequest, db: Session = Depends(get_db)):
    services.desa_config(db, payload.model_dump(exclude_unset=True))
    return {"success": True}


@router.get("/restriccions", response_model=RestriccionsResponse)
def scheduler_restriccions(db: Session = Depends(get_db)):
    return services.restriccions(db)


@router.post("/restriccions/treure-inexistents", response_model=AssignaturesTretesResponse)
def scheduler_treure_assignatures_inexistents(db: Session = Depends(get_db)):
    """Treu de les restriccions les assignatures que ja no existeixen."""
    return services.treu_assignatures_inexistents(db)


@router.put("/restriccions", response_model=ExitResponse)
def scheduler_restriccions_update(payload: SchedulerRestriccionsRequest, db: Session = Depends(get_db)):
    services.desa_restriccions(db, payload.restriccions.model_dump(exclude_unset=True))
    return {"success": True}


@router.post("/restriccions/pin", response_model=ExitResponse)
def scheduler_pin_sessions(payload: SchedulerPinRequest, db: Session = Depends(get_db)):
    """Fixa o desfixa exàmens a un dia i una hora."""
    services.fixa_examens(db, payload.pins, payload.unpins)
    return {"success": True}


@router.get("/costos-professors", response_model=CostosProfessorsResponse)
def get_costos_professors(db: Session = Depends(get_db)):
    """Els costos de professors (globals i individuals)."""
    return {"costos_professors": services.costos(db)}


@router.put("/costos-professors", response_model=ExitResponse)
def update_costos_professors(payload: CostosProfessorsRequest, db: Session = Depends(get_db)):
    """Desa els costos: {"globals": {"substitucio": 80, ...}, "individuals":
    {"Prof A": {"substitucio": 100}, ...}}."""
    services.desa_costos(db, payload.model_dump())
    return {"success": True}


@router.get("/dates", response_model=DatesResponse)
def scheduler_dates(db: Session = Depends(get_db)):
    return {"selected_dates": services.dates(db)}


@router.put("/dates", response_model=ExitResponse)
def scheduler_dates_update(payload: SchedulerDatesRequest, db: Session = Depends(get_db)):
    services.desa_dates(db, payload.selected_dates)
    return {"success": True}


@router.get("/sessions-info", response_model=list[str])
def get_scheduler_sessions_info(nivells: str = None, db: Session = Depends(get_db)):
    return services.examens_dels_nivells(db, nivells)


@router.get("/assignatures-actives", response_model=list[str])
def get_assignatures_actives(db: Session = Depends(get_db)):
    return services.examens_actius(db)


@router.get("/horari", response_model=HorariPlanificacioResponse)
def scheduler_horari(dates: str | None = None, current_user=Depends(get_current_user)):
    """Quin horari (XML) fa servir el planificador per a les dates (AAAA-MM-DD
    separades per comes; sense, les desades): la data de referència, des de
    quan és vigent i si dins les dates en comença un altre."""
    llista = [data_iso(d.strip()).isoformat() for d in (dates or "").split(",") if d.strip()]
    return horari_de_la_planificacio(current_user.institucio, llista)


@router.get("/ultim-resultat", response_model=dict | None)
def scheduler_ultim_resultat(db: Session = Depends(get_db)):
    """L'últim horari generat o editat ({desat, resultat}), o null."""
    return services.ultim_resultat(db)


@router.get("/curs-dates", response_model=CursDatesResponse)
def scheduler_curs_dates(dates: str = "", db: Session = Depends(get_db), avui: Dia = Depends(dia_d_avui)):
    """Avís si les dates (separades per comes) són d'un curs anterior."""
    return {"curs_anterior": services.cursos_anteriors(db, [d for d in dates.split(",") if d], avui.iso)}


@router.post("/generate", response_model=GeneracioResponse, response_model_exclude_unset=True)
def scheduler_generate(payload: SchedulerGenerateRequest, current_user=Depends(get_current_user)):
    return generacio.genera(payload, current_user.institucio)


@router.post("/analisi", response_model=AnalisiResponse)
def scheduler_analisi(payload: SchedulerGenerateRequest, current_user=Depends(get_current_user)):
    return generacio.analitza(payload, current_user.institucio)


@router.post("/publicar", response_model=PublicacioResponse)
def scheduler_publicar(
    payload: SchedulerPublicarRequest, current_user=Depends(get_current_user), avui: Dia = Depends(dia_d_avui)
):
    """Publica l'horari generat com a vigilàncies i grups sense classe."""
    return publicacio.publica(payload, current_user.institucio, avui.iso)


@router.post("/recalcular-cost", response_model=RecalculResponse)
def recalcular_cost(
    payload: HorariRecalcularRequest,
    current_user=Depends(get_current_user),
    planificacio: Dia = Depends(dia_de_la_planificacio),
):
    """Recalcula el cost d'un horari editat a mà, sense regenerar-lo."""
    return cost.recalcula(payload, current_user.institucio, planificacio)
