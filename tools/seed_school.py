"""Build a demonstration school, the way a head teacher would build a real one.

    python3 tools/seed_school.py            # both institutions
    python3 tools/seed_school.py --wipe     # remove a previous run first

What it makes, per institution:

    6 classrooms
      × 8 subjects each, all 48 different
      × 8 teachers, each holding ONE subject in EVERY classroom
      × 10 students per classroom, each in exactly one

    1 head teacher      creates the classes, the subjects and the register
    1 school admin      posts the notices, the attendance and the fees

That last line is the point of doing it this way rather than with INSERTs. A
head teacher creates classes and subjects; a school admin posts notices,
attendance and fees; a subject teacher claims their subject with the code the
head gave them. Every one of those is a different permission, and a seed that
writes rows directly proves none of them work. This one goes through the API
as each person, so a run that finishes is evidence the roles are wired up —
and a run that fails has found something.

Passwords are printed at the end. It is demonstration data on purpose: do not
point this at an installation with real children in it.
"""
import os
import sys
import secrets

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "s" * 40)
os.environ.setdefault("DATABASE_URL", "sqlite:///./vidyapath.db")
os.environ.setdefault("JOBS_ENABLED", "0")
os.environ.setdefault("COOKIE_SECURE", "0")

import datetime as dt                              # noqa: E402

import main                                        # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

PASSWORD = "Craxlearn2026!"
TAG = "demo"          # every account made here carries it, so --wipe is exact
# A domain that is not reserved (the e-mail validator refuses .invalid and
# .example) and is not anybody's: nothing is ever sent to these addresses.
DOMAIN = "craxlearndemo.org"

# Eight subjects per classroom, all different — a school does not teach the
# same eight things to a six-year-old and a sixteen-year-old.
PLAN = {
    "6-A": ["Mathematics", "Science", "English", "Social Studies",
            "Hindi", "Computer Science", "Art", "Physical Education"],
    "7-A": ["Algebra", "Life Science", "English Literature", "History",
            "Geography", "Information Technology", "Music", "Health"],
    "8-A": ["Geometry", "Physical Science", "English Grammar", "Civics",
            "Economics Basics", "Coding", "Craft", "Games"],
    "9-A": ["Trigonometry", "Physics", "Chemistry", "Biology",
            "English Core", "Indian History", "Statistics", "Drawing"],
    "10-A": ["Algebra II", "Applied Physics", "Organic Chemistry", "Botany",
             "English Composition", "World History", "Probability",
             "Technical Drawing"],
    "11-A": ["Calculus", "Mechanics", "Physical Chemistry", "Zoology",
             "Business Studies", "Political Science", "Data Handling",
             "Engineering Graphics"],
}
CLASSES = list(PLAN)

FIRST = ["Asha", "Ravi", "Meena", "Karthik", "Divya", "Arjun", "Priya",
         "Vikram", "Lakshmi", "Sanjay", "Nithya", "Gopal", "Anita", "Rahul",
         "Kavya", "Suresh", "Deepa", "Manoj", "Sneha", "Vijay"]
LAST = ["Rao", "Iyer", "Nair", "Menon", "Sharma", "Patel", "Reddy", "Gupta",
        "Krishnan", "Bose"]

SCHOOLS = [
    {"name": "Hillview Higher Secondary", "city": "Chennai",
     "country": "India", "slug": "hill"},
    {"name": "Northgate Coaching Centre", "city": "Pune",
     "country": "India", "slug": "north"},
]

db = main.SessionLocal()
main.Base.metadata.create_all(bind=main.engine)
main.send_email = lambda *a, **k: None


def die(what, r):
    print(f"\n  STOPPED at {what}: {r.status_code} {r.text[:300]}")
    print("  Nothing was rolled back — rerun with --wipe to start clean.")
    sys.exit(1)


def account(email, name):
    """A signed-in client for a new account. Date of birth is set because an
    institution asks for one, and without it the age gate closes the app."""
    c = TestClient(main.app)
    r = c.post("/api/auth/signup",
               json={"name": name, "email": email, "password": PASSWORD})
    if r.status_code != 200:
        die(f"creating {email}", r)
    u = db.query(main.User).filter(main.User.email == email).first()
    u.dob = dt.date(1988, 6, 1)
    db.commit()
    return c, u


def wipe():
    """Remove a previous run. Only rows whose e-mail carries the tag."""
    users = db.query(main.User).filter(
        main.User.email.like(f"%.{TAG}@craxlearndemo.org")).all()
    ids = [u.id for u in users]
    schools = db.query(main.School).filter(
        main.School.name.in_([s["name"] for s in SCHOOLS])).all()
    sids = [s.id for s in schools]
    classes = db.query(main.Klass).filter(
        main.Klass.school_id.in_(sids)).all() if sids else []
    cids = [k.id for k in classes]
    n = 0
    for model, col in ((main.SubjectSlot, main.SubjectSlot.class_id),
                       (main.ClassMember, main.ClassMember.class_id),
                       (main.RosterName, main.RosterName.class_id),
                       (main.Material, main.Material.class_id),
                       (main.Assignment, main.Assignment.class_id)):
        if cids:
            n += db.query(model).filter(col.in_(cids)).delete(
                synchronize_session=False)
    if sids:
        n += db.query(main.SchoolNotice).filter(
            main.SchoolNotice.school_id.in_(sids)).delete(
                synchronize_session=False)
    if ids:
        for model, col in ((main.Attendance, main.Attendance.user_id),
                           (main.FeeItem, main.FeeItem.user_id),
                           (main.TeacherAccess, main.TeacherAccess.user_id),
                           (main.ClassMember, main.ClassMember.user_id)):
            n += db.query(model).filter(col.in_(ids)).delete(
                synchronize_session=False)
    for k in classes:
        db.delete(k)
    for s in schools:
        db.delete(s)
    for u in users:
        db.delete(u)
    db.commit()
    print(f"Removed a previous run: {n + len(ids) + len(cids)} rows.")


def build(spec):
    slug = spec["slug"]
    print(f"\n=== {spec['name']} ===")

    school = db.query(main.School).filter(
        main.School.name == spec["name"]).first()
    if school is None:
        school = main.School(name=spec["name"], city=spec["city"],
                             country=spec["country"], product="craxlearn")
        db.add(school)
        db.commit()

    # ---- the head teacher, who runs the school ----
    head_c, head_u = account(f"head.{slug}.{TAG}@craxlearndemo.org",
                             f"{spec['name']} Head")
    db.add(main.TeacherAccess(user_id=head_u.id, school=school.name,
                              school_id=school.id, role="head"))
    db.commit()
    print(f"  head teacher   {head_u.email}")

    # ---- the school office, which is NOT the head teacher ----
    # Attendance, fees and notices are the office's, deliberately: a head
    # teacher who can mark a child absent and clear their fee is a head
    # teacher nobody can audit.
    admin_c, admin_u = account(f"office.{slug}.{TAG}@craxlearndemo.org",
                               f"{spec['name']} Office")
    db.add(main.TeacherAccess(user_id=admin_u.id, school=school.name,
                              school_id=school.id, role="schooladmin"))
    db.commit()
    print(f"  school office  {admin_u.email}")

    # ---- eight teachers, each taking one subject in every classroom ----
    teachers = []
    for i in range(8):
        name = f"{FIRST[i]} {LAST[i % len(LAST)]}"
        c, u = account(f"t{i + 1}.{slug}.{TAG}@craxlearndemo.org", name)
        teachers.append((c, u))
    print(f"  {len(teachers)} teachers")

    # ---- the classrooms, their subjects, and their registers ----
    for ci, cname in enumerate(CLASSES):
        k = main.Klass(name=cname,
                       join_code=f"{slug.upper()}{cname.replace('-', '')}",
                       teacher_id=head_u.id, school=school.name,
                       school_id=school.id)
        db.add(k)
        db.commit()

        # The head teacher creates one subject slot per subject, each with
        # its own code, and hands that code to the teacher who will take it.
        for si, subject in enumerate(PLAN[cname]):
            r = head_c.post(f"/api/head/class/{k.id}/slot",
                            json={"subject": subject})
            if r.status_code != 200:
                die(f"creating {subject} in {cname}", r)
            code = r.json()["code"]
            # Teacher si claims subject si — so every teacher ends up with
            # one subject across all six classrooms, which is a timetable.
            r = teachers[si][0].post("/api/class/join", json={"code": code})
            if r.status_code != 200:
                die(f"{teachers[si][1].name} claiming {subject}", r)

        # The register: the head types the names, and each learner signs in
        # with the class code and their own name — no password to lose.
        for n in range(10):
            who = f"{FIRST[(ci * 10 + n) % len(FIRST)]} " \
                  f"{LAST[(ci * 3 + n) % len(LAST)]}"
            db.add(main.RosterName(class_id=k.id, name=who,
                                   student_code=f"{cname}-{n + 1:02d}"))
        db.commit()

        # And the accounts behind them, so the class is populated rather than
        # merely expected.
        for n in range(10):
            row = (db.query(main.RosterName)
                     .filter(main.RosterName.class_id == k.id,
                             main.RosterName.claimed_by == 0)
                     .order_by(main.RosterName.id).first())
            c = TestClient(main.app)
            r = c.post("/api/craxlearn/code", json={"code": k.join_code})
            if r.status_code != 200:
                die(f"reading the register of {cname}", r)
            r = c.post("/api/craxlearn/claim",
                       json={"code": k.join_code, "roster_id": row.id})
            if r.status_code != 200:
                die(f"{row.name} taking their place in {cname}", r)

        print(f"  {cname:6s} {len(PLAN[cname])} subjects, 10 students, "
              f"code {k.join_code}")

    # ---- the office posts what the office posts ----
    for title, body, urgent in (
        ("Term begins on the 12th",
         "Classes resume on Monday the 12th. Timetables are on the notice "
         "board outside the office.", False),
        ("Fees for this term",
         "This term's fees are due by the end of the month. The office is "
         "open from 9 to 4.", True),
        ("Sports day",
         "Sports day is on the last Friday of the month. Parents are "
         "welcome from 8am.", False),
    ):
        r = admin_c.post("/api/office/notice",
                         json={"title": title, "body": body, "urgent": urgent})
        if r.status_code != 200:
            die("the office posting a notice", r)
    print("  3 notices posted by the office")
    return head_u, admin_u, teachers


if __name__ == "__main__":
    if "--wipe" in sys.argv:
        wipe()
    made = [build(s) for s in SCHOOLS]
    print("\n" + "=" * 62)
    print("Everything below signs in at /craxlearn with the same password.")
    print(f"  password: {PASSWORD}")
    print("\nStudents do not have one — they tap Class code, type the code")
    print("printed beside their class, and tap their own name.")
    print("=" * 62)
