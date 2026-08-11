"""A document, brought into the lesson by the board itself.

The tool that turns a teacher's PDF into a lesson had existed for months and
was reachable from exactly one place: the website, on a laptop. The teacher
who wants it is standing at a board at the front of a room with the chapter
in their hand and no keyboard to sign in from. `grep -c` said it plainly —
one caller in index.html, none in craxlearn.html.

So this pins the three things that were missing, and the guards that make
them safe to reach with a code that a classroom has read:

  as it is        the document unchanged, because a worksheet or a past
                  paper put through a model is not that worksheet any more
  written up      the PDF read and turned into steps, charged to whoever the
                  school put on the subject
  put back up     what is already saved for THIS subject, ready to present

The property that matters most is the last block. A board token names one
class and one subject; everything reachable with it must be inside that
room, whatever id is typed into a URL.
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
from _school import teacher_on, make_staff   # noqa: E402

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


db = main.SessionLocal()
sc = main.School(name=f"Bring School {st}")
db.add(sc)
db.commit()
db.refresh(sc)
HEAD = f"HEAD-B{str(st)[-4:]}"
db.add(main.TeacherCode(code=HEAD, school=sc.name, school_id=sc.id,
                        is_head=True, active=True))
db.commit()

head = TestClient(main.app)
HE = f"br{st}@example.com"
head.post("/api/auth/signup",
          json={"name": "Principal B", "email": HE, "password": "BringPass1!"})
u = db.query(main.User).filter(main.User.email == HE).first()
u.dob = dt.date(1982, 3, 3)
db.commit()
head.post("/api/class/join", json={"code": HEAD})

mk = head.post("/api/teacher/class", json={"name": f"8-B {st}"}).json()
CID = mk["id"]
sci = head.post(f"/api/head/class/{CID}/slot",
                json={"subject": "Science", "teacher_id": 0}).json()
mat = head.post(f"/api/head/class/{CID}/slot",
                json={"subject": "Maths", "teacher_id": 0}).json()

# A real teacher on Science, so the room can charge a model call to somebody.
# Signed in with their own address and password: a subject code opens a board
# and nothing else now, which is what the second half of this file is about.
_tc, TID, _e, _pw = make_staff(main, head, "Bring Teacher")
head.post("/api/head/assign",
          json={"class_id": CID, "subject": "Science", "user_id": TID})

board = TestClient(main.app)          # no session at all — a screen in a room
fresh()
room = board.post("/api/craxlearn/room", json={"code": sci["code"]}).json()
TOKEN = room.get("board_token")
H = {"X-Board-Token": TOKEN}

fresh()
other = board.post("/api/craxlearn/room", json={"code": mat["code"]}).json()
H2 = {"X-Board-Token": other.get("board_token")}

PDF = b"%PDF-1.4\n% a real enough header for the route's own check\n"

print("\nthe document, exactly as it is")
r = board.post("/api/craxlearn/board/file",
               files={"file": ("worksheet.pdf", io.BytesIO(PDF),
                               "application/pdf")},
               data={"title": f"Worksheet {st}"}, headers=H)
ck("a board holding a subject code can keep a document", r.status_code == 200,
   r.text[:140])
MID = ((r.json() or {}).get("material") or {}).get("id")
ck("and it comes back as a file, not as prose",
   (r.json() or {}).get("material", {}).get("kind") == "file",
   str(r.json())[:110])

# The whole reason this is safe with a code a class has read: the class and
# the subject are the token's, never the form's.
r = board.post("/api/craxlearn/board/file",
               files={"file": ("sneaky.pdf", io.BytesIO(PDF),
                               "application/pdf")},
               data={"title": f"Sneaky {st}", "class_id": "99999",
                     "subject": "History"}, headers=H)
ck("a form cannot point it at another class or rename its subject",
   r.status_code == 200
   and r.json()["material"]["subject"] == "Science", r.text[:130])

print("\nand nobody without a code can keep anything")
r = board.post("/api/craxlearn/board/file",
               files={"file": ("no.pdf", io.BytesIO(PDF), "application/pdf")},
               data={"title": "No"})
ck("an anonymous upload is refused", r.status_code in (401, 403),
   f"got {r.status_code}")

print("\nwhat is already saved, ready to put back up")
r = board.get("/api/craxlearn/board/materials", headers=H)
ck("the board can list its own subject", r.status_code == 200, r.text[:120])
d = r.json()
ck("and it is this class and this subject",
   d.get("class_id") == CID and d.get("subject") == "Science", str(d)[:120])
ck("the document is on the list",
   any(m.get("id") == MID for m in d.get("materials", [])),
   str(d.get("materials"))[:140])

# Another subject in the SAME class is a different teacher's shelf.
board.post("/api/craxlearn/board/save",
           json={"topic": f"Fractions {st}", "title": f"Fractions {st}",
                 "lesson": {"steps": [{"t": "A half is one over two."}]}},
           headers=H2)
r = board.get("/api/craxlearn/board/materials", headers=H)
ck("another subject's material is not on it",
   not any(f"Fractions {st}" in (m.get("title") or "")
           for m in r.json().get("materials", [])),
   str(r.json().get("materials"))[:140])
r = board.get("/api/craxlearn/board/materials", headers=H2)
ck("and the Maths board sees Maths",
   any(f"Fractions {st}" in (m.get("title") or "")
       for m in r.json().get("materials", [])), r.text[:140])

print("\nfetching the document itself")
r = board.get(f"/api/craxlearn/board/material/{MID}/file", headers=H)
ck("the board can open it", r.status_code == 200, f"got {r.status_code}")
ck("and gets the bytes back", r.content == PDF, str(r.content[:20]))
# Counting up from 1 must not walk out of this classroom.
r = board.get(f"/api/craxlearn/board/material/{MID}/file", headers=H2)
ck("a board in another subject cannot open it", r.status_code == 404,
   f"got {r.status_code}")
r = board.get(f"/api/craxlearn/board/material/{MID}/file")
ck("and nor can anybody with no code", r.status_code in (401, 403),
   f"got {r.status_code}")

print("\nthe rotation that takes a leaked code out of circulation")
_r = head.post(f"/api/head/slot/{sci['id']}/rotate")
ck("the office can rotate the subject code", _r.status_code == 200,
   _r.text[:110])
r = board.get("/api/craxlearn/board/materials", headers=H)
ck("a token from a rotated code still opens the room it names",
   r.status_code == 200, f"got {r.status_code}")
# It survives a rotation because the token is minted against the SLOT, not
# the string; what rotation stops is the next person to type the old code.
fresh()
r = board.post("/api/craxlearn/room", json={"code": sci["code"]})
ck("but the old code itself no longer opens anything", r.status_code == 404,
   f"got {r.status_code}")

print("\nwriting a document up as a lesson")
# The model is not called here — the point is who is allowed to ask for one
# and what it costs, both of which are decided before any call is made.
r = board.post("/api/teach/pdf",
               files={"file": ("empty.pdf", io.BytesIO(b""),
                               "application/pdf")}, headers=H)
ck("the board reaches the route at all (it could not before)",
   r.status_code == 400, f"got {r.status_code}: {r.text[:90]}")
r = board.post("/api/teach/pdf",
               files={"file": ("x.pdf", io.BytesIO(PDF), "application/pdf")})
ck("an anonymous caller still cannot", r.status_code in (401, 403),
   f"got {r.status_code}")

# A subject with nobody on it cannot spend. There would be no account to
# charge and no name against the bill, and the code would be an open tap.
r = board.post("/api/teach/pdf",
               files={"file": ("x.pdf", io.BytesIO(PDF), "application/pdf")},
               headers=H2)
ck("a subject with no teacher on it cannot buy a model call",
   r.status_code == 403, f"got {r.status_code}: {r.text[:90]}")

print("\nand a signed-in teacher still uses all of it")
fresh()
tch = _tc
_slot = (db.query(main.SubjectSlot)
           .filter(main.SubjectSlot.class_id == CID,
                   main.SubjectSlot.subject == "Science").first())
db.refresh(_slot)
r = TestClient(main.app).post("/api/auth/code", json={"code": _slot.code})
ck("their subject code signs that teacher in", r.status_code == 200,
   f"got {r.status_code}: {r.text[:90]}")
ck("as the teacher who holds the subject",
   (r.json() or {}).get("name") == "Bring Teacher", r.text[:90])
r = tch.post("/api/craxlearn/board/file",
             files={"file": ("notes.png", io.BytesIO(b"\x89PNG\r\n\x1a\n"),
                             "image/png")},
             data={"title": f"Notes {st}", "class_id": str(CID),
                   "subject": "Science"})
ck("a signed-in teacher can keep a document too", r.status_code == 200,
   r.text[:130])
r = tch.get(f"/api/craxlearn/board/materials?class_id={CID}&subject=Science")
ck("and read the same shelf", r.status_code == 200
   and any(f"Notes {st}" in (m.get("title") or "")
           for m in r.json().get("materials", [])), r.text[:130])
r = tch.get(f"/api/craxlearn/board/materials?class_id={CID}&subject=Maths")
ck("but not a subject they do not teach", r.status_code == 403,
   f"got {r.status_code}")

db.close()
print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
