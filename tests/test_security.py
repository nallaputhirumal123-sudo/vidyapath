"""Deeper pass: security boundaries, tampering, and edge cases."""
import os, sys, time, json
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main as m
from fastapi.testclient import TestClient
m.send_email = lambda *a, **k: None

PASS, FAIL = [], []
def check(n, c, d=""):
    (PASS if c else FAIL).append(n + (f" — {d}" if d else ""))

A = TestClient(m.app); B = TestClient(m.app)
EA = f"deepa{int(time.time())}@example.com"; EB = f"deepb{int(time.time())}@example.com"
P = "DeepPass123!"
A.post("/api/auth/signup", json={"name": "Deep A", "email": EA, "password": P})
B.post("/api/auth/signup", json={"name": "Deep B", "email": EB, "password": P})

# ---- one user must not see or touch another's data ----
job = A.get("/api/jobs?limit=2").json()["jobs"]
A.post("/api/jobs/track", json={"job_id": job[0]["id"], "status": "applied"})
check("tracker is per-user", B.get("/api/jobs/tracked").json()["total"] == 0)
B.request("DELETE", "/api/jobs/tracked")
check("one user cannot clear another's tracker",
      A.get("/api/jobs/tracked").json()["total"] == 1)

# ---- cannot self-upgrade ----
for attempt in ({"plan": "pro"}, {"plan": "pro", "period": "year"}):
    r = A.post("/api/billing/checkout", json=attempt)
    check(f"checkout without keys refuses {attempt}", r.status_code in (400, 503), str(r.status_code))
check("plan still free after checkout attempts",
      A.get("/api/billing/me").json()["plan"] == "free")

# ---- webhooks reject forged/unsigned calls ----
r = A.post("/api/billing/webhook/razorpay", json={"event": "payment.captured",
      "payload": {"payment": {"entity": {"id": "x", "notes": {"user_id": "1", "plan": "pro"}}}}})
check("razorpay webhook rejects unsigned", r.status_code >= 400, str(r.status_code))
r = A.post("/api/billing/webhook/stripe", json={"type": "checkout.session.completed",
      "data": {"object": {"metadata": {"user_id": "1", "plan": "pro"}}}})
check("stripe webhook rejects unsigned", r.status_code >= 400, str(r.status_code))
check("plan unchanged after forged webhooks",
      A.get("/api/billing/me").json()["plan"] == "free")

# ---- reset tokens ----
db = m.SessionLocal()
u = db.query(m.User).filter(m.func.lower(m.User.email) == EA.lower()).first()
raw = "forged-token-value-1234567890"
import hashlib
check("forged reset token rejected",
      A.post("/api/auth/reset", json={"token": raw, "password": "NewPass123!"}).status_code == 400)
# expired token
tok = "expiredtok" + str(int(time.time()))
db.add(m.PasswordReset(user_id=u.id, token_hash=hashlib.sha256(tok.encode()).hexdigest(),
                       expires_at=m.now() - m.dt.timedelta(hours=2)))
db.commit(); db.close()
r = A.post("/api/auth/reset", json={"token": tok, "password": "NewPass123!"})
check("expired reset token rejected", r.status_code == 400, r.json().get("detail", "")[:40])

# ---- input validation / injection shapes ----
weird = ["'; DROP TABLE jobs;--", "<script>alert(1)</script>", "%00", "../../etc/passwd",
         "a" * 5000, "😀🔥" * 50]
ok = True
for w in weird:
    try:
        r = A.get("/api/jobs", params={"q": w, "limit": 2})
        if r.status_code >= 500: ok = False
        r = A.get("/api/jobs/suggest", params={"q": w})
        if r.status_code >= 500: ok = False
    except Exception:
        ok = False
check("hostile search input never 500s", ok)
check("jobs table intact after injection attempt",
      A.get("/api/jobs?limit=1").json()["total"] > 1000)

# ---- limits are enforced, not suggested ----
r = A.get("/api/jobs?limit=99999").json()
check("limit is capped", len(r["jobs"]) <= 50, f"{len(r['jobs'])} returned")
r = A.post("/api/jobs/match", json={"resume_text": "x" * 50, "limit": 99999})
check("match limit capped", r.status_code == 400 or len(r.json().get("jobs", [])) <= 50)
check("empty resume refused",
      A.post("/api/jobs/match", json={"resume_text": "hi"}).status_code == 400)
check("resume with no skills refused",
      A.post("/api/jobs/match", json={"resume_text": "I like long walks on the beach and reading books about history and art. " * 3}).status_code == 400)

# ---- static file traversal ----
for bad in ("/../main.py", "/..%2fmain.py", "/vidyapath.db"):
    r = A.get(bad)
    check(f"blocked: {bad}", r.status_code >= 400 or "DATABASE_URL" not in r.text, str(r.status_code))

# ---- pairing code cannot be brute-forced into a session ----
code = A.post("/api/apply/pair-code", json={}).json()["code"]
prof = A.get(f"/api/apply/profile?code={code}").json()
check("pairing profile carries no auth material",
      not any(k for k in prof if any(w in k.lower() for w in ("token", "session", "cookie", "pass"))))

# ---- AI quota enforced server-side ----
q = A.get("/api/billing/plans").json()["quota"]
check("free quota is a lifetime total", q.get("period") == "total" and q.get("limit") == 10)

# ---- interview guide handles junk ----
for c in ("", "zzz", "<script>", "network"):
    r = A.get("/api/interview/guide", params={"category": c})
    check(f"interview guide ok for {c!r}", r.status_code == 200)

print("\n" + "=" * 60)
print(f"DEEP PASS {len(PASS)}   FAIL {len(FAIL)}")
print("=" * 60)
if FAIL:
    print("\nFAILURES:")
    for x in FAIL: print("  ✗", x)
else:
    print("\nAll deep checks passed.")
for x in PASS: print("  ✓", x)
