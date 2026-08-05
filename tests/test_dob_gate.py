"""Asking how old somebody is, without trapping the ones already paying.

The job board, being shown to employers and buying a subscription are for
adults. An account that has never said how old it is has not told us it is one,
and until now silence outside a school was believed.

REQUIRE_DOB is on. The code that wrote that flag warned exactly what turning it
on costs: every existing account without a date loses the job half until it
comes back and fills one in. That is the trade being accepted, not overlooked.

What it must not cost is somebody's own billing page. So there are two
different closures and telling them apart is the whole point:

    a stated age under 18   an answer. Everything closed, billing included,
                            because they cannot buy anyway.
    no date at all          a question we have not asked. The job board and
                            employer visibility close; Plans stays reachable,
                            because among those accounts are people already
                            paying, and locking somebody out of the page where
                            they cancel what they bought is not a safety
                            measure.

Both halves are asserted, and so is the one that would be easy to get wrong:
the hidden_pages the sidebar reads must hide exactly what the middleware
refuses, and nothing more. Two lists that disagree is a door drawn shut that
opens, or drawn open that does not.
"""
import os
import sys
import time
import datetime as dt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"   # local test database; refused on a deployment
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


def acct(tag, dob):
    c = TestClient(main.app)
    em = f"dg{tag}{stamp}@example.com"
    c.post("/api/auth/signup",
           json={"name": f"P{tag}", "email": em, "password": "DobPass123!"})
    u = db.query(main.User).filter(main.User.email == em).first()
    u.dob = dob
    db.commit()
    return c, u


print("\nthe setting itself")
check("a date of birth is asked of everybody", main.REQUIRE_DOB,
      "turning this on is the decision being made here")

print("\nsomebody who has said they are an adult")
grown, _ = acct("adult", dt.date(1990, 1, 1))
check("reaches the job board",
      grown.get("/api/jobs?limit=1").status_code == 200)
check("and their billing", grown.get("/api/billing/me").status_code == 200)
me = grown.get("/api/auth/me").json()
check("with nothing hidden", not me.get("hidden_pages"),
      str(me.get("hidden_pages")))

print("\nsomebody who has said they are fifteen")
child, _ = acct("child", dt.date.today().replace(
    year=dt.date.today().year - 15))
check("the job board is closed",
      child.get("/api/jobs?limit=1").status_code == 403)
check("and so is billing, because they cannot buy",
      child.get("/api/billing/me").status_code == 403)
me = child.get("/api/auth/me").json()
check("plans is hidden from them", "plans" in (me.get("hidden_pages") or []),
      str(me.get("hidden_pages")))

print("\nsomebody who has never said")
silent, silent_u = acct("silent", None)
r = silent.get("/api/jobs?limit=1")
check("the job board closes", r.status_code == 403, f"got {r.status_code}")
check("and says what to do about it",
      "date of birth" in (r.json().get("detail") or "").lower(),
      (r.json().get("detail") or "")[:70])
check("the reason is that we do not know, not that they are a child",
      r.json().get("craxlearn") == "dob_missing",
      str(r.json().get("craxlearn")))
check("but their own billing still opens",
      silent.get("/api/billing/me").status_code == 200,
      "somebody already paying must be able to cancel")

print("\nand the two lists agree")
me = silent.get("/api/auth/me").json()
hidden = me.get("hidden_pages") or []
check("the sidebar hides the job board", "careers" in hidden, str(hidden))
check("and does not hide billing", "plans" not in hidden,
      "a page drawn shut that actually opens is worse than either")

print("\nanswering the question opens it")
silent_u.dob = dt.date(1995, 6, 1)
db.commit()
check("the job board opens once a date is given",
      silent.get("/api/jobs?limit=1").status_code == 200)
check("and nothing is hidden any more",
      not (silent.get("/api/auth/me").json().get("hidden_pages") or []))

print(f"\nPASSED {PASS}   FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
