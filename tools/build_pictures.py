"""Pull every NCERT chapter's diagrams into a file the app ships.

The corpus holds the text of eighteen books and none of their pictures. For
most questions that is the right trade — the numbers are in the passage and
the board draws its own diagram. It is the wrong trade for the chapters whose
whole point IS the figure: a ray diagram, a labelled cell, a circuit, the
layout of a balance sheet. A lesson about a ray diagram is not that lesson
with the picture removed; it is a paragraph about a picture nobody can see.

These were fetched on demand at first, and the measurement killed that idea:
the first request for a chapter took **33 seconds**, because ncert.nic.in
throttles and the fetch retries through it. Thirty-three seconds is fine in a
script and unusable standing in front of a class. So they ship.

Re-encoded to JPEG at 900px, because these are PRINT images — a Class 11
Biology chapter carries 800 KB of them at a resolution meant for paper, and a
projector shows 1080 lines. That is 118 MB raw down to about 28 MB.

    .\\.venv\\Scripts\\python.exe tools\\build_pictures.py
    .\\.venv\\Scripts\\python.exe tools\\build_pictures.py --limit 20

Writes corpus-pics.db, and resumes: a chapter already in it is not fetched
again. Interrupt it and run it again.
"""
import argparse
import base64
import io
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ.setdefault("DATABASE_URL", "sqlite:///./vidyapath.db")
os.environ.setdefault("JOBS_ENABLED", "0")

import corpus                                       # noqa: E402
import teachpdf                                     # noqa: E402

OUT = "corpus-pics.db"


def open_store(path=OUT):
    con = sqlite3.connect(path)
    con.execute("""CREATE TABLE IF NOT EXISTS pictures(
        code TEXT, page INTEGER, w INTEGER, h INTEGER, jpeg BLOB)""")
    # `done` records that a chapter was LOOKED AT, which is not the same as it
    # having pictures. Without it every chapter with no diagrams — and there
    # are plenty — is re-downloaded on every run for ever.
    con.execute("CREATE TABLE IF NOT EXISTS done(code TEXT PRIMARY KEY)")
    con.execute("CREATE INDEX IF NOT EXISTS pic_code ON pictures(code)")
    con.commit()
    return con


def shrink(src):
    """One extracted picture, re-encoded small enough to project."""
    from PIL import Image
    blob = base64.b64decode(src.split(",", 1)[1])
    im = Image.open(io.BytesIO(blob)).convert("RGB")
    im.thumbnail((corpus.PIC_MAX_SIDE, corpus.PIC_MAX_SIDE))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=corpus.PIC_QUALITY, optimize=True)
    return buf.getvalue(), im.width, im.height


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--class", dest="klass", type=int, default=None)
    args = ap.parse_args()

    con = open_store()
    already = {r[0] for r in con.execute("SELECT code FROM done")}
    want = corpus.chapters(only_class=args.klass)
    todo = [c for c in want if c[0] not in already]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(want)} chapters, {len(already)} already looked at, "
          f"{len(todo)} to do")

    started = time.time()
    kept = chapters_with = 0
    for i, (code, klass, subject, n) in enumerate(todo, 1):
        raw = corpus.fetch(code)
        if not raw:
            # Not marked done: a chapter that would not download is one to try
            # again next run, not one we know has no pictures.
            print(f"  {code}: not fetched")
            continue
        try:
            found = teachpdf.pictures(raw)
        except Exception as e:
            print(f"  {code}: {type(e).__name__}")
            found = []
        rows = []
        for p in found[:corpus.PIC_PER_CHAPTER]:
            try:
                jpeg, w, h = shrink(p.get("src") or "")
            except Exception:
                continue
            rows.append((code, p.get("page", 0), w, h, jpeg))
        if rows:
            con.executemany("INSERT INTO pictures VALUES (?,?,?,?,?)", rows)
            chapters_with += 1
            kept += len(rows)
        con.execute("INSERT OR REPLACE INTO done VALUES (?)", (code,))
        con.commit()          # after every chapter: an interruption costs one
        if rows or i % 20 == 0:
            mb = os.path.getsize(OUT) / 1e6
            print(f"  [{i}/{len(todo)}] {code}: {len(rows)} pictures "
                  f"({kept} kept, {mb:.0f}MB)")

    con.execute("VACUUM")
    con.close()
    mb = os.path.getsize(OUT) / 1e6
    print(f"\n{kept} pictures from {chapters_with} chapters — {mb:.1f}MB")
    print(f"took {(time.time() - started) / 60:.1f} minutes")


if __name__ == "__main__":
    main()
