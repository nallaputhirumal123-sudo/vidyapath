"""A teacher the office added, who cannot sign in, and the screen that fixes it.

A staff account made from a school code gets a generated address ending
`.invalid`. That is right — it is a placeholder, not a mailbox — and it means
the person cannot sign in until somebody gives them a real one.

The route to do that has existed for a long time and had NO WAY IN. Worse,
the staff list hid the placeholder, on the reasoning that a fake address is
noise: so a teacher who was locked out looked exactly like one who was not,
and the only button on their row was Remove. A head with a locked-out
colleague had nothing to see and nothing to press, and the answer they were
given was to ask somebody to edit the database.

This pins the way in, and the two halves of it.

**It is named.** A placeholder reads "cannot sign in yet" rather than being
hidden, because the row is the only place anybody would notice.

**It is fixable from there.** One button, which sets a real address and hands
back a one-time password. The account is corrected rather than replaced, so
the classes they teach, the work they set and the marks they gave all stay
attached to the same row.
"""
import io
import os
import secrets
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


u = str(int(time.time())) + str(os.getpid())
db = main.SessionLocal()
sc = main.School(name=f"Fix School {u}")
db.add(sc)
db.commit()
db.refresh(sc)
hc = ("HFX" + u)[:12]
db.add(main.TeacherCode(code=hc, school=sc.name, school_id=sc.id,
                        is_head=True, active=True))
db.commit()
head = TestClient(main.app)
em = f"fx{u}@example.com"
head.post("/api/auth/signup",
          json={"name": "Fix Head", "email": em, "password": "FixPass1!"})
usr = db.query(main.User).filter(main.User.email == em).first()
usr.dob = dt.date(1980, 1, 1)
db.commit()
head.post("/api/class/join", json={"code": hc})

# Exactly the shape of the real one: a placeholder address and a password
# nobody holds.
ph = f"staff{secrets.token_hex(5)}@schoolcode.invalid"
t = main.User(name="Locked Out", email=ph,
              password_hash=main.hash_pw(secrets.token_urlsafe(9)))
db.add(t)
db.commit()
db.refresh(t)
db.add(main.TeacherAccess(user_id=t.id, school_id=sc.id, school=sc.name,
                          role="teacher"))
db.commit()

print("\nthe school can see there is something wrong")
lst = head.get("/api/head/staff")
ck("the staff list loads", lst.status_code == 200, str(lst.status_code))
rows = (lst.json() or {}).get("staff") or []
mine = [p for p in rows if (p.get("id") or p.get("user_id")) == t.id]
ck("and she is on it", bool(mine), str(len(rows)) + " rows")
ck("with the placeholder address still in the payload",
   bool(mine) and "schoolcode.invalid" in str(mine[0].get("email", "")),
   "the SCREEN decides what to show; hiding it in the API would leave the "
   "page unable to tell")

print("\nand the screen names it rather than hiding it")
IDX = io.open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
ck("there is one test for a placeholder", "function placeholderAddress(email)"
   in IDX)
ck("covering both kinds", 'e.indexOf("schoolcode.invalid") >= 0' in IDX
   and 'e.indexOf("classcode.invalid") >= 0' in IDX)
ck("and an empty address counts as one", "return !e ||" in IDX,
   "no address at all is the same problem as a fake one")
ck("the row says she cannot sign in",
   "cannot sign in yet" in IDX,
   "hidden, it looked identical to a teacher who could")

print("\nand there is a button on that row")
ck("the control exists", 'data-cls="stfix"' in IDX)
ck("it is wired", 'else if(k==="stfix") staffFix(' in IDX)
ck("and it reads as a repair when it is one",
   'placeholderAddress(p.email)?"Fix sign-in":"Edit"' in IDX,
   "the same button does an ordinary correction the rest of the time")
ck("a new account is given a password without asking",
   "body.new_password = placeholder" in IDX,
   "an address nobody can receive at has no password anybody holds either")
ck("but a working one is not signed out by surprise",
   'confirm("Also issue a new one-time password?' in IDX,
   "issuing one ends every session they have")
ck("the password is shown once, and says so",
   "it is not shown again" in IDX,
   "it is stored as a hash; there is no second chance to read it")
ck("and says another can be issued", "another from this screen" in IDX,
   "'shown once' with no way to reissue is how somebody is locked out twice")

print("\nand it actually unlocks her")
real = f"locked{u}@school.example"
fix = head.patch(f"/api/head/staff/{t.id}",
                 json={"email": real, "new_password": True, "name": ""})
ck("the head may correct it", fix.status_code == 200, fix.text[:110])
got = fix.json() or {}
ck("both the address and the password changed",
   set(got.get("changed") or []) >= {"email", "password"},
   str(got.get("changed")))
temp = got.get("temporary_password")
ck("a one-time password comes back", bool(temp))

anon = TestClient(main.app)
ok = anon.post("/api/auth/login", json={"email": real, "password": temp})
ck("and she can sign in with it", ok.status_code == 200, ok.text[:110])
# Read from a session that has not seen this row before. The one above was
# opened before the route ran and holds its own cached copy, so asking it
# would report what the row USED to say.
fresh = main.SessionLocal()
try:
    still = fresh.get(main.User, t.id)
    ck("the account was corrected, not replaced",
       still is not None and (still.email or "") == real,
       "the same row keeps its id, so her classes and marks stay hers")
finally:
    fresh.close()

print("\nand nobody else's school is reachable")
other = TestClient(main.app)
oe = f"other{u}@example.com"
other.post("/api/auth/signup",
           json={"name": "Other Head", "email": oe, "password": "OtherPass1!"})
ou = db.query(main.User).filter(main.User.email == oe).first()
ou.dob = dt.date(1980, 1, 1)
db.commit()
r = other.patch(f"/api/head/staff/{t.id}",
                json={"email": "hijack@example.com", "name": ""})
ck("a head of another school is refused", r.status_code in (401, 403),
   f"got {r.status_code}")

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
