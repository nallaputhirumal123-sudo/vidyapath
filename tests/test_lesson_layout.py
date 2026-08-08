"""A chapter's own diagrams reach the class board, and a lesson has a shape.

Two complaints, one cause. The board was "all text, no images or sketches",
and a converted PDF read as "a wall of steps".

The images were thrown away on purpose. teachpdf said so in its own
docstring: pictures inside a PDF are compressed, often scanned, and look
worse projected than they did on paper. True of some of them, and the wrong
rule — it threw away the case that matters most. A chapter about a ray
diagram, a circuit or a labelled cell is not that lesson with the picture
removed; it is a paragraph about a picture nobody can see.

The wall was a rendering decision. Every line came out as a bullet of the
same size, so a page had no shape: nothing bigger than anything else, the eye
with nowhere to land, and a room being taught from it unable to tell which of
six lines was the point.

Both halves are pinned here, and the path between them is the part that
actually broke: a picture extracted on the teacher's screen has to survive
being flattened into a Material row and come back out on the board. It did
not — `_lesson_figures` knew about drawings and 3D and nothing else — so the
teacher saw the diagram and the class did not.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"

import main                                        # noqa: E402
import teachpdf                                    # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRX = io.open(os.path.join(ROOT, "craxlearn.html"), encoding="utf-8").read()
IDX = io.open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
P, F = [], []


def ck(n, c, d=""):
    print(("PASS " if c else "FAIL ") + n + (f" — {d}" if d else ""),
          flush=True)
    (P if c else F).append(n)


print("\nthe document's pictures are extracted")
ck("there is a extractor at all", hasattr(teachpdf, "pictures"))
ck("and the docstring no longer says they are not worth keeping",
   "not worth keeping" not in teachpdf.__doc__,
   "the rule changed; the file has to say so or the next person restores it")

# The furniture filter, which is what makes keeping them tolerable: a real
# document is full of rules, logos and background panels.
try:
    from PIL import Image
    ck("a rule is not a diagram",
       not teachpdf._worth_showing(Image.new("RGB", (900, 6), "grey")),
       "thin enough to be a border")
    ck("a logo is not a diagram",
       not teachpdf._worth_showing(Image.new("RGB", (48, 48), "orange")),
       "too small to be anything else")
    ck("a flat panel is not a diagram",
       not teachpdf._worth_showing(Image.new("RGB", (600, 400), (248,) * 3)),
       "one colour is a background, not a picture")
    _real = Image.new("RGB", (900, 520), "white")
    for _x in range(0, 900, 7):
        _real.putpixel((_x, _x % 520), (0, 0, 0))
    ck("but a drawing is", teachpdf._worth_showing(_real))
except Exception as e:
    ck("the filter is testable", False, f"{type(e).__name__}: {e}")

print("\nand they survive the trip to the class board")
# This is the join that was missing. A lesson is flattened into a Material
# row to be saved, and the flattener knew about drawings and 3D scenes only.
figs = main._lesson_figures({"steps": [], "pictures": [
    {"src": "data:image/png;base64,iVBORw0KGgo=", "page": 3}]})
ck("a picture is kept beside the words", '"how": "pic"' in figs, figs[:90])
ck("with the page it came from", '"page": 3' in figs, figs[:90])

# It is stored and then handed to every child in the class, and `src` is the
# one field on that page a browser will go and fetch or execute for.
bad = main._lesson_figures({"steps": [], "pictures": [
    {"src": "javascript:alert(1)", "page": 1},
    {"src": "https://example.invalid/x.png", "page": 1},
    {"src": "data:image/svg+xml;base64,PHN2Zz4=", "page": 1},
    {"src": "data:text/html;base64,PGgxPmhpPC9oMT4=", "page": 1},
]})
ck("and nothing that is not base64 image data gets through", bad == "",
   "a src is not safe because we wrote the extractor — the lesson has been "
   "round a browser by the time it arrives here")

print("\nboth screens draw a stored figure the same way")
ck("through one function", "function figureHTML(f, id)" in CRX)
ck("used by the class's material list",
   'figureHTML(f, "mFig" + m.id + "_" + i)' in CRX)
ck("and by the board's shelf", "figureHTML(f, f.id)" in CRX)
ck("and a picture is not handed to a renderer that would fail on it",
   'if(f.how === "pic") continue;' in CRX,
   "there is nothing to mount; it is already an <img>")

print("\na lesson reads like something written")
for name, src in (("the board", CRX), ("craxle.com", IDX)):
    ck(f"{name} has headings", ".lh{" in src or ".sb-h{" in src)
    ck(f"{name} has a lead paragraph", ".lead{" in src or ".sb-lead{" in src)
ck("the board classifies lines rather than bulleting all of them",
   "function lessonProse(text)" in CRX)
ck("and a formula is not mistaken for a heading",
   "function lessonIsHeading(ln)" in CRX
   and "≤≥" in CRX or "lessonIsHeading" in CRX,
   "n = c / v is the line a student came for, not a section title")
ck("a numbered step heading is a heading, not a bullet",
   "if(numbered && lessonIsHeading(rest))" in CRX,
   "_lesson_to_body numbers the steps, and the number was eating the "
   "heading")

print("\nthe viewer is big enough to see into")
ck("the board's 3D scales with the screen",
   re.search(r"\.fig3d\{[^}]*min-height:clamp\(", CRX) is not None,
   "16:10 in a narrow column is a letterbox")
ck("and so does the Pro board's",
   re.search(r"\.sb-scene\{[^}]*min-height:clamp\(", IDX) is not None)

print("\nand the outline says what a step is")
ck("the name is not sliced mid-word",
   '(st.where||st.t||"").slice(' not in IDX
   and "esc(sbStepName(st))" in IDX,
   "a step called 'Total internal reflection and the critical angle' showed "
   "as 'Total internal reflec…' — cut once by a slice and again by an "
   "ellipsis, so the outline that exists to say where a room is said nothing")
ck("it wraps instead of being clipped to one line",
   re.search(r"\.sb-ol\{[^}]*white-space:normal", IDX) is not None)
ck("and it is taken from the step's own first line",
   "function sbStepName(st)" in IDX)

TPDF = io.open(os.path.join(ROOT, "teachpdf.py"), encoding="utf-8").read()
IMG = io.open(os.path.join(ROOT, "images.py"), encoding="utf-8").read()
MAIN = io.open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
_i = MAIN.index("async def teach_from_pdf")
# To the end of the function rather than a fixed number of characters. A
# window measured in bytes fails the moment anybody adds a paragraph to the
# route — which is a test breaking on a change it does not care about, and it
# reads exactly like the property having been removed.
_j = MAIN.index("\n@app.", _i)
_PDFROUTE = MAIN[_i:_j]

print("\nthe page a picture came from is the page that DREW it")
# `page.images` walks /Resources, and a resource dictionary is very often
# shared by every page of a chapter — so a forty-page textbook reported every
# figure on all forty, and the survivor of the de-duplication kept whichever
# page was enumerated first. The page number decides where in the lesson a
# picture appears, so taking it from the wrong place put a whole chapter's
# figures on one step.
ck("the content stream is read, not the resource list",
   "def _drawn_on(page)" in TPDF,
   "a page's content stream says what it paints: /Im1 Do")
ck("and /Resources is still the fallback", "imgs = list(page.images)" in TPDF,
   "an unreadable stream should cost the page number, not the picture")

print("\nthe picture search matches more than a few words")
import images as _im                                # noqa: E402
CASES = [
    ("refraction of light", ["Light", "Refraction"], "Refraction",
     "a prepositional phrase qualifies what came BEFORE it"),
    ("plant cell structure", ["Structure", "Plant cell"], "Plant cell",
     "a generic tail noun is not the subject"),
    ("aircraft gearbox", ["Nimitz-class aircraft carrier", "Gearbox"],
     "Gearbox", "sharing a word is not being the same object"),
    ("total internal reflection",
     ["Reflection (physics)", "Total internal reflection"],
     "Total internal reflection", "more words matched is a better answer"),
]
for _q, _titles, _want, _why in CASES:
    _ranked = sorted(((_im.score(_q, t), t) for t in _titles), reverse=True)
    _top = [t for sc, t in _ranked if sc >= _im.SCORE_FLOOR]
    ck(f"{_q!r} finds {_want!r}", bool(_top) and _top[0] == _want,
       f"{[t for _, t in _ranked]} — {_why}")
ck("and a picture of something else is refused outright",
   _im.score("aircraft gearbox", "Crane (machine)") == 0.0,
   "no picture is ordinary; the wrong machine teaches the wrong machine")
ck("the search asks for several candidates, not one",
   '"gsrlimit": "8"' in IMG)

print("\nevery step gets something to look at, or keeps its words")
ck("there is a pass that looks at every step", "async def _illustrate(" in MAIN)
ck("it skips a step that already has a drawing or a 3D scene",
   "def _has_visual(st)" in MAIN,
   "a drawn diagram beats a photograph and should not be replaced by one")
ck("and it widens the search rather than asking once",
   'tries.append(f"{head} {_images.subject_of(topic)}"[:120])' in MAIN,
   "asking once and giving up is what left a lesson with one picture")
ck("the same photograph is never used twice in one lesson",
   "if not url or url in have:" in MAIN)

print("\nand what leaves the building carries its licence")
ck("the print sheet shows the photographs", "const photoFig=(p)=>{" in IDX)
ck("and the document's own pictures", "const docPics=(k)=>allPics" in IDX)
ck("with author and licence on each",
   "[p.caption,p.author,p.license].filter(Boolean)" in IDX,
   "CC BY-SA is conditional on naming the author; a sheet without it is an "
   "unlicensed copy")
ck("the downloaded PDF embeds them too",
   "async function pdfImageData(src)" in IDX)
ck("and is built from one description of a lesson",
   "function pdfRecordOf(l, meta)" in IDX,
   "two copies of which fields go in is how one of them stops including "
   "the pictures")

print("\nthe same chapter gives the same lesson twice")
# Everywhere else a doubtful lesson is deliberately NOT cached: caching turns
# one wrong answer into everybody's wrong answer. That is the wrong trade for
# a teacher's own document. The key is a hash of the FILE, so not caching
# meant the same PDF produced a different write-up on every upload — and a
# teacher prepares against what they saw yesterday. A chapter that will not
# sit still cannot be prepared with.
ck("a PDF lesson is stored whatever the checker thought",
   'if verdict["cache"]:' not in _PDFROUTE,
   "re-rolling the dice is not a safety property")
ck("keyed on the file itself", 'qkey = f"teachpdf|{digest}"' in MAIN,
   "one chapter, one lesson, however many people upload it")
ck("and the doubt rides along instead of being discarded",
   'lesson["confidence"] = verdict["confidence"]' in _PDFROUTE,
   "marked on the screen rather than silently regenerated behind it")

print("\nthe mark is on both halves of the product")
ck("the board", 'class="dot" src="/icon-192.png"' in CRX)
ck("and craxle.com", 'class="brand-mark" src="/icon-192.png"' in IDX)

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
