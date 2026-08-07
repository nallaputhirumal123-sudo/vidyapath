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
    if not chapter or readable(chapter):
        return None

    fixed = undouble(chapter)
    if readable(fixed):
        # NCERT sets headings in capitals; keep the words, not the shouting.
        if fixed.isupper():
            fixed = fixed.title()
        return f"{book.strip()}: {fixed}".strip()

    # Nothing recoverable. The BOOK is real and is the honest label — better
    # than a string of consonants, and it still tells the model and the
    # reader which text this came from.
    return book.strip() or None


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

    if not changes:
        print("nothing to repair")
        return 0

    for old, new in changes:
        n = con.execute("select count(*) from passages where title = ?",
                        (old,)).fetchone()[0]
        print(f"  {n:5d}  {old[:52]!r}\n         -> {new[:52]!r}")

    if args.dry:
        print(f"\n{len(changes)} titles would change. Nothing written.")
        return 0

    for old, new in changes:
        con.execute("update passages set title = ? where title = ?",
                    (new, old))
    con.commit()
    con.close()
    print(f"\n{len(changes)} titles repaired.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
