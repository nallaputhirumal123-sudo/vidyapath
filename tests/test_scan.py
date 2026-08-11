"""The scanner and the course generator: validation, gating, and privacy."""
import io
import json
import os
import secrets
import sys
import time

os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"   # local test database; refused on a deployment
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main as m                                                    # noqa: E402
import scanner as SC                                                # noqa: E402
from fastapi.testclient import TestClient                           # noqa: E402

m.send_email = lambda *a, **k: None
ok = fail = 0


def check(n, c, d=""):
    global ok, fail
    if c:
        ok += 1
        print(f"  PASS  {n}" + (f"  ({d})" if d else ""))
    else:
        fail += 1
        print(f"  FAIL  {n}" + (f"  ({d})" if d else ""))


STAMP = int(time.time())
A, B = TestClient(m.app), TestClient(m.app)
EA, EB = f"scana{STAMP}@example.com", f"scanb{STAMP}@example.com"
A.post("/api/auth/signup", json={"name": "Scan A", "email": EA,
                                 "password": "ScanPass123!"})
B.post("/api/auth/signup", json={"name": "Scan B", "email": EB,
                                 "password": "ScanPass123!"})


def uid(email):
    d = m.SessionLocal()
    try:
        return d.query(m.User).filter(
            m.func.lower(m.User.email) == email.lower()).first().id
    finally:
        d.close()


# --------------------------------------------------------------------------
print("THE MODEL'S REPLY IS REBUILT, NOT TRUSTED")
out = SC.clean({"readable": True, "kind": "worked", "subject": "Thermodynamics",
                "lang": "python", "read": "Q1  2x + 5 = 15",
                "steps": [{"heading": "Move the 5",
                           "teach": "Subtract 5 from both sides.",
                           "working": "2x = 10"}],
                "answer": "x = 5", "next": "Practise two-step equations."})
check("a good reply survives", out["readable"] and len(out["steps"]) == 1)
check("the subject is free text, not a list", out["subject"] == "Thermodynamics")

check("an unknown kind falls back to other",
      SC.clean({"kind": "astrology", "steps": [{"teach": "x"}]})["kind"]
      == "other")
check("an unknown language is dropped",
      SC.clean({"lang": "brainfuck", "steps": [{"teach": "x"}]})["lang"] == "")
check("readable is false when there is nothing to show",
      not SC.clean({"readable": True, "steps": []})["readable"])
check("junk instead of an object does not raise",
      SC.clean("not a dict")["kind"] == "other")
check("steps that are not objects are skipped",
      SC.clean({"steps": ["oops", {"teach": "real"}]})["steps"] ==
      [{"heading": "", "teach": "real", "working": ""}])
check("only six steps are kept",
      len(SC.clean({"steps": [{"teach": str(i)} for i in range(20)]})["steps"])
      == 6)
# Newlines have to survive or code and derivations arrive as one long line.
check("line breaks in the reading survive",
      "\n" in SC.clean({"read": "line one\nline two",
                        "steps": [{"teach": "x"}]})["read"])
check("control characters do not",
      "\x07" not in SC.clean({"read": "bell\x07here",
                              "steps": [{"teach": "x"}]})["read"])
check("a title comes off the first real line",
      SC.title({"read": "\n\n  Find dy/dx  \nmore"}) == "Find dy/dx")
check("a title falls back to the subject",
      SC.title({"read": "", "subject": "Roman law"}) == "Roman law")

# --------------------------------------------------------------------------
print("\nBAD UPLOADS ARE REFUSED BEFORE ANY MODEL CALL")
r = A.post("/api/scan", files={"image": ("x.jpg", b"", "image/jpeg")})
check("an empty file is refused", r.status_code == 400, str(r.status_code))
r = A.post("/api/scan", files={"image": ("x.exe", b"MZ", "application/x-msdownload")})
check("a non-image is refused", r.status_code == 400, str(r.status_code))
big = io.BytesIO(b"\xff" * int((SC.MAX_MB + 1) * 1024 * 1024))
r = A.post("/api/scan", files={"image": ("big.jpg", big.getvalue(), "image/jpeg")})
check("an oversized photo is refused", r.status_code == 400, str(r.status_code))
r = A.post("/api/scan",
           files={"image": ("x.jpg", b"\xff\xd8\xff", "image/jpeg; charset=x")})
check("a charset suffix on the mime type is tolerated",
      r.status_code != 400, str(r.status_code))

print("\nSIGNED OUT, NOTHING SCANS")
G = TestClient(m.app)
check("anonymous cannot scan",
      G.post("/api/scan",
             files={"image": ("x.jpg", b"\xff\xd8\xff", "image/jpeg")}
             ).status_code == 401)
check("anonymous cannot list scans",
      G.get("/api/scan/recent").status_code == 401)
check("anonymous cannot build a course",
      G.post("/api/course", json={"topic": "anything"}).status_code == 401)

# --------------------------------------------------------------------------
print("\nONE PERSON'S SCANS ARE THEIRS")
# Planted directly: the endpoint itself needs a model, and what is under test
# here is who may read a stored answer, not how it was generated.
# Fully random, not a truncated timestamp: "deadbeef{stamp}"[:16] cut the
# stamp off mid-way, so two runs in the same ten seconds produced the same
# key and the second one died on the unique index.
DIGEST = secrets.token_hex(8)
BODY = {"readable": True, "kind": "worked", "subject": "Cardiology",
        "lang": "", "read": "How does the heart pump blood?",
        "steps": [{"heading": "Filling", "teach": "The atria fill.",
                   "working": ""}],
        "answer": "In two stages.", "next": "Read about the cardiac cycle."}
_d = m.SessionLocal()
_d.add(m.AskCache(qkey=f"scan|{DIGEST}", subject="scan", level="worked",
                  question="How does the heart pump blood?",
                  lesson=json.dumps(BODY), hits=0))
_d.add(m.Note(user_id=uid(EA), k=f"scan:{DIGEST}",
              v=json.dumps({"title": "How does the heart pump blood?",
                            "kind": "worked", "subject": "Cardiology",
                            "at": m.now().isoformat()})))
_d.commit()
_d.close()

r = A.get(f"/api/scan/{DIGEST}")
check("the owner can reopen it", r.status_code == 200 and
      r.json()["scan"]["subject"] == "Cardiology", str(r.status_code))
check("somebody else cannot, even knowing the key",
      B.get(f"/api/scan/{DIGEST}").status_code == 404)
check("it is in the owner's recent list",
      any(x["key"] == DIGEST for x in A.get("/api/scan/recent").json()["recent"]))
check("and not in anybody else's",
      not B.get("/api/scan/recent").json()["recent"])
check("a made-up key is a 404",
      A.get("/api/scan/0000000000000000").status_code == 404)
# The list route must not be swallowed by the {key} route declared beside it.
check("recent is a list, not a lookup of a scan called 'recent'",
      "recent" in A.get("/api/scan/recent").json())

n = A.request("DELETE", "/api/scan/recent").json()["cleared"]
check("clearing removes the owner's history", n >= 1, str(n))
check("and the list is then empty", not A.get("/api/scan/recent").json()["recent"])
_d = m.SessionLocal()
check("but the shared answer cache is untouched",
      _d.query(m.AskCache).filter(m.AskCache.qkey == f"scan|{DIGEST}").first()
      is not None)
_d.close()

# --------------------------------------------------------------------------
print("\nTHE COURSE IS REBUILT TOO")
c = m._clean_course({
    "title": "The cardiac cycle", "why": "You will be able to trace it.",
    "hours": "9", "prereq": ["basic anatomy"],
    "modules": [{"name": "Filling", "goal": "g", "lessons": [
        {"name": "Diastole", "teach": "The chambers relax.", "example": "e",
         "practice": "p", "trap": "t",
         "visual": {"want": "3d", "of": "human heart", "look_for": "valves"},
         "check": {"q": "Which?", "options": ["a", "b", "c", "d"],
                   "answer": 2, "why": "because"}}],
        "exam": [{"q": "In range", "options": ["a", "b"], "answer": 1},
                 {"q": "Out of range", "options": ["a", "b"], "answer": 7},
                 {"q": "Too few options", "options": ["a"], "answer": 0}]}],
    "after": "Valvular disease"})
mod = c["modules"][0]
check("hours given as a string is coerced", c["hours"] == 9)
check("a lesson keeps its self-test", mod["lessons"][0]["check"]["answer"] == 2)
check("a 3d hint survives", mod["lessons"][0]["visual"]["want"] == "3d")
check("an answer index outside the options is dropped, not clamped",
      len(mod["exam"]) == 1 and mod["exam"][0]["q"] == "In range",
      str([q["q"] for q in mod["exam"]]))
check("an invented visual kind is dropped",
      m._clean_course({"modules": [{"lessons": [
          {"teach": "t", "visual": {"want": "hologram"}}]}]}
      )["modules"][0]["lessons"][0]["visual"] is None)
check("a lesson with no teaching is dropped",
      m._clean_course({"modules": [{"lessons": [{"name": "empty"}]}]}
                      )["modules"] == [])
check("hours cannot be absurd",
      m._clean_course({"hours": 99999, "modules": []})["hours"] == 200)
check("every depth has a description",
      all(k in m._DEPTH for k in
          ("curious", "undergrad", "masters", "phd", "applied")))
check("the prompt does not steer towards programming",
      "any subject at all" in m._course_prompt("Ottoman tax law", "phd", ""))
check("the depth reaches the prompt",
      "doctoral researcher" in m._course_prompt("x", "phd", ""))
check("an unknown depth still produces a prompt",
      "at their own level" in m._course_prompt("x", "nonsense", ""))

# --------------------------------------------------------------------------
print("\nTHE ATS SCORE IS ABOUT THE RESUME, NOT THE FILTER")
# The bug this pins down: one untouched resume scored 81 on "past week" and 58
# on "past 24 hours", because the score was mostly requirement coverage
# measured over whichever jobs the date filter had left behind. The narrower
# window simply had weaker roles in it to be compared against.
RES = ("Summary\nSenior network engineer.\n"
       "Experience\nRan BGP and OSPF across 40 sites, cut latency 30%.\n"
       "Skills\npython, sql, linux, aws, docker, kubernetes, terraform, "
       "bgp, ospf, ansible, git, networking\nEducation\nBEng")


def pool(n, rich):
    """n scored jobs whose requirement coverage is high or low."""
    return [{"score": 70, "company": f"c{i}",
             "matched": ["python", "sql", "aws"] if rich else ["python"],
             "missing": [] if rich else ["go", "rust", "scala", "kafka"]}
            for i in range(n)]


skills, _ = m._profile(RES)
impact, parsing = m._impact_score(RES), m._parsing_score(RES)
wide = m._ats_view(RES, pool(20, True), impact, parsing, skills, "past week")
tight = m._ats_view(RES, pool(4, False), impact, parsing, skills,
                    "past 24 hours")

check("the score does not move with the date filter",
      wide["score"] == tight["score"], f"{wide['score']} vs {tight['score']}")
check("nor does the keyword figure",
      wide["keyword_match"] == tight["keyword_match"])
check("nor parse quality or evidence",
      wide["parse_quality"] == tight["parse_quality"]
      and wide["impact_evidence"] == tight["impact_evidence"])
# Coverage against live roles is genuinely about the jobs, so it must still be
# reported and must still move — otherwise it is measuring nothing.
check("requirement coverage is still reported",
      "pool" in wide and "pool" in tight)
check("and it does move with the filter",
      wide["pool"]["cover"] != tight["pool"]["cover"],
      f"{wide['pool']['cover']}% vs {tight['pool']['cover']}%")
check("the coverage figure names the filter it used",
      "past 24 hours" in tight["pool"]["note"], tight["pool"]["note"][:52])
check("an empty pool leaves the score intact and omits coverage",
      m._ats_view(RES, [], impact, parsing, skills)["score"] == wide["score"]
      and "pool" not in m._ats_view(RES, [], impact, parsing, skills))
check("a thin resume still scores below a full one",
      m._ats_view("Experience\nDid things.", [], 0.1, 0.5, set())["score"]
      < wide["score"])
check("every date option has its own label",
      len({m._posted_label(x) for x in ("1", "3", "7", "14", "30")}) == 5)
check("no date filter says so", m._posted_label("") == "all open roles")

# --------------------------------------------------------------------------
print("\nCOMING BACK TO IT")
for q in ("How does a MOSFET switch?", "What is a JOIN?",
          "How does a MOSFET switch?"):
    A.post("/api/recent", json={"q": q, "kind": "board"})
rec = A.get("/api/recent").json()["recent"]
check("questions are remembered", len(rec) == 2, str(len(rec)))
check("asking again moves it up rather than duplicating",
      rec[0]["q"] == "How does a MOSFET switch?", rec[0]["q"])
check("the kind is kept", rec[0]["kind"] == "board")
A.post("/api/recent", json={"q": "odd one", "kind": "telepathy"})
check("an unknown kind falls back to ask",
      [r for r in A.get("/api/recent").json()["recent"]
       if r["q"] == "odd one"][0]["kind"] == "ask")
check("one person's history is not another's",
      not B.get("/api/recent").json()["recent"])
check("blank is refused", A.post("/api/recent", json={"q": "   "}
                                 ).status_code == 400)
check("anonymous has no history", G.get("/api/recent").status_code == 401)
n = A.request("DELETE", "/api/recent").json()["cleared"]
check("clearing works", n == 3 and not A.get("/api/recent").json()["recent"],
      str(n))

print("\nPROGRESS ONLY MOVES ON ANSWERED QUESTIONS")
T = f"mosfet {STAMP}"
check("nothing answered to start with",
      A.get(f"/api/course/progress?topic={T}").json()["attempted"] == 0)
r = A.post("/api/course/progress",
           json={"topic": T, "lesson": "m0l0", "correct": False}).json()
check("a wrong answer counts as attempted, not as done",
      r["attempted"] == 1 and r["right"] == 0, str(r))
r = A.post("/api/course/progress",
           json={"topic": T, "lesson": "m0l0", "correct": True}).json()
check("getting it right later marks it done",
      r["right"] == 1 and r["answered"]["m0l0"]["tries"] == 2,
      str(r["answered"]))
r = A.post("/api/course/progress",
           json={"topic": T, "lesson": "m0l0", "correct": False}).json()
check("and a later wrong answer does not un-earn it", r["right"] == 1)
check("a different course keeps its own count",
      A.get("/api/course/progress?topic=roman law").json()["attempted"] == 0)
check("one person's progress is not another's",
      B.get(f"/api/course/progress?topic={T}").json()["attempted"] == 0)

# --------------------------------------------------------------------------
print("\nTHE DEEP EXPLANATION IS PAID, BY EVERY ROUTE")
# 3D scenes reach a learner two ways: on the Pro smart board, and inside a
# generated course. The board has always been paid; the course had one free
# go, which quietly made the whole 3D layer reachable without paying.
check("the course generator gives no free goes",
      m.FREE_TRIAL["course"] == 0, str(m.FREE_TRIAL["course"]))
r = A.post("/api/course", json={"topic": "the cardiac cycle",
                                "level": "undergrad"})
check("a free account is refused a course", r.status_code == 402,
      str(r.status_code))
check("and is told why, not just refused",
      "Pro" in r.json().get("detail", "") or "plan" in r.json().get("detail", ""),
      r.json().get("detail", "")[:60])
# An allowance of zero must not claim they spent something they never had.
check("it does not invent a free go they never had",
      "used your" not in r.json().get("detail", ""),
      r.json().get("detail", "")[:70])
# The scanner stays open, because it is the way in rather than the product.
check("the scanner still has its free goes", m.FREE_TRIAL["scan"] == 3)
check("every free-tier allowance is deliberate, not an oversight",
      set(m.FREE_TRIAL) == {"resume_upload", "match", "extension",
                            "sql_explain", "scan", "course", "solve_paper"},
      str(sorted(m.FREE_TRIAL)))
# One whole paper, and it is a considered one rather than a copy of the
# scanner's three. Solving sixty questions is many calls and it is the thing
# a school is buying, so it cannot be unlimited — but a teacher has to run
# one real paper through it before believing any of it, and a description of
# what it does is not that.
check("solving a paper gives exactly one free paper",
      m.FREE_TRIAL["solve_paper"] == 1, str(m.FREE_TRIAL["solve_paper"]))

# --------------------------------------------------------------------------
print("\nUPSTREAM FAILURES ARE NOT THE USER'S FAULT")
# Every rate limit used to come back as "the free AI limit has been reached".
# On a Pro account that is false, and it reads as a billing fault on their own
# account — the worst thing to be wrong about.
def msg(raw):
    return m._ai_error_message(Exception(raw))


check("a rate limit says the provider, not the plan",
      "provider is rate-limiting" in msg("429 Too Many Requests"),
      msg("429 Too Many Requests")[:50])
check("and reassures them nothing was spent",
      "Nothing has been used up on your account" in msg("429"))
check("spent credit says so, and says waiting will not help",
      "will not fix" in msg("Error code: 429 - insufficient_quota"),
      msg("insufficient_quota")[:50])
check("a daily pool says it resets tomorrow",
      "resets tomorrow" in msg("Quota exceeded: tokens per day"))
check("anything else stays vague rather than guessing",
      "could not respond" in msg("connection reset by peer"))
check("no message ever blames the reader's free allowance",
      not any("your free" in msg(r).lower() for r in
              ("429", "insufficient_quota", "tokens per day", "billing",
               "rate limit", "boom")))
# A bare "402" in a token count or a request id must not be read as billing.
check("a number containing 402 is not a billing failure",
      "credit has run out" not in msg("stream ended after 4402 tokens"),
      msg("stream ended after 4402 tokens")[:46])

print(f"\nPASSED {ok}   FAILED {fail}")
sys.exit(1 if fail else 0)
