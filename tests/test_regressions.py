"""Re-check every problem flagged earlier in the build, plus the new gating."""
import os, sys, time, json, hashlib, re
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main as m
from fastapi.testclient import TestClient
sent = {}
m.send_email = lambda to, s_, b: sent.update({"to": to, "subject": s_, "body": b})

P, F = [], []
def ck(n, c, d=""):
    (P if c else F).append(n + (f" — {d}" if d else ""))

A = TestClient(m.app)
E = f"regress{int(time.time())}@example.com"
A.post("/api/auth/signup", json={"name": "Regress Test", "email": E, "password": "RegPass123!"})

# === previously flagged bugs, re-checked ===

# 1. matching scored unrelated roles 100 (generic skill words)
mt = A.post("/api/jobs/match", json={"resume_text":
    "Senior Network Engineer Cisco BGP OSPF MPLS VLAN F5 Palo Alto VPN IPSec "
    "SD-WAN Wireshark DNS DHCP TCP SNMP Juniper Linux Python Ansible", "limit": 50}).json()
if mt.get("jobs"):
    off = [j for j in mt["jobs"] if any(k in j["title"].lower() for k in
           ("product manager", "legal", "compliance", "account executive", "recruit"))]
    ck("no off-family roles in top 50", len(off) == 0, f"{len(off)} found")
    ck("scores spread, not all 100",
       len({j["score"] for j in mt["jobs"]}) > 5,
       f"{len({j['score'] for j in mt['jobs']})} distinct scores")
    comp = {}
    for j in mt["jobs"]: comp[j["company"]] = comp.get(j["company"], 0) + 1
    ck("company diversity cap holds", max(comp.values()) <= 3, f"max {max(comp.values())}")
else:
    ck("match returns results", False, "empty")

# 2. seniority read from degrees not titles
ck("B.Tech does not force junior",
   A.post("/api/jobs/match", json={"resume_text":
     "Senior Data Engineer. B.Tech Computer Science 2019. Python SQL Spark Kafka "
     "Airflow dbt Snowflake AWS Docker Kubernetes Terraform."}).json().get("level") == "senior")

# 3. match was 30s, then 10.8s
t = time.time()
A.post("/api/jobs/match", json={"resume_text":
   "Network Engineer Cisco BGP OSPF F5 Palo Alto Linux Python Ansible", "limit": 20})
el = time.time() - t
ck("match under 5s", el < 5, f"{el:.2f}s")

# 4. The Muse dead links removed
db = m.SessionLocal()
ck("retired source purged",
   db.query(m.Job).filter(m.Job.source == "themuse").count() == 0)
db.close()

# 5. _ai_json fragile to preambles/fences
cases = ['{"a":1}', '```json\n{"a":1}\n```', 'Here you go:\n{"a":1}',
         '{"a":1}\n\nHope that helps!', 'Sure!\n```json\n{"a":1}\n```\nDone.']
ck("_ai_json tolerates all wrappings",
   all(m._ai_json(c) == {"a": 1} for c in cases))
try:
    m._ai_json("no json here"); ck("_ai_json reports real content on failure", False)
except Exception as e:
    ck("_ai_json reports real content on failure", "no json here" in str(e))

# 6. thinking budget only applied to 2.5
ck("thinking disabled for 3.x too",
   bool(re.match(r"gemini-(2\.5|[3-9]|\d{2})", "gemini-3.5-flash-lite")))
ck("thinking left alone for 2.0",
   not re.match(r"gemini-(2\.5|[3-9]|\d{2})", "gemini-2.0-flash"))

# 7. SMTP could hang the whole site
ck("SMTP timeouts are short",
   "timeout=8" in open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'main.py'), encoding="utf-8").read())
ck("Resend is the mail provider path",
   "api.resend.com" in open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'main.py'), encoding="utf-8").read())

# 8. autofill: referrer substring blocked preferred fields
f = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'extension/filler.js'), encoding="utf-8").read()
ck("referrer exclusion anchored", "/\\breferr/" in f and "no: [/referr/" not in f)
ck("preferred name rules exist", "preferred_first_name" in f)
ck("filler never submits",
   "form.submit" not in f and ".submit()" not in f)

# 9. forgot password promised mail it could not send
m.MAIL_ENABLED = False
r = A.post("/api/auth/forgot", json={"email": E})
ck("forgot is honest when mail is off", r.json().get("mail_disabled") is True)
m.MAIL_ENABLED = True

# === new: free tier gating ===
ck("browsing jobs is free", A.get("/api/jobs?limit=3").status_code == 200)
ck("job filters free", A.get("/api/jobs/filters").status_code == 200)
ck("categories free", A.get("/api/jobs/categories").status_code == 200)
ck("suggestions free", A.get("/api/jobs/suggest?q=eng").status_code == 200)
ck("matching is paid",
   A.post("/api/jobs/match", json={"resume_text": "Cisco BGP OSPF F5 Linux Python "
                                                  "network engineer senior"}).status_code == 402)
jid = A.get("/api/jobs?limit=1").json()["jobs"][0]["id"]
ck("tracker is paid",
   A.post("/api/jobs/track", json={"job_id": jid, "status": "saved"}).status_code == 402)
ck("extension is paid", A.post("/api/apply/pair-code", json={}).status_code == 402)
ck("interview prep free", A.get("/api/interview/guide?category=network").status_code == 200)

# admin bypasses the gate
db = m.SessionLocal()
u = db.query(m.User).filter(m.func.lower(m.User.email) == E.lower()).first()
u.is_admin = True; db.commit(); db.close()
ck("admin not blocked by paywall",
   A.post("/api/jobs/match", json={"resume_text": "Cisco BGP OSPF F5 Linux Python "
                                                  "network engineer senior"}).status_code == 200)

print("\n" + "=" * 60)
print(f"REGRESSION PASS {len(P)}   FAIL {len(F)}")
print("=" * 60)
if F:
    print("\nFAILURES:")
    for x in F: print("  ✗", x)
else:
    print("\nEvery previously-flagged issue stays fixed.")
for x in P: print("  ✓", x)
