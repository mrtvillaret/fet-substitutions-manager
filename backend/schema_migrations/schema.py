"""Instantànies immutables: esquema canònic i entrades històriques conegudes."""

import json
import re
from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine, inspect

BASE_REVISION = "0001_base"
CLEAN_REVISION = "0002_neteja_historiques"
CANONICAL_REVISION = "0003_esquema_canonic"
# La 0004 només canvia no_substituir (vigència per dates).
VIGENCIA_REVISION = "0004_vigencia_no_substituir"
# La 0005 treu les taules LEGACY; és la revisió vigent.
CURRENT_REVISION = "0005_fora_taules_legacy"
# Taules que cap codi no llegeix des que es van passar a exam_restriccions.
LEGACY_TABLES = ("exam_preferencies", "exam_pesos_optimitzacio")
SCHEMA_OBJECTS = ("objects",)
RETIRED_TABLES = frozenset({"users", "configuracio_assignatures", "exam_schedules"})
SCHEMA_ERROR = (
    "L’esquema és desconegut; no s’ha modificat la BD. "
    "Restaureu una còpia compatible o demaneu ajuda abans de tornar a migrar."
)


def base_statements(kind):
    return json.loads(Path(__file__).with_name("base_schema.json").read_text())[kind]


def create_base(connection, kind):
    for statement in base_statements(kind):
        connection.exec_driver_sql(statement)


def table_definition(sql):
    """Només ignora espais SQL; preserva ordre, defaults, literals i restriccions."""
    return tuple(re.findall(r"'(?:(?:'')|[^'])*'|\"(?:(?:\"\")|[^\"])*\"|`[^`]*`|\[[^]]*\]|\w+|[^\s]", sql))


def schema_signature(connection):
    inspector = inspect(connection)
    result = {}
    for table in inspector.get_table_names():
        if table in {"alembic_version", "sqlite_sequence"}:
            continue
        quoted = '"' + table.replace('"', '""') + '"'
        columns = tuple(tuple(row[1:]) for row in connection.exec_driver_sql(f"PRAGMA table_xinfo({quoted})"))
        indexes = []
        for _, name, unique, origin, partial in connection.exec_driver_sql(f"PRAGMA index_list({quoted})"):
            index_quoted = '"' + name.replace('"', '""') + '"'
            parts = tuple(
                (seq, col, desc, coll, key)
                for seq, _cid, col, desc, coll, key in connection.exec_driver_sql(f"PRAGMA index_xinfo({index_quoted})")
            )
            sql = connection.exec_driver_sql("SELECT sql FROM sqlite_schema WHERE name = ?", (name,)).scalar()
            indexes.append((name if origin == "c" else "", unique, origin, partial, parts, sql))
        result[table] = (
            columns,
            tuple(sorted(indexes)),
            tuple(sorted(tuple(row) for row in connection.exec_driver_sql(f"PRAGMA foreign_key_list({quoted})"))),
            tuple(sorted(c["sqltext"] for c in inspector.get_check_constraints(table))),
            table_definition(
                connection.exec_driver_sql(
                    "SELECT sql FROM sqlite_schema WHERE type = 'table' AND name = ?", (table,)
                ).scalar()
            ),
        )
    objects = connection.exec_driver_sql(
        "SELECT type, name, sql FROM sqlite_schema WHERE type IN ('view', 'trigger') ORDER BY type, name"
    ).fetchall()
    result[SCHEMA_OBJECTS] = tuple(tuple(row) for row in objects)
    return result


@lru_cache(maxsize=2)
def base_signature(kind):
    return _signature_of(base_statements(kind))


def vigencia_statements(kind):
    """DDL congelat de la 0004: no_substituir amb vigència i sense unicitat."""
    return json.loads(Path(__file__).with_name("vigencia_schema.json").read_text()).get(kind, [])


def _sense_taules(statements, tables):
    """Les sentències que no creen cap d’aquestes taules ni cap índex seu."""
    return [
        s
        for s in statements
        if not (s.startswith("CREATE TABLE ") and s.split()[2] in tables)
        and not (s.startswith(("CREATE INDEX ", "CREATE UNIQUE INDEX ")) and s.split(" ON ", 1)[1].split()[0] in tables)
    ]


def vigencia_schema_statements(kind):
    """L’esquema de la 0004: la base (0001–0003) amb no_substituir refeta."""
    replaced = vigencia_statements(kind)
    tables = {s.split()[2] for s in replaced if s.startswith("CREATE TABLE ")}
    return _sense_taules(base_statements(kind), tables) + replaced


def current_statements(kind):
    """L’esquema vigent: el de la 0004 sense les taules LEGACY (0005)."""
    return _sense_taules(vigencia_schema_statements(kind), LEGACY_TABLES)


def _signature_of(statements):
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            for statement in statements:
                connection.exec_driver_sql(statement)
            return schema_signature(connection)
    finally:
        engine.dispose()


@lru_cache(maxsize=2)
def vigencia_signature(kind):
    return _signature_of(vigencia_schema_statements(kind))


@lru_cache(maxsize=2)
def current_signature(kind):
    return _signature_of(current_statements(kind))


def validate_vigencia(connection, kind):
    if schema_signature(connection) != vigencia_signature(kind):
        raise RuntimeError(SCHEMA_ERROR)


def validate_current(connection, kind):
    if schema_signature(connection) != current_signature(kind):
        raise RuntimeError(SCHEMA_ERROR)


@lru_cache(maxsize=1)
def historical_catalog():
    return json.loads(Path(__file__).with_name("historical_schema.json").read_text())


@lru_cache(maxsize=1)
def historical_signatures():
    result = {}
    for statements in historical_catalog()["tables"]:
        engine = create_engine("sqlite://")
        try:
            with engine.begin() as connection:
                for statement in statements:
                    connection.exec_driver_sql(statement)
                signature = schema_signature(connection)
                signature.pop(SCHEMA_OBJECTS)
                for name, definition in signature.items():
                    result.setdefault(name, set()).add(definition)
        finally:
            engine.dispose()
    return result


def validate_historical(connection, kind, *, cleaned=False):
    """Llista tancada de formes de taula i conjunts de taules creats a l’historial.

    Només per al preflight i les revisions 0002/0003; mai per declarar vigent
    una BD. Admet mescles de formes conegudes: create_all no refèia taules.
    """
    actual = schema_signature(connection)
    if actual.pop(SCHEMA_OBJECTS):
        raise RuntimeError(SCHEMA_ERROR)
    names = set(actual)
    if kind == "auth":
        valid_names = names == {"users"}
    else:
        valid_names = sorted(names - RETIRED_TABLES) in historical_catalog()["data_table_sets"]
        if cleaned and names.intersection(RETIRED_TABLES):
            valid_names = False
    known = historical_signatures()
    for name, definition in actual.items():
        if definition not in known.get(name, set()):
            raise RuntimeError(SCHEMA_ERROR)
        if kind == "data" and name == "users" and any(c[0] == "versio_sessio" for c in definition[0]):
            valid_names = False
    if cleaned and kind == "data":
        if not any(i[0] == "idx_configuracio_clau" for i in actual.get("configuracio", ((), ()))[1]):
            valid_names = False
    if not valid_names:
        raise RuntimeError(SCHEMA_ERROR)


def validate_base(connection, kind, *, historical=True):
    if historical:
        validate_historical(connection, kind)
    elif schema_signature(connection) != base_signature(kind):
        raise RuntimeError(SCHEMA_ERROR)
