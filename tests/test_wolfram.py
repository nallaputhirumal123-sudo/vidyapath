"""Which questions go to Wolfram, and what comes back.

Models are fluent about arithmetic and poor at it, which is the worst pairing:
a derivation that reads correctly and is wrong in the third line is harder to
catch than one that reads badly. Everything else in this product checks
afterwards and can only reject a wrong answer; this supplies a right one.

The routing is the part worth testing, because every call costs quota. A
computation or a data lookup goes; a discussion does not. "Solve x^2-5x+6=0"
and "the melting point of tungsten" both have exact answers sitting in
Wolfram. "Why do quadratics have two roots" does not, and spending a call to
find that out buys nothing.

No network here. The live service is exercised in production, and a test that
needs an API key is a test that fails for everybody who does not have one.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import wolfram                                     # noqa: E402

PASS = FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {name}" + (f"  ({detail})" if detail else ""))
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


# Routing is decided independently of whether a key is configured.
wolfram.ENABLED = True

COMPUTE = [
    "solve x^2 - 5x + 6 = 0",
    "integrate x^2 dx",
    "the derivative of sin(x)cos(x)",
    "find the roots of x^3 - 1",
    "what is 15% of 240",
    "simplify (x^2-1)/(x-1)",
    "convert 30 celsius to fahrenheit",
]
for q in COMPUTE:
    check(f"computes: {q[:38]!r}", wolfram.wanted(q))

DATA = [
    "the melting point of tungsten",
    "the bandgap of silicon",
    "the density of copper",
    "the half-life of carbon-14",
    "the atomic mass of iron",
    "the speed of light",
    "the orbital period of Jupiter",
]
for q in DATA:
    check(f"looks up: {q[:38]!r}", wolfram.wanted(q))

DISCUSS = [
    "why do quadratics have two roots",
    "explain photosynthesis",
    "the history of calculus",
    "how does a firewall work",
    "compare TCP and UDP",
    "who discovered penicillin",
    "describe the water cycle",
]
for q in DISCUSS:
    check(f"does not spend a call on: {q[:32]!r}", not wolfram.wanted(q))

check("an empty question is refused", not wolfram.wanted(""))
check("and an essay is refused", not wolfram.wanted("solve " + "x" * 400))

# Without a key nothing is asked, whatever the question.
wolfram.ENABLED = False
check("no key means no calls", not wolfram.wanted("solve x^2 = 4"))
wolfram.ENABLED = True

# ---- the query sent, without the tutoring wrapped round it -----------
check("the lens suffix is stripped",
      wolfram._clean_query(
          "solve x^2-5x+6=0 — walk through one concrete worked example")
      == "solve x^2-5x+6=0",
      wolfram._clean_query("solve x^2-5x+6=0 — walk through one example"))
check("politeness is stripped",
      wolfram._clean_query("please can you solve x^2 = 4") == "solve x^2 = 4",
      wolfram._clean_query("please can you solve x^2 = 4"))

# ---- reading each API's reply ---------------------------------------
LLM_BODY = "Input:\nsolve x^2 - 5x + 6 = 0\n\nResult:\nx = 2, x = 3\n\nPlot:\n[image]"
check("the LLM API's result section is taken",
      wolfram._from_llm(LLM_BODY) == "x = 2, x = 3",
      repr(wolfram._from_llm(LLM_BODY)))
check("and the input echo is not",
      "solve" not in wolfram._from_llm(LLM_BODY).lower())
check("a labelled value is taken too",
      wolfram._from_llm("Input:\ntungsten\n\nValue:\n3422 °C") == "3422 °C",
      repr(wolfram._from_llm("Input:\ntungsten\n\nValue:\n3422 °C")))
check("an empty body gives nothing", wolfram._from_llm("") == "")

check("the Short Answers body is the answer",
      wolfram._from_short("x = 2, x = 3") == "x = 2, x = 3")
for refusal in ("No short answer available", "Wolfram|Alpha did not understand",
                "", "x" * 500):
    check(f"a refusal gives nothing: {refusal[:26]!r}",
          wolfram._from_short(refusal) == "")

# ---- what the model is told -----------------------------------------
note = wolfram.note("x", "3422 °C")
check("the value is handed over as ground truth", "3422 °C" in note)
check("and named as not the model's own", "not from you" in note)
check("with the working overruled",
      "your working" in note and "is wrong" in note)
check("nothing is added when there is no answer", wolfram.note("x", "") == "")

print(f"\nPASSED {PASS}   FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
