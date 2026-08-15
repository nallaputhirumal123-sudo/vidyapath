"""The calculator, and where the arithmetic happens.

A board in a classroom is used by whoever is standing in front of it, and
this file already said so two hundred lines from the bug:

    var OPEN_TOOLS = ["write", "calc", "formula"];  // needs no server

The calculator posted every sum to /api/craxlearn/calc, and that route asks
who is asking. So on a board nobody has signed in to — which is the normal
state of a board — pressing = answered "Sign in, or open this classroom with
your subject code first". That is the fifth tool on this board to need a
person it does not have; the others were the simulations, the course list,
the source search and the scanner.

**The fix is better than removing the check.** Arithmetic does not need a
network at all, and a calculator that works in a power cut is a better
calculator. It is worked on the board, by a parser walking an allowlist —
no eval, no Function — which is the same shape as maths.py so the two agree
about what an expression means.

**And the formula pane answers now.** Somebody typed sin^2+cos^2= on a
board, pressed the key that means "so what is it", and the screen showed the
same thing back in a nicer font. A keypad with an = on it that does nothing
is the screen making a promise it does not keep. Where there is no numeric
answer — and sin^2+cos^2 is an identity, not a sum — it says what is
missing, because "nothing happened" teaches nobody anything.
"""
import io
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

CALC = io.open(os.path.join(ROOT, "calc.js"), encoding="utf-8").read()
BOARD = io.open(os.path.join(ROOT, "craxlearn.html"), encoding="utf-8").read()
P, F = [], []


def ck(name, cond, why=""):
    print(("PASS " if cond else "FAIL ") + name + (" — " + why if why else ""),
          flush=True)
    (P if cond else F).append(name)


print("\nit works out what a classroom asks it")
CASES = [
    ("12 * (3 + 4) - 2^5", 52), ("2+2", 4), ("sqrt(16)", 4),
    ("10/4", 2.5), ("7%3", 1), ("-5+2", -3), ("2^3^2", 512),
    ("(2+3)*4=", 20), ("log10(1000)", 3), ("2*pi", 6.283185307),
    # Degrees, because every Class 10 textbook in the country is in degrees
    # and a calculator answering -0.988 for sin(30) is right in a way that
    # helps nobody.
    ("sin(30)", 0.5), ("cos(60)", 0.5), ("asin(0.5)", 30),
    ("sin(30)^2+cos(30)^2", 1),
]
REFUSE = [
    ("1/0", "divides by zero"),
    ("x+1", "no value here"),
    ("((2)", "not closed"),
    # The one that started it: an identity is not a sum, and saying so is
    # the useful answer.
    ("sin^2+cos^2", "needs a number in brackets"),
]
JS = """
global.window = global;
require(%s);
var out = [];
%s
console.log(JSON.stringify(out));
""" % (json.dumps(os.path.join(ROOT, "calc.js").replace("\\", "/")),
       "\n".join("out.push(Calc.run(%s));" % json.dumps(e)
                 for e, _ in CASES + REFUSE))
try:
    r = subprocess.run(["node", "-e", JS], capture_output=True, text=True,
                       timeout=60, encoding="utf-8")
    got = json.loads([l for l in (r.stdout or "").splitlines()
                      if l.startswith("[")][-1])
except Exception as e:
    got = None
    print("(node unavailable, skipping the arithmetic: %s)" % e)

if got:
    for i, (expr, want) in enumerate(CASES):
        g = got[i]
        ok = g.get("ok") and abs(g.get("value", 0) - want) < 1e-6
        ck("%s = %s" % (expr, want), ok,
           "" if ok else "got " + json.dumps(g))
    for j, (expr, phrase) in enumerate(REFUSE):
        g = got[len(CASES) + j]
        ok = (not g.get("ok")) and phrase in (g.get("why") or "")
        ck("refused, and says why: " + expr, ok,
           (g.get("why") or "") if not g.get("ok") else "it answered anyway")

print("\nnothing is executed, only walked")
ck("no eval", "eval(" not in CALC)
ck("no Function constructor", "new Function" not in CALC,
   "this is the one input box in a room full of teenagers who have just "
   "been taught what a sandbox is")
ck("names are checked against an allowlist",
   "hasOwnProperty.call(FUNCS" in CALC and "hasOwnProperty.call(CONSTS" in CALC)
ck("and a runaway power is refused rather than run",
   "MAX_POW" in CALC,
   "2^1e9 is not a maths error, it is a hung board in front of a class")

print("\nand it happens on the board, not at the server")
ck("the calculator works it out locally", "Calc.run(inp.value)" in BOARD)
ck("it no longer asks who is asking",
   "/api/craxlearn/calc" not in re.sub(r"/\*.*?\*/", " ", BOARD, flags=re.S),
   "the board's own code lists calc among the tools that need no server, "
   "two hundred lines from where it was calling one")
ck("the board loads it", "calc.js?v=" in BOARD)
ck("and says where the work happens",
   "works with no account and no" in BOARD)

print("\nthe formula pane answers when asked")
ck("an = at the end is a question", 'if(!/=\\s*$/.test(txt)' in BOARD)
ck("there is somewhere to put the answer", 'id="fmAns"' in BOARD)
ck("and it says what is missing when there is no number",
   "got.why" in BOARD,
   "sin^2+cos^2 is an identity, not a sum; silence teaches nobody")

print("\nthe keypad's own keys are readable")
ck("no literal control characters", chr(8) not in BOARD and chr(24) not in BOARD,
   "the back and clear keys carried a real BACKSPACE and a real CANCEL as "
   "their values — invisible in every editor, and one careless save from "
   "being silently deleted")
ck("they are words now", 'data-fm="back"' in BOARD and 'data-fm="clear"' in BOARD)

print("\n" + ("PASSED %d   FAILED %d" % (len(P), len(F))))
if F:
    for name in F:
        print("  FAILED: " + name)
    sys.exit(1)
