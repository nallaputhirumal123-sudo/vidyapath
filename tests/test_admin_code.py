"""A school admin signs in with their code. No email, no password.

The last credential in the school half. A school administrator was created by
redeeming a ten-digit code onto an account they had already made with an email
and a password — which is two steps and one credential too many for somebody
whose only instruction was "here is your code".

The code now carries what it needs to be a sign-in on its own:

  label       whose code it is, given when it is issued. An account has to be
              called something and a code cannot invent a name, so a code
              with no name on it is refused rather than creating an
              "Administrator" nobody can tell from the other three.
  claimed_by  the account it made. Entering it a second time returns to the
              SAME administrator. This is the rule the class register learned
              expensively this morning, where hiding a claimed name meant
              signing out destroyed the account for good.
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
    print(("PASS " if c else "FAIL ") + n + (f" - {d}" if d else ""), flush=True)
    (P if c else F).append(n)

def fresh():
    main._CODE_TRIES.clear(); main._CODE_FAILS.clear()

db = main.SessionLocal()
plat = TestClient(main.app)
PE = f"ac{st}@example.com"
plat.post("/api/auth/signup", json={"name": "Platform", "email": PE,
                                    "password": "AdminCode1!"})
pu = db.query(main.User).filter(main.User.email == PE).first()
pu.is_admin = True
pu.dob = dt.date(1980, 1, 1)
db.commit()

print("")
print("a school, and a code with a name on it")
r = plat.post("/api/admin/school",
              json={"name": f"Code Admin School {st}",
                    "admin_name": "Principal Nair"})
ck("the school is made", r.status_code == 200, r.text[:120])
SID = r.json()["id"]
CODE = r.json()["head_code"]
ck("the code is ten digits", len(CODE) == 10, CODE)
ck("and it carries the name", r.json().get("admin_name") == "Principal Nair",
   str(r.json()))

print("")
print("the code is the whole sign-in")
fresh()
a1 = TestClient(main.app)
r = a1.post("/api/auth/code", json={"code": CODE})
ck("it signs somebody in", r.status_code == 200, r.text[:140])
ck("as a school admin", r.json().get("kind") == "school admin", str(r.json()))
ck("named as the code said", r.json().get("name") == "Principal Nair",
   str(r.json().get("name")))
ck("and it is a first use", r.json().get("returning") is False)
me = a1.get("/api/auth/me").json()
AID = me.get("id")
ck("the session is real and is the head", bool(me.get("is_head")), str(me))
ck("they can run the school",
   a1.get("/api/head/overview").status_code == 200,
   str(a1.get("/api/head/overview").status_code))

print("")
print("and using it again comes back to the SAME account")
a1.post("/api/auth/logout")
fresh()
a2 = TestClient(main.app)
r = a2.post("/api/auth/code", json={"code": CODE})
ck("it signs in again", r.status_code == 200, r.text[:120])
ck("and says so", r.json().get("returning") is True, str(r.json()))
ck("the same account, not a second administrator",
   a2.get("/api/auth/me").json().get("id") == AID,
   f"{a2.get(chr(34)+chr(47)+chr(97)+chr(112)+chr(105)+chr(47)+chr(97)+chr(117)+chr(116)+chr(104)+chr(47)+chr(109)+chr(101)+chr(34))}")
db.expire_all()
# Counted against THIS code, not by name. Every previous run of this suite
# left its own "Principal Nair" in the development database, so counting the
# name counts other runs and fails on correct behaviour — the same trap that
# caught an earlier suite counting "Asha Rao".
_code_row = (db.query(main.TeacherCode)
               .filter(main.TeacherCode.code == CODE).first())
ck("the code records the one account it made",
   _code_row is not None and _code_row.claimed_by == AID,
   f"{getattr(_code_row, 'claimed_by', None)} vs {AID}")

print("")
print("no email address anybody can use, and no password anybody knows")
u = db.get(main.User, AID)
ck("the address is unroutable", u.email.endswith("@schoolcode.invalid"), u.email)
ck("and it is marked as a code account", (u.kind or "") == "schoolcode", u.kind)
ck("signing in with that address is impossible",
   TestClient(main.app).post("/api/auth/login",
       json={"email": u.email, "password": "x" * 12}).status_code in (401, 422))

print("")
print("a second administrator gets their own code and their own account")
r = plat.post(f"/api/admin/school/{SID}/head-code", json={"name": "Mr Menon"})
CODE2 = r.json()["head_code"]
ck("issued without cancelling the first", r.json().get("revoked") == 0,
   str(r.json()))
fresh()
b1 = TestClient(main.app)
r = b1.post("/api/auth/code", json={"code": CODE2})
ck("the second code signs in", r.status_code == 200, r.text[:120])
ck("as a different person", r.json().get("name") == "Mr Menon", str(r.json()))
ck("and a different account",
   b1.get("/api/auth/me").json().get("id") != AID)
fresh()
ck("the first code still works",
   TestClient(main.app).post("/api/auth/code",
                             json={"code": CODE}).status_code == 200)

print("")
print("what it refuses")
r = plat.post(f"/api/admin/school/{SID}/head-code", json={})
NONAME = r.json()["head_code"]
fresh()
r = TestClient(main.app).post("/api/auth/code", json={"code": NONAME})
ck("a code with no name on it does not invent an administrator",
   r.status_code == 409, f"got {r.status_code}")

codes = plat.get(f"/api/admin/school/{SID}/head-codes").json()
cid = [c["id"] for c in codes["codes"] if c["code"] == CODE][0]
plat.delete(f"/api/admin/school/{SID}/head-code/{cid}")
fresh()
ck("a revoked code stops signing in",
   TestClient(main.app).post("/api/auth/code",
                             json={"code": CODE}).status_code == 404)
fresh()
ck("but the administrator it already made still exists",
   db.get(main.User, AID) is not None)
fresh()
ck("gibberish is refused",
   TestClient(main.app).post("/api/auth/code",
                             json={"code": "0000000000"}).status_code == 404)

db.close()
print("")
print(chr(10).join("FAIL " + x for x in F) if F else "")
print(f"{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
