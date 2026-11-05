"""Còpia congelada dels _ensure_* anteriors a Alembic; només per caracterització."""

import logging

log = logging.getLogger(__name__)


def _ensure_users_versio_sessio_column(engine):
    """Afegeix users.versio_sessio a les auth.db creades abans que existís.
    Els usuaris existents comencen a 0: ningú no ha de tornar a entrar."""
    try:
        with engine.begin() as conn:
            columns = conn.exec_driver_sql("PRAGMA table_info(users);").fetchall()
            if "versio_sessio" not in {col[1] for col in columns}:
                conn.exec_driver_sql("ALTER TABLE users ADD COLUMN versio_sessio INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass


def _ensure_substitucions_aula_column(engine):
    """Assegura que la taula substitucions té la columna aula (migració simple)."""
    try:
        with engine.connect() as conn:
            columns = conn.exec_driver_sql("PRAGMA table_info(substitucions);").fetchall()
            column_names = {col[1] for col in columns}
            if "aula" not in column_names:
                conn.exec_driver_sql("ALTER TABLE substitucions ADD COLUMN aula VARCHAR")
    except Exception:
        # Si la taula no existeix encara o ja està migrada, no cal fer res
        pass


def _ensure_vigilancies_ordre_column(engine):
    """La columna ordre de vigilancies (posició dins de la seva hora). Les files
    que no en tenen (les d'abans de la columna) prenen l'ordre que es veia a la
    pantalla: per nivell i, dins del nivell, per id; si la seva hora ja té
    files amb ordre, van al final."""
    try:
        with engine.begin() as conn:
            columns = {col[1] for col in conn.exec_driver_sql("PRAGMA table_info(vigilancies);").fetchall()}
            if not columns:
                return
            if "ordre" not in columns:
                conn.exec_driver_sql("ALTER TABLE vigilancies ADD COLUMN ordre INTEGER")
            sense = conn.exec_driver_sql(
                "SELECT id, data, hora, nivell FROM vigilancies WHERE ordre IS NULL ORDER BY data, hora, nivell, id"
            ).fetchall()
            seguent = {}
            for vig_id, data, hora, _nivell in sense:
                if (data, hora) not in seguent:
                    maxim = conn.exec_driver_sql(
                        "SELECT MAX(ordre) FROM vigilancies WHERE data = ? AND hora = ?", (data, hora)
                    ).scalar()
                    seguent[(data, hora)] = 0 if maxim is None else maxim + 1
                conn.exec_driver_sql("UPDATE vigilancies SET ordre = ? WHERE id = ?", (seguent[(data, hora)], vig_id))
                seguent[(data, hora)] += 1
    except Exception:
        log.warning("No s'ha pogut afegir o omplir la columna ordre de vigilancies", exc_info=True)
