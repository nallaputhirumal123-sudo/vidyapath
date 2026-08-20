"""A cached lesson remembers which recipe wrote it.

Teach the board to draw a table, deploy it, ask it the first thing that comes
to mind — and get back the lesson it cached last week, in prose, with no
table in it. The change worked. The cache answered first.

A cached lesson is served verbatim and forever, and nothing in its key said
which prompt built it, so every improvement to how a lesson is made reached
only the topics nobody had asked yet. From the outside that is indis-
tinguishable from the change not working, which is the worst property a bug
can have: it sends you back to re-fix something that was already right.

The key carries a recipe now. Bumping it makes every existing row
unreachable, so the next person to ask each topic pays for one real model
call — once per topic, and that is the whole cost.

**It is a constant somebody changes on purpose, not a hash of the prompt.**
Hashing would discard the cache on every wording tweak, and on this product
the cache is the economics: one model call per question, kept forever.

**And every place that rebuilds this key has to carry it.** The two review
routes recompute the key to delete a lesson a critical finding rejected. A
key spelled differently there does not raise — it finds no row, deletes
nothing, and leaves the flagged lesson being served to everybody.
"""
import inspect
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("DATABASE_URL", "sqlite:///./vidyapath.db")
os.environ.setdefault("ALLOW_SQLITE", "1")

import main                                              # noqa: E402
import craxlearn as cl                                   # noqa: E402

SRC = io.open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
P, F = [], []


def ck(name, cond, why=""):
    print(("PASS " if cond else "FAIL ") + name + (" — " + why if why else ""),
          flush=True)
    (P if cond else F).append(name)


print("\nthere is a recipe, and it is deliberate")
ck("the recipe exists", isinstance(main.RECIPE, str) and main.RECIPE)
ck("it is short enough not to crowd the key", len(main.RECIPE) <= 8)
ck("it is not read from the environment", 'RECIPE = env(' not in SRC,
   "a cache generation that differs between two deployments of the same "
   "code is a cache that splits without anybody deciding to")
ck("and it is not a hash of the prompt",
   "hashlib" not in SRC.split("RECIPE =")[0][-400:],
   "hashing would throw the cache away on every wording tweak, and the "
   "cache is this product's economics")

print("\nevery cache built by a versioned prompt carries it")
# Asked the right way round: not "which keys did I remember to change" but
# "which caches hold a lesson written by a prompt that has a recipe". The
# first framing is how /api/ask/image was missed — it builds its lesson with
# _ask_prompt, exactly like the typed question, and its key said "askimg" so
# a search for ask|board never saw it. A photo of a question would have kept
# serving the old answer forever while typing the same question got a new
# one.
VERSIONED = ("_ask_prompt(", "_board_prompt(")


def _fn_holding(at):
    """The source of the function a given offset sits in — and no more.

    Bounded by the next top-level def, not by the next @app. route. Reaching
    for the route decorator over-ran the end of _call_model — a helper that
    calls _ask_prompt and caches nothing — and swept up an unrelated key from
    a function three screens below it.
    """
    head = SRC[:at]
    start = max(head.rfind("\nasync def "), head.rfind("\ndef "))
    nxt = [p for p in (SRC.find("\ndef ", at), SRC.find("\nasync def ", at))
           if p > 0]
    return SRC[start:min(nxt) if nxt else len(SRC)]


hits = 0
for m in re.finditer("|".join(re.escape(v) for v in VERSIONED), SRC):
    fn = _fn_holding(m.start())
    if "_cl.key(" not in fn or "AskCache" not in fn:
        continue                      # not a route that caches a lesson
    hits += 1
    key = fn[fn.index("_cl.key("):][:170]
    name = re.search(r'"(\w+)"', key)
    ck("the %s cache carries the recipe" % (name.group(1) if name else "?"),
       "RECIPE" in key,
       "its lesson is written by a prompt that has a recipe, so a change to "
       "that prompt has to reach this cache as well")
ck("and the search found the routes it should", hits >= 2,
   "%d found — if this drops to nothing the check above passed vacuously"
   % hits)

# The two recomputed keys as well, which is a different failure: they do not
# raise when they are wrong, they find no row and delete nothing.
KEYS = re.findall(r'_cl\.key\((?:scope|_scope_of\(db, user\)),\s*'
                  r'"(ask|board)"(.{0,24})', SRC, re.S)
ck("both kinds of key were found", len(KEYS) >= 4, str(len(KEYS)) + " found")
for kind, tail in KEYS:
    ck("a %s key carries the recipe" % kind, "RECIPE" in tail,
       "a key spelled differently finds no row: it does not raise, it just "
       "quietly does nothing")

print("\nthe two review routes delete the row they actually wrote")
for name, fn in (("ask", main.ask_review), ("board", main.board_lesson_review)):
    src = inspect.getsource(fn)
    ck("the %s review recomputes with the recipe" % name,
       "RECIPE" in src.split("_cl.key(")[1][:120])

print("\nand the recipe really does separate old rows from new")
old = cl.key("public", "board", main._norm_q("intermediate"),
             main._norm_q("0|photosynthesis"))
new = cl.key("public", "board", main.RECIPE, main._norm_q("intermediate"),
             main._norm_q("0|photosynthesis"))
ck("a row written before it is unreachable now", old != new)
ck("and the scope still comes first",
   new.startswith("public|"),
   "the scope is what keeps one school out of another's answers, and it is "
   "not optional")
ck("two topics still differ under one recipe",
   cl.key("public", "board", main.RECIPE, "x", "a")
   != cl.key("public", "board", main.RECIPE, "x", "b"))
ck("and the same topic is stable across two calls",
   cl.key("public", "board", main.RECIPE, "x", "a")
   == cl.key("public", "board", main.RECIPE, "x", "a"),
   "if this ever fails, nothing is ever served from cache and every "
   "question is a fresh model call")

print("\nthe note says when to bump it, because that is the hard part")
# Unwrapped before matching. The note is a comment block, so a phrase that
# happens to straddle a line break is still the same sentence — asserting on
# the wrapped text would fail the next time somebody reflows the paragraph.
NOTE = re.sub(r"\s+", " ", SRC.split("RECIPE =")[0][-1800:].replace("#", " "))
ck("it says what a bump costs", "one real model call" in NOTE)
ck("it says what earns one", "a new kind of figure" in NOTE)
ck("and what does not", "Not for a typo" in NOTE)

print("\n" + ("PASSED %d   FAILED %d" % (len(P), len(F))))
if F:
    for name in F:
        print("  FAILED: " + name)
    sys.exit(1)
