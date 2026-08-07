"""Keeping a page of working on the class page, end to end.

"Save to the class is not working" was reported twice, so this stops taking
the route's word for it and drives the whole path a board actually takes: a
subject code in, a board token out, a PNG of the writing space up, and the
same picture back down in the list the class opens.

Three separate things can each break that and each looks identical from the
front — a button that does nothing:

**The picture never reaches the route.** The writing space saves a PNG from a
canvas, and PNG has to be an accepted type. It is an image, not a document,
and the material shelf was built for PDFs.

**The route cannot tell where it goes.** The class and the subject come from
the TOKEN, never the form, which is what makes a code a whole classroom has
read safe to hold. If the token carried no class, the page had nowhere to go
and the failure was silent.

**It saves and the class cannot see it.** Landing in the database is not the
feature; appearing in the subject's list is.

The client half has its own failure mode that no server test would catch:
`ME` is null on a board, always and deliberately, and the fallback that ran
when a code named no class read `ME.classes`. A handler that throws leaves a
button that does nothing, with nothing on screen and nothing in a support
call to go on.
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
from _school import make_staff                     # noqa: E402

main.Base.metadata.create_all(bind=main.engine)
main._migrate_columns()
main.send_email = lambda *a, **k: None

st = int(time.time())
P, F = [], []


def ck(n, c, d=""):
    print(("PASS " if c else "FAIL ") + n + (f" — {d}" if d else ""),
          flush=True)
    (P if c else F).append(n)


def fresh():
    main._CODE_TRIES.clear()
    main._CODE_FAILS.clear()


# The smallest real PNG — a 1x1 pixel. What a canvas produces is longer and
# no different in any way this path cares about.
PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
       b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00"
       b"\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")

db = main.SessionLocal()
sc = main.School(name=f"Save School {st}")
db.add(sc)
db.commit()
db.refresh(sc)
HEAD = f"HEAD-S{str(st)[-4:]}"
db.add(main.TeacherCode(code=HEAD, school=sc.name, school_id=sc.id,
                        is_head=True, active=True))
db.commit()

head = TestClient(main.app)
HE = f"sv{st}@example.com"
head.post("/api/auth/signup",
          json={"name": "Principal S", "email": HE, "password": "SavePass1!"})
u = db.query(main.User).filter(main.User.email == HE).first()
u.dob = dt.date(1980, 5, 5)
db.commit()
head.post("/api/class/join", json={"code": HEAD})

CID = head.post("/api/teacher/class", json={"name": f"9-C {st}"}).json()["id"]
sci = head.post(f"/api/head/class/{CID}/slot",
                json={"subject": "Science", "teacher_id": 0}).json()
_tc, TID, _e, _pw = make_staff(main, head, "Save Teacher")
head.post("/api/head/assign",
          json={"class_id": CID, "subject": "Science", "user_id": TID})

print("\na code opens a room, and the room says which class it is")
board = TestClient(main.app)          # no session at all — a screen in a room
fresh()
room = board.post("/api/craxlearn/room", json={"code": sci["code"]}).json()
ck("the code is accepted", bool(room.get("board_token")), str(room)[:120])
ck("and it names the class", room.get("class_id") == CID, str(room)[:120])
ck("and the subject", room.get("subject") == "Science", str(room)[:120])
# Without class_id the page has nowhere to go, and the client's fallback for
# that case used to read ME.classes on a screen where ME is always null.
H = {"X-Board-Token": room.get("board_token")}

print("\na picture of the board is kept on the class page")
r = board.post("/api/craxlearn/board/file",
               files={"file": ("board.png", io.BytesIO(PNG), "image/png")},
               data={"title": f"Board notes {st}",
                     "class_id": str(CID), "subject": "Science"},
               headers=H)
ck("a PNG from the writing space is accepted", r.status_code == 200,
   r.text[:200])
mat = (r.json() or {}).get("material") or {}
MID = mat.get("id")
ck("it comes back as a file", mat.get("kind") == "file", str(mat)[:120])
ck("filed under the right class", mat.get("class_id") in (CID, None),
   str(mat)[:120])
ck("and the right subject", mat.get("subject") == "Science", str(mat)[:120])

print("\nand the class can actually open it")
lst = board.get(f"/api/craxlearn/board/materials", headers=H)
if lst.status_code != 200:
    lst = head.get(f"/api/class/{CID}/materials")
ids = []
if lst.status_code == 200:
    body = lst.json()
    rows = body if isinstance(body, list) else (body.get("materials")
                                               or body.get("items") or [])
    ids = [m.get("id") for m in rows if isinstance(m, dict)]
ck("it is in the list the class opens", MID in ids,
   f"status {lst.status_code}, {len(ids)} rows")

print("\nthe token decides where it goes, not the form")
r = board.post("/api/craxlearn/board/file",
               files={"file": ("board.png", io.BytesIO(PNG), "image/png")},
               data={"title": f"Sneaky {st}", "class_id": "99999",
                     "subject": "History"},
               headers=H)
ck("a form cannot point it at another class",
   r.status_code == 200
   and (r.json()["material"].get("class_id") in (CID, None)), r.text[:140])
ck("nor rename the subject it files under",
   r.status_code == 200 and r.json()["material"]["subject"] == "Science",
   r.text[:140])

print("\nand a board with no code keeps nothing")
r = board.post("/api/craxlearn/board/file",
               files={"file": ("no.png", io.BytesIO(PNG), "image/png")},
               data={"title": "No"})
ck("an upload with no token is refused", r.status_code in (401, 403),
   f"status {r.status_code}")

print("\nan empty canvas is refused with a reason, not a stack trace")
r = board.post("/api/craxlearn/board/file",
               files={"file": ("board.png", io.BytesIO(b""), "image/png")},
               data={"title": "Empty"}, headers=H)
ck("an empty file is a 400", r.status_code == 400, f"status {r.status_code}")
ck("and it says so in words", "empty" in r.text.lower(), r.text[:120])

print("\nthe read-only catalogues open to a board too")
# A board holding a subject code was anonymous to every route that wanted a
# session, and two of those hold nothing personal at all: the published
# course list and the simulation index. The board asked, got a 401, and
# showed "Not signed in" on the simulations and an eternal "Loading the
# courses…" on the courses — the throw landed where nothing caught it.
for path, key in (("/api/curriculum", "tracks"),
                  ("/api/craxlearn/phet", "sims")):
    anon = board.get(path)
    ck(f"{path} still refuses an anonymous caller",
       anon.status_code in (401, 403), f"got {anon.status_code}")
    withtok = board.get(path, headers=H)
    ck(f"{path} answers a board holding a code",
       withtok.status_code == 200,
       f"got {withtok.status_code}: {withtok.text[:90]}")
    if withtok.status_code == 200:
        body = withtok.json()
        ck(f"  and it has {key} in it", key in body, str(body)[:90])

print("\nthe client cannot throw where it used to")
src = io.open(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "craxlearn.html"), encoding="utf-8").read()
ck("the ME fallback is guarded", "if(!cid && ME){" in src,
   "ME is null on a board, and a handler that throws is a dead button")
ck("PNG is an accepted material type",
   '"image/png": "png"' in io.open(os.path.join(os.path.dirname(
       os.path.dirname(os.path.abspath(__file__))), "main.py"),
       encoding="utf-8").read(),
   "the shelf was built for PDFs; the writing space saves a canvas")

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
