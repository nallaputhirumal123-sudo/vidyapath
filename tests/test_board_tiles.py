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

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
