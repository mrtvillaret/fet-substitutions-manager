"""Consultes de les versions de l'XML i del professorat històric de cada centre.

Els repositoris no fan commit: el fa qui crida, un cop per operació."""

from datetime import date, timedelta

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

import rellotge
from dates import parse_date
from models import Configuracio, Professor, XMLVersion


class XMLVersionRepository:
    """Gestió d'històric d'XMLs per data"""

    @staticmethod
    def list_all(db: Session) -> list[XMLVersion]:
        return db.query(XMLVersion).order_by(XMLVersion.data_inici).all()

    @staticmethod
    def get(db: Session, version_id: int) -> XMLVersion | None:
        return db.query(XMLVersion).filter(XMLVersion.id == version_id).first()

    @staticmethod
    def comenca_el(db: Session, data_inici: date, excepte: int = None) -> bool:
        """Si alguna versió (que no sigui `excepte`) comença aquest dia."""
        q = db.query(XMLVersion).filter(XMLVersion.data_inici == data_inici)
        if excepte is not None:
            q = q.filter(XMLVersion.id != excepte)
        return q.first() is not None

    @staticmethod
    def fa_servir(db: Session, path: str) -> bool:
        """Si alguna versió apunta a aquest fitxer."""
        return db.query(XMLVersion).filter(XMLVersion.path == path).first() is not None

    @staticmethod
    def delete(db: Session, versio: XMLVersion) -> None:
        """L'esborra (cal encadena() després; el commit, qui crida)."""
        db.delete(versio)

    @staticmethod
    def get_current(db: Session) -> XMLVersion | None:
        return db.query(XMLVersion).filter(XMLVersion.data_fi.is_(None)).order_by(XMLVersion.data_inici.desc()).first()

    @staticmethod
    def vigent(db: Session, data: str = None) -> XMLVersion | None:
        """La versió vigent a `data` (per defecte avui). Si aquell dia no en
        cobreix cap: la primera que comenci després (p. ex. només s'ha pujat
        l'horari d'un curs que encara no ha començat) o, si no, la darrera."""
        data = data or rellotge.avui().isoformat()
        versio = XMLVersionRepository.get_for_date(db, data)
        if versio:
            return versio
        data_obj = parse_date(data)
        return (
            db.query(XMLVersion).filter(XMLVersion.data_inici > data_obj).order_by(XMLVersion.data_inici).first()
            or db.query(XMLVersion).order_by(XMLVersion.data_inici.desc()).first()
        )

    @staticmethod
    def get_for_date(db: Session, data: str) -> XMLVersion | None:
        data_obj = parse_date(data)
        return (
            db.query(XMLVersion)
            .filter(
                and_(
                    XMLVersion.data_inici <= data_obj, or_(XMLVersion.data_fi.is_(None), XMLVersion.data_fi >= data_obj)
                )
            )
            .order_by(XMLVersion.data_inici.desc())
            .first()
        )

    @staticmethod
    def create(db: Session, path: str, data_inici: date, hash_contingut: str = None) -> XMLVersion:
        """Una versió nova (la data de fi la posa encadena(); el commit, qui crida)."""
        nova = XMLVersion(path=path, data_inici=data_inici, hash_contingut=hash_contingut)
        db.add(nova)
        db.flush()
        db.refresh(nova)
        return nova

    @staticmethod
    def encadena(db: Session) -> None:
        """Recalcula la data de fi de totes les versions (el dia abans que
        comenci la següent; l'última, oberta), com els cursos: només es tria
        quan comença cada versió, i així no hi pot haver forats ni solapaments.
        També posa el punter xml_horari_path a la versió vigent avui. No fa
        commit: va amb el canvi que l'ha fet necessari."""
        db.flush()  # els canvis pendents (p. ex. una versió esborrada) primer
        versions = db.query(XMLVersion).order_by(XMLVersion.data_inici.asc()).all()
        for i, versio in enumerate(versions):
            seguent = versions[i + 1] if i + 1 < len(versions) else None
            nova_fi = (seguent.data_inici - timedelta(days=1)) if seguent else None
            if versio.data_fi != nova_fi:
                versio.data_fi = nova_fi
        db.flush()
        vigent = XMLVersionRepository.vigent(db)
        punter = db.query(Configuracio).filter(Configuracio.clau == "xml_horari_path").first()
        valor = vigent.path if vigent else ""
        if punter:
            punter.valor = valor
        elif valor:
            db.add(
                Configuracio(
                    clau="xml_horari_path", valor=valor, tipus="string", descripcio="Path del fitxer XML de FET"
                )
            )


class ProfessorRepository:
    """Repositori per gestionar professors històrics"""

    @staticmethod
    def existeix(db: Session, nom: str) -> bool:

        return db.query(Professor).filter_by(nom=nom).first() is not None

    @staticmethod
    def sync_from_xml(db: Session, professors_xml: list[str], data_sync=None) -> dict[str, int]:
        """Sincronitza professors amb l'XML (actiu/inactiu)"""

        data_avui = data_sync or rellotge.avui()
        professors_noms = {nom.strip() for nom in professors_xml if nom and nom.strip()}

        existing = {p.nom: p for p in db.query(Professor).all()}

        nous = 0
        reactivats = 0
        desactivats = 0

        # Afegir o reactivar professors presents a l'XML
        for nom in professors_noms:
            prof = existing.get(nom)
            if prof:
                if not prof.actiu:
                    prof.actiu = True
                    reactivats += 1
                if not prof.primera_aparicio:
                    prof.primera_aparicio = data_avui
                prof.ultima_aparicio = data_avui
            else:
                db.add(Professor(nom=nom, actiu=True, primera_aparicio=data_avui, ultima_aparicio=data_avui))
                nous += 1

        # Marcar inactius els que ja no hi són
        for nom, prof in existing.items():
            if nom not in professors_noms and prof.actiu:
                prof.actiu = False
                prof.ultima_aparicio = data_avui
                desactivats += 1

        return {"nous": nous, "reactivats": reactivats, "desactivats": desactivats, "total_xml": len(professors_noms)}
