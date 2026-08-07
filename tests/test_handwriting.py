"""Handwriting turned into text, on demand and only on demand.

Reading a board costs a vision call. A call per stroke, or on a timer, would
be the most expensive thing in the product by a wide margin — so this is a
route a teacher presses, never a background job, and it is cached on the
bytes of the picture so pressing it twice on unchanged working costs nothing.

Three properties this pins, beyond it working at all:

**It copies rather than corrects.** A teacher who writes a wrong intermediate
step on purpose, to ask a class where the mistake is, must get that step back
unchanged. A model that tidies up would quietly destroy the lesson.

**Nothing legible is not cached.** Storing a blank would serve it straight
back to the person who writes it out again more clearly.

**It is charged to whoever teaches the subject.** A board is not a person; a
grant names the teacher the school put on that slot, and the bill has to have
a name on it.

The client half matters as much. The marks are redrawn black-on-white and
cropped to what was written — a model reads that far better than the board's
own light-on-dark, and it sends a fraction of the pixels of a 4K screen.
Rubbed-out strokes are excluded, because a rubbed-out stroke is not writing.
And the text is shown back for checking rather than swapped in silently.
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
main.Base.metadata.create_all(bind=main.engine)
main._migrate_columns()
main.send_email = lambda *a, **k: None

P, F = [], []


def ck(n, c, d=""):
    print(("PASS " if c else "FAIL ") + n + (f" — {d}" if d else ""),
          flush=True)
    (P if c else F).append(n)


PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
       b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00"
       b"\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")

st = int(time.time())
uniq = f"{st}{os.getpid()}"
db = main.SessionLocal()
sc = main.School(name=f"Hand School {uniq}")
db.add(sc)
db.commit()
db.refresh(sc)
HC = f"HH-{uniq[-8:]}"
db.add(main.TeacherCode(code=HC, school=sc.name, school_id=sc.id,
                        is_head=True, active=True))
db.commit()
head = TestClient(main.app)
he = f"hw{uniq}@example.com"
head.post("/api/auth/signup",
          json={"name": "Hand Head", "email": he, "password": "HandPass1!"})
u = db.query(main.User).filter(main.User.email == he).first()
u.dob = dt.date(1980, 2, 2)
db.commit()
head.post("/api/class/join", json={"code": HC})
CID = head.post("/api/teacher/class", json={"name": f"9-H {uniq}"}).json()["id"]
slot = head.post(f"/api/head/class/{CID}/slot",
                 json={"subject": "Maths", "teacher_id": 0}).json()
_tc, TID, _e, _pw = make_staff(main, head, "Hand Teacher")
head.post("/api/head/assign",
          json={"class_id": CID, "subject": "Maths", "user_id": TID})

board = TestClient(main.app)
main._CODE_TRIES.clear()
main._CODE_FAILS.clear()
room = board.post("/api/craxlearn/room", json={"code": slot["code"]}).json()
H = {"X-Board-Token": room["board_token"]}

print("\nthe route exists and is guarded")
r = board.post("/api/craxlearn/handwriting",
               files={"file": ("h.png", io.BytesIO(PNG), "image/png")})
ck("a board with no code cannot ask", r.status_code in (401, 403),
   f"got {r.status_code} — reading a board costs a vision call")

r = board.post("/api/craxlearn/handwriting",
               files={"file": ("h.png", io.BytesIO(b""), "image/png")},
               headers=H)
ck("an empty picture is refused in words", r.status_code == 400,
   f"got {r.status_code}")
ck("and it says there is nothing written",
   "nothing written" in r.text.lower(), r.text[:100])

r = board.post("/api/craxlearn/handwriting",
               files={"file": ("h.txt", io.BytesIO(PNG), "text/plain")},
               headers=H)
ck("a file that is not a picture is refused", r.status_code == 400,
   f"got {r.status_code}")

r = board.post("/api/craxlearn/handwriting",
               files={"file": ("h.png", io.BytesIO(PNG), "image/png")},
               headers=H)
# No provider is configured in the suite, so the honest answer is 503. What
# matters is that it got PAST the guards and tried — a 401 or 422 here would
# mean the board's entitlement or the upload shape was wrong.
ck("a board holding a code reaches the reader",
   r.status_code in (200, 503), f"got {r.status_code}: {r.text[:110]}")
if r.status_code == 503:
    ck("and says the tutor is not switched on rather than crashing",
       "not switched on" in r.text.lower() or "provider" in r.text.lower(),
       r.text[:110])

print("\nthe prompt copies rather than corrects")
src = io.open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
ck("it is told to copy exactly", "Copy what is written EXACTLY" in src)
ck("no spelling correction", "Do not correct spelling" in src)
ck("no arithmetic correction", "fix arithmetic" in src)
ck("and it does not answer what it read", "answer anything" in src,
   "a wrong step may have been written on purpose for a class to find")
ck("the reason is written down", "written on purpose" in src)

print("\nand nothing legible is not stored")
ck("a blank result skips the cache",
   'return {"text": "", "cached": False}' in src,
   "caching a blank serves it straight back to whoever rewrites it")
ck("a real result is cached on the bytes",
   '_ai_cache_put(db, qkey, {"text": text})' in src,
   "pressing it twice on unchanged working must cost nothing")
ck("keyed by a hash of the picture", 'hashlib.sha256(raw).hexdigest()' in src)

print("\nit is charged to whoever teaches the subject")
ck("the grant names the teacher",
   'owner = db.get(User, grant["teacher_id"]) if grant else user' in src)
ck("and an unfilled slot is refused rather than charged to nobody",
   "Nobody is on this subject to charge this to" in src)
ck("the limit is enforced against that person",
   "_ai_enforce_limit(db, owner)" in src)

print("\nthe board sends a picture worth reading")
page = io.open(os.path.join(ROOT, "craxlearn.html"), encoding="utf-8").read()
ck("there is a button, and it is a button", 'data-ink="type"' in page,
   "on demand, never on a timer")
ck("the marks are redrawn black on white", 'c.fillStyle = "#ffffff";' in page
   and 'c.strokeStyle = "#111111";' in page,
   "a model reads dark-on-light far better than the board's own colours")
ck("cropped to what was written", "function inkSheet()" in page,
   "a whole 4K board is mostly empty pixels")
ck("rubbed-out strokes are left out", page.count("if(st.e) return;") >= 2,
   "a rubbed-out stroke is not writing")
ck("nothing is sent when nothing is written",
   'n.textContent = "There is nothing written to read.";' in page)

print("\nand the reading is shown back before it goes anywhere")
ck("into an editable box", 'id="inkTextBody"' in page,
   "handwriting is read imperfectly; a teacher must see what it made of theirs")
ck("with keeping as a separate press", 'id="inkTextKeep"' in page)
ck("and what is KEPT is what is in the box",
   'var body = (ta.value || "").trim();' in page,
   "so a correction is the thing saved")
ck("filed with the shape the save route actually takes",
   'topic: first.length >= 2 ? first : "Board notes"' in page
   and "lesson: { title: first" in page,
   "a bare body field would have been a 422 the first time it was pressed")

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
