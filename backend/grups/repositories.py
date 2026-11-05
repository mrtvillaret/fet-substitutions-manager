"""Consultes dels grups i alliberats: el que es marca cada dia, els
alliberaments per període i els grups amagats.

Els repositoris no fan commit: el fa qui crida, un cop per operació."""

from typing import Dict, List

from sqlalchemy.orm import Session

import rellotge
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
        `des_de` i mai abans d'avui (rellotge injectable), les del dia de la
        setmana `dia_setmana` (0 = dilluns) que ja tenen alguna substitució o
        vigilància, per ordre. L'historial no es reconcilia."""
        inici = max(parse_date(des_de), rellotge.avui())
        dates = set()
        for model in (Substitucio, Vigilancia):
            for (d,) in db.query(model.data).filter(model.data >= inici).distinct():
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
        from errors_domini import MissingXmlError
        from helpers import get_horari

        try:
            horari = get_horari(data_iso=data)
        except MissingXmlError:
            return result  # sense horari no hi ha activitats ni períodes a resoldre
        from grups.alliberaments import resol_alliberats

        dia = horari.get_dia_name(parse_date(data).weekday())
        return resol_alliberats(
            result,
            horari,
            parse_date(data),
            AlliberamentsPeriodeRepository.darrers(db, data, dia),
            set(GrupsAlliberatsRepository.activitats_per_defecte(db)),
        )

    @staticmethod
    def get_entre_dates(db: Session, dates: list[str]) -> dict[str, dict[str, list[str]]]:
        """Els alliberats de les dates demanades, amb consultes per interval
        i un horari per versió de l'XML. Memòria només d'aquesta crida."""
        from errors_domini import MissingXmlError
        from grups.alliberaments import resol_alliberats
        from helpers import horaris_per_dates

        dates = sorted(set(dates))
        if not dates:
            return {}
        resultat = {d: {} for d in dates}
        files = (
            db.query(GrupAlliberat)
            .filter(
                GrupAlliberat.data >= parse_date(dates[0]),
                GrupAlliberat.data <= parse_date(dates[-1]),
            )
            .all()
        )
        for fila in files:
            d = fila.data.isoformat()
            if d in resultat:
                resultat[d].setdefault(fila.hora, []).append(fila.grups)
        canvis = (
            db.query(AlliberamentPeriode)
            .filter(AlliberamentPeriode.des_de <= parse_date(dates[-1]))
            .order_by(AlliberamentPeriode.des_de, AlliberamentPeriode.id)
            .all()
        )
        per_defecte = set(GrupsAlliberatsRepository.activitats_per_defecte(db))
        horaris = horaris_per_dates(db)
        darrers, index = {}, 0
        for data in dates:
            data_obj = parse_date(data)
            while index < len(canvis) and canvis[index].des_de <= data_obj:
                c = canvis[index]
                darrers[(c.tipus, c.clau, c.dia_setmana, c.hora)] = c
                index += 1
            try:
                horari = horaris(data)
            except MissingXmlError:
                continue  # com la lectura d'un dia: només les marques manuals
            resultat[data] = resol_alliberats(resultat[data], horari, data_obj, darrers, per_defecte)
        return resultat

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
    def files_del_dia(db: Session, data: str) -> List[GrupAlliberat]:
        """Els grups marcats aquell dia (sense els dels períodes)."""
        return db.query(GrupAlliberat).filter(GrupAlliberat.data == parse_date(data)).all()

    @staticmethod
    def esborra_del_dia(db: Session, data: str) -> None:
        db.query(GrupAlliberat).filter(GrupAlliberat.data == parse_date(data)).delete(synchronize_session=False)

    @staticmethod
    def afegeix(db: Session, data: str, hora: str, grup: str) -> None:
        db.add(GrupAlliberat(data=parse_date(data), hora=hora, grups=grup))

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


class AbreviaturaGrupRepository:
    """Repositori per gestionar abreviatures de grups"""

    @staticmethod
    def get_all(db: Session) -> List[Dict]:
        """Retorna totes les abreviatures"""
        from models import AbreviaturaGrup

        abreviatures = db.query(AbreviaturaGrup).all()

        return [{"id": a.id, "grups_originals": a.grups_originals, "abreviatura": a.abreviatura} for a in abreviatures]

    @staticmethod
    def id_per_grups(db: Session, grups_originals: str):
        """L'id de l'abreviatura d'aquests grups, o None."""
        from models import AbreviaturaGrup

        fila = db.query(AbreviaturaGrup.id).filter(AbreviaturaGrup.grups_originals == grups_originals).first()
        return fila[0] if fila else None

    @staticmethod
    def id_per_abreviatura(db: Session, abreviatura: str):
        """L'id de l'abreviatura amb aquest text, o None."""
        from models import AbreviaturaGrup

        fila = db.query(AbreviaturaGrup.id).filter(AbreviaturaGrup.abreviatura == abreviatura).first()
        return fila[0] if fila else None

    @staticmethod
    def create(db: Session, grups_originals: str, abreviatura: str) -> int:
        """Crea una nova abreviatura"""
        from models import AbreviaturaGrup

        nova_abrev = AbreviaturaGrup(grups_originals=grups_originals, abreviatura=abreviatura)

        db.add(nova_abrev)
        db.commit()
        db.refresh(nova_abrev)

        return nova_abrev.id

    @staticmethod
    def update(db: Session, abreviatura_id: int, grups_originals: str = None, abreviatura: str = None) -> bool:
        """Actualitza una abreviatura"""
        from models import AbreviaturaGrup

        abrev = db.query(AbreviaturaGrup).filter(AbreviaturaGrup.id == abreviatura_id).first()

        if not abrev:
            return False

        if grups_originals is not None:
            abrev.grups_originals = grups_originals
        if abreviatura is not None:
            abrev.abreviatura = abreviatura

        db.commit()
        return True

    @staticmethod
    def delete(db: Session, abreviatura_id: int) -> bool:
        """Elimina una abreviatura"""
        from models import AbreviaturaGrup

        abrev = db.query(AbreviaturaGrup).filter(AbreviaturaGrup.id == abreviatura_id).first()

        if not abrev:
            return False

        db.delete(abrev)
        db.commit()
        return True

    @staticmethod
    def delete_all(db: Session) -> int:
        """Elimina totes les abreviatures"""
        from models import AbreviaturaGrup

        count = db.query(AbreviaturaGrup).delete()
        db.commit()
        return count


# ===========================
# PROFESSORS DE BAIXA
# ===========================
