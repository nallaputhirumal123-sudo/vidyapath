"""Separated duties: the office keeps the register, teachers keep the class.

A school has kept attendance, fees and notices away from teaching staff since
long before any of this was software, and copying that separation is cheaper
than explaining why we did not. So the tests here are mostly refusals, and
the ones that matter are refusals of people who ARE staff:

  a teacher marking a child absent
  a head teacher writing off a fee
  either of them posting a school-wide notice

All three would be a reasonable-looking bug — every one of those people is
trusted, signed in, and at the right school. None of them may do it.

The other half is the learner's own view. Attendance is computed from day
rows and never stored as a total, because "marked absent on the 14th and it
was wrong" is the most common thing a parent rings about and a stored
percentage has nothing to correct. That is asserted by correcting one.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"   # local test database; refused on a deployment
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"

import time                                        # noqa: E402

import main                                        # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402


def _pw_office(uid, pw="OfficePass123!"):
    """A password for a staff account, so this suite can hold a session.

    Staff are not given one when they are created — sign-in is by code — and
    this suite is about what the office may DO once signed in, not about how
    it got there.
    """
    d = main.SessionLocal()
    u = d.get(main.User, uid)
    u.password_hash = main.hash_pw(pw)
    d.commit(); d.close()
    return pw



def _pw(uid, pw='TeachPass123!'):
    """A password for a staff account, for suites that only need a session.

    Staff are not given one when they are created any more — a teacher signs
    in with the subject code the office hands them. These suites are about
    what a teacher may SEE once signed in, not about how they got there, so
    they set one directly rather than being rewritten around codes.
    """
    _d = main.SessionLocal()
    _u = _d.get(main.User, uid)
    _u.password_hash = main.hash_pw(pw)
    _d.commit(); _d.close()
    return pw


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

school = main.School(name=f"Office School {stamp}", city="Surat",
                     country="India", product="craxlearn")
far = main.School(name=f"Other Office {stamp}", city="Goa",
                  country="India", product="craxlearn")
db.add_all([school, far])
db.commit()


def person(tag, role=None, school_row=None):
    c = TestClient(main.app)
    email = f"of{tag}{stamp}@example.com"
    r = c.post("/api/auth/signup", json={"name": f"Person {tag}",
                                         "email": email,
                                         "password": "OfficePass123!"})
    assert r.status_code == 200, r.text
    u = db.query(main.User).filter(main.User.email == email).first()
    if role:
        db.add(main.TeacherAccess(user_id=u.id, school=school_row.name,
                                  school_id=school_row.id, role=role))
        db.commit()
    return c, u


head, head_u = person("head", "head", school)
office, office_u = person("off", "schooladmin", school)
tutor, tutor_u = person("tut", "teacher", school)
far_office, _ = person("far", "schooladmin", far)

klass = main.Klass(name="8-A", join_code=f"OF{stamp}"[:16],
                   teacher_id=head_u.id, school=school.name,
                   school_id=school.id)
db.add(klass)
db.commit()

kid, kid_u = person("kid")
kid2, kid2_u = person("kid2")
for u in (kid_u, kid2_u):
    db.add(main.ClassMember(class_id=klass.id, user_id=u.id))
db.commit()

# ---- only one login ----------------------------------------------------
print("\nOne login at a time")
check("the limit is one", main.MAX_DEVICES == 1, str(main.MAX_DEVICES))
first = TestClient(main.app)
r = first.post("/api/auth/login", json={"email": kid_u.email,
                                        "password": "OfficePass123!"})
check("a second device can sign in", r.status_code == 200, str(r.status_code))
check("and it works", first.get("/api/auth/me").status_code == 200)
check("while the first is signed out",
      kid.get("/api/auth/me").status_code == 401,
      str(kid.get("/api/auth/me").status_code))
check("and told why, not just refused",
      "somewhere else" in kid.get("/api/auth/me").json().get("detail", ""),
      kid.get("/api/auth/me").text[:140])
kid = first   # carry on with the live session

# ---- who may keep the register -----------------------------------------
print("\nWho may keep the register")
DAY = "2026-08-04"
payload = {"class_id": klass.id, "day": DAY,
           "present": {str(kid_u.id): True, str(kid2_u.id): False}}

r = tutor.post("/api/office/attendance", json=payload)
check("a teacher cannot mark attendance", r.status_code == 403,
      str(r.status_code))
# The head teacher and the office are one role now, shown as School admin: in
# the schools this is sold to they are one person, and the split meant the head
# either could not see whether a child had been marked present or was quietly
# handed the office's password.
r = head.post("/api/office/attendance", json=payload)
check("the head teacher can, being the School admin",
      r.status_code == 200, str(r.status_code))
r = kid.post("/api/office/attendance", json=payload)
check("nor a learner", r.status_code == 403, str(r.status_code))

r = office.post("/api/office/attendance", json=payload)
check("the office can", r.status_code == 200, r.text[:150])
check("marking everybody in the class", r.json()["marked"] == 2, r.text[:120])

r = far_office.post("/api/office/attendance", json=payload)
check("another school's office cannot touch this class",
      r.status_code == 403, str(r.status_code))

# An id that is not in the class must be ignored rather than written.
r = office.post("/api/office/attendance",
                json={"class_id": klass.id, "day": DAY,
                      "present": {str(tutor_u.id): False, "999999": False}})
check("ids outside the class are ignored", r.json()["marked"] == 0,
      r.text[:120])
check("and nothing was written for them",
      db.query(main.Attendance).filter(
          main.Attendance.user_id == tutor_u.id).count() == 0)

# ---- the percentage is computed, so it can be corrected -----------------
print("\nAttendance a parent can argue with")
st = kid.get("/api/craxlearn/standing").json()
check("the learner sees their percentage", st["attendance_pct"] == 100.0,
      str(st["attendance_pct"]))
st2 = TestClient(main.app)
st2.post("/api/auth/login", json={"email": kid2_u.email,
                                  "password": "OfficePass123!"})
check("and an absence shows as zero",
      st2.get("/api/craxlearn/standing").json()["attendance_pct"] == 0.0,
      str(st2.get("/api/craxlearn/standing").json()["attendance_pct"]))

# The correction. Same day, marked again — one row, not two opinions of it.
office.post("/api/office/attendance",
            json={"class_id": klass.id, "day": DAY,
                  "present": {str(kid2_u.id): True},
                  "notes": {str(kid2_u.id): "was here, marked in error"}})
got = st2.get("/api/craxlearn/standing").json()
check("a wrongly marked day can be put right",
      got["attendance_pct"] == 100.0, str(got["attendance_pct"]))
check("without creating a second record of that day",
      db.query(main.Attendance).filter(
          main.Attendance.user_id == kid2_u.id).count() == 1,
      str(db.query(main.Attendance).filter(
          main.Attendance.user_id == kid2_u.id).count()))

# Nothing recorded is not perfect attendance.
loner, loner_u = person("lone")
lone_st = loner.get("/api/craxlearn/standing").json()
check("no register taken is not 100%", lone_st["attendance_pct"] is None,
      str(lone_st["attendance_pct"]))

# ---- fees ---------------------------------------------------------------
print("\nFees")
fee = {"user_id": kid_u.id, "title": "Term 2 tuition", "amount": 1500000,
       "due_on": "2026-09-15"}
r = tutor.post("/api/office/fee", json=fee)
check("nor a teacher", r.status_code == 403, str(r.status_code))

r = office.post("/api/office/fee", json=fee)
check("the office can", r.status_code == 200, r.text[:150])
fid = r.json()["item"]["id"]
check("and it is outstanding in full",
      r.json()["item"]["outstanding"] == 1500000, r.text[:150])

r = office.post("/api/office/fee",
                json={"user_id": kid_u.id, "title": "Lab coat",
                      "amount": 60000, "kind": "buy"})
check("something to buy is recorded too", r.status_code == 200, r.text[:120])

r = far_office.post("/api/office/fee",
                    json={"user_id": kid_u.id, "title": "Not yours",
                          "amount": 100})
check("another school's office cannot bill this learner",
      r.status_code == 403, str(r.status_code))

r = office.post("/api/office/fee", json={"user_id": kid_u.id,
                                         "title": "Nope", "amount": -5})
check("a negative amount is refused", r.status_code == 400, str(r.status_code))

st = kid.get("/api/craxlearn/standing").json()
check("the learner sees what they owe", st["owed"] == 1560000, str(st["owed"]))
check("with fees and things to buy kept apart",
      len(st["fees"]) == 1 and len(st["to_buy"]) == 1, str(st)[:200])
check("and cannot change any of it",
      kid.post("/api/office/fee", json=fee).status_code == 403)

office.post(f"/api/office/fee/{fid}/paid", json={"paid": 1500000})
st = kid.get("/api/craxlearn/standing").json()
check("paying it clears it from the balance", st["owed"] == 60000,
      str(st["owed"]))
check("and it reads as settled",
      [f for f in st["fees"] if f["id"] == fid][0]["settled"] is True)

# ---- notices ------------------------------------------------------------
print("\nNotices")
r = head.post("/api/office/notice", json={"title": "Sports day"})
# This used to require the office and exclude the head, and that was wrong.
# A notice is the one thing here that is a school SPEAKING to its school, and
# the person who most often needs to tell everybody at once — an exam moved, a
# day closed — is the head. The alternative in practice was handing the head
# the office's credentials, which is worse than what the split protected.
# Attendance and fees are unchanged and remain the office's alone.
check("a head teacher can post a school notice", r.status_code == 200,
      str(r.status_code))
r = office.post("/api/office/notice",
                json={"title": "Fees due Friday", "body": "Bring the slip.",
                      "urgent": True})
check("the office can", r.status_code == 200, r.text[:150])
nid = r.json()["notice"]["id"]

office.post("/api/office/notice",
            json={"title": "Old news", "ends_on": "2020-01-01"})
office.post("/api/office/notice",
            json={"title": "Next term", "starts_on": "2099-01-01"})

st = kid.get("/api/craxlearn/standing").json()
titles = [n["title"] for n in st["notices"]]
check("the learner sees the live notice", "Fees due Friday" in titles,
      str(titles))
check("an expired one is not shown", "Old news" not in titles, str(titles))
check("nor one that has not started", "Next term" not in titles, str(titles))
check("and urgent comes first", st["notices"][0]["urgent"] is True,
      str(st["notices"][0]))

far_st = far_office.get("/api/craxlearn/standing").json()
check("another school sees none of these notices",
      "Fees due Friday" not in [n["title"] for n in far_st["notices"]],
      str(far_st["notices"]))

check("a learner cannot delete a notice",
      kid.delete(f"/api/office/notice/{nid}").status_code == 403)
check("another school's office cannot either",
      far_office.delete(f"/api/office/notice/{nid}").status_code == 403)
check("the office can", office.delete(f"/api/office/notice/{nid}").status_code == 200)

# ---- the head makes the profiles ---------------------------------------
print("\nProfiles")
r = tutor.post("/api/head/staff", json={"name": "New Teacher",
                                        "email": f"nt{stamp}@example.com"})
check("a teacher cannot create staff", r.status_code == 403, str(r.status_code))

r = head.post("/api/head/staff", json={"name": "New Teacher",
                                       "email": f"nt{stamp}@example.com"})
check("the head can", r.status_code == 200, r.text[:150])
# No password is handed over any more: a teacher signs in with the subject
# code the office gives them, and the office signs in with the school's.
check("and no password is handed over",
      not r.json().get("temporary_password"), r.text[:150])

r = head.post("/api/head/staff", json={"name": "New Clerk",
                                       "email": f"nc{stamp}@example.com",
                                       "role": "schooladmin"})
check("the head can appoint the office", r.status_code == 200, r.text[:150])
clerk_pw = _pw_office(r.json()["user_id"])
clerk = TestClient(main.app)
clerk.post("/api/auth/login", json={"email": f"nc{stamp}@example.com",
                                    "password": clerk_pw})
check("and that account can sign in with it",
      clerk.get("/api/auth/me").status_code == 200)
check("and keep the register",
      clerk.post("/api/office/attendance",
                 json={"class_id": klass.id, "day": "2026-08-05",
                       "present": {str(kid_u.id): True}}).status_code == 200)

# The head appointing the office must not be a way to become the office.
r = head.post("/api/head/staff", json={"name": "Me", "email": head_u.email,
                                       "role": "schooladmin"})
check("the head cannot promote themselves", r.status_code == 400,
      str(r.status_code))
# Being School admin already, the head gains nothing by appointing themselves
# — but the appointment must still be refused, or that check is the only thing
# standing between an ordinary teacher and the office.
check("and keeps the register as School admin",
      head.post("/api/office/attendance", json=payload).status_code == 200)

r = head.post("/api/head/staff", json={"name": "Xavier P",
                                       "email": f"x{stamp}@example.com",
                                       "role": "wizard"})
check("an invented role is refused", r.status_code == 400, str(r.status_code))
check("and nobody was created for it",
      db.query(main.User).filter(
          main.User.email == f"x{stamp}@example.com").first() is None)

staff = head.get("/api/head/staff").json()
check("the head can see who works there", len(staff["staff"]) >= 4,
      str(len(staff["staff"])))
check("and only their own school",
      all("Person far" not in s["name"] for s in staff["staff"]),
      str([s["name"] for s in staff["staff"]]))

db.close()
print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
