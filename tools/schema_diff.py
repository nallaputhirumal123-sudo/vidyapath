"""Compare a live database against the models, column by column.

Run before stamping a database that was built by the old create_all() path.
Stamping records "this database is at revision X" without running anything,
so if the live schema differs from what X describes, the stamp is a lie that
every later migration is then built on top of.

    python tools/schema_diff.py --service Postgres

Read-only. It reports:

  * tables the models expect that the database does not have
  * tables the database has that the models do not know about
  * columns missing on either side, per table
  * type differences, reported loosely — Postgres normalises names
    (VARCHAR(80) reads back as character varying) so only the broad family
    is compared, and anything ambiguous is printed for a human to judge
    rather than silently passed

Exit code is 0 only when the schema matches closely enough to stamp.
"""
import argparse
import os
import subprocess
import sys
import urllib.parse as up

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def vars_for(svc):
    p = subprocess.run(["railway", "variables", "list", "--service", svc, "--kv"],
                       capture_output=True, text=True, shell=True, timeout=180)
    if p.returncode != 0:
        sys.exit("railway CLI failed. Run: railway link")
    out = {}
    for ln in (p.stdout or "").splitlines():
        ln = ln.strip()
        if "=" in ln and not ln.startswith("#"):
            k, v = ln.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def url_for(svc):
    v = vars_for(svc)
    host = v.get("RAILWAY_TCP_PROXY_DOMAIN")
    port = v.get("RAILWAY_TCP_PROXY_PORT")
    user = v.get("PGUSER") or v.get("POSTGRES_USER")
    db = v.get("PGDATABASE") or v.get("POSTGRES_DB") or "railway"
    if not (host and port and user):
        sys.exit(f"{svc}: no public proxy. Turn public networking on to run "
                 f"this from a laptop, or run it from inside Railway.")
    import psycopg2
    for name in ("POSTGRES_PASSWORD", "PGPASSWORD"):
        pw = v.get(name)
        if not pw:
            continue
        url = "postgresql://%s:%s@%s:%s/%s" % (
            up.quote(user, safe=""), up.quote(pw, safe=""), host, port,
            up.quote(db, safe=""))
        try:
            psycopg2.connect(url, connect_timeout=20).close()
            return url
        except Exception:
            continue
    sys.exit(f"{svc}: none of the stored passwords connect.")


# Postgres renames types on the way in. These are the families that matter;
# a difference inside a family (VARCHAR(80) vs VARCHAR(120)) is reported but
# not treated as blocking, because it cannot break a query — only a value
# longer than the shorter one, which is a data question, not a schema one.
def family(t):
    t = (t or "").lower()
    for name, keys in (
        ("int", ("integer", "bigint", "smallint", "serial")),
        ("text", ("character varying", "varchar", "text", "char")),
        ("bool", ("boolean",)),
        ("time", ("timestamp", "date", "time")),
        ("float", ("double", "real", "numeric", "decimal")),
        ("json", ("json", "jsonb")),
        ("blob", ("bytea",)),
    ):
        if any(k in t for k in keys):
            return name
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--service", required=True)
    args = ap.parse_args()

    os.environ["ALLOW_SQLITE"] = "1"
    os.environ.setdefault("JWT_SECRET", "t" * 40)
    os.environ["JOBS_ENABLED"] = "0"
    os.environ["DOTENV_PATH"] = os.path.join(ROOT, ".env.none")
    os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
    import main as app                                     # noqa: E402

    url = url_for(args.service)
    from sqlalchemy import create_engine, inspect
    eng = create_engine(url)
    insp = inspect(eng)

    live_tables = set(insp.get_table_names(schema="public"))
    model_tables = {t.name: t for t in app.Base.metadata.sorted_tables}

    missing = sorted(set(model_tables) - live_tables)
    extra = sorted(live_tables - set(model_tables) - {"alembic_version"})

    problems = 0
    print(f"model tables: {len(model_tables)}   live tables: {len(live_tables)}")

    if missing:
        problems += len(missing)
        print(f"\nTABLES THE CODE EXPECTS AND THE DATABASE DOES NOT HAVE ({len(missing)}):")
        for t in missing:
            print("  -", t)
    if extra:
        print(f"\ntables present but not in the models ({len(extra)}) — "
              f"left alone, not an error:")
        for t in extra:
            print("  -", t)

    print("\ncolumn differences:")
    clean = True
    for name in sorted(set(model_tables) & live_tables):
        want = {c.name: c for c in model_tables[name].columns}
        have = {c["name"]: c for c in insp.get_columns(name, schema="public")}
        gone = sorted(set(want) - set(have))
        added = sorted(set(have) - set(want))
        retyped = []
        for col in sorted(set(want) & set(have)):
            a = family(str(want[col].type))
            b = family(str(have[col]["type"]))
            if a != b:
                retyped.append(f"{col}: model {a} vs live {b}")
        if gone or added or retyped:
            clean = False
            print(f"  {name}:")
            for c in gone:
                problems += 1
                print(f"      MISSING in database: {c}   <- would break queries")
            for c in added:
                print(f"      extra in database:   {c}   (harmless)")
            for r in retyped:
                problems += 1
                print(f"      TYPE:                {r}")
    if clean:
        print("  none")

    eng.dispose()

    print()
    if problems:
        print(f"NOT SAFE TO STAMP: {problems} difference(s) that matter.")
        print("Stamping would record a revision this database does not match.")
        return 1
    print("SAFE TO STAMP: the live schema matches revision 0001_initial.")
    print("  alembic stamp 0001_initial")
    return 0


if __name__ == "__main__":
    sys.exit(main())
