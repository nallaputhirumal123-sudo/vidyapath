"""Every column on a model has a migration behind it.

This is the test that would have prevented a live outage, and the outage is
worth writing down, because the guard already in place could not have caught
it and was not at fault.

`User.phone` was added to the model in one commit and its migration in the
next. The image built from the first commit contained:

    a model that SELECTs users.phone
    a migrations directory whose head is 0005, which never creates it

preflight compares the revision the code expects against the revision the
database is at. Inside that image both were 0005. **So preflight passed, and
it was right to.** It checks the version stamp, not the shape — it cannot
know a model grew a column no migration creates.

Then the app started, `seed_if_empty()` raised psycopg2 UndefinedColumn, and
that is a plain SQLAlchemy error rather than the ConfigError the startup
handler exits hard on. So it fell into the generic retry branch, gave up
after five attempts, printed a warning, and served anyway. Every request that
resolved a user 500'd. The site was up, passing its healthcheck, and broken.

The honest way to check this would be to run the migrations into an empty
database and compare. This project refuses to migrate SQLite — deliberately,
because SQLite has no ALTER TABLE worth the name and a migration that works
there proves nothing about Postgres — and a test must not need a live
Postgres to run. So it asks the question of the migration SOURCE instead:
does anything in migrations/versions ever create this column?

That is coarser than a real schema diff and it catches the case that actually
bites: a column that exists only on the model, which no migration has ever
heard of.
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"
os.environ["JOBS_ENABLED"] = "0"

import main                                              # noqa: E402
import db as _dbmod                                      # noqa: E402

P, F = [], []


def ck(n, c, d=""):
    print(("PASS " if c else "FAIL ") + n + (f" — {d}" if d else ""),
          flush=True)
    (P if c else F).append(n)


VDIR = os.path.join(ROOT, "migrations", "versions")
files = sorted(f for f in os.listdir(VDIR) if f.endswith(".py"))
SRC = "\n".join(io.open(os.path.join(VDIR, f), encoding="utf-8").read()
                for f in files)
# 0001 holds its DDL as Python string literals, so the file contains the two
# characters \ and t where the SQL has a tab. Left alone, `\n\tlevel` reads as
# the word "tlevel" and every column at the start of a DDL line looks
# missing. Turn the escapes back into whitespace before matching.
SRC_RAW = SRC
SRC = SRC.replace("\\n", "\n").replace("\\t", "\t")

print("\nthe migrations are a single unbroken chain")
revs, downs = {}, {}
for f in files:
    t = io.open(os.path.join(VDIR, f), encoding="utf-8").read()
    r = re.search(r'^revision\s*=\s*["\']([^"\']+)', t, re.M)
    d = re.search(r'^down_revision\s*=\s*(?:["\']([^"\']+)|None)', t, re.M)
    if r:
        revs[r.group(1)] = f
        downs[r.group(1)] = d.group(1) if (d and d.group(1)) else None

ck("every revision is unique", len(revs) == len(files), f"{len(revs)} of {len(files)}")
parents = [v for v in downs.values() if v]
heads = [r for r in revs if r not in parents]
ck("there is exactly one head", len(heads) == 1, ", ".join(sorted(heads)))
ck("and db.head_revision agrees with it",
   len(heads) == 1 and _dbmod.head_revision() == heads[0],
   f"{_dbmod.head_revision()} vs {heads}")
orphans = [r for r, d in downs.items() if d and d not in revs]
ck("no revision points at a parent that is not there", not orphans,
   ", ".join(orphans))

print("\nand every column a model declares is created by one of them")
# The exact failure this exists for. A column present only on the model
# passes every revision check and then 500s on whichever route touches it
# first — which is every route, when the model is User.
#
# Matched by name against the migration source. A column created inside a
# create_table() and one added later by add_column() both mention it, which
# is all this needs to know.
#
# Matched on a word boundary rather than a quoted string, because 0001 is
# frozen literal DDL — `qkey VARCHAR(500) NOT NULL` — and later revisions use
# sa.Column("name", ...). Both forms contain the bare word; only the later
# ones quote it.
def _named(word):
    return re.search(r"\b%s\b" % re.escape(word), SRC) is not None


unbacked = []
for t in main.Base.metadata.sorted_tables:
    if not _named(t.name):
        unbacked.append(f"{t.name} (whole table)")
        continue
    for col in t.columns:
        if not _named(col.name):
            unbacked.append(f"{t.name}.{col.name}")

ck("no model column is missing a migration", not unbacked,
   ", ".join(unbacked[:8]) or "none")
if unbacked:
    print("\n  Write a migration that creates them and bump the head.\n"
          "  A column that exists only on the model passes preflight — the\n"
          "  stamp says the database ran every migration, and it did; none\n"
          "  of them made this column.\n", flush=True)

print("\nand the startup path does not serve through a schema error")
# seed_if_empty() raising UndefinedColumn took the generic branch, which
# retries and then carries on. ConfigError exits hard; a missing column is
# not a ConfigError, so it did not.
_M = io.open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
ck("a schema refusal still exits rather than serving",
   "os._exit(1)" in _M,
   "raising would be caught by uvicorn's startup handling and the process "
   "could survive with no schema")
ck("and /api/status reports what went wrong at boot",
   '"startup_error": STARTUP_ERROR' in _M,
   "this is how the cause was found; it should stay reachable")

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\nPASSED {len(P)}   FAILED {len(F)}")
sys.exit(1 if F else 0)
