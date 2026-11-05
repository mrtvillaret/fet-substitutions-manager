"""BD inventades: caracterització del codi antic i garanties de migració."""

import json
import shutil
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from suport_database_antic import (
    _ensure_substitucions_aula_column,
    _ensure_users_versio_sessio_column,
    _ensure_vigilancies_ordre_column,
)
from suport_schema_history import assert_preserved, preserved_rows

from models import Base
from schema_migrations import runner
from schema_migrations.runner import database_state, initialize_database
from schema_migrations.schema import CANONICAL_REVISION, schema_signature
from scripts.migra_esquemes import main, run


def legacy_database(path, kind):
    """L’esquema anterior a les tres columnes + els _ensure_* originals."""
    statements = json.loads((Path(__file__).parents[1] / "schema_migrations/base_schema.json").read_text())[kind]
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        for statement in statements:
            if statement.startswith("CREATE TABLE users"):
                statement = statement.replace("\tversio_sessio INTEGER DEFAULT '0' NOT NULL, \n", "")
            elif statement.startswith("CREATE TABLE substitucions"):
                statement = statement.replace("\taula VARCHAR, \n", "")
            elif statement.startswith("CREATE TABLE vigilancies"):
                statement = statement.replace("\tordre INTEGER, \n", "")
            connection.exec_driver_sql(statement)
        if kind == "auth":
            connection.exec_driver_sql(
                "INSERT INTO users (username, password_hash, institucio) VALUES ('prova', 'hash', 'centre_prova')"
            )
        else:
            connection.exec_driver_sql(
                "INSERT INTO vigilancies (data, hora, tipus, grups, aula, nivell) "
                "VALUES ('2026-01-01', '10', 'Prova', 'G', 'A', 'N')"
            )
    if kind == "auth":
        _ensure_users_versio_sessio_column(engine)
    else:
        _ensure_substitucions_aula_column(engine)
        _ensure_vigilancies_ordre_column(engine)
    return engine


def dump_without_version(path):
    with sqlite3.connect(path) as connection:
        return tuple(line for line in connection.iterdump() if "alembic_version" not in line)


@pytest.mark.parametrize("kind", ["auth", "data"])
def test_legacy_and_new_have_identical_schema_and_preserve_data(tmp_path, kind):
    old_path = tmp_path / "old.db"
    old = legacy_database(old_path, kind)
    # DDL dels _ensure_* comprovats a git: 99d85ca, 7e824b6 i 0f360af.
    # Només users afegia un default; totes tres columnes quedaven al final.
    columns = (
        (("users", "versio_sessio", "0"),)
        if kind == "auth"
        else (
            ("substitucions", "aula", None),
            ("vigilancies", "ordre", None),
        )
    )
    with old.connect() as connection:
        for table, column, default in columns:
            info = connection.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
            assert info[-1][1] == column
            assert info[-1][4] == default
    before = preserved_rows(old_path)
    new = create_engine(f"sqlite:///{tmp_path / 'new.db'}")
    run([(kind, old_path)], apply=True, backup_dir=tmp_path / "copies")
    initialize_database(old, kind)
    initialize_database(new, kind)
    with old.connect() as a, new.connect() as b:
        assert schema_signature(a) == schema_signature(b)
        assert database_state(a, kind) == database_state(b, kind) == "vigent"
    assert_preserved(before, preserved_rows(old_path))
    # Una segona aplicació no altera ni un byte del fitxer.
    stamped = old_path.read_bytes()
    initialize_database(old, kind)
    assert old_path.read_bytes() == stamped
    assert_preserved(before, preserved_rows(old_path))


@pytest.mark.parametrize("kind", ["auth", "data"])
def test_frozen_base_matches_current_models(tmp_path, kind):
    model_engine = create_engine("sqlite://")
    Base.metadata.create_all(
        model_engine, tables=[t for t in Base.metadata.sorted_tables if (t.name == "users") == (kind == "auth")]
    )
    frozen = create_engine("sqlite://")
    initialize_database(frozen, kind)
    with model_engine.connect() as a, frozen.connect() as b:
        assert schema_signature(a) == schema_signature(b)


@pytest.mark.parametrize(
    "sql",
    [
        "ALTER TABLE vigilancies ADD COLUMN inesperada TEXT",
        "DROP INDEX idx_vigilancies_data",
        "CREATE UNIQUE INDEX inesperat ON vigilancies (hora)",
        "CREATE TABLE inesperada (id INTEGER)",
        "CREATE TABLE __objects__ (id INTEGER)",
        "CREATE VIEW inesperada AS SELECT hora FROM vigilancies",
        "CREATE TRIGGER inesperat AFTER INSERT ON vigilancies BEGIN SELECT 1; END",
    ],
)
def test_different_schema_rejected_without_writes(tmp_path, sql):
    path = tmp_path / "old.db"
    engine = legacy_database(path, "data")
    with engine.begin() as connection:
        connection.exec_driver_sql(sql)
    before = path.read_bytes()
    with pytest.raises(RuntimeError, match="esquema"):
        initialize_database(engine, "data")
    assert path.read_bytes() == before


def test_wrong_database_kind_is_rejected(tmp_path):
    path = tmp_path / "auth.db"
    engine = legacy_database(path, "auth")
    before = path.read_bytes()
    with pytest.raises(RuntimeError, match="esquema"):
        initialize_database(engine, "data")
    assert path.read_bytes() == before


@pytest.mark.parametrize("unexpected", [False, True])
def test_known_legacy_table_is_backed_up_removed_and_checked(tmp_path, unexpected):
    path = tmp_path / "legacy.db"
    engine = legacy_database(path, "data")
    statements = json.loads((Path(__file__).parents[1] / "schema_migrations/legacy_schema.json").read_text())["data"]
    with engine.begin() as connection:
        for statement in statements:
            connection.exec_driver_sql(statement)
        connection.exec_driver_sql(
            "INSERT INTO exam_schedules (dies_seleccionats, horari_resultat) VALUES ('[]', '{}')"
        )
        if unexpected:
            connection.exec_driver_sql("ALTER TABLE exam_schedules ADD COLUMN inesperada TEXT")
    before = dump_without_version(path)
    if unexpected:
        before_bytes = path.read_bytes()
        with pytest.raises(RuntimeError, match="esquema"):
            run([("data", path)], apply=True, backup_dir=tmp_path / "copies")
        assert path.read_bytes() == before_bytes
        assert not (tmp_path / "copies").exists()
    else:
        run([("data", path)], apply=True, backup_dir=tmp_path / "copies")
        assert dump_without_version(next((tmp_path / "copies").glob("*.db"))) == before
        with engine.connect() as connection:
            assert "exam_schedules" not in schema_signature(connection)


@pytest.mark.parametrize("replacement", ["nom VARCHAR COLLATE NOCASE", "nom VARCHAR DEFAULT 'canvi'"])
def test_column_constraints_and_defaults_are_checked(tmp_path, replacement):
    path = tmp_path / "wrong.db"
    statements = json.loads((Path(__file__).parents[1] / "schema_migrations/base_schema.json").read_text())["data"]
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        for statement in statements:
            if statement.startswith("CREATE TABLE nivells"):
                statement = statement.replace("nom VARCHAR", replacement)
            connection.exec_driver_sql(statement)
    before = path.read_bytes()
    with pytest.raises(RuntimeError, match="esquema"):
        initialize_database(engine, "data")
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "kind, original, replacement",
    [
        ("data", "aula VARCHAR,", "aula VARCHAR DEFAULT 0,"),
        ("data", "aula VARCHAR,", "aula VARCHAR DEFAULT '0',"),
        ("data", "ordre INTEGER,", "ordre INTEGER DEFAULT 0,"),
        ("data", "ordre INTEGER,", "ordre INTEGER DEFAULT '0',"),
        ("auth", "versio_sessio INTEGER DEFAULT '0' NOT NULL,", "versio_sessio INTEGER DEFAULT 1 NOT NULL,"),
        ("auth", "versio_sessio INTEGER DEFAULT '0' NOT NULL,", "versio_sessio INTEGER DEFAULT 0,"),
    ],
)
def test_unknown_ensure_column_variants_rejected_without_writes(tmp_path, kind, original, replacement):
    path = tmp_path / "alter_desconegut.db"
    statements = json.loads((Path(__file__).parents[1] / "schema_migrations/base_schema.json").read_text())[kind]
    engine = create_engine(f"sqlite:///{path}")
    table = "users" if kind == "auth" else "substitucions" if original.startswith("aula") else "vigilancies"
    with engine.begin() as connection:
        for statement in statements:
            if statement.startswith(f"CREATE TABLE {table} "):
                assert original in statement
                statement = statement.replace(original, "")
            connection.exec_driver_sql(statement)
        connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {replacement.removesuffix(',')}")
    before = path.read_bytes()
    copies = tmp_path / "copies"
    assert main(["--comprova", f"--{kind}", str(path)]) == 1
    assert main(["--aplica", f"--{kind}", str(path), "--backup-dir", str(copies)]) == 1
    assert path.read_bytes() == before
    assert not copies.exists()


def test_readonly_check_backup_and_repeat(tmp_path, capsys):
    path = tmp_path / "inventada.db"
    legacy_database(path, "data")
    before = path.read_bytes()
    before_dump = dump_without_version(path)
    assert main(["--comprova", "--data", str(path)]) == 0
    assert path.read_bytes() == before
    backups = tmp_path / "copies"
    assert main(["--aplica", "--backup-dir", str(backups), "--data", str(path)]) == 0
    copies = list(backups.glob("*.db"))
    assert len(copies) == 1
    assert dump_without_version(copies[0]) == before_dump
    after = path.read_bytes()
    assert main(["--aplica", "--backup-dir", str(backups), "--data", str(path)]) == 0
    assert path.read_bytes() == after
    assert len(list(backups.glob("*.db"))) == 1
    output = capsys.readouterr()
    assert str(path) not in output.out + output.err


def test_preflight_checks_all_databases_before_modifying_any(tmp_path):
    path = tmp_path / "valid.db"
    legacy_database(path, "auth")
    before = path.read_bytes()
    assert (
        main(
            [
                "--aplica",
                "--backup-dir",
                str(tmp_path / "copies"),
                "--auth",
                str(path),
                "--data",
                str(tmp_path / "missing.db"),
            ]
        )
        == 1
    )
    assert path.read_bytes() == before
    assert not (tmp_path / "missing.db").exists()
    assert main(["--aplica", "--auth", str(path)]) == 1
    assert path.read_bytes() == before
    with pytest.raises(ValueError, match="duplicades"):
        run([("auth", path), ("auth", path)])


def test_concurrent_initializations_same_and_different_databases(tmp_path):
    def initialize(number):
        # Diversos fils comparteixen algunes BD i en creen d’altres alhora.
        path = tmp_path / f"centre_{number % 3}.db"
        engine = create_engine(f"sqlite:///{path}")
        try:
            initialize_database(engine, "data")
            with engine.connect() as connection:
                assert database_state(connection, "data") == "vigent"
        finally:
            engine.dispose()

    with ThreadPoolExecutor(max_workers=6) as executor:
        list(executor.map(initialize, range(12)))


@pytest.fixture
def future_migration(tmp_path, monkeypatch):
    source = Path(__file__).parents[1] / "schema_migrations"
    target = tmp_path / "migration_code"
    shutil.copytree(source, target)
    config = runner.alembic_config

    def local_config(connection, kind):
        result = config(connection, kind)
        result.set_main_option("script_location", str(target))
        return result

    monkeypatch.setattr(runner, "alembic_config", local_config)
    return target / "versions/0004_test.py"


@pytest.mark.parametrize("fails", [False, True])
def test_pending_upgrade_only_explicit_and_transactional(tmp_path, future_migration, fails):
    path = tmp_path / "auth.db"
    engine = legacy_database(path, "auth")
    run([("auth", path)], apply=True, backup_dir=tmp_path / "initial_copies")
    initialize_database(engine, "auth")
    before = path.read_bytes()
    future_migration.write_text(
        "from alembic import op\n"
        "revision = '0004_test'\n"
        f"down_revision = {CANONICAL_REVISION!r}\n"
        "def upgrade():\n"
        "    op.execute('CREATE TABLE nova (id INTEGER)')\n"
        + ("    raise RuntimeError('fallada simulada')\n" if fails else "")
    )
    if not fails:
        fresh_engine = create_engine(f"sqlite:///{tmp_path / 'new_future.db'}")
        initialize_database(fresh_engine, "auth")
        with fresh_engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar() == "0004_test"
    with pytest.raises(RuntimeError, match="Migracions pendents"):
        initialize_database(engine, "auth")
    assert path.read_bytes() == before
    if fails:
        with pytest.raises(RuntimeError, match="fallada simulada"):
            run([("auth", path)], apply=True, backup_dir=tmp_path / "copies")
        assert path.read_bytes() == before
    else:
        run([("auth", path)], apply=True, backup_dir=tmp_path / "copies")
        with engine.connect() as connection:
            assert database_state(connection, "auth") == "vigent"
            assert connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar() == "0004_test"
        after = path.read_bytes()
        initialize_database(engine, "auth")
        assert path.read_bytes() == after
