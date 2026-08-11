"""Every reference has a name and a link, and pupils are not sent to the
open internet.

**The word "undefined", forty times, on a page that is nothing but links.**
curriculum.json and stage4 write {"t", "u"}; stage5, stage6 and stage7 write
{"title", "url"}. Everything that reads them reads t and u — so twenty-seven
references across Deep Learning, NLP, AI in the Cloud and the Capstone
rendered as the literal text "undefined" wrapped in a link to nowhere. Two
spellings of the same idea, and nothing reconciled them.

Normalised at both ends. On the way IN, so no future file reintroduces it by
picking either name. On the way OUT as well, because seeding skips a track
that already exists — every database seeded before this fix still holds the
broken rows, and those are the live ones. Fixing it on read repairs them with
no migration and without touching anybody's curriculum.

An entry missing either half is dropped rather than shown empty: a row nobody
can click is not a row.

**And the page is not for a school's pupils.** It lists every video and
outside reference across the whole platform — the open internet, one tap from
a child's timetable, with nothing between them and it. A school gave us their
class. What a pupil sees should be what their teacher put in front of them,
which is the subject page; their teacher can still hand them any of this.
Hidden from the menu AND refused by the router, because #resources is four
characters to guess and a hidden menu item is not a permission.
"""
import io
import os
import sys
import glob
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"
os.environ["JOBS_ENABLED"] = "0"

import main                                        # noqa: E402

IDX = io.open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
P, F = [], []


def ck(n, c, d=""):
    print(("PASS " if c else "FAIL ") + n + (f" — {d}" if d else ""),
          flush=True)
    (P if c else F).append(n)


print("\nboth spellings become one")
ck("t/u survives", main._links([{"t": "A", "u": "http://a"}])
   == [{"t": "A", "u": "http://a"}])
ck("title/url is converted",
   main._links([{"title": "B", "url": "http://b"}])
   == [{"t": "B", "u": "http://b"}],
   "stage5, stage6 and stage7 all use this spelling")
ck("half an entry is dropped, not shown blank",
   main._links([{"title": "no link"}, {"url": "http://c"}]) == [],
   "a row nobody can click is not a row")
ck("and junk cannot crash the page",
   main._links(["nonsense", None, 7, {}]) == [] and main._links(None) == [])

print("\nnormalised on the way in AND on the way out")
MAIN = io.open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
ck("seeding normalises", 'videos=json.dumps(_links(l.get("videos")))' in MAIN)
ck("and serving normalises too",
   '"refs": _links(json.loads(l.refs or "[]")),' in MAIN,
   "seeding skips tracks that already exist, so the broken rows are the "
   "live ones and only the read path reaches them")

print("\nthe files themselves still disagree, and that is now harmless")
shapes = set()
for f in glob.glob(os.path.join(ROOT, "*.json")):
    try:
        d = json.load(io.open(f, encoding="utf-8"))
    except Exception:
        continue
    for t in (d.get("tracks") if isinstance(d, dict) else []) or []:
        for l in (t.get("lessons") or []):
            for k in ("videos", "refs"):
                for it in (l.get(k) or []):
                    if isinstance(it, dict):
                        shapes.add("t" if "t" in it else
                                   ("title" if "title" in it else "?"))
ck("both spellings really are present in the curriculum files",
   shapes >= {"t", "title"}, str(sorted(shapes)),)
# Run every link in every curriculum file through the normaliser and insist
# none of them comes out half-formed. That is the check that would have
# caught this on the day stage5 was written.
_all = []
for f in glob.glob(os.path.join(ROOT, "*.json")):
    try:
        d = json.load(io.open(f, encoding="utf-8"))
    except Exception:
        continue
    for t in (d.get("tracks") if isinstance(d, dict) else []) or []:
        for l in (t.get("lessons") or []):
            _all += main._links(l.get("videos")) + main._links(l.get("refs"))
_broken = [x for x in _all if not x.get("t") or not x.get("u")]
ck("every link in every curriculum file normalises to a name and a URL",
   _all and not _broken, f"{len(_all)} links, {len(_broken)} half-formed")

print("\nnot offered to a school's pupils")
ck("the menu item is withheld from them",
   'USER.craxlearn_only?"":nav("resources","🔗","All resources")' in IDX)
ck("and typing the address does not get there either",
   "if(USER && USER.craxlearn_only) renderHome(); else renderResources();"
   in IDX,
   "a hidden menu item is not a permission")
ck("staff never had it and still do not",
   "if(!staff){" in IDX,
   "a school admin checking a fee is not offered a game engine either")

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\nPASSED {len(P)}   FAILED {len(F)}")
sys.exit(1 if F else 0)
