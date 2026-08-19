"""Three level buttons that became none, and one wait instead of two.

**The levels were the same answer three times.** The picker offered
Beginner, Intermediate and Advanced, and the prompt said "the learner's level
is: Advanced" and, further down, "language matched to the stated level". A
model given that writes one lesson with slightly different adjectives.

The first fix was to write three genuinely different sets of instructions —
what may be assumed, how far to go, what to leave out. They still came back
close enough that nobody using it could tell which chip was lit, and they
were part of the cache key, so one question was paid for three times.

**So the picker is gone.** The evidence was always in the question: "what is
a derivative" and "prove the chain rule from the limit definition" do not
need a chip to tell them apart, and the person asking should not have to
classify themselves before they are allowed to ask. The three named levels
stay in the server for the classroom board, which genuinely knows the class
in front of it.

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


print("\nnobody is asked to classify themselves first")
ck("the level chips are gone from the page",
   'data-ask="level"' not in IDX and "ASK_LEVELS" not in IDX,
   "three chips, three answers too close to tell apart, and three cache "
   "entries for one question")
ck("and nothing is left styling them",
   ".ask-picker{" not in IDX and ".ask-plabel{" not in IDX)
ck("the chip styles the board still uses stay",
   ".ask-chip{" in IDX,
   "the board's trail of topics is built from them")
ck("the page starts with no level",
   'const ASK={subject:"General",level:"",' in IDX,
   'it started as "Class 6-8", from a scheme replaced twice over, matching '
   "none of the chips on screen — so until somebody pressed one, every "
   "question was asked at a level the server had never heard of")

print("\nand the question is read for the level instead")
UNSET = main._ask_prompt("what is a derivative", "Maths", "")
ck("an unstated level says so", "LEVEL: READ IT FROM THE QUESTION" in UNSET)
ck("it is told where to look", "the question itself says more" in UNSET)
ck("and it is the default for anything unrecognised",
   all("LEVEL: READ IT FROM THE QUESTION" in main._ask_prompt("q", "s", lv)
       for lv in (None, "", "Class 6-8", "Wizard")),
   "a stale client sending an old value must not fall into a hole")

print("\nthe named levels stay for the board, which does know its class")
PROMPTS = {lv: main._ask_prompt("what is a derivative", "Maths", lv)
           for lv in ("Beginner", "Intermediate", "Advanced")}
ck("they are still three different prompts", len(set(PROMPTS.values())) == 3)
for lv in PROMPTS:
    ck(lv + " says what it means",
       ("LEVEL: " + lv.upper()) in PROMPTS[lv])
ck("beginner defines its terms",
   "Define every term the first time it appears" in PROMPTS["Beginner"])
ck("advanced assumes the vocabulary",
   "are known and are not explained" in PROMPTS["Advanced"])
ck("a photo question is not pitched differently from a typed one",
   'level: str = Form(default="")' in io.open(
       os.path.join(ROOT, "main.py"), encoding="utf-8").read(),
   "coercing it to Intermediate there would answer the same question two "
   "ways depending on whether it arrived as a picture")

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
