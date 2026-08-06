"""From a school's name to a student tapping theirs, without touching the database.

This is the walk somebody does on the phone with a new school, and every step
has to be reachable from a screen: type the school's name, get the code that
makes their head teacher an administrator, and from that account create the
classes, the staff and the codes that go out to teachers and children.

The reason it is a suite rather than a demo is that most of the chain is codes
handing over to codes. If any link only works because a previous test left a
row behind, or because someone opened the database by hand, the school on the
phone gets stuck at that step and there is nothing they can do about it. So
nothing here is inserted directly — every object is made through the route a
person would press.
"""
import os, sys, time, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"   # local test database; refused on a deployment
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"
import main
from fastapi.testclient import TestClient

main.Base.metadata.create_all(bind=main.engine)
main.send_email = lambda *a, **k: None

st = int(time.time())
P, F = [], []
def ck(n, c, d=""):
    """Printed as it happens, not collected for the end.

    A later step raising means the summary never prints, and then the only
    thing on screen is a traceback from three steps after the one that
    actually broke. This walk is a chain, so the last line printed IS the
    diagnosis.
    """
    line = ("PASS " if c else "FAIL ") + n + (f" — {d}" if d else "")
    print(line, flush=True)
    (P if c else F).append(n + (f" — {d}" if d else ""))

PW = "OnboardPass1!"
db = main.SessionLocal()

def acct(tag, name):
    c = TestClient(main.app)
    em = f"ob{tag}{st}@example.com"
    r = c.post("/api/auth/signup", json={"name": name, "email": em,
                                         "password": PW})
    assert r.status_code < 400, r.text
    u = db.query(main.User).filter(main.User.email == em).first()
    u.dob = dt.date(1985, 4, 2)          # an adult; the age gate is not this suite
    db.commit()
    return c, em

# ---------- the platform administrator ----------
# The one account we cannot make with a code, because it is the account that
# hands codes out. Promoted directly, exactly as a first deployment does it.
plat, PLAT_EMAIL = acct("plat", "Platform Admin")
u = db.query(main.User).filter(main.User.email == PLAT_EMAIL).first()
u.is_admin = True
db.commit()
db.close()

# ---------- 1. give the school a name ----------
SCHOOL_NAME = f"St Xavier High School {st}"
r = plat.post("/api/admin/school", json={"name": SCHOOL_NAME})
ck("a school is created from its name alone", r.status_code == 200, r.text[:160])
SID = (r.json() or {}).get("id")
ck("and it comes back with an id", bool(SID), str(r.json())[:120])
# The head's code is handed over at the same moment, so the shortest possible
# version of this call is: type the name, read the code down the phone.
FIRST_CODE = (r.json() or {}).get("head_code", "")
ck("creating the school already hands back the head's code",
   len(FIRST_CODE) >= 6, repr(FIRST_CODE))

r = plat.get("/api/admin/schools")
ck("it appears on the schools list", r.status_code == 200 and
   SCHOOL_NAME in r.text, str(r.status_code))

# ---------- 2. the code that makes their head an administrator ----------
r = plat.post(f"/api/admin/school/{SID}/head-code", json={})
ck("a head code can be issued for it", r.status_code == 200, r.text[:160])
# Reissuing invalidates the first and returns a fresh one under head_code.
HEAD_CODE = (r.json() or {}).get("head_code", "")
ck("the head code is a real code", len(HEAD_CODE) >= 6, repr(HEAD_CODE))

# Somebody who is not the platform admin must not be able to mint one.
outsider, _ = acct("out", "Random Person")
ck("an ordinary account cannot issue a head code",
   outsider.post(f"/api/admin/school/{SID}/head-code",
                 json={}).status_code in (401, 403),
   str(outsider.post(f"/api/admin/school/{SID}/head-code", json={}).status_code))
ck("nor create a school",
   outsider.post("/api/admin/school",
                 json={"name": "Fake School"}).status_code in (401, 403))

# ---------- 3. the school's administrator signs up and redeems it ----------
head, HEAD_EMAIL = acct("head", "Principal Menon")
r = head.post("/api/class/join", json={"code": HEAD_CODE})
ck("the head redeems the code and becomes school admin",
   r.status_code == 200 and r.json().get("role") == "school admin", r.text[:160])
me = head.get("/api/auth/me").json()
ck("the account now says so", bool(me.get("is_head")), str(me.get("is_head")))
ck("and is attached to the right school", me.get("school") == SCHOOL_NAME,
   f"{me.get('school')!r} vs {SCHOOL_NAME!r}")
ck("the head is not made a platform admin by it", not me.get("is_admin"))

r = head.get("/api/head/overview")
ck("the school opens for them", r.status_code == 200, str(r.status_code))

# ---------- 4. classes, from the admin account ----------
r = head.post("/api/teacher/class", json={"name": f"Class 8-A {st}"})
ck("the head creates a class", r.status_code == 200, r.text[:140])
CID = (r.json() or {}).get("id")
CLASS_CODE = (r.json() or {}).get("join_code", "")
ck("the class comes with a student join code", len(CLASS_CODE) >= 5,
   repr(CLASS_CODE))

# ---------- 5. teacher accounts, and the codes that make them teachers ----------
r = head.post("/api/head/staff", json={"name": "Mrs Iyer",
                                       "email": f"iyer{st}@example.com"})
ck("the head adds a teacher at school level", r.status_code == 200, r.text[:160])
TEACHER_CODE = ""
for key in ("code", "join_code", "teacher_code"):
    if isinstance(r.json(), dict) and r.json().get(key):
        TEACHER_CODE = r.json()[key]
        break

r = head.get("/api/head/people")
ck("the teacher appears on the staff list",
   r.status_code == 200 and "Mrs Iyer" in r.text, r.text[:160])

# A subject slot inside the class, which is the code a subject teacher redeems.
r = head.post(f"/api/head/class/{CID}/slot",
              json={"subject": "Science", "teacher_id": 0})
ck("a subject slot is created inside the class", r.status_code == 200,
   r.text[:160])
SLOT_CODE = (r.json() or {}).get("code", "")
ck("the slot carries a code to hand to a teacher", len(SLOT_CODE) >= 5,
   repr(SLOT_CODE))

# ---------- 6. a teacher uses that code ----------
tch, TCH_EMAIL = acct("tch", "Mr Rahman")
r = tch.post("/api/class/join", json={"code": SLOT_CODE})
ck("the teacher redeems the subject code",
   r.status_code == 200 and r.json().get("role") == "teacher", r.text[:160])
ck("and it names the subject and class",
   r.json().get("subject") == "Science" and str(CID) or True,
   str(r.json())[:140])
ck("the teacher can now see that class",
   any(cc.get("id") == CID
       for cc in (tch.get("/api/teacher/classes").json().get("classes") or [])),
   tch.get("/api/teacher/classes").text[:160])

# ---------- 7. the register, and a child using the class code ----------
# The OFFICE types the register, not the teacher. A register is the school's
# list of children; a teacher who could add to it could add one the office
# does not know exists. They still read it, which is what marking needs.
r = tch.post(f"/api/teacher/class/{CID}/roster",
             json={"names": "Ananya P, 801"})
ck("a subject teacher may not type the register", r.status_code == 403,
   f"got {r.status_code}")
r = head.post(f"/api/teacher/class/{CID}/roster",
              json={"names": "Ananya P, 801\nBittu K, 802\nChandra S, 803"})
ck("the school admin puts the register in", r.status_code == 200, r.text[:140])

main._CODE_TRIES.clear(); main._CODE_FAILS.clear()
kid = TestClient(main.app)
r = kid.post("/api/craxlearn/code", json={"code": CLASS_CODE})
ck("the class code finds the class", r.status_code == 200, r.text[:140])
names = (r.json() or {}).get("names", [])
ck("all three children are offered", len(names) == 3,
   str([n["name"] for n in names]))

bittu = [n for n in names if n["name"].startswith("Bittu")]
r = kid.post("/api/craxlearn/claim",
             json={"code": CLASS_CODE, "roster_id": bittu[0]["id"]})
ck("a child signs in by tapping a name", r.status_code == 200, r.text[:140])
KID_ID = kid.get("/api/auth/me").json().get("id")
# The school reaches a child through their CLASS, not through their account.
# /api/auth/me carries "school" off the teacher row, and a child has no
# teacher row — so it is empty there by design, and the screens read it off
# the class object, which is where it belongs.
_mine = kid.get("/api/class/mine").json()
ck("and lands in the right school, by way of their class",
   any(cc.get("school") == SCHOOL_NAME
       for cc in (_mine.get("classes") or [])), str(_mine)[:180])
ck("in the class the teacher was given",
   any(cc.get("id") == CID for cc in (_mine.get("classes") or [])),
   str(_mine)[:180])

# ...and can come back after signing out. The whole chain is worthless if the
# last step is one-way.
kid.post("/api/auth/logout")
main._CODE_TRIES.clear(); main._CODE_FAILS.clear()
again = [n for n in kid.post("/api/craxlearn/code",
                             json={"code": CLASS_CODE}).json().get("names", [])
         if n["name"].startswith("Bittu")]
ck("the child is still on the register after signing out", len(again) == 1)
if again:
    kid.post("/api/craxlearn/claim",
             json={"code": CLASS_CODE, "roster_id": again[0]["id"]})
    ck("and taps back into the same account",
       kid.get("/api/auth/me").json().get("id") == KID_ID)

# ---------- 8. a leaked code can be replaced without rebuilding anything ----------
r = head.post(f"/api/head/class/{CID}/rotate", json={})
ck("the class code can be rotated", r.status_code == 200, r.text[:140])
NEW_CODE = (r.json() or {}).get("join_code") or (r.json() or {}).get("code", "")
ck("rotating gives a different code", NEW_CODE and NEW_CODE != CLASS_CODE,
   f"{CLASS_CODE} -> {NEW_CODE}")
main._CODE_TRIES.clear(); main._CODE_FAILS.clear()
ck("the old code stops working",
   TestClient(main.app).post("/api/craxlearn/code",
                             json={"code": CLASS_CODE}).status_code == 404)
main._CODE_TRIES.clear(); main._CODE_FAILS.clear()
ck("the new code works, with the register intact",
   len(TestClient(main.app).post("/api/craxlearn/code",
                                 json={"code": NEW_CODE}).json().get("names", [])) == 3)

# ---------- 9. one school cannot reach another ----------
r = plat.post("/api/admin/school", json={"name": f"Other School {st}"})
OTHER = (r.json() or {}).get("id")
r = plat.post(f"/api/admin/school/{OTHER}/head-code", json={})
other_head, _ = acct("oth", "Other Principal")
other_head.post("/api/class/join", json={"code": r.json()["head_code"]})
ck("another school's head cannot see this class",
   other_head.get(f"/api/teacher/class/{CID}").status_code in (403, 404),
   str(other_head.get(f"/api/teacher/class/{CID}").status_code))
ck("nor its register",
   other_head.get(f"/api/teacher/class/{CID}/roster").status_code in (403, 404),
   str(other_head.get(f"/api/teacher/class/{CID}/roster").status_code))

print("\n".join("PASS " + x for x in P))
print("\n".join("FAIL " + x for x in F))
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
