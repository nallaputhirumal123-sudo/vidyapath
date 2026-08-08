"""Ingest ONE chapter into the corpus and the diagram archive.

A full rebuild is two hours and re-fetches three hundred PDFs to add a
chapter that failed. This does the one, into both files, and is idempotent —
a chapter already in either is left alone.

It exists because of lebo102. Class 12 Biology chapter 2 is a 64 MB PDF, and
it was the single chapter missing from both the text corpus and the picture
archive after two independent runs on different days. In the logs it read as
a network failure, because the first probe of it happened to time out, and
the size cap underneath would have refused it anyway. Neither log said
"64 MB", so it looked like the same transient failure twice.

    .\\.venv\\Scripts\\python.exe tools\\add_chapter.py lebo102
"""
import argparse
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ.setdefault("DATABASE_URL", "sqlite:///./vidyapath.db")
os.environ.setdefault("ALLOW_SQLITE", "1")
os.environ.setdefault("JOBS_ENABLED", "0")

import corpus                                      # noqa: E402
import rag                                         # noqa: E402

CORPUS = "corpus.db"
PICS = "corpus-pics.db"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("code")
    args = ap.parse_args()
    code = args.code.strip().lower()

    want = [c for c in corpus.chapters() if c[0] == code]
    if not want:
        print(f"{code} is not a chapter in the books this repo knows about.")
        return 1
    _c, klass, subject, n = want[0]

    print(f"{code}: Class {klass} {subject}, chapter {n}")
    t = time.time()
    raw = corpus.fetch(code)
    if not raw:
        print("  could not be fetched")
        return 1
    print(f"  fetched {len(raw)/1e6:.1f} MB in {time.time()-t:.0f}s")

    # ---- the text
    ix = rag.open_fts(CORPUS)
    if ix is None:
        print(f"  no corpus at {CORPUS}")
        return 1
    if code in corpus.already_in(ix):
        print("  text: already in")
    else:
        text = corpus.text_of(raw)
        if len(text) < 400:
            print(f"  text: only {len(text)} chars — not indexed")
        else:
            title = corpus.title_of(text, f"{subject} chapter {n}")
            ix.add(text, f"Class {klass} {subject}: {title}",
                   f"NCERT Class {klass} {subject}", code)
            ix.db.commit()
            print(f"  text: {len(text):,} chars — {title[:60]}")
    ix.db.close()

    # ---- the pictures
    if not os.path.exists(PICS):
        print(f"  pictures: no {PICS}, skipped")
        return 0
    con = sqlite3.connect(PICS)
    try:
        done = {r[0] for r in con.execute("SELECT code FROM done")}
        if code in done:
            print("  pictures: already looked at")
        else:
            # The archive stores the JPEG bytes, not a data URI — the route
            # builds the URI when it serves them, so the file is not carrying
            # a third of its own size in base64.
            import base64
            pics = corpus.chapter_pictures(code)
            for p in pics:
                jpeg = base64.b64decode(p["src"].split(",", 1)[1])
                con.execute(
                    "INSERT INTO pictures(code, page, w, h, jpeg) "
                    "VALUES (?,?,?,?,?)",
                    (code, p.get("page", 0), p["w"], p["h"], jpeg))
            con.execute("INSERT OR REPLACE INTO done(code) VALUES (?)",
                        (code,))
            con.commit()
            print(f"  pictures: {len(pics)}")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
