"""How long a lesson should be, decided from the question rather than guessed.

"How can I solve a squared plus b squared" came back as six steps of modular
arithmetic. The prompt had said "2 to 4 steps for a specific question, 7 to 10
for something broad" and left the model to judge which it had — and a model
asked how much to write nearly always writes more, because it answers the
subject rather than the sentence.

The shape of a question is in its words, so it is read here, for nothing, and
the prompt is handed a number. Then the lesson is trimmed to it, because a
number in a prompt is a request and this is the part that makes it true.

Biased towards the shorter answer on purpose. Anybody who wants more can press
Go deeper; anybody given six steps for a one-step question has already
stopped reading.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"   # local test database; refused on a deployment
os.environ["JOBS_ENABLED"] = "0"

import depth                                       # noqa: E402
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


def band(q):
    lo, hi, _ = depth.measure(q)
    return (lo, hi)


# ---- one question, one answer ---------------------------------------
NARROW = [
    "how can I solve a square + b square",   # the one that started this
    "how do I solve x^2 - 5x + 6 = 0",
    "what is a MAC address table",
    "why is the sky blue",
    "what is 5 mod 2",
    "how do I convert 45 degrees to radians",
]
# Against depth's own constants, not against the numbers they happen to
# hold. The judgement being tested is "is this one question or a subject",
# and that is unchanged; the bands themselves were widened deliberately —
# a board a class is taught from is not a search result, and a lesson that
# stopped at four steps left the teacher filling in the rest.
NARROW_BAND = depth.NARROW[:2]
STANDARD_BAND = depth.STANDARD[:2]
BROAD_BAND = depth.BROAD[:2]
for q in NARROW:
    check(f"narrow: {q[:34]!r}", band(q) == NARROW_BAND, str(band(q)))

# ---- a topic with parts ---------------------------------------------
STANDARD = [
    "photosynthesis",
    "how does photosynthesis work",
    "TCP vs UDP",
    "the difference between mitosis and meiosis",
    "the TCP handshake",
]
for q in STANDARD:
    check(f"standard: {q[:32]!r}", band(q) == STANDARD_BAND, str(band(q)))

# ---- a whole subject -------------------------------------------------
BROAD = [
    "networking",
    "everything about kubernetes",
    "a complete introduction to machine learning",
    "the fundamentals of organic chemistry",
    "a roadmap to becoming a data scientist",
]
for q in BROAD:
    check(f"broad: {q[:34]!r}", band(q) == BROAD_BAND, str(band(q)))

# ---- the lens is an explicit request about depth ---------------------
BASE = "aircraft gearbox"
check("'go deeper' asks for more than broad",
      band(BASE + " — go deeper, with the details an expert would want")[1]
      > BROAD_BAND[1],
      "somebody who asks to go deeper is asking past the widest ordinary "
      "answer, not for one of the same size")
check("'one worked example' asks for less",
      band(BASE + " — walk through one concrete worked example end to end")[1]
      < STANDARD_BAND[1])
check("'much more simply' asks for less",
      band(BASE + " — explain much more simply, for a beginner")[1]
      < STANDARD_BAND[1])
check("a follow-up is one specific thing",
      band(BASE + " — specifically: how is backlash measured")[1]
      < STANDARD_BAND[1])

# ---- the instruction that reaches the prompt -------------------------
ins = depth.instruction("how can I solve a square + b square")
check("the instruction names a number",
      "%d to %d steps" % NARROW_BAND in ins, ins[:48])
check("and says why", "one specific question" in ins)
check("the prompt carries it",
      "LENGTH: %d to %d steps" % NARROW_BAND in main._board_prompt(
          "how can I solve a square + b square", "Intermediate"))

# ---- and the lesson is actually held to it ---------------------------
def lesson(n):
    return {"title": "t", "takeaway": "k",
            "steps": [{"t": "step %d" % i} for i in range(n)]}


check("a narrow question is trimmed to its band",
      len(main._trim_to_depth(lesson(NARROW_BAND[1] + 3),
                              NARROW[0])["steps"]) == NARROW_BAND[1])
check("and a standard topic to its own",
      len(main._trim_to_depth(lesson(STANDARD_BAND[1] + 3),
                              "photosynthesis")["steps"]) == STANDARD_BAND[1])
check("a broad question keeps its nine",
      len(main._trim_to_depth(lesson(9),
                              "everything about kubernetes")["steps"]) == 9)
check("a lesson already short enough is untouched",
      len(main._trim_to_depth(lesson(5), "photosynthesis")["steps"]) == 5)
check("the takeaway survives trimming",
      main._trim_to_depth(lesson(9), NARROW[0])["takeaway"] == "k")

# The only diagram must not be lost to a length rule.
L = lesson(6)
L["steps"][5]["sketch"] = {"kind": "plot"}
L = main._trim_to_depth(L, NARROW[0])
check("a picture on a cut step moves to the last kept one",
      bool(L["steps"][-1].get("sketch")), str(len(L["steps"])) + " steps")

# ---- it must never break a lesson ------------------------------------
for junk in (None, {}, {"steps": None}, {"steps": "not a list"},
             {"steps": [None, 5, {"t": "x"}]}, "text", 42):
    try:
        main._trim_to_depth(junk, "photosynthesis")
        check(f"survives {str(junk)[:26]}", True)
    except Exception as e:
        check(f"survives {str(junk)[:26]}", False, f"{type(e).__name__}: {e}")

check("an empty topic still gives a band", band("") == STANDARD_BAND,
      str(band("")))

print(f"\nPASSED {PASS}   FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
