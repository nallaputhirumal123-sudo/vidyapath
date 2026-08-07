"""A test somebody could not pass by having skimmed the page.

"Learning quizzes are basic. Make them learn properly, not half half."

Fair. The test had three kinds — choice, blank, match — and all three are
RETRIEVAL. Recognise the term, recall the word, pair the two. Nothing asked
the learner to DO anything with what they had just been told, so a careful
reader who understood none of it passed.

Two kinds are added, and the important one is `apply`: a situation the lesson
did not literally describe. That is the only question here that distinguishes
having learnt something from having read it. `order` is the second — a
process put back into sequence, because knowing all five words of gradient
descent in the wrong order is not knowing gradient descent.

And the mix is a requirement in the prompt rather than a suggestion, because
a model asked for "a variety" returns four multiple-choice questions and one
gap-fill, every time.

The other half of this file is a fault found while testing it, and it is the
larger one: the quiz feature had never run at all. quizui.js is a separate
<script> and reached for `window.SB` and `window.ASK`, which do not exist —
a top-level `const` in a classic script makes a scope binding and not a
property of window. So "Test me on this" found no lesson, said "Ask something
first", and returned. Every time, for everybody.
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import quiz                                         # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX = io.open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
UI = io.open(os.path.join(ROOT, "quizui.js"), encoding="utf-8").read()
P, F = [], []


def ck(n, c, d=""):
    print(("PASS " if c else "FAIL ") + n + (f" — {d}" if d else ""),
          flush=True)
    (P if c else F).append(n)


print("\nthe feature was never reachable")
# The whole thing, silently doing nothing since it was written.
ck("the page publishes its state for the quiz module",
   "window.ASK = ASK;" in IDX and "window.SB = SB;" in IDX,
   "a top-level const is not a property of window")
ck("and the module still looks somewhere explicit",
   "window.SB" in UI and "window.ASK" in UI,
   "one file reaching into another's lexical scope is what broke, silently")

print("\nfive kinds, not three")
for k in ("choice", "blank", "match", "order", "apply"):
    ck(f"{k} is a kind", k in quiz.KINDS)
ck("apply is asked for FIRST in the prompt",
   quiz.PROMPT.index('"apply"') < quiz.PROMPT.index('"choice"'),
   "it is the only one that tests transfer rather than retrieval")
ck("the mix is stated as a requirement",
   "a requirement, not a" in quiz.PROMPT and "suggestion" in quiz.PROMPT,
   'a model asked for "a variety" returns four choice questions')
ck("and the test is longer than five questions",
   "EIGHT TO TEN QUESTIONS" in quiz.PROMPT and quiz.MAX_QUESTIONS >= 10,
   str(quiz.MAX_QUESTIONS))

print("\nan order question is built and marked on the stored sequence")
q = quiz.clean({"questions": [
    {"kind": "order", "q": "Put these in order",
     "steps": ["Predict", "Measure the error", "Find the slope",
               "Step against the slope"], "why": "w"}]})
ck("it survives cleaning", len(q) == 1 and q[0]["kind"] == "order", str(q))
ck("the steps are kept in the order given",
   q[0]["steps"][0] == "Predict" and q[0]["steps"][-1] == "Step against the slope",
   "the page shuffles for display; the stored order IS the answer")
right = quiz.mark(q, {"0": q[0]["steps"]})
ck("the right sequence scores", right["score"] == 1, str(right))
back = quiz.mark(q, {"0": list(reversed(q[0]["steps"]))})
ck("a reversed sequence does not", back["score"] == 0, str(back))
part = quiz.mark(q, {"0": q[0]["steps"][:2]})
ck("nor a half-finished one", part["score"] == 0, str(part))

print("\nand a sequence too short to be one is refused")
ck("two steps is a pair, not an order",
   quiz.clean({"questions": [{"kind": "order", "q": "x",
                              "steps": ["a", "b"], "why": "w"}]}) == [],
   "a malformed question is never shown; one fewer costs nothing")
ck("nor may a step repeat",
   quiz.clean({"questions": [{"kind": "order", "q": "x",
                              "steps": ["a", "b", "a"], "why": "w"}]}) == [],
   "an ambiguous position cannot be marked")

print("\nan apply question is a choice underneath, and stays distinguishable")
a = quiz.clean({"questions": [
    {"kind": "apply", "q": "Loss falls, validation rises. What now?",
     "options": ["Stop early", "Raise the rate", "Add epochs", "Drop it"],
     "correct": "Stop early", "why": "overfitting"}]})
ck("it survives cleaning", len(a) == 1 and a[0]["kind"] == "apply", str(a))
ck("the answer is resolved from TEXT, not a number",
   a[0]["answer"] == 0, str(a[0].get("answer")),)
ck("and it marks like a choice", quiz.mark(a, {"0": 0})["score"] == 1)
ck("kept apart from choice so the mix can be enforced",
   a[0]["kind"] != "choice",
   "merged, a test becomes five recognition questions in different hats")

print("\nthe page can draw both")
ck("apply is drawn as a choice",
   'q.kind === "choice" || q.kind === "apply"' in UI)
ck("order has its own renderer", 'q.kind === "order"' in UI)
ck("its display order is shuffled away from the answer",
   "hash(a + i) - hash(b + i)" in UI)
ck("but deterministically, so it does not move under somebody's hand",
   "function hash(str)" in UI,
   "reshuffling on every repaint is a puzzle that changes as you solve it")
ck("tapping a step twice takes it back out",
   "if (at >= 0) cur.splice(at, 1); else cur.push(val);" in UI)

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
