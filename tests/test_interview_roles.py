"""Practising for a job by name, for a pasted posting, and what it costs.

Three things shipped together and none had a suite of its own:

1. **Roles by name.** The trainer offered six families, and nobody
   interviews for a family. The catalogue has to cover every category the
   board uses — a family with no roles under it is a dead chip — and it has
   to rank the clean canonical title above the board's long tail, because
   sorting on openings alone put "Staff Site Reliability Engineer
   (Linux/Network troubleshooting/Scripting)" above "Network Engineer".

2. **A pasted job description.** The board holds a hundred thousand postings
   and none of them is the one somebody is interviewing for on Thursday.

3. **What practice costs.** It used to be metered against the general AI
   quota under a 200-a-day brake, so a candidate preparing properly was
   spending the allowance they also need to apply for things. It has its own
   counter now, and the whole point is that the two do not touch.

The model is replaced with a counted fake for the entire run, so nothing
here spends anything and the assertions about cost are exact rather than
inferred.
"""
import os
import sys
import time

os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main as m                                          # noqa: E402
import roles as R                                         # noqa: E402
from fastapi.testclient import TestClient                 # noqa: E402

m.Base.metadata.create_all(m.engine)
P, F = [], []


def ck(n, c, d=""):
    (P if c else F).append(n + (f" — {d}" if d else ""))


# ---- a counted fake in place of the model --------------------------------
CALLS = {"n": 0, "last": ""}
GUIDE = ('{"role":"Network Engineer","opening":"They want someone who can '
         'find a fault.","rounds":[{"name":"Technical","what_they_test":'
         '"depth","questions":[{"q":"A BGP session is flapping. How do you '
         'find out why?","why":"evidence","answer_with":"Logs on both sides, '
         'then MTU."}]}],"gaps":[],"ask_them":["What is on-call like?"]}')


SCORE = ('{"score":71,"verdict":"Good method, no result.","covered":'
         '["Went to both sides logs"],"missed":["What you actually found"],'
         '"structure":"Situation and action.","delivery":"Steady.",'
         '"model_answer":"I would check both sides...","followup":"And then?"}')


async def _fake_ai(prompt, tokens=1500, **kw):
    CALLS["n"] += 1
    CALLS["last"] = prompt
    # One fake, two shapes. A scorer handed a question set gets nothing it
    # can read, which surfaced as a 502 and looked like a bug in the app.
    return SCORE if "just heard this answer out loud" in prompt else GUIDE


_real_ai, _real_enabled = m._ai_text, m.ASK_ENABLED
m._ai_text = _fake_ai
m.ASK_ENABLED = True

stamp = int(time.time())
A = TestClient(m.app)

# ---- the catalogue itself -------------------------------------------------
# A family with nothing under it is a chip that opens onto an empty list,
# which is worse than not offering the family at all.
ck("every category the board uses has roles",
   set(m.CATEGORY_LABELS) == set(R.ROLES),
   str(sorted(set(m.CATEGORY_LABELS) ^ set(R.ROLES))))
ck("no family is empty", all(R.ROLES.values()))
ck("no family repeats a role",
   all(len(v) == len(set(v)) for v in R.ROLES.values()))
ck("there are enough of them to be worth a search",
   sum(len(v) for v in R.ROLES.values()) > 300,
   str(sum(len(v) for v in R.ROLES.values())))

# The two the trainer was originally asked for, by name.
flat = {r["role"].lower() for r in R.all_roles()}
ck("network engineering is covered", "network engineer" in flat)
ck("and BIM/CAD is, which the board alone never supplies",
   "bim coordinator" in flat and "cad engineer" in flat)

# Ranking: a prefix beats a mention in the middle.
res = [r["role"] for r in R.search("data")]
ck("a prefix match ranks above a match in the middle",
   res and res[0].lower().startswith("data"), str(res[:3]))
ck("searching for nothing still returns something", bool(R.search("")))

# ---- the account ----------------------------------------------------------
E = f"roles{stamp}@example.com"
r = A.post("/api/auth/signup", json={"name": "Roles Test", "email": E,
                                     "password": "RolesPass123!"})
assert r.status_code < 400, r.text
db = m.SessionLocal()
u = db.query(m.User).filter(m.User.email == E).first()
u.dob = m.dt.date(1994, 2, 2)
u.plan = "pro"
db.add(m.Note(user_id=u.id, k="resume_uptext",
              v="Network Engineer, 5 years. BGP, OSPF and MPLS across Cisco "
                "and Juniper. Packet captures in Wireshark, VLANs, DNS, "
                "DHCP and IPsec. Cut outage time by 60 percent."))
db.commit()
db.close()

# ---- the roles endpoint ---------------------------------------------------
before = CALLS["n"]
d = A.get("/api/interview/roles?category=manufacturing&limit=12").json()
names = [x["role"] for x in d.get("roles", [])]
ck("a family lists its roles", len(names) >= 8, str(len(names)))
ck("and they are that family's roles",
   any("BIM" in n or "CAD" in n or "Revit" in n for n in names), str(names[:5]))
ck("every family is offered for picking",
   len(d.get("families", [])) == len(R.ROLES), str(len(d.get("families", []))))
ck("listing roles spends nothing", CALLS["n"] == before)

d = A.get("/api/interview/roles?q=network&limit=6").json()
names = [x["role"] for x in d.get("roles", [])]
ck("search finds the job", "Network Engineer" in names, str(names[:4]))
# This is the ordering bug that made the list look broken: one real posting
# outranked the canonical title.
ck("the clean title outranks the board's long tail",
   names and names[0] == "Network Engineer", str(names[:3]))
ck("a search that matches nothing is not an error",
   A.get("/api/interview/roles?q=zzzzqqq").status_code == 200)
ck("signed out, there are no roles to browse",
   TestClient(m.app).get("/api/interview/roles").status_code == 401)

# ---- questions for one named job -----------------------------------------
# Cached on the TITLE ALONE, with no resume in the key. That is the whole
# economics: a few hundred roles is a few hundred calls across the entire
# product, not one per person — which is why it can be free to use.
ROLE = f"Network Engineer {stamp}"
before = CALLS["n"]
r = A.post("/api/interview/role", json={"role": ROLE})
ck("a named job gets its own questions", r.status_code == 200,
   f"{r.status_code} {r.text[:120]}")
ck("which cost one call", CALLS["n"] == before + 1, str(CALLS["n"] - before))
ck("and the job title reaches the prompt", ROLE.split()[0] in CALLS["last"])
# The assembled prompt, not the source text: these phrases are split across
# source lines and only exist as one string at runtime, which is the only
# form the model ever sees.
ROLE_PROMPT = CALLS["last"]
if r.status_code == 200:
    ck("it comes back as rounds of questions",
       bool((r.json().get("guide") or {}).get("rounds")))
    ck("and is not reported as cached", r.json().get("cached") is False)

before = CALLS["n"]
r2 = A.post("/api/interview/role", json={"role": ROLE})
ck("asking again costs nothing", CALLS["n"] == before, str(CALLS["n"] - before))
ck("and says it was cached", r2.json().get("cached") is True)

# Somebody else entirely gets the same free answer — no resume in the key.
B = TestClient(m.app)
B.post("/api/auth/signup", json={"name": "Other", "email": f"o{stamp}@example.com",
                                 "password": "OtherPass123!"})
# REQUIRE_DOB closes the whole job side on an account that has never said how
# old it is, which is most of what this suite touches.
_db = m.SessionLocal()
_o = _db.query(m.User).filter(m.User.email == f"o{stamp}@example.com").first()
_o.dob = m.dt.date(1996, 5, 5)
_db.commit()
_db.close()
before = CALLS["n"]
r3 = B.post("/api/interview/role", json={"role": ROLE})
ck("and it is free for everybody after the first person",
   r3.status_code == 200 and CALLS["n"] == before, str(r3.status_code))
ck("a role too short to mean anything is refused",
   A.post("/api/interview/role", json={"role": "x"}).status_code == 400)

# ---- a pasted job description --------------------------------------------
JD = (f"[ref {stamp}] " + "We are hiring a Senior Network Engineer to run our campus and data "
      "centre fabric. You will own BGP and OSPF, work on Cisco and Arista "
      "kit, automate with Ansible and Python, and share an on-call rotation. "
      "Experience reading packet captures is essential.")
before = CALLS["n"]
r = A.post("/api/interview/jd", json={"jd": JD, "company": f"Northwind{stamp}",
                                      "title": "Senior Network Engineer"})
ck("a pasted posting gets questions", r.status_code == 200,
   f"{r.status_code} {r.text[:120]}")
ck("which cost one call", CALLS["n"] == before + 1)
ck("and the posting reaches the prompt", "Arista" in CALLS["last"]
   or "arista" in CALLS["last"].lower())
# Captured here, not read later: by the end of the suite CALLS["last"] holds
# the scoring prompt, which is a different prompt entirely.
JD_PROMPT = CALLS["last"]
before = CALLS["n"]
r = A.post("/api/interview/jd", json={"jd": JD, "company": f"Northwind{stamp}",
                                      "title": "Senior Network Engineer"})
ck("the same posting again is free", CALLS["n"] == before
   and r.json().get("cached") is True)
ck("a couple of lines is not a job description",
   A.post("/api/interview/jd", json={"jd": "network job"}).status_code == 400)

# ---- what practice costs --------------------------------------------------
# The counter that matters, and the one it must not touch.
db = m.SessionLocal()
u = db.query(m.User).filter(m.User.email == E).first()
mock_before = m._mock_used_today(db, u)
ai_before = m._ai_used_today(db, u)
db.close()

ANS = ("I would check both sides' logs to see which end sent the notification "
       "and why, then look at MTU on the peering link because that has caught "
       "me before, and only then start touching configuration.")
r = A.post("/api/interview/mock", json={
    "question": f"A BGP session is flapping. How do you find out why? [{stamp}]",
    "answer": ANS, "seconds": 34, "words": len(ANS.split()), "fillers": 1})
ck("an answer is marked", r.status_code == 200, f"{r.status_code} {r.text[:110]}")
_marked = r.status_code == 200 and not r.json().get("cached")

db = m.SessionLocal()
u = db.query(m.User).filter(m.User.email == E).first()
ck("practice is counted on its own allowance",
   m._mock_used_today(db, u) == mock_before + (1 if _marked else 0),
   f"{mock_before} -> {m._mock_used_today(db, u)}, marked={_marked}")
# The whole reason the counter exists: a practice session must not spend the
# allowance somebody also needs for apply kits and job matches.
ck("and NOT against the general AI quota",
   m._ai_used_today(db, u) == ai_before,
   f"{ai_before} -> {m._ai_used_today(db, u)}")
db.close()

ck("the practice allowance is generous enough for a real session",
   m.MOCK_DAILY_LIMIT >= 100, str(m.MOCK_DAILY_LIMIT))
ck("but still bounded, so a script cannot run up a bill",
   m.MOCK_DAILY_LIMIT <= 500, str(m.MOCK_DAILY_LIMIT))

# Spent out, it says so in words rather than failing oddly.
db = m.SessionLocal()
u = db.query(m.User).filter(m.User.email == E).first()
_key = f"mock_{m.now().strftime('%Y%m%d')}"
row = db.query(m.Note).filter(m.Note.user_id == u.id,
                              m.Note.k == _key).first()
if row:
    row.v = str(m.MOCK_DAILY_LIMIT)
else:
    db.add(m.Note(user_id=u.id, k=_key, v=str(m.MOCK_DAILY_LIMIT)))
db.commit()
db.close()
r = A.post("/api/interview/mock", json={
    "question": f"Another question entirely [{stamp}]",
    "answer": ANS, "seconds": 30})
ck("spent out, practice says so", r.status_code == 429, str(r.status_code))
ck("and says when it comes back", "tomorrow" in r.text.lower(), r.text[:90])

# ---- the questions have to be the ones people are really asked ----------
# "Not generic interview questions" is an instruction with nothing behind
# it. A model told only what NOT to do returns the safest thing it knows,
# which is the interview-advice column — and that is what was coming back.
src = open(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "main.py"), encoding="utf-8").read()
prompt = ROLE_PROMPT

ck("the role prompt says what a real question IS, not only what it is not",
   "WHAT A REAL QUESTION LOOKS LIKE" in prompt)
ck("it shows a good and a bad example",
   "BAD:" in prompt and "GOOD:" in prompt)
ck("in more than one field, so it does not become a software interview",
   "Network Engineer" in prompt and "BIM Coordinator" in prompt)
for banned in ("tell me about yourself", "three / five years",
               "greatest weakness", "why should we hire you"):
    ck(f"the column question {banned!r} is banned by name",
       banned in prompt.lower(), banned)
ck("a required mix is specified, not just a count",
   "REQUIRED MIX" in prompt)
ck("including a scenario that has gone wrong",
   "gone wrong" in prompt and "symptoms" in prompt)
ck("and experience anchored to the job rather than to conflict",
   "not 'a conflict'" in prompt or "not 'a conflict'" in prompt)
ck("hands-on jobs are asked about hands-on work",
   "Do not turn every job into a software interview" in prompt)

# The fallback that 25 of the 31 families used to land on.
ck("the fallback questions cannot be answered with an adjective",
   "Tell me about yourself." not in src
   and "Where do you want to be in three years?" not in src)
ck("and it points at the thing actually worth practising",
   "these are the " in src and "not the ones this job gets" in src)


# ---- the posting prompt asks about the work, not about the CV -----------
# Read out of production, this one was returning "What experience do you have
# with MongoDB?" and "How do you stay current with the latest trends?" --
# a recruiter reading a CV out loud and waiting to hear a noun back. The
# instruction that caused it told the model to MENTION the tool the posting
# names, which it did, in the blandest frame available.
jd_prompt = JD_PROMPT
ck("naming the tool is called the floor, not the question",
   "NAMING THE TOOL IS THE FLOOR" in jd_prompt)
for bad in ("what experience do you have with", "can you describe your ",
            "are you familiar with", "how do you stay current"):
    ck(f"the phrasing {bad.strip()!r} is banned by name",
       bad in jd_prompt.lower(), bad)
ck("and it shows what to ask instead",
   "BAD:" in jd_prompt and "GOOD:" in jd_prompt)
ck("the candidate has to be put inside the work",
   "INSIDE the work" in jd_prompt)
ck("a question answerable with a list of tools is called a failure",
   "answerable with a list of tools" in jd_prompt)

# Changing what generates an answer does nothing while the old answer is
# still cached under the same key.
ck("the interview caches were bumped past the weak answers",
   all(k in src for k in ('"iv2|"', '"ivr2|"', '"ivjd2"', '"ivrole2|"')))
ck("and the old keys are gone",
   not any(k in src for k in ('"iv|" + str(job.id)', '"ivrole|" +')))


# ---- the page is wired ----------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
js = open(os.path.join(ROOT, "mock.js"), encoding="utf-8").read()
ck("mock.js has the role picker", "rolePickerHTML" in js)
ck("and a search box", 'id="mkRoleQ"' in js)
ck("and the paste-a-description box", 'id="mkJd"' in js)
ck("the search is debounced, so typing does not repaint the box",
   "_roleT" in js and "setTimeout" in js)
# The bug that made a fully pasted description sit under a greyed-out button.
ck("the start button is toggled directly, not by repainting",
   "function syncStart(" in js and "b.disabled" in js)
# The one that showed a score and nothing to learn from.
ck("the answer falls back to the guide's own when marking returns none",
   "cur && cur.model" in js)

print("\n".join("PASS " + x for x in P))
print("\n".join("FAIL " + x for x in F))

m._ai_text, m.ASK_ENABLED = _real_ai, _real_enabled
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
