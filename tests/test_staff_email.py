"""An account a head creates must be one the login form will accept.

A head typed latha@bhashyam.100 into "Add teacher". The route took it, made
the account, printed a one-time password and said "Lathas can sign in now."
They could not, and never would: StaffIn.email was a plain string with a
minimum length, while LoginIn.email is EmailStr, so the address was refused
at the sign-in form before the password was even looked at.

Everyone involved — the head, the teacher, and me — assumed the password or
the class code was wrong. Neither was. The account was unusable from the
moment it was created, and nothing on the way in said so.

Two forms validating the same field differently is the whole bug, so that is
what this pins: whatever create accepts, login must accept.

It also covers the two repairs that did not exist. A mistyped address could
not be corrected — removing the member of staff left the User row holding the
address, so it could not even be reused — and a one-time password shown once
could not be reissued to somebody who closed the tab.
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
sc = main.School(name=f"Email School {st}")
db.add(sc); db.commit(); db.refresh(sc)
HEAD = f"HEAD-E{str(st)[-4:]}"
db.add(main.TeacherCode(code=HEAD, school=sc.name, school_id=sc.id,
                        is_head=True, active=True))
db.commit()

head = TestClient(main.app)
HEAD_EMAIL = f"eh{st}@example.com"
head.post("/api/auth/signup", json={"name": "Principal E", "email": HEAD_EMAIL,
                                    "password": "HeadPass1!"})
u = db.query(main.User).filter(main.User.email == HEAD_EMAIL).first()
u.dob = dt.date(1985, 1, 1); db.commit()
head.post("/api/class/join", json={"code": HEAD})

print("\nthe address that could not sign in")
r = head.post("/api/head/staff",
              json={"name": "Latha B", "email": "latha@bhashyam.100",
                    "role": "teacher"})
ck("an address with an invalid top-level domain is refused at creation",
   r.status_code == 422, f"got {r.status_code}")
# And the refusal has to be readable. FastAPI answers 422 with a LIST of
# {loc, msg}; a client that stringifies that shows "[object Object]", which
# is what the head actually saw.
if r.status_code == 422:
    d = r.json().get("detail")
    ck("the refusal says which field and why",
       isinstance(d, list) and d and "email" in str(d[0].get("loc", ""))
       and "valid email" in d[0].get("msg", "").lower(),
       str(d)[:90])

print("\nwhatever creation accepts, sign-in must accept")
GOOD = f"latha{st}@example.com"
r = head.post("/api/head/staff",
              json={"name": "Latha B", "email": GOOD, "role": "teacher"})
ck("a real address is accepted", r.status_code == 200, r.text[:120])
temp = (r.json() or {}).get("temporary_password", "")
ck("and a one-time password comes back", len(temp) > 6)

fresh = TestClient(main.app)
r = fresh.post("/api/auth/login", json={"email": GOOD, "password": temp})
ck("THE ACCOUNT CAN ACTUALLY SIGN IN", r.status_code == 200, r.text[:120])
ck("and it is a teacher",
   bool(fresh.get("/api/auth/me").json().get("is_teacher")))

print("\ncorrecting an address that was typed wrongly")
# Made directly, because the route now refuses to create one — which is the
# point. Schools already have these rows from before the fix.
bad = main.User(name="Old Typo", email=f"typo{st}@bhashyam.100",
                password_hash=main.hash_pw("x" * 12), is_active=True)
db.add(bad); db.commit(); db.refresh(bad)
main._grant_teacher(db, bad, sc.name, sc.id, "teacher")
db.commit()
BAD_ID = bad.id

r = TestClient(main.app).post("/api/auth/login",
                              json={"email": f"typo{st}@bhashyam.100",
                                    "password": "x" * 12})
ck("the old broken account cannot sign in (this is the reported bug)",
   r.status_code == 422, f"got {r.status_code}")

FIXED = f"typo{st}@example.com"
r = head.patch(f"/api/head/staff/{BAD_ID}", json={"email": FIXED})
ck("a head can correct the address", r.status_code == 200, r.text[:140])
db.expire_all()
ck("the SAME account is corrected, not replaced",
   db.get(main.User, BAD_ID).email == FIXED,
   str(db.get(main.User, BAD_ID).email))
r = TestClient(main.app).post("/api/auth/login",
                              json={"email": FIXED, "password": "x" * 12})
ck("and now they can sign in with their existing password",
   r.status_code == 200, r.text[:120])

print("\nreissuing a password somebody did not write down")
r = head.patch(f"/api/head/staff/{BAD_ID}", json={"new_password": True})
ck("a head can issue a new one", r.status_code == 200, r.text[:120])
newpw = (r.json() or {}).get("temporary_password", "")
ck("it comes back once", len(newpw) > 6)
ck("the new password works",
   TestClient(main.app).post("/api/auth/login",
                             json={"email": FIXED, "password": newpw}).status_code == 200)
ck("and the old one no longer does",
   TestClient(main.app).post("/api/auth/login",
                             json={"email": FIXED, "password": "x" * 12}).status_code == 401)

print("\nwhat a head must not be able to do")
r = head.patch(f"/api/head/staff/{BAD_ID}", json={"email": GOOD})
ck("take an address another account already uses", r.status_code == 409,
   f"got {r.status_code}")

# A class-code pupil has no password by design; issuing one would create a
# second way into a child's account.
k = main.Klass(name=f"7-Z {st}", join_code=f"VP-EM{st % 10000:04d}",
               teacher_id=0, school=sc.name, school_id=sc.id)
db.add(k); db.commit(); db.refresh(k)
db.add(main.RosterName(class_id=k.id, name="Kid E", claimed_by=0))
db.commit()
main._CODE_TRIES.clear(); main._CODE_FAILS.clear()
kid = TestClient(main.app)
row = kid.post("/api/craxlearn/code", json={"code": k.join_code}).json()["names"][0]
kid.post("/api/craxlearn/claim", json={"code": k.join_code, "roster_id": row["id"]})
KID_ID = kid.get("/api/auth/me").json().get("id")
r = head.patch(f"/api/head/staff/{KID_ID}", json={"new_password": True})
ck("give a pupil's class-code account a password", r.status_code in (400, 403),
   f"got {r.status_code}")

print("\na pupil must never become staff")
# A staff list showed "thirumal · teacher · roster1.60b0f2a9@classcode.invalid"
# — a child's class-code account holding teacher access at the school. The
# route in was Join with code: a pupil signs in by tapping their name, then
# types a subject code (the six characters chalked on a board and passed
# around a class) and comes out the other side able to read every register,
# mark and message in the school.
slot = main.SubjectSlot(class_id=k.id, subject="Physics",
                        code=main._gen_slot_code(db), teacher_id=0,
                        status="open")
db.add(slot); db.commit(); db.refresh(slot)
r = kid.post("/api/class/join", json={"code": slot.code})
ck("a pupil entering a teacher code is refused", r.status_code == 403,
   f"got {r.status_code}: {r.text[:90]}")
db.expire_all()
ck("and gains no staff access at all",
   db.query(main.TeacherAccess).filter(
       main.TeacherAccess.user_id == KID_ID).first() is None)
ck("their own account still works",
   kid.get("/api/auth/me").status_code == 200)
ck("and it is still not a teacher",
   not kid.get("/api/auth/me").json().get("is_teacher"),
   str(kid.get("/api/auth/me").json().get("is_teacher")))

# The head code is the more serious one: it would have made a child the
# administrator of the school.
r = kid.post("/api/class/join", json={"code": HEAD})
ck("nor can a pupil redeem the head-teacher code", r.status_code == 403,
   f"got {r.status_code}")

# And the legitimate path still works, so this is a guard and not a wall.
tch = TestClient(main.app)
TE = f"et{st}@example.com"
tch.post("/api/auth/signup", json={"name": "Real Teacher",
                                   "email": TE, "password": "RealPass1!"})
_u = db.query(main.User).filter(main.User.email == TE).first()
_u.dob = dt.date(1990, 5, 5); db.commit()
r = tch.post("/api/class/join", json={"code": slot.code})
ck("an ordinary account with the same code still becomes a teacher",
   r.status_code == 200 and r.json().get("role") == "teacher", r.text[:110])

outsider = TestClient(main.app)
OE = f"eo{st}@example.com"
outsider.post("/api/auth/signup", json={"name": "Outsider E", "email": OE,
                                        "password": "OutPass1!"})
r = outsider.patch(f"/api/head/staff/{BAD_ID}", json={"email": "x@example.com"})
ck("an ordinary account cannot edit staff at all",
   r.status_code in (401, 403), f"got {r.status_code}")

r = head.patch(f"/api/head/staff/{BAD_ID}", json={})
ck("an empty edit is refused rather than reporting success",
   r.status_code == 400, f"got {r.status_code}")

db.close()
print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
