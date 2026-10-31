"""Regles dels cursos acadèmics: la llista, els avisos d'XML i els canvis.

Cap dada de substitucions o vigilàncies es toca en crear, editar o eliminar
un curs."""

from datetime import date

from sqlalchemy.orm import Session

from cursos.repositories import CursRepository
from errors_domini import NoTrobat, NoValid
from horari.repositories import XMLVersionRepository


def fitxa(c) -> dict:
    return {
        "id": c.id,
        "nom": c.nom,
        "data_inici": c.data_inici.isoformat() if c.data_inici else None,
        # derivada pel sistema; None = últim curs (obert)
        "data_fi": c.data_fi.isoformat() if c.data_fi else None,
    }


def llista(db: Session) -> list[dict]:
    """Els cursos (més recent primer), amb la data_fi ja derivada."""
    return [fitxa(c) for c in CursRepository.list_all(db)]


def avisos_xml(db: Session) -> list[dict]:
    """Cursos que arrencarien amb l'horari d'un curs anterior.

    Un curs hauria de començar amb un XML que entra en vigor el mateix dia. Si l'XML
    vigent a la seva data d'inici va començar abans, el curs hereta l'horari de l'any
    anterior — típicament perquè encara no s'ha pujat el nou.

    Només es revisen el curs vigent i els futurs (els passats ja no són accionables).
    """
    cursos = CursRepository.list_all(db)
    if not cursos:
        return []

    avui = date.today()
    primer_inici = min(c.data_inici for c in cursos)
    avisos = []

    for c in cursos:
        if c.data_fi is not None and c.data_fi < avui:
            continue  # curs ja tancat: no accionable
        if c.data_inici == primer_inici:
            continue  # el primer curs no té cap anterior
        versio = XMLVersionRepository.get_for_date(db, c.data_inici.isoformat())
        if not versio:
            continue  # sense historial d'XML per aquella data
        if versio.data_inici < c.data_inici:
            avisos.append(
                {
                    "curs_id": c.id,
                    "curs_nom": c.nom,
                    "curs_inici": c.data_inici.isoformat(),
                    "xml_inici": versio.data_inici.isoformat(),
                    "xml_path": versio.path,
                }
            )

    return avisos


def _comprova_inici_lliure(db: Session, data_inici: date, excepte: int = None) -> None:
    # Dos cursos el mateix dia deixarien la cadena amb una data de fi anterior a la d'inici
    if CursRepository.comenca_el(db, data_inici, excepte=excepte):
        raise NoValid("Ja hi ha un altre curs que comença aquest dia", codi="curs_mateix_dia")


def crea(db: Session, nom: str, data_inici: date) -> dict:
    _comprova_inici_lliure(db, data_inici)
    curs = CursRepository.create(db, nom, data_inici)
    db.commit()
    return fitxa(curs)


def edita(db: Session, curs_id: int, nom: str, data_inici: date) -> dict:
    if not CursRepository.get(db, curs_id):
        raise NoTrobat("Curs no trobat", codi="curs_no_trobat")
    _comprova_inici_lliure(db, data_inici, excepte=curs_id)
    curs = CursRepository.update(db, curs_id, nom, data_inici)
    db.commit()
    return fitxa(curs)


def esborra(db: Session, curs_id: int) -> None:
    """Esborra només la metadada del curs; no toca substitucions ni vigilàncies."""
    if not CursRepository.delete(db, curs_id):
        raise NoTrobat("Curs no trobat", codi="curs_no_trobat")
    db.commit()
