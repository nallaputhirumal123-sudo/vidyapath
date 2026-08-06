"""A child writes to their teacher. A child does not write to another child.

The classroom discussion is the group, one thread per subject, in front of
everybody, and it already exists. What did not exist is the quiet question —
a child who will not put their hand up and will not type it under their own
name in front of thirty classmates.

So the shape of this is the rule, and the rule is not symmetric:

    a child   may write to the teacher of a subject their class is taught,
              and to nobody else
    a teacher may write to any child on the register of a class and subject
              they hold

There is no child-to-child path, and its absence is the point rather than
something to fill in later: a school that hands thirty children a private
channel to each other has taken on moderating it, in the evenings, in a
product with no moderators.

Everything below goes through the live API. The refusals are the reason this
file exists — a messaging feature is judged by who it will NOT deliver to.
"""
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
from _school import teacher_on                     # noqa: E402

main.Base.metadata.create_all(bind=main.engine)
main._migrate_columns()
main.send_email = lambda *a, **k: None

st = int(time.time())
P, F = [], []


def ck(n, c, d=""):
    print(("PASS " if c else "FAIL ") + n + (f" — {d}" if d else ""),
          flush=True)
    (P if c else F).append(n)


def fresh():
    main._CODE_TRIES.clear()
    main._CODE_FAILS.clear()


db = main.SessionLocal()
sc = main.School(name=f"Msg School {st}")
db.add(sc); db.commit(); db.refresh(sc)
HEAD = main._gen_head_code(db)
db.add(main.TeacherCode(code=HEAD, school=sc.name, school_id=sc.id,
                        is_head=True, active=True, label="Principal M"))
db.commit()

office = TestClient(main.app)
OE = f"mo{st}@example.com"
office.post("/api/auth/signup",
            json={"name": "Principal M", "email": OE, "password": "MsgPass1!"})
_u = db.query(main.User).filter(main.User.email == OE).first()
_u.dob = dt.date(1980, 2, 2); db.commit()
office.post("/api/class/join", json={"code": HEAD})

A = office.post("/api/teacher/class", json={"name": f"6-M {st}"}).json()
B = office.post("/api/teacher/class", json={"name": f"7-M {st}"}).json()
office.post(f"/api/teacher/class/{A['id']}/roster",
            json={"names": "Anu M, 601\nBala M, 602"})
office.post(f"/api/teacher/class/{B['id']}/roster", json={"names": "Chitra M"})

PHYS, PHYS_ID, _c, _s = teacher_on(main, office, A["id"], "Physics",
                                   "Physics M")
CHEM, CHEM_ID, _c2, _s2 = teacher_on(main, office, A["id"], "Chemistry",
                                     "Chem M")
FAR, FAR_ID, _c3, _s3 = teacher_on(main, office, B["id"], "Physics",
                                   "Far M")


def pupil(klass):
    """The first name nobody has taken. Claimed names stay on the register, so
    asking for "the second" would hand back a child already signed in — and
    single-session sign-in would then quietly sign the first one out."""
    fresh()
    c = TestClient(main.app)
    names = c.post("/api/craxlearn/code",
                   json={"code": klass["join_code"]}).json()["names"]
    free = [n for n in names if not n.get("taken")]
    assert free, f"no free name on {klass['name']}"
    c.post("/api/craxlearn/claim",
           json={"code": klass["join_code"], "roster_id": free[0]["id"]})
    me = c.get("/api/auth/me").json()
    return c, me.get("id"), me.get("name") or ""


ANU, ANU_ID, ANU_NAME = pupil(A)
BALA, BALA_ID, BALA_NAME = pupil(A)
CHITRA, CHITRA_ID, _cn = pupil(B)

print("\na child writes to the teacher of their subject")
r = ANU.post("/api/messages",
             json={"class_id": A["id"], "subject": "Physics",
                   "body": "I did not follow refraction, sorry."})
ck("it is accepted", r.status_code == 200, r.text[:120])
r = ANU.get(f"/api/messages/thread?class_id={A['id']}&subject=Physics")
ck("and it is in the thread", r.status_code == 200
   and len(r.json().get("messages", [])) == 1, r.text[:130])
d = r.json()
ck("with the teacher named", d.get("teacher") == "Physics M", str(d)[:120])
ck("and the message carries who wrote it",
   d["messages"][0].get("from") == ANU_NAME, str(d["messages"][0])[:120])
ck("marked as theirs, not the teacher's",
   d["messages"][0].get("from_teacher") is False)

print("\nthe teacher sees it, with a name on it")
r = PHYS.get("/api/messages")
ck("it is in their inbox", r.status_code == 200
   and len(r.json().get("threads", [])) == 1, r.text[:130])
t = r.json()["threads"][0]
ck("from a person, not an id", t.get("with") == ANU_NAME, str(t)[:130])
ck("and it says which class and subject",
   t.get("subject") == "Physics" and t.get("class_id") == A["id"], str(t)[:130])
ck("and that it is unread", t.get("unread") == 1, str(t.get("unread")))
ck("the count is on the top level too", r.json().get("unread") == 1)

r = PHYS.get(f"/api/messages/thread?class_id={A['id']}&subject=Physics"
             f"&with_id={ANU_ID}")
ck("they can open it", r.status_code == 200, r.text[:120])
ck("reading it marks it read",
   PHYS.get("/api/messages").json().get("unread") == 0)

print("\nand can answer")
r = PHYS.post("/api/messages",
              json={"class_id": A["id"], "subject": "Physics",
                    "to_id": ANU_ID, "body": "Look at figure 4.3 first."})
ck("the teacher writes back", r.status_code == 200, r.text[:120])
d = ANU.get(f"/api/messages/thread?class_id={A['id']}&subject=Physics").json()
ck("the child sees the reply", len(d.get("messages", [])) == 2)
ck("marked as the teacher's", d["messages"][1].get("from_teacher") is True)
ck("with the teacher's name", d["messages"][1].get("from") == "Physics M",
   str(d["messages"][1])[:110])

print("\nA CHILD CANNOT WRITE TO ANOTHER CHILD")
# There is no route that takes a pupil as a recipient, and the one that
# takes a `to_id` throws it away for anybody who is not the subject's
# teacher. So the way to try it is to send as a pupil and name a classmate,
# which is exactly what a pupil would try.
r = BALA.post("/api/messages",
              json={"class_id": A["id"], "subject": "Physics",
                    "to_id": ANU_ID, "body": "psst"})
ck("naming a classmate is accepted but does not reach them",
   r.status_code == 200, r.text[:120])
d = ANU.get(f"/api/messages/thread?class_id={A['id']}&subject=Physics").json()
ck("Anu's thread is untouched by it", len(d.get("messages", [])) == 2,
   str(len(d.get("messages", []))))
d = BALA.get(f"/api/messages/thread?class_id={A['id']}&subject=Physics").json()
ck("it went to the TEACHER instead, which is the only place it can go",
   len(d.get("messages", [])) == 1 and d.get("teacher") == "Physics M",
   str(d)[:130])
ck("and the classmate is nowhere in that thread",
   ANU_NAME not in str(d), str(d)[:130])
# The inbox is the other half of the same claim.
ck("and the first child's inbox does not show the second",
   not any(BALA_NAME in (x.get("with") or "")
           for x in ANU.get("/api/messages").json().get("threads", [])),
   str(ANU.get("/api/messages").json())[:140])

print("\nnor to a teacher who does not teach them")
r = ANU.post("/api/messages",
             json={"class_id": B["id"], "subject": "Physics",
                   "body": "hello"})
ck("a class they are not in is refused", r.status_code == 403,
   f"got {r.status_code}")
r = ANU.post("/api/messages",
             json={"class_id": A["id"], "subject": "Astrology",
                   "body": "hello"})
ck("a subject the class does not have is refused", r.status_code == 404,
   f"got {r.status_code}")

print("\nand a teacher cannot reach somebody else's pupil")
r = FAR.post("/api/messages",
             json={"class_id": A["id"], "subject": "Physics",
                   "to_id": ANU_ID, "body": "hello"})
ck("another class's teacher is refused", r.status_code in (403, 404),
   f"got {r.status_code}")
r = PHYS.post("/api/messages",
              json={"class_id": A["id"], "subject": "Physics",
                    "to_id": CHITRA_ID, "body": "hello"})
ck("a child who is not on this register is refused", r.status_code == 404,
   f"got {r.status_code}")
r = PHYS.post("/api/messages",
              json={"class_id": A["id"], "subject": "Chemistry",
                    "to_id": ANU_ID, "body": "hello"})
ck("and a subject they do not hold — it becomes a pupil's message, "
   "not a teacher's",
   r.status_code in (200, 403, 409), f"got {r.status_code}")
if r.status_code == 200:
    d = CHEM.get("/api/messages").json()
    ck("which the Chemistry teacher does NOT receive from them as staff",
       not any(x.get("with") == ANU_NAME for x in d.get("threads", [])),
       str(d)[:140])

print("\nthe office is not in anybody's private thread")
r = office.get("/api/messages")
ck("a school admin's inbox is empty", r.status_code == 200
   and not r.json().get("threads"), str(r.json())[:130])
r = office.get(f"/api/messages/thread?class_id={A['id']}&subject=Physics"
               f"&with_id={ANU_ID}")
ck("and reading somebody else's is refused", r.status_code in (400, 403, 404),
   f"got {r.status_code}")

print("\nnobody at all without a session")
anon = TestClient(main.app)
ck("no inbox", anon.get("/api/messages").status_code == 401)
ck("no thread",
   anon.get(f"/api/messages/thread?class_id={A['id']}&subject=Physics"
            ).status_code == 401)
ck("no sending",
   anon.post("/api/messages",
             json={"class_id": A["id"], "subject": "Physics",
                   "body": "x"}).status_code == 401)

db.close()
print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
