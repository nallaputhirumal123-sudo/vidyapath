"""How a school is wired together, asserted end to end.

The shape being pinned:

    a school (or college, or coaching centre)
      └── a classroom
            ├── ONE roll of students, each in exactly one classroom
            └── several SUBJECTS, each with its own teacher

    a teacher holds subjects in SEVERAL classrooms
    a student holds ONE classroom and is taught several subjects in it

Every one of those sentences is a rule something can break, and the ones
that break quietly are the ones here:

**A subject teacher must see her classes.** Membership ran off "who created
this class", so a teacher who claimed a subject slot signed in and saw no
classes at all — no register, no way to set work, no way to file a lesson
she had just taught. Nothing errored. The screens were simply empty, which
reads as "this product does not work" rather than as a bug.

**A lesson lands on a real subject.** A free-text box lets the same subject
be filed as "Biology", "biology" and "Bio" in one term, and lets a maths
teacher file work under somebody else's science. Neither is noticed until a
class cannot find last week's lesson.

**One school cannot see another.** Schools, colleges and coaching centres
share one deployment. A classroom, its subjects and its roll belong to
exactly one of them.
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
    email = f"cr{tag}{stamp}@example.com"
    r = c.post("/api/auth/signup", json={"name": f"Person {tag}",
                                         "email": email,
                                         "password": "RoomPass123!"})
    assert r.status_code == 200, r.text
    u = db.query(main.User).filter(main.User.email == email).first()
    u.dob = dt.date(1990, 1, 1)
    db.commit()
    return c, u


LESSON = {"title": "Osmosis",
          "steps": [{"t": "Water crosses a membrane towards the salt.",
                     "where": "", "code": ""}],
          "takeaway": "Water moves, the solute does not."}

# --- a school with one classroom, two subjects, two subject teachers ------
print("\nSetting up a school")
school = main.School(name=f"Hill School {stamp}", city="Chennai",
                     country="India", product="craxlearn")
coach = main.School(name=f"Coaching Centre {stamp}", city="Pune",
                    country="India", product="craxlearn")
db.add_all([school, coach])
db.commit()

head_c, head_u = account("head")
db.add(main.TeacherAccess(user_id=head_u.id, school=school.name,
                          school_id=school.id, role="head"))
db.commit()

k9 = main.Klass(name="9-A", join_code=f"CR9{stamp}"[:16],
                teacher_id=head_u.id, school=school.name, school_id=school.id)
k10 = main.Klass(name="10-A", join_code=f"CRX{stamp}"[:16],
                 teacher_id=head_u.id, school=school.name, school_id=school.id)
db.add_all([k9, k10])
db.commit()

# The head teacher creates the subjects. Each gets its own code.
made = {}
for cid, subject in ((k9.id, "Biology"), (k9.id, "Maths"), (k10.id, "Biology")):
    r = head_c.post(f"/api/head/class/{cid}/slot", json={"subject": subject})
    assert r.status_code == 200, r.text
    made[(cid, subject)] = r.json()["code"]
check("a class can have several subjects, each with its own code",
      len({v for v in made.values()}) == 3, str(len(made)))

# Two subject teachers claim theirs. Bio teaches Biology in BOTH classes.
bio_c, bio_u = account("bio")
mat_c, mat_u = account("mat")
for c, code in ((bio_c, made[(k9.id, "Biology")]),
                (bio_c, made[(k10.id, "Biology")]),
                (mat_c, made[(k9.id, "Maths")])):
    r = c.post("/api/class/join", json={"code": code})
    assert r.status_code == 200, r.text

# --- a subject teacher can actually see her classrooms -------------------
print("\nA teacher has several classrooms")
me = bio_c.get("/api/craxlearn/me").json()
rooms = {c["name"]: c for c in me["classes"]}
check("the Biology teacher sees BOTH classes she teaches in",
      set(rooms) == {"9-A", "10-A"}, str(sorted(rooms)))
check("and they are marked as hers to teach in",
      all(c["mine"] for c in rooms.values()),
      str([(n, c["mine"]) for n, c in rooms.items()]))
check("but she is not the head of them",
      not any(c["head"] for c in rooms.values()))
check("she may file under Biology and nothing else",
      rooms["9-A"]["my_subjects"] == ["Biology"],
      str(rooms["9-A"]["my_subjects"]))
check("while the class itself has both its subjects listed",
      sorted(x["name"] for x in rooms["9-A"]["subjects"]) == ["Biology", "Maths"],
      str([x["name"] for x in rooms["9-A"]["subjects"]]))
check("with the OTHER subject's teacher named, not hers",
      [x["teacher"] for x in rooms["9-A"]["subjects"]
       if x["name"] == "Maths"] == [mat_u.name],
      str([x for x in rooms["9-A"]["subjects"] if x["name"] == "Maths"]))

me = head_c.get("/api/craxlearn/me").json()
head_rooms = {c["name"]: c for c in me["classes"]}
check("the head teacher sees the classes she created",
      set(head_rooms) == {"9-A", "10-A"}, str(sorted(head_rooms)))
check("and may file under any subject those classes have",
      sorted(head_rooms["9-A"]["my_subjects"]) == ["Biology", "Maths"],
      str(head_rooms["9-A"]["my_subjects"]))

# --- a student has ONE classroom ------------------------------------------
print("\nA student has one classroom")
kid_c, kid_u = account("kid")
r = kid_c.post("/api/class/join", json={"code": k9.join_code})
check("a student joins their class", r.status_code == 200, r.text[:120])
r = kid_c.post("/api/class/join", json={"code": k10.join_code})
check("and cannot then join a second one", r.status_code == 409,
      f"{r.status_code} {r.text[:90]}")
check("the message says which class they are already in",
      "9-A" in r.text, r.text[:110])
check("and they are still in exactly one",
      db.query(main.ClassMember).filter(
          main.ClassMember.user_id == kid_u.id).count() == 1)

me = kid_c.get("/api/craxlearn/me").json()
check("the student sees their one classroom", len(me["classes"]) == 1,
      str([c["name"] for c in me["classes"]]))
check("with both its subjects",
      sorted(x["name"] for x in me["classes"][0]["subjects"])
      == ["Biology", "Maths"])
check("and the name of the teacher who takes each",
      sorted(x["teacher"] for x in me["classes"][0]["subjects"])
      == sorted([bio_u.name, mat_u.name]),
      str([x["teacher"] for x in me["classes"][0]["subjects"]]))
check("and none of them is theirs to teach",
      not any(x["mine"] for x in me["classes"][0]["subjects"]))

# --- a lesson is filed under a subject that exists -------------------------
print("\nA lesson lands on a real subject")
r = bio_c.post("/api/craxlearn/board/save",
               json={"class_id": k9.id, "topic": "osmosis",
                     "title": "Osmosis", "subject": "Biology",
                     "lesson": LESSON})
check("the Biology teacher files a Biology lesson", r.status_code == 200,
      r.text[:140])
check("under the subject as the school spells it",
      r.json()["material"]["subject"] == "Biology",
      str(r.json()["material"]["subject"]))

r = bio_c.post("/api/craxlearn/board/save",
               json={"class_id": k9.id, "topic": "osmosis", "title": "Osmosis",
                     "subject": "bIoLoGy", "lesson": LESSON})
check("case does not create a second subject",
      r.status_code == 200 and r.json()["material"]["subject"] == "Biology",
      r.text[:110])

r = bio_c.post("/api/craxlearn/board/save",
               json={"class_id": k9.id, "topic": "algebra", "title": "Algebra",
                     "subject": "Maths", "lesson": LESSON})
check("she cannot file under somebody else's subject", r.status_code == 403,
      f"{r.status_code} {r.text[:90]}")

r = bio_c.post("/api/craxlearn/board/save",
               json={"class_id": k9.id, "topic": "osmosis", "title": "Osmosis",
                     "subject": "Astrology", "lesson": LESSON})
check("nor invent one the class does not have", r.status_code == 403,
      str(r.status_code))

r = bio_c.post("/api/craxlearn/board/save",
               json={"class_id": k9.id, "topic": "osmosis", "title": "Osmosis",
                     "subject": "", "lesson": LESSON})
check("with one subject to her name, she need not say which",
      r.status_code == 200 and r.json()["material"]["subject"] == "Biology",
      r.text[:110])

r = head_c.post("/api/craxlearn/board/save",
                json={"class_id": k9.id, "topic": "osmosis", "title": "Osmosis",
                      "subject": "", "lesson": LESSON})
check("a head teacher with two must say which", r.status_code == 400,
      f"{r.status_code} {r.text[:90]}")
check("and is told what the choices are",
      "Biology" in r.text and "Maths" in r.text, r.text[:110])

# Setting work goes through the same gate as filing a lesson.
r = bio_c.post("/api/craxlearn/board/assign",
               json={"class_id": k9.id, "topic": "algebra", "title": "Algebra",
                     "subject": "Maths", "lesson": LESSON})
check("nor can she set WORK under another teacher's subject",
      r.status_code == 403, str(r.status_code))
r = bio_c.post("/api/craxlearn/board/assign",
               json={"class_id": k9.id, "topic": "osmosis", "title": "Osmosis",
                     "subject": "Biology", "lesson": LESSON})
check("but she can set work under her own", r.status_code == 200,
      r.text[:120])

# --- and the class can read what was filed --------------------------------
r = kid_c.get(f"/api/class/{k9.id}/materials")
kept = [m for m in r.json()["materials"] if m["kind"] == "lesson"]
check("the class can read the lessons kept for them", len(kept) >= 1,
      str(len(kept)))
check("each one under its subject",
      all(m["subject"] == "Biology" for m in kept),
      str({m["subject"] for m in kept}))

# --- one school cannot reach another --------------------------------------
print("\nOne school cannot see another")
far_c, far_u = account("far")
db.add(main.TeacherAccess(user_id=far_u.id, school=coach.name,
                          school_id=coach.id, role="head"))
db.commit()
far_k = main.Klass(name="Batch 1", join_code=f"CC{stamp}"[:16],
                   teacher_id=far_u.id, school=coach.name, school_id=coach.id)
db.add(far_k)
db.commit()

me = far_c.get("/api/craxlearn/me").json()
check("the coaching centre's head sees only their own batch",
      [c["name"] for c in me["classes"]] == ["Batch 1"],
      str([c["name"] for c in me["classes"]]))
check("and their own institution",
      (me.get("institution") or {}).get("name") == coach.name,
      str((me.get("institution") or {}).get("name")))
r = far_c.post("/api/craxlearn/board/save",
               json={"class_id": k9.id, "topic": "osmosis", "title": "Osmosis",
                     "subject": "Biology", "lesson": LESSON})
check("and cannot file a lesson into the school's class",
      r.status_code in (403, 404), str(r.status_code))
r = far_c.get(f"/api/class/{k9.id}/materials")
check("nor read what that class has been given",
      r.status_code in (403, 404), str(r.status_code))
r = far_c.post(f"/api/head/class/{k9.id}/slot", json={"subject": "Bio"})
check("nor add a subject to it", r.status_code in (403, 404),
      str(r.status_code))

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
