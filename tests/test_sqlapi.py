"""The SQL board over HTTP: gating, persistence and one user's work staying theirs."""
import os
import sys
import time

os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"   # local test database; refused on a deployment
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main as m                                                    # noqa: E402
from fastapi.testclient import TestClient                           # noqa: E402

m.send_email = lambda *a, **k: None

ok = fail = 0


def check(n, c, d=""):
    global ok, fail
    if c:
        ok += 1
        print(f"  PASS  {n}" + (f"  ({d})" if d else ""))
    else:
        fail += 1
        print(f"  FAIL  {n}" + (f"  ({d})" if d else ""))


STAMP = int(time.time())
A = TestClient(m.app)
B = TestClient(m.app)
EA, EB = f"sqla{STAMP}@example.com", f"sqlb{STAMP}@example.com"
P = "SqlPass123!"
A.post("/api/auth/signup", json={"name": "Sql A", "email": EA, "password": P})
B.post("/api/auth/signup", json={"name": "Sql B", "email": EB, "password": P})

print("THE BOARD OPENS")
r = A.get("/api/sql/board")
check("the board loads", r.status_code == 200, str(r.status_code))
d = r.json()
check("the schema comes with it", len(d["schema"]) == 4)
check("it starts on the first exercise", d["next"]["id"] == "e1", d["next"]["id"])
check("nothing is done yet", d["done"] == 0)
check("the model answer is not in the payload", "ref" not in d["exercises"][0])

print("\nRUNNING IS FREE")
# Both accounts are on the free plan and neither has paid for anything.
check("a free account can run a query",
      A.post("/api/sql/run", json={"sql": "SELECT * FROM customers"}).json()["ok"])
check("a free account can read a plan",
      A.post("/api/sql/plan", json={"sql": "SELECT * FROM orders"}).json()["ok"])
check("a free account can be marked",
      A.post("/api/sql/check",
             json={"exercise": "e1",
                   "sql": "SELECT name, city FROM customers WHERE city='Bengaluru'"}
             ).json()["correct"])
check("a free account gets the join picture",
      A.get("/api/sql/join/e7").json()["ok"])
check("an exercise without a picture says so",
      A.get("/api/sql/join/e1").status_code == 404)

print("\nSIGNED OUT, NOTHING RUNS")
G = TestClient(m.app)
for path, kw in (("/api/sql/board", {}),
                 ("/api/sql/run", {"json": {"sql": "SELECT 1"}}),
                 ("/api/sql/check", {"json": {"exercise": "e1", "sql": "SELECT 1"}})):
    fn = G.get if not kw else G.post
    check(f"anonymous is refused at {path}", fn(path, **kw).status_code == 401)

print("\nTHE ATTEMPT IS REMEMBERED")
A.post("/api/sql/check", json={"exercise": "e3", "sql": "SELECT title FROM products"})
d = A.get("/api/sql/board").json()
check("a solved exercise stays solved", d["history"]["e1"]["solved"])
check("a failed attempt is counted", d["history"]["e3"]["tries"] == 1
      and not d["history"]["e3"]["solved"])
check("the board offers the failed one again", d["next"]["id"] == "e3",
      d["next"]["id"])
check("the count went up", d["done"] == 1)

# Getting it right later must clear it, or the path never moves on.
A.post("/api/sql/check", json={"exercise": "e3",
       "sql": "SELECT title, price FROM products ORDER BY price DESC LIMIT 3"})
d = A.get("/api/sql/board").json()
check("solving it on the second go is recorded", d["history"]["e3"]["solved"])
check("tries keeps counting", d["history"]["e3"]["tries"] == 2)
check("and the path moves on", d["next"]["id"] not in ("e1", "e3"),
      d["next"]["id"])

print("\nONE STUDENT'S WORK IS THEIRS")
db = B.get("/api/sql/board").json()
check("the second account sees none of the first's progress", db["done"] == 0)
check("and starts at the beginning", db["next"]["id"] == "e1")

print("\nTHE SANDBOX HOLDS OVER HTTP")
for sql in ("DROP TABLE customers", "DELETE FROM users",
            "ATTACH DATABASE 'vidyapath.db' AS x",
            "SELECT * FROM users", "SELECT * FROM sqlite_master"):
    r = A.post("/api/sql/run", json={"sql": sql}).json()
    check(f"refused over HTTP: {sql[:34]}", not r["ok"], r.get("error", "")[:34])

# The real product database has to be untouched by all of that.
_d = m.SessionLocal()
check("the real users table still exists",
      _d.query(m.User).filter(m.func.lower(m.User.email) == EA.lower()).first()
      is not None)
_d.close()

check("an unknown exercise is a 404",
      A.post("/api/sql/check", json={"exercise": "nope", "sql": "SELECT 1"}
             ).status_code == 404)

print("\nONLY THE WRITTEN EXPLANATION IS PAID")
r = A.post("/api/sql/explain", json={"exercise": "e1", "sql": "SELECT name FROM customers"})
# No key is configured in tests, so this is 503 — the point of the check is
# that it is not 200: the paid path must never be free by accident.
check("explaining is not simply open", r.status_code != 200, str(r.status_code))
check("the free allowance is advertised",
      A.get("/api/sql/board").json()["explain_left"] == 3,
      str(A.get("/api/sql/board").json()["explain_left"]))

print("\nTHE THROTTLE IS THERE")
m._SQL_HITS.pop(
    m.SessionLocal().query(m.User).filter(
        m.func.lower(m.User.email) == EA.lower()).first().id, None)
codes = {A.post("/api/sql/run", json={"sql": "SELECT 1 FROM customers"}).status_code
         for _ in range(m._SQL_PER_MIN + 6)}
check("hammering it eventually returns 429", 429 in codes, str(sorted(codes)))

print(f"\nPASSED {ok}   FAILED {fail}")
sys.exit(1 if fail else 0)
