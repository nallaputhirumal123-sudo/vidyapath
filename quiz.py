"""Questions built from a lesson, in the three shapes that test different things.

A lesson ends and nothing checks whether any of it landed. The course builder
has a multiple-choice validator, but it is nested inside the course cleaner and
reachable from nowhere else, so every other explanation on the site — the
board, a scan, a PDF — finishes and stops.

Five kinds, because they fail differently and that is the point:

  choice    four options, one right. Tests recognition. Cheap to answer and
            cheap to guess: one in four is right by accident.
  blank     a sentence with a word removed. Tests recall, which is harder,
            and cannot be guessed at all.
  match     pairs to join. Tests whether the relationships were understood
            rather than the words memorised — somebody can recognise every
            term on the list and still not know which goes with which.
  order     steps put back into sequence. Tests whether the PROCESS was
            followed or only its vocabulary collected: gradient descent has
            an order, and knowing all five words in the wrong order is not
            knowing gradient descent.
  apply     a situation the lesson did not literally describe, with four
            outcomes. Tests transfer, which is the only one of these that
            distinguishes having learnt something from having read it.

The first three were the whole test, and a test made of them is passable by
somebody who has read the page carefully and understood none of it. That is
what "the quizzes are basic" means and it is a fair description: recognition,
recall and pairing are all retrieval. Nothing asked the learner to DO
anything with what they had just been told.

The mix is enforced rather than suggested, because a model asked for "a
variety" returns four multiple-choice questions and one gap-fill every time.

The rule that matters is the same one that fixed the CSS course: the correct
answer is given as TEXT and the index is worked out here. Asked for a
position, a model counts wrong often enough to mark right answers wrong while
explaining, in the same breath, why they were right.

Nothing here calls a model or the network. It takes what a model returned and
rebuilds it into a shape the page can render, dropping anything that does not
survive — a malformed question is not shown, because a broken question in a
test is worse than one fewer question.
"""
import re

# Eight was the cap and five was what came back. A lesson worth
# twenty minutes deserves more than five questions, and the floor
# matters more than the ceiling: a two-question test tells the
# learner nothing and tells us less.
MAX_QUESTIONS = 12
MIN_QUESTIONS = 6
MAX_STEPS = 6
MAX_OPTIONS = 4
MAX_PAIRS = 6

KINDS = ("choice", "blank", "match", "order", "apply")


def _txt(v, n):
    return " ".join(str(v or "").split())[:n]


def _norm(t):
    """An option reduced to what it says, for comparing."""
    return " ".join(str(t or "").lower().split()).strip(" .;:!?—-")


def match_option(value, options):
    """Which option is this text? None if it is not exactly one of them.

    By text, never by index. A model asked for "the third one" counts wrong
    often enough to mark a right answer wrong, and it does it while
    explaining correctly why that answer is right — so the failure looks like
    a bug in the marking rather than in the question.
    """
    want = _norm(value)
    if not want:
        return None
    norm = [_norm(o) for o in options]
    hits = [i for i, o in enumerate(norm) if o and o == want]
    return hits[0] if len(hits) == 1 else None


def _choice(q):
    """Four options, one right."""
    opts = [_txt(o, 200) for o in (q.get("options") or [])[:MAX_OPTIONS]]
    opts = [o for o in opts if o]
    if len(opts) < 2:
        return None
    if len(set(_norm(o) for o in opts)) != len(opts):
        return None                      # two identical options is not a test
    a = match_option(q.get("correct"), opts)
    if a is None:
        return None                      # no index fallback: text or nothing
    return {"kind": "choice", "q": _txt(q.get("q"), 300),
            "options": opts, "answer": a, "why": _txt(q.get("why"), 300)}


_GAP = re.compile(r"_{2,}|\[\s*blank\s*\]|\.{3,}", re.I)


def _blank(q):
    """A sentence with a word taken out.

    The sentence must actually contain a gap. A model sometimes returns the
    complete sentence and the answer separately, which renders as a question
    with nothing to fill in — worse than no question, because the reader
    looks for the gap and blames themselves.
    """
    text = _txt(q.get("text") or q.get("q"), 300)
    answer = _txt(q.get("answer") or q.get("correct"), 80)
    if not text or not answer:
        return None
    if not _GAP.search(text):
        # Make the gap ourselves if the answer appears in the sentence.
        pat = re.compile(re.escape(answer), re.I)
        if not pat.search(text):
            return None
        text = pat.sub("_____", text, count=1)
    # The answer must not still be sitting in the sentence beside the gap.
    if re.search(re.escape(answer), _GAP.sub(" ", text), re.I):
        return None
    return {"kind": "blank", "text": text, "answer": answer,
            "why": _txt(q.get("why"), 300)}


def _match(q):
    """Pairs to join up."""
    pairs = []
    for p in (q.get("pairs") or [])[:MAX_PAIRS]:
        if isinstance(p, dict):
            left, right = _txt(p.get("left"), 120), _txt(p.get("right"), 160)
        elif isinstance(p, (list, tuple)) and len(p) >= 2:
            left, right = _txt(p[0], 120), _txt(p[1], 160)
        else:
            continue
        if left and right:
            pairs.append({"left": left, "right": right})
    if len(pairs) < 2:
        return None
    # Two identical left-hand terms make the question unanswerable, and two
    # identical right-hand ones make a wrong answer indistinguishable from a
    # right one.
    if len(set(_norm(p["left"]) for p in pairs)) != len(pairs):
        return None
    if len(set(_norm(p["right"]) for p in pairs)) != len(pairs):
        return None
    return {"kind": "match", "q": _txt(q.get("q"), 300) or "Join each to its pair",
            "pairs": pairs, "why": _txt(q.get("why"), 300)}


def _order(q):
    """Steps to put back into sequence.

    The right answer is the order they are GIVEN in, and the page shuffles
    them for display — so the model never has to number anything, which is
    the same rule that fixed `choice`. Asked for positions, a model produces
    a list that contradicts its own explanation often enough to mark a right
    answer wrong.
    """
    steps = [_txt(x, 120) for x in (q.get("steps") or [])]
    steps = [x for x in steps if x]
    # Fewer than three is not a sequence, it is a pair.
    if len(steps) < 3 or len(steps) > MAX_STEPS:
        return None
    if len({_norm(x) for x in steps}) != len(steps):
        return None
    return {"kind": "order", "q": _txt(q.get("q"), 240) or "Put these in order",
            "steps": steps, "why": _txt(q.get("why"), 240)}


def _apply(q):
    """A situation the lesson did not literally describe.

    Structurally a `choice`, and kept apart from it on purpose: the two are
    scored the same and are not the same question. Merging them is how a test
    ends up as five recognition questions wearing different labels — the
    model is told how many of each to write, and it can only be held to that
    if the two are distinguishable.
    """
    built = _choice(q)
    if not built:
        return None
    if not built.get("q"):
        return None
    built["kind"] = "apply"
    return built


def clean(raw):
    """Rebuild a quiz from what a model returned, dropping what will not work.

    A malformed question is never shown. One fewer question costs nothing; a
    question with two identical options, or a gap that is not there, wastes
    somebody's time and makes them distrust the rest of the test.
    """
    if isinstance(raw, dict):
        raw = raw.get("questions") or raw.get("quiz") or []
    if not isinstance(raw, list):
        return []
    out = []
    for q in raw[:MAX_QUESTIONS * 2]:
        if not isinstance(q, dict):
            continue
        kind = str(q.get("kind") or "choice").strip().lower()
        built = {"choice": _choice, "blank": _blank, "order": _order,
                 "apply": _apply,
                 "match": _match}.get(kind, _choice)(q)
        if built:
            out.append(built)
        if len(out) >= MAX_QUESTIONS:
            break
    return out


def mark(questions, answers):
    """Score a set of answers. Pure arithmetic, no model, no network."""
    total = right = 0
    detail = []
    for i, q in enumerate(questions or []):
        given = (answers or {}).get(str(i), (answers or {}).get(i))
        total += 1
        ok = False
        if q.get("kind") == "choice":
            try:
                ok = int(given) == int(q.get("answer"))
            except (TypeError, ValueError):
                ok = False
        elif q.get("kind") == "blank":
            ok = _norm(given) == _norm(q.get("answer"))
        elif q.get("kind") == "apply":
            # Scored as a choice, because that is what it is underneath.
            try:
                ok = int(given) == int(q.get("answer"))
            except (TypeError, ValueError):
                ok = False
        elif q.get("kind") == "order":
            # The stored order IS the answer; the page shuffles for display
            # and sends back the sequence the learner built.
            want = [_norm(x) for x in (q.get("steps") or [])]
            got = [_norm(x) for x in given] if isinstance(given, list) else []
            ok = bool(want) and got == want
        elif q.get("kind") == "match":
            want = {_norm(p["left"]): _norm(p["right"]) for p in q["pairs"]}
            got = {_norm(k): _norm(v) for k, v in (given or {}).items()} \
                if isinstance(given, dict) else {}
            ok = bool(want) and got == want
        right += 1 if ok else 0
        detail.append({"i": i, "correct": ok})
    return {"score": right, "total": total, "detail": detail,
            "passed": total > 0 and right == total}


PROMPT = """Write a test on what this lesson just taught. Not a quick check —
a test somebody could not pass by having skimmed the page.

WRITE EIGHT TO TEN QUESTIONS, and use this mix. It is a requirement, not a
suggestion: a test of five recognition questions is passable by somebody who
understood none of it.

  2-3  "apply"   THE MOST IMPORTANT ONES. A situation the lesson did NOT
                 literally describe, and four outcomes. The learner has to
                 take what they were told and use it somewhere new. Same
                 shape as "choice": four options, one right, given as text.
  1-2  "order"   steps of a process, GIVEN IN THE RIGHT ORDER — the page
                 shuffles them. Use it where the lesson taught a procedure.
                 Three to six steps.
  2-3  "choice"  four options, exactly one right. Recognition.
  1-2  "blank"   a sentence with one word removed, written with _____ where
                 the word was. Recall, and cannot be guessed.
  1-2  "match"   terms and what each goes with. Relationships.

WRITE FOR SOMEBODY WHO WILL BE EXAMINED ON THIS. Ask about the thing the
lesson was FOR, not the sentence it happened to open with. If the lesson gave
a formula, ask them to use it. If it gave a procedure, ask what breaks when a
step is skipped. If it warned about a mistake, build a question where somebody
has made it. A question whose answer is a word lifted from the page is a
question that has tested reading, not learning.

Rules that matter:
- Give "correct" as the option's TEXT, copied out in full. Never a number,
  never a letter, never "the third one".
- Ask about what the lesson actually said. A question needing something it
  did not cover teaches nobody and reads as a mistake.
- The wrong options must be plausible and wrong. An obviously silly option
  turns a four-way question into a two-way one.
- No two options may say the same thing, and in "match" no two terms and no
  two answers may repeat.
- One short sentence in "why" saying why the answer is right.

- In "order", give the steps in the CORRECT order. Do not number them and do
  not shuffle them; the page does that.
- In "why", say why the answer is right in one sentence — and for "apply",
  say which idea from the lesson it rests on.

Reply with ONLY this JSON:
{"questions":[
  {"kind":"apply","q":"A situation the lesson did not describe...",
   "options":["...","...","...","..."],
   "correct":"the winning option copied out in full","why":"..."},
  {"kind":"order","q":"Put these in the order they happen",
   "steps":["first","second","third"],"why":"..."},
  {"kind":"choice","q":"...","options":["...","...","...","..."],
   "correct":"the winning option copied out in full","why":"..."},
  {"kind":"blank","text":"A sentence with _____ removed.",
   "answer":"the missing word","why":"..."},
  {"kind":"match","q":"Join each to its pair",
   "pairs":[{"left":"term","right":"what it goes with"}],"why":"..."}
]}"""
