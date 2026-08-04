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
        key = max(q, key=lambda w: math.log(
            1 + (self.n - self.df.get(w, 0) + 0.5) / (self.df.get(w, 0) + 0.5)))
        if key not in self.df:
            return []

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
