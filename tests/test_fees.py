"""A fee plan, and a school that can see its own money.

The office could set a fee on a learner and then see that learner. It could not
see the school — how much is outstanding, who is overdue, what falls due next —
and answering that by opening four hundred learners one at a time is why
schools keep this in a spreadsheet instead of in the thing they bought.

Two things pinned:

**A term fee goes on everybody at once.** It is the same number for the whole
class, and setting it one child at a time is how a class of forty gets
thirty-nine and nobody notices until a parent asks why they were not told.

**Running it twice does not bill twice.** That is the mistake that costs a
school its parents rather than an afternoon, so a learner who already has that
title outstanding is skipped.
"""
import os
import sys
import time
import datetime as dt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
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

sc = main.School(name=f"FeeSchool {stamp}")
db.add(sc)
db.commit()
db.refresh(sc)
hc = main._gen_head_code(db)
db.add(main.TeacherCode(code=hc, school=sc.name, school_id=sc.id,
                        is_head=True, active=True))
db.commit()

print("\nthe code a school admin is given")
check("it is ten characters", len(hc) == 10, hc)
check("and all of them digits", hc.isdigit(),
      "every character is on a number pad, which is what a board has")

admin = TestClient(main.app)
em = f"fe{stamp}@example.com"
admin.post("/api/auth/signup",
           json={"name": "Admin", "email": em, "password": "FeePass123!"})
u = db.query(main.User).filter(main.User.email == em).first()
u.dob = dt.date(1990, 1, 1)
db.commit()
r = admin.post("/api/class/join", json={"code": hc})
check("and it signs the admin in", r.status_code == 200, r.text[:60])

CID = admin.post("/api/teacher/class",
                 json={"name": f"6-C {stamp}"}).json()["id"]
admin.post(f"/api/teacher/class/{CID}/roster",
           json={"names": "Ila K\nJai M\nKiran P"})
code = db.get(main.Klass, CID).join_code

main._CODE_TRIES.clear()
main._CODE_FAILS.clear()
kids = []
for i in range(3):
    c = TestClient(main.app)
    free = c.post("/api/craxlearn/code", json={"code": code}).json()["names"]
    if not free:
        break
    c.post("/api/craxlearn/claim",
           json={"code": code, "roster_id": free[0]["id"]})
    kids.append(c)
check("three learners signed in", len(kids) == 3, str(len(kids)))

print("\none fee, put on the whole class")
due = (dt.date.today() + dt.timedelta(days=20)).isoformat()
r = admin.post("/api/office/fee/plan",
               json={"class_id": CID, "title": "Term 2 tuition",
                     "amount": 1500000, "due_on": due, "kind": "fee"})
check("the plan bills every learner", r.status_code == 200
      and r.json()["billed"] == 3, r.text[:80])

r = admin.post("/api/office/fee/plan",
               json={"class_id": CID, "title": "Term 2 tuition",
                     "amount": 1500000, "due_on": due, "kind": "fee"})
check("running it again bills nobody twice",
      r.json()["billed"] == 0 and r.json()["skipped"] == 3, r.text[:80])

print("\nthe school can see its own money")
book = admin.get("/api/office/fees").json()
check("everything outstanding is listed",
      len(book["upcoming"]) == 3, str(len(book["upcoming"])))
check("with the total billed", book["totals"]["billed"] == 4500000,
      str(book["totals"]["billed"]))
check("and nothing collected yet", book["totals"]["collected"] == 0)
check("upcoming is ordered by when it falls due",
      [i["due_on"] for i in book["upcoming"]]
      == sorted(i["due_on"] for i in book["upcoming"]))
check("each row names the learner",
      all(i["who"] for i in book["upcoming"]),
      "an amount with no name attached is not an invoice")

print("\nwhen one is paid")
fid = book["upcoming"][0]["id"]
r = admin.post(f"/api/office/fee/{fid}/paid", json={"paid": 1500000})
check("it can be marked paid", r.status_code == 200, r.text[:60])
book = admin.get("/api/office/fees").json()
check("it leaves the outstanding list", len(book["upcoming"]) == 2)
check("and appears in what came in", len(book["recent"]) == 1)
check("the totals move", book["totals"]["collected"] == 1500000
      and book["totals"]["outstanding"] == 3000000,
      str(book["totals"]))

print("\noverdue is worked out, not typed")
past = (dt.date.today() - dt.timedelta(days=3)).isoformat()
admin.post("/api/office/fee/plan",
           json={"class_id": CID, "title": "Late library fine",
                 "amount": 20000, "due_on": past, "kind": "fee"})
book = admin.get("/api/office/fees").json()
check("a fee past its date reads as overdue",
      any(i["overdue"] for i in book["upcoming"]),
      "a school chasing payments needs this without doing the arithmetic")
check("and one still in the future does not",
      any(not i["overdue"] for i in book["upcoming"]))

print("\nthe learner sees their own dates")
st = kids[1].get("/api/craxlearn/standing").json()
check("their fees carry a due date",
      any(f.get("due_on") for f in st.get("fees", [])),
      "a parent needs the date, not just the amount")

print("\nnobody else sees the book")
r = kids[0].get("/api/office/fees")
check("a learner cannot read the school's fees", r.status_code == 403,
      f"got {r.status_code}")

print(f"\nPASSED {PASS}   FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
