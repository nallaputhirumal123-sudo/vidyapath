"""A head teacher must be able to put children on a register.

The class screen showed the register and said, when empty, "No students yet —
share the code." That is not what happens. A learner signing in with a class
code is shown the names on the register and taps their own; with no register
there is nothing to tap and /api/craxlearn/code answers roster_ready: false.
The one instruction on screen was the one thing that could not work.

The route has always existed and always permitted a head teacher. Craxlearn had
a page for it. craxle.com never grew one — so a head teacher there could create
classes, subjects and codes, and then had no way to put a single child on a
register.

What is pinned here is the whole loop, because each half was already fine
separately and it was the join between them that was missing:

    a head teacher types the names
      → a learner signs in with the class code and taps one
        → that name is taken and nobody else can be it

And the rule that protects work already done: adding names never removes one a
learner has claimed. A teacher retyping the list to fix one spelling must not
delete the account a child has homework in.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"

import datetime as dt                              # noqa: E402
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


def account(tag, admin=False):
    cl = TestClient(main.app)
    email = f"rg{tag}{stamp}@example.com"
    r = cl.post("/api/auth/signup", json={"name": f"Person {tag}",
                                          "email": email,
                                          "password": "RegPass123!"})
    assert r.status_code == 200, r.text
    u = db.query(main.User).filter(main.User.email == email).first()
    u.dob = dt.date(1990, 1, 1)
    if admin:
        u.is_admin = True
    db.commit()
    return cl, u


head, head_user = account("head", admin=True)
outsider, _ = account("out")

r = head.post("/api/teacher/class", json={"name": f"7-A {stamp}"})
assert r.status_code == 200, r.text
klass = r.json()
CID, CODE = klass["id"], klass["join_code"]

print("\nthe head teacher types the register")
r = head.post(f"/api/teacher/class/{CID}/roster",
              json={"names": "Asha Rao\nVikram Singh\nMeera Pillai"})
check("the register accepts names", r.status_code == 200, r.text[:70])

r = head.get(f"/api/teacher/class/{CID}/roster")
d = r.json()
check("all three are on it", d["total"] == 3, str(d["total"]))
check("all three are free to claim", d["free"] == 3)
check("each name carries an id so it can be removed",
      all(x.get("id") for x in d["roster"]))

print("\nwhich is exactly what the learner needed")
anon = TestClient(main.app)
main._CODE_TRIES.clear()
main._CODE_FAILS.clear()
r = anon.post("/api/craxlearn/code", json={"code": CODE})
d = r.json()
check("the class is now ready to sign in to", d.get("roster_ready") is True,
      "this was False, and the screen told teachers to share the code anyway")
check("and the names are offered",
      sorted(n["name"] for n in d["names"])
      == ["Asha Rao", "Meera Pillai", "Vikram Singh"])

print("\ntapping a name takes it")
rid = [n["id"] for n in d["names"] if n["name"] == "Asha Rao"][0]
r = anon.post("/api/craxlearn/claim", json={"code": CODE, "roster_id": rid})
check("the learner is signed in", r.status_code == 200, r.text[:70])

other = TestClient(main.app)
r = other.post("/api/craxlearn/code", json={"code": CODE})
check("that name is no longer on offer",
      "Asha Rao" not in [n["name"] for n in r.json()["names"]])
r = other.post("/api/craxlearn/claim", json={"code": CODE, "roster_id": rid})
check("and cannot be taken twice", r.status_code == 409, f"got {r.status_code}")

print("\nretyping the list does not delete a child's account")
r = head.post(f"/api/teacher/class/{CID}/roster",
              json={"names": "Asha Rao\nVikram Singh\nMeera Pillai\nRohan D"})
d = head.get(f"/api/teacher/class/{CID}/roster").json()
check("the new name is added", d["total"] == 4, str(d["total"]))
check("and the claimed one is still claimed",
      any(x["name"] == "Asha Rao" and x["claimed"] for x in d["roster"]),
      "a teacher fixing a spelling must not delete work")

print("\nonly this class's teachers may touch it")
r = outsider.post(f"/api/teacher/class/{CID}/roster", json={"names": "Sneaky S"})
check("somebody else's account cannot add names", r.status_code in (403, 404),
      f"got {r.status_code}")
r = outsider.get(f"/api/teacher/class/{CID}/roster")
check("nor read the register", r.status_code in (403, 404),
      f"got {r.status_code} — a register is a list of children's names")

print("\nremoving is possible and specific")
free_id = [x["id"] for x in d["roster"] if not x["claimed"]][0]
r = head.delete(f"/api/teacher/roster/{free_id}")
check("a free name can be removed", r.status_code == 200, r.text[:60])
check("and the register shrinks",
      head.get(f"/api/teacher/class/{CID}/roster").json()["total"] == 3)

print(f"\nPASSED {PASS}   FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
