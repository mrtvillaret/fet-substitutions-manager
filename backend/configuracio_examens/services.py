"""Regles de la configuració d'exàmens: la configuració mestra (nivells,
assignatures i grups de cada nivell, aules) i les assignacions de titulars.

La configuració d'exàmens no es sincronitza mai amb l'XML: pot ser diferent
a propòsit (p. ex. un grup que no és a l'horari)."""

from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from configuracio_examens.repositories import ConfiguracioExamenRepository, MasterConfigRepository
from errors_domini import NoTrobat, NoValid
from grups.repositories import AbreviaturaGrupRepository
from noms import neteja_noms, nom_net

# ---------------------------------------------------------------- nivells


def nivells(db: Session) -> List[str]:
    return MasterConfigRepository.get_nivells(db)


def afegeix_nivell(db: Session, codi: Optional[str], nom: Optional[str]) -> None:
    if not codi:
        raise NoValid("Codi de nivell requerit", codi="nivell_sense_codi")
    if not MasterConfigRepository.add_nivell(db, codi, nom):
        raise NoValid("Nivell ja existeix", codi="nivell_existent")
    db.commit()


# Les assignacions que fan servir un nivell o un grup (comptades a la
# configuració d'exàmens: les dels grups del nivell, o les del grup). En
# esborrar-lo, la pantalla pregunta si s'esborren també (en la mateixa
# operació, tot o res); si no, es queden i tornen a servir si es torna a
# crear. Les d'una aula no s'esborren mai: una assignació sense aula és vàlida.


def _grups_del_nivell(db: Session, codi: str) -> List[str]:
    if codi not in MasterConfigRepository.get_nivells(db):
        raise NoTrobat("Nivell no trobat", codi="nivell_no_trobat")
    return MasterConfigRepository.get_grups_per_nivell(db, codi)


def _comprova_grup(db: Session, codi: str) -> None:
    if codi not in MasterConfigRepository.codis_de_grups(db):
        raise NoTrobat("Grup no trobat", codi="grup_no_trobat")


def assignacions_del_nivell(db: Session, codi: str) -> int:
    return ConfiguracioExamenRepository.compta(db, grups=_grups_del_nivell(db, codi))


def assignacions_del_grup(db: Session, codi: str) -> int:
    _comprova_grup(db, codi)
    return ConfiguracioExamenRepository.compta(db, grups=[codi])


def esborra_nivell(db: Session, codi: str, amb_assignacions: bool = False) -> int:
    """Amb els seus grups i assignatures (CASCADE) i, si es demana, les
    assignacions dels seus grups. Retorna quantes assignacions en feien servir
    els grups (segons la configuració)."""
    grups = _grups_del_nivell(db, codi)
    assignacions = ConfiguracioExamenRepository.compta(db, grups=grups)
    if amb_assignacions:
        ConfiguracioExamenRepository.delete_per_grups(db, grups)
    if not MasterConfigRepository.delete_nivell(db, codi):
        raise NoTrobat("Nivell no trobat", codi="nivell_no_trobat")
    db.commit()
    return assignacions


# ---------------------------------------------------------------- assignatures


def assignatures(db: Session, nivell: str) -> List[str]:
    return MasterConfigRepository.get_assignatures_per_nivell(db, nivell)


def afegeix_assignatura(db: Session, nivell: str, nom: Optional[str]) -> None:
    if not nom:
        raise NoValid("Nom d'assignatura requerit", codi="assignatura_sense_nom")
    if not MasterConfigRepository.add_assignatura(db, nivell, nom):
        raise NoValid("Assignatura ja existeix o nivell no trobat", codi="assignatura_no_afegida")
    db.commit()


def reanomena_assignatura(db: Session, nivell: str, nom: str, nou_nom: str) -> None:
    """També a les assignacions amb aquesta assignatura."""
    if not MasterConfigRepository.rename_assignatura(db, nivell, nom, nou_nom):
        raise NoValid("No s'ha pogut reanomenar l'assignatura", codi="assignatura_no_reanomenada")


def esborra_assignatura(db: Session, nivell: str, nom: str) -> None:
    if not MasterConfigRepository.delete_assignatura(db, nivell, nom):
        raise NoTrobat("Assignatura no trobada", codi="assignatura_no_trobada")


# ---------------------------------------------------------------- grups


def grups(db: Session, nivell: str) -> List[str]:
    return MasterConfigRepository.get_grups_per_nivell(db, nivell)


def afegeix_grup(db: Session, nivell: str, codi: Optional[str]) -> None:
    if not codi:
        raise NoValid("Codi de grup requerit", codi="grup_sense_codi")
    if not MasterConfigRepository.add_grup(db, nivell, codi):
        raise NoValid("Grup ja existeix o nivell no trobat", codi="grup_no_afegit")
    db.commit()


def reanomena_grup(db: Session, codi: str, nou_codi: str) -> None:
    """També a les assignacions amb aquest grup."""
    if not MasterConfigRepository.rename_grup(db, codi, nou_codi):
        raise NoValid("No s'ha pogut reanomenar el grup", codi="grup_no_reanomenat")


def esborra_grup(db: Session, codi: str, amb_assignacions: bool = False) -> int:
    """I, si es demana, les seves assignacions. Retorna quantes el tenien."""
    assignacions = ConfiguracioExamenRepository.compta(db, grups=[codi])
    if amb_assignacions:
        ConfiguracioExamenRepository.delete_per_grups(db, [codi])
    if not MasterConfigRepository.delete_grup(db, codi):
        raise NoTrobat("Grup no trobat", codi="grup_no_trobat")
    db.commit()
    return assignacions


# ---------------------------------------------------------------- aules


def aules(db: Session) -> List[str]:
    return MasterConfigRepository.get_aules(db)


def afegeix_aula(db: Session, codi: Optional[str]) -> str:
    """Retorna el codi net."""
    codi = nom_net(codi)
    if not codi:
        raise NoValid("Codi d'aula requerit", codi="aula_sense_codi")
    if not MasterConfigRepository.add_aula(db, codi):
        raise NoValid("Aula ja existeix", codi="aula_existent")
    db.commit()
    return codi


def reanomena_aula(db: Session, codi: str, nou_codi: str) -> None:
    """També a les assignacions amb aquesta aula."""
    if not MasterConfigRepository.rename_aula(db, codi, nou_codi):
        raise NoValid("No s'ha pogut reanomenar l'aula", codi="aula_no_reanomenada")


def esborra_aula(db: Session, codi: str) -> int:
    """Retorna quantes assignacions la tenen (no es toquen)."""
    assignacions = ConfiguracioExamenRepository.compta(db, aula=codi)
    if not MasterConfigRepository.delete_aula(db, codi):
        raise NoTrobat("Aula no trobada", codi="aula_no_trobada")
    return assignacions


# ---------------------------------------------------------------- assignacions


def assignacions(db: Session) -> List[Dict]:
    return ConfiguracioExamenRepository.get_all(db)


def assignacions_obsoletes(db: Session, horari) -> List[Dict]:
    """Assignacions amb un grup o un titular que no són a `horari` (l'XML del
    planificador). El nom de l'assignatura no es té en compte: es pot haver
    canviat a mà (p.ex. "1.1 Prof 7" per a una franja d'optatives). Un grup
    dels nivells de la configuració d'exàmens també és vàlid, encara que no
    sigui a l'XML (p.ex. «4-ESO-AB», d'un professor que fa d'enllaç de dos
    grups): si es treu de la configuració, torna a sortir."""
    grups = set(horari.tots_grups) | set(horari.tots_grups_raw)
    grups |= {part.strip() for g in list(grups) for part in g.split(",")}
    grups |= MasterConfigRepository.codis_de_grups(db)
    abreviatures = {
        a["abreviatura"]: [g.strip() for g in a["grups_originals"].split(",")]
        for a in AbreviaturaGrupRepository.get_all(db)
    }
    # Tots els de l'XML: l'horari del dia no té els que tenen una absència
    # coberta, i la seva assignació continua sent d'aquest curs
    professors = set(horari.tots_professors)

    def grup_existeix(grup: str) -> bool:
        if grup in grups:
            return True
        parts = abreviatures.get(grup) or [g.strip() for g in grup.split(",")]
        return len(parts) > 1 and all(p in grups for p in parts)

    obsoletes = []
    for a in ConfiguracioExamenRepository.get_all(db):
        motius = []
        if a.get("grup") and not grup_existeix(a["grup"]):
            motius.append("grup")
        if a.get("titular") and a["titular"] not in professors:
            motius.append("titular")
        if motius:
            obsoletes.append({**a, "motius": motius})
    return obsoletes


def crea_assignacio(db: Session, dades: Dict) -> tuple:
    """L'assignatura i el grup són obligatoris; titular i aula buits = cap.
    Retorna (id, assignatura, grup)."""
    dades = neteja_noms(dades, "assignatura", "titular", "aula")
    assignatura = dades.get("assignatura")
    grup = dades.get("grup")
    if not assignatura or not grup:
        raise NoValid("Assignatura i grup són obligatoris", codi="assignacio_incompleta")
    assignacio_id = ConfiguracioExamenRepository.create(
        db, assignatura, grup, dades.get("titular", "") or None, dades.get("aula", "") or None, dades.get("ordre", 0)
    )
    db.commit()
    return assignacio_id, assignatura, grup


def edita_assignacio(db: Session, assignacio_id: int, dades: Dict) -> None:
    """Només el titular i l'aula (buits = cap)."""
    dades = neteja_noms(dades, "titular", "aula")
    titular = dades.get("titular", "") or None
    aula = dades.get("aula", "") or None
    if not ConfiguracioExamenRepository.update(db, assignacio_id, titular, aula):
        raise NoTrobat("Assignació no trobada", codi="assignacio_no_trobada")


def esborra_assignacio(db: Session, assignacio_id: int) -> None:
    if not ConfiguracioExamenRepository.delete(db, assignacio_id):
        raise NoTrobat("Assignació no trobada", codi="assignacio_no_trobada")


def esborra_assignacions(db: Session, dades: Dict) -> int:
    """`ids`: les d'aquests ids; `tot: true`: totes. Retorna quantes."""
    if dades.get("tot"):
        eliminades = ConfiguracioExamenRepository.delete_all(db)
        db.commit()
        return eliminades

    ids = dades.get("ids", [])
    if not ids:
        raise NoValid("Cal indicar 'ids' o 'tot: true'", codi="assignacions_sense_ids")
    eliminades = ConfiguracioExamenRepository.delete_ids(db, ids)
    db.commit()
    return eliminades
