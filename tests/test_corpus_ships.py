"""The books travel with the code.

corpus.db holds eighteen NCERT books and 7,523 passages, and it was
gitignored as a build artefact. That is ordinary hygiene with a consequence
nobody had costed: a deployment made from this repository had NO NCERT in it.
Retrieval fell back to the site's own coding lessons, every science question
was answered from the model's memory with no book behind it, and nothing said
so — on a product sold to schools as "answers from the syllabus".

Rebuilding on the server is not an option. The builder fetches a few hundred
PDFs from a government site and takes about three hours; that is a batch job,
not a deploy step. So the corpus ships, gzipped from 15.7 MB to 6.7 MB, and
is unpacked at boot in under a tenth of a second — both measured.

The value of doing it this way rather than downloading at boot or mounting a
prepared volume is that the corpus and the code that expects it are ONE
artefact. There is no window where the app is up and the books are not, and
nothing to provision by hand before a deploy works.

Four situations, and the third is the one that would have bitten in a year:

  a fresh deploy      no corpus anywhere — unpack it
  an ordinary restart it is already there — do nothing, quickly
  a REBUILT corpus    CORPUS_PATH is a volume in production and a volume
                      survives the deploy that replaces the archive. Without
                      a stamp saying which archive the file came from, the
                      unpack is skipped and the old books are served for ever
                      by a deployment that looks entirely healthy.
  somebody's own file a corpus with no stamp beside it was put there by hand.
                      Left alone: overwriting it because we cannot prove where
                      it came from is worse than serving it.
"""
import gzip
import hashlib
import io
import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"

import main                                        # noqa: E402
import rag                                         # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P, F = [], []


def ck(n, c, d=""):
    print(("PASS " if c else "FAIL ") + n + (f" — {d}" if d else ""),
          flush=True)
    (P if c else F).append(n)


print("\nthe archive is in the repository")
GZ = os.path.join(ROOT, "corpus.db.gz")
ck("corpus.db.gz exists", os.path.exists(GZ),
   "without it a deployment has no NCERT at all")
if os.path.exists(GZ):
    mb = os.path.getsize(GZ) / 1e6
    ck(f"and it is small enough to commit ({mb:.1f} MB)", mb < 25,
       "a binary in git is a real cost; a product that cannot do the thing "
       "it is sold for is a larger one")

ign = io.open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
ck("the ignore rule lets it through", "!corpus.db.gz" in ign)
ck("while the raw build artefact stays ignored", "corpus.db*" in ign)

src = io.open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
ck("it is unpacked before the corpus is opened",
   "_unpack_corpus()\n    built = _rag.open_fts(CORPUS_PATH)" in src,
   "the order is the whole point — a fresh process unpacks, then reads")
ck("and a failure to unpack is never fatal",
   "could not unpack the" in src,
   "a server that will not boot because it could not write a cache file is "
   "worse than one that boots without NCERT and says so")
# One unpacker, two archives. The books and their pictures have different
# lives — the text is rebuilt when a book changes, the pictures when the
# extraction improves — but the mechanics of getting either into place are
# the same, and two copies of this logic is how one of them loses its stamp.
# The unpacker is parameterised even though only one archive uses it now.
# The corpus is 24.5 MB of text down to 10.2 and worth compressing; the
# diagrams are already JPEG, where gzip buys eight per cent in exchange for
# an unpack at boot, a stamp to keep in step with it, and twice the disk
# while both copies exist. They ship raw and are read where they land.
ck("the unpacker is general, not corpus-shaped",
   "def _unpack_gz(gz, target, label):" in src)
ck("and the pictures do not go through it", "PICS_GZ" not in src,
   "eight per cent is not worth a second thing that can be out of date")
ck("the warning about a missing corpus is still there",
   "NCERT is NOT loaded" in src)

# --------------------------------------------------------------------------
# The four situations, against a throwaway directory rather than the real
# corpus — this file must be safe to run on a working laptop.
print("\nwhat happens at boot")
tmp = tempfile.mkdtemp(prefix="corpus-ships-")
real_path, real_gz = main.CORPUS_PATH, main.CORPUS_GZ
try:
    main.CORPUS_PATH = os.path.join(tmp, "corpus.db")
    main.CORPUS_GZ = os.path.join(tmp, "corpus.db.gz")
    # A small but genuine FTS corpus, built the way the real one is.
    seed = os.path.join(tmp, "seed.db")
    # Long enough to survive chunking — a one-line passage indexes to nothing,
    # and an empty corpus is exactly what open_fts is right to refuse.
    rag.build_fts([(("Photosynthesis is the process by which green plants "
                     "use light energy to make food. It happens in the "
                     "chloroplast, which contains the green pigment "
                     "chlorophyll. Carbon dioxide from the air and water "
                     "from the soil are combined, and oxygen is given off "
                     "as a by-product. The food made is stored as starch. "
                     ) * 6, "Photosynthesis", "Biology", "bio-1")], seed)
    with open(seed, "rb") as s, gzip.open(main.CORPUS_GZ, "wb", 6) as d:
        shutil.copyfileobj(s, d, 1024 * 1024)
    want = hashlib.sha256(open(seed, "rb").read()).hexdigest()

    main._unpack_corpus()
    ck("a fresh deploy unpacks the archive",
       os.path.exists(main.CORPUS_PATH))
    ck("byte for byte",
       os.path.exists(main.CORPUS_PATH)
       and hashlib.sha256(open(main.CORPUS_PATH, "rb").read()).hexdigest()
       == want)
    # Opened and CLOSED. The real boot order is unpack, then read, and a
    # handle held open across the next unpack is a situation that cannot
    # arise there — on Windows it would also make os.replace fail, which is
    # a property of this test rather than of the code.
    opened = rag.open_fts(main.CORPUS_PATH)
    ck("and what lands is a readable index", opened is not None)
    ck("with the passage in it", bool(opened and opened.n),
       str(getattr(opened, "n", None)))
    if opened is not None:
        try:
            opened.db.close()
        except Exception:
            pass
    ck("a stamp records which archive it came from",
       os.path.exists(main.CORPUS_PATH + ".from"))

    t = time.time()
    main._unpack_corpus()
    el = time.time() - t
    ck(f"an ordinary restart does nothing, quickly ({el * 1000:.1f} ms)",
       el < 0.5)

    # The one that would have bitten in a year.
    os.utime(main.CORPUS_GZ, (time.time() + 120, time.time() + 120))
    main._unpack_corpus()
    ck("a rebuilt corpus replaces the one on the volume",
       open(main.CORPUS_PATH + ".from", encoding="utf-8").read().strip()
       == f"{os.path.getsize(main.CORPUS_GZ)}:"
          f"{int(os.stat(main.CORPUS_GZ).st_mtime)}",
       "a volume survives the deploy that replaces the archive, so without "
       "this the old books are served for ever")

    # Somebody's own file, put there by hand.
    os.remove(main.CORPUS_PATH + ".from")
    with open(main.CORPUS_PATH, "wb") as fh:
        fh.write(b"a corpus somebody put here themselves")
    main._unpack_corpus()
    ck("an unstamped corpus is left alone",
       open(main.CORPUS_PATH, "rb").read()
       == b"a corpus somebody put here themselves",
       "overwriting it because we cannot prove where it came from is worse "
       "than serving it")

    # And no half-written database is ever left behind.
    ck("nothing is left part-unpacked",
       not os.path.exists(main.CORPUS_PATH + ".unpacking"),
       "it is written beside the target and moved into place")
finally:
    main.CORPUS_PATH, main.CORPUS_GZ = real_path, real_gz
    shutil.rmtree(tmp, ignore_errors=True)

print("\nit is unpacked at STARTUP, not on the first question")
# It used to happen lazily, inside the retrieval index's first build, which
# meant it had not happened yet for anything that opens the corpus FILE
# directly. The syllabus-coverage page does exactly that, so a fresh
# container told every coaching centre that looked "No corpus is built on
# this deployment" until somebody happened to ask a question first. It said
# it in production, on the deploy that shipped the corpus.
ck("startup unpacks it", "    try:\n        _unpack_corpus()" in src,
   "a page that reads the corpus can be served before any question is asked")
ck("and it is not left to the background thread",
   src.index("_unpack_corpus()\n    except Exception")
   < src.index("asyncio.create_task(asyncio.to_thread(_seed_with_retries))"),
   "a request can arrive before that thread finishes")
ck("the coverage route still reports honestly when there is none",
   "No corpus is built on this deployment." in src,
   "a hard-coded yes is a promise the product breaks in front of a class")

print("\nand a running server says what it actually has")
# Both the books and their figures travel in the repository, and both have
# been missing from a running server before — the corpus for months, in
# silence, on a product sold as "answers from the syllabus". A number on the
# status page is how anybody checks without a subject code, and without
# guessing from whether an answer "looks grounded".
ck("the passage count is reported",
   '"corpus_passages": _corpus_count()' in src)
ck("and the diagram count with it",
   '"book_diagrams": _diagram_count()' in src)
ck("both read the file rather than remembering a number",
   "def _corpus_count():" in src and "def _diagram_count():" in src)
ck("and neither can take the status page down",
   src.count("    except Exception:\n        return 0") >= 2,
   "a status page that falls over is one nobody can use at the moment they "
   "most need it")

print("\nand the real corpus is still what it should be")
if os.path.exists(real_path):
    live = rag.open_fts(real_path)
    ck("it opens", live is not None)
    if live:
        ck(f"with {live.n} passages", live.n > 5000, str(live.n))
        ck("and answers a question from the books",
           len(live.search("photosynthesis", 3)) > 0)

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
