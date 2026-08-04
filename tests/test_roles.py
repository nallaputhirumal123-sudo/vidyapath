"""Who may do what, stated once, for the four people a school has.

Capabilities were added one at a time over a long day, each with its own test
proving the thing it added worked. What no test asked was whether the four
roles, taken together, still made sense — and that is the question a school
asks first, because getting it wrong means either a teacher who cannot teach or
a child who can read the fee book.

    platform admin   runs the product. Sees everything, by design.
    school admin     runs one school: classes, staff, students, money, notices.
    teacher          teaches their own subjects to their own classes.
    student          learns, and sees only their own class and their own money.

Every row below is a capability and a role, asserted in both directions: that
the people who should have it do, and that the people who should not, do not.
A permission test that only checks the allowed case passes just as happily when
the door is open to everybody.
"""
import os
import sys
import time
import datetime as dt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"

import main                                        # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

PASS = FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {name}" + (f"  ({detail})" if detail else ""))
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


main.Base.metadata.create_all(bind=main.engine)
main.send_email = lambda *a, **k: None
stamp = int(time.time())
db = main.SessionLocal()

sc = main.School(name=f"RoleSchool {stamp}")
db.add(sc)
db.commit()
db.refresh(sc)
hc = main._gen_head_code(db)
db.add(main.TeacherCode(code=hc, school=sc.name, school_id=sc.id,
                        is_head=True, active=True))
db.commit()


def acct(tag, born=1985):
    c = TestClient(main.app)
    em = f"rl{tag}{stamp}@example.com"
    c.post("/api/auth/signup",
           json={"name": f"P{tag}", "email": em, "password": "RolePass1!"})
    u = db.query(main.User).filter(main.User.email == em).first()
    u.dob = dt.date(born, 1, 1)
    db.commit()
    return c, u


admin, admin_u = acct("adm")
admin.post("/api/class/join", json={"code": hc})
CID = admin.post("/api/teacher/class",
                 json={"name": f"8-R {stamp}"}).json()["id"]
admin.post(f"/api/teacher/class/{CID}/roster", json={"names": "Nita R, 8101"})

made = admin.post("/api/head/staff",
                  json={"name": "Teach R", "email": f"rlt{stamp}@s.in",
                        "role": "teacher"}).json()
admin.post("/api/head/assign",
           json={"class_id": CID, "subject": "Science",
                 "user_id": made["user_id"]})
teacher = TestClient(main.app)
teacher.post("/api/auth/login",
             json={"email": f"rlt{stamp}@s.in",
                   "password": made["temporary_password"]})

main._CODE_TRIES.clear()
main._CODE_FAILS.clear()
code = db.get(main.Klass, CID).join_code
student = TestClient(main.app)
free = student.post("/api/craxlearn/code", json={"code": code}).json()["names"]
student.post("/api/craxlearn/claim",
             json={"code": code, "roster_id": free[0]["id"]})

outsider, _ = acct("out")

WHO = {"school admin": admin, "teacher": teacher, "student": student,
       "outsider": outsider}


def allowed(name, call, yes, note=""):
    """`call` is run as every role. `yes` names the ones that must succeed."""
    bad = []
    for role, client in WHO.items():
        try:
            code_ = call(client)
        except Exception as e:
            code_ = f"raised {type(e).__name__}"
        ok = code_ in (200, 201) if role in yes else code_ not in (200, 201)
        if not ok:
            bad.append(f"{role}={code_}")
    check(name, not bad, "; ".join(bad) or note)


print("\nrunning the school")
allowed("only the school admin creates a class",
        lambda c: c.post("/api/teacher/class",
                         json={"name": f"tmp{stamp}"}).status_code,
        {"school admin"})
allowed("only the school admin adds staff",
        lambda c: c.post("/api/head/staff",
                         json={"name": "X Y", "email": f"x{stamp}@s.in",
                               "role": "teacher"}).status_code,
        {"school admin"})
allowed("only the school admin puts a teacher on a subject",
        lambda c: c.post("/api/head/assign",
                         json={"class_id": CID, "subject": "Science",
                               "user_id": made["user_id"]}).status_code,
        {"school admin"})
allowed("only the school admin types the register",
        lambda c: c.post(f"/api/teacher/class/{CID}/roster",
                         json={"names": "Temp Name"}).status_code,
        {"school admin", "teacher"},
        "a subject teacher of the class may also add a name")

print("\nmoney and attendance")
allowed("only the school admin reads the fee book",
        lambda c: c.get("/api/office/fees").status_code, {"school admin"})
allowed("only the school admin bills a class",
        lambda c: c.post("/api/office/fee/plan",
                         json={"class_id": CID, "title": f"Fee {stamp}",
                               "amount": 1000, "due_on": "",
                               "kind": "fee"}).status_code,
        {"school admin"})
allowed("only the school admin takes the register",
        lambda c: c.post("/api/office/attendance",
                         json={"class_id": CID,
                               "day": dt.date.today().isoformat(),
                               "present": {}, "notes": {}}).status_code,
        {"school admin"})
allowed("only the school admin sees every learner",
        lambda c: c.get("/api/head/students").status_code, {"school admin"})

print("\nteaching")
allowed("staff set work, learners do not",
        lambda c: c.post(f"/api/teacher/class/{CID}/assignment",
                         json={"subject": "Science", "title": "T",
                               "body": "b", "due_date": ""}).status_code,
        {"school admin", "teacher"})
allowed("staff share material, learners do not",
        lambda c: c.post(f"/api/teacher/class/{CID}/material/link",
                         json={"title": "Notes", "url": "https://x.in/a",
                               "subject": "Science", "note": ""}).status_code,
        {"school admin", "teacher"})
allowed("staff file a taught lesson, learners do not",
        lambda c: c.post("/api/craxlearn/board/save",
                         json={"class_id": CID, "topic": "refraction", "title": "Ray",
                               "subject": "Science", "note": "",
                               "lesson": {"title": "T", "steps": [
                                   {"t": "a line", "where": "", "code": ""}],
                                   "takeaway": ""}}).status_code,
        {"school admin", "teacher"})

print("\nspeaking to the school")
allowed("only the school admin addresses everybody",
        lambda c: c.post("/api/office/notice",
                         json={"title": f"All {stamp}", "body": "b",
                               "urgent": False, "starts_on": "",
                               "ends_on": "", "audience": "all"}).status_code,
        {"school admin"})
allowed("a teacher may address their own class",
        lambda c: c.post("/api/office/notice",
                         json={"title": f"Cls {stamp}", "body": "b",
                               "urgent": False, "starts_on": "", "ends_on": "",
                               "audience": "class",
                               "class_id": CID}).status_code,
        {"school admin", "teacher"})
allowed("only staff may look a person up",
        lambda c: c.get("/api/head/people").status_code,
        {"school admin", "teacher"})

print("\nwhat a learner has of their own")
allowed("everybody in the class reads its material",
        lambda c: c.get(f"/api/class/{CID}/materials").status_code,
        {"school admin", "teacher", "student"})
allowed("everybody in the class reads its subjects",
        lambda c: c.get(f"/api/class/{CID}/subjects").status_code,
        {"school admin", "teacher", "student"})
allowed("everybody in the class may ask a question",
        lambda c: c.post(f"/api/class/{CID}/discussion",
                         json={"body": "a question"}).status_code,
        {"school admin", "teacher", "student"},
        "a discussion only one side can start is a noticeboard")
allowed("anybody signed in reads their own updates",
        lambda c: c.get("/api/my/notices").status_code,
        {"school admin", "teacher", "student", "outsider"},
        "an outsider has none, but asking is not an offence")

print("\nand the platform admin is above all of it")
admin_u.is_admin = True
db.commit()
r = admin.get("/api/admin/schools")
check("a platform admin runs the product", r.status_code == 200,
      f"got {r.status_code}")

print(f"\nPASSED {PASS}   FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
