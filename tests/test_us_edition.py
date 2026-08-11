"""learncraxle.com — the US edition, and a teacher who could hold one device.

Two things that arrived together.

## The edition

A US school gets its own deployment with its own database, and that is not a
preference. A US pupil must not have a row in a database built around resumes
and employers; an Indian class code must never open a US classroom; and "we do
not hold your children's data" has to be true of the server, not only of the
screens. There is a comment in main.py arguing for one deployment with a list
of school hostnames instead — right for two front doors on one product in one
country, and it stops being right at a border.

So EDITION=us, which:

  * implies CRAXLEARN_ONLY, rather than being a second way to say it. One
    switch that can be forgotten beats two that can disagree.
  * turns the job crawler off at the source. Every route that reads a job is
    already unreachable, so leaving it running would fetch postings nobody can
    see and write them into a US school's database — the one thing this
    edition promises it does not do.
  * serves the SITE at the root and the board at /board. Teachers plan on the
    site and pupils hand work in on it; a board at the root would mean every
    teacher who typed learncraxle.com landed on a code prompt.
  * tells the signed-out page which edition it is. /api/me carries that for
    somebody signed in, and the landing page — the first thing a US parent
    ever sees — is precisely the screen nobody has signed in on.

## One device

Reported as: a teacher enters the address and password the office gave her
and the screen says she is not signed in.

MAX_DEVICES was 1, and every word of the reasoning behind it is about a class
account — thirty children with one code between them. A teacher is the
opposite case. She plans at her desk, checks a register on her phone and signs
in on the computer wired to the board: three devices in one morning, all hers,
and at one device each silently ended the last. What she saw was a correct
message about a rule she had not broken, which reads as a broken password.

The cap is per role now. Pupils are unchanged — that rule exists for a reason
and this test holds it in place. Staff get enough devices to do the job.
"""
import io
import os
import sys
import time
import datetime as dt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"

import main                                        # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = io.open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
main.Base.metadata.create_all(bind=main.engine)
main._migrate_columns()
main.send_email = lambda *a, **k: None
P, F = [], []


def ck(n, c, d=""):
    print(("PASS " if c else "FAIL ") + n + (f" — {d}" if d else ""),
          flush=True)
    (P if c else F).append(n)


c = TestClient(main.app)

print("\nthe classroom door has a name you can read off a wall")
r = c.get("/board")
ck("/board is served", r.status_code == 200, str(r.status_code))
ck("and it is the board", "craxlearn" in r.text.lower()
   or "Craxlearn" in r.text, r.text[:80])
ck("on every edition, so one set of instructions is true everywhere",
   '@app.get("/board")' in MAIN
   and "return FileResponse(BASE_DIR / \"craxlearn.html\")" in MAIN)
ck("and the old address still works",
   c.get("/craxlearn").status_code == 200)

print("\nthe edition is one switch, not two that can disagree")
ck("EDITION names it", 'EDITION = env("EDITION", "in")' in MAIN)
ck("us and usa both count", 'US_EDITION = EDITION in ("us", "usa")' in MAIN)
ck("and it implies craxlearn-only",
   'CRAXLEARN_ONLY = US_EDITION or env("CRAXLEARN_ONLY", "0")' in MAIN,
   "one switch that can be forgotten beats two that can disagree")

print("\nno jobs, and not merely no job screens")
ck("the crawler is off at the source",
   "JOBS_ENABLED = (not US_EDITION) and env(" in MAIN,
   "every job route is already unreachable, so a crawl would write postings "
   "nobody can see into a US school's database")
ck("and the job half is closed by the middleware, not by the page",
   "def is_job_side(path)" in io.open(
       os.path.join(ROOT, "craxlearn.py"), encoding="utf-8").read())

print("\nthe site at the root, the board at /board")
ck("the US edition serves the site at the root",
   "if US_EDITION:\n        return FileResponse(BASE_DIR / \"index.html\")"
   in MAIN,
   "a board at the root means every teacher who types the address lands on "
   "a code prompt")
ck("and India is untouched by that branch",
   "if CRAXLEARN_ONLY or _is_school_host(request):" in MAIN,
   "the existing behaviour has to survive the new one being added above it")

print("\nthe signed-out page can tell which edition it is")
d = c.get("/api/auth/config").json()
ck("the config says so", "edition" in d, str(d)[:120])
ck("and whether jobs exist here", "jobs" in d, str(d)[:120])
ck("this build is the India one", d.get("edition") == "in", str(d.get("edition")))
ck("with jobs on", d.get("jobs") is True)

print("\nA TEACHER MAY HOLD MORE THAN ONE DEVICE")
u = str(int(time.time())) + str(os.getpid())
db = main.SessionLocal()
sc = main.School(name=f"Edition School {u}")
db.add(sc)
db.commit()
db.refresh(sc)
hc = ("HED" + u)[:12]
db.add(main.TeacherCode(code=hc, school=sc.name, school_id=sc.id,
                        is_head=True, active=True))
db.commit()
office = TestClient(main.app)
oem = f"ed.off{u}@example.com"
office.post("/api/auth/signup", json={"name": "Ed Office", "email": oem,
                                      "password": "EdPass1!"})
orow = db.query(main.User).filter(main.User.email == oem).first()
orow.dob = dt.date(1980, 1, 1)
db.commit()
office.post("/api/class/join", json={"code": hc})
cid = office.post("/api/teacher/class", json={"name": f"8-E {u}"}).json()["id"]
tem = f"ed.t{u}@example.com"
pw = office.post("/api/head/staff",
                 json={"name": "Ed Teacher", "email": tem,
                       "role": "teacher"}).json().get("temporary_password")
trow = db.query(main.User).filter(main.User.email == tem).first()
office.post("/api/head/assign", json={"class_id": cid, "subject": "Maths",
                                      "user_id": trow.id})

devices = [TestClient(main.app) for _ in range(4)]
for i, dev in enumerate(devices):
    dev.post("/api/auth/login", json={"email": tem, "password": pw})
    alive = [x.get("/api/teacher/classes").status_code for x in devices[:i + 1]]
    ck(f"after device {i + 1} signs in, all {i + 1} still work",
       all(s == 200 for s in alive), str(alive))
ck("her desk, her phone and the classroom computer",
   main.MAX_DEVICES_STAFF >= 3,
   "three devices in one morning is an ordinary morning")

print("\nand a pupil is still one at a time")
# The sharing rule the limit was written for. Thirty children with one code
# between them is the thing it stops, and it must keep stopping it.
kem = f"ed.kid{u}@example.com"
k1 = TestClient(main.app)
k1.post("/api/auth/signup", json={"name": "Ed Pupil", "email": kem,
                                  "password": "KidPass1!"})
krow = db.query(main.User).filter(main.User.email == kem).first()
krow.dob = dt.date(2011, 1, 1)
db.commit()
k1.post("/api/auth/login", json={"email": kem, "password": "KidPass1!"})
ck("the pupil signs in", k1.get("/api/class/mine").status_code == 200)
k2 = TestClient(main.app)
k2.post("/api/auth/login", json={"email": kem, "password": "KidPass1!"})
r = k1.get("/api/class/mine")
ck("and a second sign-in still ends the first", r.status_code == 401,
   str(r.status_code))
ck("with a message that names the real number",
   "One device at a time" in r.text, r.text[:110])
ck("the cap is decided per account, not globally",
   "def _device_cap(user, db) -> int:" in MAIN)
ck("and a lookup that fails falls to the stricter number",
   "return MAX_DEVICES\n" in MAIN,
   "never let an error open an account up; the safe direction is closed")

print("\nand the landing page stops advertising a job board")
# The first screen a US school's parent ever sees. It read "Free to browse
# every job and match your resume" on a product sold to them for teaching
# thirteen-year-olds, where the job half is not hidden but not served at all.
_IDX = io.open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
ck("the pitch can be addressed", 'id="joinPitch"' in _IDX
   and 'id="joinPitchSub"' in _IDX)
ck("and is rewritten for a school edition",
   'if(c && (c.edition === "us" || c.jobs === false)){' in _IDX)
ck("driven by the server's answer, not the hostname",
   '"/api/auth/config"' in _IDX,
   "a hostname is a header; this decides what the page claims to be")

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\nPASSED {len(P)}   FAILED {len(F)}")
sys.exit(1 if F else 0)
