"""Alembic rep sempre una connexió i el tipus de BD del runner segur."""

from alembic import context

connection = context.config.attributes["connection"]
context.configure(connection=connection, transactional_ddl=True)
with context.begin_transaction():
    context.run_migrations()
