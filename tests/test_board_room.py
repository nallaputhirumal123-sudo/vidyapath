"""A code tells the board which room it is standing in. It signs nobody in.

The board at the front of a class needs to know where it is — which class and
which subject — so a lesson taught on it is filed where the class will look
for it. Two codes name that: the class code names the room, the subject code
names the room and the subject.

The obvious build was to let a subject code sign the teacher in, since that is
exactly what the same code does at /api/class/join. On a shared screen at the
front of a classroom it is not the same thing at all: the code has been read
by every child in the room, and a session handed out on the strength of it is
a session handed to all of them.

So this route answers "where am I" and nothing else. Identity still comes from
signing in. That is the decision this suite pins — the absence of a session is
the feature.
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
sc = main.School(name=f"Room School {st}")
db.add(sc); db.commit(); db.refresh(sc)
HEAD = f"HEAD-R{str(st)[-4:]}"
db.add(main.TeacherCode(code=HEAD, school=sc.name, school_id=sc.id,
                        is_head=True, active=True))
db.commit()

head = TestClient(main.app)
HE = f"rm{st}@example.com"
head.post("/api/auth/signup", json={"name": "Principal R", "email": HE,
                                    "password": "RoomPass1!"})
u = db.query(main.User).filter(main.User.email == HE).first()
u.dob = dt.date(1983, 2, 2); db.commit()
head.post("/api/class/join", json={"code": HEAD})

mk = head.post("/api/teacher/class", json={"name": f"9-R {st}"}).json()
CID, CLASS_CODE = mk["id"], mk["join_code"]
head.post(f"/api/teacher/class/{CID}/roster", json={"names": "Priya K, 901"})
sci = head.post(f"/api/head/class/{CID}/slot",
                json={"subject": "Science", "teacher_id": 0}).json()
SUBJ_CODE = sci["code"]

# A teacher on that subject, so the room can say who teaches it.
tch = TestClient(main.app)
TE = f"rmt{st}@example.com"
tch.post("/api/auth/signup", json={"name": "Rao Science",
                                   "email": TE, "password": "RoomPass1!"})
_t = db.query(main.User).filter(main.User.email == TE).first()
_t.dob = dt.date(1987, 4, 4); db.commit()
tch.post("/api/class/join", json={"code": SUBJ_CODE})

board = TestClient(main.app)     # nobody signed in — a bare screen in a room

print("\na class code names the room")
fresh()
r = board.post("/api/craxlearn/room", json={"code": CLASS_CODE})
ck("it resolves", r.status_code == 200, r.text[:120])
d = r.json()
ck("as a class", d.get("kind") == "class", str(d.get("kind")))
ck("and names it", d.get("class_name", "").startswith("9-R"), str(d.get("class_name")))
ck("and lists the subjects taught in it",
   any(x.get("subject") == "Science" for x in d.get("subjects", [])),
   str(d.get("subjects")))
ck("with who teaches each",
   any(x.get("teacher") == "Rao Science" for x in d.get("subjects", [])),
   str(d.get("subjects")))

print("\na subject code names the room AND the subject")
fresh()
r = board.post("/api/craxlearn/room", json={"code": SUBJ_CODE})
ck("it resolves", r.status_code == 200, r.text[:120])
d = r.json()
ck("as a subject", d.get("kind") == "subject", str(d.get("kind")))
ck("in the right class", d.get("class_id") == CID, str(d.get("class_id")))
ck("and names the subject", d.get("subject") == "Science", str(d.get("subject")))
ck("and its teacher", d.get("teacher") == "Rao Science", str(d.get("teacher")))

print("\nand it signs NOBODY in — this is the point")
ck("the board still has no session",
   board.get("/api/auth/me").status_code in (401, 403),
   str(board.get("/api/auth/me").status_code))
ck("so it cannot save a lesson on the strength of a code",
   board.post("/api/craxlearn/board/save",
              json={"class_id": CID, "subject": "Science",
                    "topic": "sneaky", "lesson": {"steps": [{"t": "x"}]}}
              ).status_code in (401, 403))
ck("nor read the class's discussion",
   board.get(f"/api/class/{CID}/discussion").status_code in (401, 403))
ck("nor the register",
   board.get(f"/api/teacher/class/{CID}/roster").status_code in (401, 403))

print("\na wrong code is refused, and costs the same as guessing a register")
fresh()
r = board.post("/api/craxlearn/room", json={"code": "T-ZZZZ"})
ck("an unknown subject code is not found", r.status_code == 404,
   f"got {r.status_code}")
fresh()
r = board.post("/api/craxlearn/room", json={"code": "VP-NOPE99"})
ck("an unknown class code is not found", r.status_code == 404,
   f"got {r.status_code}")

print("\nthe signed-in teacher still saves where the room says")
r = tch.post("/api/craxlearn/board/save",
             json={"class_id": CID, "subject": "Science",
                   "topic": f"Refraction {st}", "title": f"Refraction {st}",
                   "lesson": {"steps": [{"t": "Light bends when it changes medium."}]}})
ck("a real teacher can save into that class and subject",
   r.status_code == 200, r.text[:130])
mats = tch.get(f"/api/class/{CID}/materials").json().get("materials", [])
ck("and it lands under the subject",
   any(m.get("subject") == "Science" and f"Refraction {st}" in (m.get("title") or "")
       for m in mats), str(mats)[:150])

print("\nthe student sign-in is untouched")
fresh()
r = board.post("/api/craxlearn/code", json={"code": CLASS_CODE})
ck("the class code still returns the register",
   r.status_code == 200 and r.json().get("roster_ready") is True, r.text[:110])
fresh()
r = board.post("/api/craxlearn/code", json={"code": SUBJ_CODE})
ck("and a subject code is still not a register",
   r.status_code == 404, f"got {r.status_code}")

db.close()
print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
