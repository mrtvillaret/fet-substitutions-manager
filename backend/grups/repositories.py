"""Consultes dels grups i alliberats: el que es marca cada dia, els
alliberaments per període i els grups amagats.

Els repositoris no fan commit: el fa qui crida, un cop per operació."""

from typing import Dict, List

from sqlalchemy.orm import Session

from models import AlliberamentPeriode, GrupAlliberat, Substitucio, Vigilancia
from repositories import ConfiguracioRepository, parse_date


class AlliberamentsPeriodeRepository:
    """Canvis d'estat d'alliberaments que duren fins al canvi següent. Només
    de professors (els reforços): cap canvi per període als grups ni a les
    activitats (decidit el 9/10/2026)."""

    TIPUS = ("professor",)

    @staticmethod
    def darrers(db: Session, data: str, dia_setmana: str = None) -> Dict[tuple, AlliberamentPeriode]:
        """{(tipus, clau, dia_setmana, hora): darrer canvi fet fins a `data`}
        (d'un dia de la setmana, si s'indica). La taula sempre hi és: es crea
        en obrir la BD (database.create_data_tables)."""
        q = db.query(AlliberamentPeriode).filter(AlliberamentPeriode.des_de <= parse_date(data))
        if dia_setmana:
            q = q.filter(AlliberamentPeriode.dia_setmana == dia_setmana)
        canvis = q.order_by(AlliberamentPeriode.des_de, AlliberamentPeriode.id).all()
        darrer = {}
        for c in canvis:
            darrer[(c.tipus, c.clau, c.dia_setmana, c.hora)] = c
        return darrer

    @staticmethod
    def estats(db: Session, data: str, dia_setmana: str) -> Dict[str, List[Dict]]:
        """{hora: [{tipus, clau, des_de}]} del que està alliberat per període
        en una data (que és un `dia_setmana`)."""
        darrer = {
            (t, c, h): canvi
            for (t, c, _d, h), canvi in AlliberamentsPeriodeRepository.darrers(db, data, dia_setmana).items()
        }
        result = {}
        for (tipus, clau, hora), c in darrer.items():
            if c.alliberat:
                result.setdefault(hora, []).append({"tipus": tipus, "clau": clau, "des_de": c.des_de.isoformat()})
        return result

    @staticmethod
    def canvis(db: Session, tipus: str = None, clau: str = None) -> List[Dict]:
        q = db.query(AlliberamentPeriode)
        if tipus:
            q = q.filter(AlliberamentPeriode.tipus == tipus)
        if clau:
            q = q.filter(AlliberamentPeriode.clau == clau)
        return [
            {
                "id": c.id,
                "tipus": c.tipus,
                "clau": c.clau,
                "dia_setmana": c.dia_setmana,
                "hora": c.hora,
                "des_de": c.des_de.isoformat(),
                "alliberat": bool(c.alliberat),
            }
            for c in q.order_by(AlliberamentPeriode.des_de, AlliberamentPeriode.id).all()
        ]

    @staticmethod
    def afegeix(
        db: Session, tipus: str, clau: str, dia_setmana: str, hores: List[str], des_de: str, alliberat: bool
    ) -> None:
        # Un sol canvi per (qui, dia, hora, data): el nou substitueix el que hi hagués
        for hora in hores:
            db.query(AlliberamentPeriode).filter(
                AlliberamentPeriode.tipus == tipus,
                AlliberamentPeriode.clau == clau,
                AlliberamentPeriode.dia_setmana == dia_setmana,
                AlliberamentPeriode.hora == hora,
                AlliberamentPeriode.des_de == parse_date(des_de),
            ).delete()
            db.add(
                AlliberamentPeriode(
                    tipus=tipus,
                    clau=clau,
                    dia_setmana=dia_setmana,
                    hora=hora,
                    des_de=parse_date(des_de),
                    alliberat=alliberat,
                )
            )
        db.flush()

    @staticmethod
    def dates_afectades(db: Session, des_de: str, dia_setmana: int) -> List[str]:
        """Les dates que un canvi per període pot afectar: a partir de
        `des_de`, les del dia de la setmana `dia_setmana` (0 = dilluns) que ja
        tenen alguna substitució o vigilància, per ordre."""
        dates = set()
        for model in (Substitucio, Vigilancia):
            for (d,) in db.query(model.data).filter(model.data >= parse_date(des_de)).distinct():
                if d.weekday() == dia_setmana:
                    dates.add(d.isoformat())
        return sorted(dates)


class GrupsAlliberatsRepository:
    """Operacions per grups alliberats"""

    @staticmethod
    def get_by_date(db: Session, data: str) -> Dict[str, List[str]]:
        """Alliberats efectius per hora en una data: els marcats aquell dia més
        els que vénen d'un alliberament per període; les activitats alliberades
        es resolen als professors que les fan (perquè compti com qualsevol
        professor alliberat)."""
        result = GrupsAlliberatsRepository.get_dia_by_date(db, data)
        from core.alliberats import (
            activitats_de,
            clau_ocupat,
            clau_professor,
            ocupats_de,
        )
        from helpers import MissingXmlError, get_horari

        try:
            horari = get_horari(data_iso=data)
        except MissingXmlError:
            return result  # sense horari no hi ha activitats ni períodes a resoldre
        dia = horari.get_dia_name(parse_date(data).weekday())

        for hora, items in AlliberamentsPeriodeRepository.estats(db, data, dia).items():
            for item in items:
                clau = clau_professor(item["clau"])  # només n'hi ha de professors
                if clau not in result.setdefault(hora, []):
                    result[hora].append(clau)

        for hora, valors in result.items():
            activitats = set(activitats_de(valors))
            if not activitats:
                continue
            for professor in horari.professors:
                act = horari.get_activitat(dia, hora, professor) or {}
                if (act.get("assignatura") or "") in activitats:
                    clau = clau_professor(professor)
                    if clau not in valors:
                        valors.append(clau)

        # Activitats «alliberades fins que tinguin alumnes» (p.ex. Reforç): qui
        # les fa està alliberat, tret de les franges marcades amb alumnes
        per_defecte = set(GrupsAlliberatsRepository.activitats_per_defecte(db))
        if per_defecte:
            darrers = AlliberamentsPeriodeRepository.darrers(db, data, dia)
            for hora in horari.hores:
                for professor in horari.professors:
                    act = horari.get_activitat(dia, hora, professor) or {}
                    if act.get("grup") or (act.get("assignatura") or "") not in per_defecte:
                        continue
                    canvi = darrers.get(("professor", professor, dia, hora))
                    if canvi is not None and not canvi.alliberat:
                        continue  # ja té alumnes
                    if clau_ocupat(professor) in result.get(hora, []):
                        continue  # aquell dia sí que té alumnes
                    clau = clau_professor(professor)
                    if clau not in result.setdefault(hora, []):
                        result[hora].append(clau)

        # Un professor marcat «ocupat» aquell dia no està alliberat, vingui d'on
        # vingui l'alliberament (per defecte o per un canvi d'estat)
        for valors in result.values():
            for professor in ocupats_de(valors):
                clau = clau_professor(professor)
                while clau in valors:
                    valors.remove(clau)
        return result

    @staticmethod
    def activitats_per_defecte(db: Session) -> List[str]:
        """Activitats alliberables que estan alliberades fins que tenen alumnes."""
        import json

        try:
            return [
                a for a in json.loads(ConfiguracioRepository.get(db, "activitats_alliberades_per_defecte") or "[]") if a
            ]
        except (ValueError, TypeError):
            return []

    @staticmethod
    def get_dia_by_date(db: Session, data: str) -> Dict[str, List[str]]:
        """Només el que s'ha marcat aquell dia (sense els alliberaments per període)"""
        grups = db.query(GrupAlliberat).filter(GrupAlliberat.data == parse_date(data)).all()

        result = {}
        for g in grups:
            if g.hora not in result:
                result[g.hora] = []
            result[g.hora].append(g.grups)

        return result

    @staticmethod
    def set_for_date(db: Session, data: str, grups_per_hora: Dict[str, List[str]]):
        """Estableix grups alliberats per una data (substitueix existents)"""
        # Eliminar existents
        db.query(GrupAlliberat).filter(GrupAlliberat.data == parse_date(data)).delete()

        # Afegir nous
        for hora, grups_list in grups_per_hora.items():
            for grups in grups_list:
                ga = GrupAlliberat(data=parse_date(data), hora=hora, grups=grups)
                db.add(ga)

        db.flush()


class GrupsAmagatsRepository:
    """Grups que el centre amaga (llista d'exclusió; buida = es mostren tots)."""

    @staticmethod
    def get_all(db: Session) -> List[str]:
        """Llista dels grups amagats (buida si no se n'amaga cap)."""
        from models import GrupAmagat

        return [g.grup for g in db.query(GrupAmagat).order_by(GrupAmagat.grup).all()]

    @staticmethod
    def set_all(db: Session, grups: List[str]) -> int:
        """Reemplaça la llista d'amagats sencera per la donada."""
        from models import GrupAmagat

        db.query(GrupAmagat).delete()
        vistos = set()
        for grup in grups:
            grup = (grup or "").strip()
            if grup and grup not in vistos:
                vistos.add(grup)
                db.add(GrupAmagat(grup=grup))
        db.flush()
        return len(vistos)
