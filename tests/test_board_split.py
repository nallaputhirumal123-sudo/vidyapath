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
for p in ("roster", "roll", "inbox"):
    check(f"{p!r} still routes", f'page === "{p}"' in page or f'{p}()' in page,
          "a bookmark from last term must not break")

print("\nexcept what the class is asking, which left the board entirely")
# Untiling a page and REMOVING it are different decisions, and this one is
# the second. It was the only screen on this board that read a craxle.com
# session rather than a subject code, and it put a list of what children are
# struggling with onto a screen thirty of them are looking at. A bookmark to
# it cannot be honoured by showing it anyway.
check("no route to it on the board", 'page === "activity"' not in page,
      "the board knows a room, never a person")
check("and no code left behind either", "activity" not in page,
      "a function nobody calls is the next person's tile")
check("an old bookmark lands on Home rather than a blank screen",
      "  return home();\n}" in page,
      "every unknown page falls through, so removing one is safe")

print("\nand craxle.com carries them properly")
idx = io.open("index.html", encoding="utf-8").read()
check("the register is there, with roll numbers",
      "rosterPaint" in idx and "student_code" in idx)
check("with search over name or number", 'id="rosFind"' in idx)
check("attendance too", "renderAttend" in idx)
check("and every learner in the school", "renderLearners" in idx,
      "none of which the board tiles ever had")
check("what the class is asking has a screen here", "renderAsking" in idx)
check("with a way in", 'nav("asking"' in idx,
      "a route with no menu entry is how a page goes unread for a term")
check("only for somebody who actually takes a class",
      "async function renderAsking(){\n  if(!teaches()){" in idx,
      "a school office account does not have a class to be curious about")
check("and it still names nobody", "no student is named on any row" in idx,
      "the limit is deliberate, so the page says so before anyone asks")

print("\na board holding a code is not an anonymous board")
# Both ways in go through openBoard(), which set OPEN unconditionally. So a
# board that had been given a subject code was still treated as having none,
# and two things followed. The header said "not signed in" while the board
# sat in a named room — which is what somebody reads just before concluding
# that saving to the class cannot work. And the tool menu is filtered by OPEN
# down to what needs no server, so every teaching tool was hidden: the
# material shelf, the sources, everything already saved for that subject.
# Entering the code changed nothing a teacher could see. Measured in a
# browser: four tools offered before, sixteen after.
check("OPEN follows the code", "OPEN = !boarded();" in page)
check("and the header names the room instead of denying it",
      'el("who").innerHTML = boarded()' in page
      and 'esc(ROOM.class_name || "This class")' in page)

print("\nbut a board still has no person, so some tools cannot be there")
check("the register, your classes and the queue are named",
      'var ACCOUNT_TOOLS = ["roster", "roll", "inbox"];' in page)
check("and kept out of the menu",
      "if(ACCOUNT_TOOLS.indexOf(k) >= 0) return false;" in page,
      "a code names a room and nobody in it")

print("\nthe board's one credential goes on BOTH clients")
check("api carries the board token too",
      'headers: bhdr({ "Content-Type":"application/json" })' in page,
      "simulations answered 'Not signed in' and the course list sat on "
      "'Loading…' for ever, on a board holding a perfectly good code")
check("and credentials are still omitted", 'credentials:"omit"' in page,
      "the token names a room; it must not become whoever last signed in here")

print("\nand a tap on Student messages reaches the assignment")
check("tmOpen sets the fields the dispatcher reads",
      'S.view={page:"tassign", cid:+cid, aid:+aid, student:+studentId};' in idx,
      "it set id and student while the dispatcher read v.cid and v.aid, so "
      "both arrived undefined and every tap showed an error")
check("and the row carries the class it needs", 'data-klass="${t.class_id}"'
      in idx)

print("\nnothing server-side moved")
main = io.open("main.py", encoding="utf-8").read()
for r in ("/api/craxlearn/standing", "/api/teacher/classes",
          "/api/class/{cid}/materials"):
    check(f"{r} still exists", f'"{r}"' in main,
          "a UI decision must not quietly become an API change")

print(f"\nPASSED {PASS}   FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
