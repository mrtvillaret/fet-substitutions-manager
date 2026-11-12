"""Inicialització idempotent; upgrades existents només amb l’script explícit."""

from pathlib import Path
from threading import RLock

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from schema_migrations.schema import (
    BASE_REVISION,
    CANONICAL_REVISION,
    CLEAN_REVISION,
    CURRENT_REVISION,
    create_base,
    validate_base,
    validate_current,
    validate_historical,
)

_migration_lock = RLock()  # Alembic també usa proxies globals dins del procés.


def alembic_config(connection, kind):
    if kind not in {"auth", "data"}:
        raise ValueError("Tipus de BD desconegut")
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parent))
    config.attributes.update(connection=connection, kind=kind)
    return config


def database_state(connection, kind):
    config = alembic_config(connection, kind)
    heads = MigrationContext.configure(connection).get_current_heads()
    head = ScriptDirectory.from_config(config).get_current_head()
    if not heads:
        tables = set(inspect(connection).get_table_names()) - {"alembic_version"}
        if not tables:
            # Una vista sola tampoc no és una BD nova.
            validate_empty = inspect(connection).get_view_names()
            if validate_empty:
                raise RuntimeError("La BD conté objectes inesperats.")
            return "nova"
        validate_base(connection, kind)
        return "sense versió"
    if heads == (head,):
        if head == CURRENT_REVISION:
            validate_current(connection, kind)
        return "vigent"
    if len(heads) != 1 or ScriptDirectory.from_config(config).get_revision(heads[0]) is None:
        raise RuntimeError("Versió de BD desconeguda.")
    if heads == (BASE_REVISION,):
        validate_base(connection, kind)
    elif heads == (CLEAN_REVISION,):
        validate_historical(connection, kind, cleaned=True)
    elif heads == (CANONICAL_REVISION,):
        validate_base(connection, kind, historical=False)
    elif heads == (CURRENT_REVISION,):
        validate_current(connection, kind)
    return "pendent"


def migrate_connection(connection, kind, *, allow_upgrade=False):
    with _migration_lock:
        return _migrate_connection(connection, kind, allow_upgrade=allow_upgrade)


def _migrate_connection(connection, kind, *, allow_upgrade):
    state = database_state(connection, kind)
    config = alembic_config(connection, kind)
    if state == "nova":
        create_base(connection, kind)
        command.stamp(config, BASE_REVISION)
    elif state == "sense versió":
        # L’adopció només estampa; les revisions següents normalitzen l’esquema.
        command.stamp(config, BASE_REVISION)
    if state != "vigent":
        current = MigrationContext.configure(connection).get_current_heads()
        head = ScriptDirectory.from_config(config).get_current_head()
        if current != (head,):
            if not allow_upgrade and state != "nova":
                raise RuntimeError("Migracions pendents: atureu el backend i executeu scripts.migra_esquemes.")
            command.upgrade(config, "head")
    return state


def initialize_database(engine, kind):
    # BEGIN explícit: sqlite3 legacy no inicia transacció amb DDL. IMMEDIATE
    # serialitza també dos workers que intentin crear/stampar la mateixa BD.
    with engine.connect().execution_options(sqlite_manual_begin=True) as connection:
        try:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            migrate_connection(connection, kind)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
