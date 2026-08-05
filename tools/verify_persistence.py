"""Prove that data written by one process is still there for the next one.

This is the check the whole first commit exists to satisfy, and it cannot be
done inside a single process. A redeploy replaces the container: a new
process, a new engine, a new connection pool, against the same database. The
failure it is looking for — writes going to a SQLite file inside the
container — looks completely fine until that swap happens, which is exactly
why it survived so long.

So each phase is its own OS process, run separately:

    python tools/verify_persistence.py inspect     read-only; changes nothing
    python tools/verify_persistence.py write       writes one marked row
    python tools/verify_persistence.py check       a NEW process reads it back
    python tools/verify_persistence.py cleanup     removes the marked row
    python tools/verify_persistence.py revision    stale-revision refusal

The marked row is a School named "__persistence_check__<timestamp>". A school
row holds no personal data, so nothing about a real person is created to run
this. Every phase reports what it did and nothing about the credential.
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import db as _db                                          # noqa: E402

MARK = "__persistence_check__"


def engine():
    url = _db.resolve_database_url()
    if _db.is_sqlite(url):
        sys.exit("This proves nothing against SQLite. Point DATABASE_URL at "
                 "the Postgres instance you actually deploy.")
    from sqlalchemy import create_engine
    return create_engine(url, pool_pre_ping=True)


def inspect():
    from sqlalchemy import text
    eng = engine()
    with eng.connect() as c:
        tables = [r[0] for r in c.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' "
            "ORDER BY tablename")).fetchall()]
        print(f"tables in public: {len(tables)}")
        rev = c.execute(text("SELECT version_num FROM alembic_version")).fetchall()
        print(f"alembic_version : {[r[0] for r in rev]}")

        # What is actually in there. Row counts only — no contents, because
        # this may be pointed at a database with real students in it.
        interesting = ["users", "schools", "classes", "roster_names",
                       "class_members", "submissions", "materials",
                       "class_posts", "assignments", "tracks", "lessons"]
        print("\nrow counts:")
        for t in interesting:
            if t not in tables:
                print(f"  {t:16s} (table not present)")
                continue
            n = c.execute(text(f'SELECT count(*) FROM "{t}"')).scalar()
            print(f"  {t:16s} {n}")
    eng.dispose()
    return 0


def write():
    from sqlalchemy import text
    eng = engine()
    stamp = str(int(time.time()))
    name = MARK + stamp
    with eng.begin() as c:
        c.execute(text("INSERT INTO schools (name, city, country, created_at) "
                       "VALUES (:n, '', '', now())"), {"n": name})
    eng.dispose()
    print(f"wrote a row: {name}")
    print("Now run the 'check' phase as a SEPARATE process — that is the "
          "part that matters.")
    return 0


def check():
    from sqlalchemy import text
    eng = engine()
    with eng.connect() as c:
        rows = c.execute(text(
            "SELECT id, name, created_at FROM schools "
            "WHERE name LIKE :p ORDER BY id"), {"p": MARK + "%"}).fetchall()
    eng.dispose()
    if not rows:
        print("FAIL: nothing found. The write did not reach this database.")
        return 1
    for r in rows:
        print(f"found id={r[0]} {r[1]} written {r[2]}")
    print(f"\nPASS: {len(rows)} row(s) written by an earlier process are "
          f"readable by this one.")
    return 0


def cleanup():
    from sqlalchemy import text
    eng = engine()
    with eng.begin() as c:
        n = c.execute(text("DELETE FROM schools WHERE name LIKE :p"),
                      {"p": MARK + "%"}).rowcount
    eng.dispose()
    print(f"removed {n} marked row(s)")
    return 0


def revision():
    """Move the recorded revision, prove the refusal, put it back.

    The restore is in a finally block and is checked afterwards. Leaving this
    database at a revision that does not exist would stop the application
    booting, which is the correct behaviour and a very inconvenient way to
    find out that a test did not clean up after itself.
    """
    from sqlalchemy import text
    eng = engine()
    with eng.connect() as c:
        real = c.execute(text("SELECT version_num FROM alembic_version")).scalar()
    print(f"current revision: {real}")

    ok = False
    try:
        with eng.begin() as c:
            c.execute(text("UPDATE alembic_version SET version_num='0000_not_a_real_revision'"))
        print("temporarily set the revision to a value this code does not know")
        try:
            _db.require_schema_at_head(eng)
            print("FAIL: a wrong revision was accepted")
        except _db.ConfigError:
            print("PASS: refused, as it should be")
            ok = True
    finally:
        with eng.begin() as c:
            c.execute(text("UPDATE alembic_version SET version_num=:v"), {"v": real})
        with eng.connect() as c:
            back = c.execute(text("SELECT version_num FROM alembic_version")).scalar()
        print(f"restored revision: {back}")
        if back != real:
            print("ERROR: the revision was NOT restored. Fix this before "
                  "deploying — the app will refuse to start.")
            ok = False
        else:
            try:
                _db.require_schema_at_head(eng)
                print("PASS: accepted again at the real revision")
            except _db.ConfigError:
                print("ERROR: still refused after restore")
                ok = False
    eng.dispose()
    return 0 if ok else 1


PHASES = {"inspect": inspect, "write": write, "check": check,
          "cleanup": cleanup, "revision": revision}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in PHASES:
        sys.exit("usage: verify_persistence.py "
                 "{inspect|write|check|cleanup|revision}")
    sys.exit(PHASES[sys.argv[1]]())
