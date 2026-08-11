"""The whole way in for a teacher, from the office adding them to the board.

Not a route test. Every step here already passes on its own; the question is
whether they join up into something a school can actually run on, because
that is the journey the school walks on day one and there is nobody to ask
when it breaks halfway.

    the office adds her                 ->  she has an account
    the office puts her on a subject    ->  the subject knows her
    the office issues her a password    ->  she can sign in
    she signs in                        ->  she lands on what she teaches
    the subject's code opens a board    ->  and signs her in too

That last line went back and forth and has settled. The code is chalked up
and read by a whole class, so whoever holds it can become that teacher —
a real cost, written down in sign_in_with_code. It is accepted because the
alternative was tested and was worse: a teacher given only a code was
refused, told to use an email and password nobody had issued her, and had
no way in at all. She went round that loop instead of teaching. The answer
to the cost is that the code rotates, and that email and password still
exist and are still stronger.

What this is really guarding is the join between the two halves. A teacher
who signs in and sees no classes is indistinguishable, from her side, from a
broken product — and the office, looking at a row that says she holds
Biology, has no way to see what she is seeing.
"""
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

# The school, and its administrator.
sc = main.School(name=f"Path School {u}")
db.add(sc)
db.commit()
db.refresh(sc)
hc = ("HPT" + u)[:12]
db.add(main.TeacherCode(code=hc, school=sc.name, school_id=sc.id,
                        is_head=True, active=True))
db.commit()
office = TestClient(main.app)
oem = f"office{u}@example.com"
office.post("/api/auth/signup",
            json={"name": "Path Office", "email": oem,
                  "password": "OfficePass1!"})
orow = db.query(main.User).filter(main.User.email == oem).first()
orow.dob = dt.date(1980, 1, 1)
db.commit()
office.post("/api/class/join", json={"code": hc})

print("\nthe office builds the timetable")
r = office.post("/api/teacher/class", json={"name": f"10-B {u}"})
ck("a classroom is created", r.status_code == 200, r.text[:100])
cid = (r.json() or {}).get("id") or (r.json() or {}).get("class_id")
ck("and it has an id", bool(cid), str(r.json())[:120])

print("\nand adds a teacher, who gets a password shown once")
tem = f"teach{u}@example.com"
r = office.post("/api/head/staff", json={"name": "Path Teacher",
                                         "email": tem, "role": "teacher"})
ck("she is added", r.status_code == 200, r.text[:140])
pw = (r.json() or {}).get("temporary_password") or ""
ck("with a password handed back exactly once", bool(pw),
   "it is stored as a hash — if it is not returned here there is no second "
   "chance to read it, and the account is unreachable")
trow = db.query(main.User).filter(main.User.email == tem).first()
ck("and a real account behind it", trow is not None)

print("\nthe office puts her on a subject")
r = office.post("/api/head/assign",
                json={"class_id": cid, "subject": "Biology",
                      "user_id": trow.id if trow else 0})
ck("the subject accepts her", r.status_code == 200, r.text[:140])
code = (r.json() or {}).get("code") or ""
ck("and hands back the board code for it", code.startswith("T-"), code)

db.expire_all()
slot = (db.query(main.SubjectSlot)
          .filter(main.SubjectSlot.class_id == cid,
                  main.SubjectSlot.subject == "Biology").first())
ck("the slot really holds her id, not just a name on a screen",
   slot is not None and slot.teacher_id == (trow.id if trow else -1),
   f"teacher_id={slot and slot.teacher_id}")
ck("and assigning a subject is what made her staff here",
   main.teacher_row(trow, db) is not None,
   "she had no TeacherAccess row until this point")

print("\nshe signs in with the two things she was given")
her = TestClient(main.app)
r = her.post("/api/auth/login", json={"email": tem, "password": pw})
ck("email and password get her in", r.status_code == 200, r.text[:140])

print("\nand lands on what she teaches — the join this exists to check")
r = her.get("/api/teacher/classes")
ck("the teaching side opens for her", r.status_code == 200, r.text[:140])
d = r.json() if r.status_code == 200 else {}
classes = d.get("classes") or []
ck("her classroom is there", any(c.get("id") == cid for c in classes),
   f"{len(classes)} classes back")
mine = [c for c in classes if c.get("id") == cid]
ck("named as hers, with the subject she holds",
   bool(mine) and "Biology" in (mine[0].get("my_subjects") or []),
   str(mine[:1])[:160])
posts = d.get("posts") or []
ck("and the class+subject+code appear together",
   any(p.get("class_id") == cid and p.get("subject") == "Biology"
       and (p.get("code") or "").startswith("T-") for p in posts),
   "9-A Maths and 9-B Maths are different posts and the code is what tells "
   "a board which one it is standing in")

print("\nshe is a subject teacher, not an administrator")
ck("she cannot open the school's own screens",
   her.get("/api/head/overview").status_code == 403,
   "being put on a subject grants that subject, not the school")

print("\nand the subject's code opens a board without signing anybody in")
board = TestClient(main.app)
r = board.post("/api/craxlearn/room", json={"code": code})
ck("the code names the room", r.status_code == 200, r.text[:120])
room = r.json() if r.status_code == 200 else {}
ck("with her name on it", (room.get("teacher") or "") == "Path Teacher",
   room.get("teacher"))
ck("and a board token rather than a session", bool(room.get("board_token")))
# The same code signs her in. One code, both jobs — restored after the
# refusal left a teacher holding only a code with no way in at all, going
# round a loop instead of teaching. The trade is written down in
# sign_in_with_code and answered by the code being rotatable.
signin = TestClient(main.app)
r = signin.post("/api/auth/code", json={"code": code})
ck("the same code signs its teacher in", r.status_code == 200, r.text[:140])
ck("as the teacher on that subject",
   (r.json() or {}).get("name") == "Path Teacher", r.text[:140])
ck("and it names the class and subject it belongs to",
   (r.json() or {}).get("subject") == "Biology", r.text[:140])
ck("she lands on her classes",
   signin.get("/api/teacher/classes").status_code == 200)

print("\nthe office can see, and repair, how she gets in")
r = office.get("/api/head/overview")
ck("the overview loads", r.status_code == 200, r.text[:100])
ov = r.json() if r.status_code == 200 else {}
subs = []
for c in (ov.get("classrooms") or []):
    if c.get("id") == cid:
        subs = c.get("subjects") or []
ck("the subject row carries her address, not only her name",
   any(s.get("teacher_email") == tem for s in subs),
   "the row that shows a board code beside a teacher's name is where "
   "somebody asks how she signs in; the answer belongs on it")

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\nPASSED {len(P)}   FAILED {len(F)}")
sys.exit(1 if F else 0)
