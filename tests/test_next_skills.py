"""The join between the live board and the curriculum.

The claim this feature makes is a number — "learn Java and 26 postings open
up" — so the whole suite is about whether that number can be trusted:

1. **The sentinel stops leaking.** `jobs.skills` stores "none" to mean
   "parsed, found nothing", so the backfill does not read the same rows on
   every boot. It is a marker, not a skill, and it was being counted as a
   requirement — which put "none" fourth on the list of most demanded skills
   and showed users "missing: none" in their match gaps.

2. **An employer's own name is not a skill to learn.** 86 of the 91 postings
   that "wanted" Adobe were jobs AT Adobe. Ranked by demand, that put Adobe
   top of the page — advice that was pure artefact.

3. **A lesson that says a word once does not teach it.** "node" appears
   throughout every lesson on linked lists, which had Node.js being taught
   by "Linked lists".

4. **The ranking is by what a skill opens, not by how loud it is.** A skill
   six hundred postings mention but that you are five skills away from is
   not the next thing to learn.

And the tab is checked for wiring, because a tab with no click branch is
dead and says nothing about it.
"""
import os
import re
import sys
import time

os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main as m                                          # noqa: E402
from fastapi.testclient import TestClient                 # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P, F = [], []


def ck(n, c, d=""):
    (P if c else F).append(n + (f" — {d}" if d else ""))


stamp = int(time.time())
A = TestClient(m.app)

# ---- the sentinel, at the read boundary ----------------------------------
class _FakeJob:
    """Not an ORM row — _job_skills must cope, and must still filter."""
    def __init__(self, skills="", req_skills="", text=""):
        self.skills, self.req_skills, self.text = skills, req_skills, text


ck("the sentinel has a name", getattr(m, "_NO_SKILLS", None) == "none")
ck("a 'none' posting yields no skills",
   m._job_skills(_FakeJob(skills="none")) == set(),
   str(m._job_skills(_FakeJob(skills="none"))))
ck("and 'none' never appears beside real ones",
   m._job_skills(_FakeJob(skills="none,python,sql")) == {"python", "sql"},
   str(m._job_skills(_FakeJob(skills="none,python,sql"))))
ck("requirements drop it too",
   m._job_req_skills(_FakeJob(req_skills="none,java")) == {"java"},
   str(m._job_req_skills(_FakeJob(req_skills="none,java"))))
ck("an empty requirement list is still empty",
   m._job_req_skills(_FakeJob(req_skills="")) == set())
ck("a real skill list is untouched",
   m._job_skills(_FakeJob(skills="python,docker")) == {"python", "docker"})

# ---- the lesson index -----------------------------------------------------
m._SKILL_LESSONS = None                      # rebuild, do not reuse a cache
db = m.SessionLocal()
idx = m._skill_lesson_index(db)
db.close()
ck("the curriculum is indexed by skill", isinstance(idx, dict) and len(idx) > 0,
   f"{len(idx)} skills")
ck("a lesson entry says which track it is in",
   all(("track" in x and "slug" in x and "title" in x)
       for lst in idx.values() for x in lst))
ck("no skill carries more than six lessons",
   all(len(v) <= 6 for v in idx.values()))

# "node" is in every lesson about linked lists. If Node.js is "taught" by a
# data-structures lesson, the whole page stops being trustworthy.
node_titles = " ".join(x["title"].lower() for x in idx.get("node", []))
ck("Node.js is not taught by linked lists",
   "linked list" not in node_titles, node_titles[:70] or "(no node lessons)")
ck("words that lead a double life are listed",
   "node" in m._AMBIGUOUS_SKILLS and "pandas" in m._AMBIGUOUS_SKILLS)
for amb in ("node", "spark", "rust", "pandas", "excel"):
    for x in idx.get(amb, []):
        ck(f"an ambiguous skill ({amb}) only matches on a title",
           amb in (x["title"] + " " + x["track_name"]).lower(), x["title"][:50])

# The ones it does claim to teach should be obviously right.
java_t = " ".join(x["title"].lower() for x in idx.get("java", []))
ck("Java is taught by a Java lesson", "java" in java_t, java_t[:60])
sql_t = " ".join(x["title"].lower() for x in idx.get("sql", []))
ck("SQL is taught by a SQL lesson", "sql" in sql_t, sql_t[:60])

# ---- the account and its resume ------------------------------------------
E = f"next{stamp}@example.com"
r = A.post("/api/auth/signup", json={"name": "Next Test", "email": E,
                                     "password": "NextPass123!"})
assert r.status_code < 400, r.text
db = m.SessionLocal()
u = db.query(m.User).filter(m.User.email == E).first()
u.dob = m.dt.date(1995, 6, 1)
db.commit()

# Without a resume there is nothing to diff against, and the page must say so
# rather than showing an empty list that reads as "you need nothing".
d = A.get("/api/career/next-skills").json()
ck("with no resume it says what to do", d.get("ready") is False and d.get("message"),
   str(d)[:90])

# A posting whose only unmet requirement is one skill, at a company whose own
# name is also a skill word — both behaviours in one row.
# A category of their own, so these two postings can be asserted about
# without 1,600 real ones drowning them out of the top of the ranking.
CAT = f"tcat{stamp}"
CO = "Adobe"
job = m.Job(title=f"Backend Engineer {stamp}", company=CO, location="Pune",
            url="https://example.com/n1", is_open=True, category=CAT,
            description="python and kubernetes", text="python kubernetes adobe",
            skills="python,kubernetes,adobe", req_skills="python,kubernetes,adobe",
            source="test", external_id=f"next-{stamp}-1")
db.add(job)
# A second posting that is two skills away.
job2 = m.Job(title=f"Platform Engineer {stamp}", company="Northwind", location="Pune",
             url="https://example.com/n2", is_open=True, category=CAT,
             description="python terraform kubernetes", text="python terraform kubernetes",
             skills="python,terraform,kubernetes", req_skills="python,terraform,kubernetes",
             source="test", external_id=f"next-{stamp}-2")
db.add(job2)
RESUME = ("Test Candidate\nBackend Engineer, 3 years\n"
          "Built Python services and shipped them. Wrote SQL for reporting and "
          "used Git every day on Linux. Reduced latency by 40 percent.\n"
          "Skills: Python, SQL, Git, Linux\n")
db.add(m.Note(user_id=u.id, k="resume_uptext", v=RESUME))
db.commit()
db.close()

d = A.get(f"/api/career/next-skills?limit=20&category={CAT}").json()
ck("with a resume it answers", d.get("ready") is True, str(d)[:90])
ck("it says what it counted against", "open postings" in (d.get("basis") or ""),
   (d.get("basis") or "")[:70])
ck("it reports how many you already match fully",
   isinstance(d.get("matched_now"), int))

by = {s["skill"]: s for s in d.get("skills", [])}
ck("'none' is not offered as a skill to learn", "none" not in by,
   ",".join(list(by)[:8]))
ck("the employer's own name is not a skill to learn", "adobe" not in by,
   ",".join(list(by)[:8]))
ck("kubernetes is the one skill blocking the first posting",
   by.get("kubernetes", {}).get("unlocks", 0) >= 1,
   str(by.get("kubernetes", {}).get("unlocks")))
ck("the two-skills-away posting is counted as nearly, not unlocked",
   by.get("terraform", {}).get("nearly", 0) >= 1,
   str(by.get("terraform", {}).get("nearly")))

# The ranking rule, stated as an assertion rather than as a comment.
ranks = [(s["skill"], s["unlocks"]) for s in d.get("skills", [])]
ck("ranked by what each skill unlocks",
   all(ranks[i][1] >= ranks[i + 1][1] for i in range(len(ranks) - 1)),
   str(ranks[:5]))
ck("every row carries its lessons and its jobs",
   all(isinstance(s.get("lessons"), list) and isinstance(s.get("jobs"), list)
       for s in d.get("skills", [])))
ck("a row that unlocks something names one",
   all(s["jobs"] for s in d.get("skills", []) if s["unlocks"] > 0))

# ---- core matching: the same two fixes, where they matter most -----------
# These are not the new endpoint. _job_skills and _job_req_skills feed the
# match score, the gap lists and interview prep, so the employer-name fix has
# to hold there too — including through the bulk memo attributes the match
# endpoint fills, which bypass both functions entirely.
class _CoJob:
    def __init__(self, company, skills="", req_skills=""):
        self.company, self.skills, self.req_skills, self.text = (
            company, skills, req_skills, "")


adobe = _CoJob("Adobe", "adobe,python,photoshop", "adobe,python")
ck("an employer's own name is not one of its skills",
   "adobe" not in m._job_skills(adobe), str(sorted(m._job_skills(adobe))))
ck("nor one of its requirements",
   "adobe" not in m._job_req_skills(adobe), str(sorted(m._job_req_skills(adobe))))
ck("and the real skills survive",
   m._job_skills(adobe) == {"python", "photoshop"},
   str(sorted(m._job_skills(adobe))))
ck("GitLab's own name goes too",
   "gitlab" not in m._job_skills(_CoJob("GitLab", "gitlab,cicd,docker")))
# The point of doing it per posting rather than striking the word from the
# vocabulary: Salesforce is a real skill everywhere except at Salesforce.
ck("but the same word stays a skill at a different employer",
   "salesforce" in m._job_skills(_CoJob("Northwind", "salesforce,python")))
ck("a posting with no company is unaffected",
   m._job_skills(_CoJob("", "python,sql")) == {"python", "sql"})

# The fit score is fit only. impact and readability are identical for every
# posting in a search, so they could never reorder anything — they only
# lifted and squashed the number. They are still reported, separately.
db = m.SessionLocal()
u = db.query(m.User).filter(m.User.email == E).first()
u.plan = "pro"
db.commit()
db.close()
mt = A.post("/api/jobs/match", json={"resume_text": RESUME, "limit": 30}).json()
w = ((mt.get("scoring") or {}).get("weights") or {})
ck("the published weights are the fit factors only",
   set(w) == {"hard_skills", "role_and_seniority", "domain"}, str(w))
ck("and they add up to 100", sum(w.values()) == 100, str(sum(w.values())))
ck("resume quality is still measured and shown",
   "your_impact_score" in (mt.get("scoring") or {})
   and "your_readability_score" in (mt.get("scoring") or {}))
ck("the tier bands match what match_tier does",
   m.match_tier(75)["tier"] == "S" and m.match_tier(74)["tier"] == "A"
   and m.match_tier(62)["tier"] == "A" and m.match_tier(61)["tier"] == "B"
   and m.match_tier(44)["tier"] == "C")
ck("and the bands the page quotes agree with them",
   (mt.get("scoring") or {}).get("tiers", {}).get("S", "").startswith("75"),
   str((mt.get("scoring") or {}).get("tiers", {}).get("S")))
scores = [j["score"] for j in mt.get("jobs", [])]
ck("scores are no longer stuck in a narrow band",
   (max(scores) - min(scores)) >= 15 if len(scores) > 5 else True,
   f"{min(scores)}-{max(scores)}" if scores else "no jobs")


# ---- the admin view -------------------------------------------------------
r = A.get("/api/admin/career")
ck("a normal account cannot open the admin view", r.status_code == 403,
   str(r.status_code))

db = m.SessionLocal()
u = db.query(m.User).filter(m.User.email == E).first()
u.is_admin = True
db.commit()
db.close()

r = A.get("/api/admin/career")
ck("an admin can", r.status_code == 200, str(r.status_code))
if r.status_code == 200:
    a = r.json()
    ck("it counts the board", (a.get("board") or {}).get("open", 0) > 0)
    ck("it counts what we teach",
       isinstance((a.get("curriculum") or {}).get("skills_taught"), int))
    ck("it reports the gap between demand and the curriculum",
       isinstance((a.get("curriculum") or {}).get("gap"), list))
    gap = (a.get("curriculum") or {}).get("gap") or []
    ck("nothing in the gap list is something we teach",
       all(not idx.get(g["skill"]) for g in gap),
       ",".join(g["skill"] for g in gap[:5]))
    ck("the gap is ranked by open postings",
       all(gap[i]["postings"] >= gap[i + 1]["postings"]
           for i in range(len(gap) - 1)))
    ck("'none' is not reported as demand",
       all(x["skill"] != "none" for x in (a.get("top_demand") or [])))
    ck("it reports what the mock interview cost",
       isinstance((a.get("mock") or {}).get("answers_marked"), int))

# ---- the tab is wired -----------------------------------------------------
h = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
ck("1/5 index.html loads learn.js",
   re.search(r'src="learn\.js\?v=', h) is not None)
ck("2/5 the tab has a button", '${tab("learn"' in h)
ck("3/5 the tab has a switch branch",
   'JB.tab==="learn"' in h and "Learn.openTab()" in h)
ck("4/5 the tab has a render branch", "Learn.html()" in h)
ck("5/5 its clicks are delegated", "Learn.click(e)" in h)

js = open(os.path.join(ROOT, "learn.js"), encoding="utf-8").read()
ck("learn.js escapes the skill name", "esc(s.skill)" in js)
ck("learn.js escapes job titles", "esc(j.title)" in js)
ck("learn.js attribute-escapes what goes in an attribute",
   "function escAttr(" in js and "escAttr(x.track)" in js)
ck("learn.js reuses the page's own lesson navigation",
   'data-nav="lesson"' in js)
ck("learn.js uses bare api, never window.api",
   "api.get(" in js and "window.api" not in js and "global.api" not in js)

ah = open(os.path.join(ROOT, "admin.html"), encoding="utf-8").read()
ck("admin has a Career & skills button", 'data-p="career"' in ah)
ck("and a route to it", "career:renderCareer" in ah)
ck("and a renderer", "async function renderCareer(" in ah)

print("\n".join("PASS " + x for x in P))
print("\n".join("FAIL " + x for x in F))
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
