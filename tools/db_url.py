"""Build a working DATABASE_URL from Railway's parts, and write it to .env.

RUN THIS IN YOUR OWN TERMINAL. It writes a credential to .env (gitignored)
and prints nothing sensitive.

Why not just use DATABASE_PUBLIC_URL:

That variable is stored as a literal string, not as a template referencing
POSTGRES_PASSWORD. So after the password was rotated it still held the OLD
one, and the failure it produced pointed nowhere near the cause:

    could not translate host name "123@altaria.proxy.rlwy.net"

The old password contained an "@" and the username is an email address, so
the URL had three unescaped "@" in it and the parser chose the wrong one as
the host separator. The error blamed DNS. It was a stale password and a
character that should have been percent-encoded.

So this builds the URL from the individual variables instead — user, password,
host, port, database — and percent-encodes each part. Then it CONNECTS with
it before writing anything, because a connection string that has not been
tried is a guess.

    python tools/db_url.py --service Postgres-xK4G
"""
import argparse
import subprocess
import sys
import urllib.parse as up

ROOT_ENV = "C:\\Users\\nalla\\vidyapath\\.env"


def railway_vars(service):
    p = subprocess.run(
        ["railway", "variables", "list", "--service", service, "--kv"],
        capture_output=True, text=True, shell=True, timeout=180)
    if p.returncode != 0:
        sys.exit("railway CLI failed. Is the project linked? Run: railway link")
    out = {}
    for line in (p.stdout or "").splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def build(user, password, host, port, database):
    """A URL with every part percent-encoded.

    quote() with safe="" is the point: an email username and any password
    containing @ : / ? or # all become unambiguous. This is what the stored
    DATABASE_PUBLIC_URL should have been.
    """
    return "postgresql://%s:%s@%s:%s/%s" % (
        up.quote(user, safe=""), up.quote(password, safe=""),
        host, port, up.quote(database, safe=""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--service", required=True)
    ap.add_argument("--out", default=ROOT_ENV)
    args = ap.parse_args()

    try:
        import psycopg2                                   # noqa: F401
    except ImportError:
        sys.exit("psycopg2 is not installed. Run:\n"
                 "    .\\.venv\\Scripts\\python.exe -m pip install psycopg2-binary")
    import psycopg2

    v = railway_vars(args.service)
    host = v.get("RAILWAY_TCP_PROXY_DOMAIN")
    port = v.get("RAILWAY_TCP_PROXY_PORT")
    user = v.get("PGUSER") or v.get("POSTGRES_USER")
    database = v.get("PGDATABASE") or v.get("POSTGRES_DB") or "railway"

    if not (host and port and user):
        sys.exit("Missing RAILWAY_TCP_PROXY_DOMAIN / RAILWAY_TCP_PROXY_PORT / "
                 "PGUSER on that service. Public networking must be on for "
                 "this to work from a laptop.")

    # The password may have been rotated in one variable and not another, so
    # try each candidate and report WHICH ONE worked by name. That is the
    # diagnostic: if PGPASSWORD works and POSTGRES_PASSWORD does not, the two
    # have drifted and something is holding a stale value.
    candidates = []
    for name in ("POSTGRES_PASSWORD", "PGPASSWORD"):
        if v.get(name) and (name, v[name]) not in candidates:
            candidates.append((name, v[name]))
    if not candidates:
        sys.exit("No password variable found on that service.")

    print(f"host {host}:{port}, database {database}")
    print(f"trying {len(candidates)} password variable(s)...")

    working = None
    for name, pw in candidates:
        url = build(user, pw, host, port, database)
        try:
            c = psycopg2.connect(url, connect_timeout=20)
            c.close()
            print(f"  {name}: CONNECTED")
            working = url
            break
        except Exception as e:
            first = str(e).strip().splitlines()[0][:90]
            print(f"  {name}: failed — {first}")

    if not working:
        sys.exit("\nNone of the stored passwords connect. If the password was "
                 "just rotated, the variables may not have caught up — check "
                 "the Postgres service has finished redeploying.")

    with open(args.out, "w", encoding="ascii", newline="\n") as fh:
        fh.write("DATABASE_URL=" + working + "\n")
    print(f"\nwrote {args.out}")
    print("It is gitignored. alembic and preflight both read it, so you do "
          "not need to export anything.")
    print("\nNext:")
    print("    .\\.venv\\Scripts\\python.exe -m alembic upgrade head")
    print("    .\\.venv\\Scripts\\python.exe preflight.py")


if __name__ == "__main__":
    main()
