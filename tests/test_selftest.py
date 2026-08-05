"""The diagnostic must not be the thing that needs diagnosing.

/api/ai/selftest reached for `db` to inspect the board's cache rows, but `db`
was never in its signature, so FastAPI never supplied it and every call raised
NameError — a 500. The endpoint built to explain "Internal Server Error for
board" answered with an Internal Server Error of its own, which cost a full
round trip to discover.

Admin-only endpoints get no traffic, so nothing found this by accident. The
test forces the branch that touches the database: a key is set so the endpoint
does not take its early "no AI configured" return, the upstream call then
fails against a fake key, and execution carries on into the cache and quota
block — which is exactly the code that was broken.
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Must be set before main is imported: ASK_ENABLED is computed at import time,
# and without it the endpoint returns before reaching the code under test.
os.environ.setdefault("GEMINI_API_KEY", "test-key-not-real")
os.environ.setdefault("JWT_SECRET", "test-secret-for-selftest-long-enough")
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"   # local test database; refused on a deployment
os.environ["JOBS_ENABLED"] = "0"
# The session cookie is Secure in production and the test client speaks http,
# so without this the jar silently drops it and every request reads as signed
# out — which looks exactly like an auth bug and is not one.
os.environ["COOKIE_SECURE"] = "0"

from fastapi.testclient import TestClient          # noqa: E402
import main                                        # noqa: E402

PASS = FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {name}" + (f"  ({detail})" if detail else ""))
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


C = TestClient(main.app)
EMAIL = f"selftest-{uuid.uuid4().hex[:10]}@example.com"
PW = "a-long-enough-password"

r = C.post("/api/auth/signup", json={"name": "Self Test", "email": EMAIL,
                                     "password": PW})
check("signup", r.status_code == 200, str(r.status_code))

check("selftest refuses a non-admin",
      C.get("/api/ai/selftest").status_code in (401, 403),
      str(C.get("/api/ai/selftest").status_code))

db = main.SessionLocal()
u = db.query(main.User).filter(main.User.email == EMAIL).first()
u.is_admin = True
db.commit()
db.close()

# Sign in again so the session belongs to a row that is now an admin. The jar
# is emptied first: the client keeps the signup cookie otherwise and sends the
# stale one, which reads as not signed in at all.
C.cookies.clear()
lr = C.post("/api/auth/login", json={"email": EMAIL, "password": PW})
check("logged back in as admin",
      lr.status_code == 200 and lr.json().get("is_admin") is True,
      str(lr.status_code))

r = C.get("/api/ai/selftest")
check("selftest does not 500", r.status_code == 200, f"HTTP {r.status_code}")

if r.status_code == 200:
    d = r.json()
    # The block that was crashing. Its presence proves execution reached past
    # the database access rather than stopping at the AI call.
    check("it reports the endpoint's gates", "board_endpoint_gates" in d,
          str(sorted(d))[:120])
    g = d.get("board_endpoint_gates", {})
    check("the cache was actually read", "cached_board_lessons" in g,
          str(sorted(g))[:140])
    check("it says whether the caller is entitled", "entitled" in g)
    check("it names the provider order", bool(d.get("fallback_order")),
          str(d.get("fallback_order")))
    check("a dead key is reported, not raised",
          d.get("ok") is False and "smart_board_call" in d)
else:
    print("    body:", r.text[:400])

print(f"\nPASSED {PASS}   FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
