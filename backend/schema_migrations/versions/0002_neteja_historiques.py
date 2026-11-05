"""Retira taules sense ús de dades i completa l’índex de configuració.

Només amb la còpia prèvia de scripts.migra_esquemes per a BD existents.
Auth no canvia. El default històric '0' d’auto_assignada es conserva.
"""

from alembic import context, op
from sqlalchemy import inspect

from schema_migrations.schema import validate_base, validate_historical

revision = "0002_neteja_historiques"
down_revision = "0001_base"
branch_labels = None
depends_on = None


def upgrade():
    if context.config.attributes["kind"] != "data":
        return
    connection = op.get_bind()
    validate_base(connection, "data")
    tables = set(inspect(connection).get_table_names())
    for table in ("users", "configuracio_assignatures", "exam_schedules"):
        if table in tables:
            op.drop_table(table)
    indexes = inspect(connection).get_indexes("configuracio")
    if not any(index["name"] == "idx_configuracio_clau" for index in indexes):
        op.create_index("idx_configuracio_clau", "configuracio", ["clau"])
    validate_historical(connection, "data", cleaned=True)


def downgrade():
    raise RuntimeError("Les taules antigues es recuperen restaurant la còpia de seguretat.")
