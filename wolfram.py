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

# The LLM API returns computed results and curated data together, with
# enough context to hand straight to a model. Short Answers returns one line
# and refuses anything it does not read as a computation.
#
# Which one an AppID is granted for is chosen at signup, so both are tried.
LLM = "https://www.wolframalpha.com/api/v1/llm-api"
SHORT = "https://api.wolframalpha.com/v1/result"
TIMEOUT = 9.0

# Questions worth spending a call on: something is being computed, not
# discussed. "Solve x^2-5x+6=0" yes; "why do quadratics have two roots" no.
_COMPUTE = re.compile(
    r"\b(solve|evaluate|calculate|compute|integrate|differentiate|"
    r"derivative of|integral of|simplify|factor|factorise|factorize|"
    r"expand|roots? of|limit of|sum of|series|determinant|inverse of|"
    r"eigenvalue|convert|how many|how much|what is the value)\b", re.I)

# The other half of what Wolfram holds: curated data. "The melting point of
# tungsten" has a sourced answer there and was going to the model's memory
# instead, which is exactly the substitution this whole tool exists to stop.
_DATA = re.compile(
    r"\b(melting point|boiling point|density of|atomic (?:mass|number|radius)|"
    r"molar mass|molecular (?:mass|weight)|specific heat|"
    r"thermal conductivity|resistivity|refractive index|bandgap|band gap|"
    r"work function|half[- ]life|ionisation energy|ionization energy|"
    r"electronegativity|boiling|freezing point|speed of|charge of|"
    r"mass of (?:a|an|the)|radius of|distance to|orbital period|"
    r"population of|elevation of|wavelength of|frequency of|"
    r"solubility|viscosity|tensile strength|young.s modulus)\b", re.I)

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
    if _NOT.search(q) and not (_MATHY.search(q) or _DATA.search(q)):
        return False
    return bool(_COMPUTE.search(q) or _MATHY.search(q)
                or _DATA.search(q))


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
    # The LLM API first: it answers data questions as well as computations
    # and gives enough context to be worth handing to a model. Short Answers
    # is the fallback for a key granted only for that one.
    for url, params, parse in (
        (LLM, {"appid": APPID, "input": q, "maxchars": 900}, _from_llm),
        (SHORT, {"appid": APPID, "i": q, "units": "metric"}, _from_short),
    ):
        try:
            r = await client.get(url, timeout=TIMEOUT, params=params)
        except Exception as e:
            print(f"Wolfram lookup failed for {q[:50]!r}: "
                  f"{type(e).__name__}: {e}")
            continue
        # 501 is "I have no answer for that", which is a normal outcome and
        # not a failure. 403 means this key is not valid for this API, which
        # is why the other one is tried.
        if r.status_code != 200:
            continue
        text = parse(r.text or "")
        if text:
            return text
    return ""


def _from_short(body):
    """The Short Answers API returns the answer as the whole body."""
    text = str(body or "").strip()
    if not text or len(text) > 400:
        return ""
    if text.lower().startswith(("no ", "wolfram", "(data not available")):
        return ""
    return text


def _from_llm(body):
    """The LLM API returns labelled sections; the result is what is wanted.

    Everything else it sends — the input interpretation, plots, related
    queries — is context for a chat assistant and noise here, because the
    model is being handed one fact to explain rather than a page to read.
    """
    text = str(body or "").strip()
    if not text:
        return ""
    want = ("result", "exact result", "decimal approximation", "value",
            "solution", "solutions", "roots")
    for block in text.split("\n\n"):
        head, _, rest = block.partition(":")
        if head.strip().lower() in want and rest.strip():
            line = " ".join(rest.split())
            if line and len(line) <= 400:
                return line
    # No labelled result: take the first substantial line that is not the
    # echo of the question.
    for line in text.splitlines():
        line = line.strip()
        if (line and not line.lower().startswith(
                ("input", "query", "assumption", "wolfram"))
                and 3 < len(line) <= 400):
            return line
    return ""


def note(question, answer):
    """The line to hand the model, naming where the number came from.

    Given as ground truth to explain rather than as a suggestion, because the
    entire point is that this number is not the model's opinion.
    """
    if not answer:
        return ""
    return (
        "\n\nVERIFIED VALUE (from Wolfram Alpha — a computer algebra system "
        f"and a curated data source, not from you): {answer}\n"
        "This is the correct result. Explain how it is reached and what it "
        "means; do not recompute it, do not contradict it, and do not round "
        "it differently. If your own working disagrees with it, your working "
        "is wrong.")
