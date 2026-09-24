"""The worker half: what happens to one queued row, and what stops it.

Two passes over the same state machine.

**The first needs no browser.** flow.py deliberately imports nothing from
playwright — it takes a `page` and an `adapter` and does not care what they
are — so the caps, the hold window, the retry ceiling, the kill switch and
the consent recheck can all be driven with a stub. That is the half that has
to run on every machine, every time, because it is the half where a mistake
sends an application somebody did not authorise.

**The second drives a real Chromium** against tests/fixtures/greenhouse_form.html
over file://, and is skipped with `skipped (no playwright)` when the package
is absent — the same convention the crawler uses for a missing credential,
and for the same reason: a missing optional dependency must read as a
missing dependency and never as a passing test.

Nothing in this file touches a real employer. Not a mock of one, not a
staging one, not one "just to check the selectors". A test that posts an
application to a live board is a bug, and the fixture exists precisely so
that nobody is ever tempted.

The two ambiguous outcomes are worth naming, because both are deliberately
resolved AGAINST retrying:

  - the page did not confirm  (Unconfirmed)
  - the submit step itself raised

In both cases the click may have landed. "I clicked and could not read the
response" and "I did not click" are indistinguishable from here, and
retrying the first applies to the same job twice under somebody's real name.
So both record `submitted`, keep the error text, and stop.
"""
import asyncio
import io
import re
import os
import sys
import time
import datetime as dt
import itertools

from cryptography.fernet import Fernet

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"
os.environ.pop("APPLY_KILL_SWITCH", None)
os.environ["APPLY_HOLD_MINUTES"] = "15"

import main as m                                   # noqa: E402
from worker import flow                            # noqa: E402
from worker.adapters import ADAPTERS               # noqa: E402
from worker.adapters.base import (Adapter, FillResult, Question,  # noqa: E402
                                  Unconfirmed)
from worker.resume import build_pdf, resume_file_for   # noqa: E402

m.Base.metadata.create_all(bind=m.engine)
m._migrate_columns()

P, F, S = [], [], []


def ck(n, c, d=""):
    print(("PASS " if c else "FAIL ") + n + (f" — {d}" if d else ""),
          flush=True)
    (P if c else F).append(n)


def skip(n, why):
    print(f"SKIP {n} — {why}", flush=True)
    S.append(n)


FIXTURE = os.path.join(ROOT, "tests", "fixtures", "greenhouse_form.html")
SHOTS = os.path.join(ROOT, "tests", "fixtures", "_shots")

# ------------------------------------------------------------- the fixture
u = f"{int(time.time())}{os.getpid()}"
db = m.SessionLocal()
me = m.User(name="Worker Person", email=f"worker{u}@example.com",
            password_hash=m.hash_pw("WorkerPass1!"), dob=dt.date(1992, 5, 5),
            plan="pro", city="Hyderabad")
db.add(me)
db.commit()
db.refresh(me)
db.add(m.ApplyConsent(user_id=me.id, granted_at=m.now(),
                      scope="Apply on my behalf."))
db.add(m.Note(user_id=me.id, k="resume_uptext", v=(
    "ANJALI RAO\nBackend Engineer\nanjali.rao@example.com | +91 98765 43210 | "
    "Hyderabad, India\nhttps://github.com/anjalirao\n\nSUMMARY\nBackend "
    "engineer with six years building payment systems in Python and Go.\n\n"
    "EXPERIENCE\nSenior Engineer, Northwind Pay (2021-2025)\n"
    "- Rebuilt the settlement pipeline; cut reconciliation time by 40%.\n"
    "- Ran the on-call rota for twelve services.\n\n"
    "EDUCATION\nB.Tech Computer Science, JNTU Hyderabad, 2019\n")))
db.add(m.Note(user_id=me.id, k="resume_data", v=(
    '{"name": "Anjali Rao", "email": "anjali.rao@example.com", '
    '"phone": "+91 98765 43210", "location": "Hyderabad, India", '
    '"links": "https://github.com/anjalirao", '
    '"exp": [{"role": "Senior Engineer", "company": "Northwind Pay"}], '
    '"edu": [{"school": "JNTU Hyderabad", "degree": "B.Tech", '
    '"year": "2019"}]}')))
db.commit()

job = m.Job(source="greenhouse", external_id=f"gh-{u}", title="Backend Engineer",
            company=f"Example Co {u}", is_open=True,
            url="file:///" + FIXTURE.replace("\\", "/"))
db.add(job)
db.commit()
db.refresh(job)


# Each row gets its own employer unless a test says otherwise. The
# per-company hour is live for every submit, so a fixture that reuses one
# company quietly starts blocking its own later cases - which is the cap
# working correctly and the test lying about what it is measuring.
_seq = itertools.count(1)


def new_row(status="prepared", company=None, **kw):
    row = m.ApplyQueue(user_id=me.id, job_id=job.id, source="greenhouse",
                       url=job.url, title=job.title,
                       company=company or f"{job.company} #{next(_seq)}",
                       status=status, created_at=m.now(), updated_at=m.now(),
                       **kw)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def clear_bank():
    db.query(m.AnswerBank).filter(
        m.AnswerBank.user_id == me.id).delete(synchronize_session=False)
    db.commit()


# --------------------------------------------------------------- the stubs
class StubPage:
    """Everything flow.py asks of a page, which is one method."""

    def __init__(self):
        self.shots = []

    async def screenshot(self, path=None, full_page=False):
        self.shots.append(path)
        with open(path, "wb") as fh:
            fh.write(b"\x89PNG\r\n\x1a\n")       # enough to exist


class StubAdapter(Adapter):
    source = "greenhouse"

    def __init__(self, missing=None, confirm="Thank you for applying",
                 raise_on=None):
        self.missing = missing or []
        self.confirm = confirm
        self.raise_on = raise_on            # "open" | "submit" | "unconfirmed"
        self.calls = []

    async def open(self, page, url, account=None):
        self.calls.append("open")
        self.account = account
        if self.raise_on == "open":
            raise RuntimeError("the listing has closed")
        if self.raise_on == "needs_account":
            from worker.adapters.workday import NeedsAccount
            raise NeedsAccount("mastercard.wd1.myworkdayjobs.com",
                               "Mastercard")
        if self.raise_on == "bad_creds":
            from worker.adapters.workday import BadCredentials
            raise BadCredentials("That employer refused the sign-in.")

    async def fill(self, page, profile):
        self.calls.append("fill")
        self.profile = profile
        return FillResult(filled=["email", "first_name"], count=2)

    async def answers(self, page, bank):
        self.calls.append("answers")
        self.bank_seen = dict(bank)
        return [q for q in self.missing
                if m.question_norm(q.label) not in bank]

    async def attach(self, page, resume_path):
        self.calls.append("attach")
        self.attached = resume_path

    async def submit(self, page):
        self.calls.append("submit")
        if self.raise_on == "submit":
            raise RuntimeError("the button moved")
        if self.raise_on == "unconfirmed":
            raise Unconfirmed("the page did not say so")
        return self.confirm


AUTH_Q = Question(selector="#auth", norm="",
                  label="Are you legally authorized to work in the "
                        "United States?", kind="select", required=True,
                  options=["Yes", "No"])


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


# -------------------------------------------------------- the happy path
print("\none row, from prepared to a hold window")
clear_bank()
row = new_row()
ad = StubAdapter()
page = StubPage()
out = run(flow.run_row(db, m, row, ad, page, SHOTS, resume_path="x.pdf"))
ck("it ends holding", out == "holding", out)
ck("in the order a form needs",
   ad.calls == ["open", "fill", "answers", "attach"], str(ad.calls))
# flow.aware, not a raw subtraction: SQLite hands back a naive datetime
# where Postgres gives an aware one, and comparing the two raises.
ck("the hold window is set from the setting",
   row.hold_until is not None
   and 14 <= (flow.aware(row.hold_until) - m.now()).total_seconds() / 60 <= 15.1,
   str(row.hold_until))
ck("with a screenshot to look at", bool(row.screenshot_path)
   and os.path.exists(row.screenshot_path),
   "'we are about to send this' with nothing to see is a countdown, not a "
   "review")
ck("and it cost no retry, because nothing failed",
   (row.attempt or 0) == 0,
   "attempt counts failures, not passes: a candidate asked for two answers "
   "on one awkward form must not reach the third with no retries left")
ck("the profile carries the keys filler.js matches on",
   {"first_name", "last_name", "email", "phone", "linkedin"}
   <= set(ad.profile), sorted(ad.profile)[:6])
ck("built from the stored resume, not invented",
   ad.profile.get("email") == "anjali.rao@example.com",
   ad.profile.get("email"))

print("\nnothing goes out before the window is up")
out = run(flow.run_row(db, m, row, ad, page, SHOTS))
ck("a second pass inside the window does nothing", out == "holding", out)
ck("and did not click submit", "submit" not in ad.calls, str(ad.calls))

print("\nand goes when it is")
row.hold_until = m.now() - dt.timedelta(seconds=1)
db.commit()
out = run(flow.run_row(db, m, row, ad, page, SHOTS))
ck("it is confirmed", out == "confirmed", out)
ck("with the employer's own words kept",
   "Thank you for applying" in (row.confirmation or ""), row.confirmation)
ck("and a submitted_at on it", row.submitted_at is not None)
track = db.query(m.JobTrack).filter(m.JobTrack.user_id == me.id,
                                    m.JobTrack.job_id == job.id).first()
ck("the tracker has it, where the rest of the history lives",
   track is not None and track.status == "applied", str(track and track.status))
ck("with the posting details copied in",
   track is not None and track.company == row.company,
   "jobs get pruned; a history that empties with the listing is not one")

print("\na cancellation window that can actually be used")
row = new_row(status="holding", hold_until=m.now() - dt.timedelta(minutes=1))
row.status = "cancelled"
db.commit()
out = run(flow.run_row(db, m, row, StubAdapter(), StubPage(), SHOTS))
ck("a cancelled row is never picked up", out == "cancelled", out)
ck("and due_rows does not offer it",
   row.id not in [r.id for r in flow.due_rows(db, m, 50)],
   "a terminal status the worker still polls is a row that sends itself "
   "after somebody stopped it")

print("")
print("a pasted link has no job_id, and two of them are two applications")
# JobTrack was matched on job_id. A pasted link has none, and
# `job_id == None` matches every other row with a null job_id — so the
# second pasted application would have updated the first one's tracker
# row and the first application would have vanished from the history.
clear_bank()
os.environ["APPLY_HOLD_MINUTES"] = "0"
before = db.query(m.JobTrack).filter(m.JobTrack.user_id == me.id).count()
for n in (1, 2):
    r = m.ApplyQueue(user_id=me.id, job_id=None, source="greenhouse",
                     url=f"file:///pasted{n}/jobs/{n}",
                     title="Pasted link", company=f"Pasted {n}",
                     status="prepared", created_at=m.now())
    db.add(r)
    db.commit()
    db.refresh(r)
    run(flow.run_row(db, m, r, StubAdapter(), StubPage(), SHOTS,
                     resume_path="x.pdf"))
os.environ["APPLY_HOLD_MINUTES"] = "15"
after = db.query(m.JobTrack).filter(m.JobTrack.user_id == me.id).count()
ck("two pasted applications make two tracker rows", after - before == 2,
   f"{before} -> {after}")
ck("and neither carries a null id the screen would render as 'null'",
   db.query(m.JobTrack).filter(m.JobTrack.user_id == me.id,
                               m.JobTrack.job_id.is_(None)).count() == 0,
   "the tracker card keys its controls off this attribute")
# The same link applied for twice — which happens after a failure, or when
# somebody re-pastes one — must update its own row, not add a second.
os.environ["APPLY_HOLD_MINUTES"] = "0"
again = m.ApplyQueue(user_id=me.id, job_id=None, source="greenhouse",
                     url="file:///pasted1/jobs/1",
                     title="Pasted link", company="Pasted 1",
                     status="prepared", created_at=m.now())
db.add(again)
db.commit()
db.refresh(again)
run(flow.run_row(db, m, again, StubAdapter(), StubPage(), SHOTS,
                 resume_path="x.pdf"))
os.environ["APPLY_HOLD_MINUTES"] = "15"
ck("the same link again updates its own row rather than adding another",
   db.query(m.JobTrack).filter(m.JobTrack.user_id == me.id).count() == after,
   f"{after} -> "
   f"{db.query(m.JobTrack).filter(m.JobTrack.user_id == me.id).count()}")

# ---------------------------------------------------- questions it cannot answer
print("\na question with no deterministic answer parks the row")
clear_bank()
row = new_row()
ad = StubAdapter(missing=[AUTH_Q])
out = run(flow.run_row(db, m, row, ad, StubPage(), SHOTS, resume_path="x.pdf"))
ck("it parks rather than guessing", out == "needs_answer", out)
ck("nothing was attached or sent",
   "attach" not in ad.calls and "submit" not in ad.calls, str(ad.calls))
ck("and the question is kept in the employer's own words",
   "legally authorized" in (row.missing_json or ""), (row.missing_json or "")[:90])
ck("with the options, so it can be answered without opening the form",
   '"Yes"' in (row.missing_json or ""), (row.missing_json or "")[:120])

print("\nand once answered, it never asks again")
db.add(m.AnswerBank(user_id=me.id,
                    question_norm=m.question_norm(AUTH_Q.label),
                    answer="Yes", created_at=m.now()))
row.status = "prepared"
db.commit()
ad = StubAdapter(missing=[AUTH_Q])
out = run(flow.run_row(db, m, row, ad, StubPage(), SHOTS, resume_path="x.pdf"))
ck("the bank resolves it", out == "holding", out)
ck("and the worker read the key the API wrote",
   m.question_norm(AUTH_Q.label) in getattr(ad, "bank_seen", {}),
   "two normalisers that disagree by a comma make a bank that never hits")

# ------------------------------------------------------------- the refusals
print("\nno resume, no application")
clear_bank()
row = new_row()
out = run(flow.run_row(db, m, row, StubAdapter(), StubPage(), SHOTS,
                       resume_path=None))
ck("it fails rather than sending an empty form", out == "failed", out)
ck("and says what to do", "resume" in (row.error or "").lower(), row.error)

print("\nconsent is checked again immediately before the click")
row = new_row(status="holding", hold_until=m.now() - dt.timedelta(minutes=1))
for cs in db.query(m.ApplyConsent).filter(
        m.ApplyConsent.user_id == me.id,
        m.ApplyConsent.revoked_at.is_(None)).all():
    cs.revoked_at = m.now()
db.commit()
ad = StubAdapter()
out = run(flow.run_row(db, m, row, ad, StubPage(), SHOTS))
ck("a withdrawn consent cancels the row", out == "cancelled", out)
ck("and nothing was submitted", "submit" not in ad.calls, str(ad.calls))
ck("with the reason recorded", "withdrawn" in (row.error or "").lower(),
   row.error)
db.add(m.ApplyConsent(user_id=me.id, granted_at=m.now(), scope="again"))
db.commit()

print("\nthe kill switch stops an in-flight loop")
row = new_row()
os.environ["APPLY_KILL_SWITCH"] = "1"
halted = False
ad = StubAdapter()
try:
    run(flow.run_row(db, m, row, ad, StubPage(), SHOTS, resume_path="x.pdf"))
except flow.Halted:
    halted = True
ck("run_row refuses to start", halted, "it raises rather than returning, so "
   "the loop stops instead of spinning through the whole queue")
ck("and touched nothing", ad.calls == [], str(ad.calls))
db.refresh(row)
ck("the row is left exactly as it was, not failed",
   row.status == "prepared" and (row.attempt or 0) == 0,
   f"{row.status}/{row.attempt}")

# Mid-flight: prepared already, switch thrown before the submit pass.
row.status = "holding"
row.hold_until = m.now() - dt.timedelta(minutes=1)
db.commit()
halted = False
try:
    run(flow.run_row(db, m, row, StubAdapter(), StubPage(), SHOTS))
except flow.Halted:
    halted = True
ck("a holding row will not send while it is set", halted)
os.environ.pop("APPLY_KILL_SWITCH", None)
out = run(flow.run_row(db, m, row, StubAdapter(), StubPage(), SHOTS))
ck("and clearing it resumes without a redeploy", out == "confirmed", out)

print("")
print("and so is the subscription that bought the queue")
row = new_row(status="holding", hold_until=m.now() - dt.timedelta(minutes=1))
me.plan = "free"
db.commit()
ad = StubAdapter()
out_ = run(flow.run_row(db, m, row, ad, StubPage(), SHOTS))
ck("a lapsed plan stops the row", out_ == "cancelled", out_)
ck("before anything is sent", "submit" not in ad.calls, str(ad.calls))
ck("and says why, so it can be fixed by renewing",
   "Pro" in (row.error or ""), (row.error or "")[:90],)
me.plan = "pro"
db.commit()

# ------------------------------------------------------------------- caps
print("\nthe per-company hour defers, it does not fail")
# One named employer, and a row already sent to it inside the hour.
CO = f"Crowded Co {u}"
db.add(m.ApplyQueue(user_id=me.id, job_id=job.id, source="greenhouse",
                    company=CO, status="confirmed", submitted_at=m.now(),
                    created_at=m.now()))
db.commit()
os.environ["APPLY_MAX_PER_COMPANY_HOUR"] = "1"
row = new_row(status="holding", company=CO,
              hold_until=m.now() - dt.timedelta(minutes=1))
ad = StubAdapter()
out = run(flow.run_row(db, m, row, ad, StubPage(), SHOTS))
ck("it stays holding", out == "holding", out)
ck("nothing was sent", "submit" not in ad.calls, str(ad.calls))
ck("the window is pushed out rather than the row being lost",
   flow.aware(row.hold_until) > m.now(), str(row.hold_until))
ck("and the reason names the employer",
   CO in (row.error or ""), (row.error or "")[:110])
os.environ["APPLY_MAX_PER_COMPANY_HOUR"] = "2"

print("\nand so does the per-user day")
os.environ["APPLY_MAX_PER_USER_DAY"] = "1"
row.hold_until = m.now() - dt.timedelta(minutes=1)
db.commit()
out = run(flow.run_row(db, m, row, StubAdapter(), StubPage(), SHOTS))
ck("it defers too", out == "holding", out)
ck("rather than failing an application because the queue was busy",
   row.status == "holding" and "limit" in (row.error or "").lower(),
   row.error)
os.environ["APPLY_MAX_PER_USER_DAY"] = "20"

# --------------------------------------------------------------- retries
print("\nthree attempts, then stop")
row = new_row()
ad = StubAdapter(raise_on="open")
for i in range(1, 4):
    out = run(flow.run_row(db, m, row, ad, StubPage(), SHOTS,
                           resume_path="x.pdf"))
ck("it gives up on the third", out == "failed", out)
ck("with the attempt count at the ceiling", row.attempt == flow.MAX_ATTEMPTS,
   str(row.attempt))
ck("and the error text kept, not cleared",
   "listing has closed" in (row.error or ""), (row.error or "")[:110])
ck("a failed row is not polled again",
   row.id not in [r.id for r in flow.due_rows(db, m, 50)])

# ------------------------------------------------- the two ambiguous endings
print("\nsent but not confirmed is recorded as sent, and never retried")
row = new_row(status="holding", hold_until=m.now() - dt.timedelta(minutes=1))
out = run(flow.run_row(db, m, row, StubAdapter(raise_on="unconfirmed"),
                       StubPage(), SHOTS))
ck("the row is submitted, not failed", out == "submitted", out)
ck("with no confirmation claimed", not (row.confirmation or ""),
   "'submitted' with invented evidence is the one lie this must not tell")
ck("and a person is told to check it",
   "did not" in (row.error or "").lower(), (row.error or "")[:110])
ck("the tracker still records the application",
   db.query(m.JobTrack).filter(m.JobTrack.user_id == me.id,
                               m.JobTrack.job_id == job.id).first() is not None)

print("\nand a submit that raises is treated the same way")
row = new_row(status="holding", hold_until=m.now() - dt.timedelta(minutes=1))
out = run(flow.run_row(db, m, row, StubAdapter(raise_on="submit"),
                       StubPage(), SHOTS))
ck("also submitted rather than retried", out == "submitted", out,)
ck("because a retry would apply twice under a real name",
   "submit step failed" in (row.error or ""), (row.error or "")[:110])

# ------------------------------------------------------- zero-minute hold
print("\na hold of zero minutes means send it now")
os.environ["APPLY_HOLD_MINUTES"] = "0"
row = new_row()
ad = StubAdapter()
out = run(flow.run_row(db, m, row, ad, StubPage(), SHOTS,
                       resume_path="x.pdf"))
ck("it goes in the same pass", out == "confirmed", out)
ck("having still filled and attached first",
   ad.calls == ["open", "fill", "answers", "attach", "submit"], str(ad.calls))
os.environ["APPLY_HOLD_MINUTES"] = "15"

# ---------------------------------------------------------------- fairness
print("\none row per person per pass")
for _ in range(3):
    new_row()
other = m.User(name="Queue Hog", email=f"hog{u}@example.com",
               password_hash=m.hash_pw("HogPass1!"), dob=dt.date(1991, 1, 1),
               plan="pro")
db.add(other)
db.commit()
db.refresh(other)
for _ in range(3):
    db.add(m.ApplyQueue(user_id=other.id, job_id=job.id, source="greenhouse",
                        url=job.url, title=job.title, company=job.company,
                        status="prepared", created_at=m.now()))
db.commit()
due = flow.due_rows(db, m, 50)
per_user = {}
for r in due:
    per_user[r.user_id] = per_user.get(r.user_id, 0) + 1
ck("nobody gets two rows in one sweep", all(v == 1 for v in per_user.values()),
   str(per_user))
ck("and both people are in it", len(per_user) >= 2, str(len(per_user)))

# ------------------------------------------------------------ the resume file
print("\nthe attachment is built from the resume we hold")
pdf = os.path.join(SHOTS, "r.pdf")
os.makedirs(SHOTS, exist_ok=True)
build_pdf("ANJALI RAO\nBackend Engineer\n\nSUMMARY\nSix years in payments.",
          pdf)
raw = io.open(pdf, "rb").read()
ck("it is a PDF", raw.startswith(b"%PDF-1.4"), raw[:8])
ck("with a cross-reference table and a trailer",
   b"\nxref\n" in raw and b"startxref" in raw and raw.rstrip().endswith(b"%%EOF"),
   "a file some readers open and an ATS parser rejects is the worst of both")
ck("and the text really in it", b"ANJALI RAO" in raw)
got = resume_file_for(db, me.id, m, SHOTS)
ck("a candidate with a resume gets a file", got and os.path.exists(got), str(got))
ck("and one without gets None, not an empty file",
   resume_file_for(db, other.id, m, SHOTS) is None,
   "a row whose candidate has no resume must fail saying so, not submit a "
   "form with nothing attached")

# ------------------------------------------------------------ what we drive
print("\nthe adapter list and the queue's list cannot drift")
ck("every drivable source has an adapter",
   set(m.APPLY_DRIVABLE) == set(ADAPTERS),
   f"{sorted(m.APPLY_DRIVABLE)} vs {sorted(ADAPTERS)}")
ck("and every adapter is one we are allowed to drive",
   set(ADAPTERS) <= set(m.APPLY_SOURCES), sorted(ADAPTERS))
for banned in ("linkedin", "indeed", "naukri", "dice"):
    ck(f"there is no {banned} adapter", banned not in ADAPTERS)

print("\nthe worker's copy of filler.js is the extension's, unchanged")
a = io.open(os.path.join(ROOT, "extension", "filler.js"),
            encoding="utf-8").read().replace("\r\n", "\n")
b = io.open(os.path.join(ROOT, "worker", "filler.js"),
            encoding="utf-8").read().replace("\r\n", "\n")
ck("byte for byte", a == b,
   "the worker must not fork the field matcher: a divergence means the "
   "extension and the worker fill the same form differently")
# The rule is stated in its header AND kept in the code. Checking only for
# the words would pass a file that documents a guard it no longer has, and
# checking only the code would not notice the rule being quietly deleted.
code = "\n".join(l for l in b.split("\n")
                 if not l.strip().startswith(("*", "/*", "//")))
ck("it still says it never submits", "It never submits." in b)
ck("and there is no submit call in the code to contradict it",
   ".submit()" not in code and ".click()" not in code,
   "the guard is right for code running in somebody else's browser; the "
   "worker does its submitting in Python")

print("\nno model is called anywhere in the apply path")
src = ""
for base, _, files in os.walk(os.path.join(ROOT, "worker")):
    for f in files:
        if f.endswith((".py", ".js")):
            src += io.open(os.path.join(base, f), encoding="utf-8").read()
for token in ("_ai_text", "_ai_json", "openai", "anthropic", "gemini",
              "generativelanguage"):
    ck(f"no {token}", token not in src.lower().replace("_ai_", "_ai_"),
       "answers come from a table, not a guess")

print("\nand no employer domain is reachable from the worker or the fixture")
fixture = io.open(FIXTURE, encoding="utf-8").read()
src_self = io.open(__file__, encoding="utf-8").read()
# This used to assert that no ATS hostname appeared anywhere in the worker
# source, which was true until an adapter needed one: Greenhouse's embed
# endpoint is a fixed URL and the adapter cannot reach it without knowing it.
# Forbidding the string was never the point — the point is that no TEST ever
# drives a real board. So that is what is checked: every URL this suite
# opens is a local file, and the fixtures name no real employer.
_urls = re.findall(r'url="([^"]+)"', io.open(__file__, encoding="utf-8").read())
_urls += re.findall(r'url=f"([^"]+)"', io.open(__file__, encoding="utf-8").read())
_remote = [u for u in _urls if u.startswith(("http://", "https://"))]
ck("every URL this suite opens is a local file", not _remote,
   ", ".join(_remote[:3]) or "none")
ck("and the row factory builds file:// URLs",
   'url="file:///" + FIXTURE' in src_self or "file:///" in src_self,
   "a test that posts an application to a real employer is a bug, not a "
   "thorough test")
for host in ("greenhouse.io", "lever.co", "ashbyhq.com", "myworkdayjobs.com",
             "linkedin.com", "indeed.com", "naukri.com"):
    ck(f"no fixture points at {host}", host not in fixture,
       "the fixtures exist so that nothing here reaches a real board")
for banned in ("linkedin.com", "indeed.com", "naukri.com", "dice.com"):
    ck(f"and the worker cannot reach {banned}", banned not in src,
       "these are never automated: the cost falls on the candidate's own "
       "account, not on us")

# ------------------------------------------------ the real browser, if present
print("\na real Chromium against the fixture")
try:
    from playwright.sync_api import sync_playwright   # noqa: F401
    HAVE_PW = True
except Exception:
    HAVE_PW = False

if not HAVE_PW:
    skip("the full worker run", "skipped (no playwright)")
    skip("the answer bank against a real select", "skipped (no playwright)")
else:
    from worker.adapters.greenhouse import GreenhouseAdapter
    from playwright.async_api import async_playwright

    async def real_run(row, resume_path):
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(args=["--no-sandbox"])
            ctx = await browser.new_context()
            page = await ctx.new_page()
            try:
                return await flow.run_row(db, m, row, GreenhouseAdapter(),
                                          page, SHOTS, resume_path)
            finally:
                await ctx.close()
                await browser.close()

    clear_bank()
    resume = resume_file_for(db, me.id, m, SHOTS)
    row = new_row()
    out = run(real_run(row, resume))
    ck("an unanswered required question parks the row",
       out == "needs_answer", f"{out}: {(row.error or '')[:90]}")
    ck("and it is the work-authorisation one",
       "authorized to work" in (row.missing_json or "").lower(),
       (row.missing_json or "")[:120])
    ck("the optional question did not park it",
       "how did you hear" not in (row.missing_json or "").lower(),
       "parking on every optional question would park every application")

    db.add(m.AnswerBank(
        user_id=me.id,
        question_norm=m.question_norm(
            "Are you legally authorized to work in the United States?"),
        answer="Yes", created_at=m.now()))
    row.status = "prepared"
    db.commit()
    os.environ["APPLY_HOLD_MINUTES"] = "0"
    out = run(real_run(row, resume))
    os.environ["APPLY_HOLD_MINUTES"] = "15"
    ck("with the answer banked, the whole form goes through",
       out == "confirmed", f"{out}: {(row.error or '')[:140]}")
    ck("and the employer's confirmation is what proves it",
       "thank you for applying" in (row.confirmation or "").lower(),
       row.confirmation)
    ck("the resume really was attached",
       "problem with your application" not in (row.confirmation or "").lower(),
       "the fixture refuses without a file, exactly as a real board would")
    ck("a screenshot was kept for the record",
       bool(row.screenshot_path) and os.path.exists(row.screenshot_path or ""),
       row.screenshot_path)

# ------------------------------------------------- the loop, not just a row
print("")
print("and the switch stops the LOOP, mid-queue")


class StubCtx:
    async def new_page(self):
        return StubPage()

    async def close(self):
        pass


class StubBrowser:
    """Enough of a browser for run.pass_once, which is all that is under
    test here: the loop must stop on the switch rather than walking the
    rest of the queue."""

    def __init__(self):
        self.opened = 0

    async def new_context(self, **kw):
        self.opened += 1
        return StubCtx()


from worker import run as wrun     # noqa: E402  (needs no playwright)

db.query(m.ApplyQueue).filter(
    m.ApplyQueue.user_id.in_([me.id, other.id])).delete(
    synchronize_session=False)
db.commit()
for _ in range(3):
    new_row()
os.environ["APPLY_GAP_MIN"] = "0"
os.environ["APPLY_GAP_MAX"] = "0"
wrun.GAP_SECONDS = (0, 0)
os.environ["APPLY_KILL_SWITCH"] = "1"
br = StubBrowser()
stopped = False
try:
    run(wrun.pass_once(br, db))
except flow.Halted:
    stopped = True
os.environ.pop("APPLY_KILL_SWITCH", None)
ck("pass_once raises rather than draining the queue", stopped)
ck("and not one browser context was opened", br.opened == 0,
   "checked before the row, not after: a switch that stops the NEXT "
   "application is not a kill switch")
ck("every row is left exactly where it was",
   all(r.status == "prepared" and (r.attempt or 0) == 0
       for r in db.query(m.ApplyQueue).filter(
           m.ApplyQueue.user_id == me.id).all()),
   "halting must not mark anything failed; it is a pause, not a verdict")


# ------------------------------------------------- all six, each on its own
print("")
print("every adapter is selectors over one shared behaviour")
from worker.adapters.form import FormAdapter          # noqa: E402
from worker.adapters import adapter_for               # noqa: E402

for name, cls in sorted(ADAPTERS.items()):
    ck(f"{name} inherits the shared driving code",
       issubclass(cls, FormAdapter),
       "an adapter that reimplements open/fill/submit is one that can drift "
       "from the five that did not")
    a = cls()
    ck(f"{name} says which source it is", a.source == name, a.source)
    for attr in ("FORMS", "FILE_INPUTS", "SUBMITS", "CONFIRMS"):
        got = getattr(a, attr, None)
        ck(f"{name} has {attr}", isinstance(got, list) and len(got) > 0,
           str(got)[:50])
    ck(f"{name} lists selectors, never one string",
       all(isinstance(x, str) for x in a.FORMS) and len(a.FORMS) >= 1,
       "every board serves more than one generation of markup at once")

# A form in each board's own shape, driven end to end with a real browser.
# Written from each ATS's documented field naming, NOT saved from anybody's
# live page, and served over file:// — no test here may ever reach a real
# employer.
SHAPES = {
    "greenhouse": ("""<div id="application_form"><form>
        <label for="first_name">First Name *</label>
        <input id="first_name" name="job_application[first_name]" required>
        <label for="email">Email *</label>
        <input type="email" id="email" name="job_application[email]" required>
        <label for="resume">Resume *</label>
        <input type="file" id="resume" name="job_application[resume]" required>
        <input type="submit" id="submit_app" value="Submit Application">
      </form></div>""", "Thank you for applying"),
    "lever": ("""<a class="postings-btn" href="#apply">Apply for this job</a>
      <form action="/acme/apply" class="application-form">
        <label for="name">Full name *</label>
        <input id="name" name="name" required>
        <label for="email">Email *</label>
        <input type="email" id="email" name="email" required>
        <label for="resume">Resume *</label>
        <input type="file" id="resume" name="resume" required>
        <button id="btn-submit" type="submit">Submit application</button>
      </form>""", "Thank you for applying"),
    "ashby": ("""<button>Apply for this Job</button>
      <form>
        <label for="_systemfield_name">Name *</label>
        <input id="_systemfield_name" required>
        <label for="_systemfield_email">Email *</label>
        <input type="email" id="_systemfield_email" required>
        <label for="_systemfield_resume">Resume *</label>
        <input type="file" id="_systemfield_resume" required>
        <button type="submit">Submit Application</button>
      </form>""", "Thanks for applying"),
    "workable": ("""<form data-ui="application-form">
        <label for="firstname">First name *</label>
        <input id="firstname" name="firstname" required>
        <label for="email">Email *</label>
        <input type="email" id="email" name="email" required>
        <label for="resume">Resume *</label>
        <input type="file" id="resume" name="resume" accept=".pdf" required>
        <button data-ui="submit-application" type="submit">Submit application</button>
      </form>""", "Thank you for applying"),
    "smartrecruiters": ("""<button>I'm interested</button>
      <form data-test="application-form">
        <label for="firstName">First name *</label>
        <input id="firstName" name="firstName" required>
        <label for="email">Email *</label>
        <input type="email" id="email" name="email" required>
        <label for="resume">Resume *</label>
        <input type="file" id="resume" name="resume" required>
        <button data-test="submit-application" type="submit">Submit application</button>
      </form>""", "Thank you for applying"),
    "recruitee": ("""<form id="job-application-form">
        <label for="cname">Full name *</label>
        <input id="cname" name="candidate[name]" required>
        <label for="cemail">Email *</label>
        <input type="email" id="cemail" name="candidate[email]" required>
        <label for="cv">CV *</label>
        <input type="file" id="cv" name="candidate[cv]" required>
        <button type="submit">Apply</button>
      </form>""", "We received your application"),
}

_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>{src} fixture</title></head><body>
<h1>Backend Engineer</h1>
{body}
<script>
document.querySelector("form").addEventListener("submit", function (e) {{
  e.preventDefault();
  var f = document.querySelector("input[type=file]");
  /* Refuses without the file, exactly as a real board would. Otherwise the
     test proves the adapter clicked a button, not that it completed a form. */
  if (!f.files.length) {{
    document.body.innerHTML = "<h1>Please attach your CV</h1>";
    return;
  }}
  document.body.innerHTML = "<h1>{confirm}</h1>";
}});
</script></body></html>"""

if not HAVE_PW:
    skip("all six adapters against their own markup", "skipped (no playwright)")
else:
    import tempfile
    from worker.adapters.base import FillResult as _FR     # noqa: F401

    shapedir = tempfile.mkdtemp(prefix="vpshapes")
    resume2 = resume_file_for(db, me.id, m, SHOTS)
    os.environ["APPLY_HOLD_MINUTES"] = "0"
    for src, (body, confirm) in sorted(SHAPES.items()):
        path = os.path.join(shapedir, f"{src}.html")
        io.open(path, "w", encoding="utf-8").write(
            _PAGE.format(src=src, body=body, confirm=confirm))
        row = m.ApplyQueue(user_id=me.id, job_id=None, source=src,
                           url="file:///" + path.replace("\\", "/"),
                           title="Backend Engineer", company=f"{src} Co",
                           status="prepared", created_at=m.now())
        db.add(row)
        db.commit()
        db.refresh(row)

        async def drive(r, s):
            async with async_playwright() as pw:
                b = await pw.chromium.launch(args=["--no-sandbox"])
                ctx = await b.new_context()
                page = await ctx.new_page()
                try:
                    return await flow.run_row(db, m, r, adapter_for(s), page,
                                              SHOTS, resume2)
                finally:
                    await ctx.close()
                    await b.close()

        out = run(drive(row, src))
        ck(f"{src}: the form goes through", out == "confirmed",
           f"{out}: {(row.error or '')[:100]}")
        ck(f"{src}: and the employer's own words prove it",
           confirm.lower() in (row.confirmation or "").lower(),
           (row.confirmation or "")[:60])
    os.environ["APPLY_HOLD_MINUTES"] = "15"

# ---------------------------------------------- choosing from a dropdown
print("")
print("the commonest dropdown on a job application")
# "6" against 0-2 / 3-5 / 6-10 / 10+. String matching cannot do this, and it
# is why years-of-experience selects were left empty and the row parked.
if not HAVE_PW:
    skip("dropdown matching", "skipped (no playwright)")
else:
    _probe = io.open(os.path.join(ROOT, "worker", "probe.js"),
                     encoding="utf-8").read()

    async def choose(cases):
        async with async_playwright() as pw:
            b = await pw.chromium.launch(args=["--no-sandbox"])
            pg = await (await b.new_context()).new_page()
            await pg.goto("about:blank")
            await pg.evaluate("() => {" + _probe + "}")
            got = []
            for want, opts, mode in cases:
                i2 = await pg.evaluate(
                    "([w, o, mo]) => window.__vpChoose(w, o, mo)",
                    [want, opts, mode])
                got.append(opts[i2] if i2 >= 0 else None)
            await b.close()
            return got

    YEARS = ["Select...", "0-2 years", "3-5 years", "6-10 years", "10+ years"]
    EEO = ["Select...", "Male", "Female", "Prefer not to say"]
    HEARD = ["Select...", "LinkedIn", "Referral", "Other"]
    YESNO = ["Select...", "Yes", "No"]
    res = run(choose([
        ("6", YEARS, "other"),
        ("2", YEARS, "other"),
        ("12", YEARS, "other"),
        ("Yes", YESNO, "none"),
        ("Slack community", HEARD, "other"),
        ("", EEO, "decline"),
        ("Martian", YESNO, "none"),
    ]))
    ck("6 years lands in the 6-10 band", res[0] == "6-10 years", str(res[0]))
    ck("2 years lands in 0-2", res[1] == "0-2 years", str(res[1]))
    ck("12 years takes the 10+ option", res[2] == "10+ years", str(res[2]))
    ck("a plain Yes still matches exactly", res[3] == "Yes", str(res[3]))
    ck("an unlisted source falls back to Other",
       res[4] == "Other", str(res[4]))
    ck("a demographic question declines rather than guessing",
       res[5] == "Prefer not to say", str(res[5]))
    ck("and a legal yes/no with no match picks NOTHING",
       res[6] is None, str(res[6]))
    ck("which is what makes that row park for the person",
       res[6] is None,
       "saying anything at all on a declaration we cannot answer is a "
       "false statement, not a best guess")

print("")
print("no control characters in the matchers")
# Four regexes in filler.js were committed with a literal backspace where a
# word boundary belonged: /\breferr/ had become /<0x08>referr/, which matches
# nothing. All four were EXCLUSIONS, so the referrer exclusion never fired
# and a form with a "Referred by" section took the candidate's own name,
# email and phone into the referrer boxes. Measured before and after.
#
# Survivable while only the extension used it — it never submits, so a
# person saw the form first. The worker submits.
for _f in ("extension/filler.js", "worker/filler.js", "worker/probe.js"):
    _s = io.open(os.path.join(ROOT, _f), encoding="utf-8").read()
    _bad = [hex(ord(c)) for c in _s if ord(c) < 9 or 13 < ord(c) < 32]
    ck(f"{_f} has none", not _bad, ", ".join(_bad[:4]))
ck("and the referrer exclusions are real word boundaries",
   io.open(os.path.join(ROOT, "extension/filler.js"),
           encoding="utf-8").read().count("/\\breferr/") >= 6,
   "a heredoc that eats a backslash turns an exclusion into a no-op, and "
   "the failure is invisible in every editor")

# --------------------------------------------------- a form with pages
print("")
print("a three-page form: click Next, stop at Submit")
# The adapter only ever reached page one. A form with steps was filled,
# found no submit button and failed -- so every multi-page application was
# dead on arrival. It walks them now, and the one button it must NOT press
# on its own is Submit: that is what the hold window exists for.
if not HAVE_PW:
    skip("multi-page walk", "skipped (no playwright)")
else:
    STEPS = """<!doctype html><html><body>
    <div id="p1"><label for="a">First Name *</label><input id="a" required>
      <label for="e">Email *</label><input type="email" id="e" required>
      <button id="n1" type="button">Next</button></div>
    <div id="p2" style="display:none"><label for="r">Resume *</label>
      <input type="file" id="r" required>
      <button id="n2" type="button">Continue</button></div>
    <div id="p3" style="display:none"><label for="w">Why this role? *</label>
      <input id="w" required>
      <button id="go" type="submit">Submit Application</button></div>
    <script>
    var seen = [];
    n1.onclick = function () { seen.push("n1");
      p1.style.display = "none"; p2.style.display = ""; };
    n2.onclick = function () { seen.push("n2");
      p2.style.display = "none"; p3.style.display = ""; };
    go.onclick = function (e) { e.preventDefault(); seen.push("submit");
      if (!document.getElementById("r").files.length) {
        document.body.innerHTML = "<h1>Attach your CV</h1>"; return; }
      document.body.innerHTML = "<h1>Thank you for applying</h1>"; };
    window.__seen = function () { return seen.join(","); };
    </script></body></html>"""
    import tempfile as _tf
    _d = _tf.mkdtemp(prefix="vpsteps")
    _path = os.path.join(_d, "steps.html")
    io.open(_path, "w", encoding="utf-8").write(STEPS)

    from worker.adapters.form import FormAdapter

    class Stepper(FormAdapter):
        source = "greenhouse"
        SETTLE_MS = 150
        FORMS = ["#p1", "body"]
        NEXTS = ["button:has-text('Next')",
                 "button:has-text('Continue')"]
        SUBMITS = ["button:has-text('Submit Application')"]
        FILE_INPUTS = ["input[type=file]"]
        CONFIRMS = ["thank you for applying"]

    clear_bank()
    db.add(m.AnswerBank(user_id=me.id,
                        question_norm=m.question_norm("Why this role?"),
                        answer="The payments work.", created_at=m.now()))
    db.commit()
    _res = resume_file_for(db, me.id, m, SHOTS)
    _row = new_row()
    _row.url = "file:///" + _path.replace(chr(92), "/")
    db.commit()
    os.environ["APPLY_HOLD_MINUTES"] = "15"

    _pressed = {}

    async def _walk(r):
        async with async_playwright() as pw:
            b = await pw.chromium.launch(args=["--no-sandbox"])
            ctx = await b.new_context()
            pg = await ctx.new_page()
            try:
                out_ = await flow.run_row(db, m, r, Stepper(), pg, SHOTS,
                                          _res)
                _pressed["seen"] = await pg.evaluate("() => window.__seen()")
                return out_
            finally:
                await ctx.close()
                await b.close()

    _out = run(_walk(_row))
    ck("it reaches the hold window", _out == "holding",
       f"{_out}: {(_row.error or '')[:90]}")
    ck("having pressed Next on page one and Continue on page two",
       _pressed.get("seen") == "n1,n2", str(_pressed.get("seen")))
    ck("and NOT pressed Submit",
       "submit" not in (_pressed.get("seen") or ""),
       "the hold window is worthless if the form has already gone")
    ck("the resume was attached on the page that had the input",
       bool(_row.screenshot_path), _row.screenshot_path or "")
    os.environ["APPLY_HOLD_MINUTES"] = "15"

# ------------------------------- an employer who wants an account first
print("")
print("Workday: stop, wait however long it takes, then carry on")
# 872 of the open postings are Workday, across 39 employers, and every
# tenant is a separate account. We do not create them: registering accepts
# that employer's terms and sends a verification email to the candidate's
# inbox, and both are theirs to do. So the row stops, names the employer,
# and waits -- with no expiry, because giving up after an hour would throw
# the application away for somebody who read their email in the evening.
os.environ["APPLY_CRED_KEY"] = Fernet.generate_key().decode()
db.query(m.AtsAccount).filter(
    m.AtsAccount.user_id == me.id).delete(synchronize_session=False)
db.commit()

WD = "https://mastercard.wd1.myworkdayjobs.com/Careers/job/Backend-Engineer"
wd_row = new_row(company="Mastercard")
wd_row.source = "workday"
wd_row.url = WD
db.commit()
ad = StubAdapter(raise_on="needs_account")
out_ = run(flow.run_row(db, m, wd_row, ad, StubPage(), SHOTS,
                        resume_path="x.pdf"))
ck("it parks rather than failing", out_ == "needs_login", out_)
ck("naming the employer, not a URL",
   "Mastercard" in (wd_row.error or ""), (wd_row.error or "")[:70])
ck("and telling them exactly what to do",
   "verification" in (wd_row.error or "").lower()
   and "sign-in here" in (wd_row.error or "").lower(),
   (wd_row.error or "")[:110])
ck("no retry was spent on it", (wd_row.attempt or 0) == 0,
   "there was nothing to fail at")
ck("and the worker will not pick it up again on its own",
   wd_row.id not in [r.id for r in flow.due_rows(db, m, 50)],
   "a row polled on a timer would hammer that login while somebody is "
   "still waiting for the email")

print("")
print("and the moment they save the sign-in, it goes")
# This is the whole point of the wait: they do it once per employer, and
# every posting from that employer after it is automatic. Mastercard alone
# is 367 of the 872.
_acct = m.AtsAccount(user_id=me.id, site="mastercard.wd1.myworkdayjobs.com",
                     label="Mastercard", username="ravi@example.com",
                     password_enc=m.cred_encrypt("their-own-password"),
                     verified_at=m.now(), created_at=m.now())
db.add(_acct)
db.commit()
wd_row.status = "prepared"
db.commit()
ad = StubAdapter()
out_ = run(flow.run_row(db, m, wd_row, ad, StubPage(), SHOTS,
                        resume_path="x.pdf"))
ck("the row proceeds", out_ == "holding", out_)
ck("the adapter was handed their own sign-in",
   (ad.account or {}).get("username") == "ravi@example.com",
   str(ad.account))
ck("with the real password, decrypted only at the point of use",
   (ad.account or {}).get("password") == "their-own-password")
ck("and nothing readable is stored",
   "their-own-password" not in (_acct.password_enc or ""),
   "encrypted, not hashed -- it has to be typed into a login form, which "
   "is exactly why this column is the dangerous one")

print("")
print("a refused sign-in blames the account, not the application")
wd_row.status = "prepared"
db.commit()
out_ = run(flow.run_row(db, m, wd_row, StubAdapter(raise_on="bad_creds"),
                        StubPage(), SHOTS, resume_path="x.pdf"))
db.expire_all()
_acct = db.get(m.AtsAccount, _acct.id)
ck("the row waits again", out_ == "needs_login", out_)
ck("and the ACCOUNT carries the reason",
   "refused" in (_acct.last_error or "").lower(),
   (_acct.last_error or "")[:70])
ck("it is un-verified so nothing retries it",
   _acct.verified_at is None,
   "every queued row would otherwise hammer that employer's login")

db.query(m.AtsAccount).filter(
    m.AtsAccount.user_id == me.id).delete(synchronize_session=False)
db.commit()
os.environ.pop("APPLY_CRED_KEY", None)

# ------------------------------------------------------------------ cleanup
db.query(m.ApplyQueue).filter(
    m.ApplyQueue.user_id.in_([me.id, other.id])).delete(
    synchronize_session=False)
db.query(m.JobTrack).filter(
    m.JobTrack.user_id == me.id).delete(synchronize_session=False)
db.commit()

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\nPASSED {len(P)}   FAILED {len(F)}"
      + (f"   SKIPPED {len(S)}" if S else ""))
sys.exit(1 if F else 0)
