"""Send the computation to something that computes.

Models are poor at arithmetic and worse at symbolic algebra. They are fluent
about it, which is the problem: a derivation that reads correctly and is wrong
in the third line is harder to catch than one that reads badly. Everything
else in this product works around that by checking afterwards — substituting
the answer back, comparing constants, testing dimensions — and none of it can
supply a right answer, only reject a wrong one.

Wolfram Alpha computes. Asked to solve an integral or a quadratic it returns
the result from a computer algebra system, not from a language model's memory
of one. So the arithmetic goes there and the model is left doing the part it
is good at: explaining what the result means.

Needs WOLFRAM_APPID in the environment. Without it every function here
returns nothing and the lesson is exactly what it was — an unconfigured tool
must cost nobody an answer.

The free tier is 2,000 calls a month, which is why this runs only on questions
that are actually computational, decided by looking at the question rather
than by asking a model.
"""
import os
import re

APPID = (os.environ.get("WOLFRAM_APPID") or "").strip()
ENABLED = bool(APPID)

SHORT = "https://api.wolframalpha.com/v1/result"
FULL = "https://api.wolframalpha.com/v2/query"
TIMEOUT = 8.0

# Questions worth spending a call on: something is being computed, not
# discussed. "Solve x^2-5x+6=0" yes; "why do quadratics have two roots" no.
_COMPUTE = re.compile(
    r"\b(solve|evaluate|calculate|compute|integrate|differentiate|"
    r"derivative of|integral of|simplify|factor|factorise|factorize|"
    r"expand|roots? of|limit of|sum of|series|determinant|inverse of|"
    r"eigenvalue|convert|how many|how much|what is the value)\b", re.I)

# A formula or an expression in the text is itself a strong signal.
_MATHY = re.compile(r"[0-9]\s*[+\-*/^=%]|[0-9]\s*%|[a-z]\s*\^\s*[0-9]"
                    r"|\\int|∫|d/dx")

# Things it must never be asked, because the answer would be worthless or
# the question is not computational at all.
_NOT = re.compile(
    r"\b(explain|why|describe|discuss|compare|history|who|opinion|"
    r"should i|meaning of|significance)\b", re.I)


def wanted(question):
    """Is this a computation rather than a discussion?"""
    q = " ".join(str(question or "").split())
    if not q or len(q) > 300 or not ENABLED:
        return False
    if _NOT.search(q) and not _MATHY.search(q):
        return False
    return bool(_COMPUTE.search(q) or _MATHY.search(q))


def _clean_query(question):
    """The question with the tutoring wrapped off it."""
    q = " ".join(str(question or "").split())
    q = re.split(r"\s+—\s+|\s+-\s+", q)[0]
    q = re.sub(r"^(please\s+)?(can you\s+)?(help me\s+)?", "", q, flags=re.I)
    return q.strip(" .?")[:200]


async def result(client, question):
    """The computed answer as one line, or an empty string.

    Never raises. Wolfram being down, slow or out of quota must leave the
    lesson exactly as it would have been.
    """
    if not wanted(question):
        return ""
    q = _clean_query(question)
    if not q:
        return ""
    try:
        r = await client.get(SHORT, timeout=TIMEOUT,
                             params={"appid": APPID, "i": q,
                                     "units": "metric"})
        # 501 is Wolfram's "I have no short answer for that", which is a
        # normal outcome for a question it does not treat as computational.
        if r.status_code != 200:
            return ""
        text = (r.text or "").strip()
    except Exception as e:
        print(f"Wolfram lookup failed for {q[:50]!r}: {type(e).__name__}: {e}")
        return ""
    if not text or len(text) > 400:
        return ""
    if text.lower().startswith(("no ", "wolfram", "(data not available")):
        return ""
    return text


def note(question, answer):
    """The line to hand the model, naming where the number came from.

    Given as ground truth to explain rather than as a suggestion, because the
    entire point is that this number is not the model's opinion.
    """
    if not answer:
        return ""
    return (
        "\n\nCOMPUTED ANSWER (from Wolfram Alpha, a computer algebra system, "
        f"not from you): {answer}\n"
        "This is the correct result. Explain how it is reached and what it "
        "means; do not recompute it, do not contradict it, and do not round "
        "it differently. If your own working disagrees with it, your working "
        "is wrong.")
