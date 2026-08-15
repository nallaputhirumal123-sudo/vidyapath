"""Will the school's own board run this? Answered before anybody buys.

Most classroom boards in service were bought years ago and have never been
updated. Their browser is whatever shipped with them, and nobody in the
school has the password to change it. Selling into that and discovering
afterwards which half of the product does not run is the worst possible
order to find out — for the school and for us.

**So the board answers for itself.** /board-check.html is opened on the
board, asks it eight questions, and says what each answer costs in words a
head of department can act on: no WebAssembly means the coding labs cannot
run Python and every other thing still works; no WebGL means 3D structures
will not draw and every lesson still reads.

**And it is written in ES5, which is the whole trick.** A checker written in
the JavaScript it is testing for cannot parse on the boards that most need
checking, and a blank page is not a report. No arrow functions, no let, no
const, no template literals, no fetch — the only modern syntax in the file
is inside a STRING handed to new Function, which is how it asks whether the
browser can parse that syntax without using it.

**The verdict is never "no".** A board that cannot be updated is still a
perfectly good screen: what has to be modern is whatever is plugged into its
HDMI socket, and a teacher's phone is almost always newer than the board on
the wall. A page that ends in a dead end sells nothing and helps nobody.
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PAGE = io.open(os.path.join(ROOT, "board-check.html"), encoding="utf-8").read()
JS = re.findall(r"<script[^>]*>(.*?)</script>", PAGE, re.S)[0]
# Comments stripped, because these files explain the very syntax they are
# being checked for not using. It is the fourth time in this codebase that
# a comment has failed a test about the code, so: never grep the prose.
_CUT = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)
IDX = _CUT.sub(" ", io.open(os.path.join(ROOT, "index.html"),
                            encoding="utf-8").read())
BOARD = _CUT.sub(" ", io.open(os.path.join(ROOT, "craxlearn.html"),
                              encoding="utf-8").read())
P, F = [], []


def ck(name, cond, why=""):
    print(("PASS " if cond else "FAIL ") + name + (" — " + why if why else ""),
          flush=True)
    (P if cond else F).append(name)


print("\nthe checker runs on the boards it is meant to check")
# Everything below is the same rule: a file that cannot parse cannot report.
for label, pat in (("arrow functions", r"=>"),
                   ("let and const", r"\b(?:let|const)\s+\w"),
                   ("template literals", r"`"),
                   ("optional chaining", r"\?\."),
                   ("nullish coalescing", r"\?\?"),
                   ("classes", r"\bclass\s+\w"),
                   ("fetch", r"\bfetch\s*\("),
                   ("Promise", r"\bPromise\b")):
    ck("no " + label, not re.search(pat, JS),
       "a checker written in the JavaScript it is testing for fails to "
       "parse on exactly the board that needed checking")
_async = re.findall(r"\basync\b", JS)
ck("async appears only inside a string it hands to new Function",
   len(_async) == 1 and 'new Function("return (async function(){})")' in JS,
   "that is how it asks whether the browser can parse modern JavaScript "
   "without itself depending on the answer")

print("\nit asks the questions that decide what a school loses")
for feature in ("WebAssembly", "webgl", "getUserMedia", "getDisplayMedia",
                "speechSynthesis", "sessionStorage"):
    ck("it tests " + feature, feature in JS)
ck("every test is wrapped so one failure cannot stop the rest",
   "function has(fn) { try { return !!fn(); } catch (e) { return false; } }"
   in JS,
   "asking an old browser for a modern thing frequently throws rather "
   "than returning undefined")

print("\nand it says what each answer costs, not just yes or no")
ck("no Python is not no product",
   "Lessons, notes, papers" in JS and "unaffected" in JS,
   "a school reading this needs to know what still works, which is most "
   "of it")
ck("no 3D is not no lesson", "Every lesson still reads" in JS)
ck("a missing camera has a way round it", "Photograph on a phone" in JS)

print("\nthe verdict is never a dead end")
ck("an old board is offered a way to be used",
   "still a perfectly good screen" in JS,
   "what has to be modern is whatever is plugged into the HDMI socket")
ck("with the cheap fix named", "HDMI" in JS and "phone" in JS)
ck("and the browser is reported for whoever is asked to fix it",
   "navigator.userAgent" in JS)
ck("which is escaped before it goes on the page",
   'replace(/[<>]/g, "")' in JS,
   "a user-agent string is not ours and goes into innerHTML")

print("\nthe app itself does not use syntax that kills an old board outright")
# Optional chaining and nullish coalescing are PARSE errors below Chrome 80.
# A parse error takes the whole script block with it, so a board that could
# have run most of this showed a blank page instead. Four of them were in
# index.html.
for label, pat in (("optional chaining", r"\?\."),
                   ("nullish coalescing", r"\?\?[^=]")):
    ck("index.html has no " + label, not re.search(pat, IDX),
       "a parse error is the difference between a board missing one "
       "feature and a board showing nothing at all")
    ck("craxlearn.html has no " + label, not re.search(pat, BOARD))

print("\n" + ("PASSED %d   FAILED %d" % (len(P), len(F))))
if F:
    for name in F:
        print("  FAILED: " + name)
    sys.exit(1)
