"""Say it to the people it is for.

Every notice went to every child in the school. Right for a closure, wrong for
almost everything else a school admin sends: "staff meeting at four" reaching
four hundred children, "your marks for 9A are outstanding" reaching the child
whose marks they are.

A notice now carries who it is for — everybody, the teachers, the students, one
class, or named people — and the attachment goes with it, because the things
worth targeting are usually the ones with a timetable or a form attached.

What is pinned:

**Nobody reads what was not addressed to them**, which is the entire point and
is checked from both sides for every audience.

**A notice written before any of this existed still reaches everybody.** Its
audience column is empty, and an empty audience has to keep meaning "all" or
the change silently unpublishes every notice a school already has.

**A target that would reach nobody is refused.** "People" with no people named
looks sent and arrives nowhere, which is worse than an error.

**Staff can read a notice at all.** They had no feed: the only one was the
learner's standing panel, so anything addressed to teachers was written and
never seen.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"   # local test database; refused on a deployment
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"

import datetime as dt                              # noqa: E402
import time                                        # noqa: E402

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
    em = f"au{tag}{stamp}@example.com"
    c.post("/api/auth/signup",
           json={"name": f"P{tag}", "email": em, "password": "AudPass123!"})
    u = db.query(main.User).filter(main.User.email == em).first()
    u.dob = dt.date(1990, 1, 1)
    db.commit()
    return c, u


sc = main.School(name=f"AudSchool {stamp}")
db.add(sc)
db.commit()
db.refresh(sc)
hcode = f"HEAD-A{str(stamp)[-4:]}"
db.add(main.TeacherCode(code=hcode, school=sc.name, school_id=sc.id,
                        is_head=True, active=True))
db.commit()

admin, au = acct("adm")
admin.post("/api/class/join", json={"code": hcode})

teacher, tu = acct("tch")
main._grant_teacher(db, tu, sc.name, sc.id, "teacher")
db.commit()

CID = admin.post("/api/teacher/class", json={"name": f"10-A {stamp}"}).json()["id"]
admin.post(f"/api/teacher/class/{CID}/roster", json={"names": "Kavya N\nRohit P"})
code = db.get(main.Klass, CID).join_code

main._CODE_TRIES.clear()
main._CODE_FAILS.clear()
pupil = TestClient(main.app)
names = pupil.post("/api/craxlearn/code", json={"code": code}).json()["names"]
pupil.post("/api/craxlearn/claim",
           json={"code": code, "roster_id": names[0]["id"]})
pupil_user = db.query(main.RosterName).get(names[0]["id"]).claimed_by

other_pupil = TestClient(main.app)
other_pupil.post("/api/craxlearn/claim",
                 json={"code": code, "roster_id": names[1]["id"]})


def post(aud, title, **kw):
    body = {"title": title, "body": "x", "urgent": False,
            "starts_on": "", "ends_on": "", "audience": aud}
    body.update(kw)
    return admin.post("/api/office/notice", json=body)


def titles(client):
    return [n["title"] for n in client.get("/api/my/notices").json()["notices"]]


print("\nto everybody")
check("posting to all works", post("all", "School shut Friday").status_code == 200)
check("a teacher sees it", "School shut Friday" in titles(teacher))
check("a student sees it", "School shut Friday" in titles(pupil))

print("\nto the teachers only")
check("posting to teachers works",
      post("teachers", "Staff meeting at four").status_code == 200)
check("the teacher sees it", "Staff meeting at four" in titles(teacher))
check("the student does not", "Staff meeting at four" not in titles(pupil),
      "four hundred children reading a staff meeting is how the panel dies")

print("\nto the students only")
check("posting to students works",
      post("students", "Bring your PE kit").status_code == 200)
check("the student sees it", "Bring your PE kit" in titles(pupil))
check("the teacher does not", "Bring your PE kit" not in titles(teacher))

print("\nto one class")
check("posting to a class works",
      post("class", "10-A trip on Monday", class_id=CID).status_code == 200)
check("a child in that class sees it", "10-A trip on Monday" in titles(pupil))
r = post("class", "Nowhere", class_id=0)
check("a class notice with no class is refused", r.status_code == 400,
      f"got {r.status_code}")

print("\nto named people")
check("posting to one person works",
      post("people", "Your marks are outstanding",
           audience_ids=str(pupil_user)).status_code == 200)
check("that person sees it",
      "Your marks are outstanding" in titles(pupil))
check("nobody else does",
      "Your marks are outstanding" not in titles(other_pupil)
      and "Your marks are outstanding" not in titles(teacher),
      "this is the one that must never leak")
r = post("people", "Nobody at all", audience_ids="")
check("naming nobody is refused", r.status_code == 400,
      "it would look sent and arrive nowhere")

print("\nan older notice, written before any of this")
n = main.SchoolNotice(school_id=sc.id, author_id=au.id,
                      title="From before", body="x")
n.audience = ""          # exactly what a migrated row has
db.add(n)
db.commit()
check("still reaches the students", "From before" in titles(pupil),
      "an empty audience must keep meaning everybody")
check("and the teachers", "From before" in titles(teacher))

print("\ntargeting can be corrected after the fact")
nid = [x["id"] for x in admin.get("/api/office/notices").json()["notices"]
       if x["title"] == "Staff meeting at four"][0]
r = admin.patch(f"/api/office/notice/{nid}",
                json={"title": "Staff meeting at four", "body": "x",
                      "urgent": False, "starts_on": "", "ends_on": "",
                      "audience": "all"})
check("an audience can be widened", r.status_code == 200, r.text[:60])
check("and the student now sees it", "Staff meeting at four" in titles(pupil))

print("\nan attachment rides along with the targeting")
r = admin.post(f"/api/office/notice/{nid}/file",
               files={"file": ("rota.pdf", b"%PDF-1.4 rota", "application/pdf")})
check("a targeted notice can carry a PDF", r.status_code == 200, r.text[:60])
check("and the recipient can fetch it",
      pupil.get(f"/api/office/notice/{nid}/file").status_code == 200)

print("\nfinding somebody to address it to")
r = admin.get("/api/head/people")
allp = r.json()["people"]
check("staff and learners are both findable", r.status_code == 200
      and any(p["kind"] == "teacher" for p in allp)
      and any(p["kind"] == "student" for p in allp), str(len(allp)))
check("a learner carries the class they are in",
      any(p["kind"] == "student" and p["where"] for p in allp))
r = admin.get("/api/head/people", params={"q": "kav"})
check("part of a name finds them",
      any("Kavya" in p["name"] for p in r.json()["people"]),
      "a school of four hundred cannot be a dropdown")
r = admin.get("/api/head/people", params={"q": str(pupil_user)})
check("so does the id typed straight in",
      any(p["id"] == pupil_user for p in r.json()["people"]),
      "which is how you tell two children called Ravi apart")
r = admin.get("/api/head/people", params={"kind": "teachers"})
check("staff can be listed on their own",
      all(p["kind"] == "teacher" for p in r.json()["people"]))
# A teacher can now post to their own class or to named students, so they
# reach this search — but only for the children they actually teach. "Can
# post to my class" must not become "can read every name in the school".
r = teacher.get("/api/head/people")
check("a teacher with no class of their own sees nobody",
      r.status_code == 200 and r.json()["people"] == [],
      f"got {r.status_code} {r.text[:60]} — a register is children's names")
check("and no staff list either",
      all(p["kind"] != "teacher" for p in r.json()["people"]),
      "addressing colleagues is what the admin's school-wide notice is for")

print("\nan attachment is only for whoever the notice was for")
r = post("people", "Private with a form", audience_ids=str(pupil_user))
pid = r.json()["notice"]["id"]
admin.post(f"/api/office/notice/{pid}/file",
           files={"file": ("form.pdf", b"%PDF-1.4 form", "application/pdf")})
check("the addressee can fetch it",
      pupil.get(f"/api/office/notice/{pid}/file").status_code == 200)
check("somebody else cannot",
      other_pupil.get(f"/api/office/notice/{pid}/file").status_code == 403,
      "the attachment IS the notice")

print(f"\nPASSED {PASS}   FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
