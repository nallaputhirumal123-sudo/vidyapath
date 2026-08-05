"""A teacher signs in with their code. No email, no password.

A teacher is handed a code by the school office — one for each classroom and
subject they teach — and that is what they were given. The sign-in asked for
an email and a password instead, neither of which anybody gave them, and the
account the office had made was created with an address that more than once
could not be signed in with at all.

So the code is the way in. It signs them in as the person the school ALREADY
put on that subject: the office makes the profile and assigns it, and this
turns the code into a session on that account. It never creates an account and
never guesses a name, because an account the school did not make is one it
cannot recognise.

The cost is stated in the route and pinned here: the code IS the credential.
Whoever holds it is that teacher. It is per classroom and per subject, so one
that leaks exposes one subject in one room, and it can be rotated. That is the
whole of the protection.
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

def fresh():
    main._CODE_TRIES.clear(); main._CODE_FAILS.clear()

db = main.SessionLocal()
sc = main.School(name=f"Code Login School {st}")
db.add(sc); db.commit(); db.refresh(sc)
HEAD = f"HEAD-L{str(st)[-4:]}"
db.add(main.TeacherCode(code=HEAD, school=sc.name, school_id=sc.id,
                        is_head=True, active=True))
db.commit()

head = TestClient(main.app)
HE = f"cl{st}@example.com"
head.post("/api/auth/signup", json={"name": "Principal L", "email": HE,
                                    "password": "CodeLogin1!"})
u = db.query(main.User).filter(main.User.email == HE).first()
u.dob = dt.date(1982, 6, 6); db.commit()
head.post("/api/class/join", json={"code": HEAD})

A = head.post("/api/teacher/class", json={"name": f"7-L {st}"}).json()
B = head.post("/api/teacher/class", json={"name": f"8-L {st}"}).json()

# The office makes the teacher's profile — this is the only place an account
# is created, which is the whole point of the design.
made = head.post("/api/head/staff",
                 json={"name": "Mrs Iyer", "email": f"iyer{st}@example.com",
                       "role": "teacher"}).json()
TID = made["user_id"]

slotA = head.post(f"/api/head/class/{A['id']}/slot",
                  json={"subject": "Maths", "teacher_id": 0}).json()
slotB = head.post(f"/api/head/class/{B['id']}/slot",
                  json={"subject": "Maths", "teacher_id": 0}).json()
head.post("/api/head/assign",
          json={"class_id": A["id"], "subject": "Maths", "user_id": TID})
head.post("/api/head/assign",
          json={"class_id": B["id"], "subject": "Maths", "user_id": TID})

print("\nthe code is the whole sign-in")
fresh()
t1 = TestClient(main.app)
r = t1.post("/api/auth/code", json={"code": slotA["code"]})
ck("a subject code signs the teacher in", r.status_code == 200, r.text[:130])
d = r.json()
ck("as the person the office assigned", d.get("name") == "Mrs Iyer", str(d))
ck("and says which classroom and subject",
   d.get("class_id") == A["id"] and d.get("subject") == "Maths", str(d))
me = t1.get("/api/auth/me").json()
ck("the session is real", me.get("id") == TID, str(me.get("id")))
ck("and it is a teacher", bool(me.get("is_teacher")))

print("\nno email or password was involved anywhere")
ck("their classes are there",
   any(c.get("id") == A["id"]
       for c in (t1.get("/api/teacher/classes").json().get("classes") or [])),
   t1.get("/api/teacher/classes").text[:140])

print("\none teacher, two classrooms, two codes")
fresh()
t2 = TestClient(main.app)
r = t2.post("/api/auth/code", json={"code": slotB["code"]})
ck("the second classroom's code also signs them in",
   r.status_code == 200 and r.json().get("class_id") == B["id"], r.text[:130])
ck("as the SAME account, not a second one",
   t2.get("/api/auth/me").json().get("id") == TID,
   str(t2.get("/api/auth/me").json().get("id")))
ck("the two codes are different", slotA["code"] != slotB["code"],
   f"{slotA['code']} / {slotB['code']}")

print("\nwhat it refuses")
fresh()
r = TestClient(main.app).post("/api/auth/code", json={"code": "T-ZZZZ"})
ck("a code nobody holds", r.status_code == 404, f"got {r.status_code}")

fresh()
empty = head.post(f"/api/head/class/{A['id']}/slot",
                  json={"subject": "History", "teacher_id": 0}).json()
r = TestClient(main.app).post("/api/auth/code", json={"code": empty["code"]})
ck("a subject with nobody assigned to it — no account is invented",
   r.status_code == 409, f"got {r.status_code}")
db.expire_all()
ck("and it really did not create one",
   db.query(main.User).filter(main.User.name == "").count() == 0)

fresh()
k = db.get(main.Klass, A["id"])
r = TestClient(main.app).post("/api/auth/code", json={"code": k.join_code})
ck("a pupil's class code is not a staff sign-in", r.status_code == 404,
   f"got {r.status_code}")

print("\na rotated code stops working, which is the only lever there is")
rot = head.post(f"/api/head/slot/{slotA['id'] if 'id' in slotA else 0}/rotate",
                json={}) if slotA.get("id") else None
if rot is not None and rot.status_code == 200:
    newcode = rot.json().get("code") or rot.json().get("join_code")
    fresh()
    ck("the old code is refused",
       TestClient(main.app).post("/api/auth/code",
                                 json={"code": slotA["code"]}).status_code == 404)
    fresh()
    ck("the new one works",
       TestClient(main.app).post("/api/auth/code",
                                 json={"code": newcode}).status_code == 200)
else:
    ck("rotation is reachable", False, f"slot rotate gave {rot.status_code if rot else 'no id'}")

print("\nand a pupil's account can never be reached through a slot")
main._CODE_TRIES.clear(); main._CODE_FAILS.clear()
head.post(f"/api/teacher/class/{A['id']}/roster", json={"names": "Tara V, 701"})
kid = TestClient(main.app)
names = kid.post("/api/craxlearn/code",
                 json={"code": k.join_code}).json()["names"]
kid.post("/api/craxlearn/claim",
         json={"code": k.join_code, "roster_id": names[0]["id"]})
KID = kid.get("/api/auth/me").json().get("id")
slot_row = db.get(main.SubjectSlot, slotB["id"])
slot_row.teacher_id = KID          # what a stopped bug used to leave behind
db.commit()
fresh()
r = TestClient(main.app).post("/api/auth/code", json={"code": slotB["code"]})
ck("a slot held by a class-code account is refused", r.status_code == 403,
   f"got {r.status_code}")

db.close()
print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
