"""Work that is open, work that is closed, and who closed it.

A due date is a request. Closing is the decision, and it belongs to a teacher:
plenty of classes hand in late and are marked anyway, and a date that shut the
door by itself would take that judgement from the person who should have it.

What is pinned:

**Closed refuses a hand-in.** Checked on the route, not only drawn on the page.
A hidden button is not a rule, and a learner submitting from a stale tab would
otherwise land work on a teacher who had finished marking.

**Closed work stays readable.** Taking the questions away at the deadline would
punish the person revising from them.

**It says who closed it.** "Why is this shut" should have an answer with a name
on it.

**Only the subject's teacher decides.** The same rule as everything else about
that subject.
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

sc = main.School(name=f"AsgSchool {stamp}")
db.add(sc)
db.commit()
db.refresh(sc)
hc = main._gen_head_code(db)
db.add(main.TeacherCode(code=hc, school=sc.name, school_id=sc.id,
                        is_head=True, active=True))
db.commit()

admin = TestClient(main.app)
aem = f"as2{stamp}@example.com"
admin.post("/api/auth/signup",
           json={"name": "Admin", "email": aem, "password": "AsgPass123!"})
u = db.query(main.User).filter(main.User.email == aem).first()
u.dob = dt.date(1985, 1, 1)
db.commit()
admin.post("/api/class/join", json={"code": hc})
CID = admin.post("/api/teacher/class",
                 json={"name": f"8-S {stamp}"}).json()["id"]
admin.post(f"/api/teacher/class/{CID}/roster", json={"names": "Tara V"})


def staff(tag, subject):
    made = admin.post("/api/head/staff",
                      json={"name": f"T{tag}", "email": f"a{tag}{stamp}@s.in",
                            "role": "teacher"}).json()
    admin.post("/api/head/assign",
               json={"class_id": CID, "subject": subject,
                     "user_id": made["user_id"]})
    c = TestClient(main.app)
    c.post("/api/auth/login", json={"email": f"a{tag}{stamp}@s.in",
                                    "password": _pw(made["user_id"])})
    return c, made["user_id"]


phys, phys_id = staff("p", "Physics")
math, _ = staff("m", "Mathematics")
AID = phys.post(f"/api/teacher/class/{CID}/assignment",
                json={"subject": "Physics", "title": "Ray diagrams",
                      "body": "Q1-Q5", "due_date": ""}).json()["id"]

main._CODE_TRIES.clear()
main._CODE_FAILS.clear()
code = db.get(main.Klass, CID).join_code
kid = TestClient(main.app)
free = kid.post("/api/craxlearn/code", json={"code": code}).json()["names"]
kid.post("/api/craxlearn/claim",
         json={"code": code, "roster_id": free[0]["id"]})


def mine():
    d = kid.get("/api/class/mine").json()
    for c in d.get("classes", []):
        for a in c.get("assignments", []):
            if a["id"] == AID:
                return a
    return {}


print("\nwhile it is open")
check("the learner sees it as open", mine().get("closed") is False,
      str(mine().get("closed")))
check("and can hand in",
      kid.post(f"/api/assignment/{AID}/submit",
               json={"response": "my answers"}).status_code == 200)

print("\nclosing it")
r = phys.post(f"/api/teacher/assignment/{AID}/close", json={"closed": True})
check("the subject teacher can close it", r.status_code == 200, r.text[:60])
a = mine()
check("the learner sees it as closed", a.get("closed") is True)
check("and who closed it", a.get("closed_by") == phys_id,
      "why is this shut should have a name on it")
check("with when", bool(a.get("closed_at")), str(a.get("closed_at"))[:20])

print("\nwhat closed actually means")
r = kid.post(f"/api/assignment/{AID}/submit", json={"response": "late work"})
check("a hand-in is refused on the route", r.status_code == 403,
      f"got {r.status_code} — a hidden button is not a rule")
check("and says they can still read it",
      "read it" in (r.json().get("detail") or ""),
      (r.json().get("detail") or "")[:70])
check("the questions are still there", bool(mine().get("title")),
      "closing must not punish somebody revising from it")

print("\nwho may decide")
r = math.post(f"/api/teacher/assignment/{AID}/close", json={"closed": True})
check("another subject's teacher cannot", r.status_code == 403,
      f"got {r.status_code}")

print("\nand it opens again")
r = phys.post(f"/api/teacher/assignment/{AID}/close", json={"closed": False})
check("the teacher can reopen it", r.status_code == 200, r.text[:60])
check("the learner sees it open", mine().get("closed") is False)
check("and can hand in again",
      kid.post(f"/api/assignment/{AID}/submit",
               json={"response": "on time now"}).status_code == 200)

print(f"\nPASSED {PASS}   FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
