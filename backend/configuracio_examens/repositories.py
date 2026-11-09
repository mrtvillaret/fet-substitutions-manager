"""Consultes de la configuració d'exàmens: la configuració mestra (nivells,
assignatures, grups i aules), les assignacions de titulars i les propostes
d'importació descartades.

Cap operació no fa commit: el servei tanca la transacció sencera."""

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from models import AbreviaturaGrup, Assignatura, Aula, ConfiguracioExamen, Grup, Nivell, PropostaDescartada


class MasterConfigRepository:
    """Operacions per master config (nivells, assignatures, grups, aules)"""

    @staticmethod
    def codis_de_grups(db: Session) -> set:
        """Els codis de tots els grups de la configuració."""
        return {codi for (codi,) in db.query(Grup.codi).all()}

    @staticmethod
    def nivell_per_grup(db: Session) -> dict[str, str]:
        """{grup: codi del seu nivell}."""
        return dict(db.query(Grup.codi, Nivell.codi).join(Nivell, Grup.nivell_id == Nivell.id))

    @staticmethod
    def esborra_tot(db: Session) -> None:
        """Grups, assignatures, aules i nivells (sense commit)."""
        db.query(Grup).delete()
        db.query(Assignatura).delete()
        db.query(Aula).delete()
        db.query(Nivell).delete()

    @staticmethod
    def get_master_config(db: Session) -> dict[str, Any]:
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
    def get_nivells(db: Session) -> list[str]:
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
        db.flush()  # el commit, qui crida (una importació és tot o res)
        return True

    @staticmethod
    def delete_nivell(db: Session, codi: str) -> bool:
        """Elimina un nivell (i totes les seves assignatures i grups per CASCADE)"""
        nivell = db.query(Nivell).filter(Nivell.codi == codi).first()
        if not nivell:
            return False

        db.delete(nivell)
        db.flush()  # el commit, qui crida (amb les assignacions, si cal)
        return True

    @staticmethod
    def get_assignatures_per_nivell(db: Session, nivell_codi: str) -> list[str]:
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
        db.flush()  # el commit, qui crida (una importació és tot o res)
        return True

    @staticmethod
    def rename_assignatura(db: Session, nivell_codi: str, nom_antic: str, nou_nom: str) -> bool:
        """Reanomena una assignatura i propaga el canvi a les assignacions d'exàmens
        dels grups del seu nivell"""

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

        # 2. Propagar a les assignacions d'exàmens d'aquest nivell: les dels seus
        # grups segons la configuració d'exàmens (no l'XML). Una assignatura amb
        # el mateix nom pot ser a diversos nivells i és una altra.
        grups_del_nivell = [codi for (codi,) in db.query(Grup.codi).filter(Grup.nivell_id == nivell.id)]
        db.query(ConfiguracioExamen).filter(
            ConfiguracioExamen.assignatura == nom_antic, ConfiguracioExamen.grup.in_(grups_del_nivell)
        ).update({"assignatura": nou_nom}, synchronize_session=False)

        db.flush()
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
        db.flush()
        return True

    @staticmethod
    def get_grups_per_nivell(db: Session, nivell_codi: str) -> list[str]:
        """Retorna grups d'un nivell ordenats"""
        nivell = db.query(Nivell).filter(Nivell.codi == nivell_codi).first()
        if not nivell:
            return []

        grups = db.query(Grup).filter(Grup.nivell_id == nivell.id).order_by(Grup.ordre).all()

        return [g.codi for g in grups]

    @staticmethod
    def grups_actius_del_nivell(db: Session, nivell_codi: str) -> list[str]:
        nivell = db.query(Nivell).filter(Nivell.codi == nivell_codi).first()
        if not nivell:
            return []
        return [g.codi for g in db.query(Grup).filter(Grup.nivell_id == nivell.id, Grup.actiu.is_(True)).all()]

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
        db.flush()  # el commit, qui crida (una importació és tot o res)
        return True

    @staticmethod
    def rename_grup(db: Session, codi_antic: str, nou_codi: str) -> bool:
        """Reanomena un grup i propaga el canvi a les assignacions d'exàmens"""

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

        db.flush()
        return True

    @staticmethod
    def delete_grup(db: Session, codi: str) -> bool:
        """Elimina un grup"""
        grup = db.query(Grup).filter(Grup.codi == codi).first()
        if not grup:
            return False

        db.delete(grup)
        db.flush()  # el commit, qui crida (amb les assignacions, si cal)
        return True

    @staticmethod
    def get_aules(db: Session) -> list[str]:
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
        db.flush()  # el commit, qui crida (una importació és tot o res)
        return True

    @staticmethod
    def rename_aula(db: Session, codi_antic: str, nou_codi: str) -> bool:
        """Reanomena una aula i propaga el canvi a les assignacions d'exàmens"""

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

        db.flush()
        return True

    @staticmethod
    def delete_aula(db: Session, codi: str) -> bool:
        """Elimina una aula"""
        aula = db.query(Aula).filter(Aula.codi == codi).first()
        if not aula:
            return False

        db.delete(aula)
        db.flush()
        return True


# ===========================
# CONFIGURACIÓ EXÀMENS - ASSIGNACIONS
# ===========================


class ConfiguracioExamenRepository:
    """Repositori per gestionar assignacions professor-titular per exàmens"""

    @staticmethod
    def existeix(db: Session, assignatura: str, grup: str, titular) -> bool:
        """Si ja hi ha una assignació amb aquesta assignatura, grup i titular."""

        return (
            db.query(ConfiguracioExamen).filter_by(assignatura=assignatura, grup=grup, titular=titular).first()
            is not None
        )

    @staticmethod
    def compta(db: Session, grups=None, aula: str = None) -> int:
        """Quantes assignacions tenen un d'aquests grups o aquesta aula."""

        q = db.query(ConfiguracioExamen)
        if grups is not None:
            q = q.filter(ConfiguracioExamen.grup.in_(list(grups)))
        if aula is not None:
            q = q.filter(ConfiguracioExamen.aula == aula)
        return q.count()

    @staticmethod
    def delete_per_grups(db: Session, grups) -> int:
        """Esborra les d'aquests grups (sense commit); quantes."""

        return (
            db.query(ConfiguracioExamen)
            .filter(ConfiguracioExamen.grup.in_(list(grups)))
            .delete(synchronize_session=False)
        )

    @staticmethod
    def delete_ids(db: Session, ids) -> int:
        """Esborra les d'aquests ids (sense commit); quantes."""

        return db.query(ConfiguracioExamen).filter(ConfiguracioExamen.id.in_(ids)).delete(synchronize_session=False)

    @staticmethod
    def delete_all(db: Session) -> int:
        """Les esborra totes (sense commit); quantes."""

        return db.query(ConfiguracioExamen).delete()

    @staticmethod
    def get_all(db: Session) -> list[dict]:
        """Retorna totes les assignacions"""

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
    def get_all_as_dict(db: Session) -> dict[str, Any]:
        """Retorna assignacions en format compatible amb el core de vigilàncies."""

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
    def create(db: Session, assignatura: str, grup: str, titular: str = None, aula: str = None, ordre: int = 0) -> int:
        """Crea una nova assignació"""

        nova_assignacio = ConfiguracioExamen(
            assignatura=assignatura,
            grup=grup,
            titular=titular if titular else None,
            aula=aula if aula else None,
            ordre=ordre,
        )

        db.add(nova_assignacio)
        db.flush()  # el commit, qui crida (una importació és tot o res)
        db.refresh(nova_assignacio)

        return nova_assignacio.id

    @staticmethod
    def update(db: Session, assignacio_id: int, titular: str = None, aula: str = None) -> bool:
        """Actualitza una assignació"""

        assignacio = db.query(ConfiguracioExamen).filter(ConfiguracioExamen.id == assignacio_id).first()

        if not assignacio:
            return False

        if titular is not None:
            assignacio.titular = titular if titular else None
        if aula is not None:
            assignacio.aula = aula if aula else None

        db.flush()
        return True

    @staticmethod
    def delete(db: Session, assignacio_id: int) -> bool:
        """Elimina una assignació"""

        assignacio = db.query(ConfiguracioExamen).filter(ConfiguracioExamen.id == assignacio_id).first()

        if not assignacio:
            return False

        db.delete(assignacio)
        db.flush()
        return True


# ===========================
# PROPOSTES DESCARTADES (importació)
# ===========================


class PropostaDescartadaRepository:
    """Recorda quines propostes d'importació s'han desmarcat expressament."""

    @staticmethod
    def get_totes(db: Session) -> set:
        """Retorna el conjunt de (assignatura, grup, titular) descartats."""

        return {(p.assignatura, p.grup, p.titular) for p in db.query(PropostaDescartada).all()}

    @staticmethod
    def marca(db: Session, assignatura: str, grup: str, titular) -> None:
        """Marca una proposta com a descartada (idempotent)."""

        existent = db.query(PropostaDescartada).filter_by(assignatura=assignatura, grup=grup, titular=titular).first()
        if not existent:
            db.add(PropostaDescartada(assignatura=assignatura, grup=grup, titular=titular))

    @staticmethod
    def elimina(db: Session, assignatura: str, grup: str, titular) -> None:
        """Treu una proposta de la llista de descartades (p.ex. si l'usuari la torna a marcar)."""

        db.query(PropostaDescartada).filter_by(assignatura=assignatura, grup=grup, titular=titular).delete()

    @staticmethod
    def elimina_totes(db: Session) -> None:
        """Buida tota la llista de descartades (p.ex. amb l'opció 'Sobreescriu')."""

        db.query(PropostaDescartada).delete()
