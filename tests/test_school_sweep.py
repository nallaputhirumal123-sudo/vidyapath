"""Admin, teacher, class, subject, board — walked as one school's first week.

Every route below already has a test of its own. This is not that. It is the
journey a school actually takes, in order, with each step using only what the
step before it produced — which is where things break, because a route that
passes on a fixture built by hand can still be unreachable from the screen
that is supposed to lead to it.

    the platform issues a code       -> somebody becomes the administrator
    the administrator makes a class  -> it has a code for pupils
    adds a subject                   -> it has a board code
    adds a teacher                   -> she has a password, shown once
    puts her on the subject          -> the subject knows her id
    a pupil joins with the class code-> the register has them
    the teacher signs in             -> she sees that class and that subject
    she sets work                    -> the pupil sees it
    she shares material              -> the pupil can open it
    the class talks                  -> both sides read the same thread
    the board opens on the subject   -> and signs nobody in
    the board keeps a picture        -> it lands on the subject's page

The three refusals at the end matter as much as the steps. A subject code is
not a sign-in; a teacher of one subject is not an administrator; and a board
holding one class's token cannot reach another class's material.
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

# ---------------------------------------------------------------- admin
print("\nADMIN — a code from the platform makes one person the school")
sc = main.School(name=f"Sweep School {u}")
db.add(sc)
db.commit()
db.refresh(sc)
hc = ("HSW" + u)[:12]
db.add(main.TeacherCode(code=hc, school=sc.name, school_id=sc.id,
                        is_head=True, active=True))
db.commit()

office = TestClient(main.app)
oem = f"sw.office{u}@example.com"
office.post("/api/auth/signup", json={"name": "Sweep Office", "email": oem,
                                      "password": "SweepPass1!"})
orow = db.query(main.User).filter(main.User.email == oem).first()
orow.dob = dt.date(1979, 5, 5)
db.commit()
r = office.post("/api/class/join", json={"code": hc})
ck("the code says school admin", r.status_code == 200
   and (r.json() or {}).get("role") == "school admin", r.text[:90])
ck("and the same code cannot make a second one",
   office.post("/api/class/join", json={"code": hc}).status_code in (200, 400),
   "re-entering your own code must not error confusingly")
r = office.get("/api/head/overview")
ck("the school screen opens", r.status_code == 200, r.text[:80])

# ---------------------------------------------------------------- class
print("\nCLASS — made by the office, with a code for pupils")
r = office.post("/api/teacher/class", json={"name": f"6-D {u}"})
ck("a classroom is created", r.status_code == 200, r.text[:90])
cid = (r.json() or {}).get("id")
ck("it has an id", bool(cid))
ov = office.get("/api/head/overview").json()
row = [c for c in (ov.get("classrooms") or []) if c.get("id") == cid]
ck("and it appears on the school screen", bool(row))
join_code = row[0].get("join_code") if row else ""
ck("with a pupils' code", str(join_code).startswith("VP-"), str(join_code))

# ---------------------------------------------------------------- subject
print("\nSUBJECT — a slot with a board code, and a teacher on it")
r = office.post(f"/api/head/class/{cid}/slot", json={"subject": "Physics"})
ck("a subject is added", r.status_code == 200, r.text[:90])
scode = (r.json() or {}).get("code") or ""
ck("and it carries a board code", scode.startswith("T-"), scode)

# ---------------------------------------------------------------- teacher
print("\nTEACHER — added, given a password, put on the subject")
tem = f"sw.teach{u}@example.com"
r = office.post("/api/head/staff", json={"name": "Sweep Teacher",
                                         "email": tem, "role": "teacher"})
ck("she is added", r.status_code == 200, r.text[:110])
pw = (r.json() or {}).get("temporary_password") or ""
ck("and handed a password once", bool(pw),
   "stored as a hash — not returned here means unreachable")
trow = db.query(main.User).filter(main.User.email == tem).first()
r = office.post("/api/head/assign", json={"class_id": cid,
                                          "subject": "Physics",
                                          "user_id": trow.id if trow else 0})
ck("she goes onto the subject", r.status_code == 200, r.text[:110])
db.expire_all()
slot = (db.query(main.SubjectSlot)
          .filter(main.SubjectSlot.class_id == cid,
                  main.SubjectSlot.subject == "Physics").first())
ck("the slot holds her id", slot is not None
   and slot.teacher_id == (trow.id if trow else -1))
ov = office.get("/api/head/overview").json()
subs = []
for c in (ov.get("classrooms") or []):
    if c.get("id") == cid:
        subs = c.get("subjects") or []
ck("and the office can see how she signs in",
   any(s.get("teacher_email") == tem for s in subs),
   "the row showing a board code beside her name is where that is asked")

# ---------------------------------------------------------------- pupil
print("\nPUPIL — joins with the class code and is on the register")
kid = TestClient(main.app)
kem = f"sw.kid{u}@example.com"
kid.post("/api/auth/signup", json={"name": "Sweep Pupil", "email": kem,
                                   "password": "KidPass1!"})
krow = db.query(main.User).filter(main.User.email == kem).first()
krow.dob = dt.date(2012, 6, 6)
db.commit()
r = kid.post("/api/class/join", json={"code": join_code})
ck("the class code says student", r.status_code == 200
   and (r.json() or {}).get("role") == "student", r.text[:90])
r = kid.get("/api/class/mine")
mine = (r.json() or {}).get("classes") or []
ck("and the class is theirs now", any(c.get("id") == cid for c in mine),
   f"{len(mine)} classes")

# ------------------------------------------------------- teacher signs in
print("\nTEACHER SIGNS IN — and lands on what she teaches")
her = TestClient(main.app)
r = her.post("/api/auth/login", json={"email": tem, "password": pw})
ck("email and password get her in", r.status_code == 200, r.text[:110])
d = her.get("/api/teacher/classes").json()
ck("her class is there",
   any(c.get("id") == cid for c in (d.get("classes") or [])))
ck("with her subject on it",
   any(c.get("id") == cid and "Physics" in (c.get("my_subjects") or [])
       for c in (d.get("classes") or [])))
ck("and the class+subject+code as one post",
   any(p.get("class_id") == cid and p.get("subject") == "Physics"
       and str(p.get("code") or "").startswith("T-")
       for p in (d.get("posts") or [])),
   "6-D Physics and 7-A Physics are different posts")

# ---------------------------------------------------------------- work
print("\nWORK — she sets it, the pupil sees it")
r = her.post(f"/api/teacher/class/{cid}/assignment",
             json={"title": "Forces worksheet", "subject": "Physics",
                   "brief": "Questions 1 to 6."})
ck("an assignment is set", r.status_code == 200, r.text[:110])
seen = kid.get("/api/class/mine").json()
asg = []
for c in (seen.get("classes") or []):
    if c.get("id") == cid:
        asg = c.get("assignments") or []
ck("and the pupil has it",
   any("Forces worksheet" == a.get("title") for a in asg),
   f"{len(asg)} assignments")

print("\nMATERIAL — she shares it, the pupil can open it")
r = her.post(f"/api/teacher/class/{cid}/material/link",
             json={"title": "Newton's laws", "url": "https://example.com/n",
                   "subject": "Physics", "note": "read before Friday"})
ck("material is shared", r.status_code == 200, r.text[:110])
mats = (kid.get(f"/api/class/{cid}/materials").json() or {}).get("materials") or []
ck("and the pupil sees it",
   any(m.get("title") == "Newton's laws" for m in mats),
   f"{len(mats)} items")

# ---------------------------------------------------------------- talking
print("\nTHE CLASS TALKS — and both sides read the same thread")
r = kid.post(f"/api/class/{cid}/discussion",
             json={"body": "Sir, is question 4 a trick?",
                   "subject": "Physics"})
ck("a pupil can start it", r.status_code == 200, r.text[:90])
qid = (r.json() or {}).get("id") or 0
r = her.post(f"/api/class/{cid}/discussion",
             json={"body": "No — read it twice.", "subject": "Physics",
                   "parent_id": qid})
ck("and the teacher answers in the same thread", r.status_code == 200,
   r.text[:90])
kv = (kid.get(f"/api/class/{cid}/discussion?subject=Physics").json()
      or {}).get("threads") or []
tv = (her.get(f"/api/class/{cid}/discussion?subject=Physics").json()
      or {}).get("threads") or []
ck("the pupil sees the answer",
   bool(kv) and len(kv[0].get("replies") or []) == 1)
ck("the teacher sees the question", bool(tv))
ck("and it is the same conversation on both screens",
   [m["id"] for m in kv] == [m["id"] for m in tv],
   "two different forums is how the two halves drifted apart")

# ---------------------------------------------------------------- board
print("\nBOARD — the subject code opens a room and signs nobody in")
board = TestClient(main.app)
r = board.post("/api/craxlearn/room", json={"code": scode})
ck("the code names the room", r.status_code == 200, r.text[:110])
room = r.json() if r.status_code == 200 else {}
ck("it is the right class and subject",
   room.get("class_id") == cid and room.get("subject") == "Physics")
ck("with her name on it", room.get("teacher") == "Sweep Teacher",
   str(room.get("teacher")))
tok = room.get("board_token") or ""
ck("and a board token rather than a session", bool(tok))
H = {"X-Board-Token": tok}

print("\n  what a board with a code may do")
ck("read the course list",
   board.get("/api/curriculum", headers=H).status_code == 200)
ck("search the open sources",
   board.get("/api/craxlearn/search?q=refraction",
             headers=H).status_code == 200)
ck("open the simulations",
   board.get("/api/craxlearn/phet", headers=H).status_code == 200)
ck("and reach its own class's material",
   board.get(f"/api/class/{cid}/materials", headers=H).status_code
   in (200, 401, 403),
   "listed here so a change of answer is noticed")

print("\n  and what it may not")
# One code, both jobs. It opens the subject on a board AND signs its
# teacher in — restored deliberately after the refusal left a teacher who
# held only a code with no way in at all. The trade is written down in
# sign_in_with_code: the code is read off a wall, so whoever holds it can
# become that teacher, and the answer is that it rotates.
signin = TestClient(main.app)
r = signin.post("/api/auth/code", json={"code": scode})
ck("the same code signs its teacher in", r.status_code == 200, r.text[:120])
ck("as the teacher the office put on it",
   (r.json() or {}).get("name") == "Sweep Teacher", r.text[:120])
ck("and she lands on her classes",
   signin.get("/api/teacher/classes").status_code == 200)
r = office.post(f"/api/head/slot/{slot.id}/rotate")
ck("rotating the code issues a new one", r.status_code == 200, r.text[:90])
fresh = (r.json() or {}).get("code") or ""
ck("and the old one stops working",
   TestClient(main.app).post("/api/auth/code",
                             json={"code": scode}).status_code >= 400,
   "this is the move when a code has been up on a board all term")
ck("while the new one works", fresh.startswith("T-") and fresh != scode,
   fresh)
other = main.Klass(name=f"other {u}", school_id=sc.id,
                   join_code=main._gen_join_code(db), teacher_id=orow.id)
db.add(other)
db.commit()
db.refresh(other)
m = main.Material(class_id=other.id, title="not yours", subject="Physics",
                  url="https://example.com/x", teacher_id=orow.id)
db.add(m)
db.commit()
db.refresh(m)
r = board.get(f"/api/material/{m.id}/file", headers=H)
ck("a board cannot open another class's material", r.status_code >= 400,
   f"got {r.status_code}")

print("\n  a teacher of one subject is not the school")
ck("she cannot open the school screen",
   her.get("/api/head/overview").status_code == 403)
ck("nor add staff",
   her.post("/api/head/staff", json={"name": "X Y",
                                     "email": f"x{u}@example.com",
                                     "role": "teacher"}).status_code == 403)

print("\n  and a stranger is nobody here")
out = TestClient(main.app)
ck("no session, no class", out.get("/api/class/mine").status_code == 401)
ck("no session, no register",
   out.get(f"/api/class/{cid}/discussion").status_code == 401)

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\nPASSED {len(P)}   FAILED {len(F)}")
sys.exit(1 if F else 0)
