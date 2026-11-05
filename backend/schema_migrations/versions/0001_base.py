"""Esquema exacte del 04/11/2026, congelat sense importar models vius."""

from alembic import context, op

from schema_migrations.schema import create_base

revision = "0001_base"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    create_base(op.get_bind(), context.config.attributes["kind"])


def downgrade():
    raise RuntimeError("La base no es desfà esborrant taules: restaureu la còpia de seguretat.")
