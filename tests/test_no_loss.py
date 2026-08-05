"""Every way I could think of to lose a class-code account, tried on purpose.

A class-code account is unlike every other account here: the email is
synthetic and receives nothing, the password hash is random bytes nobody
holds, and the row on the register IS the credential. There is no reset, no
recovery, no second route. So anything that removes that row is not a tidy-up
— it is permanent account deletion, and the child's work goes with it.

Eight tables cascade off a class row. That made deleting one class a single
click that destroyed the register, the assignments, the submissions, the
discussion, the study material and the timetable, and it asked nothing first.

So this suite is written as an attack on the data rather than a tour of the
features. Each block tries to make something disappear — sign out, retype the
register, fix a spelling, take a child off the list, rotate the code, archive
the year, delete the class — and then goes and checks that the account, the
class, and the notes saved into it are all still there.

The one case that must WORK is deliberate deletion. "Cannot be deleted" and
"cannot be deleted by accident" are different products, and a school that
genuinely wants a class gone is entitled to that.
"""
import os, sys, time, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"   # local test database; refused on a deployment
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
    (P if c else F).append(n + (f" — {d}" if d else ""))

def fresh():
    main._CODE_TRIES.clear(); main._CODE_FAILS.clear()

PW = "NoLossPass1!"
db = main.SessionLocal()

def staff(tag):
    c = TestClient(main.app)
    em = f"nl{tag}{st}@example.com"
    c.post("/api/auth/signup", json={"name": "Staff " + tag, "email": em,
                                     "password": PW})
    u = db.query(main.User).filter(main.User.email == em).first()
    u.dob = dt.date(1986, 2, 3)
    db.commit()
    return c, em

sc = main.School(name=f"No Loss School {st}")
db.add(sc); db.commit(); db.refresh(sc)
HEAD = f"HEAD-N{str(st)[-4:]}"
db.add(main.TeacherCode(code=HEAD, school=sc.name, school_id=sc.id,
                        is_head=True, active=True))
db.commit(); db.close()

head, _ = staff("head")
head.post("/api/class/join", json={"code": HEAD})
mk = head.post("/api/teacher/class", json={"name": f"Class 7-B {st}"}).json()
CID, CODE = mk["id"], mk["join_code"]
head.post(f"/api/teacher/class/{CID}/roster",
          json={"names": "Bittu K, 701\nDeepa M, 702\nEshan R, 703"})

def register(code=None):
    fresh()
    return TestClient(main.app).post("/api/craxlearn/code",
                                     json={"code": code or CODE}).json()

def sign_in(name, code=None):
    """A child taps their name. Returns their client and their user id."""
    fresh()
    c = TestClient(main.app)
    d = c.post("/api/craxlearn/code", json={"code": code or CODE}).json()
    row = [n for n in d.get("names", []) if n["name"].startswith(name)]
    if not row:
        return c, None
    r = c.post("/api/craxlearn/claim",
               json={"code": code or CODE, "roster_id": row[0]["id"]})
    if r.status_code != 200:
        return c, None
    return c, c.get("/api/auth/me").json().get("id")

# ---------- a child, with work behind them ----------
kid, KID = sign_in("Bittu")
ck("a child signs in", bool(KID), "no account")
NOTE = f"my note about photosynthesis {st}"
r = kid.post(f"/api/class/{CID}/discussion",
             json={"subject": "Science", "body": NOTE})
ck("and saves something", r.status_code == 200, r.text[:120])

def still_there(why):
    """The account, its class, and the note it saved. All three, every time."""
    d = main.SessionLocal()
    u = d.get(main.User, KID)
    post = d.query(main.ClassPost).filter(main.ClassPost.body == NOTE).first()
    row = (d.query(main.RosterName)
             .filter(main.RosterName.claimed_by == KID).first())
    d.close()
    ck(f"account survives {why}", u is not None and u.is_active)
    ck(f"saved note survives {why}", post is not None and post.user_id == KID)
    ck(f"register row survives {why}", row is not None)

# ---------- 1. signing out ----------
kid.post("/api/auth/logout")
still_there("signing out")
back, BACK_ID = sign_in("Bittu")
ck("and they get back into the SAME account", BACK_ID == KID,
   f"{BACK_ID} vs {KID}")

# ---------- 2. the teacher retypes the register ----------
r = head.post(f"/api/teacher/class/{CID}/roster",
              json={"names": "Bittu K, 701\nDeepa M, 702\nEshan R, 703\n"
                             "Farah N, 704"})
ck("retyping the register adds only the new name",
   r.status_code == 200 and r.json().get("added") == 1,
   str(r.json().get("added")))
still_there("the register being retyped")
ck("and no second row appeared for the same child",
   len([x for x in r.json()["roster"] if x["name"].startswith("Bittu")]) == 1)

# ---------- 3. a spelling is fixed ----------
rid = [x["id"] for x in r.json()["roster"] if x["name"].startswith("Bittu")][0]
fix = head.patch(f"/api/teacher/roster/{rid}",
                 json={"name": "Bittu Kumar", "student_code": "701"})
ck("a claimed name can be corrected", fix.status_code == 200, fix.text[:140])
still_there("a spelling being corrected")
c2, id2 = sign_in("Bittu Kumar")
ck("they sign in under the corrected name, same account", id2 == KID,
   f"{id2} vs {KID}")

# ---------- 4. deleting a claimed name is refused ----------
d = head.delete(f"/api/teacher/roster/{rid}")
ck("deleting a claimed name is refused", d.status_code == 400, str(d.status_code))
still_there("an attempt to delete the name")

# ---------- 5. taking a child off the register ----------
rm = head.post(f"/api/teacher/roster/{rid}/remove")
ck("a child can be taken off the register", rm.status_code == 200, rm.text[:140])
still_there("being taken off the register")
ck("their name stops being offered at sign-in",
   not [n for n in register().get("names", []) if n["name"].startswith("Bittu")])
ck("the others are still offered", len(register().get("names", [])) == 3,
   str([n["name"] for n in register().get("names", [])]))
_, blocked = sign_in("Bittu Kumar")
ck("and nobody can sign in as them", blocked is None)

# ...and putting them back
pb = head.post(f"/api/teacher/roster/{rid}/remove?on=false")
ck("putting them back works", pb.status_code == 200, pb.text[:140])
c3, id3 = sign_in("Bittu Kumar")
ck("and it is still their account", id3 == KID, f"{id3} vs {KID}")

# retyping the register also puts somebody back, since that is what a teacher
# will actually do
head.post(f"/api/teacher/roster/{rid}/remove")
r = head.post(f"/api/teacher/class/{CID}/roster",
              json={"names": "Bittu Kumar, 701"})
ck("retyping the register restores a removed child",
   r.json().get("restored") == 1, str(r.json()))
c4, id4 = sign_in("Bittu Kumar")
ck("same account again", id4 == KID, f"{id4} vs {KID}")

# ---------- 6. the code is rotated ----------
rot = head.post(f"/api/head/class/{CID}/rotate", json={})
NEW = rot.json().get("join_code") or rot.json().get("code")
still_there("the class code being rotated")
c5, id5 = sign_in("Bittu Kumar", NEW)
ck("they sign in with the new code, same account", id5 == KID,
   f"{id5} vs {KID}")
CODE = NEW

# ---------- 7. the year ends: archiving ----------
ar = head.post(f"/api/teacher/class/{CID}/archive")
ck("a class can be archived", ar.status_code == 200 and ar.json()["archived"],
   ar.text[:140])
still_there("the class being archived")
c6, id6 = sign_in("Bittu Kumar")
ck("a child already on it still gets back to their work", id6 == KID,
   f"{id6} vs {KID}")
ck("but an archived class takes nobody new",
   not [n for n in register().get("names", []) if n["name"].startswith("Farah")],
   str([n["name"] for n in register().get("names", [])]))
un = head.post(f"/api/teacher/class/{CID}/archive?on=false")
ck("and it can be brought back", un.status_code == 200
   and not un.json()["archived"], un.text[:140])
ck("with the whole register again",
   len(register().get("names", [])) == 4,
   str([n["name"] for n in register().get("names", [])]))

# ---------- 8. deleting the class ----------
dl = head.delete(f"/api/teacher/class/{CID}")
ck("deleting a class that holds work is REFUSED", dl.status_code == 409,
   str(dl.status_code))
body = dl.json().get("detail", {})
ck("and it says what it holds",
   isinstance(body, dict) and body.get("holds", {}).get("students", 0) >= 1,
   str(body)[:200])
ck("and it names what must be typed to mean it",
   isinstance(body, dict) and body.get("needs_confirm"), str(body)[:120])
still_there("a refused class deletion")

ck("a wrong confirmation does not delete it",
   head.delete(f"/api/teacher/class/{CID}?confirm=whatever").status_code == 409)
still_there("a mistyped confirmation")

# An empty class is a typo and deletes without ceremony.
empty = head.post("/api/teacher/class", json={"name": f"Typo {st}"}).json()
ck("an empty class deletes without ceremony",
   head.delete(f"/api/teacher/class/{empty['id']}").status_code == 200)

# And a school that really means it can still do it.
gone = head.delete(f"/api/teacher/class/{CID}?confirm=Class 7-B {st}")
ck("typing the class name does delete it", gone.status_code == 200,
   gone.text[:140])
d = main.SessionLocal()
ck("the class really is gone",
   d.get(main.Klass, CID) is None)
ck("the account itself still exists — the school deleted a class, not a child",
   d.get(main.User, KID) is not None)
# Nothing of the class may outlive it. SQLite does not enforce ON DELETE
# CASCADE unless the pragma is on, so the class row went and every child row
# stayed — and because SQLite reuses a freed row id, the NEXT class created
# opened with the dead one's register already on it, claimed by children who
# were never in the room. Postgres cascaded; SQLite did not; the same call
# did two different things.
left = {m.__tablename__: d.query(m).filter(m.class_id == CID).count()
        for m in (main.RosterName, main.ClassMember, main.SubjectSlot,
                  main.Assignment, main.ClassPost, main.Material,
                  main.ScheduleItem)}
ck("nothing of the class is left behind", not any(left.values()), str(left))
d.close()

# The proof that matters, done the way it actually bit: make another class
# and look at its register.
nxt = head.post("/api/teacher/class", json={"name": f"Next 7-B {st}"}).json()
fresh_reg = head.get(f"/api/teacher/class/{nxt['id']}/roster").json()
ck("a new class starts with nobody on its register",
   fresh_reg.get("total") == 0 and not fresh_reg.get("roster"),
   str(fresh_reg)[:200])
head.delete(f"/api/teacher/class/{nxt['id']}")

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
