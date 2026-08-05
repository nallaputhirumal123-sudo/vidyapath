"""From the board to the class and back: assignments, submissions, review.

The claim being tested is that nothing in this loop needs a person to
remember a step. A teacher sets what is on the board; it is on the students'
home screen with no publish. A student hands it in; it is in the teacher's
queue with no notification to configure. The teacher marks it; the student
sees the verdict. Every one of those is asserted by asking the API the way
each side's page asks it, not by reading a row back out of the table it was
written to.

The two that actually go wrong in classroom software, and are pinned here:

**A resubmission after review is waiting again.** A teacher who read version
one has not read version two. Treating "reviewed_at is set" as done makes a
student's second attempt vanish from the queue, and nobody finds out until
the student asks why they were marked on the wrong work.

**A teacher only ever sees their own classes.** The queue is the one screen
that reaches across classes, which makes it the one screen where a scoping
mistake shows somebody another school's children by name.
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


def account(tag):
    c = TestClient(main.app)
    email = f"cw{tag}{stamp}@example.com"
    r = c.post("/api/auth/signup", json={"name": f"Person {tag}",
                                         "email": email,
                                         "password": "ClassworkPass123!"})
    assert r.status_code == 200, r.text
    u = db.query(main.User).filter(main.User.email == email).first()
    u.dob = dt.date(1990, 1, 1)
    db.commit()
    return c, u


# A school, a head teacher who owns a class, two students in it — and a
# second school entirely, which must stay invisible.
print("\nSetting up")
school = main.School(name=f"Bridge School {stamp}", city="Chennai",
                     country="India", product="craxlearn")
other = main.School(name=f"Far School {stamp}", city="Delhi",
                    country="India", product="craxlearn")
db.add_all([school, other])
db.commit()

head_c, head_u = account("head")
db.add(main.TeacherAccess(user_id=head_u.id, school=school.name,
                          school_id=school.id, role="head"))
db.commit()

klass = main.Klass(name="9-A", join_code=f"CW{stamp}"[:16],
                   teacher_id=head_u.id, school=school.name,
                   school_id=school.id)
db.add(klass)
db.commit()

s1_c, s1_u = account("s1")
s2_c, s2_u = account("s2")
for u in (s1_u, s2_u):
    db.add(main.ClassMember(class_id=klass.id, user_id=u.id))
db.commit()

# The other school's teacher and their own class, for the scoping check.
far_c, far_u = account("far")
db.add(main.TeacherAccess(user_id=far_u.id, school=other.name,
                          school_id=other.id, role="head"))
db.commit()
far_class = main.Klass(name="9-A", join_code=f"FR{stamp}"[:16],
                       teacher_id=far_u.id, school=other.name,
                       school_id=other.id)
db.add(far_class)
db.commit()

check("the class exists with two students",
      db.query(main.ClassMember).filter(
          main.ClassMember.class_id == klass.id).count() == 2)

# ---- the teacher sets what is on the board ------------------------------
print("\nFrom the board")
LESSON = {
    "title": "Osmosis",
    "steps": [
        {"t": "Water moves from where there is more of it to where there is\n"
              "less, across a membrane that lets water through and not the\n"
              "solute.", "where": "", "code": ""},
        {"t": "The pressure that would stop it is the osmotic pressure.",
         "where": "Bench", "code": "pi = i * M * R * T"},
    ],
    "takeaway": "Water follows solute.",
}
r = head_c.post("/api/craxlearn/board/assign", json={
    "class_id": klass.id, "topic": "osmosis", "title": "Osmosis",
    "subject": "Science", "due_date": "2026-09-01",
    "task": "Answer the three questions below.", "lesson": LESSON})
check("the board sets it for the class", r.status_code == 200, r.text[:200])
made = r.json()
aid = made["assignment"]["id"]
check("and says how many it reached", made.get("students") == 2,
      str(made.get("students")))
check("it remembers the board topic",
      made["assignment"].get("board_topic") == "osmosis",
      str(made["assignment"]))

body = made["assignment"]["body"]
check("the lesson is in the assignment, not just the instruction",
      "osmotic pressure" in body, body[:120])
check("the teacher's own instruction is at the top",
      body.startswith("Answer the three questions"), body[:60])
check("and the takeaway is at the bottom", "Water follows solute" in body)
check("the worked line came with it", "pi = i * M * R * T" in body)

r = head_c.post("/api/craxlearn/board/assign", json={
    "class_id": klass.id, "topic": "nothing", "lesson": {}, "task": ""})
check("an empty board sets nothing", r.status_code == 400, str(r.status_code))

r = far_c.post("/api/craxlearn/board/assign", json={
    "class_id": klass.id, "topic": "osmosis", "lesson": LESSON})
check("another school's teacher cannot set work for this class",
      r.status_code in (403, 404), str(r.status_code))

# ---- it is on the students' page, with nobody publishing anything -------
print("\nOn the students' page")
mine = s1_c.get("/api/class/mine").json()
got = [a for c in mine["classes"] for a in c["assignments"] if a["id"] == aid]
check("the student sees it without anything being published", len(got) == 1,
      str(mine)[:200])
check("and it is not done yet", got and got[0]["done"] is False)
check("and not reviewed", got and got[0]["reviewed"] is False)

d = s1_c.get(f"/api/assignment/{aid}").json()
check("the detail carries the lesson", "osmotic pressure" in d["body"])
check("and the topic to be taught it again",
      d.get("board_topic") == "osmosis", str(d.get("board_topic")))
check("with no feedback yet", d.get("feedback") == "" and
      d.get("reviewed_at") is None, str(d.get("feedback")))

r = far_c.get(f"/api/assignment/{aid}")
check("somebody outside the class cannot read it",
      r.status_code == 403, str(r.status_code))

# ---- the teacher's queue -------------------------------------------------
print("\nThe teacher's queue")
q = head_c.get("/api/teacher/inbox").json()
check("nothing is waiting before anybody hands in",
      q.get("total") == 0, str(q))

r = s1_c.post(f"/api/assignment/{aid}/submit",
              json={"response": "Water moves to the salty side."})
check("a student hands it in", r.status_code == 200, r.text[:120])

q = head_c.get("/api/teacher/inbox").json()
check("it is in the teacher's queue at once", q.get("total") == 1, str(q))
w = q["waiting"][0]
check("naming the student", w["student"] == s1_u.name, str(w))
check("the assignment", w["assignment_id"] == aid)
check("and the class", w["class_name"] == "9-A")
check("and it is not a resubmission yet", w["resubmitted"] is False)

check("the other student is not in the queue",
      all(x["student_id"] != s2_u.id for x in q["waiting"]), str(q))

# The scoping check that matters most: this queue reaches across classes.
far_q = far_c.get("/api/teacher/inbox").json()
check("another school's teacher sees none of it",
      far_q.get("total") == 0, str(far_q))
check("and none of its children by name",
      not any(x["student"] in (s1_u.name, s2_u.name)
              for x in far_q.get("waiting") or []), str(far_q))

r = s1_c.get("/api/teacher/inbox")
check("a student cannot open the queue at all",
      r.status_code == 403, str(r.status_code))

# ---- reviewing it --------------------------------------------------------
print("\nReviewing")
r = head_c.post(f"/api/teacher/submission/{aid}/{s1_u.id}/review",
                json={"feedback": "Right idea. Name the membrane next time."})
check("the teacher marks it", r.status_code == 200, r.text[:120])

q = head_c.get("/api/teacher/inbox").json()
check("and the queue empties", q.get("total") == 0, str(q))
check("and counts it as reviewed", q.get("reviewed") == 1, str(q))

d = s1_c.get(f"/api/assignment/{aid}").json()
check("the student sees the verdict",
      d.get("feedback") == "Right idea. Name the membrane next time.",
      str(d.get("feedback")))
check("and when it was marked", bool(d.get("reviewed_at")))

mine = s1_c.get("/api/class/mine").json()
got = [a for c in mine["classes"] for a in c["assignments"] if a["id"] == aid]
check("the class list shows it marked, without opening it",
      got and got[0]["reviewed"] is True, str(got))

# Marking with nothing to say is a real outcome, not a gap.
s2_c.post(f"/api/assignment/{aid}/submit", json={"response": "Done."})
r = head_c.post(f"/api/teacher/submission/{aid}/{s2_u.id}/review",
                json={"feedback": ""})
check("a teacher may mark it seen with no comment", r.status_code == 200)
check("and the queue is empty again",
      head_c.get("/api/teacher/inbox").json().get("total") == 0)

r = head_c.post(f"/api/teacher/submission/{aid}/999999/review",
                json={"feedback": "x"})
check("marking somebody who has not handed in is refused",
      r.status_code == 404, str(r.status_code))

r = far_c.post(f"/api/teacher/submission/{aid}/{s1_u.id}/review",
               json={"feedback": "not mine to mark"})
check("another school's teacher cannot mark this work",
      r.status_code in (403, 404), str(r.status_code))

# ---- the one that quietly loses a student's second attempt --------------
print("\nHanding it in again")
# The submission's updated_at must move past reviewed_at for this to mean
# anything, and both are set by the server within the same second.
sub = (db.query(main.Submission)
         .filter(main.Submission.assignment_id == aid,
                 main.Submission.user_id == s1_u.id).first())
db.refresh(sub)
sub.reviewed_at = main.now() - dt.timedelta(minutes=5)
db.commit()

r = s1_c.post(f"/api/assignment/{aid}/submit",
              json={"response": "Water moves across a partially permeable "
                                "membrane to the salty side."})
check("the student hands it in again", r.status_code == 200)

q = head_c.get("/api/teacher/inbox").json()
check("reviewed work that changed is waiting again",
      q.get("total") == 1, str(q))
check("and is flagged as a resubmission",
      q["waiting"][0].get("resubmitted") is True, str(q["waiting"][0]))

subs = head_c.get(f"/api/teacher/assignment/{aid}/submissions").json()
row = [s for s in subs["students"] if s["id"] == s1_u.id][0]
check("the review screen agrees it is not reviewed",
      row["reviewed"] is False and row["resubmitted"] is True, str(row))
check("and shows the new answer",
      "partially permeable" in row["response"], row["response"][:60])
check("with the earlier feedback still there",
      "Name the membrane" in row["feedback"], row["feedback"][:60])
check("unreviewed work sorts to the top",
      subs["students"][0]["id"] == s1_u.id, str(subs["students"][0]))

db.close()
print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
