"""Repair chapter titles that came out of the PDFs doubled.

NCERT sets its chapter headings in a font that pdfplumber reads twice, so
"Earth, Moon, and" arrives as "EEaarrtthh,, MMoooonn,, aanndd". Twenty of the
corpus's 255 distinct titles are like this.

It is not cosmetic. The title is what `rag.as_source` puts in front of the
model as `[Class 7 Science: EEaarrtthh,, MMoooonn,, aanndd]`, and a source
labelled with noise is a source the model has been given no reason to trust —
and one nobody can check afterwards.

Titles only. The passage BODY is fine: the doubling is a property of the
heading font, and re-ingesting four hundred PDFs to fix twenty strings would
be hours of work for something an UPDATE does in a second.

    .\\.venv\\Scripts\\python.exe tools\\fix_corpus_titles.py --dry
    .\\.venv\\Scripts\\python.exe tools\\fix_corpus_titles.py
"""
import argparse
import os
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(HERE, "corpus.db")
# At import time, not inside main(). repair() runs before main() reached its
# own sys.path line, so "import corpus" in there raised ImportError, the
# except swallowed it, and a guard I had just written silently did nothing —
# which is how "II-traP" got written into the corpus anyway.
sys.path.insert(0, HERE)
import corpus as _c                                          # noqa: E402


def _collapse_word(word, k):
    """"EEaarrtthh" at k=2 is "Earth"; "UUUUUnnnnn" at k=5 is "Un"."""
    if len(word) < k * 2 or len(word) % k:
        return None
    out = []
    for i in range(0, len(word), k):
        run = word[i:i + k]
        if len(set(run)) != 1:
            return None
        out.append(run[0])
    return "".join(out)


def undouble(text):
    """Undo a heading whose every character arrived repeated.

    Two shapes turn up, and a whole-string test finds neither:

      "EEaarrtthh,, MMoooonn,, aanndd"   doubled, but the SPACES are single,
                                        so the string as a whole is not a
                                        run of pairs — the words are
      "UUUUUnnnnniiiiittttt"            five times over, not twice

    So it works per word, and tries each repeat factor from five down to two,
    taking the first that explains the whole word. Down rather than up
    because at k=1 everything "works" and the answer is the input.

    A word is only collapsed if the factor explains ALL of it. Without that,
    "Pollution" would become "Polution" — one real double letter is not a
    doubled word.
    """
    words = str(text or "").split()
    if not words:
        return str(text or "")
    out, changed = [], False
    for w in words:
        best = None
        for k in (5, 4, 3, 2):
            got = _collapse_word(w, k)
            if got:
                best = got
                break
        if best is not None and best != w:
            changed = True
            out.append(best)
        else:
            out.append(w)
    return " ".join(out) if changed else str(text or "")


def readable(text):
    """Is this a title a person could act on, or is it leftovers?

    "SYMMETRY" is a chapter. "CC PP MM" is what is left when the heading did
    not survive extraction, and no amount of cleaning turns it back into one.
    """
    t = str(text or "").strip()
    if len(t) < 3:
        return False
    letters = [c for c in t if c.isalpha()]
    if len(letters) < 3:
        return False
    if not any(c.lower() in "aeiou" for c in letters):
        return False
    # Three or more of the same character in a row is extraction noise.
    return not re.search(r"(.)\1{2,}", t)


def repair(title):
    """The best title we can honestly give this passage.

    Returns None when nothing needs doing.
    """
    raw = str(title or "")
    book, _, chapter = raw.partition(":")
    chapter = chapter.strip()
    # Furniture that reads as content, in either direction. Checked BEFORE
    # the readable() shortcut: "II-traP" is Part-II set as rotated sidebar
    # text, and it passes readable() — it has a vowel, no tripled letters and
    # three characters — so the shortcut returned None and left it in place.
    if _c._NOT_A_TITLE.match(chapter) or _c._NOT_A_TITLE.match(chapter[::-1]):
        return book.strip() or None
    if not chapter or readable(chapter):
        return None

    fixed = undouble(chapter)
    # Furniture, forwards or backwards.
    #
    # "II-traP" survived readable() — it has vowels, no tripled letters, and
    # is three characters long — and it is "Part-II" set as rotated sidebar
    # text, which comes out of the PDF reversed. A chapter titled "II-traP"
    # is worse than one titled after its book, because it looks like content.
    if _c._NOT_A_TITLE.match(fixed) or _c._NOT_A_TITLE.match(fixed[::-1]):
        return book.strip() or None
    if readable(fixed):
        # NCERT sets headings in capitals; keep the words, not the shouting.
        if fixed.isupper():
            fixed = fixed.title()
        return f"{book.strip()}: {fixed}".strip()

    # Nothing recoverable. The BOOK is real and is the honest label — better
    # than a string of consonants, and it still tells the model and the
    # reader which text this came from.
    return book.strip() or None


# --------------------------------------------------------------------------
# The second repair: titles that are not the chapter's name at all.
#
# The doubling above is one way an NCERT heading arrives wrong. A live search
# for "rocket" showed three more, and between them they account for 92 of the
# corpus's 317 NCERT chapter titles — nearly a third:
#
#   "Class 11 Physics: HAPTER IVE"   the drop cap on CHAPTER, lifted off by
#                                    the extractor and placed elsewhere
#   "Class 10 Mathematics: MATHEMATICS"   the running head at the top of the
#                                    page, taken as the chapter's name
#   "Class 10 Mathematics: REAL NUMBERS 1"   the page number, set on the
#                                    heading's own line
#
# corpus.title_of now rejects all three, but that only helps a corpus built
# again from four hundred PDFs, which is about three hours. The chapter's own
# text is already here, so the title is re-derived from the first passage of
# each chapter instead — the same function, on the same words, in a second.


def _rederive(con):
    """Re-read each chapter's title out of its own opening passage."""
    import corpus as _corpus

    rows = list(con.execute(
        "select distinct slug, title from passages where title like 'Class %'"))
    out = []
    for slug, title in rows:
        head = title.split(": ", 1)[1] if ": " in title else title
        prefix = title[:len(title) - len(head)]
        broken = bool(_corpus._DROPPED_CAP.match(head)
                      or _corpus._SUBJECT_ALONE.match(head)
                      or _corpus._PAGE_TAIL.search(head)
                      or len(head) > 60)
        body = con.execute(
            "select body from passages where slug = ? order by rowid limit 1",
            (slug,)).fetchone()
        if not body:
            continue

        # A real chapter name, printed backwards.
        #
        # NCERT sets some headings as rotated sidebar text and pdfplumber
        # returns those reversed, so Class 10 Civics ch 1 was titled
        # "ycarcomeD". Every earlier rule looks for furniture or for noise;
        # this is neither, which is why it survived all of them — it is the
        # right word, mirrored.
        #
        # Confirmed against the chapter's own text rather than guessed: the
        # reversal is only accepted if the word it produces actually appears
        # in the chapter, which no accident of letters is going to satisfy.
        back = head[::-1].strip()
        if (len(back) > 3 and back.lower() != head.lower()
                and back.lower() in (body[0] or "").lower()
                and head.lower() not in (body[0] or "").lower()):
            out.append((slug, title, prefix + back))
            continue
        if not broken:
            continue
        fresh = _corpus.title_of(body[0])
        # Only when it is actually better. A chapter whose opening passage
        # does not carry its heading keeps the name it has: a wrong title is
        # bad and an empty one is worse, because nothing then labels the
        # source a model is quoting from.
        if not fresh or fresh == head or len(fresh) < 3:
            continue
        if (_corpus._DROPPED_CAP.match(fresh)
                or _corpus._SUBJECT_ALONE.match(fresh)
                or _corpus._NOT_A_TITLE.match(fresh)):
            continue
        out.append((slug, title, prefix + fresh))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=CORPUS)
    ap.add_argument("--dry", action="store_true",
                    help="show what would change and write nothing")
    args = ap.parse_args()

    if not os.path.exists(args.db):
        print(f"no corpus at {args.db}")
        return 1

    con = sqlite3.connect(args.db)
    titles = [r[0] for r in con.execute("select distinct title from passages")]

    changes = []
    for t in titles:
        new = repair(t)
        if new and new != t:
            changes.append((t, new))

    # ...and the ones where the string cannot be repaired because it was
    # never the title: read those out of the chapter's own opening again.
    seen = {old for old, _ in changes}
    by_slug = [row for row in _rederive(con) if row[1] not in seen]

    if not changes and not by_slug:
        print("nothing to repair")
        return 0

    for old, new in changes:
        n = con.execute("select count(*) from passages where title = ?",
                        (old,)).fetchone()[0]
        print(f"  {n:5d}  {old[:52]!r}\n         -> {new[:52]!r}")
    for slug, old, new in by_slug:
        n = con.execute("select count(*) from passages where slug = ?",
                        (slug,)).fetchone()[0]
        print(f"  {n:5d}  {slug}  {old[:42]!r}\n         -> {new[:52]!r}")

    total = len(changes) + len(by_slug)
    if args.dry:
        print(f"\n{total} titles would change. Nothing written.")
        return 0

    for old, new in changes:
        con.execute("update passages set title = ? where title = ?",
                    (new, old))
    # Keyed on the SLUG. Five different Class 12 Physics chapters are all
    # called "Physics" right now, so matching on the title would give all
    # five whichever name the last one produced — one wrong title replaced
    # by a confidently wrong one, which is worse than leaving it alone.
    for slug, _old, new in by_slug:
        con.execute("update passages set title = ? where slug = ?",
                    (new, slug))
    con.commit()
    con.close()
    print(f"\n{total} titles repaired.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
