"""Signing in with nothing, study material, and the reset that cannot misfire.

Three things a school actually asked for, and each one has a way of going
quietly wrong.

**A login with no credential.** A learner types the class code and picks
their name. There is nothing to phish and nothing to reset — and nothing
stopping two children taking the same name unless the claim is atomic, or
stopping a class-code account reaching the job board unless that is closed
at a level the school's own settings cannot override. Both are asserted.

**Material.** A link or a file, visible to that class and to nobody else.
The check that matters is the negative one: somebody in a different class
must not be able to fetch the file by guessing its id.

**The reset.** One request deletes every non-admin account. It is guarded by
an exact typed phrase, and the test spends most of its length proving the
guard holds — a destructive endpoint's tests are mostly about the times it
must do nothing.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
# Its OWN database, not the shared one. The last section of this file
# deletes every non-admin account, and a test that does that against the
# database the other suites use is a test that breaks them for reasons
# nobody will connect to it. Gitignored by the *.db rule.
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath-classcode-test.db"
os.environ["ALLOW_SQLITE"] = "1"   # local test database; refused on a deployment
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"

import datetime as dt                              # noqa: E402
import io as _io                                   # noqa: E402
import time                                        # noqa: E402

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

school = main.School(name=f"Code School {stamp}", city="Kochi",
                     country="India", product="craxlearn")
db.add(school)
db.commit()

teach = TestClient(main.app)
temail = f"tt{stamp}@example.com"
teach.post("/api/auth/signup", json={"name": "Teacher T", "email": temail,
                                     "password": "ClassCodePass123!"})
tu = db.query(main.User).filter(main.User.email == temail).first()
db.add(main.TeacherAccess(user_id=tu.id, school=school.name,
                          school_id=school.id, role="head"))
db.commit()

CODE = f"CD{stamp}"[:16]
klass = main.Klass(name="7-B", join_code=CODE, teacher_id=tu.id,
                   school=school.name, school_id=school.id)
other = main.Klass(name="7-C", join_code=f"CE{stamp}"[:16], teacher_id=tu.id,
                   school=school.name, school_id=school.id)
db.add_all([klass, other])
db.commit()

# ---- the register ------------------------------------------------------
print("\nThe register")
r = teach.post(f"/api/teacher/class/{klass.id}/roster",
               json={"names": "Asha Rao\nBilal Khan\n  \nChitra M\nAsha Rao"})
check("names go in", r.status_code == 200, r.text[:150])
d = r.json()
check("blank lines are not names", d["total"] == 3, str(d))
check("and a repeat is not a second child", d["added"] == 3, str(d))

r = teach.post(f"/api/teacher/class/{klass.id}/roster",
               json={"names": "Asha Rao\nDeepa S"})
check("retyping the list adds only the new one",
      r.json()["added"] == 1 and r.json()["total"] == 4, str(r.json()))

# ---- signing in with the code alone ------------------------------------
print("\nSigning in with nothing")
anon = TestClient(main.app)
r = anon.post("/api/craxlearn/code", json={"code": CODE.lower()})
check("the code works in any case", r.status_code == 200, r.text[:120])
found = r.json()
check("it names the class", found["class_name"] == "7-B", str(found))
check("and lists who is free", len(found["names"]) == 4, str(found))
check("and says the register is ready", found["roster_ready"] is True)
check("and leaks nothing else",
      set(found) == {"class_id", "class_name", "school", "names",
                     "roster_ready", "archived"}, str(set(found)))

r = anon.post("/api/craxlearn/code", json={"code": "NOPE99"})
check("a wrong code finds nothing", r.status_code == 404, str(r.status_code))

r = anon.post("/api/craxlearn/code", json={"code": other.join_code})
check("a class with no register says so",
      r.json()["roster_ready"] is False, str(r.json()))

asha = [n for n in found["names"] if n["name"] == "Asha Rao"][0]
r = anon.post("/api/craxlearn/claim",
              json={"code": CODE, "roster_id": asha["id"]})
check("taking a name signs you in", r.status_code == 200, r.text[:150])
check("as that name", r.json().get("name") == "Asha Rao", r.text[:120])
check("the session works",
      anon.get("/api/auth/me").status_code == 200)

me = anon.get("/api/craxlearn/me").json()
check("and lands in the class",
      any(c["name"] == "7-B" for c in me.get("classes") or []), str(me.get("classes")))

# These two pinned the old behaviour, and the old behaviour was the bug.
#
# The name used to vanish from the register once claimed, and a second claim
# was refused with 409. For a class-code account the register row IS the
# credential — synthetic email, random password nobody holds — so a child who
# signed out found their name gone and had no way back to their work. Signing
# out deleted the account.
#
# The name stays, marked taken, and tapping it returns the SAME account. The
# cost is stated rather than hidden: whoever holds the class code can sign in
# as anyone on that register. Two things bound it — the code is rotatable,
# and sessions are single, so a second device signs the first one out with a
# message rather than sharing the account silently.
r = anon.post("/api/craxlearn/code", json={"code": CODE})
row = [n for n in r.json()["names"] if n["name"] == "Asha Rao"]
check("the name stays on the list, so its owner can come back",
      len(row) == 1, str(r.json()["names"]))
check("marked as one that has been taken", bool(row and row[0]["taken"]))

second = TestClient(main.app)
r = second.post("/api/craxlearn/claim",
                json={"code": CODE, "roster_id": asha["id"]})
check("tapping it again returns that same account, not a new one",
      r.status_code == 200 and r.json().get("returning") is True,
      f"{r.status_code} {r.text[:80]}")
check("and the first device is signed out rather than sharing it",
      anon.get("/api/auth/me").status_code == 401,
      str(anon.get("/api/auth/me").status_code))

# Proving that just signed `anon` out, and the rest of this file is written
# from Asha's side. Tap the name again to come back — which is the whole
# point of the change, so it is worth exercising here anyway.
main._CODE_TRIES.clear()
main._CODE_FAILS.clear()
anon.post("/api/craxlearn/claim", json={"code": CODE, "roster_id": asha["id"]})
check("and Asha can take her account back",
      anon.get("/api/auth/me").status_code == 200,
      str(anon.get("/api/auth/me").status_code))

bilal = [n for n in found["names"] if n["name"] == "Bilal Khan"][0]
r = second.post("/api/craxlearn/claim",
                json={"code": other.join_code, "roster_id": bilal["id"]})
check("a name cannot be claimed through another class's code",
      r.status_code == 404, str(r.status_code))

# ---- what a class-code account cannot reach ----------------------------
print("\nWhat a class login is not")
u = db.query(main.User).filter(main.User.name == "Asha Rao").order_by(
    main.User.id.desc()).first()
check("the account is marked as a class login", u.kind == "classcode", str(u.kind))
check("with an unroutable address", u.email.endswith("@classcode.invalid"),
      u.email)

for path in ("/api/jobs?limit=1", "/api/career/roles", "/api/billing/me",
             "/api/resume/extract", "/api/me/invites"):
    r = anon.get(path)
    check(f"no {path.split('?')[0]}", r.status_code in (403, 405),
          str(r.status_code))
check("and the reason is the login itself",
      anon.get("/api/jobs?limit=1").json().get("craxlearn") == "classcode",
      anon.get("/api/jobs?limit=1").text[:120])

# The school's own setting must not be able to open it.
school.product = "both"
db.commit()
r = anon.get("/api/jobs?limit=1")
check("even when the school buys the job board too",
      r.status_code == 403, str(r.status_code))
check("it is still the class login that closes it",
      r.json().get("craxlearn") == "classcode", r.text[:120])
# And a stated adult date of birth must not open it either.
u.dob = dt.date(1990, 1, 1)
db.commit()
check("and an adult birthday does not open it",
      anon.get("/api/jobs?limit=1").status_code == 403)
school.product = "craxlearn"
db.commit()

# The teaching half is entirely intact, which is the point.
for path in ("/api/curriculum", "/api/net", "/api/lab", "/api/sql/board",
             "/api/craxlearn/me", "/api/class/mine"):
    check(f"but {path} works", anon.get(path).status_code == 200,
          str(anon.get(path).status_code))

# ---- study material ----------------------------------------------------
print("\nStudy material")
r = teach.post(f"/api/teacher/class/{klass.id}/material/link",
               json={"title": "Osmosis notes", "url": "https://example.org/o",
                     "subject": "Biology", "note": "Read before Friday"})
check("a link goes up", r.status_code == 200, r.text[:150])
link_id = r.json()["material"]["id"]

r = teach.post(f"/api/teacher/class/{klass.id}/material/link",
               json={"title": "Bad", "url": "javascript:alert(1)"})
check("a link that is not a link is refused", r.status_code == 400,
      str(r.status_code))
r = teach.post(f"/api/teacher/class/{klass.id}/material/link",
               json={"title": "Bad", "url": "example.org"})
check("and so is one with no scheme", r.status_code == 400, str(r.status_code))

pdf = b"%PDF-1.4\n% a very small file\n"
r = teach.post(f"/api/teacher/class/{klass.id}/material/file",
               files={"file": ("chapter.pdf", _io.BytesIO(pdf), "application/pdf")},
               data={"title": "Chapter 3"})
check("a PDF goes up", r.status_code == 200, r.text[:200])
file_id = r.json()["material"]["id"]
check("with its size recorded",
      r.json()["material"]["size"] == len(pdf), str(r.json()["material"]))

r = teach.post(f"/api/teacher/class/{klass.id}/material/file",
               files={"file": ("x.exe", _io.BytesIO(b"MZ"),
                               "application/x-msdownload")})
check("an executable is refused", r.status_code == 400, str(r.status_code))
r = teach.post(f"/api/teacher/class/{klass.id}/material/file",
               files={"file": ("big.pdf",
                               _io.BytesIO(b"x" * (main.MATERIAL_MAX + 10)),
                               "application/pdf")})
check("and so is something over the limit", r.status_code == 400,
      str(r.status_code))

d = anon.get(f"/api/class/{klass.id}/materials").json()
check("the student sees both", len(d["materials"]) == 2, str(d)[:200])
# Subject and author were in the schema from the start and reached neither
# the payload nor the screen, so a class got a reading list from nobody in
# particular, for no lesson in particular.
link = [m for m in d["materials"] if m["kind"] == "link"][0]
check("with the subject it was filed under", link["subject"] == "Biology",
      str(link))
check("and the name of whoever put it there", link["by"] == "Teacher T",
      str(link))
check("the link carries its address",
      any(m.get("url") == "https://example.org/o" for m in d["materials"]))

r = anon.get(f"/api/material/{file_id}/file")
check("and can open the file", r.status_code == 200, str(r.status_code))
check("getting the real bytes back", r.content == pdf, str(r.content[:20]))

# The negative that matters: a guessed id from outside the class.
outsider = TestClient(main.app)
oemail = f"out{stamp}@example.com"
outsider.post("/api/auth/signup", json={"name": "Outsider O", "email": oemail,
                                        "password": "ClassCodePass123!"})
r = outsider.get(f"/api/material/{file_id}/file")
check("somebody outside the class cannot fetch the file",
      r.status_code == 403, str(r.status_code))
r = outsider.get(f"/api/class/{klass.id}/materials")
check("nor even list what exists", r.status_code == 403, str(r.status_code))
r = outsider.post(f"/api/teacher/class/{klass.id}/material/link",
                  json={"title": "x", "url": "https://x.example"})
check("nor add anything", r.status_code in (403, 404), str(r.status_code))

r = anon.delete(f"/api/teacher/material/{link_id}")
check("a student cannot delete material", r.status_code == 403,
      str(r.status_code))
r = teach.delete(f"/api/teacher/material/{link_id}")
check("the teacher can", r.status_code == 200, str(r.status_code))
check("and it is gone",
      len(anon.get(f"/api/class/{klass.id}/materials").json()["materials"]) == 1)

# ---- a claimed name is an account, not a line of text ------------------
print("\nThe register after people have signed in")
roster = teach.get(f"/api/teacher/class/{klass.id}/roster").json()
taken = [x for x in roster["roster"] if x["claimed"]][0]
r = teach.delete(f"/api/teacher/roster/{taken['id']}")
check("a claimed name cannot be deleted from under its owner",
      r.status_code == 400, str(r.status_code))
free = [x for x in roster["roster"] if not x["claimed"]][0]
check("an unclaimed one can",
      teach.delete(f"/api/teacher/roster/{free['id']}").status_code == 200)

# ---- the reset, and every time it must do nothing ----------------------
print("\nThe reset")
admin_c = TestClient(main.app)
aemail = f"adm{stamp}@example.com"
admin_c.post("/api/auth/signup", json={"name": "Admin A", "email": aemail,
                                       "password": "ClassCodePass123!"})
au = db.query(main.User).filter(main.User.email == aemail).first()
au.is_admin = True
db.commit()

r = teach.get("/api/admin/reset-users/preview")
check("a teacher cannot even preview it", r.status_code == 403,
      str(r.status_code))
r = anon.post("/api/admin/reset-users", json={"confirm": main.RESET_PHRASE})
check("nor a student run it", r.status_code == 403, str(r.status_code))

pre = admin_c.get("/api/admin/reset-users/preview")
check("an admin can preview", pre.status_code == 200, str(pre.status_code))
p = pre.json()
check("and is told what it destroys",
      all(k in p for k in ("users", "paying", "submissions", "warning")),
      str(sorted(p)))
check("and how many accounts", p["users"] >= 3, str(p["users"]))

# Everything that is NOT the phrase. Case and surrounding space are
# forgiven — the guard is "typed the whole sentence out", not "held shift
# correctly" — so neither of those appears here. A near miss does.
before = db.query(main.User).count()
for bad in ("", "yes", "confirm", "DELETE ALL ACCOUNTS",
            "DELETE ALL NON ADMIN ACCOUNT",
            "DELETE ALL NON-ADMIN ACCOUNTS",
            "please DELETE ALL NON ADMIN ACCOUNTS now"):
    r = admin_c.post("/api/admin/reset-users", json={"confirm": bad})
    check(f"{bad!r} does not run it", r.status_code == 400, str(r.status_code))
check("and nothing was deleted by any of them",
      db.query(main.User).count() == before, str(db.query(main.User).count()))

# The real thing, on this test database. Lower case and padded, to pin that
# both are accepted rather than leaving it to be discovered by an admin who
# typed it correctly and was told no.
r = admin_c.post("/api/admin/reset-users",
                 json={"confirm": "  " + main.RESET_PHRASE.lower() + "  "})
check("the exact sentence runs it, in any case, padded or not",
      r.status_code == 200, r.text[:150])
out = r.json()
check("it reports what it did", out["deleted"] >= 3, str(out))

db.expire_all()
check("admins survive",
      db.query(main.User).filter(main.User.is_admin == True).count() >= 1)  # noqa: E712
check("everybody else is gone",
      db.query(main.User).filter(main.User.is_admin == False).count() == 0,  # noqa: E712
      str(db.query(main.User).filter(main.User.is_admin == False).count()))
check("the school is kept", db.get(main.School, school.id) is not None)
check("and the class with its code",
      db.get(main.Klass, klass.id) is not None)

# The one that would otherwise strand a class: every name freed, so the
# register works again rather than being claimed by accounts that are gone.
left = db.query(main.RosterName).filter(
    main.RosterName.class_id == klass.id).all()
check("and every register name is free again",
      left and all(r_.claimed_by == 0 for r_ in left),
      str([(r_.name, r_.claimed_by) for r_ in left]))

check("the old session no longer works",
      anon.get("/api/craxlearn/me").status_code == 401,
      str(anon.get("/api/craxlearn/me").status_code))

db.close()
print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
