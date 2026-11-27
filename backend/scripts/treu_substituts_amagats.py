"""Neteja les assignacions de les files amagades per alliberament o «No substituir».

    DATA_DIR=/ruta/dades python -m scripts.treu_substituts_amagats --recompte
    DATA_DIR=/ruta/dades python -m scripts.treu_substituts_amagats --aplica

El recompte mostra cinc números per línia: ordinal del centre, files amb
substitut que es buidaran per alliberament, files amb substitut que es buidaran
per «No substituir» vigent, encadenades que quedaran òrfenes els dies afectats
i dates amb files sense horari. Si coincideixen els dos motius, la fila compta
per alliberament. Sense horari, s'avaluen les marques diàries i «No substituir».
"""

import argparse
import logging
import sys
from collections import Counter
from contextvars import copy_context
from datetime import date

import database
from config.context import fixa_institucio_peticio
from horari.domain import Dia
from prioritats.memoria import carrega_prioritats
from prioritats.repositories import NoSubstituirRepository
from substitucions.domain import DiaEscolar
from substitucions.encadenades import activitat_encadenada, reconcilia_encadenades
from substitucions.repositories import SubstitucioRepository
from substitucions.visibilitat import motiu_per_amagar


def _orfenes(db, dia: DiaEscolar, ids_buidats: set[str]) -> int:
    no_substituir = NoSubstituirRepository.vigents_a(db, dia.data)
    mares = {
        (fila.hora, fila.substitut.strip(), activitat)
        for fila in dia.files
        if fila.id not in ids_buidats
        and fila.tipus_absencia != "ENCADENADA"
        and fila.substitut.strip()
        and (activitat := activitat_encadenada(fila.tipus_substitut, no_substituir))
    }
    return sum(
        fila.tipus_absencia == "ENCADENADA" and (fila.hora, fila.professor_absent, fila.assignatura) not in mares
        for fila in dia.files
    )


def _processa_centre(centre: str, aplica: bool) -> tuple[int, int, int, int]:
    fixa_institucio_peticio(centre)
    recompte = Counter()
    orfenes = sense_horari = 0
    with database.get_data_db_session(centre, nomes_lectura=not aplica) as db:
        carrega_prioritats(db)
        for data in sorted(SubstitucioRepository.dates_entre(db, date.min.isoformat(), date.max.isoformat())):
            dia = DiaEscolar(db, Dia(data, centre))
            no_substituir = NoSubstituirRepository.vigents_a(db, dia.data)
            amagades = [
                (fila, motiu)
                for fila in dia.files
                if (fila.substitut or fila.tipus_substitut)
                and (motiu := motiu_per_amagar(fila, no_substituir, dia.alliberats.get(fila.hora, ())))
            ]
            if aplica:
                for fila, _ in amagades:
                    SubstitucioRepository.update(db, int(fila.id), {"substitut": "", "tipus_substitut": ""})
                if amagades:
                    reconcilia_encadenades(db, dia.data)
            else:
                sense_horari += dia.horari is None
                recompte.update(motiu for fila, motiu in amagades if fila.substitut)
                if amagades:
                    orfenes += _orfenes(db, dia, {fila.id for fila, _ in amagades})
        if aplica:
            db.commit()
    return recompte["alliberament"], recompte["no_substituir"], orfenes, sense_horari


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--recompte", action="store_true")
    mode.add_argument("--aplica", action="store_true")
    args = parser.parse_args(argv)

    nivell_logs = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        centres = sorted(
            cami.parent.name
            for cami in database.DATA_BASE_DIR.glob("*/gestor.db")
            if cami.is_file() and not cami.parent.name.startswith("__")
        )
        for ordinal, centre in enumerate(centres, 1):
            resultat = copy_context().run(_processa_centre, centre, args.aplica)
            if args.recompte:
                print(ordinal, *resultat)
    except Exception:
        print("Error en processar les bases de dades.", file=sys.stderr)
        return 1
    finally:
        logging.disable(nivell_logs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
