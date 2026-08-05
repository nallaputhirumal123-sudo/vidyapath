"""The fence between two institutions, and the list of where answers come from.

`AskCache` serves one person's stored answer to the next person who asks
something similar. That is the whole cost model — the first person to ask
what a foreign key is pays for it and nobody after them does — and it is
also, left unscoped, a machine for moving one school's questions into
another school's session. The question text IS the cache key. There is no
version of this where a shared key does not mean shared questions.

So the tests that matter here are boundary tests. Two schools ask the same
thing; each pays for it, each gets its own row, and neither can reach the
other's. A public learner asks it; they get neither. Nothing about that is
visible when it breaks — the wrong answer is a correct answer, served to
somebody who should not have been able to reach it — which is exactly why
it is asserted rather than reasoned about.

The other half is the source registry, and one assertion carries it: every
source used to source answer material is open. Adding a closed one takes a
deliberate edit to a test that says in words why not.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"   # local test database; refused on a deployment
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"

import craxlearn as cl                             # noqa: E402
import dalia                                       # noqa: E402
import main                                        # noqa: E402

PASS = FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {name}" + (f"  ({detail})" if detail else ""))
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


# ---- scopes ------------------------------------------------------------
print("\nScopes")
check("somebody on their own account is public",
      cl.scope_of(None, in_institution=False) == "public")
check("a school learner is their school",
      cl.scope_of(7, in_institution=True) == "school:7")
check("two schools are two scopes",
      cl.scope_of(7, in_institution=True) != cl.scope_of(8, in_institution=True))

# The failure that matters is a school's row landing in the public pool, so
# every way of not knowing has to land on the private side.
check("an institution learner with no school id is still not public",
      cl.scope_of(0, in_institution=True) == "school:0")
check("nor with a missing one", cl.scope_of(None, in_institution=True)
      == "school:0")
check("nor with a nonsense one", cl.scope_of("../public", in_institution=True)
      == "school:0")
check("nor with a negative one", cl.scope_of(-4, in_institution=True)
      == "school:0")

check("public is not an institution", not cl.is_institution("public"))
check("a school is", cl.is_institution("school:3"))
check("and nothing is public by omission", not cl.is_institution(None))
check("the school id reads back", cl.school_id_of("school:12") == 12)
check("and is zero for the public pool", cl.school_id_of("public") == 0)

# ---- keys --------------------------------------------------------------
print("\nKeys")
k_pub = cl.key("public", "board", "osmosis")
k_a = cl.key("school:1", "board", "osmosis")
k_b = cl.key("school:2", "board", "osmosis")
check("the same question makes three different keys",
      len({k_pub, k_a, k_b}) == 3, f"{k_pub} / {k_a} / {k_b}")
check("the scope comes first", k_a.startswith("school:1|"), k_a)
check("a key reads its own scope back",
      cl.scope_from_key(k_a) == "school:1", cl.scope_from_key(k_a))
check("a key written before any of this existed reads as public",
      cl.scope_from_key("board|intermediate|osmosis") == "public")
check("and so does an empty one", cl.scope_from_key("") == "public")

# A scope that could be forged out of question text would put the whole
# thing back where it started.
check("a question cannot forge a scope",
      cl.scope_from_key(cl.key("public", "ask", "school:9 what is osmosis"))
      == "public")

# ---- what gets recorded -------------------------------------------------
print("\nRecords")
check("a question is trimmed, not transformed",
      cl.redact("  what   is  osmosis  ") == "what is osmosis")
check("a very long one is cut", len(cl.redact("x" * 900)) == cl.MAX_RECORD)
check("an empty one stays empty", cl.redact("") == "")
check("None is not a question", cl.redact(None) == "")

# ---- the source registry ------------------------------------------------
print("\nSources")
# The assertion this file exists for. Everything that supplies the substance
# of an answer — a fact, a structure, a picture, the numbers behind a 2D or
# 3D view, the data a sandbox runs against — has to be a source anybody can
# go and check. If this fails, do not relax it: either the new source is open
# and the flag is wrong, or it is closed and it does not belong in sourcing.
closed_sourcing = [s["id"] for s in cl.sourcing() if not s["open"]]
check("every sourcing source is open", not closed_sourcing,
      ", ".join(closed_sourcing) or "none")
check("there are some", len(cl.sourcing()) >= 5, str(len(cl.sourcing())))

for s in cl.SOURCES:
    check(f"{s['id']} says what it is used for",
          len(s.get("used_for", "")) > 30)
    check(f"{s['id']} names a licence", bool(s.get("licence")))
    check(f"{s['id']} has a known role",
          s["role"] in ("sourcing", "computation"), s["role"])

# A registry that only lists the flattering entries is not a registry.
check("the closed dependency is listed, not hidden",
      any(s["id"] == "wolfram" for s in cl.SOURCES))
check("and it is marked closed",
      not next(s for s in cl.SOURCES if s["id"] == "wolfram")["open"])
check("and it is not a source of answers",
      next(s for s in cl.SOURCES if s["id"] == "wolfram")["role"]
      == "computation")
reg = cl.public_registry()
check("the registry shows open entries first",
      [s["open"] for s in reg["sources"]] == sorted(
          [s["open"] for s in reg["sources"]], reverse=True))
check("and counts honestly",
      reg["open_count"] == sum(1 for s in cl.SOURCES if s["open"])
      and reg["total"] == len(cl.SOURCES))
check("the tutor is told which product she is on", dalia.PRODUCT == cl.NAME)
check("and says so in the prompt", cl.NAME in dalia.system(level="Class 9"))

# ---- the fence, end to end ----------------------------------------------
# Two schools and a member of the public all ask the same thing. Everything
# below is about what each of them can and cannot reach.
print("\nThe fence")
import time                                        # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

main.Base.metadata.create_all(bind=main.engine)
main.send_email = lambda *a, **k: None
main.ASK_ENABLED = True

CALLS = {"n": 0}


async def _fake_ai(prompt, tokens, **kw):
    CALLS["n"] += 1
    return f"Osmosis explained, answer number {CALLS['n']}."


_real_ai = main._ai_text
main._ai_text = _fake_ai

stamp = int(time.time())
db = main.SessionLocal()

# Two schools, each with a classroom, each with one enrolled learner.
people = {}
for tag, school_name in (("a", f"St Anne's {stamp}"), ("b", f"Ridge {stamp}")):
    sc = main.School(name=school_name, city="Hyderabad", country="India")
    db.add(sc)
    db.commit()
    kl = main.Klass(name=f"9-A {tag}", join_code=f"J{tag.upper()}{stamp}"[:16],
                    teacher_id=1, school=school_name, school_id=sc.id)
    db.add(kl)
    db.commit()
    people[tag] = {"school": sc, "class": kl}

clients = {}
for tag in ("a", "b", "pub"):
    c = TestClient(main.app)
    email = f"cl{tag}{stamp}@example.com"
    r = c.post("/api/auth/signup", json={"name": f"Learner {tag}",
                                         "email": email,
                                         "password": "CraxlearnPass123!"})
    check(f"learner {tag} signs up", r.status_code == 200, str(r.status_code))
    u = db.query(main.User).filter(main.User.email == email).first()
    u.plan = "pro"
    u.plan_expires = main.now() + main.dt.timedelta(days=30)
    if tag in people:
        db.add(main.ClassMember(class_id=people[tag]["class"].id, user_id=u.id))
    db.commit()
    clients[tag] = {"c": c, "user": u}

check("a school learner is scoped to their school",
      main._scope_of(db, clients["a"]["user"])
      == f"school:{people['a']['school'].id}",
      main._scope_of(db, clients["a"]["user"]))
check("two school learners are scoped apart",
      main._scope_of(db, clients["a"]["user"])
      != main._scope_of(db, clients["b"]["user"]))
check("somebody with no class is public",
      main._scope_of(db, clients["pub"]["user"]) == "public")

QUESTION = f"explain osmosis to me {stamp}"
answers, before = {}, {}
for tag in ("a", "b", "pub"):
    before[tag] = CALLS["n"]
    r = clients[tag]["c"].post("/api/ask/talk",
                               json={"said": QUESTION, "subject": "Biology",
                                     "level": "Class 9"})
    check(f"learner {tag} gets an answer", r.status_code == 200, r.text[:120])
    answers[tag] = r.json().get("say", "")
    check(f"and it was not served from anyone else's cache",
          r.json().get("cached") is False, str(r.json().get("cached")))
    check(f"so learner {tag}'s school paid for it",
          CALLS["n"] == before[tag] + 1, str(CALLS["n"]))

check("three askers, three different stored answers",
      len(set(answers.values())) == 3, str(answers))

# And within one school it still pools, which is the point of scoping it to
# the school rather than to the person.
n = CALLS["n"]
r = clients["a"]["c"].post("/api/ask/talk",
                           json={"said": QUESTION, "subject": "Biology",
                                 "level": "Class 9"})
check("the same school asking again is free", r.json().get("cached") is True,
      str(r.json().get("cached")))
check("and costs no model call", CALLS["n"] == n, str(CALLS["n"]))
check("and gets its own school's answer", r.json().get("say") == answers["a"])

# The rows themselves.
rows = db.query(main.AskCache).filter(
    main.AskCache.question == QUESTION).all()
check("one cache row per scope", len(rows) == 3, str(len(rows)))
check("each row records which pool it is in",
      sorted(r.scope for r in rows) == sorted(
          ["public", f"school:{people['a']['school'].id}",
           f"school:{people['b']['school'].id}"]),
      str(sorted(r.scope for r in rows)))
check("and nobody had to remember to set that",
      all(r.scope == cl.scope_from_key(r.qkey) for r in rows))

# ---- what an institution can read ---------------------------------------
print("\nWhat an institution can read")
r = clients["a"]["c"].get("/api/craxlearn/activity")
check("a learner can read their own history", r.status_code == 200,
      str(r.status_code))
mine = r.json()
check("and it is their own view", mine.get("view") == "mine", str(mine.get("view")))
check("with the question in it",
      any(QUESTION in t["text"] for t in mine.get("topics") or []),
      str(mine.get("topics"))[:200])

# The head teacher of school A.
head = TestClient(main.app)
hemail = f"head{stamp}@example.com"
head.post("/api/auth/signup", json={"name": "Head Teacher",
                                    "email": hemail,
                                    "password": "CraxlearnPass123!"})
hu = db.query(main.User).filter(main.User.email == hemail).first()
db.add(main.TeacherAccess(user_id=hu.id, school=people["a"]["school"].name,
                          school_id=people["a"]["school"].id, role="head"))
db.commit()

r = head.get("/api/craxlearn/activity")
check("the head teacher gets a school view", r.json().get("view") == "school",
      str(r.json().get("view")))
sch = r.json()
check("of their own school", sch.get("scope")
      == f"school:{people['a']['school'].id}", str(sch.get("scope")))
check("showing what has been asked",
      any(QUESTION in t["text"] for t in sch.get("topics") or []),
      str(sch.get("topics"))[:200])
check("with a count rather than a name",
      all("user" not in t and "email" not in t
          for t in sch.get("topics") or []), str(sch.get("topics"))[:200])

# The whole point. School A's head must not be able to see that school B
# asked anything at all.
b_only = f"school b private question {stamp}"
clients["b"]["c"].post("/api/ask/talk", json={"said": b_only,
                                              "subject": "Biology",
                                              "level": "Class 9"})
r = head.get("/api/craxlearn/activity")
texts = [t["text"] for t in r.json().get("topics") or []]
check("and never the other school's questions",
      not any(b_only in t for t in texts), str(texts)[:200])
check("nor its learner count",
      r.json().get("learners", 0)
      <= db.query(main.func.count(main.func.distinct(main.LearnRecord.user_id)))
      .filter(main.LearnRecord.scope
              == f"school:{people['a']['school'].id}").scalar(),
      str(r.json().get("learners")))

# Clearing is mine and only mine.
n_before = (db.query(main.func.count(main.LearnRecord.id))
              .filter(main.LearnRecord.scope
                      == f"school:{people['a']['school'].id}").scalar())
r = head.delete("/api/craxlearn/activity")
check("a teacher can clear their own history", r.status_code == 200)
n_after = (db.query(main.func.count(main.LearnRecord.id))
             .filter(main.LearnRecord.scope
                     == f"school:{people['a']['school'].id}").scalar())
check("and it does not wipe the school's", n_after == n_before,
      f"{n_before} -> {n_after}")

# ---- the registry is readable without an account ------------------------
print("\nThe registry")
anon = TestClient(main.app)
r = anon.get("/api/craxlearn/sources")
check("anyone can read where the answers come from", r.status_code == 200,
      str(r.status_code))
body = r.json()
check("it names the product", body.get("product") == cl.NAME)
check("it states the policy", "open sources" in body.get("policy", ""))
check("and lists every source", len(body.get("sources") or []) == len(cl.SOURCES))

main._ai_text = _real_ai
db.close()

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
