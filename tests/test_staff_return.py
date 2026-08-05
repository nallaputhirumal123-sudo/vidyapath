"""A teacher and a school admin sign out, sign back in, and still hold everything.

The child's version of this was a genuine one-way door: a class-code account
has no email that receives and no password anybody knows, so hiding a claimed
name from the register destroyed the account. Staff are not built that way —
they have a real email and a real password — so the question here is different
and worth asking on its own: does what the CODE granted survive the session
that redeemed it?

Because the code is redeemed once, at join. If the subject, the school role,
or the class membership lived in the session rather than in a row, a teacher
would come back tomorrow signed in and empty-handed, holding a code that has
already been used. That is the failure this pins down.
"""
import os, sys, time, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"
import main
from fastapi.testclient import TestClient

main.Base.metadata.create_all(bind=main.engine)
main.send_email = lambda *a, **k: None

st = int(time.time())
db = main.SessionLocal()
P, F = [], []
def ck(n, c, d=""):
    (P if c else F).append(n + (f" — {d}" if d else ""))

PW = "StaffPass1!"
def acct(tag):
    c = TestClient(main.app)
    em = f"sr{tag}{st}@example.com"
    c.post("/api/auth/signup", json={"name": "Staff " + tag, "email": em,
                                     "password": PW})
    u = db.query(main.User).filter(main.User.email == em).first()
    u.dob = dt.date(1988, 6, 1)
    db.commit()
    return c, em

# A school, its head code, and an admin who redeems it.
sc = main.School(name=f"Return School {st}")
db.add(sc); db.commit(); db.refresh(sc)
HEAD = f"HEAD-R{str(st)[-4:]}"
db.add(main.TeacherCode(code=HEAD, school=sc.name, school_id=sc.id,
                        is_head=True, active=True))
db.commit()

adm, ADM_EMAIL = acct("adm")
r = adm.post("/api/class/join", json={"code": HEAD})
ck("the head code makes a school admin",
   r.status_code == 200 and r.json().get("role") == "school admin", r.text[:120])

CID = adm.post("/api/teacher/class", json={"name": f"10-C {st}"}).json()["id"]
adm.post(f"/api/teacher/class/{CID}/roster",
         json={"names": "Bittu K, 4101\nDeepa M, 4102"})

# A subject slot, and a teacher who claims it.
slot = main.SubjectSlot(class_id=CID, subject="Physics",
                        code=main._gen_slot_code(db), teacher_id=0,
                        status="open")
db.add(slot); db.commit(); db.refresh(slot)
SLOT_CODE = slot.code

tch, TCH_EMAIL = acct("tch")
r = tch.post("/api/class/join", json={"code": SLOT_CODE})
ck("the slot code makes a subject teacher",
   r.status_code == 200 and r.json().get("role") == "teacher", r.text[:120])
ck("and names the subject it granted", r.json().get("subject") == "Physics",
   str(r.json().get("subject")))

# Work set before signing out, so "still holds everything" is checked against
# something they made rather than against a flag.
r = tch.post(f"/api/teacher/class/{CID}/assignment",
             json={"subject": "Physics", "title": f"Refraction {st}",
                   "body": "Chapter 10, all of it", "due_date": ""})
ck("the teacher can set work before signing out", r.status_code == 200,
   r.text[:120])
AID = (r.json() or {}).get("id")

before = tch.get("/api/teacher/classes")
ck("the teacher has classes before signing out",
   before.status_code == 200 and len(before.json().get("classes") or []) >= 1,
   before.text[:120])

# ---------- out, and back in with the ordinary sign-in ----------
tch.post("/api/auth/logout")
ck("the teacher's session ends",
   tch.get("/api/auth/me").status_code in (401, 403))

back = TestClient(main.app)
r = back.post("/api/auth/login", json={"email": TCH_EMAIL, "password": PW})
ck("the teacher signs back in with email and password", r.status_code == 200,
   r.text[:120])

me = back.get("/api/auth/me").json()
ck("still a teacher, without redeeming the code again",
   bool(me.get("is_teacher")), str(me.get("is_teacher")))

after = back.get("/api/teacher/classes")
ck("the classes are still there", after.status_code == 200 and
   len(after.json().get("classes") or []) >= 1, after.text[:140])
ck("the same class, by id",
   any(c.get("id") == CID for c in (after.json().get("classes") or [])),
   after.text[:140])

subs = back.get(f"/api/class/{CID}/subjects")
ck("still holding Physics in it", subs.status_code == 200 and
   any((s.get("subject") == "Physics") for s in
       (subs.json().get("subjects") or [])), subs.text[:160])

cl = back.get(f"/api/teacher/class/{CID}")
ck("the work they set is still theirs", cl.status_code == 200 and
   f"Refraction {st}" in cl.text, str(cl.status_code))

ck("and they can still set more work",
   back.post(f"/api/teacher/class/{CID}/assignment",
             json={"subject": "Physics", "title": f"Lenses {st}",
                   "body": "next", "due_date": ""}).status_code == 200)

# Redeeming the same slot code again is their own code, so it must not fight
# them. A teacher who types it twice should not be told somebody else has it.
r = back.post("/api/class/join", json={"code": SLOT_CODE})
ck("their own code redeemed twice is not an error", r.status_code == 200,
   f"{r.status_code} {r.text[:100]}")

# ---------- the school admin, same round trip ----------
adm.post("/api/auth/logout")
ck("the admin's session ends",
   adm.get("/api/auth/me").status_code in (401, 403))

adm2 = TestClient(main.app)
r = adm2.post("/api/auth/login", json={"email": ADM_EMAIL, "password": PW})
ck("the admin signs back in", r.status_code == 200, r.text[:120])
# is_head, not is_admin. is_admin is the PLATFORM administrator — the person
# who creates schools. A head teacher is is_head, and conflating the two would
# have this suite pass only if the school's head could also run the platform.
_me = adm2.get("/api/auth/me").json()
ck("still the head of their school", bool(_me.get("is_head")),
   f"is_head={_me.get('is_head')} role={_me.get('role')}")
ck("and is not made a platform administrator by it",
   not _me.get("is_admin"), str(_me.get("is_admin")))
ov = adm2.get("/api/head/overview")
ck("the school is still theirs to run", ov.status_code == 200,
   str(ov.status_code))
ppl = adm2.get("/api/head/people")
ck("the teacher they appointed is still on the staff list",
   ppl.status_code == 200 and TCH_EMAIL.split("@")[0] in ppl.text
   or ppl.status_code == 200 and "Staff tch" in ppl.text, ppl.text[:160])

# ---------- and the child on that register can still come back ----------
# The same door, checked from the school side: Bittu is on this class's
# register, signs in by tapping the name, signs out, and must find the name
# still there. This is the bug that started all of this.
main._CODE_TRIES.clear(); main._CODE_FAILS.clear()
k = db.get(main.Klass, CID)
CODE = k.join_code
kid = TestClient(main.app)
d = kid.post("/api/craxlearn/code", json={"code": CODE}).json()
bittu = [n for n in d.get("names", []) if n["name"].startswith("Bittu")]
ck("Bittu is on the register", len(bittu) == 1, str(d.get("names")))
if bittu:
    r = kid.post("/api/craxlearn/claim",
                 json={"code": CODE, "roster_id": bittu[0]["id"]})
    ck("Bittu signs in", r.status_code == 200, r.text[:120])
    uid = kid.get("/api/auth/me").json().get("id")
    kid.post("/api/auth/logout")
    main._CODE_TRIES.clear(); main._CODE_FAILS.clear()
    d2 = kid.post("/api/craxlearn/code", json={"code": CODE}).json()
    again = [n for n in d2.get("names", []) if n["name"].startswith("Bittu")]
    ck("Bittu is STILL on the register after signing out", len(again) == 1,
       str([n["name"] for n in d2.get("names", [])]))
    if again:
        r = kid.post("/api/craxlearn/claim",
                     json={"code": CODE, "roster_id": again[0]["id"]})
        ck("and taps back into the same account",
           r.status_code == 200 and
           kid.get("/api/auth/me").json().get("id") == uid, r.text[:120])

db.close()
print("\n".join("PASS " + x for x in P))
print("\n".join("FAIL " + x for x in F))
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
