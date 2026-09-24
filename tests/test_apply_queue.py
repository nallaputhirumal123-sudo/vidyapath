"""Applying in somebody's name: what has to be true before anything is sent.

This is the half of auto-apply that runs in the web app — consent, the
queue, the caps, and the bank of answers that stops the same five questions
being asked on every form. The worker half is in test_apply_worker.py.

Most of what is checked here is a refusal, and that is the right shape for
this feature. The cost of a bug in the other direction is not a broken page:
it is an application sent to an employer, over a real person's name, that
they did not ask for. So the rules are:

**No consent row, nothing moves.** Not a checkbox in a settings screen — a
row with a date on it. Withdrawing it cancels everything still in flight,
because consent that leaves a queue draining has not been withdrawn at all.

**Only ATS forms.** LinkedIn, Indeed, Naukri and Dice are never automated:
no public apply API, against their terms, and doing it gets the crawler
blocked and takes the candidate's account with it. The aggregators hand back
a redirect to somebody else's site rather than a form, so they are a
discovery source and nothing more. Workday needs a per-tenant account, and
creating one means agreeing to an employer's terms as the candidate.

**Caps exist to protect everybody else.** Twelve applications into one
employer in an hour is what gets a whole domain blocked, and no individual's
limit can prevent that — which is why the per-company one counts across all
candidates and the per-user one counts what is queued, not only what was
sent. A cap that only counted sent applications would let somebody queue two
hundred and find out one submission at a time over the following week.

**A question with no deterministic answer parks the row.** There is no model
in this path. A guessed answer to "are you legally authorized to work in the
United States" is not a small bug.
"""
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
os.environ.pop("APPLY_KILL_SWITCH", None)

import main                                        # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

main.Base.metadata.create_all(bind=main.engine)
main._migrate_columns()
main.send_email = lambda *a, **k: None

P, F = [], []


def ck(n, c, d=""):
    print(("PASS " if c else "FAIL ") + n + (f" — {d}" if d else ""),
          flush=True)
    (P if c else F).append(n)


# ------------------------------------------------------------- the fixture
u = f"{int(time.time())}{os.getpid()}"
db = main.SessionLocal()
c = TestClient(main.app)
em = f"apply{u}@example.com"
c.post("/api/auth/signup",
       json={"name": "Apply Person", "email": em, "password": "ApplyPass1!"})
me = db.query(main.User).filter(main.User.email == em).first()
me.dob = dt.date(1995, 6, 1)
me.plan = "pro"                     # applying is Pro; the gate is checked below
db.commit()

# Postings on four sources: one we drive, one that needs an employer account,
# one aggregator redirect, and one ATS not in this slice.
# Realistic per-source URLs, because one of the tests below pastes one back
# in and the link reader decides what an ATS is from the host. A fixture on
# example.invalid would have proved the reader works on nothing real.
_ATS_URL = {
    "greenhouse": "https://boards.greenhouse.io/{slug}/jobs/{n}",
    "lever": "https://jobs.lever.co/{slug}/{n}",
    "workday": "https://acme.wd5.myworkdayjobs.com/External/{n}",
    "adzuna": "https://www.adzuna.co.uk/land/ad/{n}",
}


def mkjob(source, title, company):
    slug = company.split()[0].lower()
    shape = _ATS_URL.get(source, "https://example.invalid/{slug}/{n}")
    url = shape.format(slug=slug, n=abs(hash((source, title, u))) % 10**7)
    j = main.Job(source=source, external_id=f"{source}-{u}-{title}",
                 title=title, company=company, is_open=True,
                 url=url)
    db.add(j)
    db.commit()
    db.refresh(j)
    return j


gh1 = mkjob("greenhouse", "Backend Engineer", f"Alpha {u}")
gh2 = mkjob("greenhouse", "Platform Engineer", f"Beta {u}")
gh3 = mkjob("greenhouse", "Data Engineer", f"Alpha {u}")
wd = mkjob("workday", "Cloud Engineer", f"Gamma {u}")
agg = mkjob("adzuna", "Site Reliability", f"Delta {u}")
lev = mkjob("lever", "Staff Engineer", f"Epsilon {u}")
# A source with no adapter and none planned, for the refusal path. All six
# no-login ATSs are drivable now, so proving "we do not drive that" needs a
# source that genuinely is not one of them.
agg2 = mkjob("himalayas", "Remote Engineer", f"Zeta {u}")


def clean_queue():
    db.query(main.ApplyQueue).filter(
        main.ApplyQueue.user_id == me.id).delete(synchronize_session=False)
    db.commit()


def grant():
    return c.post("/api/apply/consent",
                  json={"scope": "Apply on my behalf to jobs I queue."})


# ------------------------------------------------- consent, before anything
print("\nnothing is applied for without permission on the record")
c.delete("/api/apply/consent")
r = c.post("/api/apply/queue", json={"job_ids": [gh1.id]})
ck("queueing is refused with no consent row", r.status_code == 403,
   f"{r.status_code} {r.text[:80]}")
ck("and the refusal says how to fix it",
   "permission" in r.text.lower() and "withdraw" in r.text.lower(),
   r.text[:120])
ck("nothing was queued anyway",
   db.query(main.ApplyQueue).filter(
       main.ApplyQueue.user_id == me.id).count() == 0)

r = grant()
ck("consent can be given", r.status_code == 200, r.text[:80])
ck("and it comes back stated", (r.json() or {}).get("consented") is True)
ck("with the wording that was on screen, kept verbatim",
   "Apply on my behalf" in (r.json() or {}).get("scope", ""),
   "a version number is only as good as the copy of the text it points at")
first_granted = (r.json() or {}).get("granted_at")
r2 = grant()
ck("granting twice does not stack",
   (r2.json() or {}).get("granted_at") == first_granted,
   "somebody pressing a button twice has not consented twice")
ck("and there is exactly one live row",
   db.query(main.ApplyConsent).filter(
       main.ApplyConsent.user_id == me.id,
       main.ApplyConsent.revoked_at.is_(None)).count() == 1)

# ------------------------------------------------------- what may be driven
print("\nonly forms we are allowed to drive, and a reason for each refusal")
clean_queue()
r = c.post("/api/apply/queue",
           json={"job_ids": [gh1.id, wd.id, agg.id, lev.id, agg2.id]})
ck("the request succeeds", r.status_code == 200, r.text[:100])
d = r.json()
# Two: greenhouse and lever. Both are no-login ATSs with adapters, which is
# what "drivable" means — the list grew and this number grows with it.
ck("the drivable ones are queued", d.get("queued") == 2, str(d.get("queued")))
why = {s.get("job_id"): s.get("why", "") for s in d.get("skipped", [])}
ck("workday is refused for needing an employer account",
   "account" in why.get(wd.id, "").lower(), why.get(wd.id, ""))
ck("the aggregator is refused for being a redirect, not a form",
   "aggregator" in why.get(agg.id, "").lower(), why.get(agg.id, ""))
ck("a source we do not drive at all is refused plainly",
   "manually" in why.get(agg2.id, "").lower(), why.get(agg2.id, ""))
ck("every refusal says what to do instead",
   all("apply" in v.lower() for v in why.values()), str(why)[:160])

print("\nand the four that must never be automated are not on the list")
for banned in ("linkedin", "indeed", "naukri", "dice"):
    ck(f"{banned} is not drivable", banned not in main.APPLY_SOURCES)
ck("the six that are, all need no candidate account",
   set(main.APPLY_SOURCES) == {"greenhouse", "lever", "ashby", "workable",
                               "smartrecruiters", "recruitee"},
   ", ".join(main.APPLY_SOURCES))

print("\nqueueing the same job twice does not send it twice")
r = c.post("/api/apply/queue", json={"job_ids": [gh1.id]})
ck("the duplicate is skipped", (r.json() or {}).get("queued") == 0,
   str(r.json())[:120])
ck("and says so", "already queued" in r.text.lower(), r.text[:120])

# --------------------------------------------------- queueing from a match
print("")
print("a score floor runs the match here rather than trusting the caller")
# The other path. Everything above passes explicit job ids; this one takes
# a floor and re-runs the matcher server-side from the stored resume,
# because a score that arrives in a request body is a score anybody can
# type. The matcher is deterministic Python over stored rows — no model,
# no third party — so calling it from here costs CPU and nothing else.
clean_queue()
db.add(main.Note(user_id=me.id, k="resume_uptext", v=(
    "RAVI KUMAR" + chr(10) + "Senior Backend Engineer" + chr(10) +
    "ravi@example.com" + chr(10) + chr(10) + "SKILLS" + chr(10) +
    "python, django, postgresql, aws, docker, kubernetes, redis, kafka, "
    "rest, sql, git, linux" + chr(10) + chr(10) + "EXPERIENCE" + chr(10) +
    "Senior Backend Engineer, Northwind Pay, 2021-2025" + chr(10) +
    "- Built REST APIs in Python and Django serving 4M requests a day.")))
db.add(main.Note(user_id=me.id, k="resume_data", v=(
    '{"name": "Ravi Kumar", "email": "ravi@example.com", '
    '"title": "Backend Engineer"}')))
db.commit()
r = c.post("/api/apply/queue", json={"min_score": 0, "limit": 5})
ck("it answers", r.status_code == 200, r.text[:120])
d = r.json()
rows = d.get("rows") or []
ck("and never queues a source it cannot drive",
   all(x["source"] in main.APPLY_DRIVABLE for x in rows),
   str(sorted({x["source"] for x in rows})))
if rows:
    ck("the score comes from the match, not from the request",
       any((x.get("score") or 0) > 0 for x in rows),
       str([x.get("score") for x in rows]))
else:
    # Queueing nothing is a real outcome, and there are two of them: nothing
    # matched the floor at all, or things matched and none carried a link the
    # bot can drive. Both have to reach the screen as words. "0 queued" with
    # a silent skipped list is indistinguishable from a broken button.
    ck("an empty result says which kind of empty it is",
       "lower floor" in (d.get("message") or "")
       or "could be driven" in (d.get("message") or ""),
       d.get("message"))
clean_queue()

# --------------------------------------------------------------- the caps
print("\nthe per-user day cap counts what is queued, not only what was sent")
clean_queue()
os.environ["APPLY_MAX_PER_USER_DAY"] = "2"
r = c.post("/api/apply/queue", json={"job_ids": [gh1.id, gh2.id, gh3.id]})
d = r.json()
ck("only the allowance is taken", d.get("queued") == 2, str(d.get("queued")))
ck("the rest are told why, not dropped silently",
   any("limit" in s.get("why", "").lower() for s in d.get("skipped", [])),
   str(d.get("skipped"))[:160])
ck("a second request cannot get around it",
   (c.post("/api/apply/queue",
           json={"job_ids": [gh3.id]}).json() or {}).get("queued") == 0,
   "a cap enforced only per request is not a cap")
os.environ["APPLY_MAX_PER_USER_DAY"] = "20"

print("\nthe per-company hour counts across every candidate, not one")
clean_queue()
other = main.User(name="Other Person", email=f"other{u}@example.com",
                  password_hash=main.hash_pw("OtherPass1!"),
                  dob=dt.date(1994, 2, 2), plan="pro")
db.add(other)
db.commit()
db.refresh(other)
sent = main.ApplyQueue(user_id=other.id, job_id=gh2.id, source="greenhouse",
                       company=gh1.company, status="confirmed",
                       submitted_at=main.now(), created_at=main.now())
db.add(sent)
db.commit()
ck("somebody else's application counts against the employer",
   main.company_sent_last_hour(db, gh1.company) == 1,
   "no individual's own limit can stop twelve landing on one employer")
old = main.ApplyQueue(user_id=other.id, job_id=gh3.id, source="greenhouse",
                      company=gh1.company, status="confirmed",
                      submitted_at=main.now() - dt.timedelta(hours=3),
                      created_at=main.now())
db.add(old)
db.commit()
ck("and one from three hours ago does not",
   main.company_sent_last_hour(db, gh1.company) == 1,
   "it is a rate, not a total")
ck("an unsent row does not count either",
   main.company_sent_last_hour(db, f"Nobody {u}") == 0)
db.delete(sent)
db.delete(old)
db.commit()

# --------------------------------------------------- the cancellation window
print("\nanything not yet sent can be stopped")
clean_queue()
c.post("/api/apply/queue", json={"job_ids": [gh1.id]})
row = db.query(main.ApplyQueue).filter(
    main.ApplyQueue.user_id == me.id).order_by(
    main.ApplyQueue.id.desc()).first()
row.status = "holding"
row.hold_until = main.now() + dt.timedelta(minutes=15)
db.commit()
r = c.post(f"/api/apply/queue/{row.id}/cancel")
ck("a holding row cancels", r.status_code == 200 and
   (r.json() or {}).get("status") == "cancelled", r.text[:100])
r = c.post(f"/api/apply/queue/{row.id}/cancel")
ck("cancelling it again is refused rather than pretending",
   r.status_code == 400, str(r.status_code))

row.status = "confirmed"
row.submitted_at = main.now()
db.commit()
r = c.post(f"/api/apply/queue/{row.id}/cancel")
ck("a sent one cannot be un-sent", r.status_code == 400, str(r.status_code))
ck("and the refusal is honest about why",
   "already been sent" in r.text, r.text[:100])

print("\nand one person cannot cancel another person's")
c2 = TestClient(main.app)
em2 = f"nosy{u}@example.com"
c2.post("/api/auth/signup",
        json={"name": "Nosy Person", "email": em2, "password": "NosyPass1!"})
nosy = db.query(main.User).filter(main.User.email == em2).first()
nosy.dob = dt.date(1993, 3, 3)
nosy.plan = "pro"
db.commit()
clean_queue()
c.post("/api/apply/queue", json={"job_ids": [gh1.id]})
mine = db.query(main.ApplyQueue).filter(
    main.ApplyQueue.user_id == me.id).order_by(
    main.ApplyQueue.id.desc()).first()
ck("a stranger gets a 404, not somebody else's row",
   c2.post(f"/api/apply/queue/{mine.id}/cancel").status_code == 404)
ck("nor can they answer it",
   c2.post(f"/api/apply/queue/{mine.id}/answers",
           json={"answers": {"anything": "yes"}}).status_code == 404)

# ---------------------------------------------------------- the answer bank
print("\na question asked once is answered forever")
mine.status = "needs_answer"
mine.missing_json = ('[{"label": "Are you legally authorized to work in the '
                     'United States?", "norm": "", "kind": "select", '
                     '"options": ["Yes", "No"]}]')
db.commit()
r = c.post(f"/api/apply/queue/{mine.id}/answers", json={"answers": {
    "Are you legally authorized to work in the United States? *": "Yes",
    "What is your expected salary?": "As advertised"}})
ck("the answers are taken", r.status_code == 200, r.text[:100])
ck("and the row goes back in the queue",
   (r.json() or {}).get("row", {}).get("status") == "prepared",
   str(r.json())[:120])
db.expire_all()
mine = db.get(main.ApplyQueue, mine.id)
ck("with nothing left outstanding on it", not (mine.missing_json or ""))

# The same question, dressed differently by a different employer. What
# normalisation can and cannot do is worth being exact about: it settles
# case, asterisks, "(required)" and punctuation, so "U.S.?" and "US" are
# one question. It does NOT know that "United States" and "US" are the
# same place — that would be a synonym table, and a wrong entry in one
# would put the wrong answer in somebody's application.
key = main.question_norm(
    "are you legally AUTHORIZED to work in the United States?  (required)")
bank = db.query(main.AnswerBank).filter(
    main.AnswerBank.user_id == me.id,
    main.AnswerBank.question_norm == key).first()
ck("the same question written differently finds the same answer",
   bank is not None and bank.answer == "Yes",
   "asterisks, punctuation, case and '(required)' are not the question")
ck("and an abbreviation of the same words does too",
   main.question_norm("Authorized to work in the U.S.?")
   == main.question_norm("authorized to work in the US"),
   "replacing the dot with a space would give 'u s', a third question")
ck("but two genuinely different questions stay different",
   main.question_norm("Do you require sponsorship?")
   != main.question_norm("Are you authorized to work?"),
   "a bank that collapses two questions puts the wrong answer in an "
   "application, which is worse than asking twice")
ck("two normalisers cannot drift apart",
   "from main import question_norm" in open(
       "worker/adapters/form.py", encoding="utf-8").read(),
   "the worker reads the key the API wrote; a comma between them is a bank "
   "that never hits")

r = c.post(f"/api/apply/queue/{mine.id}/answers", json={"answers": {}})
ck("an empty submission is refused rather than clearing the row",
   r.status_code == 400, str(r.status_code))

print("\nretries are not refreshed by answering")
mine.attempt = 2
mine.status = "needs_answer"
db.commit()
c.post(f"/api/apply/queue/{mine.id}/answers",
       json={"answers": {"Notice period": "30 days"}})
db.expire_all()
ck("the attempt count survives",
   db.get(main.ApplyQueue, mine.id).attempt == 2,
   "an answer does not buy a fresh set of retries against a form that may "
   "simply be unreadable")


# --------------------------------------------------- a link somebody pasted
print("")
print("a pasted link is read before anything is opened")
# The other way in. The queue above starts from the board we crawl; this
# starts from a URL found somewhere else. What matters is that the decision
# about what is on the end of it is made from the URL ALONE — a route that
# fetched an arbitrary pasted link to find out would be a request forgery
# primitive inside the network the database is on, and it would follow
# redirects to get there.
for good in ("https://boards.greenhouse.io/stripe/jobs/4123",
             "https://job-boards.greenhouse.io/acme/jobs/9",
             "boards.greenhouse.io/acme/jobs/9"):
    src, why = main.apply_source_of(good)
    ck(f"{good[:44]} is greenhouse", src == "greenhouse", why[:70])

print("")
print("and the four that must never be automated are refused by name")
for bad, name in (("https://www.linkedin.com/jobs/view/1", "LinkedIn"),
                  ("https://in.indeed.com/viewjob?jk=a", "Indeed"),
                  ("https://www.naukri.com/job-x", "Naukri"),
                  ("https://www.dice.com/jobs/detail/x", "Dice")):
    src, why = main.apply_source_of(bad)
    ck(f"{name} is refused", src is None and name in why, why[:70])
    ck(f"and told it is their terms, not a bug", "terms" in why, why[:70])

print("")
print("the checks that stop this being a fetch-anything hole")
src, why = main.apply_source_of("https://greenhouse.io.evil.com/steal")
ck("a host that merely ends in the right letters is not greenhouse",
   src is None, str(src))
ck("because the match is on the registrable host, not a substring",
   main._registrable("greenhouse.io.evil.com") == "evil.com",
   main._registrable("greenhouse.io.evil.com"))
ck("and boards.greenhouse.io still resolves properly",
   main._registrable("boards.greenhouse.io") == "greenhouse.io")
src, why = main.apply_source_of("http://boards.greenhouse.io/acme/jobs/1")
ck("plain http is refused", src is None, str(src))
ck("because a form over http sends a name and address in the clear",
   "clear" in why, why[:70])
for junk in ("", "not a url", "ftp://boards.greenhouse.io/x"):
    src, _ = main.apply_source_of(junk)
    ck(f"junk is refused: {junk!r}", src is None, str(src))
src, why = main.apply_source_of(
    "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite")
ck("Workday is refused for needing an employer account",
   src is None and "account" in why, why[:70])
# Lever has an adapter now, so the link reader should accept it. The
# "no adapter yet" branch still exists for whatever is added next.
src, why = main.apply_source_of("https://jobs.lever.co/cred/abc")
ck("a lever link is now drivable too", src == "lever", why[:70])
ck("and the no-adapter refusal is still there for whatever comes next",
   "adapter yet" in open("main.py", encoding="utf-8").read(),
   "APPLY_DRIVABLE is what we can drive today; APPLY_SOURCES is what we "
   "are allowed to")

print("")
print("queueing one goes through the same gate as everything else")
clean_queue()
LINK = "https://boards.greenhouse.io/pastedco/jobs/9911"
c.delete("/api/apply/consent")
r = c.post("/api/apply/link", json={"url": LINK})
ck("no consent, no queue", r.status_code == 403, str(r.status_code))
grant()
os.environ["APPLY_KILL_SWITCH"] = "1"
r = c.post("/api/apply/link", json={"url": LINK})
ck("the kill switch stops it too", r.status_code == 503, str(r.status_code))
os.environ.pop("APPLY_KILL_SWITCH", None)

r = c.post("/api/apply/link", json={"url": LINK})
ck("a good link is queued", r.status_code == 200, r.text[:110])
d = r.json()
ck("as a prepared row for the worker",
   (d.get("row") or {}).get("status") == "prepared", str(d.get("row"))[:90])
ck("with the employer read off the URL, so it is not blank",
   (d.get("row") or {}).get("company") == "Pastedco",
   str((d.get("row") or {}).get("company")))
ck("and the person is told about the hold window before it runs",
   "held for" in (d.get("message") or "")
   or "sent as soon" in (d.get("message") or ""), d.get("message"))
ck("it is not claimed to be a posting we know",
   d.get("recognised") is False, str(d.get("recognised")))

r = c.post("/api/apply/link", json={"url": LINK})
ck("the same link twice is refused", r.status_code == 400, str(r.status_code))
ck("and says it is already queued", "already" in r.text.lower(), r.text[:90])

print("")
print("a link to a posting we already crawl uses the crawler's own row")
# Not a detail. The per-company hour counts by employer name, so a pasted
# link recorded as "Pastedco" and a crawled row recorded as "Alpha 123"
# would be two employers as far as the cap is concerned. Reusing the known
# row keeps one employer one employer.
clean_queue()
r = c.post("/api/apply/link", json={"url": gh1.url})
ck("it is queued", r.status_code == 200, r.text[:100])
row = (r.json() or {}).get("row") or {}
ck("and recognised as one of ours", (r.json() or {}).get("recognised") is True)
ck("with the real title, not 'Pasted link'",
   row.get("title") == gh1.title, str(row.get("title")))
ck("and the employer's real name, so the hourly cap sees one employer",
   row.get("company") == gh1.company, str(row.get("company")))
ck("linked to the posting rather than floating free",
   row.get("job_id") == gh1.id, str(row.get("job_id")))

print("")
print("the day's limit covers pasted links as well")
clean_queue()
os.environ["APPLY_MAX_PER_USER_DAY"] = "1"
c.post("/api/apply/link", json={"url": LINK})
r = c.post("/api/apply/link",
           json={"url": "https://boards.greenhouse.io/other/jobs/1"})
ck("the second one is refused", r.status_code == 429, str(r.status_code))
ck("and says it can go tomorrow", "tomorrow" in r.text, r.text[:90])
os.environ["APPLY_MAX_PER_USER_DAY"] = "20"
clean_queue()

ck("and a stranger cannot queue anything at all",
   TestClient(main.app).post("/api/apply/link",
                             json={"url": LINK}).status_code == 401)

# ------------------------------------------------------------ the kill switch
print("\nthe kill switch stops new work without a redeploy")
os.environ["APPLY_KILL_SWITCH"] = "1"
ck("the app reads it live", main.apply_halted() is True,
   "read per call, not at import — a switch needing a restart is not one")
r = c.post("/api/apply/queue", json={"job_ids": [gh2.id]})
ck("queueing is refused while it is set", r.status_code == 503,
   str(r.status_code))
ck("and says the queue is untouched", "untouched" in r.text, r.text[:120])
os.environ.pop("APPLY_KILL_SWITCH", None)
ck("and clearing it is enough to resume", main.apply_halted() is False)

# ------------------------------------------------------------ withdrawing it
print("\nwithdrawing consent stops what is already in flight")
clean_queue()
c.post("/api/apply/queue", json={"job_ids": [gh1.id, gh2.id]})
held = db.query(main.ApplyQueue).filter(
    main.ApplyQueue.user_id == me.id).order_by(
    main.ApplyQueue.id.desc()).first()
held.status = "holding"
held.hold_until = main.now() + dt.timedelta(minutes=15)
done = main.ApplyQueue(user_id=me.id, job_id=gh3.id, source="greenhouse",
                       company="Already Sent", status="confirmed",
                       submitted_at=main.now(), created_at=main.now())
db.add(done)
db.commit()
r = c.delete("/api/apply/consent")
ck("it is withdrawn", r.status_code == 200 and
   (r.json() or {}).get("consented") is False, r.text[:100])
ck("and everything unsent is cancelled with it",
   (r.json() or {}).get("cancelled") == 2, str(r.json())[:140])
db.expire_all()
ck("including the one that was holding",
   db.get(main.ApplyQueue, held.id).status == "cancelled")
ck("but an application already sent is left alone",
   db.get(main.ApplyQueue, done.id).status == "confirmed",
   "it is a fact about the past; cancelling it here would only make the "
   "record wrong")
ck("the revoked row is kept, not deleted",
   db.query(main.ApplyConsent).filter(
       main.ApplyConsent.user_id == me.id,
       main.ApplyConsent.revoked_at.isnot(None)).count() >= 1,
   "'was there consent at the time' cannot be answered by a deleted row")
ck("and queueing is refused again straight away",
   c.post("/api/apply/queue",
          json={"job_ids": [gh1.id]}).status_code == 403)

# ---------------------------------------------------------------- the paywall
print("\napplying is Pro, and the gate is the existing one")
me.plan = "free"
db.commit()
r = grant()
ck("a free account is refused", r.status_code == 402, str(r.status_code))
ck("with the existing wording, not a second paywall",
   "part of Pro" in r.text, r.text[:120])
me.plan = "pro"
db.commit()
grant()

print("\nand none of it is reachable without signing in")
anon = TestClient(main.app)
for verb, path in (("post", "/api/apply/consent"),
                   ("delete", "/api/apply/consent"),
                   ("post", "/api/apply/queue"),
                   ("get", "/api/apply/queue"),
                   ("post", "/api/apply/queue/1/cancel"),
                   ("post", "/api/apply/queue/1/answers")):
    if verb == "get":
        got = anon.get(path)
    elif verb == "delete":
        got = anon.delete(path)      # httpx: DELETE carries no json body
    else:
        got = anon.post(path, json={})
    ck(f"{verb.upper()} {path}", got.status_code == 401, str(got.status_code))

print("\nthe queue reads back with what a person needs to act on it")
clean_queue()
c.post("/api/apply/queue", json={"job_ids": [gh1.id]})
d = c.get("/api/apply/queue").json()
ck("the rows come back", len(d.get("rows") or []) == 1, str(len(d.get("rows") or [])))
ck("grouped by status", set(d.get("groups", {})) == set(main.APPLY_STATUSES),
   ", ".join(sorted(d.get("groups", {}))))
ck("with the hold window stated up front",
   d.get("hold_minutes") == main.apply_hold_minutes(),
   "somebody deciding whether to trust this needs to know how long they get")
ck("and whether it is paused", d.get("paused") is False)
ck("and how much of today's allowance is gone",
   d.get("used_today") == 1 and d.get("max_per_day") == 20,
   f"{d.get('used_today')}/{d.get('max_per_day')}")

clean_queue()
db.query(main.ApplyQueue).filter(
    main.ApplyQueue.user_id == other.id).delete(synchronize_session=False)
db.commit()

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\nPASSED {len(P)}   FAILED {len(F)}")
sys.exit(1 if F else 0)
