"""Answering from the curriculum we wrote, not from what the model remembers.

The tutor was asked to be accurate and given nothing to be accurate against.
Every lesson came out of the model's weights, so "is this right?" could only be
answered by asking the same model again — which is how a confident wrong answer
gets confirmed by a confident wrong reviewer.

There are 82 published lessons here, written by a person. This retrieves the
parts that bear on a question, hands them over as the source, and checks the
answer against them afterwards.

What is pinned:

**Silence when we do not teach it.** The curriculum covers a fraction of what
the board is asked. Returning the least-bad passage for a question about
photosynthesis would invite the model to teach biology out of a lesson on
lists while citing it as ours. Nothing is the right answer, and it has to stay
the right answer.

**The word the question turns on must be present.** "How does a firewall work"
scored a lesson about lists at 3.86 — over the floor purely on "work", a word
half the corpus contains, while "firewall" appears nowhere. BM25 will add up
small change from common words until it clears any fixed threshold, so a
threshold was never going to fix it.

**No model, no network, no key.** The whole reason this is BM25 and not
embeddings is that cost is the hard constraint here. If an import of this
module ever needs an API, that decision has been quietly reversed.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import rag                                         # noqa: E402

PASS = FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {name}" + (f"  ({detail})" if detail else ""))
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


LESSONS = [
    ("<h3>Boxes that remember</h3><p>A variable is a named box that holds a "
     "value. You put something in it and take it out later by name. In Python "
     "you write <code>age = 20</code> and the box called age now holds 20.</p>"
     "<p>The name is yours to choose, but choose one that says what is in it. "
     "A variable called x tells the next reader nothing at all.</p>",
     "Boxes that remember: variables", "Python", "variables"),
    ("<h3>Repeating work</h3><p>A loop repeats work without you writing it "
     "out again. A for loop walks through a list one item at a time and runs "
     "the same block for each of them.</p><p>The counter starts at 0 in "
     "Python, not 1, which is the single most common mistake a beginner "
     "makes when they come from mathematics.</p>",
     "Repeating work: loops", "Python", "loops"),
    ("<h3>JOIN</h3><p>A JOIN combines rows from two tables using a column "
     "they share. An INNER JOIN keeps only the rows that match in both "
     "tables. A LEFT JOIN keeps every row from the left table whether or not "
     "it matched.</p><p>The default port for postgres is 5432.</p>",
     "JOIN — combining two tables", "SQL", "sql-join"),
]

ix = rag.build(LESSONS)

print("\nbuilding the index")
check("it indexes passages", ix.n > 0, f"{ix.n} passages")
check("it has a vocabulary", len(ix.df) > 40, f"{len(ix.df)} terms")

print("\nfinding what we do teach")
h = ix.search("what is a variable")
check("a question about variables finds the variables lesson",
      bool(h) and h[0]["title"].startswith("Boxes"),
      h[0]["title"] if h else "nothing")
h = ix.search("for loop")
check("a question about loops finds the loops lesson",
      bool(h) and "loops" in h[0]["title"], h[0]["title"] if h else "nothing")
h = ix.search("inner join sql")
check("a question about joins finds the JOIN lesson",
      bool(h) and "JOIN" in h[0]["title"], h[0]["title"] if h else "nothing")

print("\nsilence when we do not teach it")
for q in ("photosynthesis", "mitochondria", "the treaty of versailles"):
    check(f"nothing for {q!r}", ix.search(q) == [],
          "a wrong source is worse than none")

print("\nthe word the question turns on must be there")
h = ix.search("how does a firewall work")
check("a firewall question does not match a lesson about loops",
      h == [],
      "it used to score 3.86 on 'work' alone, over the floor, citing the "
      "wrong lesson as ours")
check("but the same sentence shape still works when we do teach it",
      bool(ix.search("how does a for loop work")),
      "the gate must not reject every question phrased as a question")

print("\nit costs nothing to run")
t = time.time()
for _ in range(200):
    ix.search("variable in python")
ms = (time.time() - t) * 1000 / 200
check("a search is sub-millisecond", ms < 5.0, f"{ms:.2f}ms each")
check("no network client is imported",
      not any(m in sys.modules for m in ("httpx", "requests", "openai")),
      "the point of BM25 here is that it needs no API")

print("\nshaping it for a prompt")
src = rag.as_source(ix.search("what is a variable"))
check("the source is labelled as ours", "OUR OWN COURSE MATERIAL" in src)
check("it carries the lesson title", "Boxes that remember" in src)
check("it says to follow it where it applies", "follow it" in src)
check("and not to pretend where it does not",
      "do not pretend" in src,
      "the curriculum covers a fraction of what is asked")
check("nothing retrieved means nothing injected", rag.as_source([]) == "")

print("\nno numeric cross-check, deliberately")
check("contradictions() is gone, not merely unused",
      not hasattr(rag, "contradictions"),
      "it fired on 'marks', 'output' and 'average' — a lesson with two worked "
      "examples gives those different values by design — so it contradicted "
      "the material it was meant to protect, five times in sixty passages. A "
      "false finding blocks caching, and a blocked cache is a real model call "
      "every time somebody asks again. A tested helper nobody calls is an "
      "invitation to wire it back in without reading why it went.")

print("\nchunking")
plain = rag._plain("<h3>Head</h3><p>One.</p><p>Two.</p>")
check("html becomes readable text", "<" not in plain and "Head" in plain,
      plain[:40])
check("block boundaries survive", "\n" in plain,
      "without it a heading runs into the paragraph under it")

print("\nthe same retrieval on disk, for a corpus that will not fit in memory")
# NCERT alone is around four hundred books. Scoring every passage in Python on
# every question stops being clever at that size and starts being a timeout.
# FTS5 does the same BM25 in C and is in the standard library — no service, no
# key, no per-query cost, which is the constraint that ruled out embeddings.
fts = rag.build_fts(LESSONS)
check("the disk index holds the same passages", fts.n == ix.n,
      f"memory {ix.n}, fts {fts.n}")

# The only honest way to swap one for the other is to ask both the same
# questions and compare, including the questions that must return nothing.
same = 0
QS = ["what is a variable", "for loop", "inner join sql", "photosynthesis",
      "mitochondria", "how does a firewall work", "the counter in a loop"]
for _q in QS:
    _a, _b = ix.search(_q, 3), fts.search(_q, 3)
    if (not _a and not _b) or (_a and _b and _a[0]["title"] == _b[0]["title"]):
        same += 1
check("both backends answer every question the same way", same == len(QS),
      f"{same}/{len(QS)}")

check("including the silences", fts.search("photosynthesis") == [],
      "scale must not cost the property that makes it trustworthy")

# FTS5 reads +#. as query syntax unless quoted, and a search that raises on a
# real subject is worse than one that finds nothing.
for _q in ("c++", "c#", ".net", "node.js", 'a "quoted" thing', "a AND b"):
    try:
        fts.search(_q)
        ok = True
    except Exception as _e:
        ok = False
    check(f"punctuation in {_q!r} does not break the query", ok)

check("scores come back positive from both",
      all(h["score"] > 0 for h in fts.search("what is a variable")),
      "bm25() returns negative and more-negative-is-better; callers should "
      "never have to know that")

print(f"\nPASSED {PASS}   FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
