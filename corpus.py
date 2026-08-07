"""NCERT, fetched and indexed, so the tutor can answer from the actual textbook.

The curriculum we wrote is 82 lessons of programming and data. A coaching
centre asks about refraction, mitosis, the Mughals and quadratic equations, and
for all of it the tutor answers out of the model's own weights with nothing to
be right against.

NCERT is the corpus that fixes that for India: it is what students here are
examined on, CBSE follows it, most state boards track it closely, and the books
are published for download rather than sold as a paywalled licence. One
ingestion covers school science, maths, biology and history from Class 6 to 12.

**Fetched once, indexed, never fetched again.** These are four-megabyte PDFs on
a government server. Downloading them per query would be slow, rude, and would
stop working the first afternoon somebody noticed.

**Chapters are addressed by NCERT's own code, not by guessing URLs.** jesc101
is Class 10 Science chapter 1 — j is the class, sc the subject, the last two
digits the chapter. The scheme is regular, which is what makes a few hundred
books tractable; it is written down here rather than inferred at runtime so a
missing chapter is a missing row and not a silent gap.

**Nothing is invented when a fetch fails.** A chapter that will not download is
recorded as not downloaded. A corpus that quietly holds nine chapters while
claiming sixteen is worse than one that holds nine and says so.
"""
import io
import re
import time
import urllib.request

BASE = "https://ncert.nic.in/textbook/pdf/{code}.pdf"
UA = "craxle-education/1.0 (+https://craxle.com)"
TIMEOUT = 60
MAX_MB = 40

# NCERT's own scheme. The class letter, then the subject, then the chapter
# number — jesc101 is Class 10 Science chapter 1.
# Every book below was probed against ncert.nic.in before it went in: the
# prefix answers 200 and the chapter count is the last chapter that does.
#
# I had extrapolated the class letters backwards from the two I knew — j is
# Class 10, so f must be Class 6 — and every Class 6 fetch 404'd. NCERT
# replaced the Class 6 and 7 books in 2024 and 2025, so those are not "sc" and
# "mh" any more: Curiosity (cu) for science and Ganita Prakash (gp) for maths.
# The chapter counts were guessed too, and Class 10 Science has 13 chapters
# rather than the 16 I had written, so three of every sixteen fetches were
# asking for something that does not exist.
#
# (prefix, class, subject, chapters)
BOOKS = [
    ("fecu1", 6, "Science", 12),
    ("fegp1", 6, "Mathematics", 10),
    ("gecu1", 7, "Science", 12),
    ("gegp1", 7, "Mathematics", 8),
    ("hesc1", 8, "Science", 13),
    ("hemh1", 8, "Mathematics", 13),
    ("iesc1", 9, "Science", 13),
    ("iemh1", 9, "Mathematics", 8),
    ("jesc1", 10, "Science", 13),
    ("jemh1", 10, "Mathematics", 14),
    ("keph1", 11, "Physics", 7),
    ("keph2", 11, "Physics", 7),
    ("kech1", 11, "Chemistry", 6),
    ("kech2", 11, "Chemistry", 3),
    ("kebo1", 11, "Biology", 19),
    ("kemh1", 11, "Mathematics", 14),
    ("leph1", 12, "Physics", 8),
    ("leph2", 12, "Physics", 6),
    ("lech1", 12, "Chemistry", 5),
    ("lech2", 12, "Chemistry", 5),
    ("lebo1", 12, "Biology", 13),
    ("lemh1", 12, "Mathematics", 6),
    ("lemh2", 12, "Mathematics", 7),

    # The commerce and civics stream — MEC and CEC.
    #
    # Their absence was not a small gap. CEC had NOTHING behind it and MEC
    # had only its Maths, which is half the intermediate market in this state
    # and the half a coaching centre asks about first.
    #
    # Probed exactly as the books above were, and for the same reason: every
    # prefix here answered 200 and every chapter count is the last chapter
    # that does, checked one by one rather than extrapolated. Class 11
    # Business Studies is deliberately ABSENT — no code under any letter I
    # tried returns a PDF, so it stays off this list and stays named as
    # missing rather than quietly assumed.
    ("keec1", 11, "Economics", 8),
    ("kest1", 11, "Economics", 8),
    ("leec1", 12, "Economics", 6),
    ("leec2", 12, "Economics", 5),
    ("keac1", 11, "Accountancy", 7),
    ("keac2", 11, "Accountancy", 2),
    ("leac1", 12, "Accountancy", 4),
    ("leac2", 12, "Accountancy", 6),
    ("lebs1", 12, "Business Studies", 8),
    ("lebs2", 12, "Business Studies", 3),
    ("keps1", 11, "Political Science", 8),
    ("kepy1", 11, "Political Science", 8),
    ("leps1", 12, "Political Science", 7),
    ("leps2", 12, "Political Science", 8),
    ("lepy1", 12, "Political Science", 7),
]


def code_for(prefix, chapter):
    """NCERT's filename for one chapter, e.g. jesc1 + 01 -> jesc101."""
    return f"{prefix}{chapter:02d}"


def chapters(only_class=None, only_subject=None):
    """Every chapter we know how to ask for, as (code, class, subject, n)."""
    out = []
    for prefix, klass, subject, count in BOOKS:
        if only_class and klass != only_class:
            continue
        if only_subject and subject.lower() != only_subject.lower():
            continue
        for n in range(1, count + 1):
            out.append((code_for(prefix, n), klass, subject, n))
    return out


def fetch(code):
    """One chapter's PDF bytes, or None.

    Never raises. A chapter that will not download is a chapter we do not
    have, which is a fact to record rather than an exception to handle
    somewhere up the stack.

    Retried, because the first version was not. A run of ninety-five
    chapters came back with ninety-one URLErrors, and every one of those
    codes downloaded perfectly when asked for on its own a minute later:
    ncert.nic.in simply stops accepting connections from a client that asks
    for three-megabyte PDFs back to back. Treating that as "we do not have
    this chapter" put a silent hole in a syllabus — the book is listed, the
    ingestion says it failed in a log nobody reads, and a coaching centre
    finds the gap in front of a class.

    Four attempts with a widening pause. A refusal that survives all four is
    a chapter we really cannot get.
    """
    url = BASE.format(code=code)
    last = None
    for attempt in range(4):
        if attempt:
            time.sleep(2 ** attempt)        # 2s, 4s, 8s
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                raw = r.read(MAX_MB * 1024 * 1024 + 1)
            if len(raw) > MAX_MB * 1024 * 1024:
                print(f"corpus: {code} is larger than {MAX_MB}MB, skipped")
                return None
            if not raw.startswith(b"%PDF"):
                # Not a transient failure: whatever is there is not a PDF,
                # and asking again will hand back the same thing.
                return None
            return raw
        except Exception as e:
            last = e
    print(f"corpus: {code} not fetched after 4 tries "
          f"({type(last).__name__})")
    return None


# Page furniture: a running header, a page number, the reprint notice that
# appears on every page of every NCERT book.
_JUNK = re.compile(
    r"^\s*(?:\d{1,4}|[IVXLC]+|reprint\s*\d{4}[-–]\d{2,4}|"
    r"rationalised\s*\d{4}[-–]\d{2,4}|©\s*ncert.*|"
    r"not\s+to\s+be\s+republished.*)\s*$", re.I)


def text_of(raw, max_chars=200_000):
    """Readable text out of a chapter PDF, or "".

    NCERT PDFs are typeset two-column in places and carry a reprint stamp on
    every page. What survives is the prose; what goes is the furniture that
    would otherwise be the most frequent phrase in the whole corpus and would
    poison every search that touched it.
    """
    try:
        import pdfplumber
    except Exception:
        print("corpus: pdfplumber is not installed")
        return ""
    lines = []
    try:
        with pdfplumber.open(io.BytesIO(raw)) as doc:
            for page in doc.pages:
                try:
                    t = page.extract_text() or ""
                except Exception:
                    continue
                for ln in t.splitlines():
                    ln = " ".join(ln.split())
                    if not ln or _JUNK.match(ln):
                        continue
                    lines.append(ln)
                if sum(len(x) for x in lines) > max_chars:
                    break
    except Exception as e:
        print(f"corpus: {type(e).__name__} reading a chapter")
        return ""
    return "\n".join(lines)[:max_chars].strip()


# "CHAPTER" on its own line, then the number, then the actual title — which
# is why the first substantial line is the least useful one in the file.
_NOT_A_TITLE = re.compile(
    r"^\s*(?:chapter|unit|part|section|contents|index|appendix|"
    r"answers?|exercises?|activity|figure|table|notes?)[\s\d.:-]*$", re.I)


_LEADING_NUMBER = re.compile(r"^\d+(?:\.\d+)?[\s.:)-]+")
# Prepositions and conjunctions only. "a", "an" and "the" were here too and
# made this greedy: "6.1 Perimeter" ran on into "A closed figure is…", because
# an article is how an ordinary sentence starts at least as often as it is how
# a heading continues.
_CONTINUES = re.compile(
    r"^(?:to|of|and|or|in|for|from|with|through|between|into)\b", re.I)
_UNFINISHED = re.compile(
    r"\b(?:and|or|of|the|a|an|in|to|for|from|with|through|between|into)$",
    re.I)


def title_of(text, fallback=""):
    """The chapter's own heading.

    Taking the first substantial line gave "CHAPTER" for every NCERT chapter
    in the corpus — the word sits alone above the number, which sits alone
    above the title. Every chapter was then indexed under the same name, so a
    search could find the right passage and could not tell you which chapter
    it came from.

    Three more faults showed up in a real run of twenty chapters: "7
    Temperature and" and "8 A Journey through" were cut off mid-heading, "3
    Mindful Eating: A Path" carried its chapter number, and "6.1 Perimeter"
    was a section heading rather than the chapter. NCERT's newer books set a
    heading across two or three lines, so taking one line takes a fragment —
    and the title is indexed as searchable text, so a fragment is a worse
    search and not only a worse label.
    """
    lines = [ln.strip() for ln in (text or "").splitlines()[:60]]
    for i, ln in enumerate(lines):
        if not (3 <= len(ln) <= 80) or _NOT_A_TITLE.match(ln):
            continue
        # "retpahC" — one chapter set the word Chapter as rotated sidebar
        # text, and it comes out of the PDF backwards. It is furniture either
        # way round, and a chapter titled "retpahC" is worse than one titled
        # nothing because it looks like content.
        if _NOT_A_TITLE.match(ln[::-1]):
            continue
        # "3 Mindful Eating" and "6.1 Perimeter": the number is which chapter
        # it is, not what it is called.
        head = _LEADING_NUMBER.sub("", ln).strip()
        if len(head) < 3 or sum(c.isalpha() for c in head) < 3:
            continue
        if head.lower() == head:          # prose, not a heading
            continue
        # A heading ending on a preposition or an article is half a heading,
        # and so is a very short one. Take the next line while that is true.
        parts = [head]
        for nxt in lines[i + 1:i + 4]:
            # The joined title so far, not the last line appended to it.
            # Checking the last line alone kept "PATTERNS IN MATHEMATICS"
            # going, because "MATHEMATICS" is short — and swallowed the first
            # sentence of the chapter.
            tail = " ".join(parts).rstrip()
            if not nxt or len(nxt) > 60 or _NOT_A_TITLE.match(nxt):
                break
            # A line beginning "to", "of", "and" is the rest of the heading
            # above it: "Mindful Eating: A Path" / "to a Healthy Body".
            # No "the heading looks short, take another line" rule. It was
            # here and it swallowed "6.1 Perimeter" into "Perimeter A closed
            # figure is…", because a short heading is usually just a short
            # heading. Where a heading really is cut off it says so — it ends
            # on a preposition, or the next line opens with one.
            continues = _CONTINUES.match(nxt)
            if not (continues or tail.endswith((",", ":", "-", "—"))
                    or _UNFINISHED.search(tail)):
                break
            if nxt.lower() == nxt and not continues:
                break
            parts.append(nxt)
        title = re.sub(r"\s+", " ", " ".join(parts)).strip(" .:-—")
        if len(title) >= 3:
            return title[:90]
    return fallback


PIC_MAX_SIDE = 900       # a board is 1080 tall; nothing needs more
PIC_QUALITY = 72
PIC_PER_CHAPTER = 6


def chapter_pictures(code, limit=PIC_PER_CHAPTER):
    """The diagrams from one NCERT chapter, fetched when somebody asks.

    NOT stored in the corpus, and the number is why. The pictures in 316
    chapters are 118 MB as they come out of the PDFs and 28 MB re-encoded —
    against 10 MB for the entire text of the same books. Shipping them would
    quadruple an artefact that travels in the repository, to carry diagrams
    for hundreds of chapters no class will open this term.

    So they are fetched from the chapter's own PDF the first time anybody
    wants them and cached by the caller. One three-second download per
    chapter, once, for the chapters actually taught — and nothing at all for
    the rest.

    Re-encoded to JPEG at 900px because these are print images: a Class 11
    Biology chapter carries 800 KB of them at a resolution meant for paper,
    and a projector shows 1080 lines.

    Returns [] rather than raising. A chapter whose diagrams cannot be got is
    a lesson without diagrams, which is how every lesson worked until now.
    """
    try:
        import base64
        import io as _io
        import teachpdf
        from PIL import Image
    except Exception:
        return []
    raw = fetch(code)
    if not raw:
        return []
    try:
        found = teachpdf.pictures(raw)
    except Exception as e:
        print(f"corpus: no pictures from {code} ({type(e).__name__})")
        return []
    out = []
    for p in found[:limit]:
        try:
            src = p.get("src") or ""
            blob = base64.b64decode(src.split(",", 1)[1])
            im = Image.open(_io.BytesIO(blob))
            im = im.convert("RGB")
            im.thumbnail((PIC_MAX_SIDE, PIC_MAX_SIDE))
            buf = _io.BytesIO()
            im.save(buf, "JPEG", quality=PIC_QUALITY, optimize=True)
            out.append({
                "src": "data:image/jpeg;base64,"
                       + base64.b64encode(buf.getvalue()).decode(),
                "page": p.get("page", 0),
                "w": im.width, "h": im.height,
            })
        except Exception:
            continue
    return out


def already_in(index):
    """Chapter codes this index already holds.

    Every chapter is stored under its own code as the slug, so the index knows
    what it has without a second file to keep in step with it.
    """
    try:
        rows = index.db.execute(
            "SELECT DISTINCT slug FROM passages WHERE slug != ''").fetchall()
        return {r[0] for r in rows}
    except Exception:
        return set()


def ingest(index, want, log=print, resume=True):
    """Fetch, read and index chapters into an FtsIndex. Returns a report.

    `want` is what chapters() returns. Each chapter is one document, labelled
    with its class and subject so a search for "class 10 refraction" has
    something to match on beyond the prose.

    **Committed after every chapter, and this is the whole point.** It used to
    commit once at the end, so a run that reached chapter 205 of 222 and was
    interrupted — a power cut, a closed laptop, anything — rolled back all of
    it. Two and a half hours of downloading from a government server, gone,
    with a twelve-megabyte file on disk holding nothing but the curriculum it
    started with. A batch job measured in hours must not be all-or-nothing.

    **And it resumes.** Chapters already in the index are skipped, so a second
    run finishes what the first one started instead of fetching two hundred
    PDFs again. Pass resume=False to rebuild from nothing.
    """
    have = already_in(index) if resume else set()
    if have:
        log(f"resuming: {len(have)} chapters already indexed")
    done, failed, skipped, chars = 0, [], 0, 0
    for code, klass, subject, n in want:
        if code in have:
            skipped += 1
            continue
        raw = fetch(code)
        if not raw:
            failed.append(code)
            continue
        text = text_of(raw)
        if len(text) < 400:
            failed.append(code)
            log(f"  {code}: too little text, skipped")
            continue
        title = title_of(text, f"{subject} chapter {n}")
        index.add(text, f"Class {klass} {subject}: {title}",
                  f"NCERT Class {klass} {subject}", code)
        # Committed here, not at the end. One chapter is what an interruption
        # may now cost.
        try:
            index.db.commit()
        except Exception as e:
            log(f"  {code}: indexed but not committed ({type(e).__name__})")
        done += 1
        chars += len(text)
        log(f"  {code}: {len(text):,} chars — {title[:52]}")
    return {"indexed": done, "failed": failed, "skipped": skipped,
            "chars": chars}
