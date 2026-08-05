"""Putting a named teacher on a subject, and leaving the timetable alone.

A subject slot has always carried a code the teacher redeems. That is right
when a school is handing codes to staff it has not enrolled yet, and wrong once
the admin has already created the account: they know who teaches Physics in
8-A, and reading a code down the corridor to somebody in the staffroom is a
step that exists only because the software could not do the obvious thing.

Two properties matter more than the convenience, and both were already true
before this route existed — which is why they are asserted here rather than
assumed:

**A teacher holds as many subjects as the timetable says.** Several in one
class, and across as many classes as they teach. A restriction to one would
have to be invented; none is.

**Detaching does not delete the subject.** A school working out who covers
Chemistry next term still has Chemistry on the timetable, with its code intact.
"""
import os
import sys
import time
import datetime as dt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"   # local test database; refused on a deployment
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"

import main                                        # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

PASS = FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {name}" + (f"  ({detail})" if detail else ""))
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


main.Base.metadata.create_all(bind=main.engine)
main.send_email = lambda *a, **k: None
stamp = int(time.time())
db = main.SessionLocal()


def acct(tag):
    c = TestClient(main.app)
    em = f"as{tag}{stamp}@example.com"
    c.post("/api/auth/signup",
           json={"name": f"Person {tag}", "email": em, "password": "AsPass123!"})
    u = db.query(main.User).filter(main.User.email == em).first()
    u.dob = dt.date(1990, 1, 1)
    db.commit()
    return c, u


sc = main.School(name=f"AsSchool {stamp}")
db.add(sc)
db.commit()
db.refresh(sc)
hc = f"HEAD-S{str(stamp)[-4:]}"
db.add(main.TeacherCode(code=hc, school=sc.name, school_id=sc.id,
                        is_head=True, active=True))
db.commit()

admin, _ = acct("adm")
admin.post("/api/class/join", json={"code": hc})
A = admin.post("/api/teacher/class", json={"name": f"8-A {stamp}"}).json()["id"]
B = admin.post("/api/teacher/class", json={"name": f"8-B {stamp}"}).json()["id"]

teacher, tu = acct("tch")
outsider, ou = acct("out")

print("\nassigning without a code")
r = admin.post("/api/head/assign",
               json={"class_id": A, "subject": "Physics", "user_id": tu.id})
check("a named teacher can be put on a subject", r.status_code == 200,
      r.text[:80])
check("the subject keeps a code for anybody who needs one",
      bool(r.json().get("code")), r.json().get("code"))
check("assigning makes them a teacher here",
      main.teacher_row(tu, db) is not None,
      "somebody given a subject IS staff")

print("\nas many subjects as the timetable says")
admin.post("/api/head/assign",
           json={"class_id": A, "subject": "Maths", "user_id": tu.id})
admin.post("/api/head/assign",
           json={"class_id": B, "subject": "Maths", "user_id": tu.id})
check("several subjects in one class",
      main._my_subjects(db, A, tu) == {"Physics", "Maths"},
      str(main._my_subjects(db, A, tu)))
check("and across classes", main._my_subjects(db, B, tu) == {"Maths"},
      str(main._my_subjects(db, B, tu)))

print("\nand they can then do the job")
r = teacher.post(f"/api/teacher/class/{A}/assignment",
                 json={"subject": "Physics", "title": "Ch 2", "body": "read",
                       "due_date": ""})
check("the assigned teacher can set work in that subject",
      r.status_code == 200, r.text[:70])
r = teacher.post(f"/api/teacher/class/{A}/assignment",
                 json={"subject": "Chemistry", "title": "No", "body": "x",
                       "due_date": ""})
check("but not in one they do not hold", r.status_code == 403,
      f"got {r.status_code}")

print("\ndetaching leaves the subject standing")
r = admin.post("/api/head/assign",
               json={"class_id": A, "subject": "Physics", "user_id": 0})
check("a teacher can be taken off", r.status_code == 200, r.text[:60])
slot = (db.query(main.SubjectSlot)
          .filter(main.SubjectSlot.class_id == A,
                  main.SubjectSlot.subject == "Physics").first())
db.refresh(slot)
check("the subject still exists", slot is not None and slot.teacher_id == 0)
check("with its code intact", bool(slot.code),
      "a school deciding who covers Chemistry still has Chemistry")

print("\nnobody else may do this")
r = teacher.post("/api/head/assign",
                 json={"class_id": A, "subject": "Maths", "user_id": ou.id})
check("a subject teacher cannot assign staff", r.status_code == 403,
      f"got {r.status_code}")
r = outsider.post("/api/head/assign",
                  json={"class_id": A, "subject": "Maths", "user_id": ou.id})
check("nor can somebody outside the school", r.status_code in (403, 404),
      f"got {r.status_code}")

print(f"\nPASSED {PASS}   FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
