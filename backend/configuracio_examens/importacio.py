"""Importació i exportació de la configuració d'exàmens: propostes a partir de
l'horari (XML), importació d'aquestes propostes o d'un CSV, amb un resum previ
que no escriu res, i exportació a CSV.

Amb «Sobreescriu» s'esborra tota la configuració d'exàmens abans d'importar.
Cada importació és tot o res: un sol commit al final, també el «Sobreescriu».
La simulació (resum previ) i la importació real són la mateixa funció: la
simulació fa la importació dins d'un savepoint i el desfà, de manera que
compta exactament igual (p. ex. una assignació sense titular que ja hi és)."""

import csv
import io

from sqlalchemy.orm import Session

from configuracio_examens.propostes import generar_propostes, nivells_amb_substitucions
from configuracio_examens.repositories import (
    ConfiguracioExamenRepository,
    MasterConfigRepository,
    PropostaDescartadaRepository,
)
from errors_domini import NoValid
from horari.repositories import ProfessorRepository
from nivells import deriva_nivell
from noms import neteja_noms

CSV_COLUMNES = ["nivell", "assignatura", "grup", "titular", "aula"]


def esborra_tota_la_configuracio(db: Session) -> None:
    """Esborra TOTA la configuració d'exàmens (nivells, grups, assignatures,
    aules i assignacions) de la institució actual. Fet servir per l'opció
    "Sobreescriu" de qualsevol dels diàlegs d'importació: en comptes de
    barrejar dades noves amb configuració mestra vella d'un XML anterior,
    comença sempre net. També oblida les propostes que s'havien descartat
    expressament (amb tot net, té sentit tornar-les a revisar de zero)."""
    ConfiguracioExamenRepository.delete_all(db)
    MasterConfigRepository.esborra_tot(db)
    PropostaDescartadaRepository.elimina_totes(db)
    db.flush()  # sense commit: va amb la importació, tot o res


def _resum(nivells, grups, assignatures, aules, assignacions, ja_existien, avisos) -> dict:
    return {
        "nivells_creats": nivells,
        "grups_creats": grups,
        "assignatures_creades": assignatures,
        "aules_creades": aules,
        "assignacions_creades": assignacions,
        "ja_existien": ja_existien,
        "avisos": avisos,
    }


# ---------------------------------------------------------------- des de l'XML


def propostes_de_l_horari(db: Session, horari) -> dict:
    """Propostes d'assignacions (assignatura/grup/titular/aula) a partir de
    l'horari, sense escriure res a la BD. `horari` ha de tenir tothom (les
    classes d'un titular amb una absència coberta també són del curs)."""
    propostes = generar_propostes(horari)

    # Descarta nivells que no s'usen mai a substitucions/vigilàncies
    # (Infantil/Primària a un IES, per exemple) perquè no s'omplin de
    # matèries que el centre no gestiona amb aquest mòdul.
    nivells_valids = nivells_amb_substitucions(db)
    if nivells_valids:
        propostes = [p for p in propostes if p["nivell"] in nivells_valids]

    existents = {(a["assignatura"], a["grup"], a["titular"]) for a in ConfiguracioExamenRepository.get_all(db)}
    descartades = PropostaDescartadaRepository.get_totes(db)
    for p in propostes:
        clau = (p["assignatura"], p["grup"], p["titular"])
        p["ja_existeix"] = clau in existents
        p["descartada"] = clau in descartades

    return {"propostes": propostes, "nivells_valids": sorted(nivells_valids)}


def _simula(db: Session, aplica) -> dict:
    """Fa la importació dins d'un savepoint i la desfà: el resum és el de la
    importació real, sense desar res."""
    punt = db.begin_nested()
    try:
        return aplica()
    finally:
        punt.rollback()


def impacte_propostes(db: Session, propostes: list[dict], overwrite: bool) -> dict:
    """Què crearia una llista de propostes (nivells/grups/assignatures/aules/
    assignacions noves, quantes ja existeixen, avisos), SENSE escriure res a
    la BD: el resum previ (dry-run). Compta com la importació real."""
    return _simula(db, lambda: _aplica_propostes(db, propostes, [], overwrite, simula=True))


def importa_propostes(db: Session, propostes: list[dict], descartades: list[dict], overwrite: bool) -> dict:
    """Aplica una llista de propostes: crea nivell/assignatura/grup/aula mestres si
    calen, i l'assignació (evitant duplicats exactes assignatura+grup+titular).
    `descartades`: propostes que l'usuari ha desmarcat expressament (no
    existeixen encara), perquè no es tornin a proposar marcades la propera
    vegada que s'obri el diàleg d'importació."""
    resum = _aplica_propostes(db, propostes, descartades, overwrite, simula=False)
    db.commit()
    return {"success": True, **resum}


def _aplica_propostes(
    db: Session, propostes: list[dict], descartades: list[dict], overwrite: bool, simula: bool
) -> dict:
    """La importació de propostes, sense commit."""
    if overwrite:
        esborra_tota_la_configuracio(db)

    no_es_fa = "no s'importarà" if simula else "no s'ha importat"
    propostes = [neteja_noms(p, "assignatura", "titular", "aula") for p in propostes]
    nivells_creats = []
    grups_creats = []
    assignatures_creades = []
    aules_creades = []
    assignacions_creades = []
    ja_existien = 0
    avisos = []

    for idx, p in enumerate(propostes, start=1):
        assignatura = (p.get("assignatura") or "").strip()
        grup = (p.get("grup") or "").strip()
        nivell = (p.get("nivell") or "").strip()
        titular = (p.get("titular") or "").strip() or None
        aula = (p.get("aula") or "").strip() or None

        if not assignatura or not grup or not nivell:
            falten = [n for n, v in [("assignatura", assignatura), ("grup", grup), ("nivell", nivell)] if not v]
            avisos.append(f"Proposta {idx}: falta {', '.join(falten)}, {no_es_fa}")
            continue

        # Si es torna a marcar una proposta que abans s'havia descartat,
        # deixa de considerar-se descartada.
        PropostaDescartadaRepository.elimina(db, assignatura, grup, titular)

        if MasterConfigRepository.add_nivell(db, nivell):
            nivells_creats.append(nivell)
        if MasterConfigRepository.add_assignatura(db, nivell, assignatura):
            assignatures_creades.append(f"{assignatura} ({nivell})")
        if MasterConfigRepository.add_grup(db, nivell, grup):
            grups_creats.append(f"{grup} ({nivell})")
        if aula and MasterConfigRepository.add_aula(db, aula):
            aules_creades.append(aula)

        if ConfiguracioExamenRepository.existeix(db, assignatura, grup, titular):
            ja_existien += 1
            continue

        ConfiguracioExamenRepository.create(db, assignatura, grup, titular, aula)
        assignacions_creades.append(f"{assignatura} – {grup}" + (f" ({titular})" if titular else ""))

    for d in descartades:
        assignatura = (d.get("assignatura") or "").strip()
        grup = (d.get("grup") or "").strip()
        titular = (d.get("titular") or "").strip() or None
        if assignatura and grup:
            PropostaDescartadaRepository.marca(db, assignatura, grup, titular)

    return _resum(
        nivells_creats, grups_creats, assignatures_creades, aules_creades, assignacions_creades, ja_existien, avisos
    )


# ---------------------------------------------------------------- CSV


def exporta_csv(db: Session) -> str:
    """Totes les assignacions, amb el nivell real de cada grup (des de la
    taula mestra), perquè el fitxer es pugui reimportar sense ambigüitat."""
    nivell_per_grup = MasterConfigRepository.nivell_per_grup(db)

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNES)
    writer.writeheader()
    for a in ConfiguracioExamenRepository.get_all(db):
        nivell = nivell_per_grup.get(a["grup"]) or deriva_nivell(a["grup"])
        writer.writerow({"nivell": nivell, **{k: a.get(k, "") for k in CSV_COLUMNES if k != "nivell"}})
    return buffer.getvalue()


def llegeix_csv(nom_fitxer: str | None, contingut: bytes) -> list[tuple]:
    """Comprova que el fitxer és un CSV amb columnes reconegudes i en
    retorna les files (num_línia, fila) llestes per processar."""
    if not (nom_fitxer or "").endswith(".csv"):
        raise NoValid("El fitxer ha de ser CSV", codi="csv_extensio")

    try:
        text = contingut.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise NoValid("El fitxer CSV ha d'estar desat en UTF-8", codi="csv_no_utf8") from None
    reader = csv.DictReader(io.StringIO(text))

    columnes_conegudes = {"nivell", "assignatura", "grup", "titular", "aula"}
    if not columnes_conegudes.intersection(reader.fieldnames or []):
        raise NoValid(
            f"El CSV ha de tenir com a mínim una d'aquestes columnes: {', '.join(sorted(columnes_conegudes))}",
            codi="csv_sense_columnes",
        )

    # línia 1 = capçalera; els noms, nets (noms.py)
    return [(n, neteja_noms(fila, "assignatura", "titular", "aula")) for n, fila in enumerate(reader, start=2)]


def impacte_csv(db: Session, files_rows: list[tuple], overwrite: bool) -> dict:
    """Què faria una importació CSV, SENSE escriure res: el resum previ.
    Compta com la importació real."""
    return _simula(db, lambda: _aplica_csv(db, files_rows, overwrite, simula=True))


def importa_csv(db: Session, files_rows: list[tuple], overwrite: bool) -> dict:
    """Importa les files d'un CSV (columnes: nivell,assignatura,grup,titular,aula).
    nivell, assignatura i grup són obligatoris (cap valor es dedueix ni
    s'inventa): si en falta algun, la fila es descarta sencera amb un avís.
    titular i aula són opcionals, però si es dona un titular que no existeix
    a la BD, la fila també es descarta sencera (no es crea a mitges sense
    titular). Una fila totalment buida s'ignora."""
    resum = _aplica_csv(db, files_rows, overwrite, simula=False)
    db.commit()
    return {"success": True, **resum}


def _aplica_csv(db: Session, files_rows: list[tuple], overwrite: bool, simula: bool) -> dict:
    """La importació d'un CSV, sense commit."""
    if overwrite:
        esborra_tota_la_configuracio(db)

    no_es_fa = "no s'importarà" if simula else "no s'ha importat"
    nivells_creats = []
    grups_creats = []
    assignatures_creades = []
    aules_creades = []
    assignacions_creades = []
    ja_existien = 0
    avisos = []

    for num_fila, fila in files_rows:
        assignatura = (fila.get("assignatura") or "").strip()
        grup = (fila.get("grup") or "").strip()
        titular_csv = (fila.get("titular") or "").strip() or None
        aula = (fila.get("aula") or "").strip()
        nivell = (fila.get("nivell") or "").strip()

        if not any([nivell, grup, assignatura, titular_csv, aula]):
            continue  # fila totalment buida, no cal ni avisar

        falten = [
            camp for camp, valor in [("nivell", nivell), ("assignatura", assignatura), ("grup", grup)] if not valor
        ]
        if falten:
            avisos.append(f"Línia {num_fila}: falten camps obligatoris ({', '.join(falten)}), {no_es_fa}")
            continue

        if titular_csv and not ProfessorRepository.existeix(db, titular_csv):
            avisos.append(f"Línia {num_fila}: professor «{titular_csv}» no trobat, {no_es_fa} aquesta línia")
            continue

        if MasterConfigRepository.add_nivell(db, nivell):
            nivells_creats.append(nivell)
        if aula and MasterConfigRepository.add_aula(db, aula):
            aules_creades.append(aula)
        if MasterConfigRepository.add_grup(db, nivell, grup):
            grups_creats.append(f"{grup} ({nivell})")
        if MasterConfigRepository.add_assignatura(db, nivell, assignatura):
            assignatures_creades.append(f"{assignatura} ({nivell})")

        if ConfiguracioExamenRepository.existeix(db, assignatura, grup, titular_csv):
            ja_existien += 1
        else:
            ConfiguracioExamenRepository.create(db, assignatura, grup, titular_csv, aula or None)
            assignacions_creades.append(f"{assignatura} – {grup}" + (f" ({titular_csv})" if titular_csv else ""))

    return _resum(
        nivells_creats, grups_creats, assignatures_creades, aules_creades, assignacions_creades, ja_existien, avisos
    )
