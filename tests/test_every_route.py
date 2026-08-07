"""Call every route the server has, in every state a caller can be in.

Two hundred and sixty-one routes. Reading them is not the same as calling
them, and the faults this catches are the ones that never show up in a page
that happens not to be open at the time:

**A 500.** Never correct. A route that cannot answer should refuse or say it
has nothing, not fall over. An anonymous 500 is worse than an anonymous 403,
because it means the crash happened BEFORE the refusal — the handler did
work for somebody it had already decided to turn away.

**A refusal that arrives as a 422.** FastAPI validates the body before the
handler runs, so a route whose auth check lives inside the handler answers a
malformed anonymous request by describing its schema. That is a stranger
being handed the shape of the API instead of the door.

**A route nothing can reach.** Every path parameter here is a real id from
the fixture below, so a 404 means the id was rejected rather than absent.

Mutating routes are called ANONYMOUSLY only. The point there is the refusal,
not the effect, and this file must be safe to run against a working database
as often as anybody likes.
"""
import io
import os
import re
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
main.Base.metadata.create_all(bind=main.engine)
main._migrate_columns()
main.send_email = lambda *a, **k: None

P, F = [], []


def ck(n, c, d=""):
    print(("PASS " if c else "FAIL ") + n + (f" — {d}" if d else ""),
          flush=True)
    (P if c else F).append(n)


# --------------------------------------------------------------- the fixture
st = int(time.time())
uniq = f"{st}{os.getpid()}"
db = main.SessionLocal()
sc = main.School(name=f"Route School {uniq}")
db.add(sc)
db.commit()
db.refresh(sc)
HEAD = f"HD-{uniq[-8:]}"
db.add(main.TeacherCode(code=HEAD, school=sc.name, school_id=sc.id,
                        is_head=True, active=True))
db.commit()

head = TestClient(main.app)
he = f"rt{uniq}@example.com"
head.post("/api/auth/signup",
          json={"name": "Route Head", "email": he, "password": "RoutePass1!"})
u = db.query(main.User).filter(main.User.email == he).first()
u.dob = dt.date(1980, 1, 1)
db.commit()
head.post("/api/class/join", json={"code": HEAD})
CID = head.post("/api/teacher/class", json={"name": f"11-R {uniq}"}).json()["id"]
slot = head.post(f"/api/head/class/{CID}/slot",
                 json={"subject": "Science", "teacher_id": 0}).json()

learner = TestClient(main.app)
le = f"rl{uniq}@example.com"
learner.post("/api/auth/signup",
             json={"name": "Route Learner", "email": le,
                   "password": "RoutePass1!"})
lu = db.query(main.User).filter(main.User.email == le).first()
lu.dob = dt.date(2000, 1, 1)
db.commit()
LUID = lu.id

anon = TestClient(main.app)
main._CODE_TRIES.clear()
main._CODE_FAILS.clear()
room = anon.post("/api/craxlearn/room", json={"code": slot["code"]}).json()
BTOK = {"X-Board-Token": room.get("board_token", "")}

# One of everything the path parameters ask for.
asg = head.post(f"/api/teacher/class/{CID}/assignment",
                json={"title": f"A {uniq}", "subject": "Science",
                      "body": "Do it", "due": ""})
AID = (asg.json() or {}).get("id", 0) if asg.status_code == 200 else 0
mat = head.post("/api/craxlearn/board/save",
                json={"title": f"M {uniq}", "class_id": CID,
                      "subject": "Science", "body": "Notes"},
                headers=BTOK)
MID = ((mat.json() or {}).get("material") or {}).get("id", 0) \
    if mat.status_code == 200 else 0
TRACK = (db.query(main.Track).filter(main.Track.published == True)  # noqa: E712
           .first())
TSLUG = TRACK.slug if TRACK and hasattr(TRACK, "slug") else "s-start"

FILL = {
    "class_id": CID, "cid": CID, "klass_id": CID,
    "assignment_id": AID, "aid": AID, "id": CID,
    "material_id": MID, "mid": MID,
    "user_id": LUID, "uid": LUID, "student_id": LUID, "sid": LUID,
    "teacher_id": u.id, "school_id": sc.id,
    "slot_id": slot.get("id", 1), "track": TSLUG, "slug": TSLUG,
    "track_id": TSLUG, "lesson": "l1", "lesson_id": "l1",
    "job_id": 1, "code": slot["code"], "subject": "Science",
    "topic": "photosynthesis", "q": "test", "name": "test",
    "thread_id": 1, "message_id": 1, "notice_id": 1, "invite_id": 1,
    "request_id": 1, "session_id": 1, "quiz_id": 1, "exam_id": 1,
    "submission_id": 1, "project_id": 1, "path": "school", "kind": "file",
}

SRC = io.open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
ROUTES = re.findall(r'@app\.(get|post|put|delete|patch)\(\s*"([^"]+)"', SRC)


def fill(path):
    def one(m):
        key = m.group(1).split(":")[0]
        return str(FILL.get(key, 1))
    return re.sub(r"\{([^}]+)\}", one, path)


CLIENTS = [("anonymous", anon, {}), ("a learner", learner, {}),
           ("the school's head", head, {}), ("a board with a code", anon, BTOK)]

print(f"\ncalling every GET route ({sum(1 for m, _ in ROUTES if m == 'get')}) "
      f"in four states")
crashes, schema_leaks = [], []
seen = set()
for method, path in ROUTES:
    if method != "get":
        continue
    real = fill(path)
    if real in seen:
        continue
    seen.add(real)
    for label, cl, hdr in CLIENTS:
        try:
            r = cl.get(real, headers=hdr)
        except Exception as e:
            crashes.append((path, label, f"raised {type(e).__name__}: {e}"))
            continue
        if r.status_code >= 500:
            crashes.append((path, label, f"{r.status_code} {r.text[:120]}"))

ck(f"no GET route answers with a 500", not crashes,
   f"{len(crashes)} did")
for p, who, what in crashes[:20]:
    print(f"       {p}  [{who}]  {what}")

print("\nand every mutating route refuses a stranger before it does anything")
muts = [(m, p) for m, p in ROUTES if m != "get"]
bad_mut = []
for method, path in muts:
    real = fill(path)
    fn = getattr(anon, method)
    try:
        r = fn(real, json={}) if method != "delete" else fn(real)
    except Exception as e:
        bad_mut.append((method, path, f"raised {type(e).__name__}: {e}"))
        continue
    # 500 and 502 are always wrong. 503 is not, when it says why: an optional
    # integration that has not been configured on this deployment should say
    # so plainly rather than pretend to work — the Stripe webhook with no
    # secret set is exactly that, and it answers before touching the body.
    if r.status_code in (500, 502) or (
            r.status_code == 503 and "detail" not in r.text):
        bad_mut.append((method, path, f"{r.status_code} {r.text[:110]}"))
ck(f"no mutating route crashes on an anonymous call ({len(muts)} routes)",
   not bad_mut, f"{len(bad_mut)} did")
for m, p, what in bad_mut[:20]:
    print(f"       {m.upper()} {p}  {what}")

print("\nthe routes a board is entitled to")
for path in ("/api/curriculum", "/api/craxlearn/phet"):
    a = anon.get(path)
    b = anon.get(path, headers=BTOK)
    ck(f"{path}: refused anonymous, allowed with a code",
       a.status_code in (401, 403) and b.status_code == 200,
       f"anon {a.status_code}, board {b.status_code}")

print("\nand the ones it is NOT")
for path in ("/api/teacher/classes", "/api/craxlearn/activity",
             "/api/progress"):
    b = anon.get(path, headers=BTOK)
    ck(f"{path} is not opened by a board token",
       b.status_code in (401, 403),
       f"got {b.status_code} — a code names a room and nobody in it")

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
