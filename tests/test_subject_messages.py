"""Messaging a teacher, about the subject they teach you.

A student's message to a teacher hangs off an assignment, and an assignment has
a subject — but the subject never travelled with the thread. A teacher taking
Physics in two classes and Maths in a third read messages with no indication of
which subject they were about, and a student's question only means something
beside the subject it concerns.

The second fault was quieter and worse. _own_class admits every teacher of the
classroom, which is right for reading the register and wrong for reading what a
child wrote privately to the person who teaches them Physics. The Maths teacher
could open it.

The school admin keeps the whole view, because answering a parent about a
message their child sent is the admin's job.
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

sc = main.School(name=f"MsgSchool {stamp}")
db.add(sc)
db.commit()
db.refresh(sc)
hc = main._gen_head_code(db)
db.add(main.TeacherCode(code=hc, school=sc.name, school_id=sc.id,
                        is_head=True, active=True))
db.commit()

admin = TestClient(main.app)
aem = f"ms{stamp}@example.com"
admin.post("/api/auth/signup",
           json={"name": "Admin", "email": aem, "password": "MsgPass123!"})
u = db.query(main.User).filter(main.User.email == aem).first()
u.dob = dt.date(1985, 1, 1)
db.commit()
admin.post("/api/class/join", json={"code": hc})
CID = admin.post("/api/teacher/class",
                 json={"name": f"10-M {stamp}"}).json()["id"]
admin.post(f"/api/teacher/class/{CID}/roster", json={"names": "Riya S"})


def staff(tag, subject):
    made = admin.post("/api/head/staff",
                      json={"name": f"T{tag}", "email": f"m{tag}{stamp}@s.in",
                            "role": "teacher"}).json()
    admin.post("/api/head/assign",
               json={"class_id": CID, "subject": subject,
                     "user_id": made["user_id"]})
    c = TestClient(main.app)
    c.post("/api/auth/login", json={"email": f"m{tag}{stamp}@s.in",
                                    "password": _pw(made["user_id"])})
    return c


phys = staff("p", "Physics")
math = staff("m", "Mathematics")

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

print("\na student messages their teacher")
r = kid.post(f"/api/assignment/{AID}/message",
             json={"body": "I am stuck on Q3."})
check("the message sends", r.status_code == 200, r.text[:70])

print("\nand the subject travels with it")
d = kid.get(f"/api/assignment/{AID}/messages").json()
check("the student's own view names the subject", d.get("subject") == "Physics",
      str(d.get("subject")))
check("and what the work was", d.get("title") == "Ray diagrams",
      str(d.get("title")))
d = phys.get(f"/api/teacher/assignment/{AID}/threads").json()
check("the teacher's list names it too", d.get("subject") == "Physics",
      str(d.get("subject")))
check("with the student who wrote", len(d.get("threads", [])) == 1,
      str(len(d.get("threads", []))))

print("\nand only the teacher of that subject reads it")
r = math.get(f"/api/teacher/assignment/{AID}/threads")
check("the Maths teacher cannot", r.status_code == 403, f"got {r.status_code}")
check("and is told why, not just refused",
      "taught by somebody else" in r.text, r.json().get("detail", "")[:70])
r = phys.get(f"/api/teacher/assignment/{AID}/threads")
check("the Physics teacher can", r.status_code == 200, f"got {r.status_code}")
r = admin.get(f"/api/teacher/assignment/{AID}/threads")
check("and so can the school admin", r.status_code == 200,
      "answering a parent about a message is their job")

print("\nnobody outside the class")
out = TestClient(main.app)
out.post("/api/auth/signup",
         json={"name": "Out", "email": f"mo{stamp}@example.com",
               "password": "MsgPass123!"})
r = out.get(f"/api/assignment/{AID}/messages")
check("cannot read the thread", r.status_code in (403, 404),
      f"got {r.status_code}")

print(f"\nPASSED {PASS}   FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
