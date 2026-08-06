"""Three places, so a teacher knows where a thing goes.

A class produces three different kinds of thing and they are not
interchangeable:

    Assignments     work set, with a date and somebody expected to hand it in
    Study material  something to read, which outlives the homework it was
                    first needed for
    Discussion      somebody not understanding something, and saying so

They all went into one list of assignments, or nowhere. That is how the
question nobody answered gets lost between a worksheet and a slide deck, and
why a teacher with a chapter to share sets it as homework — the only slot that
existed.

Material already had routes and no screen. Discussion had neither. What is
pinned here is that the three stay separate, and that discussion is open to the
class rather than to staff alone: a discussion only one side can start is a
noticeboard.
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
from _school import teacher_on, make_staff   # noqa: E402

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

sc = main.School(name=f"3P {stamp}")
db.add(sc)
db.commit()
db.refresh(sc)
hc = main._gen_head_code(db)
db.add(main.TeacherCode(code=hc, school=sc.name, school_id=sc.id,
                        is_head=True, active=True))
db.commit()

admin = TestClient(main.app)
em = f"tp3{stamp}@example.com"
admin.post("/api/auth/signup",
           json={"name": "Admin", "email": em, "password": "ThrPass123!"})
u = db.query(main.User).filter(main.User.email == em).first()
u.dob = dt.date(1990, 1, 1)
db.commit()
admin.post("/api/class/join", json={"code": hc})
CID = admin.post("/api/teacher/class",
                 json={"name": f"8-Z {stamp}"}).json()["id"]
admin.post(f"/api/teacher/class/{CID}/roster", json={"names": "Zara Q\nYash R"})

main._CODE_TRIES.clear()
main._CODE_FAILS.clear()
code = db.get(main.Klass, CID).join_code
kid = TestClient(main.app)
# Roster names no longer disappear when claimed, so "the first name on
# the list" is the same child every time and every client after the
# first lands in one account — which single-session sign-in then signs
# out. Take the first name nobody has taken instead.
free = [n for n in kid.post("/api/craxlearn/code", json={"code": code}).json()["names"] if not n.get("taken")]
kid.post("/api/craxlearn/claim",
         json={"code": code, "roster_id": free[0]["id"]})
kid2 = TestClient(main.app)
free2 = [n for n in kid2.post("/api/craxlearn/code", json={"code": code}).json()["names"] if not n.get("taken")]
kid2.post("/api/craxlearn/claim",
          json={"code": code, "roster_id": free2[0]["id"]})

# Material and the discussion belong to the TEACHER of a subject. `admin`
# here runs the school: it makes the class, the subject and the register, and
# the classroom itself is somebody else's.
tch, _uid, _code, _sid = teacher_on(main, admin, CID, "Science",
                                    "Places Teacher")

print("\nstudy material, which is not homework")
r = tch.post(f"/api/teacher/class/{CID}/material/link",
               json={"title": "Chapter 4 — Light", "url": "https://ncert.nic.in/x",
                     "subject": "Science", "note": "Read before Friday"})
check("a link can be shared", r.status_code == 200, r.text[:70])
r = tch.post(f"/api/teacher/class/{CID}/material/file",
               files={"file": ("slides.pdf", b"%PDF-1.4 slides",
                               "application/pdf")},
               data={"title": "Light slides", "subject": "Science", "note": ""})
check("so can a file", r.status_code == 200, r.text[:70])
mats = admin.get(f"/api/class/{CID}/materials").json()["materials"]
check("both appear together", len(mats) == 2, str(len(mats)))
check("a learner in the class can read them",
      len(kid.get(f"/api/class/{CID}/materials").json()["materials"]) == 2)

print("\nand it did not become an assignment")
asg = admin.get(f"/api/teacher/class/{CID}").json().get("assignments", [])
check("the assignment list is still empty", len(asg) == 0,
      "material outlives the homework it was first needed for")

print("\ndiscussion, which anybody in the class may start")
r = kid.post(f"/api/class/{CID}/discussion",
             json={"body": "I did not follow the refraction bit."})
check("a learner can ask a question", r.status_code == 200, r.text[:70])
qid = r.json()["id"]
r = tch.post(f"/api/class/{CID}/discussion",
             json={"body": "Look at figure 4.3 first.", "parent_id": qid})
check("a teacher can answer it", r.status_code == 200, r.text[:70])

d = kid2.get(f"/api/class/{CID}/discussion").json()
check("the whole class sees the thread", len(d["threads"]) == 1)
check("with the reply under the question",
      len(d["threads"][0]["replies"]) == 1)
check("and the teacher's reply is marked as theirs",
      d["threads"][0]["replies"][0]["from_staff"] is True,
      "a class should know which answer came from the teacher")
check("the learner's question is not",
      d["threads"][0]["from_staff"] is False)

print("\nthreads stay one level deep")
rid = d["threads"][0]["replies"][0]["id"]
r = kid.post(f"/api/class/{CID}/discussion",
             json={"body": "Thanks!", "parent_id": rid})
check("a reply to a reply is accepted", r.status_code == 200)
d = kid.get(f"/api/class/{CID}/discussion").json()
check("but lands on the original question, not nested deeper",
      len(d["threads"]) == 1 and len(d["threads"][0]["replies"]) == 2,
      "anything deeper is a forum, and a forum needs a moderator")

print("\nwho may take something down")
r = kid2.delete(f"/api/class/{CID}/discussion/{qid}")
check("not another learner", r.status_code == 403, f"got {r.status_code}")
r = kid.delete(f"/api/class/{CID}/discussion/{qid}")
check("the person who wrote it can", r.status_code == 200, r.text[:60])
d = kid.get(f"/api/class/{CID}/discussion").json()
check("and its replies go with it", len(d["threads"]) == 0,
      "a class left answering something nobody can see")

print("\nnobody outside the class")
outsider = TestClient(main.app)
oe = f"out3{stamp}@example.com"
outsider.post("/api/auth/signup",
              json={"name": "Out", "email": oe, "password": "OutPass123!"})
r = outsider.get(f"/api/class/{CID}/discussion")
check("cannot read the discussion", r.status_code in (403, 404),
      f"got {r.status_code}")
r = outsider.get(f"/api/class/{CID}/materials")
check("nor the material", r.status_code in (403, 404), f"got {r.status_code}")

print(f"\nPASSED {PASS}   FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
