"""
Repositoris (DAOs) per accedir a les dades SQLite
Encapsula tota la lògica d'accés a dades
"""

import logging
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)


def parse_date(date_str: str) -> date:
    """Converteix string YYYY-MM-DD a objecte date de Python"""
    if isinstance(date_str, date):
        return date_str
    return datetime.strptime(date_str, "%Y-%m-%d").date()


# Handle both script and module import contexts
try:
    from .models import (
        AbreviaturaGrup,
        Assignatura,
        Aula,
        Configuracio,
        Grup,
        Nivell,
    )
except ImportError:
    # When running as script, add current dir to path to find local models
    sys.path.insert(0, str(Path(__file__).parent))
    from models import (
        AbreviaturaGrup,
        Assignatura,
        Aula,
        Configuracio,
        Grup,
        Nivell,
    )


class ConfiguracioRepository:
    """Operacions per configuració general"""

    @staticmethod
    def get_all_as_dict(db: Session) -> Dict[str, str]:
        """Retorna tota la configuració com a diccionari"""
        configs = db.query(Configuracio).all()
        return {c.clau: c.valor for c in configs}

    @staticmethod
    def get(db: Session, clau: str) -> Optional[str]:
        """Obté un valor de configuració"""
        config = db.query(Configuracio).filter(Configuracio.clau == clau).first()
        return config.valor if config else None

    @staticmethod
    def nom_visible_institucio(db: Session, institucio: str) -> str:
        """El nom de la institució que es mostra a la web: el configurat o, si
        no n'hi ha, l'identificador. `db` és la BD de la mateixa institució."""
        return ConfiguracioRepository.get(db, "institucio_display_name") or institucio

    @staticmethod
    def set(db: Session, clau: str, valor: str, tipus: str = "string", descripcio: str = ""):
        """Estableix un valor de configuració i en fa commit."""
        ConfiguracioRepository.desa(db, clau, valor, tipus=tipus, descripcio=descripcio)
        db.commit()

    @staticmethod
    def desa(db: Session, clau: str, valor: str, tipus: str = "string", descripcio: str = ""):
        """Com set, però sense commit: per desar diversos valors d'un cop."""
        config = db.query(Configuracio).filter(Configuracio.clau == clau).first()

        if config:
            config.valor = valor
            config.tipus = tipus
            if descripcio:
                config.descripcio = descripcio
        else:
            config = Configuracio(clau=clau, valor=valor, tipus=tipus, descripcio=descripcio)
            db.add(config)
        db.flush()


class MasterConfigRepository:
    """Operacions per master config (nivells, assignatures, grups, aules)"""

    @staticmethod
    def get_master_config(db: Session) -> Dict[str, Any]:
        """Retorna master config en format JSON compatible"""
        # Nivells amb assignatures i grups
        nivells_dict = {}
        nivells = db.query(Nivell).order_by(Nivell.ordre).all()

        for nivell in nivells:
            # Assignatures del nivell
            assignatures = (
                db.query(Assignatura).filter(Assignatura.nivell_id == nivell.id).order_by(Assignatura.ordre).all()
            )

            # Grups del nivell
            grups = db.query(Grup).filter(Grup.nivell_id == nivell.id).order_by(Grup.ordre).all()

            nivells_dict[nivell.codi] = {
                "assignatures": [a.nom for a in assignatures],
                "grups": [g.codi for g in grups],
            }

        # Aules
        aules = db.query(Aula).order_by(Aula.ordre).all()
        aules_list = [a.codi for a in aules]

        # Abreviatures
        abreviatures = db.query(AbreviaturaGrup).all()
        abreviatures_dict = {a.grups_originals: a.abreviatura for a in abreviatures}

        return {"nivells": nivells_dict, "aules": aules_list, "abreviatures": abreviatures_dict}

    # ===== NIVELLS =====

    @staticmethod
    def get_nivells(db: Session) -> List[str]:
        """Retorna tots els codis de nivells ordenats"""
        nivells = db.query(Nivell).filter(Nivell.actiu.is_(True)).order_by(Nivell.ordre).all()
        return [n.codi for n in nivells]

    @staticmethod
    def add_nivell(db: Session, codi: str, nom: str = None) -> bool:
        """Afegeix un nou nivell"""
        # Comprovar si ja existeix
        existing = db.query(Nivell).filter(Nivell.codi == codi).first()
        if existing:
            return False

        # Obtenir següent ordre
        max_ordre = db.query(Nivell).count()

        nivell = Nivell(codi=codi, nom=nom or codi, ordre=max_ordre, actiu=True)
        db.add(nivell)
        db.commit()
        return True

    @staticmethod
    def delete_nivell(db: Session, codi: str) -> bool:
        """Elimina un nivell (i totes les seves assignatures i grups per CASCADE)"""
        nivell = db.query(Nivell).filter(Nivell.codi == codi).first()
        if not nivell:
            return False

        db.delete(nivell)
        db.commit()
        return True

    @staticmethod
    def update_nivells_ordre(db: Session, nivells_ordenats: List[str]):
        """Actualitza l'ordre dels nivells"""
        for idx, nivell_codi in enumerate(nivells_ordenats):
            nivell = db.query(Nivell).filter(Nivell.codi == nivell_codi).first()
            if nivell:
                nivell.ordre = idx

        db.commit()

    @staticmethod
    def rename_nivell(db: Session, codi_antic: str, nou_codi: str) -> bool:
        """Reanomena un nivell"""
        nivell = db.query(Nivell).filter(Nivell.codi == codi_antic).first()
        if not nivell:
            return False

        # Comprovar si el nou codi ja existeix
        if codi_antic != nou_codi:
            existing = db.query(Nivell).filter(Nivell.codi == nou_codi).first()
            if existing:
                return False

        nivell.codi = nou_codi
        nivell.nom = nou_codi
        db.commit()
        return True

    # ===== ASSIGNATURES =====

    @staticmethod
    def get_assignatures_per_nivell(db: Session, nivell_codi: str) -> List[str]:
        """Retorna assignatures d'un nivell ordenades"""
        nivell = db.query(Nivell).filter(Nivell.codi == nivell_codi).first()
        if not nivell:
            return []

        assignatures = (
            db.query(Assignatura).filter(Assignatura.nivell_id == nivell.id).order_by(Assignatura.ordre).all()
        )

        return [a.nom for a in assignatures]

    @staticmethod
    def add_assignatura(db: Session, nivell_codi: str, nom: str) -> bool:
        """Afegeix una assignatura a un nivell"""
        nivell = db.query(Nivell).filter(Nivell.codi == nivell_codi).first()
        if not nivell:
            return False

        # Comprovar si ja existeix
        existing = db.query(Assignatura).filter(Assignatura.nivell_id == nivell.id, Assignatura.nom == nom).first()

        if existing:
            return False

        # Obtenir següent ordre
        max_ordre = db.query(func.max(Assignatura.ordre)).filter(Assignatura.nivell_id == nivell.id).scalar() or 0

        assignatura = Assignatura(nom=nom, nivell_id=nivell.id, ordre=max_ordre + 1)
        db.add(assignatura)
        db.commit()
        return True

    @staticmethod
    def rename_assignatura(db: Session, nivell_codi: str, nom_antic: str, nou_nom: str) -> bool:
        """Reanomena una assignatura i propaga el canvi a les assignacions d'exàmens"""
        from models import ConfiguracioExamen

        nivell = db.query(Nivell).filter(Nivell.codi == nivell_codi).first()
        if not nivell:
            return False

        assignatura = (
            db.query(Assignatura).filter(Assignatura.nivell_id == nivell.id, Assignatura.nom == nom_antic).first()
        )

        if not assignatura:
            return False

        # Comprovar si el nou nom ja existeix en aquest nivell
        if nom_antic != nou_nom:
            existing = (
                db.query(Assignatura).filter(Assignatura.nivell_id == nivell.id, Assignatura.nom == nou_nom).first()
            )
            if existing:
                return False

        # 1. Actualitzar taula mestra
        assignatura.nom = nou_nom

        # 2. Propagar a assignacions d'exàmens (NOMÉS si l'assignatura coincideix EXACTAMENT)
        # Nota: Aquí no filtrem per nivell perquè a la taula 'configuracio_examens'
        # l'assignatura es guarda com a string global. Però normalment els noms d'assignatura
        # són únics per nivell o globals.
        db.query(ConfiguracioExamen).filter(ConfiguracioExamen.assignatura == nom_antic).update(
            {"assignatura": nou_nom}
        )

        db.commit()
        return True

    @staticmethod
    def delete_assignatura(db: Session, nivell_codi: str, nom: str) -> bool:
        """Elimina una assignatura d'un nivell"""
        nivell = db.query(Nivell).filter(Nivell.codi == nivell_codi).first()
        if not nivell:
            return False

        assignatura = db.query(Assignatura).filter(Assignatura.nivell_id == nivell.id, Assignatura.nom == nom).first()

        if not assignatura:
            return False

        db.delete(assignatura)
        db.commit()
        return True

    @staticmethod
    def update_assignatures_ordre(db: Session, nivell_codi: str, assignatures_ordenades: List[str]):
        """Actualitza l'ordre de les assignatures"""
        nivell = db.query(Nivell).filter(Nivell.codi == nivell_codi).first()
        if not nivell:
            return

        for idx, nom in enumerate(assignatures_ordenades):
            assignatura = (
                db.query(Assignatura).filter(Assignatura.nivell_id == nivell.id, Assignatura.nom == nom).first()
            )
            if assignatura:
                assignatura.ordre = idx

        db.commit()

    # ===== GRUPS =====

    @staticmethod
    def get_grups_per_nivell(db: Session, nivell_codi: str) -> List[str]:
        """Retorna grups d'un nivell ordenats"""
        nivell = db.query(Nivell).filter(Nivell.codi == nivell_codi).first()
        if not nivell:
            return []

        grups = db.query(Grup).filter(Grup.nivell_id == nivell.id).order_by(Grup.ordre).all()

        return [g.codi for g in grups]

    @staticmethod
    def add_grup(db: Session, nivell_codi: str, codi: str) -> bool:
        """Afegeix un grup a un nivell"""
        nivell = db.query(Nivell).filter(Nivell.codi == nivell_codi).first()
        if not nivell:
            return False

        # Comprovar si ja existeix
        existing = db.query(Grup).filter(Grup.codi == codi).first()
        if existing:
            return False

        # Obtenir següent ordre
        max_ordre = db.query(func.max(Grup.ordre)).filter(Grup.nivell_id == nivell.id).scalar() or 0

        grup = Grup(codi=codi, nom=codi, nivell_id=nivell.id, ordre=max_ordre + 1)
        db.add(grup)
        db.commit()
        return True

    @staticmethod
    def rename_grup(db: Session, codi_antic: str, nou_codi: str) -> bool:
        """Reanomena un grup i propaga el canvi a les assignacions d'exàmens"""
        from models import ConfiguracioExamen

        grup = db.query(Grup).filter(Grup.codi == codi_antic).first()
        if not grup:
            return False

        # Comprovar si el nou codi ja existeix
        if codi_antic != nou_codi:
            existing = db.query(Grup).filter(Grup.codi == nou_codi).first()
            if existing:
                return False

        # 1. Actualitzar taula mestra
        grup.codi = nou_codi
        grup.nom = nou_codi

        # 2. Propagar a assignacions d'exàmens
        db.query(ConfiguracioExamen).filter(ConfiguracioExamen.grup == codi_antic).update({"grup": nou_codi})

        db.commit()
        return True

    @staticmethod
    def delete_grup(db: Session, codi: str) -> bool:
        """Elimina un grup"""
        grup = db.query(Grup).filter(Grup.codi == codi).first()
        if not grup:
            return False

        db.delete(grup)
        db.commit()
        return True

    @staticmethod
    def update_grups_ordre(db: Session, nivell_codi: str, grups_ordenats: List[str]):
        """Actualitza l'ordre dels grups"""
        nivell = db.query(Nivell).filter(Nivell.codi == nivell_codi).first()
        if not nivell:
            return

        for idx, codi in enumerate(grups_ordenats):
            grup = db.query(Grup).filter(Grup.codi == codi).first()
            if grup:
                grup.ordre = idx

        db.commit()

    # ===== AULES =====

    @staticmethod
    def get_aules(db: Session) -> List[str]:
        """Retorna totes les aules ordenades"""
        aules = db.query(Aula).order_by(Aula.ordre).all()
        return [a.codi for a in aules]

    @staticmethod
    def add_aula(db: Session, codi: str) -> bool:
        """Afegeix una aula"""
        # Comprovar si ja existeix
        existing = db.query(Aula).filter(Aula.codi == codi).first()
        if existing:
            return False

        # Obtenir següent ordre
        max_ordre = db.query(func.max(Aula.ordre)).scalar() or 0

        aula = Aula(codi=codi, nom=codi, ordre=max_ordre + 1)
        db.add(aula)
        db.commit()
        return True

    @staticmethod
    def rename_aula(db: Session, codi_antic: str, nou_codi: str) -> bool:
        """Reanomena una aula i propaga el canvi a les assignacions d'exàmens"""
        from models import ConfiguracioExamen

        aula = db.query(Aula).filter(Aula.codi == codi_antic).first()
        if not aula:
            return False

        # Comprovar si el nou codi ja existeix
        if codi_antic != nou_codi:
            existing = db.query(Aula).filter(Aula.codi == nou_codi).first()
            if existing:
                return False

        # 1. Actualitzar taula mestra
        aula.codi = nou_codi
        aula.nom = nou_codi

        # 2. Propagar a assignacions d'exàmens
        db.query(ConfiguracioExamen).filter(ConfiguracioExamen.aula == codi_antic).update({"aula": nou_codi})

        db.commit()
        return True

    @staticmethod
    def delete_aula(db: Session, codi: str) -> bool:
        """Elimina una aula"""
        aula = db.query(Aula).filter(Aula.codi == codi).first()
        if not aula:
            return False

        db.delete(aula)
        db.commit()
        return True


# ===========================
# CONFIGURACIÓ EXÀMENS - ASSIGNACIONS
# ===========================


class ConfiguracioExamenRepository:
    """Repositori per gestionar assignacions professor-titular per exàmens"""

    @staticmethod
    def get_all(db: Session) -> List[Dict]:
        """Retorna totes les assignacions"""
        from models import ConfiguracioExamen

        assignacions = (
            db.query(ConfiguracioExamen).order_by(ConfiguracioExamen.assignatura, ConfiguracioExamen.ordre).all()
        )

        return [
            {
                "id": a.id,
                "assignatura": a.assignatura,
                "grup": a.grup,
                "titular": a.titular or "",
                "aula": a.aula or "",
                "ordre": a.ordre,
            }
            for a in assignacions
        ]

    @staticmethod
    def get_all_as_dict(db: Session) -> Dict[str, Any]:
        """Retorna assignacions en format compatible amb el core de vigilàncies."""
        from models import ConfiguracioExamen

        assignacions = db.query(ConfiguracioExamen).all()
        result = {"assignatures": {}}

        for config in assignacions:
            assignatura = config.assignatura
            if assignatura not in result["assignatures"]:
                result["assignatures"][assignatura] = {"assignacions": []}

            result["assignatures"][assignatura]["assignacions"].append(
                {"grup": config.grup or "", "aula": config.aula or "", "titular": config.titular or ""}
            )

        return result

    @staticmethod
    def get_by_assignatura(db: Session, assignatura: str) -> List[Dict]:
        """Retorna assignacions d'una assignatura"""
        from models import ConfiguracioExamen

        assignacions = (
            db.query(ConfiguracioExamen)
            .filter(ConfiguracioExamen.assignatura == assignatura)
            .order_by(ConfiguracioExamen.ordre)
            .all()
        )

        return [
            {
                "id": a.id,
                "assignatura": a.assignatura,
                "grup": a.grup,
                "titular": a.titular or "",
                "aula": a.aula or "",
                "ordre": a.ordre,
            }
            for a in assignacions
        ]

    @staticmethod
    def create(db: Session, assignatura: str, grup: str, titular: str = None, aula: str = None, ordre: int = 0) -> int:
        """Crea una nova assignació"""
        from models import ConfiguracioExamen

        nova_assignacio = ConfiguracioExamen(
            assignatura=assignatura,
            grup=grup,
            titular=titular if titular else None,
            aula=aula if aula else None,
            ordre=ordre,
        )

        db.add(nova_assignacio)
        db.commit()
        db.refresh(nova_assignacio)

        return nova_assignacio.id

    @staticmethod
    def update(db: Session, assignacio_id: int, titular: str = None, aula: str = None) -> bool:
        """Actualitza una assignació"""
        from models import ConfiguracioExamen

        assignacio = db.query(ConfiguracioExamen).filter(ConfiguracioExamen.id == assignacio_id).first()

        if not assignacio:
            return False

        if titular is not None:
            assignacio.titular = titular if titular else None
        if aula is not None:
            assignacio.aula = aula if aula else None

        db.commit()
        return True

    @staticmethod
    def delete(db: Session, assignacio_id: int) -> bool:
        """Elimina una assignació"""
        from models import ConfiguracioExamen

        assignacio = db.query(ConfiguracioExamen).filter(ConfiguracioExamen.id == assignacio_id).first()

        if not assignacio:
            return False

        db.delete(assignacio)
        db.commit()
        return True

    @staticmethod
    def delete_all(db: Session) -> int:
        """Elimina totes les assignacions (útil per re-importar)"""
        from models import ConfiguracioExamen

        count = db.query(ConfiguracioExamen).delete()
        db.commit()
        return count


# ===========================
# PROPOSTES DESCARTADES (importació)
# ===========================


class PropostaDescartadaRepository:
    """Recorda quines propostes d'importació s'han desmarcat expressament."""

    @staticmethod
    def get_totes(db: Session) -> set:
        """Retorna el conjunt de (assignatura, grup, titular) descartats."""
        from models import PropostaDescartada

        return {(p.assignatura, p.grup, p.titular) for p in db.query(PropostaDescartada).all()}

    @staticmethod
    def marca(db: Session, assignatura: str, grup: str, titular) -> None:
        """Marca una proposta com a descartada (idempotent)."""
        from models import PropostaDescartada

        existent = db.query(PropostaDescartada).filter_by(assignatura=assignatura, grup=grup, titular=titular).first()
        if not existent:
            db.add(PropostaDescartada(assignatura=assignatura, grup=grup, titular=titular))

    @staticmethod
    def elimina(db: Session, assignatura: str, grup: str, titular) -> None:
        """Treu una proposta de la llista de descartades (p.ex. si l'usuari la torna a marcar)."""
        from models import PropostaDescartada

        db.query(PropostaDescartada).filter_by(assignatura=assignatura, grup=grup, titular=titular).delete()

    @staticmethod
    def elimina_totes(db: Session) -> None:
        """Buida tota la llista de descartades (p.ex. amb l'opció 'Sobreescriu')."""
        from models import PropostaDescartada

        db.query(PropostaDescartada).delete()


# ===========================
# ABREVIATURES GRUPS
# ===========================


class AbreviaturaGrupRepository:
    """Repositori per gestionar abreviatures de grups"""

    @staticmethod
    def get_all(db: Session) -> List[Dict]:
        """Retorna totes les abreviatures"""
        from models import AbreviaturaGrup

        abreviatures = db.query(AbreviaturaGrup).all()

        return [{"id": a.id, "grups_originals": a.grups_originals, "abreviatura": a.abreviatura} for a in abreviatures]

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


class ProfessorRepository:
    """Repositori per gestionar professors històrics"""

    @staticmethod
    def sync_from_xml(db: Session, professors_xml: List[str], data_sync=None) -> Dict[str, int]:
        """Sincronitza professors amb l'XML (actiu/inactiu)"""
        from datetime import date

        from models import Professor

        data_avui = data_sync or date.today()
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

        db.commit()
        return {"nous": nous, "reactivats": reactivats, "desactivats": desactivats, "total_xml": len(professors_noms)}
