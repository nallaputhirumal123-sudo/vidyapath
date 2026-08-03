"""How much lesson a question actually wants.

The board was told "2 to 4 steps for a specific question, 7 to 10 for
something broad" and left to judge which it had. It judges generously —
"how do I solve a squared plus b squared" came back as six steps of modular
arithmetic — because a model asked to decide how much to write will nearly
always write more, and because it is answering the subject rather than the
sentence.

So the sentence is read here first, and the prompt is given a number instead
of a choice. Reading it needs no cleverness and no model call: the shape of a
question is in its words. "How do I solve X" is one procedure. "Explain
photosynthesis" is a process with parts. "Everything about networking" is a
subject.

Deliberately blunt, and biased towards the smaller answer. Somebody who wants
more can press "Go deeper", which is a button that exists; somebody given six
steps for a one-step question has already stopped reading.
"""
import re

# The three sizes, as (min_steps, max_steps, name).
NARROW = (2, 4, "narrow")
STANDARD = (4, 7, "standard")
BROAD = (7, 10, "broad")

# ---------------------------------------------------------------------------
# What makes a question narrow: it names one thing and asks one thing of it.
# ---------------------------------------------------------------------------
_ONE_THING = re.compile(
    r"^\s*(?:how (?:do|can|would) (?:i|you|we)|how to|what is|what's|"
    r"what are|why is|why does|when (?:do|does|should)|which|"
    r"is |are |does |do |can |should |solve|calculate|compute|find|prove|"
    r"convert|simplify|derive|evaluate)\b", re.I)

# A concrete instance rather than a class of things: numbers, a formula, a
# specific command, a named case.
_INSTANCE = re.compile(
    r"[0-9]|[+\-*/^=]|\b(this|that|my|the following|given|these)\b", re.I)

# ---------------------------------------------------------------------------
# What makes a question broad: it asks for a field, or for everything in one.
# ---------------------------------------------------------------------------
_BROAD = re.compile(
    r"\b(everything|all (?:about|of|the)|complete|comprehensive|full|"
    r"introduction to|overview of|guide to|from scratch|end to end|"
    r"fundamentals|basics of|master|learn (?:about )?(?:the )?whole|"
    r"course|syllabus|curriculum|roadmap|deep dive|in depth|"
    r"architecture|ecosystem|landscape|history of)\b", re.I)

# Fields, as opposed to things inside them. A question that is only a field
# name is asking for the field.
_FIELD = re.compile(
    r"^\s*(?:the\s+)?(?:networking|programming|chemistry|physics|biology|"
    r"mathematics|maths|history|economics|medicine|law|engineering|"
    r"machine learning|artificial intelligence|data science|"
    r"cyber ?security|cloud computing|kubernetes|devops|statistics|"
    r"calculus|algebra|geometry|literature|philosophy|psychology|"
    r"accounting|finance|marketing|linguistics|genetics|astronomy)\s*$",
    re.I)

# Comparisons and processes sit in the middle: real structure, bounded scope.
_STRUCTURED = re.compile(
    r"\b(vs\.?|versus|compared to|difference between|how does .* work|"
    r"how .* works|process of|cycle|mechanism|lifecycle|pipeline|"
    r"workflow|stages|phases|steps in)\b", re.I)

# The lens suffixes the board appends. They change the depth wanted, and they
# are instructions rather than part of the question.
_LENS_DEEPER = re.compile(r"go deeper|details an expert", re.I)
_LENS_SIMPLER = re.compile(r"much more simply|for a beginner", re.I)
_LENS_ONE = re.compile(r"one concrete worked example|specifically:", re.I)


def subject_of(topic):
    """The question without the tutoring instruction appended to it."""
    t = str(topic or "")
    for sep in ("—", " - ", " – "):
        if sep in t:
            t = t.split(sep)[0]
    return " ".join(t.split()).strip(" -—:,.?!")


def measure(topic):
    """How many steps this question wants, as (low, high, why).

    `why` is a short phrase naming the reason, which goes into the prompt so
    the instruction reads as a judgement rather than an arbitrary number.
    """
    full = str(topic or "")
    q = subject_of(full)
    words = q.split()

    # The lens overrides, because it is an explicit request about depth.
    if _LENS_ONE.search(full):
        return (2, 4, "they asked for one specific thing")
    if _LENS_DEEPER.search(full):
        return (5, 8, "they asked to go deeper")
    if _LENS_SIMPLER.search(full):
        return (2, 4, "they asked for it much more simply")

    if not q:
        return STANDARD[0], STANDARD[1], "no topic given"

    if _BROAD.search(q) or _FIELD.match(q):
        return BROAD[0], BROAD[1], "they asked for a whole subject"

    # A short question naming one thing, especially with a number or a
    # formula in it, is one answer and not a syllabus.
    if _ONE_THING.match(q) and len(words) <= 14:
        if _INSTANCE.search(q) or len(words) <= 8:
            return NARROW[0], NARROW[1], "one specific question"
        return (3, 5, "a single question, stated generally")

    if _STRUCTURED.search(q):
        return STANDARD[0], STANDARD[1], "a process with parts"

    # A bare noun phrase — "photosynthesis", "the TCP handshake" — is a topic
    # with structure, which is the middle case and the commonest one.
    if len(words) <= 3:
        return STANDARD[0], STANDARD[1], "a topic with structure"
    if len(words) >= 18:
        return BROAD[0], BROAD[1], "a long question covering ground"
    return STANDARD[0], STANDARD[1], "a topic with structure"


def instruction(topic):
    """The sentence to put in the prompt, naming a number rather than a
    range of judgement."""
    lo, hi, why = measure(topic)
    return (
        f"LENGTH: {lo} to {hi} steps. This was read as {why}, so that is the "
        f"size of the answer. Do not exceed {hi} steps. Stop when the "
        f"question is answered — length is not thoroughness when none of it "
        f"was asked for, and anybody who wants more can press Go deeper."
    )


# The output budget that matches the length. Generation time is dominated by
# tokens produced, so asking for 8,000 when the answer wants 1,200 words is
# paying seconds of waiting for text that _trim_to_depth then throws away.
#
# Roughly 1.4 tokens a word, times the upper step count, times 220 words a
# step, plus room for the JSON scaffolding, the code blocks and a drawing.
def tokens(topic):
    """How many output tokens this question's answer could need."""
    _lo, hi, _why = measure(topic)
    words = hi * 220
    return max(2200, min(8000, int(words * 1.4) + 1800))
