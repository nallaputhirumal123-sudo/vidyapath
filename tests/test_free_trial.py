"""What the free plan actually includes.

Free is the training courses plus a delayed, capped view of the job board.
Everything that acts on a resume — matching, the tracker, apply kits, the
autofill extension — is paid, with no trial.
"""
import os, sys, time
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main as m
from fastapi.testclient import TestClient

P, F = [], []
def ck(n, c, d=""):
    (P if c else F).append(n + (f" — {d}" if d else ""))

A = TestClient(m.app)
E = f"trial{int(time.time())}@example.com"
r = A.post("/api/auth/signup", json={"name": "Trial Test", "email": E,
                                     "password": "TrialPass123!"})
assert r.status_code < 400, r.text

db = m.SessionLocal()
user = db.query(m.User).filter(m.User.email == E).first()
ck("new signup is on the free plan", m.plan_of(user) == "free", m.plan_of(user))

jobs = []
for i in (1, 2):
    j = m.Job(title=f"Backend Engineer {i}", company=f"Co{i}", location="Remote",
              url=f"https://example.com/j{i}", is_open=True,
              text="Python FastAPI PostgreSQL Docker. Build and run APIs.",
              source="test", external_id=f"trial-test-{int(time.time())}-{i}")
    db.add(j); jobs.append(j)
db.commit()
JOB_A, JOB_B = jobs[0].id, jobs[1].id
db.close()

RESUME = ("Jane Doe\njane@example.com\nBackend Engineer\n"
          "Experience: built Python FastAPI services on PostgreSQL and Docker, "
          "reduced latency 40%, led a team of 4 engineers.\n"
          "Skills: Python, FastAPI, SQL, Docker, AWS\n")

# ---------- free: the paid tools are all shut ----------
ck("resume upload is paid",
   A.post("/api/resume/extract",
          files={"file": ("resume.txt", RESUME, "text/plain")}).status_code == 402)
ck("resume matching is paid",
   A.post("/api/jobs/match", json={"resume_text": RESUME}).status_code == 402)
ck("saving a job is paid",
   A.post("/api/jobs/track", json={"job_id": JOB_A, "status": "saved"}).status_code == 402)
ck("applying is paid",
   A.post("/api/jobs/track", json={"job_id": JOB_A, "status": "applied"}).status_code == 402)
ck("apply kit is paid",
   A.post("/api/jobs/apply-kit", json={"job_id": JOB_A,
                                       "resume_text": RESUME}).status_code == 402)
ck("extension pairing is paid",
   A.post("/api/apply/pair-code", json={}).status_code == 402)

# ---------- free: courses stay open ----------
ck("training courses are free", A.get("/api/curriculum").status_code == 200)
ck("progress tracking is free", A.get("/api/progress").status_code == 200)
ck("interview prep is free",
   A.get("/api/interview/guide?category=software").status_code == 200)

# ---------- free: a delayed, capped job board ----------
jb = A.get("/api/jobs?limit=50").json()
ck("free can still browse jobs", len(jb["jobs"]) > 0, str(len(jb["jobs"])))
ck("free is flagged as limited", jb.get("free_limited") is True)
ck("free is capped", jb["total"] <= m.FREE_JOB_CAP, str(jb["total"]))
ck("free reports the delay", jb.get("free_delay_days") == m.FREE_JOB_DELAY_DAYS,
   str(jb.get("free_delay_days")))

# nothing fresher than the cutoff may appear
cutoff = m.now() - m.dt.timedelta(days=m.FREE_JOB_DELAY_DAYS)
db = m.SessionLocal()
fresh_leaked = []
for j in jb["jobs"]:
    row = db.get(m.Job, j["id"])
    when = row.posted_at or row.first_seen
    if when and m._aware(when) > cutoff:
        fresh_leaked.append(j["id"])
db.close()
ck("no fresh postings leak into the free view", not fresh_leaked,
   f"{len(fresh_leaked)} leaked")

# the cap must hold when paging, not just on the first page
deep = A.get("/api/jobs?limit=50&offset=5000").json()
ck("free cannot page past the cap", deep["offset"] < m.FREE_JOB_CAP,
   f"offset {deep['offset']}")
ck("free has_more is honest once capped", deep.get("has_more") is False,
   str(deep.get("has_more")))

# ---------- paying opens everything ----------
db = m.SessionLocal()
user = db.query(m.User).filter(m.User.email == E).first()
user.plan = "pro"
user.plan_expires = m.now() + m.dt.timedelta(days=30)
db.commit(); db.close()

pj = A.get("/api/jobs?limit=50").json()
ck("pro sees the whole board", pj["total"] > m.FREE_JOB_CAP, str(pj["total"]))
ck("pro is not flagged limited", not pj.get("free_limited"))
ck("pro can upload a resume",
   A.post("/api/resume/extract",
          files={"file": ("resume.txt", RESUME, "text/plain")}).status_code == 200)
mt = A.post("/api/jobs/match", json={"resume_text": RESUME, "limit": 10})
ck("pro can match", mt.status_code == 200, f"{mt.status_code} {mt.text[:120]}")
ck("pro can match repeatedly",
   A.post("/api/jobs/match", json={"resume_text": RESUME, "limit": 10}).status_code == 200)
ck("pro can save jobs",
   A.post("/api/jobs/track", json={"job_id": JOB_A, "status": "saved"}).status_code == 200)
ck("pro can apply to several jobs",
   A.post("/api/jobs/track", json={"job_id": JOB_A, "status": "applied"}).status_code == 200
   and A.post("/api/jobs/track", json={"job_id": JOB_B, "status": "applied"}).status_code == 200)
code = A.post("/api/apply/pair-code", json={})
ck("pro can pair the extension", code.status_code == 200, str(code.status_code))
ck("pro autofill works",
   A.get(f"/api/apply/profile?code={code.json()['code']}").status_code == 200)

print("\n".join("PASS " + x for x in P))
print("\n".join("FAIL " + x for x in F))
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
