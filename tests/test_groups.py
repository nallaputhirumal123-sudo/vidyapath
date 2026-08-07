"""What a coaching centre buys, and whether we can honestly say we have it.

A school says "Class 9". A coaching centre says MPC, BiPC, NEET, JEE — a
bundle of subjects across two years, and the thing a parent is actually
paying for. Asking a centre to pick "Class 11 Physics", then "Class 12
Physics", then "Class 11 Chemistry" is asking them to translate their own
product into ours before they can tell whether it is any use.

What this file is really about is the second half: not that the mapping
exists, but that it CANNOT overstate what is behind it.

Coverage is counted from the corpus on every call, never from a list. A
hard-coded "yes, Class 12 Biology" that the ingestion actually missed is not
a stale number — it is a promise made to a customer that the product then
breaks in front of a class. And a group with nothing behind it says so:
CEC has no Commerce, Economics or Civics in the corpus, and reports "none"
rather than a confident empty result.
"""
import io
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"

import groups as G                                  # noqa: E402
import main                                         # noqa: E402
from fastapi.testclient import TestClient           # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P, F = [], []


def ck(n, c, d=""):
    print(("PASS " if c else "FAIL ") + n + (f" — {d}" if d else ""),
          flush=True)
    (P if c else F).append(n)


print("\nthe groups a centre actually teaches")
ids = {g["id"] for g in G.GROUPS}
for want in ("mpc", "bipc", "mec", "cec", "jee", "neet", "foundation"):
    ck(f"{want} is there", want in ids)

print("\ncoverage is COUNTED, never claimed")
# The whole point. A list saying we hold a book we do not is a promise that
# breaks in front of a class, so this is asked of a database that says it
# holds nothing at all and every group has to admit it.
empty = sqlite3.connect(":memory:")
empty.execute("create table passages(body text, title text, track text, "
              "slug text)")
cov = G.coverage(empty)
ck("with an empty corpus, no group claims to be ready",
   all(g["state"] == "none" for g in cov),
   str([(g["name"], g["state"]) for g in cov]))
ck("and every book is listed as missing",
   all(g["missing"] for g in cov if g["books"]),
   "a centre reads this list and decides; silence would let them find out "
   "the hard way")

# And with a corpus that holds exactly one book, the group holding it is
# PARTIAL — not ready, and not nothing.
one = sqlite3.connect(":memory:")
one.execute("create table passages(body text, title text, track text, "
            "slug text)")
one.executemany("insert into passages values (?,?,?,?)",
                [("x", "Class 11 Physics: Units", "t", "s")] * 30)
cov1 = {g["id"]: g for g in G.coverage(one)}
ck("one book of three is partial, not ready",
   cov1["mpc"]["state"] == "partial", cov1["mpc"]["state"])
ck("and the two that are absent are named",
   any("Chemistry" in m for m in cov1["mpc"]["missing"]),
   str(cov1["mpc"]["missing"]))
ck("the passage count is real, not a tick",
   cov1["mpc"]["passages"] == 30, str(cov1["mpc"]["passages"]))

print("\nagainst the corpus this repo actually has")
corpus = os.path.join(ROOT, "corpus.db")
if os.path.exists(corpus):
    con = sqlite3.connect(f"file:{corpus}?mode=ro", uri=True)
    real = {g["id"]: g for g in G.coverage(con)}
    con.close()
    ck("MPC is backed by NCERT", real["mpc"]["state"] == "ready",
       str(real["mpc"]["state"]))
    ck("so is BiPC", real["bipc"]["state"] == "ready")
    ck("and it is thousands of passages, not a handful",
       real["mpc"]["passages"] > 2000, str(real["mpc"]["passages"]))
    # The one that must NOT overstate.
    ck("CEC says plainly that it is not covered",
       real["cec"]["state"] == "none" and real["cec"]["missing"],
       str(real["cec"]))
    ck("MEC admits the half it does not have",
       any("Commerce" in m for m in real["mec"]["missing"]),
       str(real["mec"]["missing"]))
else:
    ck("a corpus exists to check against", False, "corpus.db is missing")

print("\nand it answers before anybody has an account")
# "Which syllabus do you cover" is asked by a procurement officer or a centre
# owner, and it is asked before there is a login to give them.
anon = TestClient(main.app)
r = anon.get("/api/curriculum/groups")
ck("no session needed", r.status_code == 200, str(r.status_code))
d = r.json()
ck("it names the groups", len(d.get("groups", [])) >= 6,
   str(len(d.get("groups", []))))
ck("and says what a group is NOT",
   "not the same thing" in (d.get("note") or "").lower(),
   "NCERT Physics is what JEE is built on; it is not a JEE syllabus, and "
   "the wording that reaches a customer has to say so")
r = anon.get("/api/curriculum/groups?group=neet")
ck("one group can be asked for on its own",
   [g["id"] for g in r.json().get("groups", [])] == ["neet"],
   str([g["id"] for g in r.json().get("groups", [])]))

print("\nand a deployment without the books says so")
# corpus.db is gitignored — a fifteen-megabyte build artefact that takes
# hours to make — so a deployment built from the repository has no NCERT in
# it at all. Nothing said so: retrieval fell back to the site's own coding
# lessons, kept working, and every science question was answered from the
# model's memory with no source behind it. A product selling "answers from
# the syllabus" must not fail silently back to "answers from somewhere".
MAIN = io.open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
ck("a missing corpus is a warning, not a shrug",
   "WARNING: no corpus at" in MAIN,
   "shouted at boot rather than discovered by a coaching centre")
ck("and it says what to do about it",
   "Ship corpus.db, or point CORPUS_PATH at it." in MAIN)
ck("the coverage route reports what is really there",
   '"corpus": total' in MAIN,
   "a centre reading a 'ready' table on a server with no books is the worst "
   "possible version of this")

print("\nthe chapter titles a source is labelled with")
# These go in front of the model as [Class 7 Science: ...] and in front of a
# reader who wants to check something. NCERT sets its headings in a font
# that extracts with every character repeated.
import importlib.util                               # noqa: E402
_spec = importlib.util.spec_from_file_location(
    "fixt", os.path.join(ROOT, "tools", "fix_corpus_titles.py"))
_fix = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fix)
ck("a doubled heading is recovered",
   _fix.undouble("EEaarrtthh,, MMoooonn,, aanndd") == "Earth, Moon, and")
ck("and one repeated five times",
   _fix.undouble("UUUUUnnnnniiiiittttt") == "Unit")
ck("a real double letter is left alone",
   _fix.undouble("Pollution") == "Pollution",
   "one repeated letter is not a repeated word")
ck("and an unrecoverable heading falls back to the book",
   _fix.repair("Class 8 Science: CC PP MM") == "Class 8 Science",
   "the book is true; a string of consonants is not a chapter")

if os.path.exists(corpus):
    con = sqlite3.connect(f"file:{corpus}?mode=ro", uri=True)
    left = [t for (t,) in con.execute("select distinct title from passages")
            if _fix.repair(t)]
    con.close()
    ck("nothing garbled is left in the corpus", not left, str(left[:3]))

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
