"""The diagrams out of the school books, and a way to reach them.

The corpus held the text of eighteen NCERT books and none of their figures.
For most questions that is right — the numbers are in the passage and the
board draws its own diagram. It is wrong for the chapters whose whole point
IS the figure: a ray diagram, a labelled cell, a circuit, the layout of a
balance sheet. A lesson about a ray diagram is not that lesson with the
picture removed; it is a paragraph about a picture nobody can see.

Three things this pins.

**They are shipped, not fetched.** On demand was tried first and measured
second: a chapter's first request took THIRTY-THREE SECONDS, because
ncert.nic.in throttles and the fetch retries through it. Fine in a script,
unusable standing in front of a class. From the shipped archive it is a
hundredth of that. The download stays as the fallback for a chapter the
archive missed, which is a slow answer rather than no answer.

**The route only serves chapters the books actually contain.** Without that
check it is a way to make the server fetch arbitrary files from ncert.nic.in
on request — somebody else's bandwidth, over our IP address.

**There is a way in.** A feature with an API and no route to it is the dead
end this session has spent its time removing. Searching the sources now
returns the chapters of the class's own books that match, each with a button
that opens its figures — and that search itself needed a session, so the
tool sat in the board's menu, drew its box, and answered 401 to the first
thing anybody typed. That is the same fault as the simulations and the
course list, found in a third place.
"""
import io
import os
import sys
import time
import datetime as dt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"

import main                                        # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
main.Base.metadata.create_all(bind=main.engine)
main._migrate_columns()
main.send_email = lambda *a, **k: None
P, F = [], []


def ck(n, c, d=""):
    print(("PASS " if c else "FAIL ") + n + (f" — {d}" if d else ""),
          flush=True)
    (P if c else F).append(n)


u = str(int(time.time())) + str(os.getpid())
db = main.SessionLocal()
sc = main.School(name=f"Fig {u}")
db.add(sc)
db.commit()
db.refresh(sc)
hc = ("HF" + u)[:12]
db.add(main.TeacherCode(code=hc, school=sc.name, school_id=sc.id,
                        is_head=True, active=True))
db.commit()
head = TestClient(main.app)
em = f"fig{u}@example.com"
head.post("/api/auth/signup",
          json={"name": "Figure Head", "email": em, "password": "FigPass1!"})
usr = db.query(main.User).filter(main.User.email == em).first()
usr.dob = dt.date(1980, 1, 1)
db.commit()
head.post("/api/class/join", json={"code": hc})
cid = head.post("/api/teacher/class",
                json={"name": f"Fig Class {u}"}).json()["id"]
slot = head.post(f"/api/head/class/{cid}/slot",
                 json={"subject": "Science", "teacher_id": 0}).json()
board = TestClient(main.app)
main._CODE_TRIES.clear()
main._CODE_FAILS.clear()
room = board.post("/api/craxlearn/room", json={"code": slot["code"]}).json()
H = {"X-Board-Token": room["board_token"]}

print("\nonly chapters the books actually hold")
ck("a board with no code is refused",
   board.get("/api/craxlearn/book-pictures?code=jesc105").status_code
   in (401, 403))
ck("no code at all is a 400",
   board.get("/api/craxlearn/book-pictures?code=", headers=H).status_code
   == 400)
r = board.get("/api/craxlearn/book-pictures?code=zzzz999", headers=H)
ck("an invented chapter is a 404", r.status_code == 404, str(r.status_code))
ck("and it says why", "not a chapter" in r.text.lower(), r.text[:80])
# The check exists to stop this being an open fetcher for somebody else's
# server, so a path is not a chapter either.
r = board.get("/api/craxlearn/book-pictures?code=../../etc/passwd",
              headers=H)
ck("a path is not a chapter", r.status_code in (400, 404), str(r.status_code))

print("\nthe shipped archive answers, and fast")
have_archive = os.path.exists(os.path.join(ROOT, "corpus-pics.db"))
if have_archive:
    import sqlite3
    con = sqlite3.connect(
        f"file:{os.path.join(ROOT, 'corpus-pics.db')}?mode=ro", uri=True)
    got = con.execute(
        "SELECT code FROM pictures GROUP BY code "
        "HAVING count(*) > 0 LIMIT 1").fetchone()
    con.close()
    if got:
        code = got[0]
        t = time.time()
        r = board.get(f"/api/craxlearn/book-pictures?code={code}", headers=H)
        el = time.time() - t
        ck(f"{code} comes back", r.status_code == 200, r.text[:90])
        pics = (r.json() or {}).get("pictures") or []
        ck("with pictures in it", len(pics) > 0, str(len(pics)))
        ck("each a jpeg data URI",
           all(p["src"].startswith("data:image/jpeg;base64,") for p in pics))
        ck("sized for a projector, not for paper",
           all(p["w"] <= main.__dict__.get("PIC_MAX_SIDE", 900)
               or p["w"] <= 900 for p in pics),
           str([p["w"] for p in pics]))
        ck(f"and it is fast, not a download ({el:.2f}s)", el < 3.0,
           "the whole reason these ship is that fetching took 33 seconds")
    else:
        ck("the archive holds at least one chapter's pictures", False,
           "corpus-pics.db has no rows yet")
else:
    ck("a picture archive is present", False,
       "corpus-pics.db is missing — run tools/build_pictures.py")

print("\nand searching the sources leads to them")
src = io.open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
ck("search is open to a board holding a code",
   "async def craxlearn_search(q: str, user: User = Depends(board_or_reader))"
   in src,
   "it required a session, so the tool drew its box and answered 401 to the "
   "first thing typed into it")
ck("and returns the chapters it matched", '"chapters": chapters[:3]' in src)
ck("from the corpus only, never the fallback index",
   "def _rag_index_only():" in src,
   "a coding lesson is not a chapter of a school book and must not be "
   "offered as one")

page = io.open(os.path.join(ROOT, "craxlearn.html"), encoding="utf-8").read()
ck("the board renders a button per chapter", "data-bookpics" in page)
ck("wired to a handler", "async function bookPics(btn){" in page)
ck("that asks only when pressed", 'btn.textContent = "Opening…";' in page,
   "a chapter is up to six pictures and most searches want none of them")
ck("and credits the books", "NCERT · reproduced for teaching" in page)

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
