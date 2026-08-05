"""Build the searchable corpus, once, into a file the app opens read-only.

Run it deliberately, not at startup: it fetches a few hundred four-megabyte
PDFs from a government server and takes about three hours. Startup has to be
seconds, and a server that downloads NCERT every time it restarts would be
both slow and rude.

    python tools/build_corpus.py                 everything
    python tools/build_corpus.py --class 10      one class
    python tools/build_corpus.py --limit 20      a slice, to try it
    python tools/build_corpus.py --skip-ncert    curriculum only

The curriculum goes in alongside NCERT, in the same index, because a question
should be answered from whichever of the two actually covers it — and two
indexes searched separately means somebody has to decide which to ask first,
which is a decision with no good answer.

Writes to corpus.db, and does not touch the one in place until it has
finished. A three-hour build that dies at hour two must not leave the app with
half a corpus and no way to tell.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ.setdefault("DATABASE_URL", "sqlite:///./vidyapath.db")
os.environ.setdefault("JOBS_ENABLED", "0")

import corpus                                      # noqa: E402
import rag                                         # noqa: E402

FINAL = "corpus.db"
TEMP = "corpus.db.building"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--class", dest="klass", type=int, default=None)
    ap.add_argument("--subject", default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--skip-ncert", action="store_true")
    ap.add_argument("--fresh", action="store_true",
                    help="throw away a part-built corpus and start over")
    args = ap.parse_args()

    # A leftover from a build that was interrupted must not block the next
    # one. On Windows a killed process can leave the file locked for a while,
    # and os.remove then raises PermissionError — so the script died with a
    # stack trace and no corpus, over a corpse. Take a fresh name instead:
    # the swap at the end is what matters, not which temporary file it came
    # from.
    # A part-built corpus is picked up, not deleted.
    #
    # This used to remove it and start over, which was the second half of the
    # same mistake as committing once at the end: a run that reached chapter
    # 205 of 222 and lost power left everything it had fetched in this file,
    # and the next run's first act was to delete it. Two hours of downloading
    # thrown away twice over.
    #
    # Now: if it is there and readable, carry on from it. --fresh is the way
    # to start again on purpose.
    temp = TEMP
    resume = False
    if os.path.exists(temp) and not args.fresh:
        have = rag.open_fts(temp)
        if have is not None:
            n = len(corpus.already_in(have))
            have.db.close()
            if n:
                resume = True
                print(f"resuming a part-built corpus: {n} chapters already in")
    if not resume:
        try:
            if os.path.exists(temp):
                os.remove(temp)
        except OSError:
            temp = f"{TEMP}.{os.getpid()}"
            print(f"note: {TEMP} is locked, using {temp}")
    # A journal left by a killed process is rolled back when SQLite opens it.
    ix = (rag.open_fts(temp) if resume else rag.build_fts([], temp))
    started = time.time()

    # The curriculum first: it is local, it takes a moment, and if the NCERT
    # fetch fails entirely there is still a usable corpus at the end.
    #
    # Skipped when resuming, because it is already in there. Adding it again
    # would not fail — it would quietly double every lesson, and a corpus that
    # holds each passage twice scores those passages twice.
    if resume:
        print("curriculum: already indexed, left alone")
    else:
        import main as app
        db = app.SessionLocal()
        rows = [(l.content or "", l.title or "", tr.name or "", l.slug or "")
                for l, tr in db.query(app.Lesson, app.Track)
                .join(app.Track, app.Track.id == app.Lesson.track_id)
                .filter(app.Lesson.published == True).all()]   # noqa: E712
        for content, title, track, slug in rows:
            if content:
                ix.add(content, title, track, slug)
        ix.finish()
        print(f"curriculum: {len(rows)} lessons, {ix.n} passages")

    report = {"indexed": 0, "failed": [], "chars": 0}
    if not args.skip_ncert:
        want = corpus.chapters(only_class=args.klass, only_subject=args.subject)
        if args.limit:
            want = want[:args.limit]
        print(f"ncert: {len(want)} chapters to fetch "
              f"(~{len(want) * 40 / 3600:.1f} hours)")
        report = corpus.ingest(ix, want, resume=True)
    ix.finish()

    mins = (time.time() - started) / 60
    print(f"\npassages: {ix.n}")
    print(f"ncert chapters indexed: {report['indexed']}, "
          f"already had: {report.get('skipped', 0)}, "
          f"failed: {len(report['failed'])}")
    if report["failed"]:
        print("  failed codes: " + ", ".join(report["failed"][:30]))
    print(f"took {mins:.1f} minutes")

    ix.db.close()
    # Swapped in only now. A build that dies halfway must not leave the app
    # reading half a corpus while believing it is whole.
    if os.path.exists(FINAL):
        os.replace(FINAL, FINAL + ".old")
    os.replace(temp, FINAL)
    print(f"\nwrote {FINAL} — restart the app to pick it up")


if __name__ == "__main__":
    main()
