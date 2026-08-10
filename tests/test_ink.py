"""Writing on top of whatever is on the board.

The writing space is a tool you OPEN, and that is the wrong shape for most of
what a teacher does with a pen. The moment worth annotating is a lesson
already on the screen, a diagram out of a chapter, a simulation mid-run — and
reaching the pen meant leaving them.

So the ink is a sheet over the whole board rather than a page inside it. Three
properties make that safe, and they are what this file pins:

**It is invisible until it is switched on.** The sheet covers every pixel, so
if it ever took a click while off, the board would be dead and nothing would
say why. `pointer-events: none` is the whole safety of the thing.

**It is not on the code screen.** Before a code is entered there is nothing to
annotate — the screen is a clock and a text box — so the pen, the sheet and
the bar are withdrawn rather than left inert. A control that does nothing is
worse than one that is not there.

**It survives what happens underneath.** Marks are in SCREEN coordinates, not
in the coordinates of whatever is beneath them, so switching tools does not
wipe them and does not drag them somewhere else. A teacher circling a word
does not expect the circle to follow the word.

Saving goes through the screen capture rather than through this canvas,
because the ink is part of the page: one frame has both the lesson and the
marks, which is what somebody means by "save this".
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = io.open(os.path.join(ROOT, "craxlearn.html"), encoding="utf-8").read()
P, F = [], []


def ck(n, c, d=""):
    print(("PASS " if c else "FAIL ") + n + (f" — {d}" if d else ""),
          flush=True)
    (P if c else F).append(n)


print("\nthere is a sheet over the whole board")
ck("the layer exists", 'id="inkLayer"' in SRC)
ck("it covers everything", re.search(r"#inkLayer\{[^}]*position:fixed;inset:0", SRC)
   is not None)
ck("and it is ABOVE the panes",
   re.search(r"#inkLayer\{[^}]*z-index:70", SRC) is not None)

print("\nand it is inert until switched on")
ck("clicks pass straight through by default",
   re.search(r"#inkLayer\{[^}]*pointer-events:none", SRC) is not None,
   "a full-screen sheet that swallowed clicks would kill the board silently")
ck("and only take when it is on",
   "#inkLayer.on{pointer-events:auto" in SRC)
ck("every handler checks that too", SRC.count("if(!on) return;") >= 1,
   "the class and the handler must agree, or a stale class leaves a dead board")

print("\nthe bar is pinned to the bottom, where a hand is")
ck("fixed to the bottom",
   re.search(r"#inkBar\{[^}]*bottom:0", SRC) is not None)
ck("across the whole width",
   re.search(r"#inkBar\{[^}]*left:0;right:0", SRC) is not None)
ck("hidden until the pen is out", "#inkBar.on{display:flex}" in SRC)
ck("and the page is given room so the bar does not sit on its last line",
   "body.inking{padding-bottom" in SRC)

print("\nnot on the code screen")
ck("the gate marks the body",
   'classList.toggle("gated", !signedIn)' in SRC)
# Each is checked on its own rather than as one exact list. The list has
# since grown — the split, the screenshot, the pane-head fold, Home and sign
# out all act on a board that does not exist yet either — and a test pinned
# to the whole string fails on a change it does not care about, which reads
# exactly like the pen having come back.
ck("the pen, the sheet and the bar are all withdrawn there",
   all(("body.gated #" + x) in SRC
       for x in ("inkBtn", "inkLayer", "inkBar")),
   "a control that does nothing is worse than one that is not there")
ck("in a rule that hides them", "{display:none}" in SRC)
ck("opening a board clears it", 'classList.remove("gated")' in SRC)
ck("going back to the code screen puts the pen away",
   'classList.add("gated")' in SRC and "Ink.close();" in SRC,
   "signing out and back in must not return to a screen that swallows taps")

print("\nthe marks themselves")
ck("undo is there", 'data-ink="undo"' in SRC)
ck("and redo", 'data-ink="redo"' in SRC)
ck("clear is undoable, like the writing space's",
   "undone.unshift.apply(undone, strokes.slice().reverse());" in SRC,
   "it is one tap away from a lesson's worth of annotation")
ck("a tap makes a dot", "live.p[0][0] + 0.01" in SRC,
   "a dot is a mark somebody meant to make")
ck("held-back stylus samples are read",
   "e.getCoalescedEvents ? e.getCoalescedEvents() : null" in SRC)
ck("and an empty coalesced list falls back to the event",
   "(held && held.length) ? held : [e]" in SRC,
   "an empty array is truthy; this is the bug that made every stroke a dot "
   "in the writing space")

print("\nthe bar folds away without putting the pen down")
# The writing space has a toolbar along the bottom of its pane and the pen's
# bar is fixed across the bottom of the SCREEN, so with both out they stack
# and which control belongs to which stops being obvious. Folding leaves a
# handle rather than closing: closing loses the ink, and somebody who wants
# the room to see the board does not want to lose what they drew.
ck("there is a fold control", 'data-ink="fold"' in SRC)
ck("folded, it is a handle and not a bar",
   "#inkBar.folded > *{display:none}" in SRC)
ck("the sheet still takes strokes while it is folded",
   "#inkBar.folded{padding:0;gap:0;background:transparent" in SRC,
   "the BAR stops taking presses, not the canvas")
ck("and the choice is remembered", 'localStorage.setItem("cl_inkbar"' in SRC,
   "a board is used the same way every lesson")

print("\nall four shapes, in one slot")
ck("one button, not four", 'data-ink="shape"' in SRC)
ck("cycling through freehand as well as the shapes",
   "function nextShape(){" in SRC and 'var order = [""].concat(' in SRC,
   "freehand has to be one tap away, not four")
ck("it uses the writing space's own shapes",
   "live.p = shapePoints(shape, anchor, at(e));" in SRC,
   "a straight line is a straight line on either surface, and a second "
   "vocabulary here would drift")
ck("the anchor is dropped when the stroke ends", "anchor = null;" in SRC,
   "or the next freehand stroke comes out as a shape")

print("\nthe space bars can be put away")
# Slimming them took 74px to 53, and 53 is still a row per space saying which
# tool is open — which a teacher mid-lesson already knows. Collapsed, each
# head is the 4px line that was its own bottom border, and that line is the
# way back.
ck("there is a control", 'id="headsBtn"' in SRC)
ck("collapsed, a head is its own border", "#panes.noheads .paneHead{height:4px"
   in SRC)
ck("which still shows which space is live",
   '#panes.noheads .pane[data-live="1"] .paneHead{border-bottom-color:'
   'var(--accent)}' in SRC,
   "the one thing the bar said that is not obvious from the content")
ck("dragging a head down puts them away",
   "if(ev.clientY - y0 > 24) setHeads(true);" in SRC,
   "the gesture somebody tries before finding a button")
ck("and a plain press is not a drag", "y0 = e.clientY;" in SRC)
ck("repainting does not undo the choice",
   '(headsHidden() ? " noheads" : "")' in SRC,
   "assigning className wholesale brought the bars back on every tool change")

print("\nsaving keeps what is UNDERNEATH as well as the marks")
ck("it goes through the screen capture", 'data-ink="save"' in SRC
   and "shoot()" in SRC,
   "the ink is part of the page, so one frame has the lesson and the marks")
ck("a captured frame can be kept on the class page",
   'id="shotKeep"' in SRC and "/api/craxlearn/board/file" in SRC,
   "a picture of the board is usually wanted by the class, not in a "
   "Downloads folder")
ck("dragging a rectangle selects rather than saves immediately",
   "picked = out;" in SRC,
   "there are two things to do with it now, and the drag should not choose")
ck("and with no rectangle, the whole frame is used",
   "keep(picked || src)" in SRC and "save(picked || src)" in SRC)

# A ring drawn round the third paragraph, and the third paragraph moving.
#
# The marks were kept in viewport coordinates: annotate a lesson, scroll, and
# the ring is round a different paragraph. And scrolling was locked outright
# while the pen was on, so the way to mark the next screenful was to turn the
# pen off, scroll, turn it on — and find the earlier marks in the wrong
# places. They travel with the document now.
_INK = io.open(os.path.join(ROOT, "ink.js"), encoding="utf-8").read()
print("\nmarks stay on what they were drawn on")
ck("strokes are captured in page coordinates",
   "x: e.clientX + sx(), y: e.clientY + sy()" in _INK)
ck("coalesced points too, or a stroke splits across two spaces",
   "x: evs[i].clientX + sx(), y: evs[i].clientY + sy()" in _INK)
ck("the eraser looks in the same space it drew in",
   "erase(e.clientX + sx(), e.clientY + sy())" in _INK,
   "a stroke laid down against one number and erased against another is a "
   "mark that cannot be rubbed out")
ck("and the canvas is drawn at the page's offset",
   "ctx.translate(-sx(), -sy());" in _INK)
ck("cleared before that translate, not after",
   _INK.index("ctx.clearRect(0, 0, innerWidth, innerHeight);")
   < _INK.index("ctx.translate(-sx(), -sy());"),
   "or scrolling smears a band of old marks along the leading edge")

print("\nand the page is no longer frozen under them")
ck("the pen does not lock scrolling",
   'document.documentElement.style.overflow = "";' in _INK
   and 'overflow = on ? "hidden"' not in _INK,
   "a lesson longer than a screen could only be marked one screenful at a "
   "time")
ck("scrolling repaints them", 'global.addEventListener("scroll"' in _INK)
ck("once a frame, not once an event",
   "global.requestAnimationFrame(function () { pending = false; redraw(); });"
   in _INK,
   "scroll fires far faster than a board paints")
ck("and passively, so it never fights the scroll it is following",
   "{ passive: true }" in _INK)

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
