"""Asking about a word must not rearrange the lesson it is in.

Select a phrase on the board, tap Ask Axle, and the answer arrives. Where it
arrives has now been three things.

**It replaced the pane.** That took the lesson off the screen to answer a
question about the lesson: the class loses the sentence they were looking
at, and the teacher has to find their way back to it.

**Then it opened a second space.** Better — until a board already split in
two got a THIRD, at which point every space on the screen reflowed to make
room. A question about one word should not move the diagram somebody is
pointing at.

**Now it is a window.** It floats above the work, is dragged by its bar,
resized by its corner, and closed by its ✕ — and it stays where the teacher
put it, because a window that jumps back to the middle of the screen every
time is a window a teacher stops using.

**What makes that possible without rewriting the board.** `main()` is "the
body of whichever space is being drawn into", which is what lets every page
in that file — all written against a single screen — work in any of them.
The window is one more thing to draw into, so the whole board renderer works
inside it unchanged and without knowing it is floating.

**And a space already showing the board still wins.** Every tool names its
fields by id, and two boards on one screen would both write into the same
box.
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

RAW = io.open(os.path.join(ROOT, "craxlearn.html"), encoding="utf-8").read()
# Comments stripped before anything is looked for: this file explains the
# two designs it replaced, and a search for "PANES.push" finds the sentence
# about it rather than the code. That has happened four times here.
CODE = re.sub(r"/\*.*?\*/|//[^\n]*", " ", RAW, flags=re.S)
P, F = [], []


def ck(name, cond, why=""):
    print(("PASS " if cond else "FAIL ") + name + (" — " + why if why else ""),
          flush=True)
    (P if cond else F).append(name)


print("\nit no longer takes a space of its own")
ck("asking does not add a pane",
   "PANES.push({ page: \"board\"" not in CODE,
   "on a board already split in two this made a third, and every space on "
   "the screen reflowed to make room for it")
ck("it opens a window instead", "function askFloat(" in CODE)
ck("and the old name still works, so nothing else had to change",
   "function askBeside(q){ return askFloat(q); }" in CODE)
ck("the selection popup still reaches it", "askBeside(q)" in CODE)

print("\nthe window can be moved, sized and shut")
ck("dragged by its bar",
   'bar.addEventListener("pointerdown"' in CODE
   and 'bar.addEventListener("pointermove"' in CODE,
   "pointer events, so a finger on a board and a mouse on a laptop are the "
   "same code")
ck("the pointer is captured while dragging",
   "setPointerCapture" in CODE,
   "a fast drag that leaves the bar would otherwise drop the window "
   "halfway across the screen")
ck("resized by its corner", "resize:both" in RAW)
ck("closed by its own button", 'id="askFloatShut"' in CODE)
ck("and the body is emptied when it closes",
   'el("askFloatBody").innerHTML = ""' in CODE,
   "a closed window holding the last lesson is a lesson still being asked "
   "about")

print("\nit stays where it was put")
ck("the position is kept for the session", "ASKPOS" in CODE)
ck("recorded when it is dropped and when it is closed",
   CODE.count("remember_ask(box)") >= 2)
ck("and applied when it opens again", "box.style.left = ASKPOS.left" in CODE)

print("\nand it cannot be lost off the edge of the board")
ck("the drag is clamped", "Math.max" in CODE and "window.innerWidth" in CODE,
   "a window dragged past the edge of a board is a window nobody in the "
   "room can reach, and there is no window list to get it back from")
ck("part of it always stays reachable",
   "window.innerHeight - 40" in CODE)

print("\nthe board renderer works inside it unchanged")
ck("the window is somewhere to draw into", "FLOAT_HOST" in CODE)
ck("and main() honours it", "if(FLOAT_HOST) return FLOAT_HOST;" in CODE,
   "main() is the body of whichever space is being drawn into, which is "
   "what lets pages written for one screen work in any of them")
ck("the override is cleared even if drawing throws",
   "finally{ FLOAT_HOST = null; }" in CODE,
   "left set, every later page on the board would draw into a window that "
   "may not even be open")

print("\na space already showing the board still wins")
ck("it is looked for first",
   'toolOf(PANES[i].page) === "board"' in CODE)
ck("and used rather than duplicated",
   "paintPanes();" in CODE and "return;" in CODE,
   "every tool names its fields by id, so two boards would both write into "
   "the same box")

print("\nand the window is styled to be one")
for bit, why in (("position:fixed", "it floats over the work"),
                 ("z-index:80", "above the panes and their controls"),
                 ("cursor:move", "the bar says it can be dragged"),
                 ("touch-action:none", "a finger drags it rather than "
                                       "scrolling the page under it"),
                 ("overflow:auto", "a long lesson scrolls inside it")):
    ck(bit, bit in RAW, why)
ck("and it never prints", "@media print{.askfloat{display:none}}" in RAW)

print("\n" + ("PASSED %d   FAILED %d" % (len(P), len(F))))
if F:
    for name in F:
        print("  FAILED: " + name)
    sys.exit(1)
