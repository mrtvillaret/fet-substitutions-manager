"""Dates dels documents JSON desats pel planificador."""

from datetime import date

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from planificador.repositories import SCHEDULER_ALLIBERAMENTS_KEY, SCHEDULER_DATES_KEY, llegeix_json


def data_desada(valor):
    """Converteix una data ISO canònica. Conserva els valors antics que es
    retornaven literalment, incloses les claus sense zeros dels alliberaments."""
    if isinstance(valor, str) and len(valor) == 10 and valor[4] == valor[7] == "-":
        try:
            return date.fromisoformat(valor)
        except ValueError:
            pass
    return valor


def llegeix_dates(db: Session) -> list[date]:
    desades = llegeix_json(db, SCHEDULER_DATES_KEY, [])
    return [data_desada(data) for data in desades] if isinstance(desades, list) else desades


def alliberaments_amb_dates(alliberaments: dict) -> dict:
    if not isinstance(alliberaments, dict):
        return alliberaments
    resultat = {}
    for nivell, dades in alliberaments.items():
        if isinstance(dades, dict):
            dades = dades.copy()
            if isinstance(dades.get("dates"), list):
                dades["dates"] = [data_desada(data) for data in dades["dates"]]
            if isinstance(dades.get("config"), dict):
                dades["config"] = {data_desada(data): marques for data, marques in dades["config"].items()}
        resultat[nivell] = dades
    return resultat


def llegeix_alliberaments(db: Session) -> dict:
    return alliberaments_amb_dates(llegeix_json(db, SCHEDULER_ALLIBERAMENTS_KEY, {}))


def metadata_amb_dates(metadata: dict | None) -> dict | None:
    if metadata is not None and "data_inici" in metadata:
        return dict(metadata, data_inici=data_desada(metadata["data_inici"]))
    return metadata


def horari_amb_dates(horari: dict) -> dict:
    """Llegeix les dates de l’horari, preservant els camps lliures de l’editor."""
    horari = horari.copy()
    if isinstance(horari.get("dies"), list):
        horari["dies"] = [
            dict(dia, data=data_desada(dia["data"])) if isinstance(dia, dict) and "data" in dia else dia
            for dia in horari["dies"]
        ]
    if isinstance(horari.get("metadata"), dict):
        horari["metadata"] = metadata_amb_dates(horari["metadata"])
    return horari


def resultat_amb_dates(document):
    if not isinstance(document, dict):
        return document
    resultat = document.get("resultat")
    if not isinstance(resultat, dict) or not isinstance(resultat.get("horari"), dict):
        return document
    return dict(document, resultat=dict(resultat, horari=horari_amb_dates(resultat["horari"])))


def document_iso(document):
    """Serialitza també les claus de data dels calendaris."""
    return jsonable_encoder(document, sqlalchemy_safe=False)
