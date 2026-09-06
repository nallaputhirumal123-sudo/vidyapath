"""What you could not do yet, and when it comes back.

The platform recorded that a lesson was finished and what a quiz scored.
Neither is learning: finishing is a timestamp, a score is a photograph of one
afternoon, and nothing anywhere remembered the thing somebody got WRONG.

Two rules carry the whole feature, and both are asserted here rather than
trusted:

1. **The answer is never sent until an attempt is posted.** Enforced on the
   server, because a rule the page enforces is a rule anybody can skip by
   reading the network tab. It is also the difference between recognising an
   answer and producing one, which is the difference between feeling taught
   and being taught.

2. **It comes back.** Right and the gap widens, wrong and it is tomorrow.

Nothing here is a model call, so the suite needs no stub: it is a table and a
date, which is exactly why the feature can run for every learner on every
visit and cost nothing.
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
from fastapi.testclient import TestClient                 # noqa: E402

# The suites run against the local SQLite file, and TestClient does not fire
# the startup event that builds the schema there.
m.Base.metadata.create_all(m.engine)

P, F = [], []


def ck(n, c, d=""):
    (P if c else F).append(n + (f" — {d}" if d else ""))


stamp = int(time.time())
A = TestClient(m.app)
E = f"recall{stamp}@example.com"
r = A.post("/api/auth/signup", json={"name": "Recall Test", "email": E,
                                     "password": "RecallPass123!"})
assert r.status_code < 400, r.text

Q = f"What is a base case, and what happens without one? [{stamp}]"
ANS = "The condition that stops the recursion; without one the stack overflows."

# ---- remembering it -------------------------------------------------------
r = A.post("/api/recall/add", json={"kind": "ask", "topic": "Recursion",
                                    "prompt": Q, "expect": ANS})
ck("a thing you could not do is kept", r.status_code == 200, str(r.status_code))
rid = r.json()["item"]["id"] if r.status_code == 200 else 0
ck("it comes back with an id", bool(rid))

# One row per question, however it was typed. Otherwise the same gap asked
# twice becomes two cards that both come back, and revision turns into
# punishment for having failed at something twice.
r2 = A.post("/api/recall/add", json={"prompt": Q.upper()})
ck("the same question twice is one row",
   r2.status_code == 200 and r2.json()["item"]["id"] == rid,
   str(r2.json().get("item", {}).get("id")))
r3 = A.post("/api/recall/add", json={"prompt": "   "})
ck("nothing to remember is refused", r3.status_code == 400, str(r3.status_code))

# ---- rule one: never answer first ----------------------------------------
db = m.SessionLocal()
row = db.get(m.Recall, rid)
row.due_at = m.now() - m.dt.timedelta(days=1)      # make it due
db.commit()
db.close()

d = A.get("/api/recall/due?limit=10").json()
ck("it is due", d.get("due", 0) >= 1, str(d.get("due")))
mine = [i for i in d.get("items", []) if i["id"] == rid]
ck("the question is served", bool(mine))
ck("THE ANSWER IS NOT SERVED WITH IT",
   all("expect" not in i for i in d.get("items", [])),
   "an answer leaked into the due list")
ck("nor is the previous attempt",
   all("last_attempt" not in i for i in d.get("items", [])))
ck("and the page is told why", "before you look" in (d.get("note") or "").lower())

# ---- rule two: it comes back ---------------------------------------------
a = A.post("/api/recall/answer",
           json={"id": rid, "attempt": "it stops it", "verdict": "got"})
ck("an attempt is accepted", a.status_code == 200, str(a.status_code))
got = a.json()
ck("and only now is the answer given", got["item"].get("expect") == ANS)
ck("getting it right strengthens it", got["item"]["strength"] == 1,
   str(got["item"]["strength"]))
first_gap = got["next_in_days"]
ck("and pushes it out", first_gap >= 1, str(first_gap))

a2 = A.post("/api/recall/answer",
            json={"id": rid, "attempt": "again", "verdict": "got"}).json()
ck("right again widens the gap further", a2["next_in_days"] > first_gap,
   f"{first_gap} -> {a2['next_in_days']}")
ck("and strength keeps climbing", a2["item"]["strength"] == 2,
   str(a2["item"]["strength"]))

a3 = A.post("/api/recall/answer",
            json={"id": rid, "attempt": "no idea", "verdict": "missed"}).json()
ck("missing it brings it back tomorrow", a3["next_in_days"] == 1,
   str(a3["next_in_days"]))
# Down two, not to zero: one bad evening should not throw away a month of
# work on something that was known perfectly well last week.
ck("but does not throw away everything", a3["item"]["strength"] == 0,
   str(a3["item"]["strength"]))
ck("and the miss is counted", a3["item"]["wrong"] == 1,
   str(a3["item"]["wrong"]))

# "Almost" holds its ground. A near miss is not a failure and certainly not a
# success, and pretending either way stops the schedule matching what
# somebody actually knows.
A.post("/api/recall/answer", json={"id": rid, "attempt": "x", "verdict": "got"})
before = A.get("/api/recall/due?limit=50").json()
db = m.SessionLocal()
row = db.get(m.Recall, rid)
row.due_at = m.now() - m.dt.timedelta(days=1)
s_before = row.strength
db.commit()
db.close()
al = A.post("/api/recall/answer",
            json={"id": rid, "attempt": "half of it", "verdict": "almost"}).json()
ck("almost does not advance strength", al["item"]["strength"] == s_before,
   f"{s_before} -> {al['item']['strength']}")
ck("almost still schedules it", al["next_in_days"] >= 1,
   str(al["next_in_days"]))

# ---- a verdict is required where nothing can mark it ---------------------
r = A.post("/api/recall/answer", json={"id": rid, "attempt": "something"})
ck("an unmarked kind must say how it went", r.status_code == 400,
   str(r.status_code))

# ---- a quiz is marked, not self-reported ---------------------------------
# Asking somebody to grade themselves on something a string comparison can
# settle invites the kindest possible marking at exactly the wrong moment.
QQ = f"Which keyword defines a function in Python? [{stamp}]"
q = A.post("/api/recall/add", json={"kind": "quiz", "prompt": QQ,
                                    "expect": "def"}).json()["item"]["id"]
db = m.SessionLocal()
row = db.get(m.Recall, q)
row.due_at = m.now() - m.dt.timedelta(days=1)
db.commit()
db.close()
w = A.post("/api/recall/answer",
           json={"id": q, "attempt": "lambda", "verdict": "got"}).json()
ck("a wrong quiz answer is marked wrong however it is reported",
   w["verdict"] == "missed" and w["graded"] is True, str(w.get("verdict")))
ck("and it comes back tomorrow", w["next_in_days"] == 1)
db = m.SessionLocal()
row = db.get(m.Recall, q)
row.due_at = m.now() - m.dt.timedelta(days=1)
db.commit()
db.close()
g = A.post("/api/recall/answer",
           json={"id": q, "attempt": "  DEF  ", "verdict": "missed"}).json()
ck("a right one is right, whatever the spacing or case",
   g["verdict"] == "got", str(g.get("verdict")))

# ---- it is yours ---------------------------------------------------------
B = TestClient(m.app)
B.post("/api/auth/signup", json={"name": "Other", "email": f"oth{stamp}@example.com",
                                 "password": "OtherPass123!"})
ck("somebody else cannot answer your card",
   B.post("/api/recall/answer",
          json={"id": rid, "attempt": "x", "verdict": "got"}).status_code == 404)
ck("nor see it", all(i["id"] != rid for i in
                     B.get("/api/recall/due").json().get("items", [])))
ck("nor delete it", B.delete(f"/api/recall/{rid}").status_code == 404)
ck("signed out, there is nothing to revise",
   TestClient(m.app).get("/api/recall/due").status_code == 401)

# ---- and you can drop one you know ---------------------------------------
ck("you can stop being asked", A.delete(f"/api/recall/{rid}").status_code == 200)
ck("and then it is gone", A.delete(f"/api/recall/{rid}").status_code == 404)

# ---- the schedule itself --------------------------------------------------
ck("the intervals widen", m.RECALL_DAYS == sorted(m.RECALL_DAYS),
   str(m.RECALL_DAYS))
ck("the first gap is short, because that is where forgetting happens",
   m.RECALL_DAYS[0] <= 2, str(m.RECALL_DAYS[0]))
ck("strength cannot index past the table",
   m._recall_due_in(99) == m.RECALL_DAYS[-1]
   and m._recall_due_in(-5) == m.RECALL_DAYS[0])

print("\n".join("PASS " + x for x in P))
print("\n".join("FAIL " + x for x in F))
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
