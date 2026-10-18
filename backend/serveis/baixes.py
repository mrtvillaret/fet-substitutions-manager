"""
Què passa en desar una baixa: un professor de baixa ni substitueix ni és
substituït. Per a cada dia de la baixa, d'avui endavant, que ja tingui
substitucions o vigilàncies:
- s'esborren les seves absències d'aquell dia;
- es treu com a vigilant (la vigilància queda pendent);
- es treu com a substitut (la fila queda pendent).
Els dies passats no es toquen: són historial (PDF ja repartits, informes).
"""
import logging
from datetime import date, datetime

from models import Substitucio, Vigilancia
from repositories import SubstitucioRepository, VigilanciaRepository, parse_date
from serveis.absencies import desa_absencies
from serveis.cobertures import refresca_cobertures
from serveis.dia_escolar import treu_substituts_no_valids

log = logging.getLogger(__name__)


def _dies_afectats(db, data_inici: str, data_final: str, avui: date) -> list:
    try:
        inici = datetime.strptime(data_inici, "%Y-%m-%d").date()
        final = datetime.strptime(data_final, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return []
    inici = max(inici, avui)
    if inici > final:
        return []
    dates = set()
    for model in (Substitucio, Vigilancia):
        for (d,) in (db.query(model.data)
                     .filter(model.data >= parse_date(inici.isoformat()), model.data <= parse_date(final.isoformat()))
                     .distinct()):
            dates.add(d.isoformat())
    return sorted(dates)


def aplica_baixa(db, professor: str, data_inici: str, data_final: str, avui: date = None) -> dict:
    """Aplica la baixa (veure el docstring del mòdul) i retorna el que ha canviat.
    Cal cridar-la després de recarregar les baixes (config.constants)."""

    professor = (professor or "").strip()
    canvis = {"absencies_esborrades": [], "vigilancies_buidades": [], "substituts_trets": []}
    if not professor:
        return canvis

    for d in _dies_afectats(db, data_inici, data_final, avui or date.today()):
        hores_absent = sorted({s.get("hora", "") for s in SubstitucioRepository.get_by_date(db, d)
                               if s.get("professor_absent") == professor
                               and s.get("tipus_absencia") in ("ABSENCIA", "SERVEI")})
        if hores_absent:
            # El mateix que esborrar-li totes les absències des de la pantalla
            # (també treu els substituts que ja no són vàlids, com ell mateix)
            resposta = desa_absencies(db, d, professor, hores_absencia=[], hores_servei=[])
            canvis["absencies_esborrades"] += [{"data": d, "hora": h} for h in hores_absent]
            canvis["substituts_trets"] += resposta.get("substituts_trets", [])

        hores_vigilancia = set()
        for vigs in VigilanciaRepository.get_by_date(db, d).values():
            for vig in vigs:
                if (vig.get("vigilant") or "").strip() == professor:
                    VigilanciaRepository.update_by_id(db, d, str(vig["id"]), {"vigilant": ""})
                    hores_vigilancia.add(vig.get("hora", ""))
                    canvis["vigilancies_buidades"].append(
                        {"data": d, "hora": vig.get("hora", ""), "tipus": vig.get("tipus", "")})
        for hora in sorted(hores_vigilancia):
            refresca_cobertures(d, hora, db)

        canvis["substituts_trets"] += [{**fila, "data": d} for fila in treu_substituts_no_valids(db, d)]

    return canvis


def baixa_de(professor: str, data: str):
    """La baixa que té `professor` el dia `data` ({professor, data_inici,
    data_final...}), o None."""
    from config.constants import PROFESSORS_BAIXA
    from core.baixes import professors_de_baixa

    professor = (professor or "").strip()
    for baixa in PROFESSORS_BAIXA:
        if (baixa.get("professor") or "").strip() == professor and professors_de_baixa([baixa], data):
            return baixa
    return None


def missatge_de_baixa(professor: str, baixa: dict) -> str:
    return (f"{professor} està de baixa ({baixa.get('data_inici')} – {baixa.get('data_final')}): "
            "els professors de baixa no són substituïts. Si cal cobrir-li les classes, "
            "escurça o treu la baixa.")

