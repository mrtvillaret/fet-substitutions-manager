"""Regles de les prioritats: les categories i les assignatures (amb el seu pes)
que fan servir el motor de substitucions i el de vigilàncies per triar
substituts, «No substituir» (amb vigència per dates), i la seva càrrega a
memòria (config.constants)."""

from datetime import date, timedelta

from sqlalchemy.orm import Session

import rellotge
from errors_domini import Conflicte, NoTrobat, NoValid
from prioritats.memoria import carrega_prioritats as carrega_prioritats
from prioritats.repositories import AssignaturaPrioritatRepository, CategoriaPrioritatRepository, NoSubstituirRepository


def llista_categories(db: Session) -> list[dict]:
    return CategoriaPrioritatRepository.get_all(db)


def llista_assignatures(db: Session) -> list[dict]:
    return AssignaturaPrioritatRepository.get_all(db)


def desa_totes(db: Session, ordre_categories: list[list[str]], pesos: dict, categories_actives: list[bool]) -> None:
    """Substitueix totes les categories i assignatures per les d'`ordre_categories`
    (una llista d'assignatures per categoria, en ordre de prioritat). Les
    llistes buides es salten. La categoria es diu com la seva assignatura o,
    si en té més, com les dues primeres; sense estat a `categories_actives`,
    és activa, i les assignatures d'una categoria activa s'assignen soles."""
    try:
        CategoriaPrioritatRepository.esborra_totes(db)
        for cat_ordre, assignatures in enumerate(ordre_categories):
            if not assignatures:
                continue
            nom = assignatures[0] if len(assignatures) == 1 else ", ".join(assignatures[:2])
            activa = categories_actives[cat_ordre] if cat_ordre < len(categories_actives) else True
            cat_id = CategoriaPrioritatRepository.create(db, nom, ordre=cat_ordre, activa=activa)
            for assig_ordre, assignatura in enumerate(assignatures):
                AssignaturaPrioritatRepository.create(
                    db, assignatura, cat_id, pes=pesos.get(assignatura, 1), ordre=assig_ordre, auto_assignada=activa
                )
        db.commit()
    except Exception:
        db.rollback()
        raise
    carrega_prioritats(db)


def llista_no_substituir(db: Session) -> dict:
    """Les activitats vigents avui (`assignatures`, en l'ordre en què es van
    afegir) i les entrades que valen avui o més endavant, amb les seves dates
    (`entrades`): així la pantalla diu quan comença o acaba cadascuna."""
    avui = rellotge.avui().isoformat()
    vigencia = NoSubstituirRepository.vigencia(db)
    entrades = sorted(
        (e for e in vigencia.entrades if not e.acaba_abans_de(avui)),
        key=lambda e: (e.assignatura, e.vigent_des_de or ""),
    )
    return {
        "assignatures": [e.assignatura for e in vigencia.entrades if e.vigent_a(avui)],
        "entrades": [
            {"assignatura": e.assignatura, "vigent_des_de": e.vigent_des_de, "vigent_fins_a": e.vigent_fins_a}
            for e in entrades
        ],
    }


def _data_del_canvi(data: str | None) -> date:
    """Des de quan val un canvi de «No substituir»: la data triada o avui."""
    return date.fromisoformat(data) if data else rellotge.avui()


def afegeix_no_substituir(db: Session, assignatura: str | None, data: str | None = None) -> int:
    """Una entrada nova que val des de `data` (per defecte avui). Els dies
    d'abans no canvien. No es pot solapar amb cap altra entrada de la mateixa
    activitat. El text buit s'accepta (hi ha activitats sense nom a l'XML)."""
    if not assignatura and assignatura != "":
        raise NoValid("Assignatura requerida", codi="assignatura_requerida")
    des_de = _data_del_canvi(data)
    for fila in NoSubstituirRepository.de_l_activitat(db, assignatura):
        if fila.vigent_fins_a is not None and fila.vigent_fins_a < des_de:
            continue
        if fila.vigent_des_de is None or fila.vigent_des_de <= des_de:
            raise Conflicte(
                "L'assignatura ja és a «No substituir»",
                codi="no_substituir_repetida",
                params={"assignatura": assignatura},
            )
        inici = fila.vigent_des_de.strftime("%d/%m/%Y")
        raise Conflicte(
            f"L'activitat ja té un període a «No substituir» que comença el {inici}: "
            "per afegir-la abans d'aquesta data, anul·leu primer aquell període",
            codi="no_substituir_solapada",
            params={"assignatura": assignatura, "data": fila.vigent_des_de.isoformat(), "inici": inici},
        )
    no_subst_id = NoSubstituirRepository.create(db, assignatura, vigent_des_de=des_de)
    db.commit()
    carrega_prioritats(db)
    return no_subst_id


def treu_no_substituir(db: Session, assignatura: str, data: str | None = None) -> None:
    """Treu l'entrada que val a `data` (per defecte avui): la fila no
    s'esborra, s'hi posa la data de fi (el dia abans) i els dies d'abans no
    canvien. Si aquella entrada encara no havia començat (comença justament
    `data`), no ha valgut mai cap dia: s'esborra. Les altres entrades de
    l'activitat (p. ex. un període futur programat) no es toquen; per
    anul·lar-ne una de futura, es treu des de la seva data d'inici."""
    des_de = _data_del_canvi(data)
    vigent = next(
        (
            fila
            for fila in NoSubstituirRepository.de_l_activitat(db, assignatura)
            if NoSubstituirRepository.entrada(fila).vigent_a(des_de.isoformat())
        ),
        None,
    )
    if vigent is None:
        raise NoTrobat("Assignatura no trobada", codi="assignatura_no_trobada")
    if vigent.vigent_des_de is not None and vigent.vigent_des_de >= des_de:
        NoSubstituirRepository.delete(db, vigent)
    else:
        NoSubstituirRepository.tanca(db, vigent, des_de - timedelta(days=1))
    db.commit()
    carrega_prioritats(db)
