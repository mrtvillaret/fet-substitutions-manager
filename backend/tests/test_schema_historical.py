"""Variants històriques sintètiques: comprovació estricta i còpia abans de netejar."""

import json
import sqlite3
from pathlib import Path

import pytest
from alembic.operations import Operations
from sqlalchemy import create_engine

from schema_migrations.runner import database_state, initialize_database
from schema_migrations.schema import (
    BASE_REVISION,
    CLEAN_REVISION,
    CURRENT_REVISION,
    create_base,
    current_signature,
    schema_signature,
)
from scripts.migra_esquemes import main

SCHEMAS = Path(__file__).parents[1] / "schema_migrations"
HISTORICAL_TABLES = ("users", "configuracio_assignatures", "exam_schedules")


def historical_database(path, variants=(), *, stamped=False, default_sql="'0'", historical_replace=None):
    statements = json.loads((SCHEMAS / "base_schema.json").read_text())["data"]
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        for statement in statements:
            if "assignatures_prioritat" in variants and (
                statement.startswith("CREATE TABLE assignatures_prioritat ")
                or " ON assignatures_prioritat (" in statement
            ):
                continue
            if "index" in variants and statement.startswith("CREATE INDEX idx_configuracio_clau "):
                continue
            if "default" in variants and statement.startswith("CREATE TABLE assignatures_prioritat "):
                statement = statement.replace("auto_assignada BOOLEAN", f"auto_assignada BOOLEAN DEFAULT {default_sql}")
            connection.exec_driver_sql(statement)
        # Fixture independent del catàleg que valida producció: DDL exacte
        # facilitat a l’assaig, amb l’índex explícit i l’UNIQUE implícit.
        historical_sql = Path(__file__).with_name("historical_schema.sql").read_text()
        if historical_replace:
            original, replacement = historical_replace
            assert original in historical_sql
            historical_sql = historical_sql.replace(original, replacement)
        for statement in historical_sql.split(";"):
            if any(f"TABLE {table} (" in statement or f"ON {table} (" in statement for table in variants):
                connection.exec_driver_sql(statement)
        if "users" in variants:
            connection.exec_driver_sql(
                "INSERT INTO users (username, password_hash, institucio) VALUES (?, 'hash_inventat', 'prova')",
                [(f"usuari_prova_{number}",) for number in range(5)],
            )
        if "configuracio_assignatures" in variants:
            connection.exec_driver_sql(
                "INSERT INTO configuracio_assignatures (assignatura, titular) VALUES (?, 'Prof prova')",
                [(f"Activitat prova {number}",) for number in range(84)],
            )
        if "assignatures_prioritat" in variants and not historical_replace:
            connection.exec_driver_sql("INSERT INTO categories_prioritat (id, nom, ordre) VALUES (1, 'Prova', 0)")
            connection.exec_driver_sql(
                "INSERT INTO assignatures_prioritat (assignatura, categoria_id, auto_assignada) VALUES ('Prova', 1, ?)",
                [(None,), (0,), (1,)],
            )
        connection.exec_driver_sql("INSERT INTO configuracio (clau, valor) VALUES ('prova', 'conserva')")
        if stamped:
            connection.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)")
            connection.exec_driver_sql(
                "INSERT INTO alembic_version VALUES (?)", (stamped if isinstance(stamped, str) else BASE_REVISION,)
            )
    engine.dispose()
    return engine


def dump(path):
    with sqlite3.connect(path) as connection:
        return tuple(connection.iterdump())


@pytest.mark.parametrize(
    "variants",
    [
        ("index",),
        ("default",),
        ("index", "default"),
        ("users",),
        ("configuracio_assignatures",),
        ("exam_schedules",),
        ("index", "default", *HISTORICAL_TABLES),  # variant del centre 1
        ("index", "exam_schedules"),  # variant del centre 2
        ("assignatures_prioritat",),  # ALTER: columna al final i DEFAULT 0 sense cometes
        ("index", "assignatures_prioritat", *HISTORICAL_TABLES),
    ],
)
@pytest.mark.parametrize("stamped", [False, True])
def test_known_variants_checked_migrated_and_backed_up(tmp_path, variants, stamped):
    path = tmp_path / "inventada.db"
    engine = historical_database(path, variants, stamped=stamped)
    before = path.read_bytes()
    before_dump = dump(path)
    if "assignatures_prioritat" in variants:
        with engine.connect() as connection:
            columns = connection.exec_driver_sql("PRAGMA table_xinfo(assignatures_prioritat)").fetchall()
            assert tuple(columns[-1]) == (7, "auto_assignada", "BOOLEAN", 0, "0", 0, 0)
            assert (
                "updated_at DATETIME, auto_assignada BOOLEAN DEFAULT 0,"
                in connection.exec_driver_sql(
                    "SELECT sql FROM sqlite_schema WHERE name = 'assignatures_prioritat'"
                ).scalar()
            )
    assert main(["--comprova", "--data", str(path)]) == 0
    assert path.read_bytes() == before
    with pytest.raises(RuntimeError, match="Migracions pendents"):
        initialize_database(engine, "data")
    assert path.read_bytes() == before
    copies = tmp_path / "copies"
    assert main(["--aplica", "--data", str(path), "--backup-dir", str(copies)]) == 0
    backups = list(copies.glob("*.db"))
    assert len(backups) == 1
    assert dump(backups[0]) == before_dump
    with sqlite3.connect(backups[0]) as backup:
        for table, count in zip(HISTORICAL_TABLES, (5, 84, 0), strict=True):
            if table in variants:
                assert backup.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == count
    with engine.connect() as connection:
        assert database_state(connection, "data") == "vigent"
        assert connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar() == CURRENT_REVISION
        assert schema_signature(connection) == current_signature("data")
        assert not set(HISTORICAL_TABLES).intersection(schema_signature(connection))
        assert connection.exec_driver_sql("SELECT valor FROM configuracio WHERE clau = 'prova'").scalar() == "conserva"
        columns = connection.exec_driver_sql("PRAGMA table_info(assignatures_prioritat)").fetchall()
        default = next(row[4] for row in columns if row[1] == "auto_assignada")
        assert default is None
        if "assignatures_prioritat" in variants:
            assert connection.exec_driver_sql(
                "SELECT auto_assignada FROM assignatures_prioritat ORDER BY id"
            ).scalars().all() == [None, 0, 1]

    after = path.read_bytes()
    assert main(["--comprova", "--data", str(path)]) == 0
    assert main(["--aplica", "--data", str(path), "--backup-dir", str(copies)]) == 0
    initialize_database(engine, "data")
    assert path.read_bytes() == after
    assert list(copies.glob("*.db")) == backups


@pytest.mark.parametrize("kind", ["auth", "data"])
@pytest.mark.parametrize("stamped", [False, True])
def test_0002_leaves_matching_schema_and_rows_unchanged(tmp_path, kind, stamped):
    path = tmp_path / "exacta.db"
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        create_base(connection, kind)
        if kind == "auth":
            connection.exec_driver_sql(
                "INSERT INTO users (username, password_hash, institucio) VALUES ('prova', 'x', 'prova')"
            )
        else:
            connection.exec_driver_sql("INSERT INTO configuracio (clau, valor) VALUES ('prova', 'conserva')")
        if stamped:
            connection.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)")
            connection.exec_driver_sql("INSERT INTO alembic_version VALUES (?)", (BASE_REVISION,))

    # La 0004 només refà no_substituir (tests a test_migracio_0004.py).
    def sense_versio(path):
        return tuple(line for line in dump(path) if "alembic_version" not in line and "no_substituir" not in line)

    before = sense_versio(path)
    assert main(["--aplica", f"--{kind}", str(path), "--backup-dir", str(tmp_path / "copies")]) == 0
    assert sense_versio(path) == before


@pytest.mark.parametrize("stamped", [False, True, CLEAN_REVISION])
@pytest.mark.parametrize(
    "sql",
    [
        "ALTER TABLE configuracio ADD COLUMN inesperada TEXT",
        "DROP INDEX idx_vigilancies_data",
        "CREATE TABLE desconeguda (id INTEGER)",
        "CREATE INDEX inesperat ON configuracio (valor)",
        "CREATE VIEW inesperada AS SELECT clau FROM configuracio",
        "CREATE TRIGGER inesperat AFTER INSERT ON configuracio BEGIN SELECT 1; END",
    ],
)
def test_unknown_difference_rejected_before_any_backup_or_write(tmp_path, stamped, sql):
    path = tmp_path / "desconeguda.db"
    variants = ("default",) if stamped == CLEAN_REVISION else ("index", "default")
    engine = historical_database(path, variants, stamped=stamped)
    with engine.begin() as connection:
        connection.exec_driver_sql(sql)
    before = path.read_bytes()
    assert main(["--comprova", "--data", str(path)]) == 1
    copies = tmp_path / "copies"
    assert main(["--aplica", "--data", str(path), "--backup-dir", str(copies)]) == 1
    assert path.read_bytes() == before
    assert not copies.exists()


@pytest.mark.parametrize("stamped", [False, True, CLEAN_REVISION])
@pytest.mark.parametrize(
    "sql",
    [
        *(f"ALTER TABLE {table} ADD COLUMN inesperada TEXT" for table in HISTORICAL_TABLES),
        "DROP INDEX idx_config_assignatures",
        "DROP INDEX idx_config_assignatures; "
        "CREATE INDEX idx_config_assignatures ON configuracio_assignatures (grup, assignatura, aula)",
        "CREATE INDEX inesperat ON users (username)",
        "CREATE INDEX inesperat ON exam_schedules (nom)",
        "CREATE TRIGGER inesperat AFTER INSERT ON users BEGIN SELECT 1; END",
    ],
)
def test_altered_historical_structure_is_rejected(tmp_path, stamped, sql):
    path = tmp_path / "historica_desconeguda.db"
    historical_database(path, HISTORICAL_TABLES, stamped=stamped)
    with sqlite3.connect(path) as connection:
        connection.executescript(sql)
    before = path.read_bytes()
    copies = tmp_path / "copies"
    assert main(["--comprova", "--data", str(path)]) == 1
    assert main(["--aplica", "--data", str(path), "--backup-dir", str(copies)]) == 1
    assert path.read_bytes() == before
    assert not copies.exists()


@pytest.mark.parametrize("table", HISTORICAL_TABLES)
def test_0002_rejects_even_exact_historical_tables_once_migrated(tmp_path, table):
    path = tmp_path / "historica_despres.db"
    historical_database(path, (table,), stamped=CLEAN_REVISION)
    before = path.read_bytes()
    assert main(["--comprova", "--data", str(path)]) == 1
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "replacement",
    [
        ("UNIQUE (username)", "UNIQUE (username, institucio)"),
        ("username VARCHAR NOT NULL", "username VARCHAR"),
        ("role VARCHAR", "role VARCHAR DEFAULT 'user'"),
        ("dies_seleccionats TEXT NOT NULL", "dies_seleccionats TEXT"),
        ("titular VARCHAR NOT NULL", "titular VARCHAR COLLATE NOCASE NOT NULL"),
    ],
)
def test_other_historical_constraints_are_rejected(tmp_path, replacement):
    path = tmp_path / "restriccio_desconeguda.db"
    historical_database(path, HISTORICAL_TABLES, historical_replace=replacement)
    before = path.read_bytes()
    copies = tmp_path / "copies"
    assert main(["--comprova", "--data", str(path)]) == 1
    assert main(["--aplica", "--data", str(path), "--backup-dir", str(copies)]) == 1
    assert path.read_bytes() == before
    assert not copies.exists()


@pytest.mark.parametrize("default_sql", ["0", "'1'", "NULL", "'false'"])
def test_other_defaults_rejected(tmp_path, default_sql):
    path = tmp_path / "default_desconegut.db"
    historical_database(path, ("default",), default_sql=default_sql)
    before = path.read_bytes()
    assert main(["--comprova", "--data", str(path)]) == 1
    assert path.read_bytes() == before


@pytest.mark.parametrize("stamped", [False, True, CLEAN_REVISION])
@pytest.mark.parametrize(
    "replacement",
    [
        ("auto_assignada BOOLEAN DEFAULT 0", "auto_assignada BOOLEAN DEFAULT 1"),
        ("auto_assignada BOOLEAN DEFAULT 0", "auto_assignada BOOLEAN DEFAULT NULL"),
        ("auto_assignada BOOLEAN DEFAULT 0", "auto_assignada BOOLEAN DEFAULT 'false'"),
        ("auto_assignada BOOLEAN DEFAULT 0", "auto_assignada BOOLEAN NOT NULL DEFAULT 0"),
        ("auto_assignada BOOLEAN DEFAULT 0", "auto_assignada BOOLEAN DEFAULT 0 CHECK (auto_assignada IN (0, 1))"),
        ("auto_assignada BOOLEAN DEFAULT 0", "auto_assignada BOOLEAN COLLATE NOCASE DEFAULT 0"),
        ("ON DELETE CASCADE", "ON DELETE RESTRICT"),
        (
            "idx_assignatura_categoria ON assignatures_prioritat (categoria_id)",
            "idx_assignatura_categoria ON assignatures_prioritat (assignatura)",
        ),
    ],
)
def test_unknown_alter_auto_assignada_variants_rejected_without_writes(tmp_path, stamped, replacement):
    path = tmp_path / "alter_desconegut.db"
    historical_database(path, ("assignatures_prioritat",), stamped=stamped, historical_replace=replacement)
    before = path.read_bytes()
    copies = tmp_path / "copies"
    assert main(["--comprova", "--data", str(path)]) == 1
    assert main(["--aplica", "--data", str(path), "--backup-dir", str(copies)]) == 1
    assert path.read_bytes() == before
    assert not copies.exists()


def test_0002_requires_the_index_once_migrated(tmp_path):
    path = tmp_path / "incompleta.db"
    historical_database(path, ("index",), stamped=CLEAN_REVISION)
    before = path.read_bytes()
    assert main(["--comprova", "--data", str(path)]) == 1
    assert path.read_bytes() == before


def test_unknown_difference_in_second_database_prevents_all_writes(tmp_path):
    valid = tmp_path / "valida.db"
    invalid = tmp_path / "desconeguda.db"
    historical_database(valid, ("index", "default"))
    engine = historical_database(invalid, ("index",), stamped=True)
    with engine.begin() as connection:
        connection.exec_driver_sql("ALTER TABLE configuracio ADD COLUMN inesperada TEXT")
    before = [path.read_bytes() for path in (valid, invalid)]
    copies = tmp_path / "copies"
    assert main(["--aplica", "--data", str(valid), "--data", str(invalid), "--backup-dir", str(copies)]) == 1
    assert [path.read_bytes() for path in (valid, invalid)] == before
    assert not copies.exists()


def test_0002_rolls_back_deleted_table_and_version_if_index_creation_fails(tmp_path, monkeypatch):
    path = tmp_path / "inventada.db"
    engine = historical_database(path, ("index", *HISTORICAL_TABLES))
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO exam_schedules (dies_seleccionats, horari_resultat) VALUES ('[]', '{}')"
        )
    before = path.read_bytes()
    before_dump = dump(path)
    reached = []

    def fail_create_index(operations, *args, **kwargs):
        # La fallada passa després del DROP: s’ha de recuperar també la taula.
        assert not set(HISTORICAL_TABLES).intersection(schema_signature(operations.get_bind()))
        reached.append(True)
        raise RuntimeError("fallada simulada")

    monkeypatch.setattr(Operations, "create_index", fail_create_index)
    copies = tmp_path / "copies"
    assert main(["--aplica", "--data", str(path), "--backup-dir", str(copies)]) == 1
    assert reached == [True]
    assert path.read_bytes() == before
    assert dump(path) == before_dump
    assert dump(next(copies.glob("*.db"))) == before_dump
