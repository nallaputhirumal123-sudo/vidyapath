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
check("the ones needing a person are named",
      'var ACCOUNT_TOOLS = ["roster", "roll", "inbox", "materials", '
      '"sqlboard"];' in page)
# Three different reasons, and only the first is "it reads a session".
#
# Study material spans every subject the class is taught, which is more than
# a one-subject code is entitled to — and it read ME.classes, empty on a
# board, so it told a teacher standing in 12-D they were not in a class yet.
# The SQL board is a PROGRESS screen: one learner's history, the skills they
# have shown, how many free explanations are left. There is no such person at
# a classroom board, and it said "Not signed in".
check("study material is left to an account", '"materials"' in page)
check("and the SQL board with it", '"sqlboard"' in page)
check("but the lab and the packet walkthrough stay",
      '"lab"' not in page.split("var ACCOUNT_TOOLS")[1].split("]")[0]
      and '"net"' not in page.split("var ACCOUNT_TOOLS")[1].split("]")[0],
      "they run entirely in the page and need nobody")
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

print("\na refresh does not cost the lesson")
# ROOM lived in memory and nowhere else, so reloading — a stray gesture on a
# board, a browser reclaiming a background tab, a teacher pressing refresh
# because something looked stuck — threw away the room AND what was on the
# screen, and came back at the code box or on Home.
check("the room survives a reload", "function restoreRoom(){" in page)
check("in sessionStorage, not localStorage", "sessionStorage.setItem(KEEP"
      in page,
      "per tab and gone when the tab closes, which is the right lifetime "
      "for a credential on a machine at the front of a classroom")
check("with what was on the screen", "panes: PANES.map(" in page)
check("and it is refused once the token would have expired",
      "> 11 * 3600 * 1000" in page,
      "a board left on overnight should ask for the code again")
check("signing out ends it", "forgetRoom();" in page)
check("and so does going back to the code screen",
      "OPEN = false;\n      forgetRoom();" in page,
      "a board handed to the next class must not reopen the last one's "
      "subject")

print("\nthe board does not ask what class it is in")
# There was a Class 6 / 8 / 10 / 12 / Undergraduate / Research dropdown on
# Ask the board. On a board opened with a subject code it is a question
# already answered — the code names 9-R Physics — and it is a control whose
# only correct value is the one already held. Nobody changed it, which is why
# every class was getting whatever the box happened to say.
check("the dropdown is gone", 'id="bLevel"' not in page)
check("the level comes from the room", "function roomLevel(){" in page)
check("read off the class name", "ROOM.class_name" in page)
check("and a name with no number is not guessed at",
      'return (n >= 1 && n <= 12) ? "Class " + n : "Intermediate";' in page,
      "a coaching batch is not a school year")
check("the screen says which level it is teaching at",
      'boarded() ? " Pitched for " + esc(roomLevel())' in page,
      "removing a control should not also remove the answer it gave")

print("\ntwo questions do not race")
# A lesson takes long enough that asking again is easy — a teacher retypes,
# or presses Teach it because nothing has happened yet. Both requests used to
# stay in flight with nothing deciding between them, so whichever replied
# LAST won: a new question sometimes produced the new answer and sometimes
# the old one, with no pattern visible from outside.
check("each ask is numbered", "var TEACHING = 0;" in page)
check("and a superseded reply is thrown away",
      "if(mine !== TEACHING) return;" in page)
check("the button is held while one is building",
      'go.textContent = "Teaching…";' in page,
      "so pressing twice is not how somebody discovers this")
check("and released whichever way it ends", "}finally{" in page)

MAIN = io.open("main.py", encoding="utf-8").read()

print("\nthe code screen has nothing on it that acts on a board")
# Nine controls sat in the top bar of the gate — split, screenshot, fold the
# bars, home, sign out, Ask Axle — every one of them working on a board that
# does not exist yet, plus the split panes from the LAST lesson still showing
# underneath the code box.
check("board controls are withdrawn while gated",
      "body.gated #splitBtn," in page and "body.gated #shotBtn," in page
      and "body.gated #outBtn," in page)
check("and the sources link with them", "body.gated .gatesources" in page,
      "worth reading, and not on the screen a class watches while a code is "
      "typed")
# The panes stayed because #app{display:flex} beats the browser's own
# [hidden] rule — an id selector against a UA default is not close — so
# el("app").hidden = true set the attribute and changed nothing.
check("hidden actually hides", "[hidden]{display:none !important}" in page,
      "a signed-out board was still showing the last lesson's spaces")

print("\nphotographs survive being kept")
# _lesson_figures preserved drawings, sketches, 3D and a PDF's own pictures,
# and dropped every PHOTOGRAPH. So a teacher wrote up DNA with a picture of
# DNA on the screen, pressed save, and the class opened a page of prose.
check("a lead photograph is kept",
      'lead = _photo(lesson.get("photo"), -1)' in MAIN)
check("and one per step", 'got = _photo(st.get("photo"), i)' in MAIN)
check("only over https", 'if not url.startswith("https://")' in MAIN)
check("and only from a host the picture search itself named",
      "for h in _images._HOSTS" in MAIN,
      "this is stored and handed to every child in the class")
check("the credit travels with the picture",
      '"author": str(p.get("author") or "")[:160]' in MAIN,
      "these are other people's photographs under licences that require the "
      "author be named")
check("and the board renders it back", 'if(f.how === "photo"){' in page)
check("with the credit shown", "[sp.caption, sp.author, sp.license]" in page,
      "a saved copy that loses the attribution is a licence breach on a "
      "school's page")

print("\nthe board's own tools do not need an account")
# The fourth and fifth instances of the same fault. 3D structures answered
# "Not signed in" on a board holding a perfectly good code, and the ⚠ button
# in the head of every space — the one a teacher presses the moment they see
# a wrong answer in front of a class — did the same.
check("3D structures opens to a board",
      "async def craxlearn_structure(name: str,\n"
      "                              user: User = Depends(board_or_reader)):"
      in MAIN)
check("and reporting a wrong answer does too",
      "user: User = Depends(_reader_or_board),\n"
      "                      db: Session = Depends(get_db)):" in MAIN)
check("a report is counted against the subject's teacher",
      "who = user.id if user is not None else _board_teacher_id(request, db)"
      in MAIN,
      "the limit still has to belong to somebody")

print("\na lesson shaped to be read from the back of a room")
# A section heading was .74rem, uppercase and letter-spaced — SMALLER than
# the body it introduced. Uppercase micro-type is a label on a form: it reads
# as furniture at arm's length and disappears entirely from the back of a
# room, which is the one place this has to work. Measured after: 36 / 28 /
# 23 / 19 / 19 for the step number, heading, lead, body and list.
check("headings are bigger than the body they introduce",
      ".lessonBody .lh{font-size:1.45em" in page)
check("the step number is the thing readable from the door",
      ".lessonBody .lstep b{font-size:1.9em" in page,
      "it was muted grey text the size of a caption")
check("and says how much is left",
      '"<span>of " + ((L.steps || []).length' in page,
      "a class needs to know where they are in a lesson")
check("a bullet reads the same size as a sentence",
      ".lessonBody .ll{margin:.2rem 0 .9rem 1.3rem;padding:0;font-size:1.02em}"
      in page,
      "five pixels smaller made a list look like a footnote to the sentence "
      "above it, when it is usually the substance")

print("\nevery space photographs itself, onto the class page")
# The space's camera asked to share the whole SCREEN: a permission prompt,
# the browser's own chrome in the shot, and the other half of a split board
# with it. The writing space is a canvas and can be read directly.
check("the writing space publishes how to photograph it",
      "WRITING_SHOT = function(){ return shotCanvas(); };" in page)
check("and the space's own button uses it",
      "if(isWriting && WRITING_SHOT){" in page,
      "no permission prompt, and nothing in frame that is not the board")
check("the picture is KEPT, not downloaded",
      "async function keepShot(cnv, btn){" in page,
      "a file in the Downloads folder of a machine bolted to a wall reaches "
      "nobody")
check("off a board a download is still right",
      'a.download = "craxlearn-"' in page)
check("and it says so afterwards", "function toastLine(msg){" in page,
      "a press that succeeded looked the same as one that did nothing")

print("\nnothing server-side moved")
main = io.open("main.py", encoding="utf-8").read()
for r in ("/api/craxlearn/standing", "/api/teacher/classes",
          "/api/class/{cid}/materials"):
    check(f"{r} still exists", f'"{r}"' in main,
          "a UI decision must not quietly become an API change")

print(f"\nPASSED {PASS}   FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
