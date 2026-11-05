"""Converteix les formes històriques conegudes a un únic esquema canònic.

DDL congelat, cap import dels models. Només amb còpia i transacció del runner.
Les files de les taules vigents es copien per nom, sense transformar valors.
"""

from alembic import context, op

from schema_migrations.schema import (
    base_signature,
    base_statements,
    schema_signature,
    validate_base,
    validate_historical,
)

revision = "0003_esquema_canonic"
down_revision = "0002_neteja_historiques"
branch_labels = None
depends_on = None


def _recreate(connection, name, statement):
    # Amb FK activades, DROP d’un pare executaria els ON DELETE CASCADE.
    # El runner explícit les desactiva ABANS del BEGIN, mai a mig transacció.
    if connection.exec_driver_sql("PRAGMA foreign_keys").scalar():
        raise RuntimeError("Cal migrar amb scripts.migra_esquemes, amb serveis aturats i còpia prèvia.")
    temporary = f"_migra3_{name}"
    connection.exec_driver_sql(statement.replace(f"CREATE TABLE {name} (", f"CREATE TABLE {temporary} (", 1))
    old_columns = {r[1] for r in connection.exec_driver_sql(f'PRAGMA table_xinfo("{name}")')}
    columns = list(connection.exec_driver_sql(f'PRAGMA table_xinfo("{temporary}")'))
    target = ", ".join(f'"{r[1]}"' for r in columns)
    expressions = []
    for _, column, _kind, _required, default, _pk, _hidden in columns:
        source = column
        if name == "abreviatures_grups" and "grups_origen" in old_columns:
            source = {"grups_originals": "grups_origen", "abreviatura": "grup_abreviat"}.get(column, column)
        expressions.append(f'"{source}"' if source in old_columns else default if default is not None else "NULL")
    # També es conserva rowid: configuracio té una PK textual.
    connection.exec_driver_sql(
        f'INSERT INTO "{temporary}" (rowid, {target}) '
        f'SELECT rowid, {", ".join(expressions)} FROM "{name}" ORDER BY rowid'
    )
    # Crear de nou amb el DDL exacte evita que RENAME reescrigui les FK dels
    # fills o canviï les cometes del nom de la taula al sqlite_schema.
    op.drop_table(name)
    connection.exec_driver_sql(statement)
    connection.exec_driver_sql(
        f'INSERT INTO "{name}" (rowid, {target}) SELECT rowid, {target} FROM "{temporary}" ORDER BY rowid'
    )
    op.drop_table(temporary)


def upgrade():
    connection = op.get_bind()
    kind = context.config.attributes["kind"]
    validate_historical(connection, kind, cleaned=True)
    actual = schema_signature(connection)
    expected = base_signature(kind)
    changed = set()
    for statement in base_statements(kind):
        if not statement.startswith("CREATE TABLE "):
            continue
        name = statement.split()[2]
        if name not in actual:
            connection.exec_driver_sql(statement)
            changed.add(name)
        elif actual[name] != expected[name]:
            _recreate(connection, name, statement)
            changed.add(name)
    # Només recrea els índexs de les taules creades o refetes.
    for statement in base_statements(kind):
        if statement.startswith(("CREATE INDEX ", "CREATE UNIQUE INDEX ")):
            name = statement.split(" ON ", 1)[1].split()[0]
            if name in changed:
                connection.exec_driver_sql(statement)
    validate_base(connection, kind, historical=False)


def downgrade():
    raise RuntimeError("Restaureu la còpia prèvia per recuperar l’esquema històric.")
