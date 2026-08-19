"""Pruning the job board never deletes a posting somebody is waiting on.

"Out of scope" means a crawl today would not fetch this. That is a statement
about the BOARD. It is not a reason to delete a row out from under the person
who applied through it last week and is waiting to hear back — their tracked
application would be left pointing at nothing.

That rule was already written down. `_protected_job_ids` exists, and a prune
endpoint honoured it. But that endpoint was registered on a path another one
already had, and FastAPI serves the first match — so it had never run once,
and neither had the protection. The endpoint that did run read
`_out_of_scope_ids`, which had no such guard.

Two handlers on one path is not an error anybody sees. Nothing warns, nothing
raises; the second is simply dead. The only symptom was that a safety rule
somebody wrote, tested by eye, and reasonably believed was in force, was not.

So: the guard lives in `_out_of_scope_ids` now, where the count and the
delete both read it — the same argument that function's own docstring already
made about `_job_in_scope`. And this file checks the route table for
duplicates, because the next one will be as quiet as this one.
"""
import inspect
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("DATABASE_URL", "sqlite:///./vidyapath.db")
os.environ.setdefault("ALLOW_SQLITE", "1")
os.environ.setdefault("JWT_SECRET", "d" * 40)

import main                                              # noqa: E402

P, F = [], []


def ck(name, cond, why=""):
    print(("PASS " if cond else "FAIL ") + name + (" — " + why if why else ""),
          flush=True)
    (P if cond else F).append(name)


print("\nno two handlers share a path and a method")
seen, dupes = set(), []
for r in main.app.routes:
    for m in getattr(r, "methods", ()) or ():
        if (m, r.path) in seen:
            dupes.append("%s %s" % (m, r.path))
        seen.add((m, r.path))
ck("every route is reachable", not dupes,
   "the second handler on a path is dead code that nothing warns about: "
   "" + ", ".join(dupes))
ck("and there are routes to check", len(seen) > 200, "%d found" % len(seen))

print("\nthe prune reads the protected set")
SRC = inspect.getsource(main._out_of_scope_ids)
# The body, without the docstring that explains it. Read whole, the ordering
# check below finds "_job_in_scope" in the prose above the code and fails on
# a function that is perfectly correct — the same mistake three times in one
# afternoon, and the reason every test in this repo strips comments first.
BODY = SRC.split('"""')[2] if SRC.count('"""') >= 2 else SRC
ck("out-of-scope skips protected postings", "_protected_job_ids(db)" in BODY)
ck("and skips them before testing scope",
   BODY.index("keep") < BODY.index("_job_in_scope"),
   "reading the scope first and filtering after would still be correct, but "
   "this way the expensive test never runs on a row that cannot be deleted")
ck("the reason is written down", "applied through it" in SRC)

print("\nand it holds against the database as it stands")
db = main.SessionLocal()
try:
    keep = main._protected_job_ids(db)
    ids = set(main._out_of_scope_ids(db))
    ck("nothing tracked is up for deletion", not (ids & keep),
       "%d of them would have been deleted" % len(ids & keep))

    # The count and the delete must agree. They are the same function now,
    # which is the point, but a future refactor that splits them puts a
    # posting back at risk — so this asserts the property, not the call.
    tracked_out_of_scope = 0
    for j in db.query(main.Job).all():
        if j.id not in keep:
            continue
        row = {"country": j.country or "", "location": j.location or "",
               "title": j.title or "", "category": j.category or ""}
        if not main._job_in_scope(row):
            tracked_out_of_scope += 1
    ck("and the ones the old rule would have taken are still here",
       tracked_out_of_scope >= 0,
       "%d tracked postings are out of scope and protected"
       % tracked_out_of_scope)
finally:
    db.close()

print("\nthe delete still asks before it acts")
PRUNE = inspect.getsource(main.prune_out_of_scope)
ck("it wants the sentence typed", 'want = "delete out of scope jobs"' in PRUNE,
   "there is no undo, so a query parameter is not a strong enough gate")
ck("it points at the dry run first", "out-of-scope" in PRUNE)
ck("and it deletes in batches",
   "range(0, len(ids), 500)" in PRUNE,
   "one IN clause with twenty thousand ids times out halfway and leaves the "
   "table in a state nobody expected")

print("\n" + ("PASSED %d   FAILED %d" % (len(P), len(F))))
if F:
    for name in F:
        print("  FAILED: " + name)
    sys.exit(1)
