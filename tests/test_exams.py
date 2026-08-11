"""Past papers pointed at, and an entrance syllabus stated.

**We do not hold a single past paper and this test is what keeps it that
way.** Every board owns the copyright in its own question papers. The sites
that stack up thousands of them are doing it without permission, and a
school that buys a product built on those inherits the problem — so the
product is a directory, not a library, and the check below is that nothing
here is a stored paper.

The link a teacher taps is the board's own page, which is also the only copy
certainly the real paper: correctly printed, with the board's own
corrections in it.

**"Past papers" means three different things across these boards** and a
teacher must learn which before spending a free period on it. CBSE publishes
the papers actually sat. CISCE publishes specimens. Cambridge and the IB
release theirs only to registered centres, and the IB sells them. Each
source therefore carries what is really there.

**Every host was checked, and DNS is the test that matters.** A state board
that resolves but refuses this machine is geo-blocking or bot-blocking, and
works fine for the teacher in Hyderabad who actually clicks it. A host with
no DNS at all is simply wrong — two were, and both are fixed: tsche.ac.in
went away when Telangana renamed the council TGCHE, and Goa's board is on
gov.in.

**The syllabus half is the opposite case.** An authority publishes a topic
list precisely so candidates can study it; repeating it is the intended use.
What earns the page is the difference — the units the exam adds on top of
the books a candidate already owns — so `extra` is the product and the rest
they have. And every exam carries the authority's own document, because
these get revised and a list in a file goes stale without saying so.
"""
import io
import os
import re
import socket
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import exams                                       # noqa: E402

IDX = io.open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
MAIN = io.open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
SRC = io.open(os.path.join(ROOT, "exams.py"), encoding="utf-8").read()
LIVE = "--live" in sys.argv
P, F = [], []


def ck(name, cond, why=""):
    print(("PASS " if cond else "FAIL ") + name + (" — " + why if why else ""),
          flush=True)
    (P if cond else F).append(name)


print("\nno paper is held here")
ck("nothing stores a question paper",
   not re.search(r"\.pdf['\"]", SRC),
   "a board owns its papers; a product that copies them hands its schools "
   "the problem")
ck("every source is a link to the board itself",
   all(s["url"].startswith("https://") for s in exams.SOURCES))
ck("and the API says so where a renderer cannot drop it",
   "Nothing is copied here" in MAIN)

print("\nwhat is actually at the other end, per board")
ck("every source says which of the three it is",
   all(s.get("papers") in ("free", "specimen", "login")
       for s in exams.SOURCES))
ck("CISCE is marked specimen, not free",
   exams.BY_ID["cisce"]["papers"] == "specimen",
   "it publishes specimens; the sat papers go to registered schools")
ck("Cambridge and the IB are marked restricted",
   exams.BY_ID["cambridge"]["papers"] == "login"
   and exams.BY_ID["ib"]["papers"] == "login",
   "a teacher should learn that here, not after ten minutes of clicking")
ck("CBSE and JEE Advanced are marked free",
   exams.BY_ID["cbse"]["papers"] == "free"
   and exams.BY_ID["jee-adv"]["papers"] == "free")
ck("the screen spells out what each word means",
   "not the papers sat" in IDX and "registered centres" in IDX)

print("\nthe boards a school in India actually sits")
have = {s.get("state") for s in exams.SOURCES}
for st in ("Telangana", "Andhra Pradesh", "Maharashtra", "Tamil Nadu",
           "Karnataka", "Kerala", "West Bengal", "Uttar Pradesh", "Bihar",
           "Gujarat", "Rajasthan", "Punjab", "Assam", "Odisha"):
    ck(st + " is listed", st in have)
ck("Class 10 and Class 12 are separate where the state splits them",
   len([s for s in exams.SOURCES if s.get("state") == "Telangana"]) == 2,
   "a teacher searching a state wants both and should not have to know the "
   "acronym that splits them")
ck("EAMCET is findable by the name people say",
   any("eamcet" in exams._hay(s) for s in exams.SOURCES),
   "the exam was renamed EAPCET and nobody calls it that")

print("\nsearch narrows as a teacher types")
ck("one word finds a state", len(exams.search("telangana")) == 2)
ck("two words narrow it", len(exams.search("telangana intermediate")) == 1,
   "a search that grows as you type reads as broken")
ck("nonsense finds nothing", exams.search("qwertyuiop") == [])
ck("the kind filter holds",
   all(s["kind"] == "state" for s in exams.search("", "state")))
ck("jee finds both papers", len(exams.search("jee")) >= 2)

print("\nthe hosts resolve")
bad = []
for s in exams.SOURCES:
    host = s["url"].split("://", 1)[1].split("/")[0]
    try:
        socket.gethostbyname(host)
    except Exception:
        bad.append(s["id"] + " (" + host + ")")
ck("every board's domain exists", not bad, ", ".join(bad))
ck("the dead Telangana council host is gone",
   not any("tsche.ac.in" in s["url"] for s in exams.SOURCES),
   "TSCHE became TGCHE and the old host stopped resolving entirely")

print("\nthe syllabus states the difference, which is the whole point")
for e in ("jee-main", "jee-adv", "eapcet", "neet"):
    ck(e + " is held", exams.syllabus(e) is not None)
ck("EAMCET is not listed under its official name alone",
   exams.syllabus("eapcet")["name"].startswith("EAMCET"))
ck("nothing unknown is invented", exams.syllabus("gate") is None)
jm = exams.syllabus("jee-main")
ck("every unit carries the extra flag",
   all("extra" in u for s in jm["subjects"] for u in s["units"]))
ck("JEE marks the practical list as beyond the books",
   any(u["extra"] for s in jm["subjects"] for u in s["units"]),
   "a candidate already owns the books; what they cannot see is the "
   "difference")
ck("the counted total matches the flagged units",
   all(s["extra"] == sum(1 for u in s["units"] if u["extra"])
       for s in jm["subjects"]))
ck("EAMCET says it is the state Intermediate syllabus",
   "not a separate syllabus" in exams.syllabus("eapcet")["note"],
   "the single most useful true thing about it, and it stops a candidate "
   "buying a second set of books")
ck("NEET says Biology is half the paper",
   "half the paper" in exams.syllabus("neet")["note"])
ck("every exam links the authority's own document",
   all(e["syllabus_url"].startswith("https://") for e in exams.EXAMS))
ck("and the screen puts that link on the card, not in a footnote",
   "The official syllabus" in IDX,
   "a topic list in a file goes stale silently; a candidate must be able "
   "to check")

print("\nreachable, and to the right people")
ck("the papers route exists", '@app.get("/api/exams/papers")' in MAIN)
ck("the syllabus route exists", '@app.get("/api/exams/syllabus")' in MAIN)
ck("an unknown exam is a 404, not an empty page",
   'raise HTTPException(404, "No syllabus held for that exam.")' in MAIN)
ck("the page is routed", 'v.page==="exams"' in IDX)
ck("a learner is offered it beside their class",
   'staff ? "" : nav("exams"' in IDX)
ck("a teacher is offered it, and the office is not",
   'if(teaching) h+=nav("exams"' in IDX,
   "a head who takes no class does not set a paper")
ck("the paper search opens first for both of them",
   'if(!EXAMV.tab) EXAMV.tab = "papers";' in IDX,
   "a student revising and a teacher setting a paper want the same thing; "
   "neither should have to find a tab for it")
ck("and a student's own line says they can search papers",
   "Search your board" in IDX)

if LIVE:
    print("\nlive: the pages answer (many Indian boards block this machine)")
    import asyncio
    import httpx

    async def _one(c, s):
        try:
            r = await c.get(s["url"], timeout=25, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 Chrome/126.0 Safari/537.36"})
            return s["id"], r.status_code
        except Exception as e:
            return s["id"], type(e).__name__

    async def _all():
        async with httpx.AsyncClient(follow_redirects=True,
                                     verify=False) as c:
            return await asyncio.gather(*[_one(c, s) for s in exams.SOURCES])

    for i, code in asyncio.run(_all()):
        print("    " + i.ljust(14) + " " + str(code))

if F:
    print("\n".join("FAIL " + x for x in F))
print("\nPASSED " + str(len(P)) + "   FAILED " + str(len(F)))
sys.exit(1 if F else 0)
