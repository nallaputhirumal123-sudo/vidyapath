"""A teacher sees their own classes' learners, and nobody else's.

This is the one that gets a school into trouble if it is wrong. A teacher
asking after a child they teach is ordinary; the same request for a child in
another teacher's class — or another school — must be refused, and refused
rather than filtered, so there is no version that returns half a record and
reads like an answer.

The rule is the CLASSROOM, not the school. A subject teacher may teach in
several rooms and sees those; a head sees their school because they are
responsible for it. Every check below is a teacher who is real, signed in,
and at the right school, asking about the wrong child.

Two lookups exist and both go through the same rule:

  by id      /api/teacher/student/{uid}
  by code    /api/teacher/student-by-code — which answers "no learner of
             yours has that id" for a code that exists elsewhere, because
             "exists but not yours" is still a fact about somebody's child.

Also here: the calculator, which is the one input box in a room full of
teenagers who have just been taught what a sandbox is.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"   # local test database; refused on a deployment
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"

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

school = main.School(name=f"Roll School {stamp}", city="Nagpur",
                     country="India", product="craxlearn")
far = main.School(name=f"Far Roll {stamp}", city="Bhopal",
                  country="India", product="craxlearn")
db.add_all([school, far])
db.commit()


def person(tag, role=None, sch=None):
    c = TestClient(main.app)
    email = f"rl{tag}{stamp}@example.com"
    r = c.post("/api/auth/signup", json={"name": f"Person {tag}",
                                         "email": email,
                                         "password": "RollPass123!"})
    assert r.status_code == 200, r.text
    u = db.query(main.User).filter(main.User.email == email).first()
    if role:
        db.add(main.TeacherAccess(user_id=u.id, school=sch.name,
                                  school_id=sch.id, role=role))
        db.commit()
    return c, u


head, head_u = person("head", "head", school)
mine_t, mine_u = person("mine", "teacher", school)     # teaches 6-A and 6-B
other_t, other_u = person("other", "teacher", school)  # teaches 6-C only
far_t, far_u = person("far", "teacher", far)

# Two rooms for one teacher — "she can join multiple classrooms to teach".
a = main.Klass(name="6-A", join_code=f"RA{stamp}"[:16], teacher_id=head_u.id,
               school=school.name, school_id=school.id)
b = main.Klass(name="6-B", join_code=f"RB{stamp}"[:16], teacher_id=head_u.id,
               school=school.name, school_id=school.id)
c_ = main.Klass(name="6-C", join_code=f"RC{stamp}"[:16], teacher_id=head_u.id,
                school=school.name, school_id=school.id)
db.add_all([a, b, c_])
db.commit()
for k, t in ((a, mine_u), (b, mine_u), (c_, other_u)):
    db.add(main.SubjectSlot(class_id=k.id, subject="Science",
                            code=f"S{k.id}{stamp}"[:12], teacher_id=t.id,
                            status="claimed"))
db.commit()

# Learners, enrolled by the head, with the school's own ids.
pupils = {}
for tag, k in (("p1", a), ("p2", b), ("p3", c_)):
    _c, u = person(tag)
    db.add(main.ClassMember(class_id=k.id, user_id=u.id))
    db.add(main.RosterName(class_id=k.id, name=u.name,
                           student_code=f"{tag.upper()}-{stamp}",
                           claimed_by=u.id, claimed_at=main.now()))
    pupils[tag] = u
db.commit()

# ---- a teacher's own rooms ---------------------------------------------
print("\nYour own classrooms")
d = mine_t.get("/api/teacher/roll").json()
names = sorted(k["name"] for k in d["classes"])
check("a teacher sees every room they teach in", names == ["6-A", "6-B"],
      str(names))
check("and not the one they do not", "6-C" not in names, str(names))
check("with the learners in them",
      sorted(s["name"] for k in d["classes"] for s in k["students"])
      == sorted([pupils["p1"].name, pupils["p2"].name]),
      str([s["name"] for k in d["classes"] for s in k["students"]]))
check("and the school's own id beside each",
      all(s["student_code"] for k in d["classes"] for s in k["students"]),
      str([s["student_code"] for k in d["classes"] for s in k["students"]]))
check("and their subject in that room",
      all(k["my_subjects"] == ["Science"] for k in d["classes"]),
      str([k["my_subjects"] for k in d["classes"]]))

other_d = other_t.get("/api/teacher/roll").json()
check("the other teacher sees only theirs",
      [k["name"] for k in other_d["classes"]] == ["6-C"],
      str([k["name"] for k in other_d["classes"]]))

head_d = head.get("/api/teacher/roll").json()
check("a head sees the whole school",
      sorted(k["name"] for k in head_d["classes"]) == ["6-A", "6-B", "6-C"],
      str([k["name"] for k in head_d["classes"]]))

far_d = far_t.get("/api/teacher/roll").json()
check("another school's teacher sees nothing here",
      not far_d["classes"], str(far_d))

# ---- one learner's progress --------------------------------------------
print("\nOne learner")
r = mine_t.get(f"/api/teacher/student/{pupils['p1'].id}")
check("a teacher can open a learner they teach", r.status_code == 200,
      str(r.status_code))
prog = r.json()
check("with everything on one screen",
      all(k in prog for k in ("attendance_pct", "lessons_completed", "learnt",
                              "searched", "exams", "handed_in")),
      str(sorted(prog)))
check("and the room they are in",
      [k["name"] for k in prog["classes"]] == ["6-A"], str(prog["classes"]))

# The refusals. Every one of these is a real teacher at the right school.
r = mine_t.get(f"/api/teacher/student/{pupils['p3'].id}")
check("but not a learner in another teacher's room",
      r.status_code == 403, str(r.status_code))
check("and told so plainly",
      "not in any of your classes" in r.json().get("detail", ""),
      r.text[:140])

r = other_t.get(f"/api/teacher/student/{pupils['p1'].id}")
check("and not the other way round either", r.status_code == 403,
      str(r.status_code))
r = far_t.get(f"/api/teacher/student/{pupils['p1'].id}")
check("nor another school's teacher", r.status_code == 403, str(r.status_code))
r = head.get(f"/api/teacher/student/{pupils['p3'].id}")
check("the head can, across their own school", r.status_code == 200,
      str(r.status_code))

learner_c = TestClient(main.app)
learner_c.post("/api/auth/login", json={"email": pupils["p1"].email,
                                        "password": "RollPass123!"})
check("a learner cannot open another learner",
      learner_c.get(f"/api/teacher/student/{pupils['p2'].id}").status_code == 403)
check("nor themselves through the teacher route",
      learner_c.get(f"/api/teacher/student/{pupils['p1'].id}").status_code == 403)

# ---- looking one up by the school's own id -----------------------------
print("\nBy student id")
mine_code = f"P1-{stamp}"
r = mine_t.get(f"/api/teacher/student-by-code?code={mine_code}")
check("a teacher can find their own learner by id", r.status_code == 200,
      str(r.status_code))
check("and it is the right child",
      r.json()["student"]["user_id"] == pupils["p1"].id, r.text[:120])
check("case does not matter",
      mine_t.get(f"/api/teacher/student-by-code?code={mine_code.lower()}")
      .status_code == 200)

# The important one. P3-… is a real id at this school and this teacher must
# be told it does not exist, not that it exists and is off limits.
r = mine_t.get(f"/api/teacher/student-by-code?code=P3-{stamp}")
check("a real id from another room reads as not found",
      r.status_code == 404, str(r.status_code))
check("and says nothing about whose it is",
      "not allowed" not in r.text.lower()
      and "another" not in r.text.lower(), r.text[:140])
check("an id nobody has is the same answer",
      mine_t.get("/api/teacher/student-by-code?code=ZZZZ").status_code == 404)
check("a learner cannot use the lookup at all",
      learner_c.get(f"/api/teacher/student-by-code?code={mine_code}")
      .status_code == 403)

# ---- the register takes the id alongside the name ----------------------
print("\nThe register with ids")
r = head.post(f"/api/teacher/class/{a.id}/roster",
              json={"names": "Neha Iyer, 6A-021\nRahul Das\n"})
check("names and ids go in together", r.status_code == 200, r.text[:150])
got = {x["name"]: x["student_code"] for x in r.json()["roster"]}
check("the id is kept", got.get("Neha Iyer") == "6A-021", str(got))
check("and a name without one is still a name",
      "Rahul Das" in got and got["Rahul Das"] == "", str(got))

# ---- the calculator -----------------------------------------------------
print("\nThe calculator")
for expr, want in [("6*2", "12"), ("2^10", "1024"), ("(3+4)*2", "14"),
                   ("sqrt(144)", "12"), ("10/4", "2.5")]:
    r = mine_t.post("/api/craxlearn/calc", json={"expression": expr})
    check(f"{expr} = {want}", r.status_code == 200
          and r.json()["result"] == want,
          r.text[:120])

check("a whole number does not come back as 12.0",
      mine_t.post("/api/craxlearn/calc",
                  json={"expression": "6*2"}).json()["result"] == "12")

# The reason this goes to the server's allowlisted evaluator instead of eval.
for bad in ("__import__('os').system('ls')", "open('/etc/passwd')",
            "[x for x in range(10)]", "1).__class__", "exit()",
            "eval('2+2')", "globals()"):
    r = mine_t.post("/api/craxlearn/calc", json={"expression": bad})
    check(f"{bad[:24]!r} is refused", r.status_code == 400, str(r.status_code))

check("and it needs a signed-in account",
      TestClient(main.app).post("/api/craxlearn/calc",
                                json={"expression": "1+1"}).status_code == 401)

# ---- PhET, structures and the source search ----------------------------
# These reach public catalogues, which a build machine may not be able to.
# So what is asserted is the SHAPE and the honest failure: a list that could
# not be verified comes back empty with a reason, never as a wall of frames
# that will not load in front of a class.
print("\nOutside sources")
import craxlearn as cl                             # noqa: E402

check("there are simulations to offer", len(cl.phet_candidates()) >= 12,
      str(len(cl.phet_candidates())))
check("each has an id, a title and a subject",
      all(x["id"] and x["title"] and x["subject"]
          for x in cl.phet_candidates()))
check("and a URL built to PhET's own shape",
      all(x["url"].startswith("https://phet.colorado.edu/sims/html/")
          and x["url"].endswith("_en.html") for x in cl.phet_candidates()))
check("filtering by subject works",
      all(x["subject"] == "Physics"
          for x in cl.phet_candidates("physics"))
      and len(cl.phet_candidates("physics")) >= 4,
      str(len(cl.phet_candidates("physics"))))
check("PhET is in the source registry as open",
      any(x["id"] == "phet" and x["open"] and x["role"] == "sourcing"
          for x in cl.SOURCES))

r = mine_t.get("/api/craxlearn/phet")
check("the endpoint answers", r.status_code == 200, str(r.status_code))
d = r.json()
check("with only sims that were actually reached",
      all(x["url"].startswith("https://phet.colorado.edu/")
          for x in d["sims"]), str(d)[:200])
check("and says so plainly when none could be",
      bool(d["sims"]) or "could not be reached" in d.get("note", "")
      or "answered" in d.get("note", ""), str(d)[:200])
check("it names the licence", "CC BY" in d.get("licence", ""),
      d.get("licence", ""))
check("and it needs an account",
      TestClient(main.app).get("/api/craxlearn/phet").status_code == 401)

# A structure that resolves from a table in this repository, with no network.
r = mine_t.get("/api/craxlearn/structure?name=silicon")
check("a measured structure comes back", r.status_code == 200, r.text[:150])
check("as a scene the renderer understands",
      r.json()["scene"]["kind"] in ("lattice", "molecule", "protein",
                                    "layers", "orbit"),
      str(r.json()["scene"].get("kind")))
r = mine_t.get("/api/craxlearn/structure?name=graphene")
check("and so does a layer stack",
      r.status_code == 200 and r.json()["scene"]["kind"] == "layers",
      r.text[:120])

# The refusal that matters: nothing measured means nothing shown, not a
# plausible arrangement of spheres with a real name under it.
r = mine_t.get("/api/craxlearn/structure?name=zzqqxx-not-a-thing")
check("a name with nothing behind it shows nothing", r.status_code == 404,
      str(r.status_code))
check("and says why rather than drawing a guess",
      "never a drawing of what it might be" in r.text, r.text[:200])
check("a one-letter name is refused",
      mine_t.get("/api/craxlearn/structure?name=x").status_code == 400)

r = mine_t.get("/api/craxlearn/search?q=silicon")
check("the source search answers", r.status_code == 200, str(r.status_code))
check("naming which catalogues it used",
      len(r.json().get("sources") or []) >= 5, str(r.json().get("sources")))

db.close()
print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
