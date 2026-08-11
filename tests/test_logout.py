"""Signing out has to end the session, and for an admin it did not.

Reported as "admin logout is still pending". Two faults, and they compound.

**The server did not revoke anything.** /api/auth/logout deleted the browser
cookie and stopped there, so the token inside it stayed valid. Anything
holding a copy — another browser, a machine somebody walked away from, a
cookie captured earlier — went on working after the person believed they had
signed out. The computer at the front of a classroom, used by whoever is
teaching that period, is exactly the case this matters for.

**And an admin was exempt from the check that would have caught it.**
current_user skipped the "is this token still in the user's list" test for
admins, because running the site means several browsers at once and being
locked out of your own admin panel is a cost with no benefit. The reasoning
was sound and the mechanism was wrong: it made an administrator's token
unkillable. Removing the token from the list is what ends a session for
everybody else, and for the one account that can do the most damage the list
was never read.

The exemption is gone and what it was for is handled properly instead: an
admin is staff, so _device_cap gives them four devices rather than one and
their own second browser does not push them off. The rule and the reason
match now, rather than one being suspended to paper over the other.

Only the device signing out is revoked. Signing out on a phone must not end
the session on the laptop.
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
MAIN = io.open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
main.Base.metadata.create_all(bind=main.engine)
main._migrate_columns()
P, F = [], []


def ck(n, c, d=""):
    print(("PASS " if c else "FAIL ") + n + (f" — {d}" if d else ""),
          flush=True)
    (P if c else F).append(n)


def account(is_admin=False):
    u = str(int(time.time() * 1000)) + str(os.getpid())
    em = f"lo{'a' if is_admin else 'u'}{u}@example.com"
    db = main.SessionLocal()
    row = main.User(email=em, name="Logout Test",
                    password_hash=main.hash_pw("LogoutPass1!"),
                    is_active=True, is_admin=is_admin,
                    dob=dt.date(1985, 1, 1))
    db.add(row)
    db.commit()
    db.close()
    return em


def signed_in(em):
    c = TestClient(main.app)
    c.post("/api/auth/login", json={"email": em, "password": "LogoutPass1!"})
    return c


for label, admin in (("an ordinary account", False), ("an ADMIN", True)):
    print(f"\nsigning out on {label}")
    em = account(admin)
    a = signed_in(em)
    ck("signs in", a.get("/api/auth/me").status_code == 200)
    stolen = a.cookies.get("vp_session")
    ck("signs out", a.post("/api/auth/logout", json={}).status_code == 200)
    copy = TestClient(main.app)
    if stolen:
        copy.cookies.set("vp_session", stolen)
    r = copy.get("/api/auth/me")
    ck("and the token in that cookie is dead", r.status_code == 401,
       f"got {r.status_code} — a deleted cookie is not a revoked session")

print("\nbut only the device that signed out")
em = account(True)
a, b = signed_in(em), signed_in(em)
ck("both browsers work", a.get("/api/auth/me").status_code == 200
   and b.get("/api/auth/me").status_code == 200,
   "an admin is staff, so four devices — signing in twice must not kick you")
a.post("/api/auth/logout", json={})
ck("the other one is untouched", b.get("/api/auth/me").status_code == 200,
   "signing out on a phone must not end the session on the laptop")

print("\nthe pieces that make it true")
ck("the admin exemption is gone from the session check",
   "not user.is_admin\n            and payload.get(\"st\")" not in MAIN
   and "user.is_admin" not in MAIN.split(
       "# Keyed on the TOKEN carrying an `st`")[1].split("raise")[0],
   "it made an administrator's token unkillable")
ck("and what it was for is done by the device cap instead",
   "def _device_cap(user, db) -> int:" in MAIN)
ck("logout removes this device's token, not every token",
   "left = [s for s in _sessions(u) if s != mine]" in MAIN)
ck("and needs no valid session to work",
   "def logout(request: Request, response: Response,\n"
   "           db: Session = Depends(get_db)):" in MAIN,
   "an expired or forged cookie must still be deleted, not answered 401")
# Proved rather than read: a client holding nonsense still gets a clean
# sign-out instead of a 401 it cannot act on.
junk = TestClient(main.app)
junk.cookies.set("vp_session", "not-a-real-token")
ck("a cookie the server cannot read still signs out cleanly",
   junk.post("/api/auth/logout", json={}).status_code == 200)
ck("the emptied list does not switch the check off",
   'if (payload.get("st")\n            and payload.get("st") not in '
   "_sessions(user)):" in MAIN,
   "`if user.session_token and ...` is falsy once the last device signs "
   "out, so the final sign-out revoked a token and then honoured it")
ck("the cookie is deleted either way",
   'response.delete_cookie("vp_session", path="/")' in MAIN)

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\nPASSED {len(P)}   FAILED {len(F)}")
sys.exit(1 if F else 0)
