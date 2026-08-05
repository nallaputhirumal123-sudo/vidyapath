"""A student's class, by subject, which is how a student thinks of it.

My class listed assignments from every subject in one stream. Nobody thinks
about school that way. They think "what did we do in Physics", and the
teacher's name matters because that is who they ask on Monday.

What is pinned:

**Every subject is listed, including one nobody teaches yet.** Hiding an
unstaffed subject hides from a class that it exists and nobody is on it, which
is a thing their parents would rather know than not.

**And anything filed under a subject with no slot.** A class taught something
before the timetable caught up still has that material, and it must not vanish
because the admin has not made the slot.

**A subject shows only its own things.** A student opening Physics must not be
handed Monday's Maths worksheet, which is the entire reason for splitting the
stream up.

**A learner can only see their own class.** These routes carry teachers' names
and children's questions.
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

sc = main.School(name=f"SubjSchool {stamp}")
db.add(sc)
db.commit()
db.refresh(sc)
hc = main._gen_head_code(db)
db.add(main.TeacherCode(code=hc, school=sc.name, school_id=sc.id,
                        is_head=True, active=True))
db.commit()

admin = TestClient(main.app)
aem = f"sj{stamp}@example.com"
admin.post("/api/auth/signup",
           json={"name": "Admin", "email": aem, "password": "SubjPass1!"})
u = db.query(main.User).filter(main.User.email == aem).first()
u.dob = dt.date(1985, 1, 1)
db.commit()
admin.post("/api/class/join", json={"code": hc})
CID = admin.post("/api/teacher/class",
                 json={"name": f"7-B {stamp}"}).json()["id"]
admin.post(f"/api/teacher/class/{CID}/roster", json={"names": "Isha T"})

# Physics has a teacher; Chemistry deliberately does not.
made = admin.post("/api/head/staff",
                  json={"name": "Latha R", "email": f"lt{stamp}@s.in",
                        "role": "teacher"}).json()
admin.post("/api/head/assign",
           json={"class_id": CID, "subject": "Physics",
                 "user_id": made["user_id"]})
admin.post("/api/head/assign",
           json={"class_id": CID, "subject": "Chemistry", "user_id": 0})

teacher = TestClient(main.app)
teacher.post("/api/auth/login",
             json={"email": f"lt{stamp}@s.in",
                   "password": made["temporary_password"]})
teacher.post(f"/api/teacher/class/{CID}/assignment",
             json={"subject": "Physics", "title": "Ray diagrams",
                   "body": "Q1-Q5", "due_date": ""})
teacher.post(f"/api/teacher/class/{CID}/material/link",
             json={"title": "Light notes", "url": "https://ncert.nic.in/x",
                   "subject": "Physics", "note": "Read first"})
# A worksheet under a subject that has no slot at all.
admin.post(f"/api/teacher/class/{CID}/material/link",
           json={"title": "Maths worksheet", "url": "https://x.in/m",
                 "subject": "Mathematics", "note": ""})

main._CODE_TRIES.clear()
main._CODE_FAILS.clear()
code = db.get(main.Klass, CID).join_code
kid = TestClient(main.app)
free = kid.post("/api/craxlearn/code", json={"code": code}).json()["names"]
kid.post("/api/craxlearn/claim",
         json={"code": code, "roster_id": free[0]["id"]})

print("\nthe subjects in this class")
r = kid.get(f"/api/class/{CID}/subjects")
check("a learner can read them", r.status_code == 200, r.text[:70])
subs = {x["subject"]: x for x in r.json()["subjects"]}
check("Physics is there with its teacher",
      subs.get("Physics", {}).get("teacher") == "Latha R",
      str(subs.get("Physics")))
check("Chemistry is there with nobody on it",
      "Chemistry" in subs and not subs["Chemistry"]["teacher"],
      "a class should know a subject exists and is unstaffed")
check("and Mathematics appears from its material alone",
      "Mathematics" in subs,
      "taught before the timetable caught up, and it must not vanish")

print("\nwhat each subject carries")
check("Physics counts its own work and reading",
      subs["Physics"]["assignments"] == 1 and subs["Physics"]["materials"] == 1,
      str(subs["Physics"]))
check("and does not count another subject's",
      subs["Physics"]["materials"] == 1
      and subs.get("Mathematics", {}).get("materials") == 1,
      "opening Physics must not hand over Monday's Maths worksheet")
check("an unstaffed subject counts nothing yet",
      subs["Chemistry"]["assignments"] == 0
      and subs["Chemistry"]["materials"] == 0)

print("\nasking a question against a subject")
r = kid.post(f"/api/class/{CID}/discussion",
             json={"body": "Why does the ray bend?", "subject": "Physics"})
check("a learner can ask", r.status_code == 200, r.text[:60])
subs2 = {x["subject"]: x for x in
         kid.get(f"/api/class/{CID}/subjects").json()["subjects"]}
check("and it counts against that subject",
      subs2["Physics"]["questions"] == 1, str(subs2["Physics"]["questions"]))
check("not against the others",
      subs2["Chemistry"]["questions"] == 0)

print("\nsomebody else's class")
out = TestClient(main.app)
oem = f"sjout{stamp}@example.com"
out.post("/api/auth/signup",
         json={"name": "Out", "email": oem, "password": "SubjPass1!"})
r = out.get(f"/api/class/{CID}/subjects")
check("is not readable", r.status_code in (403, 404), f"got {r.status_code}")

print(f"\nPASSED {PASS}   FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
