"""Craxlearn on its own: what a school can reach, and what it cannot.

A school is buying a URL it can put on the board at the front of a room and
hand to a fourteen-year-old. The promise is that there is no job board on it
— not hidden, not behind a flag, not one bug away. A promise like that is
worth exactly what its tests are worth, because the person who finds the hole
is a child and the way you find out is a complaint.

So this asserts refusals, and it asserts them at the door rather than in the
sidebar. Hiding a menu item stops nobody who can type a URL, and every check
below goes straight to the API the way somebody typing a URL would.

Five walls, and they fail in different directions on purpose:

  deployment   CRAXLEARN_ONLY on the server. The job half does not exist,
               for anybody, including an admin.
  classcode    a login with no adult behind it. Nothing reopens it.
  staff        a work account the school issued. Not the school's to open
               either: a school buying the job board buys it for its
               learners, not for its teachers.
  institution  the school ASKED for it to be shut. Opt-out, not opt-in: a
               school is not a reason to hide work from an eighteen-year-old,
               and a Class 12 student applying for their first job is the
               point of having built it. A school that wants none of it on
               its premises sets the switch and gets exactly that.
  age          under 18. Not the institution's to waive, ever.

So the job half is shut to a class-code login and to staff always, to anybody
under 18 always, and to a whole institution only when that institution has
asked for it.

The last test is the one that catches tomorrow's mistake: it walks the live
route table and fails if a route has appeared that belongs to neither half.
A new job-side endpoint added next month is covered by being named like its
neighbours — and if it is not, this goes red rather than quietly opening.
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

import craxlearn as cl                             # noqa: E402
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


# ---- ages ---------------------------------------------------------------
print("\nAge")
TODAY = dt.date(2026, 8, 4)
check("a birthday later this year has not happened",
      cl.age_on(dt.date(2008, 12, 25), TODAY) == 17,
      str(cl.age_on(dt.date(2008, 12, 25), TODAY)))
check("a birthday earlier this year has",
      cl.age_on(dt.date(2008, 1, 2), TODAY) == 18)
check("a birthday today counts", cl.age_on(dt.date(2008, 8, 4), TODAY) == 18)
check("the day before does not",
      cl.age_on(dt.date(2008, 8, 5), TODAY) == 17)
check("eighteen today is an adult", cl.adult(dt.date(2008, 8, 4), TODAY))
check("one day short is not", not cl.adult(dt.date(2008, 8, 5), TODAY))
check("an unknown birthday is NOT an adult", not cl.adult(None, TODAY))
check("and never rounds up", not cl.adult(dt.date(2009, 1, 1), TODAY))

# ---- which half a route belongs to --------------------------------------
print("\nSides")
for p in ("/api/jobs", "/api/jobs/categories", "/api/career/roles",
          "/api/resume/ai", "/api/billing/me", "/api/hire/search",
          "/api/interview/guide", "/api/apply/profile", "/api/invites/unread",
          "/api/me/open-to-work", "/api/employer/apply"):
    check(f"{p} is the job board", cl.is_job_side(p))
for p in ("/api/ask/talk", "/api/board/lesson", "/api/net/trace", "/api/lab",
          "/api/sql/board", "/api/curriculum", "/api/craxlearn/sources",
          "/api/craxlearn/me", "/api/class/join", "/api/progress",
          "/api/auth/me", "/api/scan"):
    check(f"{p} is teaching", not cl.is_job_side(p))

# The matching is greedy on purpose, and this pins that rather than leaving
# it to be discovered. A route named next to a job-side one is treated as
# job-side, because closing something a school was never promised is a
# complaint and opening the job board to a child is not.
check("a name beside a job-side one is treated as job-side",
      cl.is_job_side("/api/careers-advice"))
check("and a teaching route beside none of them is not",
      not cl.is_job_side("/api/craxlearn/activity"))
# The one that would actually be a bug: a teaching prefix must never be a
# substring away from being blocked.
for p in ("/api/craxlearn/me", "/api/class/mine", "/api/curriculum",
          "/api/course", "/api/scan/recent"):
    check(f"{p} survives the greedy match", not cl.is_job_side(p))

# ---- the three walls, end to end ----------------------------------------
print("\nThe walls")
main.Base.metadata.create_all(bind=main.engine)
main.send_email = lambda *a, **k: None
stamp = int(time.time())
db = main.SessionLocal()

# A school that asked for the job board to be switched off, and a coaching
# centre on the default. The default is ON for over-18 learners: a school is
# not a reason to hide work from an eighteen-year-old, and it is opt-OUT so
# that a school which does want it hidden gets exactly that.
school = main.School(name=f"Ridge School {stamp}", city="Pune",
                     country="India", product="learning_only")
centre = main.School(name=f"Apex Coaching {stamp}", city="Pune",
                     country="India", product="both")
db.add_all([school, centre])
db.commit()
for sc, code in ((school, f"RG{stamp}"[:16]), (centre, f"AX{stamp}"[:16])):
    db.add(main.Klass(name="Batch 1", join_code=code, teacher_id=1,
                      school=sc.name, school_id=sc.id))
db.commit()


def learner(tag, school_row, dob):
    """A signed-in learner, enrolled where they belong."""
    c = TestClient(main.app)
    email = f"co{tag}{stamp}@example.com"
    r = c.post("/api/auth/signup", json={"name": f"Learner {tag}",
                                         "email": email,
                                         "password": "CraxlearnPass123!"})
    assert r.status_code == 200, r.text
    u = db.query(main.User).filter(main.User.email == email).first()
    u.dob = dob
    u.plan = "pro"
    u.plan_expires = main.now() + dt.timedelta(days=30)
    if school_row is not None:
        k = (db.query(main.Klass)
               .filter(main.Klass.school_id == school_row.id).first())
        db.add(main.ClassMember(class_id=k.id, user_id=u.id))
    db.commit()
    return c, u


ADULT = dt.date(1998, 3, 3)
CHILD = dt.date(2012, 3, 3)

school_adult, _ = learner("sa", school, ADULT)     # 18+, school opted out
school_child, _ = learner("sc", school, CHILD)     # under 18, school opted out
centre_adult, _ = learner("ca", centre, ADULT)     # 18+, centre bought both
centre_child, _ = learner("cc", centre, CHILD)     # under 18 at that centre
public_adult, _ = learner("pa", None, ADULT)       # on their own account
public_none, pu = learner("pn", None, None)        # never said their age

JOB = "/api/jobs?limit=1"

r = school_adult.get(JOB)
check("an adult at a school that switched it off is refused",
      r.status_code == 403, str(r.status_code))
check("and told which wall it was",
      r.json().get("craxlearn") == "institution", str(r.json()))

r = school_child.get(JOB)
check("a child at that school likewise", r.status_code == 403, str(r.status_code))

r = centre_adult.get(JOB)
check("an adult at a centre that bought both gets through",
      r.status_code == 200, str(r.status_code))

r = centre_child.get(JOB)
check("but a child there does not", r.status_code == 403, str(r.status_code))

check("and it is the age wall, which the centre cannot waive",
      r.json().get("craxlearn") == "age", str(r.json()))

# The default, which is the case that matters most and the one nobody sets
# up deliberately: a school that has never touched the switch. Its
# eighteen-year-olds get the job board. Its fourteen-year-olds do not, its
# staff do not, and its class-code logins do not — none of which the school
# has to configure, and none of which it can turn on.
plain = main.School(name=f"Plain School {stamp}", city="Pune",
                    country="India", product="craxlearn")
db.add(plain)
db.commit()
db.add(main.Klass(name="12-A", join_code=f"PL{stamp}"[:16], teacher_id=1,
                  school=plain.name, school_id=plain.id))
db.commit()

plain_adult, _ = learner("da", plain, ADULT)
plain_child, _ = learner("dc", plain, CHILD)
plain_none, _ = learner("dn", plain, None)
plain_staff, staff_u = learner("ds", plain, ADULT)
db.add(main.TeacherAccess(user_id=staff_u.id, school=plain.name,
                          school_id=plain.id, role="teacher"))
plain_code, code_u = learner("dk", plain, ADULT)
code_u.kind = "classcode"
db.commit()

r = plain_adult.get(JOB)
check("an 18-year-old at an ordinary school REACHES the job board",
      r.status_code == 200, str(r.status_code))

r = plain_child.get(JOB)
check("a 14-year-old at the same school does not", r.status_code == 403,
      str(r.status_code))
check("and it is the age wall, not the school's",
      r.json().get("craxlearn") == "age", str(r.json().get("craxlearn")))

r = plain_none.get(JOB)
check("nor does one who never said their age — inside a school, silence "
      "is a child", r.status_code == 403, str(r.status_code))

r = plain_staff.get(JOB)
check("nor a teacher there, whatever their age", r.status_code == 403,
      str(r.status_code))
check("and it is the staff wall", r.json().get("craxlearn") == "staff",
      str(r.json().get("craxlearn")))

r = plain_code.get(JOB)
check("nor a class-code login, even one stating 18",
      r.status_code == 403, str(r.status_code))
check("and it is the class-code wall",
      r.json().get("craxlearn") == "classcode",
      str(r.json().get("craxlearn")))

# And the switch closes it again, for everybody, without touching anything
# else about the school.
plain.product = "learning_only"
db.commit()
r = plain_adult.get(JOB)
check("the school can switch it off and the same adult is refused",
      r.status_code == 403, str(r.status_code))
check("with the institution named as the reason",
      r.json().get("craxlearn") == "institution",
      str(r.json().get("craxlearn")))
plain.product = "craxlearn"
db.commit()
r = plain_adult.get(JOB)
check("and switching it back on restores them", r.status_code == 200,
      str(r.status_code))

r = public_adult.get(JOB)
check("somebody on their own account, over 18, gets through",
      r.status_code == 200, str(r.status_code))

# Silence used to keep what it had, outside an institution. REQUIRE_DOB is on
# now, and this is the half of the rule that changed: an account that has never
# said how old it is has not told us it is an adult, and the job board, being
# shown to employers and buying a subscription are for adults.
#
# The cost the old comment warned about is real and is paid deliberately —
# every existing account without a date loses the job half until it fills one
# in. What is NOT paid is somebody's own billing page: it stays reachable, so a
# subscriber can still cancel what they bought. That is asserted just below and
# in test_dob_gate.
r = public_none.get(JOB)
check("somebody who never gave a birthday is now asked for one",
      r.status_code == 403, str(r.status_code))
check("and told that is why, rather than that they are a child",
      r.json().get("craxlearn") == "dob_missing", str(r.json())[:90])
check("while their own billing stays open",
      public_none.get("/api/billing/me").status_code == 200,
      "a subscriber locked out of cancelling has been trapped, not protected")

# But a stated age is believed in both directions, even outside one.
_, pu_child = learner("pc", None, CHILD)
child_pub = TestClient(main.app)
child_pub.post("/api/auth/login", json={"email": pu_child.email,
                                        "password": "CraxlearnPass123!"})
r = child_pub.get(JOB)
check("and somebody who says they are twelve is refused anyway",
      r.status_code == 403, str(r.status_code))
check("on age", r.json().get("craxlearn") == "age", str(r.json()))

# Inside an institution there is no silence to keep: an empty field is a
# teenager until it says otherwise. Already covered above by school_child,
# and pinned here as the rule rather than as a side effect.
check("an institution learner always needs a stated age",
      not cl.age_ok(None, TODAY, proof_required=True))
check("and outside one, silence is allowed",
      cl.age_ok(None, TODAY, proof_required=False))
check("a stated age under 18 is refused either way",
      not cl.age_ok(CHILD, TODAY, proof_required=False)
      and not cl.age_ok(CHILD, TODAY, proof_required=True))
check("and over 18 is allowed either way",
      cl.age_ok(ADULT, TODAY, proof_required=False)
      and cl.age_ok(ADULT, TODAY, proof_required=True))

# The deployment switch, now on by default. It used to be off, so this checked
# that turning it on closed the silence; the interesting direction now is the
# other one — that turning it OFF gives an account with no birthday its access
# back, because that is the escape hatch a deployment with a support queue and
# no appetite for this would reach for.
was_dob = main.REQUIRE_DOB
check("REQUIRE_DOB closes the silence", was_dob
      and public_none.get(JOB).status_code == 403,
      str(public_none.get(JOB).status_code))
main.REQUIRE_DOB = False
try:
    check("and switching it off restores them",
          public_none.get(JOB).status_code == 200,
          str(public_none.get(JOB).status_code))
finally:
    main.REQUIRE_DOB = was_dob

# ---- staff never see the job board, whatever the school bought ----------
# A teacher account is a work account the school issued. A school that buys
# the job board buys it for its learners; its staff are not part of that,
# and the job board arriving inside the tool an employer handed somebody to
# teach with — on the same screen as the register — is the thing this stops.
print("\nStaff accounts")


def staff(tag, role, school_row, dob=ADULT):
    c = TestClient(main.app)
    email = f"st{tag}{stamp}@example.com"
    r = c.post("/api/auth/signup", json={"name": f"Staff {tag}",
                                         "email": email,
                                         "password": "CraxlearnPass123!"})
    assert r.status_code == 200, r.text
    u = db.query(main.User).filter(main.User.email == email).first()
    u.dob = dob
    u.plan = "pro"
    u.plan_expires = main.now() + dt.timedelta(days=30)
    db.add(main.TeacherAccess(user_id=u.id, school=school_row.name,
                              school_id=school_row.id, role=role))
    db.commit()
    return c, u


# At the coaching centre that DID buy the job board — the case that used to
# get through, and the reason this section exists.
for role in ("teacher", "head", "schooladmin"):
    c, _ = staff(role, role, centre)
    r = c.get(JOB)
    check(f"a {role} at a centre that bought both is still refused",
          r.status_code == 403, str(r.status_code))
    check(f"and told it is the account, not the school",
          r.json().get("craxlearn") == "staff", r.text[:120])

# And at a Craxlearn-only school, for completeness.
c, _ = staff("t2", "teacher", school)
check("a teacher at a Craxlearn-only school likewise",
      c.get(JOB).status_code == 403, str(c.get(JOB).status_code))

# The teaching half is untouched — this closes one half, not the account.
check("but their teaching tools all work",
      all(c.get(p_).status_code == 200
          for p_ in ("/api/curriculum", "/api/craxlearn/me",
                     "/api/teacher/roll", "/api/net")),
      "")

# An ordinary personal account, over 18, not attached to a school: the only
# kind that reaches the job half at all.
check("only a personal account gets through",
      public_adult.get(JOB).status_code == 200,
      str(public_adult.get(JOB).status_code))

# Every job-side surface, not just the one endpoint.
print("\nEvery job-side surface")
for path in ("/api/jobs?limit=1", "/api/career/roles", "/api/billing/me",
             "/api/interview/guide?role=network", "/api/me/invites",
             "/api/apply/profile", "/api/resume/extract"):
    r = school_child.get(path)
    check(f"school learner refused {path.split('?')[0]}",
          r.status_code in (403, 405), str(r.status_code))

# And the teaching half is untouched, which is the whole point of the split.
print("\nThe teaching half still works")
for path in ("/api/curriculum", "/api/net", "/api/lab", "/api/sql/board",
             "/api/craxlearn/me", "/api/craxlearn/sources", "/api/auth/me"):
    r = school_child.get(path)
    check(f"school learner can reach {path}", r.status_code == 200,
          str(r.status_code))

d = school_child.get("/api/craxlearn/me").json()
check("the app is told it is learning-only", d.get("learning_only") is True)
check("and why", d.get("why") == "institution", str(d.get("why")))
check("and which pages not to offer",
      set(d.get("hidden_pages") or []) == set(cl.JOB_PAGES),
      str(d.get("hidden_pages")))
check("and which institution it is",
      (d.get("institution") or {}).get("name") == school.name,
      str(d.get("institution")))
check("a child is not reported as an adult", d.get("adult") is False)

d2 = centre_adult.get("/api/craxlearn/me").json()
check("an adult at a centre that bought both is not learning-only",
      d2.get("learning_only") is False, str(d2))

# /api/auth/me carries the same verdict, so the main app hides the same nav.
d3 = school_child.get("/api/auth/me").json()
check("the main app is told too", d3.get("craxlearn_only") is True)
check("with the same page list",
      set(d3.get("hidden_pages") or []) == set(cl.JOB_PAGES))

# ---- setting a date of birth opens the age wall, not the others ---------
print("\nGiving a date of birth")
r = public_none.post("/api/craxlearn/dob", json={"dob": "1998-03-03"})
check("a date can be given", r.status_code == 200, r.text[:120])
check("and reads back as adult", r.json().get("adult") is True, r.text[:120])
check("which opens the job board",
      public_none.get(JOB).status_code == 200)

r = public_none.post("/api/craxlearn/dob", json={"dob": "2035-01-01"})
check("a date in the future is refused", r.status_code == 400, str(r.status_code))
r = public_none.post("/api/craxlearn/dob", json={"dob": "not a date"})
check("and so is nonsense", r.status_code == 400, str(r.status_code))

r = school_adult.post("/api/craxlearn/dob", json={"dob": "1998-03-03"})
check("a school learner may still record their age", r.status_code == 200)
check("but it does not open their school's job board",
      school_adult.get(JOB).status_code == 403,
      str(school_adult.get(JOB).status_code))

# ---- the deployment switch ----------------------------------------------
# The hardest wall: not this user, not this school — this server.
print("\nA server run by an institution")
was = main.CRAXLEARN_ONLY
main.CRAXLEARN_ONLY = True
try:
    for c, who in ((public_adult, "an adult on their own account"),
                   (centre_adult, "an adult at a centre that bought both")):
        r = c.get(JOB)
        check(f"{who} gets nothing here", r.status_code == 404,
              str(r.status_code))
    check("and the teaching half is untouched",
          public_adult.get("/api/curriculum").status_code == 200)
    r = TestClient(main.app).get("/")
    check("the root serves the institution app",
          r.status_code == 200 and "Craxlearn" in r.text, str(r.status_code))
finally:
    main.CRAXLEARN_ONLY = was

check("and the switch really did go back",
      public_adult.get(JOB).status_code == 200,
      str(public_adult.get(JOB).status_code))

# ---- the page is served and is its own app ------------------------------
print("\nThe institution app")
anon = TestClient(main.app)
r = anon.get("/craxlearn")
check("it is served", r.status_code == 200, str(r.status_code))
page = r.text
check("it is a whole page", page.lstrip().lower().startswith("<!doctype html>"))
check("it names itself", "Craxlearn" in page)
# The point of a separate file. If any of these ever appear here, the school
# is back to running a job board with the job board hidden.
for word in ("/api/jobs", "/api/billing", "/api/resume", "/api/hire",
             "apply-kit", "employer"):
    check(f"no {word!r} anywhere in the institution app", word not in page,
          "found it")

# ---- the route table, so tomorrow's endpoint cannot slip through --------
print("\nEvery route has a side")
# Routes that are neither the job board nor a teaching surface: the ones
# every app needs. Listed by prefix and deliberately short — a new group
# appearing here is a decision somebody has to make on purpose.
NEUTRAL = ("/api/auth", "/api/health", "/api/status", "/api/version",
           "/api/docs", "/api/admin", "/api/ai", "/api/mail",
           "/api/notifications", "/api/note", "/api/recent")
TEACHING = ("/api/ask", "/api/board", "/api/class", "/api/course",
            "/api/craxlearn", "/api/curriculum", "/api/lab", "/api/net",
            "/api/progress", "/api/quiz", "/api/scan", "/api/skills",
            "/api/sql", "/api/assignment", "/api/teacher", "/api/head",
            "/api/material", "/api/office",
            # Added since: the inbox a learner reads their school's updates
            # in, reporting a wrong answer, and turning a teacher's own PDF
            # into a lesson. All three are teaching and none of them touch
            # the job half — which is the thing this test exists to keep
            # true for a school that bought only the teaching product.
            "/api/my/notices", "/api/report", "/api/teach")
unfiled = []
for r_ in main.app.routes:
    p = getattr(r_, "path", "")
    if not p.startswith("/api/"):
        continue
    if cl.is_job_side(p):
        continue
    if any(p.startswith(pre) for pre in NEUTRAL + TEACHING):
        continue
    unfiled.append(p)
check("no route belongs to neither half", not unfiled,
      ", ".join(sorted(unfiled)) or "none")

db.close()
print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
