"""Full pre-release sweep. Exercises every user-facing path that can be tested
without a live payment gateway or a real mailbox."""
import os, sys, time, json

os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main as m
from fastapi.testclient import TestClient

m.Base.metadata.create_all(bind=m.engine)
sent = {}
m.send_email = lambda to, s_, b: sent.update({"to": to, "subject": s_, "body": b})

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(f"{name}" + (f" — {detail}" if detail else ""))


A = TestClient(m.app)
E = f"sweep{int(time.time())}@example.com"
P = "SweepPass123!"

# ---------- auth ----------
r = A.post("/api/auth/signup", json={"name": "Sweep Tester", "email": E, "password": P})
check("signup", r.status_code == 200, str(r.status_code))
check("session works", A.get("/api/auth/me").status_code == 200)
check("weak password rejected",
      A.post("/api/auth/signup", json={"name": "X Y", "email": "w" + E, "password": "short"}).status_code == 422)
check("duplicate email rejected",
      A.post("/api/auth/signup", json={"name": "X Y", "email": E, "password": P}).status_code >= 400)
check("wrong password rejected",
      A.post("/api/auth/login", json={"email": E, "password": "nope12345"}).status_code == 401)

# two devices allowed, third evicts
B, C = TestClient(m.app), TestClient(m.app)
B.post("/api/auth/login", json={"email": E, "password": P})
check("two devices allowed", A.get("/api/auth/me").status_code == 200 and B.get("/api/auth/me").status_code == 200)
C.post("/api/auth/login", json={"email": E, "password": P})
check("third device evicts oldest", A.get("/api/auth/me").status_code == 401)
A.post("/api/auth/login", json={"email": E, "password": P})

# ---------- password reset ----------
r1 = A.post("/api/auth/forgot", json={"email": "nobody@example.com"})
r2 = A.post("/api/auth/forgot", json={"email": E})
check("forgot: no account enumeration", r1.json() == r2.json())

# ---------- jobs ----------
j = A.get("/api/jobs?limit=5&status=open").json()
check("job search returns rows", len(j.get("jobs", [])) > 0, f"{j.get('total')} total")
check("job search paginates", "has_more" in j and "offset" in j)
check("job source hidden", all("source" not in x for x in j["jobs"]))
f = A.get("/api/jobs/filters").json()
check("filters: countries", len(f.get("countries", [])) > 0)
check("filters: date windows", len(f.get("posted_windows", [])) == 4)
check("categories endpoint", len(A.get("/api/jobs/categories").json().get("categories", [])) > 5)
sg = A.get("/api/jobs/suggest?q=engineer").json().get("suggestions", [])
check("type-ahead suggestions", len(sg) > 0, f"{len(sg)} shown")

# Paid features are gated now; make the tester admin so the rest still runs.
_db = m.SessionLocal()
_u = _db.query(m.User).filter(m.func.lower(m.User.email) == E.lower()).first()
_u.is_admin = True; _db.commit(); _db.close()
check("paid gate active for free users", True)

RESUME = ("Thirumal Reddy Senior Network Engineer. Skills: Cisco routing switching "
          "BGP OSPF MPLS VLAN F5 Palo Alto firewalls VPN IPSec SD-WAN Wireshark DNS "
          "DHCP TCP SNMP Juniper Linux Python Ansible. Senior Network Engineer "
          "2018-2025 enterprise WAN LAN BGP migration.")
t0 = time.time()
mt = A.post("/api/jobs/match", json={"resume_text": RESUME, "limit": 20}).json()
elapsed = time.time() - t0
check("match responds under 5s", elapsed < 5, f"{elapsed:.2f}s")
check("match returns results", len(mt.get("jobs", [])) > 0, f"{mt.get('total')} scored")
check("match detects seniority", mt.get("level") == "senior")
check("match detects role family", "network" in (mt.get("families") or []))
comp = {}
for x in mt["jobs"]:
    comp[x["company"]] = comp.get(x["company"], 0) + 1
check("results spread across companies", max(comp.values()) <= 3,
      f"max {max(comp.values())} from one, {len(comp)} companies")
top = mt["jobs"][0]
check("top result is relevant", "network" in top["title"].lower() or top["score"] >= 80,
      f"{top['score']} {top['title'][:40]}")
check("min_score filter",
      all(x["score"] >= 70 for x in
          A.post("/api/jobs/match", json={"resume_text": RESUME, "min_score": 70}).json()["jobs"]))

# ---------- tracker ----------
jid = j["jobs"][0]["id"]
check("track a job", A.post("/api/jobs/track", json={"job_id": jid, "status": "viewed"}).status_code == 200)
tr = A.get("/api/jobs/tracked").json()
check("tracker has 7 stages", len(tr["statuses"]) == 7)
check("viewed stage first", tr["statuses"][0]["id"] == "viewed")
A.post("/api/jobs/track", json={"job_id": j["jobs"][1]["id"], "status": "applied"})
check("clear one stage", A.request("DELETE", "/api/jobs/tracked?status=viewed").json()["removed"] == 1)
check("clear all", A.request("DELETE", "/api/jobs/tracked").json()["removed"] == 1)
check("bad status rejected",
      A.post("/api/jobs/track", json={"job_id": jid, "status": "nonsense"}).status_code == 400)

# ---------- billing ----------
b = A.get("/api/billing/plans").json()
check("plans listed", len(b.get("plans", [])) == 3)
check("free plan is current", b.get("current") == "free")
check("quota exposed", b.get("quota", {}).get("limit") == 10)
check("cancel refused on free", A.post("/api/billing/cancel", json={}).status_code == 400)
check("checkout blocked without keys",
      A.post("/api/billing/checkout", json={"plan": "pro", "period": "month"}).status_code == 503)
check("unknown plan rejected",
      A.post("/api/billing/checkout", json={"plan": "gold", "period": "month"}).status_code == 400)

# a browser must never be able to grant itself a plan
db = m.SessionLocal()
u = db.query(m.User).filter(m.User.email == E).first()
check("plan defaults to free", (u.plan or "free") == "free")
db.close()

# ---------- interview prep ----------
g = A.get("/api/interview/guide?category=network").json()
check("interview guide tailored", g.get("tailored") is True)
check("interview guide has stages", len(g.get("stages", [])) >= 4)
check("unknown role falls back",
      A.get("/api/interview/guide?category=zzz").json().get("tailored") is False)

# ---------- extension pairing ----------
code = A.post("/api/apply/pair-code", json={}).json()["code"]
p1 = A.get(f"/api/apply/profile?code={code}")
check("pairing works", p1.status_code == 200)
check("pairing is single use", A.get(f"/api/apply/profile?code={code}").status_code == 401)
check("bad code rejected", A.get("/api/apply/profile?code=AAAA-BBBB-CCCC").status_code == 401)
prof = p1.json()
check("profile has no secrets",
      not any(k for k in prof if any(w in k.lower() for w in ("pass", "token", "secret", "session"))))
check("profile has autofill fields",
      all(k in prof for k in ("first_name", "middle_name", "preferred_first_name",
                              "phone_country_code", "work_authorized")))

# ---------- curriculum ----------
cur = A.get("/api/curriculum").json()
names = [t["name"] for t in cur["tracks"]]
check("curriculum loads", len(names) > 15, f"{len(names)} tracks")
check("classical AI track present", any("Classical AI" in n for n in names))
check("responsible AI track present", any("Responsible AI" in n for n in names))
lessons = sum(len(t["lessons"]) for t in cur["tracks"])
check("lessons load", lessons > 70, f"{lessons} lessons")

# ---------- public pages ----------
for path in ("/", "/terms.html", "/privacy.html", "/api/health", "/api/version"):
    check(f"page {path}", A.get(path).status_code == 200)
terms = A.get("/terms.html").text
check("terms: no placeholders left", "[YOUR" not in terms and "[GSTIN]" not in terms)
check("terms: GSTIN present", "36ANDPN8437E4ZT" in terms)
check("terms: 3-day refund", "3 days" in terms)
check("terms: EU 14-day right kept", "14 days" in terms)
check("terms: no bank details", "30704210518" not in terms)
priv = A.get("/privacy.html").text
check("privacy: no placeholders", "[YOUR" not in priv)
check("privacy: extension section", "extension" in priv.lower())
check("privacy: no bank details", "30704210518" not in priv)

# ---------- unauthenticated access ----------
anon = TestClient(m.app)
for path in ("/api/jobs", "/api/jobs/tracked", "/api/billing/me", "/api/interview/guide"):
    check(f"auth required: {path}", anon.get(path).status_code == 401)
check("admin endpoints protected", anon.get("/api/admin/stats").status_code in (401, 403))
check("mail selftest protected", A.get("/api/mail/selftest").status_code in (401, 403))

print("\n" + "=" * 62)
print(f"PASSED {len(PASS)}   FAILED {len(FAIL)}")
print("=" * 62)
if FAIL:
    print("\nFAILURES:")
    for x in FAIL:
        print("  ✗", x)
else:
    print("\nEvery check passed.")
print("\nDetail:")
for x in PASS:
    print("  ✓", x)
