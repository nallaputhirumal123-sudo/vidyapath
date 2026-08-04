"""The board teaches. craxle.com runs the school.

Craxlearn carried six management tiles — your classes, the register, work to
review, what the class is asking — and craxle.com's teacher dashboard grew the
same things. Two places to type a register is one too many: the one you are not
standing at goes stale, and a teacher in front of thirty children should not be
working out which screen is the real one.

What stays on the board is what a teacher reaches for WHILE TEACHING, and that
deliberately includes pulling things up — free access to anything on the board
is the point of the board.

What is pinned:

**The management tiles are off the home screen**, so nobody is offered two
registers.

**The pages still route.** Only the tiles were removed. A bookmark from last
term keeps working, which is the difference between moving a door and bricking
up a room.

**Nothing server-side changed.** Every route the board used is still there and
still reachable — a UI decision must not quietly become an API change.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {name}" + (f"  ({detail})" if detail else ""))
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


page = io.open("craxlearn.html", encoding="utf-8").read()
tiles = page.split("var TEACHER_TILES")[1].split("];")[0]

print("\nwhat the board offers a teacher")
for p in ("materials", "sources"):
    check(f"{p!r} is still a tile", f'page:"{p}"' in tiles,
          "pulling things up mid-lesson is teaching")
for p in ("roll", "roster", "inbox", "activity"):
    check(f"{p!r} is not", f'page:"{p}"' not in tiles,
          "it lives on the teacher dashboard now")

print("\nbut the pages themselves still work")
for p in ("roster", "roll", "inbox", "activity"):
    check(f"{p!r} still routes", f'page === "{p}"' in page or f'{p}()' in page,
          "a bookmark from last term must not break")

print("\nand craxle.com carries them properly")
idx = io.open("index.html", encoding="utf-8").read()
check("the register is there, with roll numbers",
      "rosterPaint" in idx and "student_code" in idx)
check("with search over name or number", 'id="rosFind"' in idx)
check("attendance too", "renderAttend" in idx)
check("and every learner in the school", "renderLearners" in idx,
      "none of which the board tiles ever had")

print("\nnothing server-side moved")
main = io.open("main.py", encoding="utf-8").read()
for r in ("/api/craxlearn/standing", "/api/teacher/classes",
          "/api/class/{cid}/materials"):
    check(f"{r} still exists", f'"{r}"' in main,
          "a UI decision must not quietly become an API change")

print(f"\nPASSED {PASS}   FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
