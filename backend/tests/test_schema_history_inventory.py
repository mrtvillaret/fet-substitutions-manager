"""Cada forma històrica exacta arriba al canònic amb els mateixos valors."""

import sqlite3

import pytest
from suport_schema_history import HISTORY, assert_preserved, create_snapshot, preserved_rows, table_rows


@pytest.mark.parametrize("snapshot", HISTORY["snapshots"], ids=lambda s: s["id"])
def test_frozen_historical_ddl_with_synthetic_rows(tmp_path, snapshot):
    path = tmp_path / "inventada.db"
    create_snapshot(path, snapshot)
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        for table in snapshot["tables"]:
            assert len(table_rows(connection, table)[1]) == 3


@pytest.mark.parametrize("snapshot", HISTORY["snapshots"], ids=lambda s: s["id"])
@pytest.mark.parametrize("completed", ["original", "create_all", "ensure"])
def test_every_historical_snapshot_reaches_canonical_with_same_values(tmp_path, snapshot, completed):
    from sqlalchemy import create_engine

    from models import Base
    from schema_migrations.runner import database_state
    from schema_migrations.schema import base_statements, current_signature, schema_signature
    from scripts.migra_esquemes import main

    path = tmp_path / "inventada.db"
    data_snapshot = {**snapshot, "tables": {k: v for k, v in snapshot["tables"].items() if k != "users"}}
    create_snapshot(path, data_snapshot)
    if completed != "original":
        engine = create_engine(f"sqlite:///{path}")
        # Els models d'abans de la 0004: no_substituir, amb la forma congelada de la base.
        Base.metadata.create_all(
            engine, tables=[t for t in Base.metadata.sorted_tables if t.name not in {"users", "no_substituir"}]
        )
        with engine.begin() as connection:
            if "no_substituir" not in schema_signature(connection):
                for statement in base_statements("data"):
                    if statement.startswith("CREATE TABLE no_substituir "):
                        connection.exec_driver_sql(statement)
        engine.dispose()
    if completed == "ensure":
        with sqlite3.connect(path) as connection:
            for table, column, ddl in (
                ("substitucions", "aula", "aula VARCHAR"),
                ("vigilancies", "ordre", "ordre INTEGER"),
            ):
                if column not in {r[1] for r in connection.execute(f'PRAGMA table_info("{table}")')}:
                    connection.execute(f'ALTER TABLE "{table}" ADD COLUMN {ddl}')
    before = preserved_rows(path)
    original = path.read_bytes()
    assert main(["--comprova", "--data", str(path)]) == 0
    assert path.read_bytes() == original
    copies = tmp_path / "copies"
    assert main(["--aplica", "--data", str(path), "--backup-dir", str(copies)]) == 0
    assert_preserved(before, preserved_rows(path))
    assert preserved_rows(next(copies.glob("*.db"))) == before
    engine = create_engine(f"sqlite:///{path}")
    with engine.connect() as connection:
        assert schema_signature(connection) == current_signature("data")
        assert database_state(connection, "data") == "vigent"
        assert connection.exec_driver_sql("PRAGMA integrity_check").scalar() == "ok"
        assert not connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
    engine.dispose()
    migrated = path.read_bytes()
    assert main(["--aplica", "--data", str(path), "--backup-dir", str(copies)]) == 0
    assert path.read_bytes() == migrated
    assert len(list(copies.glob("*.db"))) == 1


@pytest.mark.parametrize("variant", HISTORY["tables"])
def test_each_exact_table_shape_and_rows_after_0003(tmp_path, variant):
    from alembic import command
    from sqlalchemy import create_engine

    from schema_migrations.runner import alembic_config
    from schema_migrations.schema import BASE_REVISION, CLEAN_REVISION, current_signature, schema_signature
    from scripts.migra_esquemes import main

    statements = HISTORY["tables"][variant]
    name = statements[0].split("(", 1)[0].split()[-1]
    kind = "auth" if name == "users" else "data"
    path = tmp_path / "forma_exacta.db"
    canonical = HISTORY["snapshots"][0]["tables"]
    snapshot = {"tables": {k: v for k, v in canonical.items() if (k == "users") == (kind == "auth")}}
    snapshot["tables"][name] = variant
    create_snapshot(path, snapshot)
    engine = create_engine(f"sqlite:///{path}")
    # Aïllar la 0003: la 0002 neteja abans; la instantània de contingut és posterior.
    with engine.connect() as connection:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        config = alembic_config(connection, kind)
        command.stamp(config, BASE_REVISION)
        command.upgrade(config, CLEAN_REVISION)
        connection.commit()
    before = preserved_rows(path)
    copies = tmp_path / "copies"
    assert main(["--aplica", f"--{kind}", str(path), "--backup-dir", str(copies)]) == 0
    after = preserved_rows(path)
    assert_preserved(before, after)
    # Totes les files i valors, també NULL/0/1, quan no s’afegeixen columnes.
    for table in before:
        if before[table][0] == after[table][0]:
            assert before[table] == after[table]
    with engine.connect() as connection:
        assert schema_signature(connection) == current_signature(kind)
        assert not connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
    engine.dispose()
