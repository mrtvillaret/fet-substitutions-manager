"""
Repositoris (DAOs) per accedir a les dades SQLite
Encapsula tota la lògica d'accés a dades
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
from pathlib import Path
import sys


def parse_date(date_str: str) -> date:
    """Converteix string YYYY-MM-DD a objecte date de Python"""
    if isinstance(date_str, date):
        return date_str
    return datetime.strptime(date_str, "%Y-%m-%d").date()

# Handle both script and module import contexts
try:
    from .models import (
        Nivell, Assignatura, Grup, Aula, AbreviaturaGrup,
        Vigilancia, Substitucio,
        GrupAlliberat, Configuracio, XMLVersion, Curs, User
    )
except ImportError:
    # When running as script, add current dir to path to find local models
    sys.path.insert(0, str(Path(__file__).parent))
    from models import (
        Nivell, Assignatura, Grup, Aula, AbreviaturaGrup,
        Vigilancia, Substitucio,
        GrupAlliberat, Configuracio, XMLVersion, Curs, User
    )


class VigilanciaRepository:
    """Operacions CRUD per vigilàncies"""

    @staticmethod
    def get_by_date(db: Session, data: str) -> Dict[str, List[Dict]]:
        """Retorna totes les vigilàncies d'una data agrupades per nivell"""
        vigilancies = db.query(Vigilancia).filter(Vigilancia.data == parse_date(data)).order_by(Vigilancia.id).all()

        # Agrupar per nivell
        result = {}
        for vig in vigilancies:
            if vig.nivell not in result:
                result[vig.nivell] = []

            result[vig.nivell].append({
                'id': str(vig.id),  # Utilitzar ID real de la base de dades
                'db_id': vig.id,    # També incloure per compatibilitat
                'hora': vig.hora,
                'tipus': vig.tipus,
                'grups': vig.grups,
                'aula': vig.aula,
                'vigilant': vig.vigilant or '',
                'comentaris': vig.comentaris or '',
                'nivell': vig.nivell,
                'updated_at': vig.updated_at.isoformat() if vig.updated_at else None
            })

        return result

    @staticmethod
    def create(db: Session, data: str, vigilancia_data: Dict) -> Vigilancia:
        """Crea una nova vigilància"""
        vig = Vigilancia(
            data=parse_date(data),
            hora=vigilancia_data['hora'],
            tipus=vigilancia_data['tipus'],
            grups=vigilancia_data['grups'],
            aula=vigilancia_data['aula'],
            vigilant=vigilancia_data.get('vigilant') or None,
            comentaris=vigilancia_data.get('comentaris', ''),
            nivell=vigilancia_data['nivell']
        )
        db.add(vig)
        db.commit()
        db.refresh(vig)
        return vig

    @staticmethod
    def update_by_id(db: Session, data: str, vig_id: str, updates: Dict) -> Optional[Vigilancia]:
        """
        Actualitza una vigilància pel seu ID (pot ser integer o compost)

        Args:
            vig_id: Pot ser:
                - Integer (ID real de la BD): "123"
                - Compost (legacy): "08:00|1-BATX|0"
        """
        vig = None

        # Intentar parsejar com a integer primer (ID real de la BD)
        try:
            db_id = int(vig_id)
            vig = db.query(Vigilancia).filter(
                and_(
                    Vigilancia.id == db_id,
                    Vigilancia.data == parse_date(data)
                )
            ).first()
        except ValueError:
            # No és un integer, provar amb format compost
            parts = vig_id.split('|')
            if len(parts) != 3:
                return None

            hora, nivell, index_str = parts
            try:
                index = int(index_str)
            except ValueError:
                return None

            # Buscar vigilància amb index
            vigilancies = db.query(Vigilancia).filter(
                and_(
                    Vigilancia.data == parse_date(data),
                    Vigilancia.hora == hora,
                    Vigilancia.nivell == nivell
                )
            ).order_by(Vigilancia.id).all()

            if index >= len(vigilancies):
                return None

            vig = vigilancies[index]

        if not vig:
            return None

        # Actualitzar camps
        if 'hora' in updates:
            vig.hora = updates['hora']
        if 'tipus' in updates:
            vig.tipus = updates['tipus']
        if 'grups' in updates:
            vig.grups = updates['grups']
        if 'aula' in updates:
            vig.aula = updates['aula']
        if 'vigilant' in updates:
            vig.vigilant = updates['vigilant'] or None
        if 'comentaris' in updates:
            vig.comentaris = updates['comentaris']
        if 'nivell' in updates:
            vig.nivell = updates['nivell']

        db.commit()
        db.refresh(vig)
        return vig

    @staticmethod
    def get_by_id(db: Session, data: str, vig_id: str) -> Optional[Vigilancia]:
        """Retorna una vigilància pel seu ID (integer o compost)."""
        vig = None

        try:
            db_id = int(vig_id)
            vig = db.query(Vigilancia).filter(
                and_(
                    Vigilancia.id == db_id,
                    Vigilancia.data == parse_date(data)
                )
            ).first()
        except ValueError:
            parts = vig_id.split('|')
            if len(parts) != 3:
                return None

            hora, nivell, index_str = parts
            try:
                index = int(index_str)
            except ValueError:
                return None

            vigilancies = db.query(Vigilancia).filter(
                and_(
                    Vigilancia.data == parse_date(data),
                    Vigilancia.hora == hora,
                    Vigilancia.nivell == nivell
                )
            ).order_by(Vigilancia.id).all()

            if index >= len(vigilancies):
                return None

            vig = vigilancies[index]

        return vig

    @staticmethod
    def delete_by_id(db: Session, data: str, vig_id: str) -> bool:
        """
        Elimina una vigilància pel seu ID (pot ser integer o compost)

        Args:
            vig_id: Pot ser:
                - Integer (ID real de la BD): "123"
                - Compost (legacy): "08:00|1-BATX|0"
        """
        vig = None

        # Intentar parsejar com a integer primer (ID real de la BD)
        try:
            db_id = int(vig_id)
            vig = db.query(Vigilancia).filter(
                and_(
                    Vigilancia.id == db_id,
                    Vigilancia.data == parse_date(data)
                )
            ).first()
        except ValueError:
            # No és un integer, provar amb format compost
            parts = vig_id.split('|')
            if len(parts) != 3:
                return False

            hora, nivell, index_str = parts
            try:
                index = int(index_str)
            except ValueError:
                return False

            # Buscar vigilància amb index
            vigilancies = db.query(Vigilancia).filter(
                and_(
                    Vigilancia.data == parse_date(data),
                    Vigilancia.hora == hora,
                    Vigilancia.nivell == nivell
                )
            ).order_by(Vigilancia.id).all()

            if index >= len(vigilancies):
                return False

            vig = vigilancies[index]

        if not vig:
            return False

        db.delete(vig)
        db.commit()
        return True

    @staticmethod
    def get_vigilants_per_hora(db: Session, data: str, hora: str) -> List[str]:
        """Retorna vigilants assignats a una hora concreta"""
        vigilancies = db.query(Vigilancia).filter(
            and_(
                Vigilancia.data == parse_date(data),
                Vigilancia.hora == hora,
                Vigilancia.vigilant.isnot(None),
                Vigilancia.vigilant != ''
            )
        ).all()

        return [v.vigilant for v in vigilancies]

    @staticmethod
    def get_unique_tipus(db: Session) -> List[str]:
        """Retorna tots els tipus d'examen únics de totes les vigilàncies"""
        result = db.query(Vigilancia.tipus).distinct().all()
        tipus_list = [r[0] for r in result if r[0] and r[0].strip()]
        return sorted(tipus_list)


class SubstitucioRepository:
    """Operacions CRUD per substitucions"""

    @staticmethod
    def get_by_date(db: Session, data: str) -> List[Dict]:
        """Retorna totes les substitucions d'una data"""
        subs = db.query(Substitucio).filter(Substitucio.data == parse_date(data)).all()

        return [{
            'id': str(sub.id),
            'data': str(sub.data),
            'hora': sub.hora,
            'professor_absent': sub.professor_absent,
            'assignatura': sub.assignatura or '',
            'grup': sub.grup or '',
            'aula': sub.aula or '',
            'substitut': sub.substitut or '',
            'tipus_substitut': sub.tipus_substitut or '',
            'tipus_absencia': sub.tipus_absencia or '',
            'comentaris': sub.comentaris or '',
            'updated_at': sub.updated_at.isoformat() if sub.updated_at else None
        } for sub in subs]

    @staticmethod
    def create(db: Session, sub_data: Dict) -> Substitucio:
        """Crea una nova substitució"""
        sub = Substitucio(
            data=parse_date(sub_data['data']),
            hora=sub_data['hora'],
            professor_absent=sub_data['professor_absent'],
            assignatura=sub_data.get('assignatura', ''),
            grup=sub_data.get('grup', ''),
            aula=sub_data.get('aula', ''),
            substitut=sub_data.get('substitut', ''),
            tipus_substitut=sub_data.get('tipus_substitut', ''),
            tipus_absencia=sub_data.get('tipus_absencia', ''),
            comentaris=sub_data.get('comentaris', '')
        )
        db.add(sub)
        db.commit()
        db.refresh(sub)
        return sub

    @staticmethod
    def update(db: Session, sub_id: int, updates: Dict) -> Optional[Substitucio]:
        """Actualitza una substitució"""
        sub = db.query(Substitucio).filter(Substitucio.id == sub_id).first()
        if not sub:
            return None

        for key, value in updates.items():
            if hasattr(sub, key):
                setattr(sub, key, value)

        db.commit()
        db.refresh(sub)
        return sub

    @staticmethod
    def delete(db: Session, sub_id: int) -> bool:
        """Elimina una substitució"""
        sub = db.query(Substitucio).filter(Substitucio.id == sub_id).first()
        if not sub:
            return False

        db.delete(sub)
        db.commit()
        return True


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
    def set(db: Session, clau: str, valor: str, tipus: str = 'string', descripcio: str = ''):
        """Estableix un valor de configuració"""
        config = db.query(Configuracio).filter(Configuracio.clau == clau).first()

        if config:
            config.valor = valor
            config.tipus = tipus
            if descripcio:
                config.descripcio = descripcio
        else:
            config = Configuracio(clau=clau, valor=valor, tipus=tipus, descripcio=descripcio)
            db.add(config)

        db.commit()


class XMLVersionRepository:
    """Gestió d'històric d'XMLs per data"""

    @staticmethod
    def list_all(db: Session) -> List[XMLVersion]:
        return db.query(XMLVersion).order_by(XMLVersion.data_inici).all()

    @staticmethod
    def get_current(db: Session) -> Optional[XMLVersion]:
        return db.query(XMLVersion).filter(XMLVersion.data_fi.is_(None)).order_by(
            XMLVersion.data_inici.desc()
        ).first()

    @staticmethod
    def get_for_date(db: Session, data: str) -> Optional[XMLVersion]:
        data_obj = parse_date(data)
        return db.query(XMLVersion).filter(
            and_(
                XMLVersion.data_inici <= data_obj,
                or_(XMLVersion.data_fi.is_(None), XMLVersion.data_fi >= data_obj)
            )
        ).order_by(XMLVersion.data_inici.desc()).first()

    @staticmethod
    def create(
        db: Session,
        path: str,
        data_inici: date,
        hash_contingut: str = None,
        data_fi: date = None
    ) -> XMLVersion:
        nova = XMLVersion(
            path=path,
            data_inici=data_inici,
            data_fi=data_fi,
            hash_contingut=hash_contingut
        )
        db.add(nova)
        db.commit()
        db.refresh(nova)
        return nova

    @staticmethod
    def close_current(db: Session, data_fi: date):
        actual = db.query(XMLVersion).filter(XMLVersion.data_fi.is_(None)).order_by(
            XMLVersion.data_inici.desc()
        ).first()
        if actual:
            actual.data_fi = data_fi
            db.commit()


class CursRepository:
    """Cursos acadèmics: seqüència CONTÍGUA de períodes (mateix patró que xml_versions).

    Només es defineix `data_inici`. `data_fi` es deriva sempre: el curs acaba el dia
    abans que comenci el següent, i l'últim queda obert (`data_fi = NULL`). Així tota
    data pertany exactament a un curs i no cal cap flag d'"actiu".
    """

    @staticmethod
    def _rechain(db: Session) -> None:
        """Recalcula data_fi de tots els cursos perquè la seqüència sigui contígua."""
        cursos = db.query(Curs).order_by(Curs.data_inici.asc()).all()
        for i, curs in enumerate(cursos):
            seguent = cursos[i + 1] if i + 1 < len(cursos) else None
            nova_fi = (seguent.data_inici - timedelta(days=1)) if seguent else None
            if curs.data_fi != nova_fi:
                curs.data_fi = nova_fi
        db.commit()

    @staticmethod
    def list_all(db: Session) -> List[Curs]:
        return db.query(Curs).order_by(Curs.data_inici.desc()).all()

    @staticmethod
    def get(db: Session, curs_id: int) -> Optional[Curs]:
        return db.query(Curs).filter(Curs.id == curs_id).first()

    @staticmethod
    def get_for_date(db: Session, data: str) -> Optional[Curs]:
        """Curs al qual pertany una data. Cap si la data és anterior al primer curs."""
        data_obj = parse_date(data)
        return db.query(Curs).filter(
            and_(
                Curs.data_inici <= data_obj,
                or_(Curs.data_fi.is_(None), Curs.data_fi >= data_obj)
            )
        ).order_by(Curs.data_inici.desc()).first()

    @staticmethod
    def create(db: Session, nom: str, data_inici: date) -> Curs:
        nou = Curs(nom=nom, data_inici=data_inici, data_fi=None)
        db.add(nou)
        db.commit()
        CursRepository._rechain(db)
        db.refresh(nou)
        return nou

    @staticmethod
    def update(db: Session, curs_id: int, nom: str, data_inici: date) -> Optional[Curs]:
        curs = db.query(Curs).filter(Curs.id == curs_id).first()
        if not curs:
            return None
        curs.nom = nom
        curs.data_inici = data_inici
        db.commit()
        CursRepository._rechain(db)
        db.refresh(curs)
        return curs

    @staticmethod
    def delete(db: Session, curs_id: int) -> bool:
        curs = db.query(Curs).filter(Curs.id == curs_id).first()
        if not curs:
            return False
        db.delete(curs)
        db.commit()
        CursRepository._rechain(db)
        return True


class GrupsAlliberatsRepository:
    """Operacions per grups alliberats"""

    @staticmethod
    def get_by_date(db: Session, data: str) -> Dict[str, List[str]]:
        """Retorna grups alliberats per hora en una data"""
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

        db.commit()


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
            assignatures = db.query(Assignatura).filter(
                Assignatura.nivell_id == nivell.id
            ).order_by(Assignatura.ordre).all()

            # Grups del nivell
            grups = db.query(Grup).filter(
                Grup.nivell_id == nivell.id
            ).order_by(Grup.ordre).all()

            nivells_dict[nivell.codi] = {
                "assignatures": [a.nom for a in assignatures],
                "grups": [g.codi for g in grups]
            }

        # Aules
        aules = db.query(Aula).order_by(Aula.ordre).all()
        aules_list = [a.codi for a in aules]

        # Abreviatures
        abreviatures = db.query(AbreviaturaGrup).all()
        abreviatures_dict = {a.grups_originals: a.abreviatura for a in abreviatures}

        return {
            "nivells": nivells_dict,
            "aules": aules_list,
            "abreviatures": abreviatures_dict
        }

    # ===== NIVELLS =====

    @staticmethod
    def get_nivells(db: Session) -> List[str]:
        """Retorna tots els codis de nivells ordenats"""
        nivells = db.query(Nivell).filter(Nivell.actiu == True).order_by(Nivell.ordre).all()
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

        nivell = Nivell(
            codi=codi,
            nom=nom or codi,
            ordre=max_ordre,
            actiu=True
        )
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

        assignatures = db.query(Assignatura).filter(
            Assignatura.nivell_id == nivell.id
        ).order_by(Assignatura.ordre).all()

        return [a.nom for a in assignatures]

    @staticmethod
    def add_assignatura(db: Session, nivell_codi: str, nom: str) -> bool:
        """Afegeix una assignatura a un nivell"""
        nivell = db.query(Nivell).filter(Nivell.codi == nivell_codi).first()
        if not nivell:
            return False

        # Comprovar si ja existeix
        existing = db.query(Assignatura).filter(
            Assignatura.nivell_id == nivell.id,
            Assignatura.nom == nom
        ).first()

        if existing:
            return False

        # Obtenir següent ordre
        max_ordre = db.query(func.max(Assignatura.ordre)).filter(
            Assignatura.nivell_id == nivell.id
        ).scalar() or 0

        assignatura = Assignatura(
            nom=nom,
            nivell_id=nivell.id,
            ordre=max_ordre + 1
        )
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

        assignatura = db.query(Assignatura).filter(
            Assignatura.nivell_id == nivell.id,
            Assignatura.nom == nom_antic
        ).first()

        if not assignatura:
            return False

        # Comprovar si el nou nom ja existeix en aquest nivell
        if nom_antic != nou_nom:
            existing = db.query(Assignatura).filter(
                Assignatura.nivell_id == nivell.id,
                Assignatura.nom == nou_nom
            ).first()
            if existing:
                return False

        # 1. Actualitzar taula mestra
        assignatura.nom = nou_nom

        # 2. Propagar a assignacions d'exàmens (NOMÉS si l'assignatura coincideix EXACTAMENT)
        # Nota: Aquí no filtrem per nivell perquè a la taula 'configuracio_examens'
        # l'assignatura es guarda com a string global. Però normalment els noms d'assignatura
        # són únics per nivell o globals.
        db.query(ConfiguracioExamen).filter(
            ConfiguracioExamen.assignatura == nom_antic
        ).update({"assignatura": nou_nom})

        db.commit()
        return True

    @staticmethod
    def delete_assignatura(db: Session, nivell_codi: str, nom: str) -> bool:
        """Elimina una assignatura d'un nivell"""
        nivell = db.query(Nivell).filter(Nivell.codi == nivell_codi).first()
        if not nivell:
            return False

        assignatura = db.query(Assignatura).filter(
            Assignatura.nivell_id == nivell.id,
            Assignatura.nom == nom
        ).first()

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
            assignatura = db.query(Assignatura).filter(
                Assignatura.nivell_id == nivell.id,
                Assignatura.nom == nom
            ).first()
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

        grups = db.query(Grup).filter(
            Grup.nivell_id == nivell.id
        ).order_by(Grup.ordre).all()

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
        max_ordre = db.query(func.max(Grup.ordre)).filter(
            Grup.nivell_id == nivell.id
        ).scalar() or 0

        grup = Grup(
            codi=codi,
            nom=codi,
            nivell_id=nivell.id,
            ordre=max_ordre + 1
        )
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
        db.query(ConfiguracioExamen).filter(
            ConfiguracioExamen.grup == codi_antic
        ).update({"grup": nou_codi})

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

        aula = Aula(
            codi=codi,
            nom=codi,
            ordre=max_ordre + 1
        )
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
        db.query(ConfiguracioExamen).filter(
            ConfiguracioExamen.aula == codi_antic
        ).update({"aula": nou_codi})

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

        assignacions = db.query(ConfiguracioExamen).order_by(
            ConfiguracioExamen.assignatura,
            ConfiguracioExamen.ordre
        ).all()

        return [
            {
                "id": a.id,
                "assignatura": a.assignatura,
                "grup": a.grup,
                "titular": a.titular or "",
                "aula": a.aula or "",
                "ordre": a.ordre
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

            result["assignatures"][assignatura]["assignacions"].append({
                "grup": config.grup or "",
                "aula": config.aula or "",
                "titular": config.titular or ""
            })

        return result

    @staticmethod
    def buscar_titular(db: Session, tipus_examen: str, grups: str = "", aula: str = "") -> Optional[str]:
        """Busca el titular amb la mateixa prioritat que a la configuració d'exàmens."""
        from models import ConfiguracioExamen

        assignacions = db.query(ConfiguracioExamen).filter(
            ConfiguracioExamen.assignatura == tipus_examen
        ).all()

        if not assignacions:
            return None

        if grups and aula:
            for a in assignacions:
                if a.grup == grups and a.aula == aula and a.titular:
                    return a.titular

        if grups:
            for a in assignacions:
                if a.grup == grups and a.titular and a.aula != "ENLLAÇ":
                    return a.titular

        if aula:
            for a in assignacions:
                if a.aula == aula and a.titular and a.aula != "ENLLAÇ":
                    return a.titular

        if grups:
            for a in assignacions:
                if a.aula == "ENLLAÇ" and a.titular:
                    if a.grup and any(part in grups for part in a.grup.split('-') if part):
                        return a.titular

        for a in assignacions:
            if a.titular:
                return a.titular

        return None

    @staticmethod
    def get_by_assignatura(db: Session, assignatura: str) -> List[Dict]:
        """Retorna assignacions d'una assignatura"""
        from models import ConfiguracioExamen

        assignacions = db.query(ConfiguracioExamen).filter(
            ConfiguracioExamen.assignatura == assignatura
        ).order_by(ConfiguracioExamen.ordre).all()

        return [
            {
                "id": a.id,
                "assignatura": a.assignatura,
                "grup": a.grup,
                "titular": a.titular or "",
                "aula": a.aula or "",
                "ordre": a.ordre
            }
            for a in assignacions
        ]

    @staticmethod
    def create(db: Session, assignatura: str, grup: str, titular: str = None,
               aula: str = None, ordre: int = 0) -> int:
        """Crea una nova assignació"""
        from models import ConfiguracioExamen

        nova_assignacio = ConfiguracioExamen(
            assignatura=assignatura,
            grup=grup,
            titular=titular if titular else None,
            aula=aula if aula else None,
            ordre=ordre
        )

        db.add(nova_assignacio)
        db.commit()
        db.refresh(nova_assignacio)

        return nova_assignacio.id

    @staticmethod
    def update(db: Session, assignacio_id: int, titular: str = None,
               aula: str = None) -> bool:
        """Actualitza una assignació"""
        from models import ConfiguracioExamen

        assignacio = db.query(ConfiguracioExamen).filter(
            ConfiguracioExamen.id == assignacio_id
        ).first()

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

        assignacio = db.query(ConfiguracioExamen).filter(
            ConfiguracioExamen.id == assignacio_id
        ).first()

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
# ABREVIATURES GRUPS
# ===========================

class AbreviaturaGrupRepository:
    """Repositori per gestionar abreviatures de grups"""

    @staticmethod
    def get_all(db: Session) -> List[Dict]:
        """Retorna totes les abreviatures"""
        from models import AbreviaturaGrup

        abreviatures = db.query(AbreviaturaGrup).all()

        return [
            {
                "id": a.id,
                "grups_originals": a.grups_originals,
                "abreviatura": a.abreviatura
            }
            for a in abreviatures
        ]

    @staticmethod
    def get_by_abreviatura(db: Session, abreviatura: str) -> Optional[str]:
        """Retorna els grups originals d'una abreviatura"""
        from models import AbreviaturaGrup

        abrev = db.query(AbreviaturaGrup).filter(
            AbreviaturaGrup.abreviatura == abreviatura
        ).first()

        return abrev.grups_originals if abrev else None

    @staticmethod
    def create(db: Session, grups_originals: str, abreviatura: str) -> int:
        """Crea una nova abreviatura"""
        from models import AbreviaturaGrup

        nova_abrev = AbreviaturaGrup(
            grups_originals=grups_originals,
            abreviatura=abreviatura
        )

        db.add(nova_abrev)
        db.commit()
        db.refresh(nova_abrev)

        return nova_abrev.id

    @staticmethod
    def update(db: Session, abreviatura_id: int, grups_originals: str = None,
               abreviatura: str = None) -> bool:
        """Actualitza una abreviatura"""
        from models import AbreviaturaGrup

        abrev = db.query(AbreviaturaGrup).filter(
            AbreviaturaGrup.id == abreviatura_id
        ).first()

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

        abrev = db.query(AbreviaturaGrup).filter(
            AbreviaturaGrup.id == abreviatura_id
        ).first()

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
        from models import Professor
        from datetime import date

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
                db.add(Professor(
                    nom=nom,
                    actiu=True,
                    primera_aparicio=data_avui,
                    ultima_aparicio=data_avui
                ))
                nous += 1

        # Marcar inactius els que ja no hi són
        for nom, prof in existing.items():
            if nom not in professors_noms and prof.actiu:
                prof.actiu = False
                prof.ultima_aparicio = data_avui
                desactivats += 1

        db.commit()
        return {
            "nous": nous,
            "reactivats": reactivats,
            "desactivats": desactivats,
            "total_xml": len(professors_noms)
        }


class ProfessorBaixaRepository:
    """Repositori per gestionar professors de baixa"""

    @staticmethod
    def get_all(db: Session) -> List[Dict]:
        """Retorna tots els professors de baixa"""
        from models import ProfessorBaixa

        professors = db.query(ProfessorBaixa).order_by(ProfessorBaixa.data_inici).all()

        return [
            {
                "id": p.id,
                "professor": p.professor,
                "data_inici": p.data_inici.isoformat(),
                "data_final": p.data_final.isoformat(),
                "motiu": p.motiu or ""
            }
            for p in professors
        ]

    @staticmethod
    def create(db: Session, professor: str, data_inici: str, data_final: str,
               motiu: str = "") -> int:
        """Crea un nou professor de baixa"""
        from models import ProfessorBaixa
        from datetime import datetime

        nova_baixa = ProfessorBaixa(
            professor=professor,
            data_inici=datetime.strptime(data_inici, "%Y-%m-%d").date(),
            data_final=datetime.strptime(data_final, "%Y-%m-%d").date(),
            motiu=motiu
        )

        db.add(nova_baixa)
        db.commit()
        db.refresh(nova_baixa)

        return nova_baixa.id

    @staticmethod
    def update(db: Session, baixa_id: int, professor: str = None,
               data_inici: str = None, data_final: str = None,
               motiu: str = None) -> bool:
        """Actualitza un professor de baixa"""
        from models import ProfessorBaixa
        from datetime import datetime

        baixa = db.query(ProfessorBaixa).filter(
            ProfessorBaixa.id == baixa_id
        ).first()

        if not baixa:
            return False

        if professor is not None:
            baixa.professor = professor
        if data_inici is not None:
            baixa.data_inici = datetime.strptime(data_inici, "%Y-%m-%d").date()
        if data_final is not None:
            baixa.data_final = datetime.strptime(data_final, "%Y-%m-%d").date()
        if motiu is not None:
            baixa.motiu = motiu

        db.commit()
        return True

    @staticmethod
    def delete(db: Session, baixa_id: int) -> bool:
        """Elimina un professor de baixa"""
        from models import ProfessorBaixa

        baixa = db.query(ProfessorBaixa).filter(
            ProfessorBaixa.id == baixa_id
        ).first()

        if not baixa:
            return False

        db.delete(baixa)
        db.commit()
        return True


# ===========================
# CATEGORIES PRIORITAT
# ===========================

class CategoriaPrioritatRepository:
    """Repositori per gestionar categories de prioritat"""

    @staticmethod
    def get_all(db: Session) -> List[Dict]:
        """Retorna totes les categories ordenades per ordre"""
        from models import CategoriaPrioritat

        categories = db.query(CategoriaPrioritat).order_by(
            CategoriaPrioritat.ordre
        ).all()

        return [
            {
                "id": c.id,
                "nom": c.nom,
                "ordre": c.ordre,
                "activa": c.activa
            }
            for c in categories
        ]

    @staticmethod
    def create(db: Session, nom: str, ordre: int = None, activa: bool = True) -> int:
        """Crea una nova categoria"""
        from models import CategoriaPrioritat

        if ordre is None:
            # Posar al final
            max_ordre = db.query(CategoriaPrioritat).count()
            ordre = max_ordre

        nova_cat = CategoriaPrioritat(
            nom=nom,
            ordre=ordre,
            activa=activa
        )

        db.add(nova_cat)
        db.commit()
        db.refresh(nova_cat)

        return nova_cat.id

    @staticmethod
    def update(db: Session, categoria_id: int, nom: str = None,
               ordre: int = None, activa: bool = None) -> bool:
        """Actualitza una categoria"""
        from models import CategoriaPrioritat

        cat = db.query(CategoriaPrioritat).filter(
            CategoriaPrioritat.id == categoria_id
        ).first()

        if not cat:
            return False

        if nom is not None:
            cat.nom = nom
        if ordre is not None:
            cat.ordre = ordre
        if activa is not None:
            cat.activa = activa

        db.commit()
        return True

    @staticmethod
    def update_ordre(db: Session, categories_ordenades: List[int]):
        """Actualitza l'ordre de les categories"""
        from models import CategoriaPrioritat

        for idx, categoria_id in enumerate(categories_ordenades):
            cat = db.query(CategoriaPrioritat).filter(
                CategoriaPrioritat.id == categoria_id
            ).first()
            if cat:
                cat.ordre = idx

        db.commit()

    @staticmethod
    def delete(db: Session, categoria_id: int) -> bool:
        """Elimina una categoria (i totes les seves assignatures per CASCADE)"""
        from models import CategoriaPrioritat

        cat = db.query(CategoriaPrioritat).filter(
            CategoriaPrioritat.id == categoria_id
        ).first()

        if not cat:
            return False

        db.delete(cat)
        db.commit()
        return True


# ===========================
# ASSIGNATURES PRIORITAT
# ===========================

class AssignaturaPrioritatRepository:
    """Repositori per gestionar assignatures dins categories de prioritat"""

    @staticmethod
    def get_all(db: Session) -> List[Dict]:
        """Retorna totes les assignatures amb la seva categoria"""
        from models import AssignaturaPrioritat, CategoriaPrioritat

        assignatures = db.query(AssignaturaPrioritat).join(
            CategoriaPrioritat
        ).order_by(
            CategoriaPrioritat.ordre,
            AssignaturaPrioritat.ordre
        ).all()

        return [
            {
                "id": a.id,
                "assignatura": a.assignatura,
                "categoria_id": a.categoria_id,
                "pes": a.pes,
                "ordre": a.ordre,
                "auto_assignada": a.auto_assignada if hasattr(a, 'auto_assignada') else False
            }
            for a in assignatures
        ]

    @staticmethod
    def get_by_categoria(db: Session, categoria_id: int) -> List[Dict]:
        """Retorna assignatures d'una categoria"""
        from models import AssignaturaPrioritat

        assignatures = db.query(AssignaturaPrioritat).filter(
            AssignaturaPrioritat.categoria_id == categoria_id
        ).order_by(AssignaturaPrioritat.ordre).all()

        return [
            {
                "id": a.id,
                "assignatura": a.assignatura,
                "pes": a.pes,
                "ordre": a.ordre
            }
            for a in assignatures
        ]

    @staticmethod
    def create(db: Session, assignatura: str, categoria_id: int,
               pes: int = 1, ordre: int = None) -> int:
        """Crea una nova assignatura dins una categoria"""
        from models import AssignaturaPrioritat

        if ordre is None:
            # Posar al final de la categoria
            max_ordre = db.query(AssignaturaPrioritat).filter(
                AssignaturaPrioritat.categoria_id == categoria_id
            ).count()
            ordre = max_ordre

        nova_assig = AssignaturaPrioritat(
            assignatura=assignatura,
            categoria_id=categoria_id,
            pes=pes,
            ordre=ordre
        )

        db.add(nova_assig)
        db.commit()
        db.refresh(nova_assig)

        return nova_assig.id

    @staticmethod
    def update(db: Session, assignatura_id: int, assignatura: str = None,
               categoria_id: int = None, pes: int = None, ordre: int = None) -> bool:
        """Actualitza una assignatura"""
        from models import AssignaturaPrioritat

        assig = db.query(AssignaturaPrioritat).filter(
            AssignaturaPrioritat.id == assignatura_id
        ).first()

        if not assig:
            return False

        if assignatura is not None:
            assig.assignatura = assignatura
        if categoria_id is not None:
            assig.categoria_id = categoria_id
        if pes is not None:
            assig.pes = pes
        if ordre is not None:
            assig.ordre = ordre

        db.commit()
        return True

    @staticmethod
    def delete(db: Session, assignatura_id: int) -> bool:
        """Elimina una assignatura de prioritat"""
        from models import AssignaturaPrioritat

        assig = db.query(AssignaturaPrioritat).filter(
            AssignaturaPrioritat.id == assignatura_id
        ).first()

        if not assig:
            return False

        db.delete(assig)
        db.commit()
        return True


# ===========================
# NO SUBSTITUIR
# ===========================

class NoSubstituirRepository:
    """Repositori per gestionar llista d'assignatures que NO es substitueixen"""

    @staticmethod
    def get_all(db: Session) -> List[str]:
        """Retorna totes les assignatures de no substituir"""
        from models import NoSubstituir

        assignatures = db.query(NoSubstituir).all()

        return [a.assignatura for a in assignatures]

    @staticmethod
    def create(db: Session, assignatura: str) -> int:
        """Afegeix una assignatura a no substituir"""
        from models import NoSubstituir

        nova = NoSubstituir(assignatura=assignatura)

        db.add(nova)
        db.commit()
        db.refresh(nova)

        return nova.id

    @staticmethod
    def delete(db: Session, assignatura: str) -> bool:
        """Elimina una assignatura de no substituir"""
        from models import NoSubstituir

        assig = db.query(NoSubstituir).filter(
            NoSubstituir.assignatura == assignatura
        ).first()

        if not assig:
            return False

        db.delete(assig)
        db.commit()
        return True

    @staticmethod
    def exists(db: Session, assignatura: str) -> bool:
        """Comprova si una assignatura està a la llista de no substituir"""
        from models import NoSubstituir

        return db.query(NoSubstituir).filter(
            NoSubstituir.assignatura == assignatura
        ).first() is not None


# ===========================
# USERS
# ===========================

class UserRepository:
    """Repositori per gestionar usuaris"""

    @staticmethod
    def get_by_username(db: Session, username: str) -> Optional[User]:
        return db.query(User).filter(User.username == username).first()

    @staticmethod
    def get_by_id(db: Session, user_id: int) -> Optional[User]:
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def list_all(db: Session) -> list[User]:
        return db.query(User).order_by(User.username.asc()).all()

    @staticmethod
    def list_by_institucio(db: Session, institucio: str) -> list[User]:
        return db.query(User).filter(User.institucio == institucio).order_by(User.username.asc()).all()

    @staticmethod
    def create(
        db: Session,
        username: str,
        password_hash: str,
        institucio: str,
        role: str = "user",
        active: bool = True
    ) -> User:
        user = User(
            username=username,
            password_hash=password_hash,
            institucio=institucio,
            role=role,
            active=active
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def update(db: Session, user: User, **fields) -> User:
        for key, value in fields.items():
            setattr(user, key, value)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def delete(db: Session, user: User) -> None:
        db.delete(user)
        db.commit()
