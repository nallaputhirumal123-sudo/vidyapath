"""Three level buttons, three different lessons — and one wait, not two.

**The levels were the same answer three times.** The picker offers Beginner,
Intermediate and Advanced, and the prompt said "the learner's level is:
Advanced" and, further down, "language matched to the stated level". A model
given that writes one lesson with slightly different adjectives. A level is
not a tone: it is a decision about what may be assumed, how far to go, and
what to leave out, so it is written here as those decisions.

**And the answer waited for a second model.** Asking a question made two
calls in a row — write the lesson, then read it back looking for errors —
and BOTH finished before anything reached the screen. That is where the ten
seconds went: the answer existed after about five of them and sat in the
server while another model read it.

The review is worth keeping; it is the pass that catches a confident wrong
number before it is cached and served to everybody. It just does not have to
be in the way. The lesson goes up as soon as it exists, the review is its
own request, and the findings land on the lesson when they arrive.

**The caching rule survives that move, which is the part that needed care.**
Caching is what turns one wrong answer into everybody's wrong answer, and
the row is written before the review runs now — so a critical finding
DELETES the cached row rather than only marking the copy on one screen.
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("DATABASE_URL", "sqlite:///./vidyapath.db")
os.environ.setdefault("ALLOW_SQLITE", "1")

import main                                             # noqa: E402
import inspect                                          # noqa: E402

IDX = io.open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
P, F = [], []


def ck(name, cond, why=""):
    print(("PASS " if cond else "FAIL ") + name + (" — " + why if why else ""),
          flush=True)
    (P if cond else F).append(name)


print("\nthe three levels ask for three different lessons")
PROMPTS = {lv: main._ask_prompt("what is a derivative", "Maths", lv)
           for lv in ("Beginner", "Intermediate", "Advanced")}
ck("they are not the same prompt", len(set(PROMPTS.values())) == 3,
   "three buttons and one answer is three buttons that do nothing")
for lv in PROMPTS:
    ck(lv + " says what it means",
       ("LEVEL: " + lv.upper()) in PROMPTS[lv])

# The differences that actually change a lesson, rather than its adjectives.
ck("beginner defines its terms",
   "Define every term the first time it appears" in PROMPTS["Beginner"])
ck("intermediate does not re-teach the grounding",
   "do not re-teach it" in PROMPTS["Intermediate"])
ck("advanced assumes the vocabulary",
   "are known and are not explained" in PROMPTS["Advanced"])
ck("and advanced is depth rather than more words",
   "depth, not breadth" in PROMPTS["Advanced"])
ck("an unknown level still gets a lesson",
   "LEVEL: INTERMEDIATE" in main._ask_prompt("q", "s", "Wizard"),
   "a level nobody offers must not produce a prompt with a hole in it")

print("\nand the answer no longer waits for the second model")
ASK = inspect.getsource(main.ask_axle) if hasattr(main, "ask_axle") else ""
if not ASK:
    # The route is registered by decorator; find it by its own text.
    src = io.open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
    ASK = src.split('qkey = _cl.key(scope, "ask"')[1].split("\n@app.")[0]
ck("the ask route does not review before answering",
   "await _review_lesson(" not in ASK,
   "both calls finished before anything reached the screen, which is where "
   "the ten seconds went")
ck("and says where it went instead", "/api/ask/review" in ASK)

REV = inspect.getsource(main.ask_review)
ck("the review has a route of its own", "async def ask_review" in REV)
ck("it never fails the caller",
   "return {\"findings\": [], \"state\": \"unchecked\"}" in REV,
   "an unavailable checker must not turn a lesson that is already on the "
   "screen into an error message")
ck("a critical finding removes the cached answer",
   "db.delete(row)" in REV,
   "caching is what turns one wrong answer into everybody's wrong answer, "
   "and the row is written before this runs now")
ck("and it is the same question's row that goes",
   '_cl.key(_scope_of(db, user), "ask"' in REV)

print("\nthe page shows the lesson first and marks it after")
ck("the review is asked for after the lesson is drawn",
   IDX.index("askShow(res.lesson);") < IDX.index('"/api/ask/review"'),
   "asked for before it, this would be the same wait wearing a different "
   "hat")
ck("it is not awaited", ".then(rev =>" in IDX)
ck("a stale answer is not marked",
   "if(ASK.question !== q || !ASK.lesson) return;" in IDX,
   "by the time it lands the learner may have asked something else")
ck("and a cached answer is not reviewed again",
   "if(!res.cached && res.lesson){" in IDX,
   "it was reviewed when it was written; doing it again is a model call "
   "for an answer nobody is waiting on")

print("\nand the board stops asking for something that was removed")
ck("the welcome line does not ask for a subject",
   "Pick a subject" not in IDX,
   "the subject chooser was taken out — it asked a learner to classify "
   "their question before they were allowed to ask it")
ck("it still says who is speaking", "Namaste! I am Axle." in IDX)

print("\n" + ("PASSED %d   FAILED %d" % (len(P), len(F))))
if F:
    for name in F:
        print("  FAILED: " + name)
    sys.exit(1)
