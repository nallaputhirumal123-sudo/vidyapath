"""Three roles, three walls, and an id in a URL does not get you through one.

Hiding a menu is not a permission. This suite never looks at a screen: it
takes each of the three accounts a school has and tries, over the real API,
to do the things belonging to the other two.

The wall that did not exist until now is the third one. A subject teacher was
kept out of attendance and fees, and that was called the separation of duties
— but nothing kept the OFFICE out of the classroom. A school admin held role
'head', `is_head` answered True, `_my_subjects` answered "all of them", and
so the person who runs the school could open any board, file study material
into any subject, and answer in any teacher's discussion.

That is the wrong way round, and it is also the whole reason an administrator
and a teacher were looking at almost the same dashboard: almost the same
permissions sat behind it.

The second half is the attack that costs nothing to try — changing a number
in a URL. A teacher who holds Physics in 9-A asking for 9-B, for another
teacher's subject, for a class at a different school entirely. Every one of
those must be refused by the server, and refused on OWNERSHIP rather than on
role: all of these callers are teachers, and being a teacher is exactly what
must not be enough.
"""
import io
import os
import sys
import time
import datetime as dt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"

import main                                        # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

main.Base.metadata.create_all(bind=main.engine)
main._migrate_columns()
main.send_email = lambda *a, **k: None

st = int(time.time())
P, F = [], []


def ck(n, c, d=""):
    print(("PASS " if c else "FAIL ") + n + (f" — {d}" if d else ""),
          flush=True)
    (P if c else F).append(n)


def refused(n, r, why=""):
    """403 or 404. Which one is deliberate and checked where it matters."""
    ck(n, r.status_code in (401, 403, 404),
       f"got {r.status_code}: {r.text[:80]}" + (f" — {why}" if why else ""))


def fresh():
    main._CODE_TRIES.clear()
    main._CODE_FAILS.clear()


db = main.SessionLocal()


def school(tag):
    sc = main.School(name=f"Wall {tag} {st}")
    db.add(sc)
    db.commit()
    db.refresh(sc)
    code = main._gen_head_code(db)
    db.add(main.TeacherCode(code=code, school=sc.name, school_id=sc.id,
                            is_head=True, active=True))
    db.commit()
    c = TestClient(main.app)
    em = f"w{tag}{st}@example.com"
    c.post("/api/auth/signup", json={"name": f"Office {tag}", "email": em,
                                     "password": "WallPass123!"})
    u = db.query(main.User).filter(main.User.email == em).first()
    u.dob = dt.date(1980, 1, 1)
    db.commit()
    c.post("/api/class/join", json={"code": code})
    return sc, c


def teacher_on(office, cid, subject, name):
    """A real teacher, made the way a school makes one, holding one subject."""
    slot = office.post(f"/api/head/class/{cid}/slot",
                       json={"subject": subject, "teacher_id": 0}).json()
    made = office.post("/api/head/staff",
                       json={"name": name, "role": "teacher"}).json()
    office.post("/api/head/assign",
                json={"class_id": cid, "subject": subject,
                      "user_id": made["user_id"]})
    fresh()
    c = TestClient(main.app)
    r = c.post("/api/auth/code",
               json={"code": db.get(main.SubjectSlot, slot["id"]).code})
    assert r.status_code == 200, r.text
    return c, made["user_id"]


# One school, two classes, two teachers who do not overlap. And a second
# school entirely, because "another teacher" and "another school's teacher"
# fail for different reasons and both must fail.
SC, OFFICE = school("a")
A = OFFICE.post("/api/teacher/class", json={"name": f"9-A {st}"}).json()
B = OFFICE.post("/api/teacher/class", json={"name": f"9-B {st}"}).json()
OFFICE.post(f"/api/teacher/class/{A['id']}/roster", json={"names": "Ravi A"})
OFFICE.post(f"/api/teacher/class/{B['id']}/roster", json={"names": "Sita B"})

PHYS, PHYS_ID = teacher_on(OFFICE, A["id"], "Physics", "Physics Teacher")
CHEM, CHEM_ID = teacher_on(OFFICE, A["id"], "Chemistry", "Chem Teacher")
BTEACH, _ = teacher_on(OFFICE, B["id"], "Physics", "B Physics Teacher")

SC2, OFFICE2 = school("b")
C = OFFICE2.post("/api/teacher/class", json={"name": f"9-C {st}"}).json()
FAR, _ = teacher_on(OFFICE2, C["id"], "Physics", "Far Teacher")

fresh()
kid = TestClient(main.app)
_names = kid.post("/api/craxlearn/code",
                  json={"code": A["join_code"]}).json()["names"]
kid.post("/api/craxlearn/claim",
         json={"code": A["join_code"], "roster_id": _names[0]["id"]})

LESSON = {"title": "T", "steps": [{"t": "a line"}]}

print("\nwall 1 — a teacher is not the office")
refused("no attendance", PHYS.post("/api/office/attendance",
                                   json={"class_id": A["id"],
                                         "day": "2026-01-01",
                                         "present": {}, "notes": {}}))
refused("no fee book", PHYS.get("/api/office/fees"))
refused("no run of the school", PHYS.get("/api/head/overview"))
refused("cannot create a class", PHYS.post("/api/teacher/class",
                                           json={"name": f"Sneaky {st}"}))
refused("cannot create a subject",
        PHYS.post(f"/api/head/class/{A['id']}/slot",
                  json={"subject": "Astrology", "teacher_id": 0}))
refused("cannot put anybody on a subject",
        PHYS.post("/api/head/assign",
                  json={"class_id": A["id"], "subject": "Chemistry",
                        "user_id": PHYS_ID}))
refused("cannot make a member of staff",
        PHYS.post("/api/head/staff", json={"name": "Ghost", "role": "teacher"}))
# The register is the school's list of children, not a subject's. A teacher
# who could add to it could add a child the office does not know exists.
refused("cannot type the register",
        PHYS.post(f"/api/teacher/class/{A['id']}/roster",
                  json={"names": "Not A Child"}))
ck("but still READS it — marking is impossible without it",
   PHYS.get(f"/api/teacher/class/{A['id']}/roster").status_code == 200,
   str(PHYS.get(f"/api/teacher/class/{A['id']}/roster").status_code))

print("\nwall 2 — the office does not teach")
# This is the wall that did not exist. Every refusal below was a 200.
refused("no board save",
        OFFICE.post("/api/craxlearn/board/save",
                    json={"class_id": A["id"], "subject": "Physics",
                          "topic": "office", "title": "Office",
                          "lesson": LESSON}))
refused("no study material by link",
        OFFICE.post(f"/api/teacher/class/{A['id']}/material/link",
                    json={"title": "Notes", "url": "https://x.in/a",
                          "subject": "Physics"}))
refused("no study material by file",
        OFFICE.post(f"/api/teacher/class/{A['id']}/material/file",
                    files={"file": ("c.pdf", io.BytesIO(b"%PDF-1.4\n"),
                                    "application/pdf")},
                    data={"title": "Chapter", "subject": "Physics"}))
refused("no document brought in at the board",
        OFFICE.post("/api/craxlearn/board/file",
                    files={"file": ("c.pdf", io.BytesIO(b"%PDF-1.4\n"),
                                    "application/pdf")},
                    data={"title": "Chapter", "class_id": str(A["id"]),
                          "subject": "Physics"}))
refused("no PDF written up as a lesson",
        OFFICE.post("/api/teach/pdf",
                    files={"file": ("c.pdf", io.BytesIO(b"%PDF-1.4\n"),
                                    "application/pdf")}))
refused("no Ask Axle", OFFICE.post("/api/ask",
                                   json={"question": "what is refraction",
                                         "subject": "Science"}))
refused("no lesson on the board", OFFICE.post("/api/board/lesson",
                                              json={"topic": "refraction",
                                                    "level": "Intermediate"}))
# And it keeps everything it is actually for, or the wall is a wall in the
# wrong place. A principal who cannot see their own school is not secured.
ck("the office still runs the school",
   OFFICE.get("/api/head/overview").status_code == 200
   and OFFICE.get("/api/head/people").status_code == 200
   and OFFICE.get("/api/office/fees").status_code == 200)
ck("and still reads what is being taught",
   OFFICE.get(f"/api/class/{A['id']}/materials").status_code == 200,
   "knowing a class is taught is not the same as teaching it")

print("\nwall 3 — a learner is neither")
refused("no board save", kid.post("/api/craxlearn/board/save",
                                  json={"class_id": A["id"],
                                        "topic": "sneaky", "title": "Sneaky",
                                        "lesson": LESSON}))
refused("no material", kid.post(f"/api/teacher/class/{A['id']}/material/link",
                                json={"title": "Sneaky",
                                      "url": "https://x.in/a"}))
refused("no register", kid.get(f"/api/teacher/class/{A['id']}/roster"))
refused("no fee book", kid.get("/api/office/fees"))
ck("but Ask Axle is theirs — it is what it was built for",
   kid.post("/api/ask", json={"question": "what is refraction",
                              "subject": "Science"}).status_code != 403,
   "no AI key here, so anything but 403 proves the gate let them through")

print("\nchanging the number in the URL")
# Every caller below IS a teacher. Being a teacher is exactly what must not
# be enough — the question is whether THIS class and THIS subject are theirs.
refused("another class in the same school",
        PHYS.get(f"/api/teacher/class/{B['id']}"),
        "9-A's teacher asking for 9-B")
refused("its register too",
        PHYS.get(f"/api/teacher/class/{B['id']}/roster"))
refused("and its material",
        PHYS.get(f"/api/class/{B['id']}/materials"))
refused("cannot file a lesson into it",
        PHYS.post("/api/craxlearn/board/save",
                  json={"class_id": B["id"], "subject": "Physics",
                        "topic": "next door", "title": "Next door",
                        "lesson": LESSON}))
refused("a class at another school",
        PHYS.get(f"/api/teacher/class/{C['id']}"))
refused("and the far teacher cannot reach back",
        FAR.get(f"/api/teacher/class/{A['id']}"))
refused("nor the office of another school",
        OFFICE2.get(f"/api/teacher/class/{A['id']}"))

print("\nthe same class, somebody else's subject")
# The harder one, and the one a role check alone always gets wrong: both of
# these people teach in 9-A. Only one of them teaches Physics in it.
ck("Physics is filed by the Physics teacher",
   PHYS.post("/api/craxlearn/board/save",
             json={"class_id": A["id"], "subject": "Physics",
                   "topic": f"Refraction {st}", "title": f"Refraction {st}",
                   "lesson": LESSON}).status_code == 200)
r = CHEM.post("/api/craxlearn/board/save",
              json={"class_id": A["id"], "subject": "Physics",
                    "topic": "not mine", "title": "Not mine",
                    "lesson": LESSON})
ck("the Chemistry teacher cannot file under Physics", r.status_code == 403,
   f"got {r.status_code}")
r = CHEM.post(f"/api/teacher/class/{A['id']}/assignment",
              json={"subject": "Physics", "title": "No", "body": "x",
                    "due_date": ""})
ck("nor set work in it", r.status_code == 403, f"got {r.status_code}")
r = CHEM.post(f"/api/teacher/class/{A['id']}/material/link",
              json={"title": "Not mine", "url": "https://x.in/a",
                    "subject": "Physics"})
ck("nor put material in it", r.status_code == 403, f"got {r.status_code}")
r = PHYS.post("/api/craxlearn/board/save",
              json={"class_id": A["id"], "subject": "Astrology",
                    "topic": "invented", "title": "Invented",
                    "lesson": LESSON})
ck("nor may anybody invent a subject the class does not have",
   r.status_code == 403, f"got {r.status_code}")

print("\nand a document is fetched against the room, not the id")
r = PHYS.post("/api/craxlearn/board/file",
              files={"file": ("own.pdf", io.BytesIO(b"%PDF-1.4\nmine\n"),
                              "application/pdf")},
              data={"title": f"Own {st}", "class_id": str(A["id"]),
                    "subject": "Physics"})
ck("the Physics teacher keeps a document", r.status_code == 200, r.text[:110])
MID = r.json()["material"]["id"]
ck("and can open it back",
   PHYS.get(f"/api/craxlearn/board/material/{MID}/file"
            f"?class_id={A['id']}&subject=Physics").status_code == 200)
refused("the Chemistry teacher cannot, by asking for its id",
        CHEM.get(f"/api/craxlearn/board/material/{MID}/file"
                 f"?class_id={A['id']}&subject=Chemistry"))
refused("nor the teacher of the class next door",
        BTEACH.get(f"/api/craxlearn/board/material/{MID}/file"
                   f"?class_id={B['id']}&subject=Physics"))
refused("nor anybody at all with no session",
        TestClient(main.app).get(
            f"/api/craxlearn/board/material/{MID}/file"))

print("\nthe platform admin is above all three, on purpose")
# Support that cannot be given without asking the customer to do it
# themselves is not support.
admin_c = TestClient(main.app)
ae = f"wadm{st}@example.com"
admin_c.post("/api/auth/signup",
             json={"name": "Platform", "email": ae, "password": "WallPass123!"})
_a = db.query(main.User).filter(main.User.email == ae).first()
_a.is_admin = True
db.commit()
ck("reaches a school's classroom",
   admin_c.get(f"/api/teacher/class/{A['id']}").status_code == 200)
ck("and its material",
   admin_c.get(f"/api/class/{A['id']}/materials").status_code == 200)

db.close()
print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
