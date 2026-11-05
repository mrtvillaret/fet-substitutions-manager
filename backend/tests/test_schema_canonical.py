"""La 0003 convergeix exactament i cap fallada pot deixar una còpia parcial."""

import json
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from suport_schema_history import HISTORY, create_snapshot, preserved_rows
from test_schema_historical import historical_database
from test_schema_migrations import legacy_database

from schema_migrations.runner import database_state, initialize_database
from schema_migrations.schema import (
    BASE_REVISION,
    CANONICAL_REVISION,
    CLEAN_REVISION,
    base_signature,
    create_base,
    schema_signature,
)
from scripts.migra_esquemes import main, run


@pytest.mark.parametrize("variant", HISTORY["tables"])
def test_0003_stamp_accepts_only_exact_canonical_tables(tmp_path, variant):
    statements = HISTORY["tables"][variant]
    name = statements[0].split("(", 1)[0].split()[-1]
    kind = "auth" if name == "users" else "data"
    canonical = HISTORY["snapshots"][0]["tables"]
    snapshot = {"tables": {k: v for k, v in canonical.items() if (k == "users") == (kind == "auth")}}
    snapshot["tables"][name] = variant
    path = tmp_path / "estampada.db"
    create_snapshot(path, snapshot)
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        matches = schema_signature(connection) == base_signature(kind)
        connection.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)")
        connection.exec_driver_sql("INSERT INTO alembic_version VALUES (?)", (CANONICAL_REVISION,))
    before = path.read_bytes()
    copies = tmp_path / "copies"
    assert main(["--comprova", f"--{kind}", str(path)]) == (0 if matches else 1)
    assert main(["--aplica", f"--{kind}", str(path), "--backup-dir", str(copies)]) == (0 if matches else 1)
    if matches:
        initialize_database(engine, kind)
    else:
        with pytest.raises(RuntimeError, match="Restaureu.*demaneu ajuda"):
            initialize_database(engine, kind)
    assert path.read_bytes() == before
    assert not copies.exists()
    engine.dispose()


@pytest.mark.parametrize("kind", ["auth", "data"])
def test_matching_tables_are_never_rebuilt(tmp_path, kind):
    path = tmp_path / "canonica.db"
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        create_base(connection, kind)
    before = preserved_rows(path)
    statements = []

    def record(connection, cursor, statement, parameters, context, executemany):
        if connection.engine.url.database == str(path):
            statements.append(statement.strip().upper())

    event.listen(Engine, "before_cursor_execute", record)
    try:
        run([(kind, path)], apply=True, backup_dir=tmp_path / "copies")
    finally:
        event.remove(Engine, "before_cursor_execute", record)
    assert not any(s.startswith(("DROP TABLE", "ALTER TABLE", "INSERT INTO _MIGRA3")) for s in statements)
    assert preserved_rows(path) == before
    engine.dispose()


@pytest.mark.parametrize(
    "kind, point",
    [
        (kind, point)
        for kind in ("auth", "data")
        for point in ("before_drop", "after_drop", "after_create", "after_copy", "index")
        if (kind, point) != ("auth", "index")
    ],
)
def test_0003_failure_rolls_back_ddl_rows_and_version(tmp_path, kind, point):
    path = tmp_path / "inventada.db"
    engine = legacy_database(path, kind)
    before = path.read_bytes()
    rows_before = preserved_rows(path)
    table = "users" if kind == "auth" else "substitucions"
    starts = {
        "before_drop": f"DROP TABLE {table}",
        "after_drop": f"CREATE TABLE {table} (",
        "after_create": f"INSERT INTO {table} (",
        "after_copy": f"DROP TABLE _migra3_{table}",
        "index": "CREATE INDEX idx_substitucions",
    }
    reached = []

    def fail(connection, cursor, statement, parameters, context, executemany):
        if connection.engine.url.database == str(path) and statement.strip().replace('"', "").startswith(starts[point]):
            reached.append(True)
            raise RuntimeError("fallada simulada")

    event.listen(Engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError, match="fallada simulada"):
            run([(kind, path)], apply=True, backup_dir=tmp_path / "copies")
    finally:
        event.remove(Engine, "before_cursor_execute", fail)
    assert reached == [True]
    assert path.read_bytes() == before
    assert preserved_rows(path) == rows_before
    backup = next((tmp_path / "copies").glob("*.db"))
    assert preserved_rows(backup) == rows_before
    with engine.connect() as connection:
        assert database_state(connection, kind) == "sense versió"
    engine.dispose()


@pytest.mark.parametrize("kind", ["auth", "data"])
def test_ensure_variants_normalize_column_order_defaults_and_all_values(tmp_path, kind):
    path = tmp_path / "alters.db"
    engine = legacy_database(path, kind)
    before = preserved_rows(path)
    run([(kind, path)], apply=True, backup_dir=tmp_path / "copies")
    assert preserved_rows(path) == before
    # Comparació independent del validador de producció, inclòs SQL i ordre.
    reference = create_engine("sqlite://")
    sql = "SELECT type, name, tbl_name, sql FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%' AND name != 'alembic_version' ORDER BY type, name"
    with reference.begin() as connection, engine.connect() as migrated:
        create_base(connection, kind)
        assert migrated.exec_driver_sql(sql).fetchall() == connection.exec_driver_sql(sql).fetchall()
    engine.dispose()
    reference.dispose()


@pytest.mark.parametrize("revision", [None, BASE_REVISION, CLEAN_REVISION, CANONICAL_REVISION])
def test_unknown_column_order_is_rejected_before_any_write(tmp_path, revision, capsys):
    path = tmp_path / "no_mostris_el_cami.db"
    statements = json.loads((Path(__file__).parents[1] / "schema_migrations/base_schema.json").read_text())["data"]
    with sqlite3.connect(path) as connection:
        for statement in statements:
            connection.execute(
                statement.replace("assignatura VARCHAR, \n\tgrup VARCHAR,", "grup VARCHAR, \n\tassignatura VARCHAR,")
            )
        if revision:
            connection.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)")
            connection.execute("INSERT INTO alembic_version VALUES (?)", (revision,))
    before = path.read_bytes()
    copies = tmp_path / "copies"
    assert main(["--aplica", "--data", str(path), "--backup-dir", str(copies)]) == 1
    assert path.read_bytes() == before
    assert not copies.exists()
    output = capsys.readouterr()
    assert "Restaureu" in output.err and "demaneu ajuda" in output.err
    assert str(path) not in output.out + output.err
    assert "substitucions" not in output.err


@pytest.mark.parametrize("revision", [None, BASE_REVISION, CLEAN_REVISION])
def test_default_variants_with_non_default_values_are_preserved(tmp_path, revision):
    path = tmp_path / "defaults.db"
    engine = historical_database(path, ("assignatures_prioritat",), stamped=revision or False)
    with engine.begin() as connection:
        connection.exec_driver_sql("UPDATE assignatures_prioritat SET auto_assignada = 23 WHERE auto_assignada = 1")
    before = preserved_rows(path)
    run([("data", path)], apply=True, backup_dir=tmp_path / "copies")
    assert preserved_rows(path) == before
    engine.dispose()


@pytest.mark.parametrize("variant", ["ensure_auth", "ensure_data", "default", "assignatures_prioritat"])
def test_a_historical_alter_is_never_current_with_0003_stamp(tmp_path, variant):
    path = tmp_path / "alter_estampat.db"
    kind = "auth" if variant == "ensure_auth" else "data"
    engine = legacy_database(path, kind) if variant.startswith("ensure_") else historical_database(path, (variant,))
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)")
        connection.exec_driver_sql("INSERT INTO alembic_version VALUES (?)", (CANONICAL_REVISION,))
    before = path.read_bytes()
    with engine.connect() as connection, pytest.raises(RuntimeError, match="esquema"):
        database_state(connection, kind)
    assert main(["--aplica", f"--{kind}", str(path), "--backup-dir", str(tmp_path / "copies")]) == 1
    assert path.read_bytes() == before
    assert not (tmp_path / "copies").exists()
    engine.dispose()


def test_copy_preserves_blob_storage_and_sparse_rowids(tmp_path):
    snapshot = next(s for s in HISTORY["snapshots"] if s["id"] == "json_sqlite")
    path = tmp_path / "binaria.db"
    create_snapshot(path, snapshot)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE configuracio SET rowid = rowid + 100")
        connection.execute("UPDATE configuracio SET valor = ?", (sqlite3.Binary(b"\x00\xff'\n"),))
        before = connection.execute(
            "SELECT rowid, clau, valor, typeof(valor) FROM configuracio ORDER BY rowid"
        ).fetchall()
    run([("data", path)], apply=True, backup_dir=tmp_path / "copies")
    with sqlite3.connect(path) as connection:
        assert (
            connection.execute("SELECT rowid, clau, valor, typeof(valor) FROM configuracio ORDER BY rowid").fetchall()
            == before
        )
