"""Migració 0005: fora les taules LEGACY i els textos del desplegable antic
(BD inventades).

Les dues taules s'esborren amb les seves files; els vigilants «--…» i els
substituts «---»/«PENDENT» queden buits; la resta de la BD no canvia."""

import sqlite3

import pytest
from alembic import command
from sqlalchemy import create_engine
from suport_schema_history import preserved_rows

from schema_migrations.runner import alembic_config, database_state, initialize_database
from schema_migrations.schema import (
    BASE_REVISION,
    CURRENT_REVISION,
    LEGACY_TABLES,
    VIGENCIA_REVISION,
    create_base,
    current_signature,
    schema_signature,
)
from scripts.migra_esquemes import main

VIGILANTS = [
    (1, "-- selecciona vigilant --"),
    (2, "--"),
    (3, "Prof 1"),
    (4, ""),
    (5, None),
    (6, "Prof -- 2"),
]
SUBSTITUTS = [(1, "---"), (2, "PENDENT"), (3, "Prof 3"), (4, ""), (5, None), (6, "pendent")]


def bd_a_la_0004(path, kind="data"):
    """Esquema de la 0004 estampat, amb files inventades a totes les taules tocades."""
    engine = create_engine(f"sqlite:///{path}")
    with engine.connect() as connection:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        create_base(connection, kind)
        config = alembic_config(connection, kind)
        command.stamp(config, BASE_REVISION)
        command.upgrade(config, VIGENCIA_REVISION)
        if kind == "auth":
            connection.exec_driver_sql(
                "INSERT INTO users (username, password_hash, institucio) VALUES ('prova', 'hash', 'centre_prova')"
            )
        else:
            connection.exec_driver_sql(
                "INSERT INTO exam_preferencies (tipus, assignatures, pes) VALUES ('mateix_dia', '[\"A\", \"B\"]', 3)"
            )
            connection.exec_driver_sql(
                "INSERT INTO exam_pesos_optimitzacio (clau, valor) VALUES ('restriccio_dura', 50), ('espera', 7)"
            )
            connection.exec_driver_sql(
                "INSERT INTO vigilancies (id, data, hora, tipus, grups, aula, nivell, vigilant) "
                "VALUES (?, '2026-03-02', '09:00', 'Prova', 'G', 'A', 'N', ?)",
                VIGILANTS,
            )
            connection.exec_driver_sql(
                "INSERT INTO substitucions (id, data, hora, professor_absent, substitut) "
                "VALUES (?, '2026-03-02', '09:00', 'Prof 9', ?)",
                SUBSTITUTS,
            )
            connection.exec_driver_sql("INSERT INTO configuracio (clau, valor) VALUES ('prova', 'conserva')")
        connection.commit()
    engine.dispose()


def _sense(files, *taules):
    return {k: v for k, v in files.items() if k not in taules}


def test_la_0005_esborra_les_taules_legacy_i_buida_els_textos_antics(tmp_path):
    path = tmp_path / "centre.db"
    bd_a_la_0004(path)
    abans = preserved_rows(path)
    copies = tmp_path / "copies"
    assert main(["--comprova", "--data", str(path)]) == 0
    assert main(["--aplica", "--data", str(path), "--backup-dir", str(copies)]) == 0
    # La còpia és la BD d'abans, sencera.
    assert preserved_rows(next(copies.glob("*.db"))) == abans
    despres = preserved_rows(path)
    assert not set(LEGACY_TABLES) & set(despres)
    tocades = ("vigilancies", "substitucions", *LEGACY_TABLES)
    assert _sense(despres, *tocades) == _sense(abans, *tocades)
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT id, vigilant FROM vigilancies ORDER BY id").fetchall() == [
            (1, ""),
            (2, ""),
            (3, "Prof 1"),
            (4, ""),
            (5, None),
            (6, "Prof -- 2"),
        ]
        assert connection.execute("SELECT id, substitut FROM substitucions ORDER BY id").fetchall() == [
            (1, ""),
            (2, ""),
            (3, "Prof 3"),
            (4, ""),
            (5, None),
            (6, "pendent"),
        ]
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


def test_a_la_bd_d_usuaris_nomes_canvia_la_versio(tmp_path):
    path = tmp_path / "auth.db"
    bd_a_la_0004(path, kind="auth")
    abans = preserved_rows(path)
    assert main(["--aplica", "--auth", str(path), "--backup-dir", str(tmp_path / "copies")]) == 0
    assert preserved_rows(path) == abans
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == CURRENT_REVISION


def test_el_backend_no_arrenca_amb_la_0005_pendent(tmp_path):
    path = tmp_path / "centre.db"
    bd_a_la_0004(path)
    abans = path.read_bytes()
    with pytest.raises(RuntimeError, match="Migracions pendents"):
        initialize_database(create_engine(f"sqlite:///{path}"), "data")
    assert path.read_bytes() == abans


def test_una_bd_nova_neix_sense_les_taules_legacy(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'nova.db'}")
    initialize_database(engine, "data")
    with engine.connect() as connection:
        assert not set(LEGACY_TABLES) & set(schema_signature(connection))
        assert connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar() == CURRENT_REVISION
    engine.dispose()


@pytest.mark.parametrize(
    "sql",
    [
        "ALTER TABLE exam_preferencies ADD COLUMN inesperada TEXT",
        "DROP TABLE exam_pesos_optimitzacio",
        "CREATE INDEX inesperat ON vigilancies (vigilant)",
    ],
)
def test_una_forma_desconeguda_a_la_0004_es_rebutja_sense_tocar_res(tmp_path, sql):
    path = tmp_path / "desconeguda.db"
    bd_a_la_0004(path)
    with sqlite3.connect(path) as connection:
        connection.execute(sql)
    abans = path.read_bytes()
    copies = tmp_path / "copies"
    assert main(["--comprova", "--data", str(path)]) == 1
    assert main(["--aplica", "--data", str(path), "--backup-dir", str(copies)]) == 1
    assert path.read_bytes() == abans
    assert not copies.exists()


def test_una_fallada_a_mig_0005_ho_desfa_tot(tmp_path):
    path = tmp_path / "centre.db"
    bd_a_la_0004(path)
    abans = path.read_bytes()
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    def falla(connection, cursor, statement, parameters, context, executemany):
        if connection.engine.url.database == str(path) and statement.startswith("UPDATE substitucions"):
            raise RuntimeError("fallada simulada")

    event.listen(Engine, "before_cursor_execute", falla)
    try:
        assert main(["--aplica", "--data", str(path), "--backup-dir", str(tmp_path / "copies")]) == 1
    finally:
        event.remove(Engine, "before_cursor_execute", falla)
    assert path.read_bytes() == abans
