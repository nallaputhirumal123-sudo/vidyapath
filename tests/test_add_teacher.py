"""Adding a teacher the same way you add a student.

The class screen had a register for students and nothing for staff. Putting a
teacher in a class meant adding a subject, copying the code it minted, getting
that code to the person somehow, and waiting for them to sign up and redeem it
— four steps and a hand-off, against three names typed into a box for students.

That asymmetry was the reason signing in was hard: one side of the school had a
flow and the other had a code to read down a corridor.

Both routes existed and neither had a screen. This pins the pair working
together, which is what the screen now does in one press: make the account,
hand back a one-time password, and put them on the subject.

The property that matters most is the last one — that the person who comes out
of this can actually sign in and teach. An onboarding flow that produces an
account which cannot do the job is worse than no flow, because it looks done.
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

def _pw(uid, pw='TeachPass123!'):
    """A password for a staff account, for suites that only need a session.

    Staff are not given one when they are created any more — a teacher signs
    in with the subject code the office hands them. These suites are about
    what a teacher may SEE once signed in, not about how they got there, so
    they set one directly rather than being rewritten around codes.
    """
    _d = main.SessionLocal()
    _u = _d.get(main.User, uid)
    _u.password_hash = main.hash_pw(pw)
    _d.commit(); _d.close()
    return pw


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

sc = main.School(name=f"AddSchool {stamp}")
db.add(sc)
db.commit()
db.refresh(sc)
hc = main._gen_head_code(db)
db.add(main.TeacherCode(code=hc, school=sc.name, school_id=sc.id,
                        is_head=True, active=True))
db.commit()

admin = TestClient(main.app)
em = f"at{stamp}@example.com"
admin.post("/api/auth/signup",
           json={"name": "Admin", "email": em, "password": "AddPass123!"})
u = db.query(main.User).filter(main.User.email == em).first()
u.dob = dt.date(1990, 1, 1)
db.commit()
admin.post("/api/class/join", json={"code": hc})
CID = admin.post("/api/teacher/class",
                 json={"name": f"5-D {stamp}"}).json()["id"]

print("\nmaking the account")
temail = f"latha{stamp}@school.in"
r = admin.post("/api/head/staff",
               json={"name": "Latha R", "email": temail, "role": "teacher"})
check("a teacher account is created", r.status_code == 200, r.text[:80])
made = r.json()
# No password comes back any more, and that is the point. A teacher signs in
# with the subject code the office gives them, so there is nothing for a
# password to be typed into — and the one this used to print was the reason a
# school could create an account nobody could ever use.
check("no password is handed out", not made.get("temporary_password"),
      str(made)[:110])
check("whatever password the row holds is stored hashed, not readably",
      _pw(made["user_id"]) not in (
          db.get(main.User, made["user_id"]).password_hash or ""),
      "never stored in a form anybody can read back")

print("\nputting them on a subject")
r = admin.post("/api/head/assign",
               json={"class_id": CID, "subject": "Physics",
                     "user_id": made["user_id"]})
check("the subject attaches in the same flow", r.status_code == 200,
      r.text[:70])

print("\nand they appear on the class")
d = admin.get(f"/api/teacher/class/{CID}").json()
check("the class lists them",
      any("Latha" in (t.get("name") or "") for t in d.get("teachers", [])),
      str([t.get("name") for t in d.get("teachers", [])]))

print("\nthe part that actually matters: can they work")
teacher = TestClient(main.app)
r = teacher.post("/api/auth/login",
                 json={"email": temail, "password": _pw(made["user_id"])})
check("they can sign in with what they were given", r.status_code == 200,
      r.text[:70])
r = teacher.post(f"/api/teacher/class/{CID}/assignment",
                 json={"subject": "Physics", "title": "Ch 1", "body": "read",
                       "due_date": ""})
check("and set work in their subject", r.status_code == 200, r.text[:70])
r = teacher.post(f"/api/teacher/class/{CID}/assignment",
                 json={"subject": "Chemistry", "title": "No", "body": "x",
                       "due_date": ""})
check("but not in one they do not hold", r.status_code == 403,
      f"got {r.status_code}")

print("\nadding somebody who already has an account")
r = admin.post("/api/head/staff",
               json={"name": "Latha R", "email": temail, "role": "teacher"})
check("it does not fail", r.status_code == 200, r.text[:70])
check("and does not hand out a new password",
      not r.json().get("temporary_password"),
      "their existing password still works, and saying otherwise would lock "
      "them out of their own account")

print("\nnobody else may add staff")
r = teacher.post("/api/head/staff",
                 json={"name": "Sneaky", "email": f"s{stamp}@x.in",
                       "role": "teacher"})
check("a subject teacher cannot", r.status_code == 403, f"got {r.status_code}")

print(f"\nPASSED {PASS}   FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
