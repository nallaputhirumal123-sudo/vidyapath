"""One deployment, two front doors.

learncraxle.com is the same application as craxle.com — the same database, the
same accounts, the same class codes — with only the door different. A school
never has to explain to a parent why the site their child learns on opens on a
job board.

Kept as a host list rather than a second deployment because two deployments
means two of everything that can drift: two schemas, two sets of class codes,
two places every bug has to be fixed. A code issued on one would not work on
the other, which is exactly what codes exist to prevent.

What is pinned here:

**Nothing changes when it is not configured.** An empty CRAXLEARN_HOSTS must
leave craxle.com behaving precisely as it did. This is the whole safety
argument for the change and is the first thing that would rot.

**Sessions do not cross.** The cookie is set without a domain attribute, so it
is host-only: signing in at one door is not signing in at the other. For a
board at the front of a classroom that is the behaviour you want, and it is a
property of the cookie that a careless `domain=` would silently destroy.

**The door is recognised however it is typed.** A Host header carries a port
and a configured hostname does not; somebody will type www.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"   # local test database; refused on a deployment
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"
os.environ["CRAXLEARN_HOSTS"] = "learncraxle.com, board.example.edu"

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
c = TestClient(main.app)


def body(host):
    return c.get("/", headers={"host": host}).text


# The <title> is the one string that is definitely different between the two
# documents. "Craxlearn" alone is not: index.html links to the school app and
# mentions it by name, so an earlier version of this test passed the school
# document and the job board document identically.
SCHOOL = "<title>Craxlearn — the teaching board</title>"

print("\nwhich app answers the door")
check("the school domain gets the school app",
      SCHOOL in body("learncraxle.com"))
check("a second configured domain does too",
      SCHOOL in body("board.example.edu"))
check("craxle.com is untouched",
      SCHOOL not in body("craxle.com"),
      "the job board must not become the school app")
check("an unknown host is untouched too",
      SCHOOL not in body("something-else.com"))

print("\nhowever it is typed")
check("a port on the host header is ignored",
      SCHOOL in body("learncraxle.com:8080"))
check("www is ignored", SCHOOL in body("www.learncraxle.com"))
check("case is ignored", SCHOOL in body("LearnCraxle.COM"))
check("a lookalike is not the school",
      SCHOOL not in body("notlearncraxle.com"),
      "matching on a suffix would hand the app to any domain ending in it")

print("\nthe rest of the site is the same site")
r = c.get("/craxlearn", headers={"host": "learncraxle.com"})
check("/craxlearn still serves the school app", r.status_code == 200)
r = c.get("/craxlearn", headers={"host": "craxle.com"})
check("and still does on the original domain", r.status_code == 200,
      "the existing URL must keep working")

print("\nsessions do not cross the two doors")
import inspect                                     # noqa: E402
check("the session cookie carries no domain attribute",
      "domain=" not in inspect.getsource(main.set_session).lower(),
      "a domain attribute would share one login across both hosts")

print("\nwhen it is not configured at all")
saved = main.CRAXLEARN_HOSTS
main.CRAXLEARN_HOSTS = ()
try:
    check("every host gets the job board again",
          SCHOOL not in body("learncraxle.com"),
          "an empty setting must change nothing")
finally:
    main.CRAXLEARN_HOSTS = saved

print("\nwhich address goes into a link")
# Deriving this from the Host header is a known attack: set Host to a server
# you own, ask for a password reset, and the victim is emailed a working reset
# link pointing at you. PUBLIC_BASE_URL exists to stop exactly that, so an
# entry in the allowlist must be the ONLY thing that can override it.


class FakeReq:
    def __init__(self, host):
        self.headers = {"host": host}
        self.base_url = "http://testserver/"


main.PUBLIC_BASE_URL = "https://craxle.com"
check("a configured school host is used for its own links",
      main._site_base(FakeReq("learncraxle.com")) == "https://learncraxle.com",
      main._site_base(FakeReq("learncraxle.com")))
check("an attacker's host is ignored",
      main._site_base(FakeReq("evil.example.net")) == "https://craxle.com",
      "a reset link must never point at a host somebody merely claimed")
check("a lookalike host is ignored too",
      main._site_base(FakeReq("learncraxle.com.evil.net")) == "https://craxle.com")
check("the job board keeps its own configured base",
      main._site_base(FakeReq("craxle.com")) == "https://craxle.com")
check("https is forced for a school host",
      main._site_base(FakeReq("learncraxle.com")).startswith("https://"),
      "a verification link must not be sent over plain http")

print(f"\nPASSED {PASS}   FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
