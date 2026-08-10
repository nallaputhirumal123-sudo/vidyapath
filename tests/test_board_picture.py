"""A picture on the whiteboard, and the reason it cannot come straight from
Wikimedia.

A teacher puts up a diagram of the eye and labels it. That is the whole
feature, and it was the last thing on the board that could only be done by
holding a phone up to the screen.

**The proxy is not politeness.** A remote image drawn onto a canvas TAINTS
it, and a tainted canvas throws on toBlob and toDataURL. Drop a diagram
straight from upload.wikimedia.org and the board still looks right — and
then Save to the class and Download, the two things a teacher does at the
end of the lesson, both stop working with an error nobody can act on. Coming
back through our own origin, the bytes are same-origin and the board can
still be photographed. So this route exists for the export, not the fetch.

**And a proxy is an open door unless it is shut.** Without the allowlist,
`?url=` would make the server fetch anything in the world on its own behalf,
from inside the network the database is on. It takes the same host list the
lesson figures use. SVG is refused outright: it is an image everywhere else
and a document that can carry script here, and serving one from our own
origin is the exact shape of a stored XSS.

The board side is a mode, not a mood. Hit-testing pictures while the pen is
live would mean a teacher writing across a diagram drags the diagram
instead — so pictures are inert until the 🖼 is pressed and the pen is inert
while it is. One lit button, one answer to "what does dragging do".
"""
import io
import os
import sys
import time
import datetime as dt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"

import main                                        # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = io.open(os.path.join(ROOT, "craxlearn.html"), encoding="utf-8").read()
main.Base.metadata.create_all(bind=main.engine)
main._migrate_columns()
P, F = [], []


def ck(n, c, d=""):
    print(("PASS " if c else "FAIL ") + n + (f" — {d}" if d else ""),
          flush=True)
    (P if c else F).append(n)


u = str(int(time.time())) + str(os.getpid())
db = main.SessionLocal()
c = TestClient(main.app)
em = f"pic{u}@example.com"
c.post("/api/auth/signup",
       json={"name": "Pic Teacher", "email": em, "password": "PicPass1!"})
row = db.query(main.User).filter(main.User.email == em).first()
row.dob = dt.date(1990, 1, 1)
db.commit()

print("\nthe door is shut before anything is fetched")
# Each of these must be refused BEFORE the server makes any request. A proxy
# that validates after fetching has already done the thing it was guarding.
bad = [
    ("plain http", "http://upload.wikimedia.org/a.png"),
    ("somebody else's host", "https://evil.example.com/a.png"),
    ("a host that merely ends in the right letters",
     "https://notupload.wikimedia.org.evil.com/a.png"),
    ("the machine's own metadata service",
     "http://169.254.169.254/latest/meta-data/"),
    ("something on the box itself", "https://localhost:8012/admin"),
]
for name, url in bad:
    r = c.get("/api/craxlearn/picture", params={"url": url})
    ck(name + " is refused", r.status_code == 400, str(r.status_code))
ck("the allowlist is the lesson figures' own, not a second copy",
   "for h in _images._HOSTS" in
   io.open(os.path.join(ROOT, "main.py"), encoding="utf-8").read(),
   "two lists drift, and the one nobody is looking at is the one that lets "
   "something through")

print("\nand SVG does not come back through our origin")
_MAIN = io.open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
ck("only raster types are served",
   'kind not in ("image/png", "image/jpeg", "image/webp", "image/gif")'
   in _MAIN,
   "an SVG served from our own host is a document that can carry script")
ck("and there is a size ceiling", "12 * 1024 * 1024" in _MAIN,
   "a board is a classroom screen, not a photo library")

print("\nsigned out, it is not a fetching service for the internet at large")
anon = TestClient(main.app)
r = anon.get("/api/craxlearn/picture",
             params={"url": "https://upload.wikimedia.org/a.png"})
ck("no session, no proxy", r.status_code == 401, str(r.status_code))

print("\nthe board asks for its pictures through it, not around it")
ck("the fetch goes to our own origin",
   '"/api/craxlearn/picture?url=" +' in SRC)
ck("carrying the board's token", "headers: bhdr({})" in SRC)
ck("and the reason is written where the next person will look",
   "taints it" in SRC and "toBlob" in SRC,
   "this looks like a pointless hop until you know what it is for")
ck("the object URL is released after the image has decoded",
   "URL.revokeObjectURL(u);" in SRC,
   "revoking before decode gives a broken image on a slow board; never "
   "revoking leaks one per picture per lesson")
ck("a failure is not cached as permanent",
   'pr["catch"](function(){ delete PICBYTES[url]; });' in SRC,
   "the network comes back, and Place pressed again deserves a real second "
   "attempt")

print("\nwhat is on the board is one kind of thing, in one set of units")
ck("pictures live beside the ink and survive a split",
   "view: null, pics: [] }" in SRC,
   "rebuilding the panes must not take the diagram down")
ck("in board units, so they pan and zoom with everything else",
   "var pic = { url: url, x: VIEW.x + (vw - w2) / 2," in SRC)
ck("drawn under the ink, so labels go on top",
   SRC.index("paintPics(ctx,") < SRC.index("paintInk(ink,"),
   "a teacher labels a diagram, and the eraser must take the label off "
   "without punching a hole through the picture")
ck("and they count as something being on the board",
   "BOARD_INK.pics.forEach(function(p){" in SRC
   and "hit(p.x + p.w, p.y + p.h);" in SRC,
   "bounds() is what the empty-board guard reads: a board holding only a "
   "picture would have answered 'there is nothing here yet' to Save")
ck("Clear takes them too", "BOARD_INK.pics.length = 0;" in SRC,
   "leaving them means Clear visibly does not clear")

print("\nthe export is the reason for all of it")
ck("pictures are painted into the saved picture",
   "paintPics(c, scale, (-b[0] + pad) * scale," in SRC)
ck("in the same order as the screen",
   SRC.index("paintPics(c, scale,") < SRC.index("paintInk(lay.getContext"),
   "what is saved has to be what the room was looking at")

print("\narranging is a mode, and the button says which one you are in")
ck("pictures are inert until the drawer is open", "if(picking){" in SRC,
   "otherwise writing across a diagram drags the diagram")
ck("and the pen is inert while it is",
   "cv.style.cursor = picking ? \"move\"" in SRC)
ck("topmost picture wins an overlap",
   "for(var pi = BOARD_INK.pics.length - 1; pi >= 0; pi--)" in SRC,
   "the last one placed is the one on top and the one a finger meant")
ck("resizing keeps the catalogue's own aspect",
   "var ratio = bx[3] / bx[2];" in SRC,
   "two free axes means a squashed diagram nobody can undo")
ck("Delete takes the selected one off",
   "BOARD_INK.pics.splice(i, 1);" in SRC)
ck("but not while the search box is being typed into",
   '/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)' in SRC,
   "or backspacing a search term removes the diagram behind it")
ck("and the key listener removes itself with the pane",
   'document.removeEventListener("keydown", picKey);' in SRC,
   "a listener left by a closed pane eats Delete in every box on the board")

print("\nthe licence comes with the picture, as everywhere else")
ck("credited under the result",
   'esc(d.photo.author)' in SRC and 'esc(d.photo.license)' in SRC)

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\nPASSED {len(P)}   FAILED {len(F)}")
sys.exit(1 if F else 0)
