"""A school has paid for its people, so its people are not asked again.

Everyone who arrives through a school code gets the Pro board: the pupil off
the register, the teacher with a subject code, the administrator with the
school's ten digits. The alternative was a lesson on a classroom wall stopping
to advertise a subscription to a room of children, and a teacher being offered
a personal upgrade for a tool their school had already bought.

Decided from users.kind, because plan_of is read on nearly every request and a
database lookup per call to answer "which plan" would be paid for on every
page. That is why the kinds matter and why a migration marks the staff who
existed before the mark did.
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
PE = f"pro{st}@example.com"
plat.post("/api/auth/signup", json={"name": "Platform", "email": PE,
                                    "password": "ProPass1!"})
pu = db.query(main.User).filter(main.User.email == PE).first()
pu.is_admin = True; pu.dob = dt.date(1980, 1, 1); db.commit()

r = plat.post("/api/admin/school",
              json={"name": f"Pro School {st}", "admin_name": "Head Pro"})
SID = r.json()["id"]; ADMIN_CODE = r.json()["head_code"]

print("")
print("the administrator")
fresh()
adm = TestClient(main.app)
adm.post("/api/auth/code", json={"code": ADMIN_CODE})
AID = adm.get("/api/auth/me").json().get("id")
db.expire_all()
au = db.get(main.User, AID)
ck("signs in with a code", au is not None)
ck("and is on the Pro board", main.plan_of(au) == "pro", main.plan_of(au))
ck("without anything being bought", (au.plan or "free") == "free", str(au.plan))

print("")
print("the teacher")
made = adm.post("/api/head/staff",
                json={"name": "Miss Rao", "email": f"rao{st}@example.com",
                      "role": "teacher"}).json()
TID = made["user_id"]
db.expire_all()
tu = db.get(main.User, TID)
ck("is marked as school staff when granted access",
   (tu.kind or "") == "schoolstaff", str(tu.kind))
ck("and is on the Pro board", main.plan_of(tu) == "pro", main.plan_of(tu))

print("")
print("the pupil")
K = adm.post("/api/teacher/class", json={"name": f"7-P {st}"}).json()
adm.post("/api/teacher/class/" + str(K["id"]) + "/roster",
         json={"names": "Ravi S, 701"})
fresh()
kid = TestClient(main.app)
names = kid.post("/api/craxlearn/code",
                 json={"code": K["join_code"]}).json()["names"]
kid.post("/api/craxlearn/claim",
         json={"code": K["join_code"], "roster_id": names[0]["id"]})
KID = kid.get("/api/auth/me").json().get("id")
db.expire_all()
ku = db.get(main.User, KID)
ck("taps their name off the register", ku is not None)
ck("and is on the Pro board too", main.plan_of(ku) == "pro", main.plan_of(ku))

print("")
print("and an ordinary learner is NOT given it")
out = TestClient(main.app)
OE = f"pfree{st}@example.com"
out.post("/api/auth/signup", json={"name": "Ordinary", "email": OE,
                                   "password": "ProPass1!"})
ou = db.query(main.User).filter(main.User.email == OE).first()
ck("somebody arriving on their own is on the free plan",
   main.plan_of(ou) == "free", main.plan_of(ou))
ck("and their kind is untouched", (ou.kind or "") == "", str(ou.kind))

print("")
print("the migration marks staff who existed before the mark did")
old = main.User(name="Old Hand", email=f"old{st}@example.com",
                password_hash=main.hash_pw("x" * 12), is_active=True)
db.add(old); db.commit(); db.refresh(old)
db.add(main.TeacherAccess(user_id=old.id, school="Pro School", school_id=SID,
                          role="teacher"))
db.commit()
ck("an account with a school role and no kind starts on free",
   main.plan_of(old) == "free", main.plan_of(old))
# Exactly the statement migration 0003 runs.
from sqlalchemy import text as _sql
db.execute(_sql("UPDATE users SET kind = 'schoolstaff' "
                "WHERE (kind IS NULL OR kind = '') "
                "AND id IN (SELECT user_id FROM teacher_access)"))
db.commit()
db.expire_all()
old2 = db.get(main.User, old.id)
ck("and the migration puts them on Pro", main.plan_of(old2) == "pro",
   main.plan_of(old2))
db.expire_all()
ou2 = db.query(main.User).filter(main.User.email == OE).first()
ck("while leaving an ordinary learner alone", main.plan_of(ou2) == "free",
   main.plan_of(ou2))

db.close()
print("")
print(chr(10).join("FAIL " + x for x in F) if F else "")
print(f"{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
