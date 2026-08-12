"""A model's JSON, and the six letters that eat its mathematics.

A lesson on fractions reached a class reading "consider the fraction 16 where
both 16 and 20 can be divided by their highest common factor" — the fraction
itself simply gone, and no error anywhere in the system.

The model had written \\frac{16}{20} inside its JSON reply, where it should
have written \\\\frac. What makes that dangerous rather than merely wrong is
that \\f IS a valid JSON escape — a form feed — so the parse SUCCEEDS. It
hands back a form feed and the letters "rac{16}{20}", the renderer sees no
LaTeX command, strips the braces, and the class reads a sentence with a hole
in it.

Six letters do this, and between them they take out most of the mathematics
on a maths paper:

    \\frac  \\begin  \\beta  \\neq  \\nabla  \\rho  \\times  \\theta  \\tan
    \\to  \\text

Every other letter after a backslash — \\alpha, \\sqrt, \\cdot — is not a
JSON escape at all, so those replies failed to parse outright and the whole
lesson was lost rather than one fraction of it.

The repair cannot simply double every backslash: "line one\\nline two" is a
model using a real newline and meaning it. So the letters after the backslash
are read, and it is doubled only where they spell a LaTeX command we know.
\\nabla is protected; \\next stays a newline.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import main                                            # noqa: E402

B = chr(92)
P, F = [], []


def ck(name, cond, why=""):
    print(("PASS " if cond else "FAIL ") + name + (" — " + why if why else ""),
          flush=True)
    (P if cond else F).append(name)


def got(body):
    """What the site ends up with, given exactly what the model sent."""
    return main._ai_json('{"t": "' + body + '"}')["t"]


print("\nthe mathematics survives the parse")
ck("a fraction is still a fraction",
   got(B + "frac{16}{20}") == B + "frac{16}{20}",
   "this is the lesson that reached a class as 'the fraction 16 where'")
for cmd in ("times", "theta", "tan", "to", "text{cm}", "neq", "nabla",
            "rho", "beta", "begin{align}", "underline{x}"):
    ck(B + cmd + " arrives whole", got(B + cmd) == B + cmd)

print("\nand so does everything that was failing to parse at all")
for cmd in ("alpha", "sqrt{2}", "cdot", "int_0^1", "pi", "left(", "(x)"):
    ck(B + cmd + " no longer loses the whole reply", got(B + cmd) == B + cmd,
       "an invalid escape took the lesson with it, not just the symbol")

print("\nwhat the model actually meant is still what it gets")
ck("a real newline is a newline",
   got("line one" + B + "nline two") == "line one\nline two",
   "'next' is not a LaTeX command, so this is a model breaking a line")
ck("a real tab is a tab", got("a" + B + "there") == "a\there")
ck("a unicode escape still decodes", got(B + "u00e9cole") == "école")
ck("but upsilon is not one", got(B + "upsilon") == B + "upsilon",
   "four hex digits make a unicode escape; 'psilon' is not four hex digits")
ck("an escaped quote still closes nothing",
   main._ai_json('{"t": "a ' + B + '"quote' + B + '" inside"}')["t"]
   == 'a "quote" inside')
ck("a backslash the model escaped properly is left alone",
   got(B + B + "frac{1}{2}") == B + "frac{1}{2}",
   "a model that got it right must not be corrected into getting it wrong")
ck("a Windows path survives", got("C:" + B + B + "Users") == "C:" + B + "Users")

print("\nand nothing else about the reply changes")
ck("ordinary JSON is untouched",
   main._ai_json('{"a": 1, "b": [true, null, "x"]}')
   == {"a": 1, "b": [True, None, "x"]})
ck("a fenced reply still parses",
   main._ai_json('```json\n{"a": 2}\n```') == {"a": 2})
ck("a reply with no backslash takes the fast path",
   main._json_keeps_latex('{"a": "plain"}') == '{"a": "plain"}')
print("\na reply cut off mid-answer keeps the answers it did finish")
CUT = ('{"questions": [{"n": "1", "answer": "x = 2"}, '
       '{"n": "2", "answer": "y')
ck("the complete answers survive the truncation",
   main._ai_json(CUT)["questions"][0]["answer"] == "x = 2",
   "this is what a truncation actually looks like — a batch that ran out "
   "of room in the middle of writing an answer")
ck("and the half-written one is not passed off as an answer",
   "answer" not in main._ai_json(CUT)["questions"][1],
   "a question with a blank answer reads as solved; it has to come back "
   "as unanswered so it is asked again")
ck("a lesson cut between steps keeps the finished steps",
   main._ai_json('{"steps": [{"t": "one"}, {"t": "two')["steps"]
   == [{"t": "one"}],
   "seven steps of eight is a lesson; a parse error is nothing")

print("\nthe repair only ever runs inside a string")
ck("a backslash outside a string is left where it is",
   main._json_keeps_latex('{"a": 1} \\ trailing').endswith("\\ trailing"))

print("\n" + ("PASSED %d   FAILED %d" % (len(P), len(F))))
if F:
    for name in F:
        print("  FAILED: " + name)
    sys.exit(1)
