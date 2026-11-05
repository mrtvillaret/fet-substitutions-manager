"""Fixtures SQLite històriques amb dades exclusivament inventades."""

import json
import sqlite3
from pathlib import Path

HISTORY = json.loads(Path(__file__).with_name("schema_history.json").read_text())


def create_snapshot(path, snapshot):
    with sqlite3.connect(path) as connection:
        for variant in snapshot["tables"].values():
            for statement in HISTORY["tables"][variant]:
                connection.execute(statement)
        seed_rows(connection)


def seed_rows(connection):
    """Tres files per taula, amb NULL, zeros, valors no predeterminats i FK reals."""
    tables = connection.execute(
        "SELECT name FROM sqlite_schema WHERE type='table' AND name!='sqlite_sequence'"
    ).fetchall()
    for (table,) in tables:
        columns = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
        foreign_keys = {r[3] for r in connection.execute(f'PRAGMA foreign_key_list("{table}")')}
        names = ", ".join(f'"{r[1]}"' for r in columns)
        placeholders = ", ".join("?" for _ in columns)
        for number, ident in enumerate((1, 7, 31)):
            row = []
            for _, name, kind, required, _default, pk in columns:
                if pk and kind == "INTEGER" or name in foreign_keys:
                    value = ident
                elif not required and not pk and number == 0:
                    value = None
                elif kind in {"INTEGER", "BOOLEAN"}:
                    value = (0, 1, 23)[number]
                elif kind == "DATE":
                    value = f"2026-01-{ident:02d}"
                elif kind in {"DATETIME", "TIMESTAMP"}:
                    value = f"2026-01-{ident:02d} 12:34:56.123456"
                else:
                    value = f"Prova {name} {ident}: àèíòü ' \n"
                row.append(value)
            connection.execute(f'INSERT INTO "{table}" ({names}) VALUES ({placeholders})', row)


def table_rows(connection, table):
    columns = sorted(r[1] for r in connection.execute(f'PRAGMA table_info("{table}")'))
    projection = ", ".join(f'"{name}"' for name in columns)
    return columns, connection.execute(f'SELECT {projection} FROM "{table}" ORDER BY rowid').fetchall()


def preserved_rows(path):
    with sqlite3.connect(path) as connection:
        names = connection.execute(
            "SELECT name FROM sqlite_schema WHERE type='table' AND name NOT IN ('alembic_version', 'sqlite_sequence')"
        ).fetchall()
        return {name: table_rows(connection, name) for (name,) in names}


def assert_preserved(before, after):
    for name, (columns, rows) in before.items():
        if name in {"configuracio_assignatures", "exam_schedules"}:
            continue  # Neteja de la 0002, conservada íntegra a la còpia.
        new_columns, new_rows = after[name]
        aliases = (
            {"grups_origen": "grups_originals", "grup_abreviat": "abreviatura"} if name == "abreviatures_grups" else {}
        )
        positions = [new_columns.index(aliases.get(c, c)) for c in columns]
        assert [tuple(row[i] for i in positions) for row in new_rows] == rows, name
