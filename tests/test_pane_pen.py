"""A pen for each space, fixed to what is in that space.

The board has had Ink since early on: one sheet of glass over the whole
screen. That is right for annotating the room's display and wrong the moment
the board is split. A ring drawn round a term in the lesson on the left
belongs to the lesson on the left — and on the glass it stayed where the
glass was. It did not move when that pane scrolled, and it was still sitting
there when the pane was swapped to a simulation, now ringing nothing.

So each space gets its own pen. Three things are pinned here because each of
them is a way this quietly stops working.

**The canvas is a child of the scrolling body and sized to its scrollHeight.**
Not fixed and repositioned on a scroll listener — in the flow, so the browser
carries it with the content and a mark cannot lag a fast flick. Sized to the
visible box instead, every mark below the fold would have nowhere to land.

**The strokes live on the pane object, not on the element.** Panes are
rebuilt from scratch whenever a tool changes or the board is split again.
Marks kept on the canvas would vanish each time, which looks exactly like the
pen having been switched off by itself.

**Not offered on the writing space.** That already IS a pen, with its own
colours, its own eraser and an endless surface. A second sheet of glass over
it takes the pointer events the board needs, and the result is a writing
space you cannot write on.
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = io.open(os.path.join(ROOT, "craxlearn.html"), encoding="utf-8").read()
P = F = 0


def ck(name, cond, note=""):
    global P, F
    print(("  PASS  " if cond else "  FAIL  ") + name +
          (f" ({note})" if note else ""), flush=True)
    if cond:
        P += 1
    else:
        F += 1


print("\nevery space has its own pen")
ck("a button on the pane's own head", 'data-mark="' in SRC)
ck("which turns that space's pen on and off",
   "function markToggle(i, btn){" in SRC)
ck("and the pane says which one is being drawn on",
   '.pane[data-marking="1"] .paneHead{border-bottom-color:#ff3b30}' in SRC,
   "two panes and one red pen is a guess about where the next mark lands")

print("\nthe marks are fixed to what they were drawn on")
ck("the canvas is a child of the scrolling body",
   "body.appendChild(cv);" in SRC,
   "fixed and repositioned on a scroll listener always lags a fast flick")
ck("sized to the scrollable extent, not the visible box",
   "Math.max(body.scrollHeight, body.clientHeight)" in SRC,
   "a canvas the height of the fold has nowhere to put a mark made after "
   "scrolling")
ck("and it grows when the content does",
   "cv._ro = new ResizeObserver(function(){ size(); });" in SRC,
   "a lesson finishes rendering and an image loads after the pen is on")
ck("pointer positions are read against the canvas itself",
   "var r = cv.getBoundingClientRect();" in SRC,
   "which already carries the pane's scroll, so nothing else has to know "
   "about it")

print("\nand a mark cannot cross into the space next door")
ck("the pane clips", ".pane{display:flex;flex-direction:column;min-width:0;"
   "min-height:0;\n  overflow:hidden}" in SRC)
ck("and the body clips on BOTH axes",
   "overflow:hidden auto" in SRC,
   "naming only overflow-y leaves x `visible`, which the spec promotes to "
   "`auto` — not the same as clipping, and a stroke dragged past the right "
   "edge paints into the space beside it")
ck("the canvas is only as wide as its own pane",
   "var w = body.clientWidth," in SRC)
ck("and a drag that leaves the pane keeps belonging to it",
   "cv.setPointerCapture(e.pointerId);" in SRC,
   "without capture, crossing the divider hands the stroke to the other "
   "pane's glass mid-line")

print("\nand they survive the pane being rebuilt")
ck("strokes are kept on the pane, not the element", "p.marks = p.marks" in SRC)
ck("a space that was being drawn on gets its pen back",
   "if(p.marking && p.page !== \"write\") markOn(i);" in SRC,
   "panes are rebuilt on every tool change and every split")

print("\noff means gone, because a lesson underneath has to be clickable")
ck("the glass is inert until the pen is on",
   ".paneMark{position:absolute;left:0;top:0;z-index:5;pointer-events:none;"
   in SRC)
ck("and takes events only then",
   ".paneMark.on{pointer-events:auto;cursor:crosshair}" in SRC)
ck("with a way to put it down that is not the same button",
   'data-mdone="1"' in SRC,
   "a teacher mid-lesson should not have to find the head bar again")

print("\nnot on the writing space, which is already a pen")
ck("no second pen is offered there",
   'p.page === "write" ? "" :' in SRC,
   "a sheet of glass over the writing space is a writing space you cannot "
   "write on")
ck("and a pane swapped to it puts the pen down",
   "else if(p.marking) p.marking = false;" in SRC)

print("\nthe usual tools, because a pen with one colour is a novelty")
ck("colours", "var MARK_COLOURS = [" in SRC)
ck("an eraser that removes strokes rather than painting over them",
   "p.marks = p.marks.filter(function(s){" in SRC,
   "painting the background over a mark leaves a hole when the pane scrolls "
   "or the theme changes")
ck("and Clear", 'data-mclear="1"' in SRC)

print(f"\nPASSED {P}   FAILED {F}")
sys.exit(1 if F else 0)
