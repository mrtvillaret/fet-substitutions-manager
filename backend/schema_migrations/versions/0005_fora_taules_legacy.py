"""Fora les taules LEGACY i els textos de la pantalla antiga desats com a dades.

- `exam_preferencies` i `exam_pesos_optimitzacio`: cap codi no les llegeix des
  que les preferències i els pesos són a `exam_restriccions` (la pantalla hi
  desa i en llegeix). S'esborren amb les seves files: els valors vigents ja
  són a `exam_restriccions`.
- El text del desplegable antic («-- selecciona vigilant --» i qualsevol
  vigilant que comenci per «--», la mateixa regla que l'entrada de l'API) i
  «---»/«PENDENT» com a substitut volien dir «cap»: queden buits, com els desa
  ara l'aplicació. Així cap lectura no ha de reconèixer aquests textos.

Només amb la còpia i la transacció de scripts.migra_esquemes (o en crear una
BD nova). Idempotent: si la BD ja té la forma nova, no fa res.
"""

from alembic import context, op

from schema_migrations.schema import (
    LEGACY_TABLES,
    current_signature,
    schema_signature,
    validate_current,
    validate_vigencia,
)

revision = "0005_fora_taules_legacy"
down_revision = "0004_vigencia_no_substituir"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    kind = context.config.attributes["kind"]
    if schema_signature(connection) == current_signature(kind):
        return
    # Només des de l’esquema exacte de la 0004.
    validate_vigencia(connection, kind)
    for table in LEGACY_TABLES:
        op.drop_table(table)
    connection.exec_driver_sql("UPDATE vigilancies SET vigilant = '' WHERE vigilant LIKE '--%'")
    connection.exec_driver_sql("UPDATE substitucions SET substitut = '' WHERE substitut IN ('---', 'PENDENT')")
    validate_current(connection, kind)


def downgrade():
    raise RuntimeError("Restaureu la còpia prèvia per recuperar l’esquema anterior a la 0005.")
