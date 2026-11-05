"""Migració explícita amb serveis aturats; no carrega .env ni descobreix centres.

python -m scripts.migra_esquemes --comprova --auth /dades/auth.db --data /dades/prova/gestor.db
python -m scripts.migra_esquemes --aplica --backup-dir /copies/fase4 --data /dades/prova/gestor.db
"""

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from schema_migrations.runner import database_state, migrate_connection


def readonly_engine(path):
    uri = path.resolve().as_uri() + "?mode=ro"
    return create_engine("sqlite://", creator=lambda: sqlite3.connect(uri, uri=True), poolclass=NullPool)


def backup_database(path, destination):
    """API SQLite: còpia coherent, incloent-hi eventuals fitxers WAL."""
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Reservar nom sense sobreescriure cap còpia anterior.
    with destination.open("xb"):
        pass
    destination.chmod(0o600)
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as source:
        with sqlite3.connect(destination) as target:
            source.backup(target)


def run(databases, *, apply=False, backup_dir=None):
    paths = [path.resolve() for _, path in databases]
    if len(paths) != len(set(paths)):
        raise ValueError("La llista conté BD duplicades.")
    if apply and backup_dir is None:
        raise ValueError("Cal una carpeta de còpies.")
    states = []
    # Validar totes abans de tocar-ne cap. Mai crear una BD per un camí erroni.
    for kind, path in databases:
        if not path.is_file():
            raise ValueError("Falta una de les BD indicades.")
        engine = readonly_engine(path)
        try:
            with engine.connect() as connection:
                states.append(database_state(connection, kind))
        finally:
            engine.dispose()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    for number, ((kind, path), state) in enumerate(zip(databases, states, strict=True), 1):
        if apply and state != "vigent":
            backup_database(path, backup_dir / f"{timestamp}_{number}_{kind}.db")
            engine = create_engine(f"sqlite:///{path.resolve()}", poolclass=NullPool)
            try:
                with engine.connect() as connection:
                    try:
                        # SQLite no permet canviar foreign_keys dins del BEGIN.
                        # Evita ON DELETE CASCADE mentre es reconstrueixen pares.
                        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
                        connection.exec_driver_sql("BEGIN IMMEDIATE")
                        migrate_connection(connection, kind, allow_upgrade=True)
                        connection.commit()
                    except Exception:
                        connection.rollback()
                        raise
            finally:
                engine.dispose()
        print(f"BD {number} ({kind}): {state}" + (" → vigent" if apply else ""))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--comprova", action="store_true")
    mode.add_argument("--aplica", action="store_true", help="Només amb backend i reset de demo aturats")
    parser.add_argument("--auth", type=Path, action="append", default=[])
    parser.add_argument("--data", type=Path, action="append", default=[])
    parser.add_argument("--backup-dir", type=Path)
    args = parser.parse_args(argv)
    if not args.auth and not args.data:
        parser.error("Cal indicar almenys una BD amb --auth o --data")
    try:
        run(
            [("auth", p) for p in args.auth] + [("data", p) for p in args.data],
            apply=args.aplica,
            backup_dir=args.backup_dir,
        )
    except Exception:
        # No exposar camins de centres ni dades dins d’una excepció SQL.
        print(
            "ERROR: esquema desconegut o migració fallida. Restaureu una còpia compatible o demaneu ajuda; manteniu els serveis aturats.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
