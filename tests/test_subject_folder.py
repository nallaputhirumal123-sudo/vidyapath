"""What a teacher saves off the board has to open where the class looks.

Reported as "none of them are going into the website", and the data was
never the problem — it was arriving and could not be opened.

Everything kept for a subject is a Material, and there are three kinds:

    lesson   words saved from the board. The content is in `body`; it has
             no url and no file.
    file     a picture of the board, or a document the teacher uploaded.
    link     an address the teacher shared.

Both screens rendered all three the same way — `<a href={url or /file}>` —
so a lesson, which has neither, became a link to a file that does not
exist. Every lesson a teacher saved from the board was listed on the page
and was unopenable, on the pupil's side and on her own.

They are grouped now, and each kind opens the way it can: a lesson unfolds
where it sits, because the words ARE the material and a phone opens them
faster than it opens a file; a file comes from us; a link goes where it
points.
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
IDX = io.open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
main.Base.metadata.create_all(bind=main.engine)
main._migrate_columns()
main.send_email = lambda *a, **k: None
P, F = [], []


def ck(n, c, d=""):
    print(("PASS " if c else "FAIL ") + n + (f" — {d}" if d else ""),
          flush=True)
    (P if c else F).append(n)


u = str(int(time.time()))[-6:] + str(os.getpid())
db = main.SessionLocal()
sc = main.School(name=f"Folder {u}")
db.add(sc)
db.commit()
db.refresh(sc)
hc = ("HFD" + u)[:12]
db.add(main.TeacherCode(code=hc, school=sc.name, school_id=sc.id,
                        is_head=True, active=True))
db.commit()
off = TestClient(main.app)
oem = f"fd{u}@example.com"
off.post("/api/auth/signup", json={"name": "Folder Office", "email": oem,
                                   "password": "OffPass1!"})
row = db.query(main.User).filter(main.User.email == oem).first()
row.dob = dt.date(1980, 1, 1)
db.commit()
off.post("/api/class/join", json={"code": hc})
cid = off.post("/api/teacher/class", json={"name": f"9-F {u}"}).json()["id"]
slot = off.post(f"/api/head/class/{cid}/slot",
                json={"subject": "Physics"}).json()
tem = f"fdt{u}@example.com"
pw = off.post("/api/head/staff",
              json={"name": "Folder Teacher", "email": tem,
                    "role": "teacher"}).json()["temporary_password"]
trow = db.query(main.User).filter(main.User.email == tem).first()
off.post("/api/head/assign", json={"class_id": cid, "subject": "Physics",
                                   "user_id": trow.id})

print("\nthree things reach a subject, by three different doors")
board = TestClient(main.app)
room = board.post("/api/craxlearn/room", json={"code": slot["code"]}).json()
H = {"X-Board-Token": room["board_token"]}
r = board.post("/api/craxlearn/board/save", headers=H,
               json={"class_id": cid, "topic": "Newton's second law",
                     "title": "Newton's second law", "subject": "Physics",
                     "lesson": {"title": "Newton's second law",
                                "steps": ["F = ma"], "takeaway": "force"}})
ck("a lesson saved from the board", r.status_code == 200, r.text[:80])
png = b"\x89PNG\r\n\x1a\n"
r = board.post("/api/craxlearn/board/file", headers=H,
               files={"file": ("board.png", png, "image/png")},
               data={"title": "Picture of the board", "class_id": str(cid),
                     "subject": "Physics"})
ck("a picture kept from the board", r.status_code == 200, r.text[:80])
her = TestClient(main.app)
her.post("/api/auth/login", json={"email": tem, "password": pw})
r = her.post(f"/api/teacher/class/{cid}/material/link",
             json={"title": "Khan Academy — forces",
                   "url": "https://example.com/forces", "subject": "Physics"})
ck("and a link the teacher shared", r.status_code == 200, r.text[:80])

print("\nthe class sees all three, each with a kind that says how to open it")
kem = f"fdk{u}@example.com"
kid = TestClient(main.app)
kid.post("/api/auth/signup", json={"name": "Folder Pupil", "email": kem,
                                   "password": "KidPass1!"})
krow = db.query(main.User).filter(main.User.email == kem).first()
krow.dob = dt.date(2012, 1, 1)
db.commit()
kid.post("/api/class/join",
         json={"code": db.get(main.Klass, cid).join_code})
mats = (kid.get(f"/api/class/{cid}/materials").json() or {}).get("materials") or []
kinds = {m.get("kind") for m in mats}
ck("all three arrived", len(mats) >= 3, f"{len(mats)} items")
ck("and they are told apart", {"lesson", "file", "link"} <= kinds, str(kinds))

lesson = [m for m in mats if m.get("kind") == "lesson"]
ck("the board lesson carries its words", bool(lesson) and bool(lesson[0].get("body")),
   "this is the one that was unopenable: no url, no file, only body")
ck("and has neither a url nor a file to link to",
   bool(lesson) and not lesson[0].get("url") and not lesson[0].get("file_name"),
   "which is exactly why `<a href={url or /file}>` produced a dead link")

print("\nand the page opens each kind the way it can")
ck("a folder, grouped by where it came from", "function matFolder(mats)" in IDX)
ck("a lesson unfolds in place", 'data-cls="matopen"' in IDX
   and "function matOpen(mid)" in IDX)
ck("a file still comes from us",
   '"/api/material/"+m.id+"/file"' in IDX)
ck("a link still goes where it points", 'kind === "link" ? esc(m.url)' in IDX)
ck("the kind is trusted from the server, with a fallback",
   "function matKindOf(m)" in IDX,
   "an older row without one is still classified rather than mis-linked")
ck("the teacher's own screen uses the same folder",
   "box.innerHTML = matFolder(rows)" in IDX,
   "she could not open what she had just saved either")
ck("and the empty case names what will arrive",
   "Lessons saved from the board, pictures of the board" in IDX)

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\nPASSED {len(P)}   FAILED {len(F)}")
sys.exit(1 if F else 0)
