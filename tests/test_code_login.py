"""A subject code opens a board. It is not a way into an account.

This file used to pin the opposite, and the reasoning it pinned was written
down honestly at the time: a teacher standing in front of a class does not
type an email address and a password, they were handed a code by the office,
so the code should be the way in. The cost was stated too — the code IS the
credential, whoever holds it is that teacher — and judged acceptable because
a code covers one subject in one room and can be rotated.

What that skates over is where the code lives. A subject code exists so that
a BOARD can be told which room it is standing in. It is chalked up, read
aloud, printed on a timetable, passed down a row. Every child in the room has
it, by design, because that is what it is for.

And the session it handed out was not scoped to the classroom at all. It was
the teacher's own account: every class they teach, every register, every
mark, every subject's discussion, and Ask Axle billed to them. One code read
off a wall bought all of it.

So the two jobs are separated, and that is what this pins now:

    T-XXXX at /api/craxlearn/room   ->  a board token. One class, one
                                        subject, the routes that file a
                                        lesson into them, and nothing else.
    T-XXXX at /api/auth/code        ->  refused, and told where it goes.
    email + password at /api/auth/login  ->  the teacher, and their classes.

The ten digits are untouched. That code is handed to one person once, it
carries the name it was issued in, and it is not written on anything a room
can read.
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
from _school import make_staff                      # noqa: E402

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
HEAD = main._gen_head_code(db)
db.add(main.TeacherCode(code=HEAD, school=sc.name, school_id=sc.id,
                        is_head=True, active=True, label="Principal L"))
db.commit()

head = TestClient(main.app)
HE = f"cl{st}@example.com"
head.post("/api/auth/signup",
          json={"name": "Principal L", "email": HE, "password": "CodePass1!"})
_u = db.query(main.User).filter(main.User.email == HE).first()
_u.dob = dt.date(1981, 1, 1); db.commit()
head.post("/api/class/join", json={"code": HEAD})

A = head.post("/api/teacher/class", json={"name": f"7-L {st}"}).json()
B = head.post("/api/teacher/class", json={"name": f"8-L {st}"}).json()

# The office makes the teacher's profile — still the only place an account is
# created — and is handed a password ONCE, which it gives to the teacher.
TEACH, TID, TEMAIL, TPW = make_staff(main, head, "Mrs Iyer")

slotA = head.post(f"/api/head/class/{A['id']}/slot",
                  json={"subject": "Maths", "teacher_id": 0}).json()
slotB = head.post(f"/api/head/class/{B['id']}/slot",
                  json={"subject": "Maths", "teacher_id": 0}).json()
head.post("/api/head/assign",
          json={"class_id": A["id"], "subject": "Maths", "user_id": TID})
head.post("/api/head/assign",
          json={"class_id": B["id"], "subject": "Maths", "user_id": TID})

print("\nthe teacher signs in as themselves")
me = TEACH.get("/api/auth/me").json()
ck("the account the office made", me.get("id") == TID, str(me.get("id")))
ck("and it is a teacher", bool(me.get("is_teacher")))

print("\none account, every class and subject they hold")
# The reason a teacher never signs out to move between subjects: they are all
# on the one identity, and each carries its own code for a board.
d = TEACH.get("/api/teacher/classes").json()
posts = d.get("posts") or []
ck("both classrooms are theirs",
   {p["class_id"] for p in posts} == {A["id"], B["id"]},
   str([p["class_id"] for p in posts]))
ck("each with its own code",
   len({p["code"] for p in posts}) == 2, str([p["code"] for p in posts]))
ck("and the codes are shown, not hidden",
   all(p.get("code") for p in posts), str(posts)[:140])

print("\nbut the code itself signs nobody in")
fresh()
r = TestClient(main.app).post("/api/auth/code", json={"code": slotA["code"]})
ck("a subject code is refused at the sign-in", r.status_code == 403,
   f"got {r.status_code}: {r.text[:100]}")
ck("and is told where it actually goes", "board" in r.text.lower(),
   r.text[:110])
ck("no session came out of it",
   TestClient(main.app).get("/api/auth/me").status_code == 401)

print("\nwhat it DOES open, and the shape of what that buys")
fresh()
board = TestClient(main.app)
r = board.post("/api/craxlearn/room", json={"code": slotA["code"]})
ck("the same code opens the room at the board", r.status_code == 200,
   r.text[:120])
room = r.json()
ck("it names the class and the subject",
   room.get("class_id") == A["id"] and room.get("subject") == "Maths",
   str(room)[:120])
ck("and hands over a board token", bool(room.get("board_token")))
H = {"X-Board-Token": room.get("board_token")}
ck("STILL no session — this is the whole point",
   board.get("/api/auth/me").status_code == 401)
ck("the token cannot read the register",
   board.get(f"/api/teacher/class/{A['id']}/roster",
             headers=H).status_code in (401, 403))
ck("nor the class's discussion",
   board.get(f"/api/class/{A['id']}/discussion",
             headers=H).status_code in (401, 403))
ck("nor the school's fees",
   board.get("/api/office/fees", headers=H).status_code in (401, 403))
ck("but it CAN file a lesson into the room it names",
   board.post("/api/craxlearn/board/save",
              json={"topic": f"Fractions {st}", "title": f"Fractions {st}",
                    "lesson": {"steps": [{"t": "A half is one over two."}]}},
              headers=H).status_code == 200)

print("\nthe ten digits are a different thing and still work")
fresh()
adm = TestClient(main.app)
r = adm.post("/api/auth/code", json={"code": HEAD})
ck("an admin code signs the administrator in", r.status_code == 200,
   r.text[:120])
ck("as the school admin", (r.json() or {}).get("kind") == "school admin",
   r.text[:110])

print("\nwhat the sign-in refuses")
fresh()
r = TestClient(main.app).post("/api/auth/code", json={"code": "T-ZZZZ"})
ck("a code nobody holds", r.status_code == 404, f"got {r.status_code}")
fresh()
k = db.get(main.Klass, A["id"])
r = TestClient(main.app).post("/api/auth/code", json={"code": k.join_code})
ck("a pupil's class code is not a staff sign-in", r.status_code == 404,
   f"got {r.status_code}")

print("\nrotation takes a leaked code out of circulation")
rot = head.post(f"/api/head/slot/{slotA['id']}/rotate")
ck("the office can rotate it", rot.status_code == 200, rot.text[:110])
newcode = (rot.json() or {}).get("code", "")
fresh()
ck("the old code opens nothing",
   TestClient(main.app).post("/api/craxlearn/room",
                             json={"code": slotA["code"]}).status_code == 404)
fresh()
ck("the new one opens the same room",
   TestClient(main.app).post("/api/craxlearn/room",
                             json={"code": newcode}).status_code == 200)
# And the teacher is untouched by any of it. Their identity is not the code.
ck("the teacher's own session still works",
   TEACH.get("/api/auth/me").status_code == 200)
ck("and they still hold both subjects",
   len((TEACH.get("/api/teacher/classes").json().get("posts") or [])) == 2)

# Last, deliberately. Signing in on a second client signs the first one out —
# one account, one device, which is a rule of this product — so proving the
# password works has to come after everything that uses the first session.
fresh()
ck("and the password the office handed over is what gets them in",
   TestClient(main.app).post(
       "/api/auth/login",
       json={"email": TEMAIL, "password": TPW}).status_code == 200)

db.close()
print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
