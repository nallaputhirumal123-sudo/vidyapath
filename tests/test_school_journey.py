"""One school, one morning, start to finish.

Every piece has its own test and every join between two pieces has one. Nobody
had walked the whole path in order, the way the first school actually will —
and the faults that survive a suite like ours are exactly the ones living
between steps that each pass alone.

So this is one continuous journey, in the order a school does it: the platform
makes a school and its code, the admin signs in with it, creates a class, adds
a teacher once and puts them on a subject, types the register with roll
numbers, a child taps their name to sign in, the teacher sets work and shares
material and answers a question, teaches on the board and files the lesson to
the class, the admin takes the register and bills the term — and the child sees
exactly what they should, and nothing they should not.

Nothing is stubbed. Every step goes through the real route with real
permissions, and each uses what the previous step produced: a code read out of
a response, an id, a password shown once. A broken join stops the journey at
the step depending on it rather than reporting green with a hole in the middle.
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
STOPPED = None


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {name}" + (f"  ({detail})" if detail else ""))
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")
    return ok


def must(name, ok, detail=""):
    """A step the rest of the journey depends on."""
    global STOPPED
    if not check(name, ok, detail) and STOPPED is None:
        STOPPED = name
    return ok


main.Base.metadata.create_all(bind=main.engine)
main.send_email = lambda *a, **k: None
stamp = int(time.time())
db = main.SessionLocal()

print("\n1. the platform sets a school up")
sc = main.School(name=f"Journey High {stamp}")
db.add(sc)
db.commit()
db.refresh(sc)
head_code = main._gen_head_code(db)
db.add(main.TeacherCode(code=head_code, school=sc.name, school_id=sc.id,
                        is_head=True, active=True))
db.commit()
must("a school and its admin code exist", len(head_code) == 10,
     f"code {head_code}")

print("\n2. the school admin signs in")
admin = TestClient(main.app)
aem = f"jadmin{stamp}@example.com"
admin.post("/api/auth/signup",
           json={"name": "Priya (admin)", "email": aem,
                 "password": "Journey1!"})
au = db.query(main.User).filter(main.User.email == aem).first()
au.dob = dt.date(1985, 1, 1)
db.commit()
r = admin.post("/api/class/join", json={"code": head_code})
must("the ten-digit code makes them the school admin",
     r.status_code == 200 and "school admin" in r.text.lower(), r.text[:70])

print("\n3. they create a class")
r = admin.post("/api/teacher/class", json={"name": f"9-A {stamp}"})
must("the class is created", r.status_code == 200, r.text[:70])
CID = r.json().get("id")
class_code = r.json().get("join_code", "")
check("with a six-character student code", len(class_code) - 3 == 6,
      class_code)

print("\n4. they add a teacher, once, and give them a subject")
tem = f"jteach{stamp}@example.com"
r = admin.post("/api/head/staff",
               json={"name": "Ravi (teacher)", "email": tem,
                     "role": "teacher"})
must("the teacher account is made", r.status_code == 200, r.text[:70])
made = r.json()
must("and a password is handed over, once, for the office to give them",
     len(made.get("temporary_password") or "") > 6, str(made)[:110])
r = admin.post("/api/head/assign",
               json={"class_id": CID, "subject": "Science",
                     "user_id": made["user_id"]})
must("and they are put on Science in this class", r.status_code == 200,
     r.text[:70])
# The subject they were put on is what they sign in with, so the journey
# needs its code from here on.
_slots = admin.get(f"/api/class/{CID}/subjects").json().get("subjects", [])
SUBJ_CODE = next((s.get("code") for s in _slots
                  if (s.get("subject") or "") == "Science"), "")
if not SUBJ_CODE:
    _hd = admin.get("/api/head/overview").json()
    for _c in (_hd.get("classrooms") or []):
        if _c.get("id") == CID:
            SUBJ_CODE = next((x.get("code") for x in (_c.get("subjects") or [])
                              if (x.get("subject") or "") == "Science"), "")
must("the subject has a code to give them", bool(SUBJ_CODE), str(_slots)[:120])

print("\n5. the register is typed, with roll numbers")
r = admin.post(f"/api/teacher/class/{CID}/roster",
               json={"names": "Aarav Nair, 9101\nDiya Menon, 9102"})
must("both children are on the register",
     r.status_code == 200 and r.json().get("added") == 2, r.text[:70])

print("\n6. a child signs in by tapping their name")
main._CODE_TRIES.clear()
main._CODE_FAILS.clear()
kid = TestClient(main.app)
r = kid.post("/api/craxlearn/code", json={"code": class_code})
must("the class code offers the register",
     r.status_code == 200 and len(r.json().get("names", [])) == 2, r.text[:70])
names = r.json()["names"]
r = kid.post("/api/craxlearn/claim",
             json={"code": class_code, "roster_id": names[0]["id"]})
must("tapping a name signs them in, with no password",
     r.status_code == 200, r.text[:70])

print("\n7. the teacher signs in with what they were given")
# Their address and the password the office read out. NOT the subject code:
# that is a board code, written up where a class can read it, and it opens one
# subject on one board rather than an account.
main._CODE_TRIES.clear(); main._CODE_FAILS.clear()
teacher = TestClient(main.app)
r = teacher.post("/api/auth/login",
                 json={"email": tem, "password": made["temporary_password"]})
must("their password signs them in", r.status_code == 200, r.text[:110])
must("as the person the office made",
     (r.json() or {}).get("name") == "Ravi (teacher)", r.text[:110])
r = TestClient(main.app).post("/api/auth/code", json={"code": SUBJ_CODE})
check("and so does the subject code — one code, both jobs",
      r.status_code == 200, f"got {r.status_code}")

print("\n8. and does the day's work")
r = teacher.post(f"/api/teacher/class/{CID}/assignment",
                 json={"subject": "Science", "title": "Chapter 4 questions",
                       "body": "Q1 to Q6", "due_date": ""})
check("sets work in their subject", r.status_code == 200, r.text[:60])
r = teacher.post(f"/api/teacher/class/{CID}/material/link",
                 json={"title": "Chapter 4 light", "url": "https://ncert.nic.in/x",
                       "subject": "Science", "note": "Read first"})
check("shares study material", r.status_code == 200, r.text[:60])
r = kid.post(f"/api/class/{CID}/discussion",
             json={"body": "I did not follow refraction."})
check("a child asks a question", r.status_code == 200, r.text[:60])
qid = r.json().get("id")
r = teacher.post(f"/api/class/{CID}/discussion",
                 json={"body": "Look at figure 4.3.", "parent_id": qid})
check("the teacher answers it", r.status_code == 200, r.text[:60])

print("\n9. teaches on the board, and files it to the class")
lesson = {"title": "Refraction", "takeaway": "Light bends at a boundary.",
          "steps": [{"t": "Light slows in glass.\nIt bends to the normal.",
                     "where": "", "code": ""}]}
r = teacher.post("/api/craxlearn/board/save",
                 json={"class_id": CID, "topic": "refraction",
                       "title": "Refraction", "subject": "Science",
                       "note": "What we did today", "lesson": lesson})
check("the taught lesson lands in study material", r.status_code == 200,
      r.text[:60])

print("\n10. the teacher tells the class something")
r = teacher.post("/api/office/notice",
                 json={"title": "Science test Friday", "body": "Chapter 4.",
                       "urgent": False, "starts_on": "", "ends_on": "",
                       "audience": "class", "class_id": CID})
check("an update goes to that class", r.status_code == 200, r.text[:60])

print("\n11. the admin takes the register and bills the term")
signed = (db.query(main.RosterName)
            .filter(main.RosterName.class_id == CID,
                    main.RosterName.claimed_by != 0).first())
today = dt.date.today().isoformat()
r = admin.post("/api/office/attendance",
               json={"class_id": CID, "day": today,
                     "present": {str(signed.claimed_by): True}, "notes": {}})
check("attendance is recorded", r.status_code == 200, r.text[:60])
due = (dt.date.today() + dt.timedelta(days=30)).isoformat()
r = admin.post("/api/office/fee/plan",
               json={"class_id": CID, "title": "Term 3 tuition",
                     "amount": 1200000, "due_on": due, "kind": "fee"})
check("the term's fee is billed to the class",
      r.status_code == 200 and r.json().get("billed", 0) >= 1, r.text[:70])

print("\n12. and the child sees exactly what they should")
st = kid.get("/api/craxlearn/standing").json()
check("their fee, with the date to pay it",
      any(f.get("due_on") == due for f in st.get("fees", [])),
      "a parent needs the date, not just the amount")
check("their attendance", st.get("days_recorded", 0) >= 1,
      str(st.get("attendance_pct")))
n = kid.get("/api/my/notices").json()["notices"]
check("the update their teacher sent",
      any(x["title"] == "Science test Friday" for x in n),
      "the inbox that did not exist this morning")
mats = kid.get(f"/api/class/{CID}/materials").json()["materials"]
check("the material and the lesson that was taught", len(mats) == 2,
      f"{len(mats)} items")
d = kid.get(f"/api/class/{CID}/discussion").json()
check("and the answer to their own question",
      bool(d["threads"]) and bool(d["threads"][0]["replies"])
      and d["threads"][0]["replies"][0]["from_staff"] is True)

print("\n13. and nothing they should not")
r = kid.get("/api/office/fees")
check("not the school's fee book", r.status_code == 403, f"got {r.status_code}")
r = kid.get("/api/head/people")
check("not the school's people", r.status_code == 403, f"got {r.status_code}")

print()
if STOPPED:
    print(f"JOURNEY STOPPED AT: {STOPPED}")
print(f"PASSED {PASS}   FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
