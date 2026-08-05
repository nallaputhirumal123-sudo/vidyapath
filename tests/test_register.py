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
        → that name is theirs, and tapping it again returns them to it

That last step used to read "and nobody else can be it", which was achieved by
taking the name off the list — and taking the name off the list is how a child
who signed out lost their account for good. The register row is the credential
for a class-code account: the email receives nothing and the password is
random bytes nobody holds. So the name stays.

And the rule that protects work already done: adding names never removes one a
learner has claimed. A teacher retyping the list to fix one spelling must not
delete the account a child has homework in.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"   # local test database; refused on a deployment
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

# These two used to assert the opposite, and the opposite was the bug: the
# name came off the list and a second tap was refused with a 409.
#
# For a class-code account the register row IS the credential — the email
# receives nothing and the password is random bytes nobody holds — so hiding
# a claimed name meant a child who signed out could never get back in, and
# their work was gone with them. Signing out was account deletion.
#
# The name therefore stays, marked, and tapping your own signs you back into
# the same account. What that costs is stated rather than hidden: the class
# code is the class's credential, so anybody holding it can now sign in as
# anybody on that register, not only as a name nobody has taken yet. It was
# already three-quarters true — any unclaimed name was open to any code
# holder. The lever is the code, which is per-class and rotatable.
other = TestClient(main.app)
r = other.post("/api/craxlearn/code", json={"code": CODE})
row = [n for n in r.json()["names"] if n["name"] == "Asha Rao"]
check("a claimed name stays on the register, so its owner can return",
      len(row) == 1, str([n["name"] for n in r.json()["names"]]))
check("and it is marked as one that has been used",
      bool(row and row[0].get("taken")))
r = other.post("/api/craxlearn/claim", json={"code": CODE, "roster_id": rid})
check("tapping it again returns the SAME account, never a second one",
      r.status_code == 200 and r.json().get("returning") is True,
      f"{r.status_code} {r.text[:80]}")
_row = db.get(main.RosterName, rid)
db.refresh(_row)
check("which is the account the register row already pointed at",
      _o_id := other.get("/api/auth/me").json().get("id"),
      "no session")
check("and the row still points at that one account",
      _row.claimed_by == _o_id, f"{_row.claimed_by} vs {_o_id}")

# And the safeguard that makes the trade-off above liveable: sessions are
# single. A second device signing into this account ends the first one's
# session and says why, so somebody else using your name is something you
# find out about rather than something that happens quietly behind you.
_a = anon.get("/api/auth/me")
check("the first device is signed out, and told why",
      _a.status_code == 401 and "somewhere else" in _a.text,
      f"{_a.status_code} {_a.text[:80]}")

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
