"""Checks that must pass before the server is allowed to start.

Run from start.sh, before uvicorn. Exits non-zero to fail the deploy.

This is deliberately separate from main.py and imports almost nothing. main
pulls in the AI providers, the job crawler and the corpus, and the whole
point of a preflight is to give a clear answer when the application cannot
start — so it must not depend on the application starting.

What it refuses:

  * a missing, unresolved, non-Postgres or SQLite DATABASE_URL
  * a database that is not at the migration revision this code needs
  * a missing JWT_SECRET on a deployment

The schema check is the reason this exists. Nothing reconciles the schema at
boot any more, so a release whose migration has not been applied would
otherwise come up healthy and then fail in pieces — 500s on whichever routes
happen to touch a new column first, while everything else looks fine. That
is far worse than not starting.

Usage:
    python preflight.py            check and exit 0/1
    python preflight.py --verbose  also print the revision found
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db as _db                                          # noqa: E402


def main(argv):
    verbose = "--verbose" in argv

    # Say where the URL came from, before using it.
    #
    # An exported DATABASE_URL from an earlier command sat in a shell for
    # three rounds, silently overriding a freshly written .env, while the
    # error it produced read "could not translate host name" and pointed at
    # DNS. Any of these two lines would have ended it immediately.
    seen = _db.load_dotenv()
    if seen.get("DATABASE_URL") == "shadowed":
        print("DATABASE_URL: taken from the ENVIRONMENT, which is overriding "
              "a different value in .env", flush=True)
        print("  If that is not what you want, open a new terminal or run:", flush=True)
        print("      Remove-Item Env:DATABASE_URL", flush=True)
    elif seen.get("DATABASE_URL") == "dotenv":
        print("DATABASE_URL: taken from .env", flush=True)
    elif (os.environ.get("DATABASE_URL") or "").strip():
        print("DATABASE_URL: taken from the environment", flush=True)

    try:
        url = _db.resolve_database_url()
    except _db.ConfigError:
        return 1                      # db.py has already explained it

    if _db.is_sqlite(url):
        print("preflight: SQLite (local only) — schema check skipped", flush=True)
        return 0

    if _db.is_deployed() and not (os.environ.get("JWT_SECRET") or "").strip():
        sys.stderr.write(
            "\nFATAL: JWT_SECRET is not set on a deployed instance.\n"
            "Session cookies are signed with it.\n\n")
        return 1

    from sqlalchemy import create_engine
    try:
        engine = create_engine(url, pool_pre_ping=True)
    except Exception as e:
        sys.stderr.write(f"\nFATAL: could not build a database engine: "
                         f"{type(e).__name__}: {e}\n\n")
        return 1

    # Postgres is often not accepting connections in the first seconds of a
    # deploy. A refused connection is worth waiting out; a wrong schema is
    # not, and is reported immediately by require_schema_at_head.
    import time
    last = None
    for attempt in range(1, 7):
        try:
            rev = _db.require_schema_at_head(engine)
            print(f"preflight: database at {rev}", flush=True)
            return 0
        except _db.ConfigError:
            return 1                  # already explained; do not retry
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
            if verbose:
                print(f"preflight: attempt {attempt}/6 — {last}")
            if attempt < 6:
                time.sleep(attempt * 2)

    sys.stderr.write(
        f"\nFATAL: could not reach the database after 6 attempts.\n"
        f"Last error: {last}\n\n"
        f"The database may still be starting, or DATABASE_URL may point "
        f"somewhere unreachable from this service.\n\n")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
