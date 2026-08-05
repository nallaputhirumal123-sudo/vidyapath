"""A school has more than one person in the office.

Issuing an admin code used to deactivate every code already issued for that
school. The intention was revocation — a head who leaves must not be able to
re-register — but the effect was that a school could only ever have one
administrator. Giving the second one their code cancelled the first one's,
silently, and the first person found out the next time they tried to use it.

Issuing is now issuing. Revoking is its own act, on one code, with its own
route: one button that quietly does two things is how access you meant to
grant gets taken away.

What is pinned here:

  * two codes issued, two different people redeem them, both are admins
  * revoking one leaves the other working
  * revoking a code does NOT remove the administrator who already used it —
    a code is how somebody became an administrator, not what keeps them one
  * replace_all still exists for the case the old behaviour was really for
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

def account(tag, name, admin=False):
    c = TestClient(main.app)
    em = f"ma{tag}{st}@example.com"
    c.post("/api/auth/signup", json={"name": name, "email": em,
                                     "password": "ManyPass1!"})
    u = db.query(main.User).filter(main.User.email == em).first()
    u.dob = dt.date(1984, 7, 7)
    if admin:
        u.is_admin = True
    db.commit()
    return c, u.id

plat, _ = account("plat", "Platform Admin", admin=True)

print("\none school, two admin codes")
r = plat.post("/api/admin/school", json={"name": f"Two Heads School {st}"})
SID = r.json()["id"]
FIRST = r.json()["head_code"]
ck("creating the school gives the first code", len(FIRST) == 10, FIRST)

r = plat.post(f"/api/admin/school/{SID}/head-code", json={})
SECOND = r.json()["head_code"]
ck("a second code is issued", len(SECOND) == 10 and SECOND != FIRST, SECOND)
ck("and it did NOT cancel the first — this is the whole bug",
   r.json().get("revoked") == 0 and r.json().get("live_codes") == 2,
   str(r.json()))

print("\nboth are redeemable, by different people")
a1, A1 = account("a1", "Office One")
r = a1.post("/api/class/join", json={"code": FIRST})
ck("the first admin signs in with the first code",
   r.status_code == 200 and r.json().get("role") == "school admin", r.text[:110])

a2, A2 = account("a2", "Office Two")
r = a2.post("/api/class/join", json={"code": SECOND})
ck("the second admin signs in with the second code",
   r.status_code == 200 and r.json().get("role") == "school admin", r.text[:110])

ck("both are heads of the school",
   bool(a1.get("/api/auth/me").json().get("is_head"))
   and bool(a2.get("/api/auth/me").json().get("is_head")))
ck("and both can run the school",
   a1.get("/api/head/overview").status_code == 200
   and a2.get("/api/head/overview").status_code == 200)

print("\nthe list says what is out there")
d = plat.get(f"/api/admin/school/{SID}/head-codes").json()
codes = {c["code"]: c["active"] for c in d.get("codes", [])}
ck("both codes are listed and live",
   codes.get(FIRST) is True and codes.get(SECOND) is True, str(codes))
ck("and it names who signed up with them",
   len(d.get("admins", [])) == 2, str(d.get("admins")))

print("\nrevoking one leaves the other alone")
cid_first = [c["id"] for c in d["codes"] if c["code"] == FIRST][0]
r = plat.delete(f"/api/admin/school/{SID}/head-code/{cid_first}")
ck("a single code can be stopped", r.status_code == 200, r.text[:110])

fresh = TestClient(main.app)
fresh.post("/api/auth/signup", json={"name": "Late Comer",
                                     "email": f"malate{st}@example.com",
                                     "password": "ManyPass1!"})
r = fresh.post("/api/class/join", json={"code": FIRST})
ck("the stopped code no longer works", r.status_code == 404,
   f"got {r.status_code}")

fresh2 = TestClient(main.app)
fresh2.post("/api/auth/signup", json={"name": "Third Office",
                                      "email": f"ma3{st}@example.com",
                                      "password": "ManyPass1!"})
r = fresh2.post("/api/class/join", json={"code": SECOND})
ck("the other code still does", r.status_code == 200, r.text[:110])

print("\nand revoking a code does not unmake an administrator")
# A code is how somebody became an admin, not what keeps them one. Taking
# their access away is done on the staff list, where you can see who they are.
ck("the first admin is still an administrator",
   a1.get("/api/head/overview").status_code == 200,
   str(a1.get("/api/head/overview").status_code))

print("\nreplace_all still exists for when somebody leaves")
r = plat.post(f"/api/admin/school/{SID}/head-code?replace_all=true", json={})
THIRD = r.json()["head_code"]
ck("it revokes what was live", r.json().get("revoked") >= 1, str(r.json()))
ck("and leaves exactly the new one", r.json().get("live_codes") == 1,
   str(r.json()))
fresh3 = TestClient(main.app)
fresh3.post("/api/auth/signup", json={"name": "Fourth",
                                      "email": f"ma4{st}@example.com",
                                      "password": "ManyPass1!"})
ck("the previous code stops working",
   fresh3.post("/api/class/join", json={"code": SECOND}).status_code == 404)
ck("the new one works",
   fresh3.post("/api/class/join", json={"code": THIRD}).status_code == 200)

print("\nonly the platform admin may do any of this")
out, _ = account("out", "Not An Admin")
ck("issuing is refused",
   out.post(f"/api/admin/school/{SID}/head-code", json={}).status_code in (401, 403))
ck("listing is refused",
   out.get(f"/api/admin/school/{SID}/head-codes").status_code in (401, 403))
ck("revoking is refused",
   out.delete(f"/api/admin/school/{SID}/head-code/{cid_first}").status_code
   in (401, 403))
ck("a school admin cannot mint codes for their own school either",
   a2.post(f"/api/admin/school/{SID}/head-code", json={}).status_code
   in (401, 403),
   str(a2.post(f"/api/admin/school/{SID}/head-code", json={}).status_code))

r = plat.delete(f"/api/admin/school/{SID}/head-code/99999999")
ck("a code that is not theirs is not found", r.status_code == 404,
   f"got {r.status_code}")

db.close()
print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
