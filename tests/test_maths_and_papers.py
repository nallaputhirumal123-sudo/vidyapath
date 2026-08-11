"""Maths that looks like maths, and where the subject goes next.

**The board showed the commands instead of the equation.** mathText — which
turns a sqrt command into a root sign, a caret into a real superscript and a
frac into a stacked fraction — lived inside index.html. The classroom board
had no copy of any of it, so the same lesson rendered as an equation on a
pupil's phone and as raw LaTeX on the screen thirty children were reading
from. That is the whole of "the squares and the roots are missing".

It is one file now, loaded by both, because two copies of a formatter for
one lesson is a formatter that will disagree with itself.

Order matters and is pinned: escape FIRST, format SECOND. mathText emits
real tags — a stacked fraction is a span — so escaping afterwards would
print those tags at the class instead of the equation, and escaping first
means anything a lesson contains is inert before any markup of ours is
added.

**And a lesson can say where the subject goes.** A school lesson is bounded
by its syllabus and should be; but somebody in that room wants to know
whether there is more, and the honest answer is a real paper with an author
on it rather than a longer paragraph from a model.

arXiv, because its terms permit exactly this: a documented public API, no
key, asking only that clients identify themselves. Three things it is not:
it does not build the lesson, nothing from it reaches the model, and it is
not offered outside the fields it actually holds — a lesson on the Mughals
or the nephron gets nothing rather than something irrelevant.
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import papers                                      # noqa: E402

MATHJS = io.open(os.path.join(ROOT, "mathtext.js"), encoding="utf-8").read()
IDX = io.open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
BOARD = io.open(os.path.join(ROOT, "craxlearn.html"), encoding="utf-8").read()
MAIN = io.open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
P, F = [], []


def ck(n, c, d=""):
    print(("PASS " if c else "FAIL ") + n + (f" — {d}" if d else ""),
          flush=True)
    (P if c else F).append(n)


print("\none maths formatter, loaded by both screens")
ck("it is its own file", "function mathText(" in MATHJS)
ck("the website loads it", 'src="mathtext.js' in IDX)
ck("and the board loads it too", 'src="mathtext.js' in BOARD,
   "the board had no maths formatting at all — raw commands on a "
   "classroom screen")
ck("neither page keeps a second copy",
   "function mathText(" not in IDX and "function mathText(" not in BOARD,
   "two copies of one formatter is a formatter that disagrees with itself")

print("\nit covers what a lesson actually writes")
for name, needle in (("square roots", "sqrt"),
                     ("powers and indices", "msup"),
                     ("subscripts", "msub"),
                     ("stacked fractions", "mfrac"),
                     ("times, division, plus-or-minus", "times:"),
                     ("less-than-or-equal and friends", "leq:"),
                     ("greek letters", "theta:"),
                     ("set symbols", "mathbb")):
    ck(name + " are handled", needle in MATHJS)
ck("and a dollar sign that is money stays money",
   "looksMathy(inner)?inner:m" in MATHJS,
   'stripping every $ turned "profit is $3" into "profit is 3"')

print("\nthe board escapes first and formats second")
ck("one helper does both, in that order",
   'return (typeof mathText === "function") ? mathText(esc(x)) : esc(x);'
   in BOARD,
   "formatting first would let a lesson's own angle brackets become tags; "
   "escaping second would print our tags at the class")
ck("headings, list items and paragraphs all go through it",
   BOARD.count("M(") >= 6)
ck("and the stacked fraction has styles on the board",
   ".mfrac{display:inline-flex" in BOARD,
   "without them a numerator and denominator sit side by side, which reads "
   "as two numbers")

print("\nfurther reading, and only where there is any")
ck("arXiv is asked", "https://api" not in papers.API and "arxiv.org" in papers.API)
ck("the fields it holds are named", papers.in_scope("quantum entanglement")
   and papers.in_scope("graph theory") and papers.in_scope("machine learning"))
for out_of in ("the Mughal empire", "the nephron", "photosynthesis",
               "Shakespeare's sonnets", "the Indian Constitution"):
    ck(f"{out_of} is not asked about", not papers.in_scope(out_of),
       "arXiv would answer confidently with something unrelated")
ck("titles come back with an author and a date",
   '"by": ", ".join(authors)' in io.open(
       os.path.join(ROOT, "papers.py"), encoding="utf-8").read())
ck("links are https, not the http arXiv returns",
   'link = "https://" + link.split("://", 1)[1]' in io.open(
       os.path.join(ROOT, "papers.py"), encoding="utf-8").read(),
   "a mixed-content link on an https page is a dead link")

print("\nand it is reading, not teaching")
ck("nothing from a paper reaches the model",
   "_papers.find(_pic_client, topic, 3)" in MAIN
   and "_papers" not in MAIN.split("_board_prompt(")[1].split(")")[0],
   "a lesson is what a class is examined on; a preprint is an argument")
ck("fetched beside the picture, so it costs no extra wait",
   "text, photo, further = await asyncio.gather(" in MAIN)
ck("shown on the last step, not the first",
   "${(SB.i===l.steps.length-1)?sbPapersHTML(l):\"\"}" in IDX,
   "further reading on step one is an invitation to leave")
ck("and it says they are preprints",
   "most have not yet been peer reviewed" in IDX,
   "the one thing a reader must know before treating one as settled")

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\nPASSED {len(P)}   FAILED {len(F)}")
sys.exit(1 if F else 0)
