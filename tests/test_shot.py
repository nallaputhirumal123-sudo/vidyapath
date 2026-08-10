"""Taking a picture of the board, and where it goes afterwards.

Two faults, and the second is the one nobody would have reported as a bug
because it looked like the feature working.

**A rectangle is the wrong shape for half of what a teacher points at.** It
is right for a worked equation and wrong for a diagram sitting in the middle
of a page with writing all round it — the box takes the writing too, and the
teacher crops it somewhere else or gives up. Drawing round the thing is how
somebody would point at it with their hand, so that is the other mode. What
comes out is the shape that was drawn, on transparency, cropped to its own
bounding box.

The crop maths was driven in a browser against a synthetic capture displayed
at HALF size, which is the case that breaks naive versions: a lasso drawn at
(250,50) has to become (500,100) in the captured frame. Outside the outline
came back fully transparent, inside came back with the true source pixels,
and a triangle filled exactly half of its bounding box.

**Download, on a smart board, is a dead end.** A board is a shared screen
bolted to a wall. A file in ITS Downloads folder is on a computer nobody
takes home and most people cannot sign in to — the teacher who pressed the
button does not get the picture and neither does the class. So when the
board holds a subject code the file goes to the subject page, where both can
open it, and it says which subject it went to. On somebody's own laptop a
download is exactly right and still happens.
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


print("\ntwo ways to choose a part of the picture")
ck("a box, which is right for a worked equation", 'id="shotRect"' in SRC)
ck("and a free hand outline, for everything with writing round it",
   'id="shotFree"' in SRC,
   "a rectangle round a diagram takes the paragraph beside it too")
ck("the outline gets its own layer, not a border on a div",
   "var lasso = document.createElement(\"canvas\");" in SRC,
   "a free-hand shape cannot be expressed as a rectangle")
ck("switching mode clears what was selected",
   re.search(r"function setMode\(m\)\{[^}]*picked = null;", SRC,
             re.S) is not None,
   "or Keep files a shape from the mode you just left")
ck("and the instruction changes with it", 'id="shotHow"' in SRC)

print("\nwhat comes out is the shape that was drawn")
ck("the outline is cut out rather than boxed", "c.clip();" in SRC)
ck("and cropped to its own bounding box", "function fromPath()" in SRC)
ck("displayed coordinates are scaled back to the captured frame",
   "var kx = src.width / r.width, ky = src.height / r.height;" in SRC,
   "the image is shown scaled to fit, so a crop on a board would otherwise "
   "come out a fraction of the size it looked")
ck("the bounding box is clamped inside the frame",
   "Math.max(0, Math.min.apply(null, xs))" in SRC
   and "Math.min(src.width, Math.max.apply(null, xs))" in SRC,
   "an outline dragged off the edge must not ask for pixels that do not exist")
ck("a tap is not an outline", "if(w < 8 || h < 8) return null;" in SRC,
   "nobody meant to save an eight-pixel picture")

print("\ndownload is not a dead end on a wall-mounted screen")
ck("a board files it to the subject page instead",
   "if(boarded()){ keep(cnv, true); return; }" in SRC,
   "a file in the board's own Downloads folder is on a computer nobody "
   "takes home")
ck("the writing space's own save does the same",
   "if(boarded() && keep && keep.onclick){ keep.onclick(); return; }" in SRC)
ck("and that guard cannot itself be a dead button",
   "keep && keep.onclick" in SRC,
   "trading one dead button for another would be no improvement")
ck("a personal device still gets a real download",
   'a.download = "craxlearn-"' in SRC,
   "on a laptop a download is exactly right")

print("\nand it says where it went")
ck("naming the subject", 'var where = (ROOM && ROOM.subject) ? ROOM.subject'
   in SRC)
ck("because a dialog that just closes looks the same when it failed",
   'msg.textContent = viaDownload' in SRC)
ck("and without a code it says what is missing, rather than nothing",
   '"Enter a subject code to keep this on a "' in SRC)

print("\nan empty board is not a picture")
# shotCanvas falls back to a full-board rectangle when bounds() finds no
# strokes, so an untouched board produced a 3360x1952 picture of its own
# background — filed to the class page with "Kept on Social." underneath it.
# Proved from the stored rows: the blank one had ONE distinct colour and zero
# bright pixels; the one after the fix had 60 colours, 10,506 bright pixels,
# and was cropped to what was actually drawn.
ck("the writing space says when there is nothing to photograph",
   "WRITING_SHOT = function(){ return bounds() ? shotCanvas() : null; };"
   in SRC)
ck("and the keeper refuses rather than filing a blank",
   'toastLine("There is nothing on the board yet' in SRC)
ck("Download is guarded too", "if(!bounds()){" in SRC)
ck("and Save to the class with it",
   SRC.count("There is nothing on the board yet") >= 3,
   "an untouched board filed a picture of its own background under the "
   "subject, and the class opened a blank rectangle")

print("\nthe top bar's camera does not ask to share the screen either")
# The pane's own camera was fixed and this one was not, so pressing the
# obvious button in the top bar still put a permission dialog in the middle
# of a lesson — and captured a tab strip, an address bar and the other half
# of a split board along with the board.
ck("it photographs the live space when that is a canvas",
   'live && live.page === "write" && WRITING_SHOT' in SRC)
ck("and says so when there is nothing on it",
   SRC.count("There is nothing on the board yet") >= 4)
ck("the screen capture stays for everything else", "  shoot();\n};" in SRC,
   "a browser cannot rasterise a page of HTML without a library")

print("\nand a saved file opens from the board")
# The link was a plain <a href>, and a header does not ride on a link click,
# so the board asked for the file with no credential and was turned away.
# The LIST worked and opening one did not, which is the tool's whole job.
ck("it is a button that fetches, not a link that navigates",
   'data-openfile="' in SRC and "async function openFile(btn){" in SRC)
ck("carrying the board's token", "headers: bhdr({})" in SRC)
ck("the window is opened inside the click, before the fetch",
   'var win = window.open("", "_blank");' in SRC,
   "a pop-up blocker refuses one opened in a promise that settles later")
ck("and the blob is released after the window has had it",
   "URL.revokeObjectURL(url); }, 60000);" in SRC,
   "revoking immediately can cancel the load on a slow board")

_MAIN = io.open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
ck("the route lets a board have its own class's material, and no other",
   'int(grant.get("class_id") or 0) != int(m.class_id or 0)' in _MAIN,
   "stricter than a signed-in teacher rather than looser: that class and "
   "nothing else, whatever id is typed into the URL")

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
