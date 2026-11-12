"""Migració 0004: «No substituir» amb vigència per dates (BD inventades).

Les entrades existents queden vàlides des de sempre (dates nul·les) i la resta
de la BD no canvia; la taula perd la unicitat d’assignatura."""

import sqlite3

import pytest
from alembic import command
from sqlalchemy import create_engine
from suport_schema_history import preserved_rows

from schema_migrations.runner import alembic_config, database_state, initialize_database
from schema_migrations.schema import (
    BASE_REVISION,
    CANONICAL_REVISION,
    CURRENT_REVISION,
    create_base,
    current_signature,
    schema_signature,
)
from scripts.migra_esquemes import main

FILES = [
    (1, "Guàrdia", "2026-01-01 08:00:00.000000", "2026-01-02 09:00:00.000000"),
    (4, "", "2026-01-03 10:00:00.000000", None),
    (9, "Reunió ' àèíòü", None, None),
]


def bd_a_la_0003(path, files=FILES):
    """Esquema canònic de la 0003 estampat, amb files inventades."""
    engine = create_engine(f"sqlite:///{path}")
    with engine.connect() as connection:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        create_base(connection, "data")
        config = alembic_config(connection, "data")
        command.stamp(config, BASE_REVISION)
        command.upgrade(config, CANONICAL_REVISION)
        if files:
            connection.exec_driver_sql(
                "INSERT INTO no_substituir (id, assignatura, created_at, updated_at) VALUES (?, ?, ?, ?)", files
            )
        connection.exec_driver_sql("INSERT INTO configuracio (clau, valor) VALUES ('prova', 'conserva')")
        connection.commit()
    engine.dispose()
    return engine


def test_la_0004_conserva_les_files_i_les_deixa_valides_des_de_sempre(tmp_path):
    path = tmp_path / "centre.db"
    bd_a_la_0003(path)
    abans = preserved_rows(path)
    copies = tmp_path / "copies"
    assert main(["--comprova", "--data", str(path)]) == 0
    assert main(["--aplica", "--data", str(path), "--backup-dir", str(copies)]) == 0
    assert preserved_rows(next(copies.glob("*.db"))) == abans
    despres = preserved_rows(path)
    # La resta de taules, idèntiques; no_substituir, les mateixes files i
    # valors amb les dues dates noves nul·les.
    assert {k: v for k, v in despres.items() if k != "no_substituir"} == {
        k: v for k, v in abans.items() if k != "no_substituir"
    }
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT rowid, id, assignatura, created_at, updated_at, vigent_des_de, vigent_fins_a "
            "FROM no_substituir ORDER BY rowid"
        ).fetchall() == [(f[0], *f, None, None) for f in FILES]
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == CURRENT_REVISION
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    engine = create_engine(f"sqlite:///{path}")
    with engine.connect() as connection:
        assert schema_signature(connection) == current_signature("data")
        assert database_state(connection, "data") == "vigent"
    engine.dispose()
    # Idempotent: tornar-la a aplicar no toca ni un byte ni fa cap còpia nova.
    migrada = path.read_bytes()
    assert main(["--aplica", "--data", str(path), "--backup-dir", str(copies)]) == 0
    initialize_database(create_engine(f"sqlite:///{path}"), "data")
    assert path.read_bytes() == migrada
    assert len(list(copies.glob("*.db"))) == 1


def test_despres_de_la_0004_una_activitat_pot_tenir_diversos_periodes(tmp_path):
    path = tmp_path / "centre.db"
    bd_a_la_0003(path)
    with sqlite3.connect(path) as connection, pytest.raises(sqlite3.IntegrityError):
        connection.execute("INSERT INTO no_substituir (assignatura) VALUES ('Guàrdia')")
    assert main(["--aplica", "--data", str(path), "--backup-dir", str(tmp_path / "copies")]) == 0
    with sqlite3.connect(path) as connection:
        connection.execute("INSERT INTO no_substituir (assignatura, vigent_des_de) VALUES ('Guàrdia', '2026-12-01')")
        assert connection.execute("SELECT count(*) FROM no_substituir WHERE assignatura = 'Guàrdia'").fetchone()[0] == 2


def _sense_no_substituir(files):
    return {k: v for k, v in files.items() if k != "no_substituir"}


def test_la_0004_amb_la_taula_buida(tmp_path):
    path = tmp_path / "centre.db"
    bd_a_la_0003(path, files=[])
    abans = preserved_rows(path)
    assert main(["--aplica", "--data", str(path), "--backup-dir", str(tmp_path / "copies")]) == 0
    assert _sense_no_substituir(preserved_rows(path)) == _sense_no_substituir(abans)
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT count(*) FROM no_substituir").fetchone()[0] == 0
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        connection.execute("INSERT INTO no_substituir (assignatura) VALUES ('Guàrdia')")
        assert connection.execute("SELECT id FROM no_substituir").fetchone()[0] == 1
    engine = create_engine(f"sqlite:///{path}")
    with engine.connect() as connection:
        assert database_state(connection, "data") == "vigent"
    engine.dispose()
    assert main(["--comprova", "--data", str(path)]) == 0


def test_una_bd_nova_ja_neix_amb_la_forma_vigent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'nova.db'}")
    initialize_database(engine, "data")
    with engine.connect() as connection:
        assert schema_signature(connection) == current_signature("data")
        assert connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar() == CURRENT_REVISION
    engine.dispose()


@pytest.mark.parametrize(
    "sql",
    [
        "ALTER TABLE no_substituir ADD COLUMN vigent_des_de DATE",
        "CREATE INDEX inesperat ON no_substituir (updated_at)",
    ],
)
def test_una_forma_desconeguda_a_la_0003_es_rebutja_sense_tocar_res(tmp_path, sql):
    path = tmp_path / "desconeguda.db"
    bd_a_la_0003(path)
    with sqlite3.connect(path) as connection:
        connection.execute(sql)
    abans = path.read_bytes()
    copies = tmp_path / "copies"
    assert main(["--comprova", "--data", str(path)]) == 1
    assert main(["--aplica", "--data", str(path), "--backup-dir", str(copies)]) == 1
    assert path.read_bytes() == abans
    assert not copies.exists()


def test_una_fallada_a_mig_0004_ho_desfa_tot(tmp_path, monkeypatch):
    path = tmp_path / "centre.db"
    bd_a_la_0003(path)
    abans = path.read_bytes()
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    def falla(connection, cursor, statement, parameters, context, executemany):
        if connection.engine.url.database == str(path) and statement.startswith("CREATE INDEX idx_no_substituir"):
            raise RuntimeError("fallada simulada")

    event.listen(Engine, "before_cursor_execute", falla)
    try:
        assert main(["--aplica", "--data", str(path), "--backup-dir", str(tmp_path / "copies")]) == 1
    finally:
        event.remove(Engine, "before_cursor_execute", falla)
    assert path.read_bytes() == abans
