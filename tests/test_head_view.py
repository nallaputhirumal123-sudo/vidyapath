"""What a head teacher can see, change and attach.

They had responsibility for a school and no way to exercise most of it.

**The notices they put up.** Posting and deleting existed; listing did not, so
the only place a notice could be read back was the learner's standing screen —
which filters to what is live today. A head could write a notice, never see it
again, and not know what the school was currently being told.

**Correcting one.** There was no edit. A wrong time could only be deleted and
retyped, and in between the school had no notice at all.

**The thing being talked about.** A timetable, a consent form, a photograph of
the notice board.

**The children.** Staff were listable; learners were not. "How many have
actually signed in" was answered by opening every class in turn.

**A misspelt name.** Deleting a claimed name is refused because there is an
account behind it — so a child whose name was typed wrong was stuck with it.
Renaming is safe where deleting is not: the row keeps its id and its claim, so
the account and its work are untouched and only the label changes.

Every one of these returns children's names, so every one is checked for
crossing between schools.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
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
    em = f"hv{tag}{stamp}@example.com"
    c.post("/api/auth/signup",
           json={"name": f"P{tag}", "email": em, "password": "HeadView123!"})
    u = db.query(main.User).filter(main.User.email == em).first()
    u.dob = dt.date(1990, 1, 1)
    db.commit()
    return c, u


def school(tag):
    sc = main.School(name=f"S{tag}{stamp}")
    db.add(sc)
    db.commit()
    db.refresh(sc)
    code = f"HEAD-{tag}{str(stamp)[-4:]}"
    db.add(main.TeacherCode(code=code, school=sc.name, school_id=sc.id,
                            is_head=True, active=True))
    db.commit()
    c, u = acct(tag)
    c.post("/api/class/join", json={"code": code})
    return c, u, sc


head, hu, sc1 = school("a")
rival, ru, sc2 = school("b")

r = head.post("/api/teacher/class", json={"name": f"9-A {stamp}"})
CID = r.json()["id"]
head.post(f"/api/teacher/class/{CID}/roster",
          json={"names": "Nila Raman\nArun Kumar\nDivya S"})

print("\nthe notices this school has put up")
r = head.post("/api/office/notice",
              json={"title": "Exam moved", "body": "Now Tuesday.",
                    "urgent": True, "starts_on": "", "ends_on": ""})
check("a notice can be put up", r.status_code == 200, r.text[:60])
NID = r.json()["notice"]["id"]

r = head.get("/api/office/notices")
check("and read back", r.status_code == 200 and
      any(n["id"] == NID for n in r.json()["notices"]),
      "this had no route at all — a head could not see what they had said")

# one that expired yesterday: the learner view hides it, this must not
head.post("/api/office/notice",
          json={"title": "Old one", "body": "x", "urgent": False,
                "starts_on": "", "ends_on": "2020-01-01"})
titles = [n["title"] for n in head.get("/api/office/notices").json()["notices"]]
check("including one that has expired", "Old one" in titles,
      "deciding what to say next means seeing what was already said")

print("\ncorrecting one instead of deleting it")
r = head.patch(f"/api/office/notice/{NID}",
               json={"title": "Exam moved to Wednesday", "body": "Not Tuesday.",
                     "urgent": True, "starts_on": "", "ends_on": ""})
check("a notice can be edited", r.status_code == 200, r.text[:60])
check("and the change stuck",
      r.json()["notice"]["title"] == "Exam moved to Wednesday")

print("\nattaching a picture or a PDF")
pdf = b"%PDF-1.4 timetable"
r = head.post(f"/api/office/notice/{NID}/file",
              files={"file": ("timetable.pdf", pdf, "application/pdf")})
check("a PDF attaches", r.status_code == 200, r.text[:60])
check("and the notice says so", r.json()["notice"]["has_file"] is True)
r = head.post(f"/api/office/notice/{NID}/file",
              files={"file": ("board.png", b"\x89PNG\r\n\x1a\n", "image/png")})
check("so does a picture", r.status_code == 200, r.text[:60])
r = head.post(f"/api/office/notice/{NID}/file",
              files={"file": ("sneaky.html", b"<script>", "text/html")})
check("anything else is refused", r.status_code == 400,
      "a notice is read by every child in the school")

r = head.get(f"/api/office/notice/{NID}/file")
check("the attachment downloads", r.status_code == 200 and r.content[:4] == b"\x89PNG",
      f"got {r.status_code}")
r = head.delete(f"/api/office/notice/{NID}/file")
check("and can be taken off again", r.status_code == 200)
check("leaving the notice itself",
      head.get("/api/office/notices").status_code == 200)

print("\nthe children, all of them")
r = head.get("/api/head/students")
d = r.json()
check("the head sees every register in the school", r.status_code == 200
      and d["total"] == 3, str(d.get("total")))
check("and how many have signed in", d["signed_in"] == 0, str(d["signed_in"]))
check("grouped by class with its code",
      d["classes"][0]["join_code"].startswith("VP-"))

print("\ncorrecting a child's name")
rid = d["classes"][0]["students"][0]["id"]
r = head.patch(f"/api/teacher/roster/{rid}", json={"name": "Arun Kumaran"})
check("a name can be corrected", r.status_code == 200, r.text[:60])
r = head.patch(f"/api/teacher/roster/{rid}", json={"name": "Divya S"})
check("but not into another child's name", r.status_code == 409,
      f"got {r.status_code}")

# a claimed name is the case deleting refuses, and renaming must allow
main._CODE_TRIES.clear()
main._CODE_FAILS.clear()
code = d["classes"][0]["join_code"]
anon = TestClient(main.app)
free = anon.post("/api/craxlearn/code", json={"code": code}).json()["names"]
taken = free[0]["id"]
anon.post("/api/craxlearn/claim", json={"code": code, "roster_id": taken})
r = head.delete(f"/api/teacher/roster/{taken}")
check("a claimed name still cannot be deleted", r.status_code == 400,
      "there is an account with work behind it")
r = head.patch(f"/api/teacher/roster/{taken}", json={"name": "Corrected Name"})
check("but it can be corrected", r.status_code == 200, r.text[:60])
u = db.query(main.User).filter(
    main.User.id == db.get(main.RosterName, taken).claimed_by).first()
db.refresh(u)
check("and the account is renamed with it", u.name == "Corrected Name",
      f"{u.name} — otherwise the register and the screen disagree")

print("\nnone of it crosses to another school")
r = rival.get("/api/head/students")
check("a different head sees none of these children",
      r.status_code == 200 and r.json()["total"] == 0, str(r.json().get("total")))
r = rival.get("/api/office/notices")
check("nor any of these notices",
      all(n["id"] != NID for n in r.json()["notices"]))
r = rival.patch(f"/api/office/notice/{NID}",
                json={"title": "Hijacked", "body": "", "urgent": False,
                      "starts_on": "", "ends_on": ""})
check("and cannot edit one", r.status_code == 403, f"got {r.status_code}")
r = rival.patch(f"/api/teacher/roster/{rid}", json={"name": "Hijacked"})
check("nor rename a child in it", r.status_code in (403, 404),
      f"got {r.status_code}")

print(f"\nPASSED {PASS}   FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
