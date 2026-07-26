"""The free tier: one resume upload, one application, then the paywall.

Checks the things that would quietly cost money or quietly break the funnel —
an allowance that never runs out, or one that runs out halfway through the
single application we promised was free.
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

# two real jobs to apply to
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


def upload():
    return A.post("/api/resume/extract",
                  files={"file": ("resume.txt", RESUME, "text/plain")})


# --- one resume upload, then blocked ---
r1 = upload()
ck("1st resume upload allowed", r1.status_code == 200, f"{r1.status_code} {r1.text[:120]}")
ck("upload reports 0 uploads left", r1.json().get("trial_left") == 0,
   str(r1.json().get("trial_left")))
r2 = upload()
ck("2nd resume upload blocked with 402", r2.status_code == 402,
   f"{r2.status_code} {r2.text[:120]}")
r3 = upload()
ck("still blocked on 3rd try", r3.status_code == 402, str(r3.status_code))

# --- a failed upload must not burn the allowance ---
E2 = f"trial2{int(time.time())}@example.com"
B = TestClient(m.app)
B.post("/api/auth/signup", json={"name": "Trial Two", "email": E2,
                                 "password": "TrialPass123!"})
bad = B.post("/api/resume/extract",
             files={"file": ("empty.txt", "x", "text/plain")})
ck("unreadable upload rejected", bad.status_code == 400, str(bad.status_code))
good = B.post("/api/resume/extract",
              files={"file": ("resume.txt", RESUME, "text/plain")})
ck("failed upload did not consume the free go", good.status_code == 200,
   f"{good.status_code} {good.text[:120]}")

# --- one application, tied to one job ---
a1 = A.post("/api/jobs/track", json={"job_id": JOB_A, "status": "applied"})
ck("1st application allowed", a1.status_code == 200, f"{a1.status_code} {a1.text[:120]}")
a2 = A.post("/api/jobs/track", json={"job_id": JOB_A, "status": "applied"})
ck("same job again still allowed (no double charge)", a2.status_code == 200,
   f"{a2.status_code} {a2.text[:120]}")
a3 = A.post("/api/jobs/track", json={"job_id": JOB_B, "status": "applied"})
ck("2nd, different job blocked with 402", a3.status_code == 402,
   f"{a3.status_code} {a3.text[:120]}")

# the apply kit is the other half of the same application — it must not be
# charged separately, or the free application dead-ends halfway
k = A.post("/api/jobs/apply-kit", json={"job_id": JOB_A, "resume_text": RESUME})
ck("apply kit open for the free application's job", k.status_code != 402,
   f"{k.status_code} {k.text[:120]}")
kb = A.post("/api/jobs/apply-kit", json={"job_id": JOB_B, "resume_text": RESUME})
ck("apply kit blocked for any other job", kb.status_code == 402,
   f"{kb.status_code} {kb.text[:120]}")

# --- saving/tracking beyond the free application stays paid ---
sv = A.post("/api/jobs/track", json={"job_id": JOB_B, "status": "saved"})
ck("saving jobs remains paid-only", sv.status_code == 402, str(sv.status_code))

# --- browsing jobs stays free, which is the whole point ---
br = A.get("/api/jobs?limit=5")
ck("browsing jobs still free", br.status_code == 200, str(br.status_code))

# --- what the UI is told ---
db = m.SessionLocal()
user = db.query(m.User).filter(m.User.email == E).first()
q = m.ai_quota(db, user)
ck("quota reports upload spent", q["trial"]["resume_upload_left"] == 0, str(q.get("trial")))
ck("quota reports application spent", q["trial"]["apply_left"] == 0, str(q.get("trial")))
ck("quota names the free application's job", q["trial"]["apply_job_id"] == JOB_A,
   str(q["trial"]["apply_job_id"]))

# --- paying lifts both limits ---
user.plan = "pro"
user.plan_until = m.now() + m.dt.timedelta(days=30)
db.commit(); db.close()
ck("pro plan active", True)
pu = A.post("/api/resume/extract",
            files={"file": ("resume.txt", RESUME, "text/plain")})
ck("pro can upload again", pu.status_code == 200, f"{pu.status_code} {pu.text[:120]}")
pa = A.post("/api/jobs/track", json={"job_id": JOB_B, "status": "applied"})
ck("pro can apply to any job", pa.status_code == 200, f"{pa.status_code} {pa.text[:120]}")

print("\n".join("PASS " + x for x in P))
print("\n".join("FAIL " + x for x in F))
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
