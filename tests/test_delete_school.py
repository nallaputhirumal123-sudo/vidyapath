"""Deleting a school takes its school with it.

The route deleted the School row and nothing else. Nothing references a school
by foreign key — school_id is a plain integer on the teacher codes, the staff
access rows and the classrooms — so the school vanished from the list and its
teachers, its codes and its classes all stayed behind, attached to a school
that no longer existed. The admin screen read "Schools: none yet" above three
teachers and two classrooms.

Accounts are kept on purpose. A teacher's account may be their own, and a
platform administrator removing a school has no business deleting a person.
What goes is their access to a school that is not there any more.
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
PE = f"ds{st}@example.com"
plat.post("/api/auth/signup", json={"name": "Platform", "email": PE,
                                    "password": "DelPass1!"})
pu = db.query(main.User).filter(main.User.email == PE).first()
pu.is_admin = True; pu.dob = dt.date(1980, 1, 1); db.commit()

SCHOOL = f"Doomed School {st}"
r = plat.post("/api/admin/school",
              json={"name": SCHOOL, "admin_name": "Head Doomed"})
SID = r.json()["id"]; ACODE = r.json()["head_code"]

fresh()
adm = TestClient(main.app)
adm.post("/api/auth/code", json={"code": ACODE})
AID = adm.get("/api/auth/me").json().get("id")
K = adm.post("/api/teacher/class", json={"name": f"5-D {st}"}).json()
CID = K["id"]
adm.post("/api/teacher/class/" + str(CID) + "/roster",
         json={"names": "Deepa X, 501"})
made = adm.post("/api/head/staff",
                json={"name": "Mr Doomed", "email": f"td{st}@example.com",
                      "role": "teacher"}).json()
TID = made["user_id"]
slot = adm.post("/api/head/class/" + str(CID) + "/slot",
                json={"subject": "Maths", "teacher_id": 0}).json()
adm.post("/api/head/assign",
         json={"class_id": CID, "subject": "Maths", "user_id": TID})
fresh()
kid = TestClient(main.app)
names = kid.post("/api/craxlearn/code",
                 json={"code": K["join_code"]}).json()["names"]
kid.post("/api/craxlearn/claim",
         json={"code": K["join_code"], "roster_id": names[0]["id"]})
KID = kid.get("/api/auth/me").json().get("id")

print("")
print("a school with things in it is not deleted on a single click")
r = plat.delete("/api/admin/school/" + str(SID))
ck("it refuses", r.status_code == 409, f"got {r.status_code}")
body = r.json().get("detail", {})
ck("and says what it holds",
   isinstance(body, dict) and body.get("holds", {}).get("classes", 0) >= 1,
   str(body)[:170])
ck("and names what must be typed",
   isinstance(body, dict) and body.get("needs_confirm") == SCHOOL,
   str(body)[:120])
db.expire_all()
ck("nothing was removed", db.get(main.Klass, CID) is not None)

print("")
print("typing the name deletes it, and everything that belonged to it")
r = plat.delete("/api/admin/school/" + str(SID) + "?confirm=" + SCHOOL.replace(" ", "%20"))
ck("it is deleted", r.status_code == 200, r.text[:150])
db.expire_all()
ck("the school is gone", db.get(main.School, SID) is None)
ck("its classroom is gone", db.get(main.Klass, CID) is None)
ck("no register rows are left behind",
   db.query(main.RosterName).filter(main.RosterName.class_id == CID).count() == 0)
ck("no subject slots are left behind",
   db.query(main.SubjectSlot).filter(main.SubjectSlot.class_id == CID).count() == 0)
ck("no staff access to a school that does not exist",
   db.query(main.TeacherAccess).filter(
       main.TeacherAccess.school_id == SID).count() == 0)
ck("and none of its codes survive",
   db.query(main.TeacherCode).filter(
       main.TeacherCode.school_id == SID).count() == 0)

print("")
print("but the people are kept")
ck("the teacher's account still exists", db.get(main.User, TID) is not None)
ck("the administrator's account still exists", db.get(main.User, AID) is not None)
ck("the pupil's account still exists", db.get(main.User, KID) is not None)
ck("the teacher is no longer staff anywhere",
   db.query(main.TeacherAccess).filter(
       main.TeacherAccess.user_id == TID).count() == 0)

print("")
print("and the codes really stop working")
fresh()
ck("the admin code is dead",
   TestClient(main.app).post("/api/auth/code",
                             json={"code": ACODE}).status_code == 404)
fresh()
ck("the subject code is dead",
   TestClient(main.app).post("/api/auth/code",
                             json={"code": slot["code"]}).status_code == 404)
fresh()
ck("the class code is dead",
   TestClient(main.app).post("/api/craxlearn/code",
                             json={"code": K["join_code"]}).status_code == 404)

print("")
print("an empty school still deletes without ceremony")
r = plat.post("/api/admin/school",
              json={"name": f"Empty School {st}", "admin_name": "Nobody"})
ck("it goes on the first click",
   plat.delete("/api/admin/school/" + str(r.json()["id"])).status_code == 200)

print("")
print("and only the platform admin may do it")
out = TestClient(main.app)
out.post("/api/auth/signup", json={"name": "Outsider", "email": f"do{st}@example.com",
                                   "password": "DelPass1!"})
r2 = plat.post("/api/admin/school", json={"name": f"Safe School {st}",
                                          "admin_name": "Safe"})
ck("an ordinary account is refused",
   out.delete("/api/admin/school/" + str(r2.json()["id"])).status_code in (401, 403))

db.close()
print("")
print(chr(10).join("FAIL " + x for x in F) if F else "")
print(f"{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
