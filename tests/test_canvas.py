"""A board with no edges, and the four bugs that hid behind a blank screen.

A lesson is longer than a screen. The writing space was a fixed rectangle
that fitted itself into the pane, so a teacher working through a derivation
filled it and then had to rub out the beginning of the working to write the
end — which is the one moment a child looks up and needs the beginning.

It is a plane now: strokes in world coordinates with no bounds, and the
screen a window onto it with an offset and a scale. Everything else follows
from that one change, which is why it was not a rewrite — `world → screen`
used to be a constant and is now a function.

The reason this file exists is what turning it on uncovered. The writing
space had been quietly broken for weeks and nobody could tell, because the
whole page had been broken for longer, and every fault below PARSES:

  * SHAPES was named in the markup on write()'s first line and declared with
    `var` further down. The name hoisted; the value did not. The toolbar
    threw before it was drawn.
  * The pane grabbed #wCanvas by id. With the writing space open in two
    spaces, both closures took the FIRST canvas — every stroke recorded
    twice, second board dead.
  * getCoalescedEvents returns an EMPTY ARRAY for events the browser did not
    generate, and `|| [e]` does not fire on an empty array. Every stroke came
    out as the dot from pointerdown.
  * The grid loop multiplies until the spacing looks right. Fit computes its
    scale from the size of what is on the board, and a mark with no width
    makes that scale zero — a loop with no exit, and the board is gone
    mid-lesson.

Source-level, like test_board_tiles: what is pinned is that these four
cannot come back silently. The behaviour itself was driven in a browser.
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


print("\nthe surface has no edges")
ck("strokes are kept in world coordinates, not board units",
   "var BOARD_UNIT = 1600;" in SRC and "BOARD_W" not in SRC,
   "BOARD_W was the width of a board that ended")
ck("the window is an offset and a scale",
   "VIEW = { k: w / BOARD_UNIT, x: 0, y: 0 }" in SRC)
ck("and it travels with the ink, so splitting a space comes back here",
   "var BOARD_INK = { strokes: [], undone: [], view: null };" in SRC)
ck("a stroke that runs off the screen is NOT clamped to it",
   "Math.min(BOARD_W" not in SRC,
   "the clamp was the edge of the board, and there is no edge")

print("\nand a way back from anywhere")
ck("Fit is a button", 'id="wFit"' in SRC)
ck("built from the bounding box of every mark", "function bounds()" in SRC)
ck("zoom holds the point under the fingers", "function zoomAt(" in SRC)
ck("two fingers pan and pinch together", "pinch = { d: d, c: c };" in SRC)
ck("a wheel scrolls and ctrl-wheel zooms",
   "if(e.ctrlKey || e.metaKey){" in SRC)
ck("and ✋ is a TOOL, not only a gesture", 'id="wHand"' in SRC,
   "a wall-mounted board with a stylus has no wheel and no second finger")
ck("there is somewhere that says where you are", 'id="wWhere"' in SRC)

print("\nthe toolbar is at the bottom, where a hand is")
i_surf = SRC.index('<div class="wsurf" id="wSurf">')
i_tools = SRC.index('<div id="wTools" class="wtools">')
ck("the surface is written before the tools", i_surf < i_tools,
   "the top of a wall-mounted screen is above head height")
ck("it is a solid bar, not a variable that might be transparent",
   "background:#101823" in SRC)
ck("and it holds Ask Axle, so a teacher need not go home for it",
   'id="wAsk"' in SRC)

print("\nthe four that parsed and were still wrong")
ck("SHAPES is declared before the markup that names it",
   SRC.index("var SHAPES = [") < SRC.index("function write(){"),
   "hoisting lifts the name and not the value")
ck("the pane finds its own canvas rather than the document's first",
   'function wq(id){ return host.querySelector("#" + id); }' in SRC,
   "ids are unique per pane, not per document")
ck("and that helper is not named over a local",
   "function w(id){" not in SRC,
   "redraw() already uses w for the canvas width")
ck("an empty coalesced list falls back to the event itself",
   "var pts = (held && held.length) ? held : [e];" in SRC,
   "an empty array is truthy, so || [e] never ran")
ck("the grid refuses a scale that would loop forever",
   "if(!(VIEW.k > 0) || !isFinite(VIEW.k)) return;" in SRC)
ck("and Fit cannot produce one",
   "if(!(k > 0) || !isFinite(k)) k = base;" in SRC)
ck("a finished stroke repaints, so the board does not say 0 marks",
   re.search(r"live = null;\s*/\*[^*]*(?:\*(?!/)[^*]*)*\*/\s*redraw\(\);",
             SRC) is not None)

print("\nrubbing out reaches ink and nothing else")
ck("strokes are composited from their own layer",
   "var inkc = document.createElement(\"canvas\");" in SRC,
   "destination-out on one layer cuts through the background and the grid")
ck("and the export does the same",
   "var lay = document.createElement(\"canvas\");" in SRC,
   "or an eraser stroke punches a transparent hole in the saved picture")

print("\nwhat is saved is the working, not the window")
ck("the picture is taken from the bounds of every mark",
   "function shotCanvas()" in SRC and "var b = bounds() ||" in SRC,
   "saving the screen would lose the half of the derivation off to the left")
ck("and it is capped, because an endless board holds an endless amount",
   "var SHOT_MAX = 4200;" in SRC)

print("\nthe grid is off unless somebody asks for it")
# It answered a real problem — panning an empty part of an endless surface
# looks exactly like a board that has stopped responding — and it solved that
# at the cost of the thing the board is for. A page of working written over
# graph paper is a page of graph paper. Fit, the zoom readout and the mark
# count answer "where am I" well enough on their own.
ck("off by default",
   'localStorage.getItem("cl_grid") === "1"' in SRC,
   "absent means off, so a board nobody has configured is clean")
ck("there is a switch", 'id="wGrid"' in SRC)
ck("and the choice is remembered", 'localStorage.setItem("cl_grid"' in SRC,
   "it is a property of how a room teaches, not of one lesson")
ck("both draw paths honour it", SRC.count("if(gridOn()) paintGrid") == 2,
   "the fast path that paints a single stroke repaints the background too")
ck("but the grid itself is kept, not deleted",
   "function paintGrid(c, w, h)" in SRC,
   "it genuinely helps for plotting axes and drawing to scale")

print("\nthe tool bar gives way, and the board does not")
# This has been wrong in both directions, so the rule is written down here
# rather than left in the CSS to be re-derived.
#
# It began as a surface with a 9rem floor that refused to shrink, which
# pushed the wrapped toolbar out of the bottom of a pane that clips — "Save
# to the class is not working", when the button was simply 211 pixels below
# the visible area. Making the surface yield instead put the fault the other
# way up: in a 394px pane the tools wrapped into 245 pixels of rows on a
# board 256 tall, the canvas came out 452x2, and nothing could be written on
# it at all.
#
# Three attempts in between are worth not repeating. A media query on the
# WINDOW width does not help, because wrapping depends on the PANE's width —
# a board split three ways at 1440px still gave 211 pixels of tools against a
# 182-pixel surface. Forcing one sideways-scrolling row fixed the height
# everywhere and hid controls behind a scroll on a full-width board, where
# there was no problem to solve. And a fixed rem ceiling bites on a real
# board, which runs at a 26px root font.
#
# What settles it is an order of precedence: the surface keeps a floor, the
# BAR is what may shrink, and it scrolls inside itself once it has. Measured
# after: one pane 78% surface with every row visible, three panes 65% with
# the bar shrunk to 84px, a phone 58% and writable.
ck("the surface has a floor it cannot go below",
   ".wsurf{flex:1 1 0;min-height:7rem;position:relative}" in SRC,
   "min-height:0 let it collapse to two pixels the moment the bar grew")
ck("and the BAR is what gives way",
   "flex:0 1 auto;min-height:2.6rem;overflow-y:auto" in SRC,
   "flex:0 0 auto made the bar immovable, so the board gave way instead")
ck("it still wraps, so nothing hides when there is room",
   ".wtools{display:flex;gap:.35rem;flex-wrap:wrap" in SRC,
   "on a full-width board every control was visible and should stay so")
ck("with a scroll as the last resort, so nothing is ever unreachable",
   "gap:.5rem;overflow-y:auto}" in SRC,
   "clipping loses the control; scrolling only moves it")

print("\nwriting keeps up with the pen")
# Two costs, both paid on EVERY pointer sample, and a stylus reports about a
# hundred and twenty a second.
#
# getBoundingClientRect forces the browser to settle the layout before it can
# answer — measured at 0.462ms here, so the board was doing over a hundred
# forced reflows a second while somebody wrote. And the composite underneath
# the new segment redrew the background, the grid and the whole ink layer:
# 0.048ms on a laptop pane, and roughly nine times that on a 4K wall screen.
ck("the canvas rect is cached, not asked for per sample",
   "var RECT = null;" in SRC and "function rect(){" in SRC,
   "a forced reflow per stylus sample is most of what 'lagging behind the "
   "pen' was")
ck("and dropped when the pane moves under it",
   "RECT = null;\n    DPR = window.devicePixelRatio" in SRC,
   "splitting the board resizes a pane without resizing the window, and a "
   "stale rect puts every later stroke at an offset")
ck("the composite is paced to the display",
   "frame = requestAnimationFrame(function(){" in SRC,
   "120 samples a second against a screen that shows 60")
ck("but every sample is still drawn onto the layer",
   "ink.globalCompositeOperation = live.e" in SRC,
   "only the SHOWING is paced; nothing is dropped from the stroke")
ck("and a frame already booked is not booked twice",
   "if(frame) return;" in SRC)

print("\nthe board ends where the screen ends")
# `#panes` was `height: calc(100vh - 4rem)`, and both halves of that were
# wrong on a phone. The header WRAPS to two rows on a narrow screen — 124px
# against the 76px being subtracted — so the panes were 48px taller than the
# screen and .pane's overflow:hidden cut the bottom off. And 100vh on a phone
# is the height with the browser's own bars HIDDEN, which is not the height
# anything is being read at, so the real overflow was worse again. Half an
# explanation went missing.
ck("nothing subtracts a guess at the header's height",
   "calc(100vh - 4rem)" not in SRC,
   "the header is 102px on a laptop and 124px wrapped on a phone")
ck("the page is a column of exactly the screen",
   "height:100vh; height:100dvh;" in SRC,
   "dvh tracks the viewport the browser is actually showing")
ck("and the panes take what is left",
   "flex:1 1 auto; min-height:0}" in SRC)
ck("the header is not squeezed to make room", "flex:0 0 auto;\n}" in SRC)
ck("and the code screen scrolls rather than being clipped",
   "#gate{flex:1 1 auto; min-height:0; overflow-y:auto}" in SRC,
   "it is taller than a phone with the keyboard up")

print("\na phone is not a wall")
# Board size is 26px because a wall-mounted screen is read from the back of a
# room, every measurement here is in rem, and "board" is the DEFAULT. On a
# 375px phone that left the writing surface 38% of its pane — measured — with
# the top bar, pane head and tool rows taking the rest. It is 61% now.
ck("board size is brought back on a small screen",
   '@media (max-width:600px){\n  :root[data-scale="board"]{ font-size:19px }'
   in SRC,
   "26px on a 390px phone spends the screen on chrome")
ck("and desk size with it", ':root[data-scale="desk"]{ font-size:16px }\n}'
   in SRC)
ck("but the choice itself is still the teacher's, not guessed from width",
   'localStorage.getItem("cl_scale") || "board"' in SRC,
   "a smart board reports a perfectly ordinary 1920 and must not get "
   "laptop type")

print("\nthe vertical divider divides something")
# Three spaces put the third across the whole bottom, and a handle pinned
# top-to-bottom drew a line straight down through it — a divider drawn over a
# pane that is not divided.
ck("it stops at the row divider when the bottom pane is full width",
   'v.style.bottom = (n === 3) ? ((1 - ROWS) * 100) + "%" : "0";' in SRC,
   "and it tracks ROWS, because layout() reruns on every drag")

print("\nthe writing space cannot be squeezed to nothing")
ck("the board takes the space rather than its own content height",
   ".wboard{flex:1 1 0;" in SRC)
ck("and nothing else competes with it in the pane",
   "signInPrompt(\"keep this on your subject's page\")" not in SRC,
   "the pane cannot scroll, so anything below the board takes its height")

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
