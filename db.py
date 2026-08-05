"""Where the database URL is decided, and where a stale schema stops a deploy.

Two jobs, both of them refusals.

**The URL is Postgres, from the environment, or the process does not start.**
It used to fall back to SQLite with a printed warning when DATABASE_URL was
missing or arrived as an unresolved Railway reference. A warning in a deploy
log is not a control. What actually happened when that fired was that the
container came up healthy, served real traffic, wrote real accounts and real
student work into a file inside the container, and lost all of it at the next
redeploy — with a green healthcheck the whole time. A missing database is not
a degraded mode, it is a stopped service, and it should look like one.

**The schema is at head, or the process does not start.** There is no
reconciliation at boot any more. What was here before — create_all(), an
ADD COLUMN reconciler, and a drop_all() that fired on drift if the user count
happened to be zero — meant the schema was whatever the last deploy's models
implied, applied silently, with no record of what ran or in what order, and
one branch that deleted every table. Now the database says which revision it
is at, the code says which revision it needs, and if they differ the app
refuses to serve rather than reading and writing columns that may not mean
what it thinks they mean.

Migrations are never applied from here. Applying them is a deliberate act:

    alembic upgrade head

Running them automatically at boot would put schema changes on the same
trigger as a restart — so a crash loop would replay migrations, and two
instances starting together would race each other through them.
"""
import os
import sys

# SQLite is permitted for the test suite and nowhere else.
#
# Every test in tests/ runs against a local SQLite file, and rewriting thirty
# suites onto Postgres is its own piece of work, not a rider on this one. So
# there is an explicit opt-in, and it is checked against the deployment
# markers below: you cannot set it on Railway and have it be obeyed. An escape
# hatch nobody can reach by accident is a hatch; one that a stray environment
# variable opens in production is a hole.
ALLOW_SQLITE = (os.environ.get("ALLOW_SQLITE") or "").strip() in ("1", "true", "yes")

# Set by the platform, not by us. Their presence means "this is a deployment".
_DEPLOY_MARKERS = ("RAILWAY_ENVIRONMENT", "RAILWAY_PROJECT_ID",
                   "RAILWAY_SERVICE_ID")


def is_deployed():
    return any((os.environ.get(k) or "").strip() for k in _DEPLOY_MARKERS)


def load_dotenv(path=None):
    """Read a local .env into the environment, without overriding it.

    Local convenience only. There is no .env in the container, so this does
    nothing in production — and because it never overwrites a variable that
    is already set, a real environment always wins over a stale file.

    It exists because the alternative was "export the variable, then run the
    command, in the same window", and that failed three times in a row: the
    export silently produced nothing, the next command reported a missing
    DATABASE_URL, and the connection between the two was invisible. A file
    that persists between windows removes the whole class of mistake.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    # DOTENV_PATH points somewhere else, or at nothing. The suites that check
    # "a missing DATABASE_URL is fatal" need a way to run as if there were no
    # .env — otherwise a developer's own file makes that check pass for the
    # wrong reason, and it stops testing anything on the one machine where it
    # runs most often.
    path = path or (os.environ.get("DOTENV_PATH") or "").strip() \
        or os.path.join(here, ".env")
    if not os.path.exists(path):
        return {}
    loaded = {}
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if not k:
                    continue
                existing = (os.environ.get(k) or "").strip()
                if not existing:
                    os.environ[k] = v
                    loaded[k] = "dotenv"
                elif existing != v:
                    # The environment wins, which is right — but silently
                    # winning is how an exported value from an earlier
                    # command kept overriding a freshly written .env while
                    # the error message talked about DNS. Recorded so the
                    # caller can say which one is in play.
                    loaded[k] = "shadowed"
                else:
                    loaded[k] = "same"
    except OSError:
        return {}
    return loaded


class ConfigError(RuntimeError):
    """Something about the environment makes it unsafe to start."""


def _die(message):
    sys.stderr.write("\n" + "=" * 62 + "\n")
    sys.stderr.write("FATAL: " + message.strip() + "\n")
    sys.stderr.write("=" * 62 + "\n\n")
    sys.stderr.flush()
    raise ConfigError(message.strip().splitlines()[0])


def resolve_database_url():
    """The connection string, or a refusal to start. Never a fallback."""
    load_dotenv()
    url = (os.environ.get("DATABASE_URL") or "").strip()

    if not url:
        _die("DATABASE_URL is not set.\n\n"
             "This used to fall back to a SQLite file inside the container. "
             "That container is replaced on every deploy, so everything "
             "written to it — accounts, registers, submissions — was lost at "
             "the next release, while the healthcheck stayed green.\n\n"
             "In Railway: + New Variable > Add Reference > Postgres.")

    if "${{" in url:
        _die("DATABASE_URL is an unresolved variable reference:\n"
             "    %s\n\n"
             "Railway substitutes references at deploy time; this one did "
             "not resolve, so the value arrived as literal template text.\n\n"
             "Add it with '+ New Variable' > 'Add Reference' > Postgres "
             "rather than typing the variable name by hand." % url[:80])

    # Railway hands out postgres://; SQLAlchemy 2 requires postgresql://.
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    if url.startswith("sqlite"):
        if is_deployed():
            _die("DATABASE_URL points at SQLite on a deployed instance:\n"
                 "    %s\n\n"
                 "ALLOW_SQLITE is ignored here. A SQLite file lives inside "
                 "the container and is destroyed with it." % url[:80])
        if not ALLOW_SQLITE:
            _die("DATABASE_URL points at SQLite:\n"
                 "    %s\n\n"
                 "This project runs on Postgres. If this is the test suite, "
                 "set ALLOW_SQLITE=1 — it is honoured locally and refused on "
                 "a deployment." % url[:80])
        return url

    if not url.startswith("postgresql"):
        _die("DATABASE_URL is not a Postgres URL:\n"
             "    %s\n\n"
             "Expected postgresql://… — this project's migrations are "
             "Postgres DDL." % url[:80])

    return url


def is_sqlite(url):
    return url.startswith("sqlite")


# --------------------------------------------------------------------------
# Schema version
# --------------------------------------------------------------------------

def head_revision():
    """The revision this code expects, read from migrations/versions."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    here = os.path.dirname(os.path.abspath(__file__))
    cfg = Config(os.path.join(here, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(here, "migrations"))
    heads = ScriptDirectory.from_config(cfg).get_heads()
    if len(heads) != 1:
        _die("The migration history has %d heads: %s\n\n"
             "Two heads means two branches of schema history and no single "
             "answer to 'what should the database look like'. Merge them "
             "with 'alembic merge' before deploying."
             % (len(heads), ", ".join(heads) or "none"))
    return heads[0]


def current_revision(engine):
    """The revision the database is at, or None if it has never migrated."""
    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            rows = conn.execute(
                text("SELECT version_num FROM alembic_version")).fetchall()
        except Exception:
            return None
    if not rows:
        return None
    if len(rows) > 1:
        _die("alembic_version holds %d rows. A database can only be at one "
             "revision; this one cannot say which." % len(rows))
    return rows[0][0]


def require_schema_at_head(engine):
    """Refuse to serve unless the database is exactly at head.

    Behind head is the dangerous one and the reason this exists: the code
    reads and writes columns the database does not have, and the failure
    surfaces as scattered 500s on whichever routes happen to touch a new
    column first — not as a failed deploy.

    Ahead of head is refused too. It means an older release is being rolled
    out over a newer schema, and the old code does not know what the new
    migration did to the data it is about to write.
    """
    want = head_revision()
    have = current_revision(engine)

    if have is None:
        _die("The database has no schema history.\n\n"
             "Expected revision: %s\n"
             "Found:             no alembic_version table\n\n"
             "This database has never been migrated. Run:\n"
             "    alembic upgrade head" % want)

    if have != want:
        _die("The database schema is not at the revision this code needs.\n\n"
             "Expected revision: %s\n"
             "Database is at:    %s\n\n"
             "Serving anyway would mean reading and writing columns that may "
             "not exist or may no longer mean the same thing.\n\n"
             "Run:\n"
             "    alembic upgrade head" % (want, have))

    return want
