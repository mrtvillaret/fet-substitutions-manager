"""Vigència per dates a «No substituir».

Afegeix `vigent_des_de` i `vigent_fins_a` (DATE, nul·les) i treu la unicitat
d’`assignatura`, perquè una activitat que es treu i es torna a afegir tingui
una fila per a cada període. SQLite no pot treure un UNIQUE amb ALTER: la
taula es refà amb el DDL congelat de `vigencia_schema.json`, sense importar
models. Les files es copien per rowid sense transformar cap valor i les dates
queden nul·les: totes les entrades existents valen des de sempre i cap xifra
no canvia. Només amb la còpia i la transacció de scripts.migra_esquemes (o
en crear una BD nova). Idempotent: si la taula ja té la forma nova, no fa res.
"""

from alembic import context, op

from schema_migrations.schema import (
    current_signature,
    schema_signature,
    validate_base,
    validate_current,
    vigencia_statements,
)

revision = "0004_vigencia_no_substituir"
down_revision = "0003_esquema_canonic"
branch_labels = None
depends_on = None

_TAULA = "no_substituir"
_TEMPORAL = "_migra4_no_substituir"
_COLUMNES_ANTIGUES = ("id", "assignatura", "created_at", "updated_at")


def upgrade():
    connection = op.get_bind()
    kind = context.config.attributes["kind"]
    if schema_signature(connection) == current_signature(kind):
        return
    # Només des de l’esquema canònic exacte de la 0003.
    validate_base(connection, kind, historical=False)
    table, *indexes = vigencia_statements(kind)
    # Cap taula no té claus foranes cap a no_substituir: canviar-li el nom
    # no reescriu cap altra taula. La nova es crea amb el DDL exacte.
    connection.exec_driver_sql(f'ALTER TABLE "{_TAULA}" RENAME TO "{_TEMPORAL}"')
    connection.exec_driver_sql(table)
    columnes = ", ".join(f'"{c}"' for c in _COLUMNES_ANTIGUES)
    connection.exec_driver_sql(
        f'INSERT INTO "{_TAULA}" (rowid, {columnes}) SELECT rowid, {columnes} FROM "{_TEMPORAL}" ORDER BY rowid'
    )
    op.drop_table(_TEMPORAL)
    for statement in indexes:
        connection.exec_driver_sql(statement)
    validate_current(connection, kind)


def downgrade():
    raise RuntimeError("Restaureu la còpia prèvia per recuperar l’esquema anterior a la 0004.")
