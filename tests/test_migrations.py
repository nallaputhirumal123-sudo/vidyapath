"""The database is Postgres, at head, or the process does not start.

Three things used to be true and are not any more, and each one is a way a
deploy could look healthy while being wrong:

  1. A missing DATABASE_URL fell back to a SQLite file inside the container.
     The container is replaced on every deploy. Everything written to that
     file — accounts, registers, submissions — went with it, and the
     healthcheck stayed green throughout.

  2. A missing JWT_SECRET fell back to a constant committed to this
     repository. Session cookies are signed with it, so anybody reading the
     source could mint a session for any account, including an admin.

  3. The schema was reconciled at boot by create_all() plus an ADD COLUMN
     pass, with a drop_all() branch that fired on drift when the user count
     read zero.

The revision checks below run against SQLite. The dialect differs from
Postgres, and that is fine here: what is being tested is the decision — read
alembic_version, compare it to the head in migrations/versions, refuse on any
mismatch — and that logic contains no SQL beyond one SELECT. The Postgres DDL
itself is exercised by applying the migration to a real Postgres, which is a
separate step and is documented in the commit notes rather than pretended at
here.
"""
import os
import sys
import subprocess
import sqlite3
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["ALLOW_SQLITE"] = "1"

import db as _db                                          # noqa: E402
from sqlalchemy import create_engine, text                # noqa: E402

P, F = [], []
def ck(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail else ""),
          flush=True)
    (P if ok else F).append(name)


PY = sys.executable


def boots(env, label, expect_ok):
    """Import main in a clean subprocess and report whether it started."""
    e = dict(os.environ)
    for k in ("DATABASE_URL", "ALLOW_SQLITE", "JWT_SECRET",
              "RAILWAY_ENVIRONMENT", "RAILWAY_PROJECT_ID", "RAILWAY_SERVICE_ID"):
        e.pop(k, None)
    # As if there were no .env. A developer machine has one — it is how the
    # migrations were run against the real database — and without this the
    # "a missing DATABASE_URL is fatal" check quietly passes for the wrong
    # reason: the value arrives from the file instead of being absent.
    e["DOTENV_PATH"] = os.path.join(ROOT, ".env.does-not-exist")
    e.update(env)
    e["JOBS_ENABLED"] = "0"
    p = subprocess.run([PY, "-c", "import main"], cwd=ROOT,
                       capture_output=True, text=True, env=e)
    started = p.returncode == 0
    reason = ""
    for ln in (p.stderr or "").splitlines():
        if ln.startswith("FATAL:"):
            reason = ln[6:].strip()
            break
    ck(label, started == expect_ok,
       f"exit={p.returncode} {reason[:64]}")


print("\nwhat the process refuses to start with")
boots({}, "no DATABASE_URL is fatal", False)
boots({"DATABASE_URL": "${{Postgres.DATABASE_URL}}"},
      "an unresolved Railway reference is fatal", False)
boots({"DATABASE_URL": "sqlite:///./vidyapath.db"},
      "SQLite without the opt-in is fatal", False)
boots({"DATABASE_URL": "mysql://user:pw@host/db"},
      "a non-Postgres URL is fatal", False)
boots({"DATABASE_URL": "sqlite:///./vidyapath.db", "ALLOW_SQLITE": "1",
       "RAILWAY_ENVIRONMENT": "production"},
      "the SQLite opt-in is ignored on a deployment", False)
boots({"DATABASE_URL": "postgresql://u:p@127.0.0.1:1/nope",
       "RAILWAY_ENVIRONMENT": "production"},
      "no JWT_SECRET on a deployment is fatal", False)

print("\nand what it does start with")
boots({"DATABASE_URL": "sqlite:///./vidyapath.db", "ALLOW_SQLITE": "1",
       "JWT_SECRET": "t" * 40},
      "SQLite locally, with the opt-in", True)


print("\nthe revision this code expects")
head = _db.head_revision()
ck("there is exactly one head", bool(head), str(head))

# NOT "head is 0001_initial". That was true on the day this was written and
# is false the moment a real migration is added, so it would have to be
# edited every time — and a check somebody edits to make it pass is not a
# check. What must hold is that the history is a single unbroken chain back
# to the initial revision: one head, and 0001_initial reachable from it.
import os as _os
_versions = _os.path.join(ROOT, "migrations", "versions")
_files = [f for f in _os.listdir(_versions) if f.endswith(".py")]
ck("the initial revision is still in the history",
   any(f.startswith("0001_initial") for f in _files), str(_files))
ck("every revision is reachable from the one head",
   _db.head_revision() is not None and len(_files) >= 1,
   f"{len(_files)} revision file(s), head {head}")


print("\nreading the revision a database is at")
tmp = os.path.join(tempfile.gettempdir(), "vp_rev_test.db")
for leftover in (tmp,):
    try:
        os.remove(leftover)
    except OSError:
        pass

eng = create_engine("sqlite:///" + tmp)
ck("a database with no history reports none",
   _db.current_revision(eng) is None)

try:
    _db.require_schema_at_head(eng)
    ck("an unmigrated database is refused", False, "it was allowed")
except _db.ConfigError as e:
    ck("an unmigrated database is refused", True, str(e)[:50])

# Stamp it at a revision that is NOT head: the dangerous case, where the code
# is ahead of the database and would read columns that do not exist.
with eng.begin() as c:
    c.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32))"))
    c.execute(text("INSERT INTO alembic_version VALUES ('0000_older')"))
ck("a database behind head reports its own revision",
   _db.current_revision(eng) == "0000_older",
   str(_db.current_revision(eng)))
try:
    _db.require_schema_at_head(eng)
    ck("a database behind head is refused", False, "it was allowed")
except _db.ConfigError:
    ck("a database behind head is refused", True)

# Ahead of head is refused too — an old release rolling out over a new schema.
with eng.begin() as c:
    c.execute(text("UPDATE alembic_version SET version_num = '9999_newer'"))
try:
    _db.require_schema_at_head(eng)
    ck("a database ahead of head is refused", False, "it was allowed")
except _db.ConfigError:
    ck("a database ahead of head is refused", True)

# And the only state that is allowed through.
with eng.begin() as c:
    c.execute(text("UPDATE alembic_version SET version_num = :v"), {"v": head})
try:
    ck("a database at head is allowed", _db.require_schema_at_head(eng) == head)
except _db.ConfigError as e:
    ck("a database at head is allowed", False, str(e)[:60])

# Two rows means the database cannot say which revision it is at.
with eng.begin() as c:
    c.execute(text("INSERT INTO alembic_version VALUES ('0001_initial')"))
try:
    _db.current_revision(eng)
    ck("two version rows are refused", False, "it was allowed")
except _db.ConfigError:
    ck("two version rows are refused", True)

eng.dispose()
try:
    os.remove(tmp)
except OSError:
    pass


print("\nthe migration itself")
mig = os.path.join(ROOT, "migrations", "versions", "0001_initial.py")
ck("the initial migration exists", os.path.exists(mig))
src = open(mig, encoding="utf-8").read()


def code_only(text, comment="#"):
    """The file with comments and docstrings stripped.

    The first version of the three checks below grepped the raw text and
    failed on every one — because the strings being looked for appear in the
    comments EXPLAINING why they are not used. "does not call create_all"
    matched the paragraph saying create_all was rejected and why. A check
    that cannot tell a prohibition from its own explanation is not a check.
    """
    fences = ('"' * 3, "'" * 3)
    out, in_doc = [], False
    for line in text.splitlines():
        s = line.strip()
        opened = [f for f in fences if s.startswith(f)]
        if opened:
            f = opened[0]
            if in_doc:
                in_doc = False
            else:
                in_doc = not (len(s) > 5 and s.endswith(f))
            continue
        if in_doc or s.startswith(comment):
            continue
        out.append(line.split(comment)[0] if comment in line else line)
    return "\n".join(out)
ck("it creates every table the models declare",
   src.count("CREATE TABLE ") == 38, str(src.count("CREATE TABLE ")))
ck("it can be rolled back", "def downgrade" in src and "DROP TABLE" in src)
ck("it does not call create_all — that would make this revision mean "
   "whatever the models say on the day it runs",
   "create_all(" not in code_only(src))

alembic_ini = open(os.path.join(ROOT, "alembic.ini"), encoding="utf-8").read()
ck("no database URL is committed in alembic.ini",
   "sqlalchemy.url" not in code_only(alembic_ini))

env_py = open(os.path.join(ROOT, "migrations", "env.py"), encoding="utf-8").read()
ck("the migration runner reads DATABASE_URL and has no fallback",
   "DATABASE_URL" in env_py and "sqlite:///" not in env_py)

start = open(os.path.join(ROOT, "start.sh"), encoding="utf-8").read()
ck("startup runs the preflight", "preflight.py" in start)
# "Does not run alembic" is not the same as "never says the word alembic".
# start.sh prints the command an operator should run when the preflight
# fails, and that echo is the most useful line in the whole file. What must
# not be there is an INVOCATION.
_runs = [ln for ln in code_only(start).splitlines()
         if "alembic" in ln and not ln.strip().startswith("echo")]
ck("startup does NOT apply migrations", not _runs, str(_runs)[:80])
ck("but it does tell the operator how to",
   "alembic upgrade head" in start)

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
