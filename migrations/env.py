"""Alembic environment.

The database URL comes from DATABASE_URL and from nowhere else. Not from
alembic.ini, not from a default, not from a fallback to SQLite. A migration
runner that guesses which database to migrate will eventually guess the
wrong one, and the wrong guess here rewrites a school's tables.

Importing main.py is avoided on purpose. main imports the whole application —
the AI providers, the job crawler, the corpus — and a migration must be able
to run when the application cannot even start, which is exactly the situation
you are in when a deploy has failed. So this reads the URL itself and knows
nothing about the app.
"""
import os
import sys

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config


def database_url():
    """The one place the URL is resolved, with no fallback."""
    # A local .env, if there is one. Same loader the app uses, so a URL that
    # works for the app works for a migration — and neither depends on
    # remembering to export a variable in the right terminal window.
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        import db as _db
        _db.load_dotenv()
    except Exception:
        pass          # a missing loader must not stop a migration
    url = (os.environ.get("DATABASE_URL") or "").strip()
    if not url:
        sys.stderr.write(
            "\nDATABASE_URL is not set.\n"
            "Migrations do not have a default database and will not invent "
            "one. Set DATABASE_URL to the Postgres instance you mean to "
            "migrate.\n\n")
        raise SystemExit(2)
    # Railway hands out postgres://; SQLAlchemy 2 requires postgresql://.
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    # An unresolved Railway variable reference arrives as a literal string.
    if "${{" in url:
        sys.stderr.write(
            "\nDATABASE_URL is an unresolved reference (%s).\n"
            "In Railway, add it with '+ New Variable' > 'Add Reference' > "
            "Postgres.\n\n" % url[:60])
        raise SystemExit(2)
    if url.startswith("sqlite"):
        sys.stderr.write(
            "\nDATABASE_URL points at SQLite (%s).\n"
            "This project migrates Postgres. SQLite has no ALTER TABLE worth "
            "the name, so a migration that works there proves nothing about "
            "the database that actually holds the data.\n\n" % url[:60])
        raise SystemExit(2)
    return url


# No target_metadata. Autogenerate is deliberately not wired up: it needs to
# import the models, which means importing main, which this file refuses to
# do for the reason above. Revisions are written by hand.
target_metadata = None


def run_migrations_offline():
    context.configure(
        url=database_url(), target_metadata=target_metadata,
        literal_binds=True, dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = database_url()
    connectable = engine_from_config(
        section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
