"""Practising the interview out loud, and being marked on it.

Three things this covers, in the order they can hurt:

1. **What it costs.** Marking one answer is one model call by design, so the
   things that stop it being several — the too-short short circuit, the
   cache on an identical answer, delivery being counted in the browser —
   are the difference between a feature and a bill. Each is asserted
   against a counted fake, not inspected by eye.

2. **What it is allowed to say.** The marker's reply is validated before it
   reaches a page: the score is clamped to 0-100 whatever the model returns,
   and every string is truncated. Nothing here is rendered as markup, which
   is checked statically against mock.js as well as here.

3. **Whether the button exists at all.** The trainer is a tab inside the
   careers page, and a tab needs its button, its switch branch, its render
   branch and its click delegation — the same shape as the sidebar click
   chain that has silently swallowed a page three times. An unwired tab
   throws no error; it just does nothing. So the wiring is asserted.

Nothing in here spends a real model call: _ai_text is replaced with a
counted fake for the whole run and put back at the end.
"""
import os
import re
import sys
import time

os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"   # local test database; refused on a deployment
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main as m                                          # noqa: E402
from fastapi.testclient import TestClient                 # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P, F = [], []


def ck(n, c, d=""):
    (P if c else F).append(n + (f" — {d}" if d else ""))


# ---- a counted fake in place of the model --------------------------------
CALLS = {"n": 0, "last": ""}
REPLY = ('{"score": 72, "verdict": "Solid on the what, thin on the result.",'
         '"covered": ["Named the actual tool and why it was chosen"],'
         '"missed": ["What changed afterwards, in a number"],'
         '"structure": "Situation and action, no result.",'
         '"delivery": "Steady pace, a few fillers.",'
         '"model_answer": "We moved the core pair overnight...",'
         '"followup": "What would you do differently?"}')


async def _fake_ai(prompt, tokens=1500, **kw):
    CALLS["n"] += 1
    CALLS["last"] = prompt
    return REPLY


_real_ai = m._ai_text
m._ai_text = _fake_ai
_real_enabled = m.ASK_ENABLED
m.ASK_ENABLED = True

stamp = int(time.time())
A = TestClient(m.app)

# ---- one account, adult, paid where it needs to be -----------------------
E = f"mock{stamp}@example.com"
r = A.post("/api/auth/signup", json={"name": "Mock Test", "email": E,
                                     "password": "MockPass123!"})
assert r.status_code < 400, r.text

db = m.SessionLocal()
u = db.query(m.User).filter(m.User.email == E).first()
u.dob = m.dt.date(1992, 3, 14)          # REQUIRE_DOB gates the whole job side
db.commit()

COMPANY = f"Northwind{stamp}"
job = m.Job(title="Network Engineer", company=COMPANY, location="Chennai",
            url="https://example.com/nw", is_open=True, category="network",
            description="BGP, OSPF, packet capture. On-call rotation.",
            text="bgp ospf packet capture on-call",
            source="test", external_id=f"mock-{stamp}")
db.add(job)
db.commit()
JOB_ID = job.id
db.close()


# ---- the validator, on its own -------------------------------------------
# It runs on whatever the model returned, which on a bad day is anything.
wild = m._clean_mock({"score": 900, "verdict": "x" * 5000,
                      "covered": ["ok", None, {"not": "a string"}],
                      "missed": None, "model_answer": "y" * 5000})
ck("a score above 100 is clamped", wild["score"] == 100, str(wild["score"]))
ck("a score below 0 is clamped",
   m._clean_mock({"score": -40})["score"] == 0)
ck("a non-numeric score becomes 0",
   m._clean_mock({"score": "banana"})["score"] == 0)
ck("the verdict is truncated", len(wild["verdict"]) <= 300, str(len(wild["verdict"])))
ck("the model answer is truncated", len(wild["model_answer"]) <= 1200)
ck("a null list becomes a list", wild["missed"] == [])
ck("junk entries are dropped from a list, strings kept",
   "ok" in wild["covered"] and len(wild["covered"]) <= 4, str(wild["covered"]))
ck("every field comes back a string, never markup",
   all(isinstance(wild[k], str)
       for k in ("verdict", "structure", "delivery", "model_answer", "followup")))

# ---- the short answer costs nothing --------------------------------------
before = CALLS["n"]
r = A.post("/api/interview/mock", json={
    "question": "Tell me about a time you handled an outage.",
    "answer": "um yeah I did that once"})
ck("a too-short answer still answers", r.status_code == 200, str(r.status_code))
if r.status_code == 200:
    d = r.json()
    ck("a too-short answer scores 0", d.get("score") == 0, str(d.get("score")))
    ck("and says so rather than finding something kind",
       bool(d.get("verdict")))
ck("a too-short answer spends no model call", CALLS["n"] == before,
   f"{CALLS['n'] - before} spent")

# ---- marking is a paid feature, and the free plan is zero -----------------
# PLANS["free"]["ai_total"] is 0: a free account has no AI requests at all,
# lifetime. So marking is paid outright — not "paid once you run out" — and
# the refusal must arrive as a paywall rather than as a broken feature.
db = m.SessionLocal()
u = db.query(m.User).filter(m.User.email == E).first()
ck("this account starts free", m.plan_of(u) == "free", m.plan_of(u))
db.close()

before = CALLS["n"]
r = A.post("/api/interview/mock", json={
    "question": f"Tell me about yourself. [{stamp}]",
    "answer": "I have spent six years running enterprise networks, mostly "
              "campus and data centre, and the last two on migrations."})
ck("free cannot have an answer marked", r.status_code == 402, str(r.status_code))
ck("and it says so as a paywall, not an outage",
   "plan" in r.text.lower() or "upgrade" in r.text.lower(), r.text[:90])
ck("and refusing spends nothing", CALLS["n"] == before)

db = m.SessionLocal()
u = db.query(m.User).filter(m.User.email == E).first()
u.plan = "pro"
db.commit()
db.close()

# ---- a real marking ------------------------------------------------------
Q = f"Walk me through a BGP session that keeps flapping. [{stamp}]"
ANSWER = ("So the first thing I would do is check whether the session is "
          "actually flapping or whether the monitoring is lying to me. I "
          "would look at the logs on both sides and see whether the reset is "
          "coming from us or from them, and then I would check MTU because "
          "that has bitten me before on a peering link.")
before = CALLS["n"]
r = A.post("/api/interview/mock", json={
    "question": Q, "answer": ANSWER, "why": "Whether they debug from evidence",
    "seconds": 38, "words": len(ANSWER.split()), "fillers": 2})
ck("a real answer is marked", r.status_code == 200,
   f"{r.status_code} {r.text[:160]}")
first = r.json() if r.status_code == 200 else {}
ck("marking spent exactly one model call", CALLS["n"] == before + 1,
   f"{CALLS['n'] - before}")
if first:
    ck("the score comes through", first.get("score") == 72, str(first.get("score")))
    ck("what was missed comes through", bool(first.get("missed")))
    ck("a model answer comes through", bool(first.get("model_answer")))
    ck("it is not reported as cached", first.get("cached") is False)

# The delivery numbers are counted in the browser and handed over as fact —
# paying a model to measure words per minute would be paying for arithmetic.
ck("the prompt is told the pace rather than asked to work it out",
   "words per minute" in CALLS["last"] or "per minute" in CALLS["last"])
ck("the prompt carries the filler count", "filler" in CALLS["last"])
ck("the prompt carries the question", "flapping" in CALLS["last"])
ck("the marker is told not to judge the accent", "accent" in CALLS["last"])

# ---- the same answer twice is not two bills ------------------------------
before = CALLS["n"]
r2 = A.post("/api/interview/mock", json={
    "question": Q, "answer": ANSWER, "why": "Whether they debug from evidence",
    "seconds": 38, "words": len(ANSWER.split()), "fillers": 2})
ck("the same answer marks again", r2.status_code == 200, str(r2.status_code))
ck("the same answer is served from cache", CALLS["n"] == before,
   f"{CALLS['n'] - before} spent")
if r2.status_code == 200:
    ck("and says it was cached", r2.json().get("cached") is True)
    ck("and gives the same mark", r2.json().get("score") == first.get("score"))

# A different answer to the same question is a different marking.
before = CALLS["n"]
A.post("/api/interview/mock", json={
    "question": Q,
    "answer": ANSWER + " And then I would raise it with the peer's NOC "
                       "because the reset was coming from their side."})
ck("a different answer is marked afresh", CALLS["n"] == before + 1,
   f"{CALLS['n'] - before}")

# ---- practising against one posting is the paid product ------------------
# Back to free for one request, to prove the per-posting gate is its own
# refusal and not just the quota running out.
db = m.SessionLocal()
u = db.query(m.User).filter(m.User.email == E).first()
u.plan = "free"
db.commit()
db.close()

before = CALLS["n"]
r = A.post("/api/interview/mock", json={
    "question": Q + " again", "answer": ANSWER, "job_id": JOB_ID})
ck("free cannot practise against a specific job", r.status_code == 402,
   str(r.status_code))
ck("and refusing costs nothing", CALLS["n"] == before)

db = m.SessionLocal()
u = db.query(m.User).filter(m.User.email == E).first()
u.plan = "pro"
db.commit()
db.close()

r = A.post("/api/interview/mock", json={
    "question": f"What would you check first on a slow site? [{stamp}]",
    "answer": ANSWER, "job_id": JOB_ID, "seconds": 30, "fillers": 0})
ck("paid can practise against a specific job", r.status_code == 200,
   f"{r.status_code} {r.text[:140]}")
ck("and the posting reaches the marker",
   "Network Engineer" in CALLS["last"] and COMPANY in CALLS["last"])

# ---- the company panel, which costs nothing ------------------------------
before = CALLS["n"]
r = A.get(f"/api/interview/company?job_id={JOB_ID}")
ck("the company panel answers", r.status_code == 200, str(r.status_code))
if r.status_code == 200:
    c = r.json()
    ck("it names the company", c.get("company") == COMPANY, str(c.get("company")))
    ck("it counts the openings we hold", c.get("openings", 0) >= 1,
       str(c.get("openings")))
    ck("it says what it is counted from", "not reported interview questions"
       in (c.get("basis") or "").lower(), (c.get("basis") or "")[:80])
    ck("rounds and history are lists",
       isinstance(c.get("rounds"), list) and isinstance(c.get("history"), list))
ck("the company panel spends no model call", CALLS["n"] == before)

r = A.get("/api/interview/company")
ck("a company panel with nothing to look up is refused",
   r.status_code == 400, str(r.status_code))

# The tracker is the one piece of past data that is unambiguously real.
A.post("/api/jobs/track", json={"job_id": JOB_ID, "status": "interviewing"})
r = A.get(f"/api/interview/company?job_id={JOB_ID}")
if r.status_code == 200:
    hist = r.json().get("history") or []
    ck("your own history with them shows up", len(hist) >= 1, str(len(hist)))
    ck("and it is labelled in words, not a status code",
       bool(hist and hist[0].get("label")), str(hist[:1]))

# ---- with no provider configured, it says so -----------------------------
m.ASK_ENABLED = False
r = A.post("/api/interview/mock", json={"question": Q, "answer": ANSWER})
ck("with no AI provider, marking says so rather than failing oddly",
   r.status_code == 503, str(r.status_code))
m.ASK_ENABLED = True

# ---- what the browser does with the reply --------------------------------
# Nothing the model wrote is trusted as markup. mock.js escapes every field
# it prints; this is the static half of that promise.
js = open(os.path.join(ROOT, "mock.js"), encoding="utf-8").read()
for field in ("s.verdict", "s.structure", "s.delivery", "s.model_answer",
              "s.followup"):
    # esc(s.verdict) and esc(s.verdict || "") are both escaped; a prefix
    # match accepts either without accepting an unescaped print.
    ck(f"mock.js escapes {field}", f"esc({field}" in js)
    bare = re.search(r"[+$]\s*\{?\s*" + re.escape(field) + r"\s*\}?\s*\+", js)
    ck(f"mock.js never prints {field} raw", bare is None,
       bare.group(0) if bare else "")
ck("mock.js escapes the question", "esc(cur.q)" in js)
ck("mock.js escapes what you said", "esc(M.heard)" in js)

# esc() escapes & < > and not quotes, which is correct between tags and wrong
# inside an attribute. Job titles and company names come off crawled
# postings; round names come from a model. A double quote in any of them
# would break out of the attribute it sits in.
ck("mock.js has an attribute-safe escaper", "function escAttr(" in js)
for attr in re.findall(r'data-mk(?:round|title|co|cat|label)="\' \+ (\w+)\(', js):
    ck(f"the {attr} attribute value is attribute-escaped", attr == "escAttr",
       attr)

# ---- the microphone stays on the device ----------------------------------
ck("mock.js posts a transcript, not audio",
   "/api/interview/mock" in js and "FormData" not in js and "Blob" not in js)
ck("mock.js never records audio",
   "MediaRecorder" not in js and "getUserMedia" not in js)

# ---- voice.js still exposes what the trainer calls ------------------------
v = open(os.path.join(ROOT, "voice.js"), encoding="utf-8").read()
for fn in ("V.dictate", "V.endDictation", "V.speak", "V.answerStats",
           "V.dictating", "V.hushNow"):
    ck(f"voice.js exposes {fn}", fn + " =" in v or fn + "=" in v)
# The restart inside onend is the mechanism, not a fallback: without it one
# pause for thought ends the answer and the candidate is marked on half of it.
ck("dictation restarts itself after a pause",
   "dlisten();" in v and v.count("dlisten") >= 3, str(v.count("dlisten")))

# ---- the tab is actually wired ------------------------------------------
# A tab needs four things, exactly like the sidebar click chain. Miss one and
# the button is dead with no error anywhere.
h = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
ck("1/4 index.html loads mock.js", re.search(r'src="mock\.js\?v=', h) is not None)
ck("2/4 the Practice tab has a button", 'data-jbtab="mock"' in h
   or '${tab("mock"' in h)
ck("3/4 the tab has a switch branch", 'JB.tab==="mock"' in h and "Mock.open()" in h)
ck("4/4 the tab has a render branch", "Mock.html()" in h)
ck("and clicks inside it are delegated", "Mock.click(e)" in h)
ck("and its checkboxes are delegated", "Mock.change(e)" in h)

# ---- put the model back --------------------------------------------------
m._ai_text = _real_ai
m.ASK_ENABLED = _real_enabled

print("\n".join("PASS " + x for x in P))
print("\n".join("FAIL " + x for x in F))
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
