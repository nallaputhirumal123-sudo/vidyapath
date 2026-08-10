"""Your own account: the details, the password, the plan, and the way to ask.

Tapping your own name in the sidebar did nothing at all. It is the first
place everybody presses looking for a password, a phone number or a bill,
and what they wanted was spread across five screens: the plan on the billing
page, the school on the teacher dashboard, the phone number nowhere, and no
way to change a password without signing out and pretending to have
forgotten it.

Two rules in here are worth stating, because both are refusals rather than
features and a later reader will be tempted to relax them.

**The old password is required to set a new one.** Without that, anybody who
reaches an unlocked laptop for ten seconds owns the account permanently — and
on a school device left signed in at a desk, ten seconds is not a stretch.

**The sign-in address is shown and not editable.** Changing your own address
in a settings panel is how somebody locks themselves out of a school account
with one typo and no way back. The office issues and repairs addresses,
because the office can prove who you are before it moves them.

And a password change drops every other session. Somebody changes a password
because they think another person has it; a change that leaves that person
signed in has done nothing at all.
"""
import io
import os
import sys
import time
import datetime as dt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"

import main                                        # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
main.Base.metadata.create_all(bind=main.engine)
main._migrate_columns()
main.send_email = lambda *a, **k: None
P, F = [], []


def ck(n, c, d=""):
    print(("PASS " if c else "FAIL ") + n + (f" — {d}" if d else ""),
          flush=True)
    (P if c else F).append(n)


u = str(int(time.time())) + str(os.getpid())
db = main.SessionLocal()
c = TestClient(main.app)
em = f"acct{u}@example.com"
OLD, NEW = "AcctPass1!", "AcctPass2!"
c.post("/api/auth/signup",
       json={"name": "Acct Person", "email": em, "password": OLD})
row = db.query(main.User).filter(main.User.email == em).first()
row.dob = dt.date(1990, 1, 1)
db.commit()

print("\none screen with what was on five")
r = c.get("/api/me/account")
ck("it loads", r.status_code == 200, str(r.status_code))
a = r.json() if r.status_code == 200 else {}
ck("the address you sign in with", a.get("email") == em)
ck("the plan", "plan" in a, str(a.get("plan")))
ck("how many devices are on it", "devices" in a and "max_devices" in a)
ck("and somebody to write to", "@" in (a.get("support") or ""),
   "an account you cannot get into needs a human, not a form that needs a "
   "sign-in")

print("\na phone number, which had nowhere to live before")
r = c.patch("/api/me/account", json={"name": "", "phone": "+91 98765 43210"})
ck("a real one is kept", r.status_code == 200 and
   r.json().get("phone") == "+91 98765 43210", r.text[:90])
r = c.patch("/api/me/account", json={"name": "", "phone": "ring me at school"})
ck("a sentence is refused", r.status_code == 400, str(r.status_code))
ck("and says what a number looks like",
   "digits" in r.text.lower(), r.text[:80])
r = c.patch("/api/me/account", json={"name": "", "phone": ""})
ck("clearing it is allowed", r.status_code == 200 and
   r.json().get("phone") == "", r.text[:80])

print("\nthe name follows, because it is the one on every screen")
r = c.patch("/api/me/account", json={"name": "Acct Renamed", "phone": ""})
ck("a new name is kept", r.status_code == 200 and
   r.json().get("name") == "Acct Renamed", r.text[:80])
r = c.patch("/api/me/account", json={"name": "A", "phone": ""})
ck("one letter is refused", r.status_code == 400, str(r.status_code))

print("\nthe address is not editable here, on purpose")
_IDX = io.open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
ck("the account screen prints it rather than offering a box",
   'You sign in as <b style="color:var(--text)">${esc(a.email)}</b>' in _IDX)
ck("and says who can move it",
   "ask your school office" in _IDX,
   "one typo in a self-service box locks somebody out of a school account "
   "with no way back")
ck("the route takes no address either",
   "email" not in main.AccountIn.model_fields,
   "a field the screen does not show is still a field the network has")

print("\nchanging a password needs the old one")
r = c.post("/api/me/password", json={"current": "NotMyPassword1", "new": NEW})
ck("a wrong current password is refused", r.status_code == 400,
   str(r.status_code))
ck("and told plainly", "current password" in r.text, r.text[:80])
r = c.post("/api/me/password", json={"current": OLD, "new": "short"})
ck("a short new one is refused", r.status_code == 422 or r.status_code == 400,
   str(r.status_code))
r = c.post("/api/me/password", json={"current": OLD, "new": OLD})
ck("and the one you already have is refused",
   r.status_code == 400, str(r.status_code))

r = c.post("/api/me/password", json={"current": OLD, "new": NEW})
ck("the right one goes through", r.status_code == 200, r.text[:90])
db.expire_all()
row = db.query(main.User).filter(main.User.email == em).first()
ck("the new password is the one that works now",
   main.verify_pw(NEW, row.password_hash))
ck("and the old one no longer does", not main.verify_pw(OLD, row.password_hash))

print("\nand every other device is signed out with it")
ck("it says so", "signed out" in (r.json().get("message") or ""),
   r.json().get("message"))
ck("this session still works", c.get("/api/me/account").status_code == 200,
   "signing yourself out by changing your own password is a trap")

print("\nnone of it is reachable without being signed in")
anon = TestClient(main.app)
ck("reading it", anon.get("/api/me/account").status_code == 401)
ck("changing it", anon.patch("/api/me/account",
                             json={"name": "x", "phone": ""}).status_code == 401)
ck("or the password",
   anon.post("/api/me/password",
             json={"current": OLD, "new": NEW}).status_code == 401)

print("\nand the sidebar name is a way in")
ck("your own name opens it", 'id="whoOpen"' in _IDX,
   "it did nothing, and it is where everybody presses first")
ck("by keyboard too", 'if(e.key==="Enter"||e.key===" ")' in _IDX)
ck("the router knows the page", 'v.page==="account"' in _IDX)

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\nPASSED {len(P)}   FAILED {len(F)}")
sys.exit(1 if F else 0)
