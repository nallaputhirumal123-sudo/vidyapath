"""The three things to look at, for the person doing the learning.

A 3D viewer, the PhET catalogue and a picture search have been in the
classroom board's tool menu since it shipped. On craxle.com itself — the
side a student opens on their own device, at home, the evening before the
test — there were none of the three. They existed only in the room where a
teacher was standing.

That is the wrong way round for the 3D one in particular. A molecule you can
turn over is the thing a printed diagram cannot be, and the person who needs
to turn it is the learner, not the room. So the same three sit under the
smart board on the site: same routes, same catalogues, same licence line
printed underneath, no model call and no new server work.

Two mechanical things this pins, because both are the kind that break
quietly:

The panel is drawn by its own function into its own container. renderAsk()
replaces the whole section on every level change and every sample question —
a WebGL canvas mounted inside that markup would be destroyed and rebuilt
each time, throwing away whatever the learner had turned the molecule to.

And mounting is guarded on the canvas already being there. Three3D.mount()
appends; called twice into the same host, the panel ends up with two scenes
stacked, the second one on top and the first one still spinning underneath.
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX = io.open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
P = F = 0


def ck(name, cond, note=""):
    global P, F
    print(("  PASS  " if cond else "  FAIL  ") + name +
          (f" ({note})" if note else ""), flush=True)
    if cond:
        P += 1
    else:
        F += 1


print("\nthree chips under the board, on the student's own side")
ck("a 3D structure", 'data-look="scene"' in IDX,
   "the one that cannot be a picture in a book")
ck("a simulation", 'data-look="sim"' in IDX)
ck("a picture", 'data-look="pic"' in IDX)
ck("and they are not gated behind having asked a question first",
   IDX.index('data-look="scene"') < IDX.index("${hasLesson&&!sbOn?"),
   "the row above them appears only once a lesson is on the board; a "
   "student wanting to look at benzene has not asked anything yet")

print("\nreusing the board's routes rather than inventing any")
ck("the measured structure", '"/api/craxlearn/structure?name="' in IDX)
ck("the PhET catalogue", '"/api/craxlearn/phet"' in IDX)
ck("the open picture search", '"/api/craxlearn/search?q="' in IDX)

print("\nand the licence travels with what it licenses")
# images.py returns caption / author / license / page. Both the board's
# picture search and the lesson pages read title / credit / licence — all
# three undefined, so the line under a CC BY photograph rendered empty and
# the picture went up with no credit at all. A licence that does not print
# is a licence that is not being honoured, and this is a tool whose own
# subtitle promises "with the licence beside each result".
_BRD = io.open(os.path.join(ROOT, "craxlearn.html"), encoding="utf-8").read()
ck("the photograph's author and licence, on the site",
   'o.photo.license?" · "+esc(o.photo.license)' in IDX
   and 'esc(o.photo.caption||"")' in IDX)
ck("on the board's picture search",
   'esc(d.photo.caption || "")' in _BRD
   and '(d.photo.license ? " · " + esc(d.photo.license) : "")' in _BRD)
ck("and on a lesson's lead picture",
   'esc(L.photo.caption || "")' in _BRD
   and '(L.photo.license ? " · " + esc(L.photo.license) : "")' in _BRD)
ck("no reader is left on the old field names",
   "photo.credit" not in IDX and "photo.credit" not in _BRD
   and "photo.licence" not in IDX and "photo.licence" not in _BRD,
   "they are not errors — they are undefined, which renders as nothing")
ck("and the source page is linkable, so a claim can be checked",
   'rel="noopener">source</a>' in IDX and "source</a>" in _BRD)
ck("PhET's, under the simulation", "esc(o.licence||\"\")" in IDX)
ck("and the structures say they are measured, not drawn",
   "Measured, not drawn" in IDX)

print("\nthe canvas survives a redraw of the section around it")
ck("the panel has its own container", 'id="lookWrap"' in IDX)
ck("and its own draw, not renderAsk's",
   "function renderLook(){" in IDX,
   "renderAsk() replaces the whole section on every level change")
ck("which is called again after that redraw",
   IDX.count("renderLook();") >= 1 and "  renderLook();\n}" in IDX,
   "or an open panel goes blank behind a chip that still looks pressed")
ck("mounting is refused when a canvas is already there",
   'if(out.querySelector("canvas")) return;' in IDX,
   "Three3D.mount appends — twice gives two scenes, one spinning unseen "
   "under the other")
ck("and a blocked CDN says so instead of showing an empty box",
   "The 3D\n        viewer could not load" in IDX,
   "an empty box reads as broken software rather than a blocked network")

print("\nsmall things that are dead ends when they are missing")
ck("a two-letter query is refused with a reason, not silently",
   "Type the name of the thing itself" in IDX)
ck("nothing found says what to try instead",
   "Try the plain name of the " in IDX)
ck("the simulation list marks the one on screen",
   ".ask-samp.on{" in IDX,
   "identical pills with no mark is a row you cannot read your place in")
ck("and pressing an open chip closes it",
   'LOOK.open = LOOK.open===kind ? "" : kind;' in IDX)

print(f"\nPASSED {P}   FAILED {F}")
sys.exit(1 if F else 0)
