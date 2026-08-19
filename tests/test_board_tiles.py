"""The board's home screen: teaching surfaces for staff, everything for pupils.

A board at the front of a room is operated mid-sentence, and twelve tiles on
it is a menu somebody has to read while thirty people wait. Four of them are
places to PRACTISE — work through the course, type queries, send packets, run
reactions — and practising is what a pupil does at their own desk at their own
pace. A teacher standing at the board is teaching.

So the practice tiles come off the home screen for staff and stay for pupils.
The pages themselves stay routable: a bookmark from last term still opens, and
a teacher who wants to demonstrate the SQL board can still reach it. Only the
home screen is shortened — the difference between moving a door and bricking
up a room.

This is checked by reading craxlearn.html rather than by driving a browser.
The tile list is a literal in that file, and a literal is exactly the kind of
thing that drifts back one tile at a time.
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = io.open(os.path.join(ROOT, "craxlearn.html"), encoding="utf-8").read()

P, F = [], []
def ck(n, c, d=""):
    print(("PASS " if c else "FAIL ") + n + (f" — {d}" if d else ""), flush=True)
    (P if c else F).append(n)

# Every tile the board declares, by its page name.
tiles = re.findall(r'\{\s*page:\s*"([a-z0-9]+)"', SRC)
tiles = [t for t in tiles if t]
ck("the board declares its tiles as a list", len(tiles) >= 10, str(len(tiles)))

PRACTICE = {"tracks", "net", "lab", "sqlboard"}
TEACHING = {"board", "write", "calc", "structure", "find", "phet", "scan",
            "remote"}

for t in sorted(PRACTICE):
    ck(f"{t} is still a tile that exists", t in tiles, str(tiles))
for t in sorted(TEACHING):
    ck(f"{t} is still a tile that exists", t in tiles, str(tiles))

print("\nthe split itself")
m = re.search(r'var PRACTICE_TILES\s*=\s*\[(.*?)\]', SRC, re.S)
ck("the practice list is named in one place", bool(m))
if m:
    named = set(re.findall(r'"([a-z0-9]+)"', m.group(1)))
    ck("and it is exactly the four practice surfaces", named == PRACTICE,
       str(sorted(named)))
    ck("no teaching surface was swept into it",
       not (named & TEACHING), str(sorted(named & TEACHING)))

ck("the filter only removes them for staff",
   re.search(r'teacher\s*&&\s*PRACTICE_TILES\.indexOf', SRC) is not None,
   "the condition must include `teacher`, or pupils lose them too")

print("\nwhat must NOT have happened")
# Hiding a tile is a home screen decision. Deleting the page is a different
# act, and would break a bookmark a class has been using all term.
for page in sorted(PRACTICE):
    ck(f"the {page} page itself still exists",
       f'"{page}"' in SRC and SRC.count(f'"{page}"') > 1, str(SRC.count(f'"{page}"')))

ck("students are not filtered — the open board keeps its own rule",
   "OPEN_TOOLS.indexOf(t.page)" in SRC)

print("\nthe remote survives, because it is how a teacher faces the room")
ck("remote is a tile", "remote" in tiles)
ck("and it is not treated as practice", "remote" not in PRACTICE)

print("")
print("the board does not put a register on a television")
# The class code used to answer with every child's name so a pupil could tap
# theirs. On a pupil's own phone that is right, and it is still there. On a
# screen at the front of a room it was a list of children, readable by the
# whole class and by anybody walking past.
ck("the board never asks for the register",
   "craxlearn/code" not in SRC, "the roster route is called from the board")
ck("nor claims a name from it",
   "craxlearn/claim" not in SRC, "the claim route is called from the board")
ck("a class code opens the room instead",
   'room.kind === "class"' in SRC)
INDEX = io.open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
ck("and a pupil can still sign in on their own device",
   "craxlearn/code" in INDEX and "craxlearn/claim" in INDEX,
   "the register sign-in must survive somewhere")

print("")
print("a code buys a BOARD, not four tiles")
# It bought a writing space, a calculator, the shelf and the phone remote.
# Everything that makes this a teaching board — ask it a topic, turn a
# molecule round, run a simulation, photograph a question out of a book —
# needed an account, and the whole point of the code is that a teacher at
# the front of a room has not got one. The board was empty in the only way
# that matters: empty of the reason to use it.
ck("a coded board is not held to the no-server tools",
   "if(!boarded()) return false;" in SRC,
   "OPEN_TOOLS is the list for a board with NO code")
ck("it gets the teaching surfaces", "return PRACTICE_TILES.indexOf(t.page) < 0;" in SRC)
ck("but not the practice ones",
   "PRACTICE_TILES = [\"tracks\", \"net\", \"lab\", \"sqlboard\"]" in SRC,
   "working through a course at your own pace is a pupil at their own desk")
ck("and the lesson request carries the code's token",
   'window.bapi.post("/api/board/lesson"' in SRC,
   "a board is not signed in; the token says which room is asking")
# The calculator used to post here too, and this checked that it carried the
# code's token. It carries nothing now: arithmetic does not need a network,
# and a calculator that works in a power cut is a better calculator. The
# route it called asked who was asking, which a board cannot answer.
ck("and the calculator asks nobody anything",
   'window.bapi.post("/api/craxlearn/calc"' not in SRC
   and "Calc.run(inp.value)" in SRC)

print("")
print("the board is not signed in, and cannot be")
# It used to read the craxle.com session, so whatever account was signed in
# on that browser became the board — on a classroom machine that is whoever
# last used it, with their classes on a screen the whole room can see.
ck("no request from this page carries a cookie",
   'credentials:"same-origin"' not in SRC,
   "one omitted credential is the whole seam between the two halves")
ck("and it never asks who is signed in",
   'api.get("/api/craxlearn/me")' not in SRC,
   "a board is a screen on a wall; it has no user")
ck("what it knows comes from a code",
   "async function roomFromLink()" in SRC and "function boarded()" in SRC)

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
