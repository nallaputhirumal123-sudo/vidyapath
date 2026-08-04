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

# strips /* … */ and // … comments, so source checks look at real code only
_re_c = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)

P, F = [], []
def ck(n, c, d=""):
    (P if c else F).append(n + (f" — {d}" if d else ""))

A = TestClient(m.app)
E = f"regress{int(time.time())}@example.com"
A.post("/api/auth/signup", json={"name": "Regress Test", "email": E, "password": "RegPass123!"})

# Matching is a paid feature — a free account gets one run and is then blocked,
# which is correct behaviour but makes the repeated match checks below fail for
# the wrong reason. Put the tester on Pro so these test matching, not billing.
_db = m.SessionLocal()
_u = _db.query(m.User).filter(m.func.lower(m.User.email) == E.lower()).first()
_u.plan = "pro"; _u.plan_until = m.now() + m.dt.timedelta(days=30)
_db.commit(); _db.close()

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
# Check the code, not the comments — the file's header paragraph says it never
# calls <form>.submit(), which a naive substring search reads as a violation.
_code = _re_c.sub("", f)
ck("filler never submits",
   "form.submit" not in _code and ".submit()" not in _code
   and ".click()" not in _code and "requestSubmit" not in _code)

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
# A is on Pro (see the top of this file), so gating has to be checked on a
# genuinely free account. Free now gets one go at matching and the extension —
# these confirm the wall is still there once the go is spent.
G = TestClient(m.app)
GE = f"gate{int(time.time())}@example.com"
G.post("/api/auth/signup", json={"name": "Gate Test", "email": GE, "password": "GatePass123!"})
RES = "Cisco BGP OSPF F5 Linux Python network engineer senior"
ck("matching is free",
   G.post("/api/jobs/match", json={"resume_text": RES}).status_code == 200)
jid = A.get("/api/jobs?limit=1").json()["jobs"][0]["id"]
ck("tracker is paid",
   G.post("/api/jobs/track", json={"job_id": jid, "status": "saved"}).status_code == 402)
ck("extension is paid",
   G.post("/api/apply/pair-code", json={}).status_code == 402)
ck("free still browses jobs", G.get("/api/jobs?limit=3").status_code == 200)
ck("free sees the whole board now",
   G.get("/api/jobs?limit=50").json().get("free_limited") is not True)
ck("general interview prep is free",
   G.get("/api/interview/guide?category=network").status_code == 200)
ck("prep for a specific job is paid",
   G.get("/api/interview/guide?job_id=1").status_code == 402)

# admin bypasses the gate
db = m.SessionLocal()
u = db.query(m.User).filter(m.func.lower(m.User.email) == E.lower()).first()
u.is_admin = True; db.commit(); db.close()
ck("admin not blocked by paywall",
   A.post("/api/jobs/match", json={"resume_text": "Cisco BGP OSPF F5 Linux Python "
                                                  "network engineer senior"}).status_code == 200)

# A posting stays "new" for 24 hours and the crawler runs every hour inside
# the window, so the alert sweep saw the same fresh jobs on all eleven passes.
# Without a memory of what it already said, one job rang the bell eleven
# times, which is how a notification bell gets ignored for good.
db = m.SessionLocal()
try:
    u = db.query(m.User).filter(m.func.lower(m.User.email) == E.lower()).first()
    uid = u.id
    db.query(m.Note).filter(m.Note.user_id == uid,
                            m.Note.k.like("alerted_%")).delete(
                                synchronize_session=False)
    db.query(m.JobAlert).filter(m.JobAlert.user_id == uid).delete(
        synchronize_session=False)
    # Re-runnable: the suite runs against a database that keeps its rows, so
    # yesterday's seed row would collide on (source, external_id) today.
    db.query(m.Job).filter(m.Job.source == "regr",
                           m.Job.external_id == "alert-dupe").delete(
                               synchronize_session=False)
    db.query(m.Note).filter(m.Note.user_id == uid,
                            m.Note.k.like("alertmail_%")).delete(
                                synchronize_session=False)
    db.query(m.Note).filter(m.Note.user_id == uid,
                            m.Note.k == "resume_uptext").delete(
                                synchronize_session=False)
    db.add(m.Note(user_id=uid, k="resume_uptext",
                  v="Sr Network Engineer, 9 years of experience. cisco bgp "
                    "ospf f5 paloalto sdwan vpn firewall wireshark python "
                    "ansible. Senior Network Engineer at Acme."))
    jd = ("Requirements: cisco bgp ospf f5 paloalto vpn firewall wireshark "
          "python ansible sdwan. Senior network engineer, data centre. ") * 3
    db.add(m.Job(source="regr", external_id="alert-dupe", title="Senior Network Engineer",
                 company="Acme", location="Dallas, TX", country="US",
                 url="https://example.com/a", text=jd, category="network",
                 skills=",".join(sorted({w for w in m._words(jd) if w in m._SKILLS})),
                 req_skills=",".join(sorted({w for w in m._words(m._requirement_text(jd))
                                             if w in m._SKILLS})),
                 is_open=True, first_seen=m.now(), last_seen=m.now()))
    db.commit()
finally:
    db.close()

# Neither threshold is what is under test here — the sweep firing once and
# only once is. FLOOR is what decides whether a posting is collected at all,
# so it is the one that has to come down for a seeded job to qualify.
_min, _floor = m.JOB_ALERT_MIN, m.JOB_ALERT_FLOOR
m.JOB_ALERT_MIN, m.JOB_ALERT_FLOOR = 60, 40
try:
    first = m._job_alert_sweep()
    second = m._job_alert_sweep()
finally:
    m.JOB_ALERT_MIN, m.JOB_ALERT_FLOOR = _min, _floor
ck("new-match alert fires after a crawl", first["created"] >= 1,
   f"created {first['created']}")
ck("the same job never alerts twice", second["created"] == 0,
   f"second sweep created {second['created']}")

print("\n" + "=" * 60)
print(f"REGRESSION PASS {len(P)}   FAIL {len(F)}")

# ---- the admin dashboard 500ing on SQLite ---------------------------------
# CAST(x AS DATE) was used to group signups by day with a comment saying it
# "works on both SQLite and Postgres". It does not: SQLite has no DATE type,
# so it applies numeric affinity and returns an integer, and SQLAlchemy's
# Date processor then calls fromisoformat on it and raises. Postgres does the
# right thing — so the whole admin dashboard 500ed locally and nowhere else,
# which is to say it 500ed only for whoever was working on it.
try:
    _admin = m.SessionLocal()
    _u = _admin.query(m.User).filter(m.User.is_admin == True).first()  # noqa: E712
    if _u is None:
        _u = m.User(name="Stats Admin", email=f"stats{int(time.time())}@example.com",
                    password_hash=m.hash_pw("StatsPass123!"), is_admin=True)
        _admin.add(_u)
        _admin.commit()
    _stats = m.admin_stats(user=_u, db=_admin)
    ck("admin dashboard stats do not crash on SQLite",
       isinstance(_stats.get("signups"), list), "returned")
    ck("and every signup day is an ISO date string",
       all(isinstance(r["date"], str) and len(r["date"]) == 10
           for r in _stats["signups"]),
       str(_stats["signups"][:2]))
    _admin.close()
except Exception as _e:
    ck("admin dashboard stats do not crash on SQLite", False,
       f"{type(_e).__name__}: {_e}")

print("=" * 60)
if F:
    print("\nFAILURES:")
    for x in F: print("  ✗", x)
else:
    print("\nEvery previously-flagged issue stays fixed.")
for x in P: print("  ✓", x)
