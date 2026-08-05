"""A subject's discussion belongs to the teacher of that subject.

The thread under a subject is the one place in a class where children talk to
each other with a teacher present. It was open to every teacher of the class:
the maths teacher could read the science thread, answer in it, and delete out
of it. The gate was "in this class, or teaching anything in it", which is the
right test for study material and the wrong one for a conversation.

Three answers, and this pins all three:

  * the head and the office see everything — they are responsible for the
    school and cannot supervise what they cannot read;
  * a child sees every subject their own class is taught;
  * a teacher sees the subjects they hold in that class, and no others.

The case that decides the shape is a teacher who holds Maths in a class and
nothing else, against a thread under Science in the same class.
"""
import os, sys, time, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"
import main
from fastapi.testclient import TestClient

main.Base.metadata.create_all(bind=main.engine)
main._migrate_columns()
main.send_email = lambda *a, **k: None

st = int(time.time())
P, F = [], []
def ck(n, c, d=""):
    print(("PASS " if c else "FAIL ") + n + (f" — {d}" if d else ""), flush=True)
    (P if c else F).append(n)

db = main.SessionLocal()
sc = main.School(name=f"Walls School {st}")
db.add(sc); db.commit(); db.refresh(sc)
HEAD = f"HEAD-W{str(st)[-4:]}"
db.add(main.TeacherCode(code=HEAD, school=sc.name, school_id=sc.id,
                        is_head=True, active=True))
db.commit()

def account(tag, name):
    c = TestClient(main.app)
    em = f"w{tag}{st}@example.com"
    c.post("/api/auth/signup", json={"name": name, "email": em,
                                     "password": "WallPass1!"})
    u = db.query(main.User).filter(main.User.email == em).first()
    u.dob = dt.date(1988, 3, 3); db.commit()
    return c, u.id

head, HEAD_ID = account("head", "Principal W")
head.post("/api/class/join", json={"code": HEAD})
mk = head.post("/api/teacher/class", json={"name": f"8-W {st}"}).json()
CID, CODE = mk["id"], mk["join_code"]
head.post(f"/api/teacher/class/{CID}/roster",
          json={"names": "Nila P, 801\nOmar S, 802"})

# Two subjects, two different teachers.
maths = head.post(f"/api/head/class/{CID}/slot",
                  json={"subject": "Maths", "teacher_id": 0}).json()
sci = head.post(f"/api/head/class/{CID}/slot",
                json={"subject": "Science", "teacher_id": 0}).json()

mt, MT_ID = account("mt", "Maths Teacher")
mt.post("/api/class/join", json={"code": maths["code"]})
sct, SCT_ID = account("sct", "Science Teacher")
sct.post("/api/class/join", json={"code": sci["code"]})

# A child of the class.
main._CODE_TRIES.clear(); main._CODE_FAILS.clear()
kid = TestClient(main.app)
names = kid.post("/api/craxlearn/code", json={"code": CODE}).json()["names"]
kid.post("/api/craxlearn/claim",
         json={"code": CODE, "roster_id": names[0]["id"]})
KID_ID = kid.get("/api/auth/me").json().get("id")

print("\nthe child asks in each subject")
r = kid.post(f"/api/class/{CID}/discussion",
             json={"subject": "Science", "body": f"why is the sky blue {st}"})
ck("a child can ask in Science", r.status_code == 200, r.text[:110])
SCI_Q = (r.json() or {}).get("id")
r = kid.post(f"/api/class/{CID}/discussion",
             json={"subject": "Maths", "body": f"what is a prime {st}"})
ck("and in Maths", r.status_code == 200, r.text[:110])

print("\nthe science teacher")
def bodies_in(d):
    """Every body in the response, questions and replies alike."""
    out = []
    for t in (d.get("threads") or []):
        out.append(t.get("body") or "")
        for r in (t.get("replies") or []):
            out.append(r.get("body") or "")
    return " ".join(out)

d = sct.get(f"/api/class/{CID}/discussion?subject=Science").json()
ck("reads the Science thread",
   f"why is the sky blue {st}" in bodies_in(d), str(d)[:120])
r = sct.post(f"/api/class/{CID}/discussion",
             json={"subject": "Science", "parent_id": SCI_Q,
                   "body": "Because of scattering."})
ck("and answers in it", r.status_code == 200, r.text[:110])

print("\nthe maths teacher, in a subject that is not theirs")
r = mt.get(f"/api/class/{CID}/discussion?subject=Science")
ck("cannot read the Science thread", r.status_code == 403,
   f"got {r.status_code}")
r = mt.post(f"/api/class/{CID}/discussion",
            json={"subject": "Science", "body": "butting in"})
ck("cannot post into it", r.status_code == 403, f"got {r.status_code}")
r = mt.post(f"/api/class/{CID}/discussion",
            json={"subject": "Science", "parent_id": SCI_Q, "body": "nor reply"})
ck("cannot reply to it either — a reply inherits the question's subject",
   r.status_code == 403, f"got {r.status_code}")
r = mt.delete(f"/api/class/{CID}/discussion/{SCI_Q}")
ck("cannot delete out of it", r.status_code == 403, f"got {r.status_code}")

print("\nand the whole-class view is narrowed too, not just the filtered one")
d = mt.get(f"/api/class/{CID}/discussion").json()
bodies = bodies_in(d)
ck("asking for everything returns only their own subject",
   f"what is a prime {st}" in bodies and f"why is the sky blue {st}" not in bodies,
   bodies[:110])

print("\ntheir own subject still works")
d = mt.get(f"/api/class/{CID}/discussion?subject=Maths").json()
ck("the maths teacher reads Maths",
   f"what is a prime {st}" in bodies_in(d), str(d)[:120])
ck("and can answer in it",
   mt.post(f"/api/class/{CID}/discussion",
           json={"subject": "Maths", "body": "A prime has two factors."}
           ).status_code == 200)

print("\nthe child sees every subject of their own class")
d = kid.get(f"/api/class/{CID}/discussion").json()
bodies = bodies_in(d)
ck("both threads are theirs to see",
   f"what is a prime {st}" in bodies and f"why is the sky blue {st}" in bodies,
   bodies[:130])
ck("and they can read a subject they were answered in",
   kid.get(f"/api/class/{CID}/discussion?subject=Science").status_code == 200)

print("\nthe head sees everything, because they answer for it")
d = head.get(f"/api/class/{CID}/discussion").json()
bodies = bodies_in(d)
ck("every subject", f"what is a prime {st}" in bodies
   and f"why is the sky blue {st}" in bodies, bodies[:130])
ck("including one filtered by subject",
   head.get(f"/api/class/{CID}/discussion?subject=Science").status_code == 200)

print("\nand nobody outside the class gets in at all")
out, _ = account("out", "Outsider W")
ck("an unrelated account is refused",
   out.get(f"/api/class/{CID}/discussion").status_code in (403, 404),
   str(out.get(f"/api/class/{CID}/discussion").status_code))

print("\nreading everything is not the same as being able to delete it")
# The first version of this rule reused the read-scope helper to decide who
# may delete. For a child in the class that helper answers "every subject" —
# correct for reading, and it handed thirty children the power to delete each
# other's messages. Two questions, two helpers.
kid2 = TestClient(main.app)
main._CODE_TRIES.clear(); main._CODE_FAILS.clear()
n2 = kid2.post("/api/craxlearn/code", json={"code": CODE}).json()["names"]
free = [n for n in n2 if not n.get("taken")]
kid2.post("/api/craxlearn/claim", json={"code": CODE, "roster_id": free[0]["id"]})
r = kid.post(f"/api/class/{CID}/discussion",
             json={"subject": "Maths", "body": f"mine alone {st}"})
THEIRS = (r.json() or {}).get("id")
ck("a classmate cannot delete another child's message",
   kid2.delete(f"/api/class/{CID}/discussion/{THEIRS}").status_code == 403,
   str(kid2.delete(f"/api/class/{CID}/discussion/{THEIRS}").status_code))
ck("but the subject's own teacher can",
   mt.delete(f"/api/class/{CID}/discussion/{THEIRS}").status_code == 200)

print("\na message with no subject belongs to the whole class")
# Restricting these broke posting entirely: the check fired on an empty
# string, which is in nobody's subject list.
r = mt.post(f"/api/class/{CID}/discussion", json={"body": f"class notice {st}"})
ck("a teacher can post to the class without naming a subject",
   r.status_code == 200, r.text[:110])
ck("and still sees it in their own view",
   f"class notice {st}" in bodies_in(
       mt.get(f"/api/class/{CID}/discussion").json()))
ck("as does a teacher of a different subject",
   f"class notice {st}" in bodies_in(
       sct.get(f"/api/class/{CID}/discussion").json()))

print("\na child may still unsay their own message")
r = kid.post(f"/api/class/{CID}/discussion",
             json={"subject": "Maths", "body": f"oops {st}"})
mine = (r.json() or {}).get("id")
ck("their own comes down",
   kid.delete(f"/api/class/{CID}/discussion/{mine}").status_code == 200)

db.close()
print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
