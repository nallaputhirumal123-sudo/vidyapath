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
import urllib.request

BASE = "https://ncert.nic.in/textbook/pdf/{code}.pdf"
UA = "craxle-education/1.0 (+https://craxle.com)"
TIMEOUT = 60
MAX_MB = 40

# NCERT's own scheme. The class letter, then the subject, then the chapter
# number — jesc101 is Class 10 Science chapter 1.
CLASS_LETTER = {6: "f", 7: "g", 8: "h", 9: "i", 10: "j", 11: "k", 12: "l"}

# (subject key, NCERT subject code, book number, how many chapters).
# Written down rather than discovered, so a chapter that is missing shows up
# as a failed fetch instead of never being asked for.
BOOKS = [
    # Class 6 to 8, general science and maths.
    (6, "Science", "sc", 1, 16), (6, "Mathematics", "mh", 1, 14),
    (7, "Science", "sc", 1, 18), (7, "Mathematics", "mh", 1, 15),
    (8, "Science", "sc", 1, 18), (8, "Mathematics", "mh", 1, 16),
    # Class 9 and 10, the boards.
    (9, "Science", "sc", 1, 15), (9, "Mathematics", "mh", 1, 15),
    (10, "Science", "sc", 1, 16), (10, "Mathematics", "mh", 1, 15),
    # Class 11 and 12, where a subject becomes its own book — and where a
    # coaching centre spends most of its time.
    (11, "Physics", "ph", 1, 8), (11, "Physics", "ph", 2, 7),
    (11, "Chemistry", "ch", 1, 7), (11, "Chemistry", "ch", 2, 7),
    (11, "Biology", "bo", 1, 11), (11, "Biology", "bo", 2, 11),
    (11, "Mathematics", "mh", 1, 16),
    (12, "Physics", "ph", 1, 8), (12, "Physics", "ph", 2, 7),
    (12, "Chemistry", "ch", 1, 8), (12, "Chemistry", "ch", 2, 8),
    (12, "Biology", "bo", 1, 13),
    (12, "Mathematics", "mh", 1, 6), (12, "Mathematics", "mh", 2, 7),
]


def code_for(klass, subject_code, book, chapter):
    """NCERT's filename for one chapter, e.g. jesc101."""
    letter = CLASS_LETTER.get(klass)
    if not letter:
        return ""
    return f"{letter}e{subject_code}{book}{chapter:02d}"


def chapters(only_class=None, only_subject=None):
    """Every chapter we know how to ask for, as (code, class, subject, n)."""
    out = []
    for klass, subject, scode, book, count in BOOKS:
        if only_class and klass != only_class:
            continue
        if only_subject and subject.lower() != only_subject.lower():
            continue
        for n in range(1, count + 1):
            c = code_for(klass, scode, book, n)
            if c:
                out.append((c, klass, subject, n))
    return out


def fetch(code):
    """One chapter's PDF bytes, or None.

    Never raises. A chapter that will not download is a chapter we do not
    have, which is a fact to record rather than an exception to handle
    somewhere up the stack.
    """
    url = BASE.format(code=code)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read(MAX_MB * 1024 * 1024 + 1)
        if len(raw) > MAX_MB * 1024 * 1024:
            print(f"corpus: {code} is larger than {MAX_MB}MB, skipped")
            return None
        if not raw.startswith(b"%PDF"):
            return None
        return raw
    except Exception as e:
        print(f"corpus: {code} not fetched ({type(e).__name__})")
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


def title_of(text, fallback=""):
    """The chapter's own heading.

    Taking the first substantial line gave "CHAPTER" for every NCERT chapter
    in the corpus — the word sits alone above the number, which sits alone
    above the title. Every chapter was then indexed under the same name, so a
    search could find the right passage and could not tell you which chapter
    it came from.
    """
    for ln in (text or "").splitlines()[:60]:
        ln = ln.strip()
        if not (4 <= len(ln) <= 80):
            continue
        if _NOT_A_TITLE.match(ln):
            continue
        if ln[0].isdigit() and len(ln) < 12:      # a bare chapter number
            continue
        letters = [c for c in ln if c.isalpha()]
        if len(letters) < 4:
            continue
        # A heading is Title Case or CAPITALS; a sentence of prose is not.
        if ln.lower() == ln:
            continue
        return ln.strip(" .:-")
    return fallback


def ingest(index, want, log=print):
    """Fetch, read and index chapters into an FtsIndex. Returns a report.

    `want` is what chapters() returns. Each chapter is one document, labelled
    with its class and subject so a search for "class 10 refraction" has
    something to match on beyond the prose.
    """
    done, failed, chars = 0, [], 0
    for code, klass, subject, n in want:
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
        done += 1
        chars += len(text)
        log(f"  {code}: {len(text):,} chars — {title[:52]}")
    return {"indexed": done, "failed": failed, "chars": chars}
