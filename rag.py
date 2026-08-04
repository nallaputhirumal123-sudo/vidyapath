"""Answer from the curriculum we wrote, not from what the model remembers.

The tutor was asked to be accurate and given nothing to be accurate against.
Every lesson it produced came out of the model's own weights, so "is this
right?" could only ever be answered by asking the same model a second time —
which is how a confident wrong answer gets confirmed by a confident wrong
reviewer.

There are 82 published lessons here, 237,000 characters, written by a person
and reviewed. That is the thing to be right against. So this retrieves the
passages of it that bear on a question, hands them to the model as the source
to teach from, and afterwards checks what came back against them.

**No embeddings, and that is a decision rather than a shortcut.** An embedding
index means an API call per question, or per chunk on every rebuild, and cost
is the hard constraint on this product — the co-pilot was removed over exactly
this. BM25 is a ranking function from the 1970s that needs no model, no
network and no key. On a corpus this size it scores every passage in
single-digit milliseconds, and for "which of my lessons talks about pointers"
it is not meaningfully worse than a vector search. It would be worse on
paraphrase — a question sharing no words with the passage that answers it —
and that limit is real and stated rather than hidden.

**The index is built once and held.** Rebuilt only when the curriculum changes,
which is a deploy, not a request.

**Retrieval that finds nothing returns nothing.** A weak match dressed up as a
source is worse than no source: it invites the model to teach from something
irrelevant while citing it. There is a floor, and below it this says so.
"""
import math
import re

# Chunking. Long enough to carry an argument, short enough that four of them
# fit in a prompt without crowding out the question.
CHUNK_MIN = 240
CHUNK_MAX = 1100
# A floor, but a low one, because it is no longer what keeps out rubbish.
#
# It started at 3.0, tuned by eye against the 215-passage curriculum, and that
# was a mistake worth recording: BM25's idf term grows with corpus size, so a
# fixed cutoff means something entirely different on 215 passages than on 5.
# The same index code scored well on the real corpus and rejected everything
# on a small one, which is exactly the sort of threshold that works until the
# day the content changes.
#
# Precision now comes from requiring the question's rarest term to appear
# (see search). This is only a last guard against a passage that contains the
# word once, in passing.
FLOOR = 0.8
K1 = 1.5             # BM25 term-frequency saturation
B = 0.75             # BM25 length normalisation

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t]+")
_BLOCK = re.compile(r"</(?:p|h[1-6]|pre|li|ul|ol|div|table)>", re.I)

# Words that appear in every lesson and separate nothing.
_STOP = frozenset("""
a an the and or but if then else of to in on at by for with from as is are was
were be been being it its this that these those you your we our they them he
she his her do does did done have has had will would can could should may
might must not no so than too very just also into out up down over under
about which what when where who whom how why all any both each few more most
other some such only own same s t don now
""".split()) | frozenset("""
work works working use uses used using make makes made making get gets got
take takes taking put puts need needs want wants know knows learn learns
understand understands mean means thing things way ways example examples
called call calls happen happens look looks see sees give gives run runs
write writes written read reads reading like time times first next last
""".split())
# The second list is the fix for a specific fault, not tidiness. Rarity picks
# the term a question turns on, and "how does a for loop work" turned on
# "work" — rarer in this corpus than "loop", and generic enough that a lesson
# about lists outscored the lesson about loops. A teaching corpus is full of
# these: they are frequent enough to look meaningful and carry no subject at
# all. Removing them leaves "loop", which is what the question was about.


def _tokens(text):
    """Words, keeping the ones that carry meaning in this subject.

    +#. survive because c++, c#, .net and node.js are terms here, and a
    tokeniser that splits them turns three different things into "c".
    """
    return [w for w in re.split(r"[^a-z0-9+#.]+", (text or "").lower())
            if w and w not in _STOP and len(w) > 1]


def _plain(html):
    """Readable text out of lesson HTML, with block boundaries kept.

    The boundary matters: without it a heading runs into the paragraph under
    it and a chunk can begin mid-sentence.
    """
    s = _BLOCK.sub("\n", html or "")
    s = _TAG.sub(" ", s)
    s = (s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<")
          .replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'"))
    s = _WS.sub(" ", s)
    return "\n".join(ln.strip() for ln in s.split("\n") if ln.strip())


def _chunks(text):
    """Split into passages on paragraph boundaries, never mid-sentence."""
    out, buf = [], ""
    for para in text.split("\n"):
        if len(buf) + len(para) + 1 <= CHUNK_MAX:
            buf = (buf + "\n" + para).strip() if buf else para
            continue
        if len(buf) >= CHUNK_MIN:
            out.append(buf)
            buf = para
        else:
            # A short buffer plus an oversized paragraph: keep them together
            # rather than emitting a fragment that says nothing on its own.
            out.append((buf + "\n" + para).strip() if buf else para)
            buf = ""
    if buf.strip():
        if out and len(buf) < CHUNK_MIN:
            out[-1] = out[-1] + "\n" + buf      # trailing scrap joins the last
        else:
            out.append(buf.strip())
    return [c for c in out if c.strip()]


class Index:
    """A BM25 index over the curriculum. Built once, queried many times."""

    def __init__(self):
        self.passages = []      # {text, title, track, slug}
        self.tf = []            # term -> count, per passage
        self.lens = []
        self.df = {}
        self.avg = 0.0
        self.n = 0

    def add(self, text, title, track, slug):
        # The title and the track are searchable, though only the body is
        # ever shown. A lesson called "JOIN — combining two tables" in the SQL
        # track never says the word "sql" in its body, so "sql join" found
        # nothing at all — the one term the question turned on existed only in
        # the heading above the text being searched. What a lesson is called
        # is usually the best short description of it that exists.
        label = _tokens(f"{title} {track}")
        for c in _chunks(_plain(text)):
            toks = _tokens(c) + label
            if len(toks) - len(label) < 12:      # body too thin to be a source
                continue
            counts = {}
            for w in toks:
                counts[w] = counts.get(w, 0) + 1
            self.passages.append({"text": c, "title": title,
                                  "track": track, "slug": slug})
            self.tf.append(counts)
            self.lens.append(len(toks))
            for w in counts:
                self.df[w] = self.df.get(w, 0) + 1

    def finish(self):
        self.n = len(self.passages)
        self.avg = (sum(self.lens) / self.n) if self.n else 0.0
        return self

    def search(self, query, k=4):
        """The passages that bear on this question, best first.

        Returns [] rather than the least-bad passage when nothing clears the
        floor. A source that does not answer the question is worse than none:
        it invites teaching from the wrong thing while citing it.
        """
        if not self.n:
            return []
        q = _tokens(query)
        if not q:
            return []

        # The word the question actually turns on must be in the passage.
        #
        # Without this, "how does a firewall work" scored a lesson about lists
        # at 3.86 — over the floor purely on "work", a word half the corpus
        # contains, while "firewall" appears nowhere in it. BM25 is happy to
        # add up small change from common words until it clears any fixed
        # threshold, so the threshold was never going to fix it.
        #
        # The rarest term in the question is the one carrying its subject.
        # Requiring it turns "firewall" from one signal among several into the
        # thing being asked about, and a passage that never mentions it is not
        # a source about it however many times it says "work".
        # The rarest term THAT WE ACTUALLY HOLD, not the rarest term asked.
        #
        # Picking the globally rarest and then checking it exists threw away
        # good questions: "c++ pointers" chose "c++", which appears nowhere in
        # a corpus that writes it as C, and returned nothing — while a lesson
        # called "C, memory and pointers" sat right there. A word we have
        # never seen carries no evidence either way, so it should not be the
        # word the whole search turns on. Absent terms are set aside and the
        # rarest of the rest decides; when none of them is present, that is a
        # subject we do not teach and nothing comes back.
        present = [w for w in dict.fromkeys(q) if self.df.get(w)]
        if not present:
            return []
        key = min(present, key=lambda w: self.df[w])

        scored = []
        for i in range(self.n):
            if key not in self.tf[i]:
                continue
            tf, dl = self.tf[i], self.lens[i]
            s = 0.0
            for w in q:
                f = tf.get(w)
                if not f:
                    continue
                df = self.df.get(w, 0)
                # Robertson/Sparck-Jones idf, floored so a term appearing in
                # most passages contributes nothing rather than going negative
                # and actively pushing good matches down.
                idf = math.log(1 + (self.n - df + 0.5) / (df + 0.5))
                s += idf * (f * (K1 + 1)) / (f + K1 * (1 - B + B * dl / self.avg))
            if s > 0:
                scored.append((s, i))
        scored.sort(key=lambda x: -x[0])
        out = []
        for s, i in scored[:k]:
            if s < FLOOR:
                break
            p = dict(self.passages[i])
            p["score"] = round(s, 2)
            out.append(p)
        return out


def build(lessons):
    """Index published lessons. `lessons` is (content, title, track, slug)."""
    ix = Index()
    for content, title, track, slug in lessons:
        if content:
            ix.add(content, title, track, slug)
    return ix.finish()


def as_source(hits, limit=3):
    """The retrieved passages, shaped for a prompt.

    Labelled as the site's own material and ordered best first. The
    instruction to prefer it is deliberately narrow: the curriculum covers a
    fraction of what the board is asked, and a rule to answer ONLY from it
    would turn every uncovered question into a refusal.
    """
    if not hits:
        return ""
    parts = []
    for h in hits[:limit]:
        parts.append(f"[{h['title']}]\n{h['text']}")
    return (
        "OUR OWN COURSE MATERIAL ON THIS, written and reviewed by us:\n\n"
        + "\n\n---\n\n".join(parts)
        + "\n\nWhere this material covers the question, follow it: its"
          " definitions, its notation, its worked order. A learner who reads"
          " the lesson and then asks the board must not be told something"
          " different by the same site. Where it does not cover what was"
          " asked, answer normally and do not pretend it did.\n")


# ---------------------------------------------------------------------------
# The same retrieval, on disk, for a corpus that will not fit in memory.
#
# The in-memory index above is right for 82 lessons: it builds in 77ms and
# searches in 0.4ms, and every part of it can be read on one screen. It is the
# wrong shape for what is coming. NCERT alone is around four hundred books, and
# open university material on top of that puts the corpus into hundreds of
# thousands of passages — at which point scoring every one of them in Python on
# every question stops being clever and starts being a timeout.
#
# SQLite's FTS5 does the same job in C, with the same BM25 ranking function,
# and it is in the standard library. No service, no key, no per-query cost —
# which is the constraint that ruled out embeddings and rules them out at this
# size too.
#
# The interface is deliberately identical to Index: .n and .search(query, k)
# returning the same dicts. That is what lets the two be compared on the same
# corpus and the same questions, which is the only honest way to swap one for
# the other.
# ---------------------------------------------------------------------------

import sqlite3


class FtsIndex:
    """A BM25 index in SQLite. Same interface as Index, different scale."""

    def __init__(self, path=":memory:"):
        self.path = path
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        # tokenchars keeps c++, c#, .net and node.js whole. Without it FTS5's
        # default tokenizer splits on punctuation and three different subjects
        # all become "c" — the same fault the in-memory tokeniser guards.
        self.db.executescript("""
            DROP TABLE IF EXISTS passages;
            CREATE VIRTUAL TABLE passages USING fts5(
                body, title, track, slug UNINDEXED,
                tokenize="unicode61 tokenchars '+#.'"
            );
        """)
        self.n = 0

    def add(self, text, title, track, slug):
        rows = []
        for c in _chunks(_plain(text)):
            if len(_tokens(c)) < 12:
                continue
            rows.append((c, title or "", track or "", slug or ""))
        if rows:
            self.db.executemany(
                "INSERT INTO passages (body, title, track, slug) "
                "VALUES (?, ?, ?, ?)", rows)

    def finish(self):
        self.db.commit()
        self.n = self.db.execute("SELECT count(*) FROM passages").fetchone()[0]
        return self

    def _df(self, term):
        """How many passages contain this term. Used to find the rarest."""
        try:
            row = self.db.execute(
                "SELECT count(*) FROM passages WHERE passages MATCH ?",
                (f'"{term}"',)).fetchone()
            return row[0] if row else 0
        except sqlite3.OperationalError:
            return 0

    def search(self, query, k=4):
        """Same contract as Index.search, including the silence.

        The rarest term is required rather than merely scored, for the reason
        recorded above: BM25 will add up small change from common words until
        it clears any threshold, and "how does a firewall work" matched a
        lesson about lists on the strength of "work" alone.
        """
        if not self.n:
            return []
        q = _tokens(query)
        if not q:
            return []
        dfs = {w: self._df(w) for w in dict.fromkeys(q)}
        present = [w for w, d in dfs.items() if d]
        if not present:
            return []
        key = min(present, key=lambda w: dfs[w])
        others = [w for w in present if w != key]
        # key AND (anything else that is actually in the corpus). Quoted, so a
        # term containing punctuation cannot be read as FTS5 query syntax —
        # "c++" unquoted is a syntax error, and a search that raises on a
        # legitimate subject is worse than one that finds nothing.
        expr = f'"{key}"'
        if others:
            expr += " AND (" + " OR ".join(f'"{w}"' for w in others) + ")"
        try:
            rows = self.db.execute(
                "SELECT body, title, track, slug, bm25(passages) AS score "
                "FROM passages WHERE passages MATCH ? "
                "ORDER BY score LIMIT ?", (expr, k)).fetchall()
        except sqlite3.OperationalError as e:
            print(f"fts search failed: {e}")
            return []
        out = []
        for r in rows:
            # bm25() returns a NEGATIVE number and more negative is better,
            # which is the opposite of every other score in this file. Flipped
            # here so callers never have to know, and so `score` means the
            # same thing whichever backend produced it.
            out.append({"text": r["body"], "title": r["title"],
                        "track": r["track"], "slug": r["slug"],
                        "score": round(-r["score"], 2)})
        return out


def build_fts(lessons, path=":memory:"):
    """Index into SQLite. `lessons` is (content, title, track, slug)."""
    ix = FtsIndex(path)
    for content, title, track, slug in lessons:
        if content:
            ix.add(content, title, track, slug)
    return ix.finish()
