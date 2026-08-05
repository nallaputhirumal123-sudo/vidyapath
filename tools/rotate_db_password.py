"""Rotate the Postgres password without it ever being displayed.

RUN THIS IN YOUR OWN TERMINAL. Not through an assistant, not in CI, not in
anything that captures stdout — the whole point is that the credential does
not end up in a transcript.

Why this exists rather than "change POSTGRES_PASSWORD in Railway":

The Railway Postgres image reads POSTGRES_PASSWORD only when the data
directory is EMPTY. Once there is a database in the volume, changing that
variable rewrites the composed connection strings — DATABASE_URL,
DATABASE_PUBLIC_URL — and does NOT change the password the server will
actually accept. You end up with connection strings that no longer work
while the old password still does, which is worse than either.

So this does both, in the order that survives a failure between them:

  1. ALTER USER on the live server, so the real password changes.
  2. Update POSTGRES_PASSWORD so the composed URLs match.

If step 2 fails, the new password is printed so you can set it by hand. That
is the only circumstance in which it is printed.

It connects with PGHOST/PGUSER/PGPASSWORD as separate values rather than
parsing DATABASE_URL, because a password containing "@" or ":" makes that URL
ambiguous — which is the state this database is in right now.

    python tools/rotate_db_password.py --service Postgres-xK4G
"""
import argparse
import secrets
import subprocess
import sys


def railway_vars(service):
    """Every variable for the service, as a dict. Never printed."""
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--service", required=True)
    ap.add_argument("--length", type=int, default=24,
                    help="bytes of randomness; 24 gives a 48-character hex string")
    args = ap.parse_args()

    try:
        import psycopg2
    except ImportError:
        sys.exit("psycopg2 is not installed here. Run:\n"
                 "    .\\.venv\\Scripts\\python.exe -m pip install psycopg2-binary")

    v = railway_vars(args.service)

    # The public proxy, because this runs from a laptop and the private
    # hostname only resolves inside Railway's network.
    host = v.get("RAILWAY_TCP_PROXY_DOMAIN")
    port = v.get("RAILWAY_TCP_PROXY_PORT")
    user = v.get("PGUSER") or v.get("POSTGRES_USER")
    pw = v.get("PGPASSWORD") or v.get("POSTGRES_PASSWORD")
    dbname = v.get("PGDATABASE") or v.get("POSTGRES_DB") or "railway"

    missing = [n for n, x in (("RAILWAY_TCP_PROXY_DOMAIN", host),
                              ("RAILWAY_TCP_PROXY_PORT", port),
                              ("PGUSER", user), ("PGPASSWORD", pw)) if not x]
    if missing:
        sys.exit("These variables are not set on the service: "
                 + ", ".join(missing)
                 + "\nPublic networking may be turned off — this needs it.")

    # Hex only. The password this replaces contained "@", which is what made
    # the connection URL ambiguous in the first place; a new one that repeats
    # the mistake would fix nothing.
    new = secrets.token_hex(args.length)

    print(f"connecting to {host}:{port} as the database user...")
    try:
        conn = psycopg2.connect(host=host, port=int(port), user=user,
                                password=pw, dbname=dbname, connect_timeout=20)
    except Exception as e:
        sys.exit(f"could not connect: {type(e).__name__}: "
                 f"{str(e).strip().splitlines()[0][:120]}")

    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            # CURRENT_USER, so this cannot be pointed at a different role by
            # a typo. psycopg2 has no placeholder for a password literal in
            # ALTER USER, so it is quoted the way Postgres wants: single
            # quotes, doubled inside. `new` is hex, so there is nothing to
            # escape — the quoting is belt and braces.
            cur.execute("ALTER USER CURRENT_USER WITH PASSWORD '%s'"
                        % new.replace("'", "''"))
        print("the database password has been changed.")
    finally:
        conn.close()

    print("updating POSTGRES_PASSWORD so the composed URLs match...")
    p = subprocess.run(
        ["railway", "variables", "set", "--service", args.service,
         f"POSTGRES_PASSWORD={new}"],
        capture_output=True, text=True, shell=True, timeout=180)
    if p.returncode != 0:
        print("\n" + "!" * 62)
        print("The password WAS changed on the server, but the Railway")
        print("variable was NOT updated. Set it by hand now, or the app will")
        print("be holding a connection string that no longer works:")
        print()
        print("    POSTGRES_PASSWORD=" + new)
        print("!" * 62)
        sys.exit(1)

    print("done. Redeploy the app service so it picks up the new URL.")
    print("Nothing sensitive was printed.")


if __name__ == "__main__":
    main()
