"""The libraries a school network cannot be trusted to fetch.

A school filters its network. That is not an edge case here — it is the
market. Every part of this product that reads or writes a PDF was pulling its
library from a public CDN, and a blocked CDN produces a failure with no cause
anyone in the room can see:

  - **pdf.js** and its worker, from cdn.jsdelivr.net. Used for marking
    homework on the board, turning an uploaded chapter into a lesson, and
    reading a scanned paper. The WORKER is the worse half: it is fetched
    later, from inside the library, so a network that blocks it fails after
    the reader has apparently loaded fine.
  - **pdf-lib**, from the same host, which writes the marked-up PDF back out.
    A teacher can annotate a worksheet for a whole period and only find out
    at Save.
  - **jsPDF**, from cdnjs.cloudflare.com, which every download on the site
    goes through.

All four files ship with the app now and are served from this origin. The CDN
stays as a second try, for a deployment older than the files, and the version
is pinned identically on both sides.

**The worker always comes from wherever the library came from.** A worker of
one version under a library of another does not fail cleanly: it fails while
reading the document, which reads as a corrupt file rather than a mismatched
pair.
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("DATABASE_URL", "sqlite:///./vidyapath.db")
os.environ.setdefault("ALLOW_SQLITE", "1")

IDX = io.open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
PV = io.open(os.path.join(ROOT, "pdfview.js"), encoding="utf-8").read()
P, F = [], []


def ck(name, cond, why=""):
    print(("PASS " if cond else "FAIL ") + name + (" — " + why if why else ""),
          flush=True)
    (P if cond else F).append(name)


def chunk(src, header):
    """One function's own text, so a search cannot wander into another's.

    Stripping /* */ comments out of a file this size joins an opener in one
    string to a closer in another and eats the code between them, which is
    how two checks in the sibling test passed for the wrong reason.
    """
    return src.split(header)[1].split("\nfunction ")[0]


print("\nthe files are here, and they are what they claim to be")
FILES = [
    ("jspdf.umd.min.js", 200_000,
     "jsPDF - PDF Document creation from JavaScript"),
    ("pdf.min.js", 200_000, "3.11.174"),
    ("pdf.worker.min.js", 500_000, "3.11.174"),
    ("pdf-lib.min.js", 300_000, "PDFDocument"),
]
for name, least, mark in FILES:
    path = os.path.join(ROOT, name)
    there = os.path.isfile(path)
    ck(name + " ships with the app",
       there and os.path.getsize(path) >= least,
       "missing" if not there else "only %d bytes" % os.path.getsize(path))
    if there:
        head = io.open(path, encoding="utf-8", errors="ignore").read(400_000)
        ck(name + " is the right library", mark in head)

print("\nand this server will serve them")
from fastapi.testclient import TestClient                # noqa: E402
import main                                              # noqa: E402
c = TestClient(main.app)
for name, _, _ in FILES:
    r = c.get("/" + name)
    ck("GET /" + name, r.status_code == 200
       and "javascript" in r.headers.get("content-type", ""),
       "%s %s" % (r.status_code, r.headers.get("content-type")))

print("\nthe page asks this server first, everywhere")
ENS = chunk(IDX, "function ensurePdfJs(")
ck("the reader is loaded from here", 'load("/")' in ENS)
ck("and the CDN is only the fallback",
   'load("/").catch(()=>load(CDN))' in ENS,
   "checking which URL appears first in the text finds where the constant "
   "is declared, not which one is tried first")
ck("the worker comes from the same place as the library",
   'base+"pdf.worker.min.js"' in ENS,
   "a worker of one version under a library of another fails while reading "
   "the document, which reads as a corrupt file")
ck("a script that loads but is empty counts as a failure",
   '"loaded but empty"' in ENS,
   "onload fires for a blocked page served as an error document too")
ck("and there is one loader, not one per caller",
   IDX.count("pdfjs-dist@3.11.174/build/pdf.min.js") == 0,
   "the URL was written out at each call site; the worker was set in some "
   "of them and not others")

print("\nso does the board, which is the one on the school's own network")
ck("pdf.js is loaded from here", 'var HERE = "/";' in PV)
ck("the reader tries here before the CDN",
   PV.index("pdfjsFrom(HERE)") < PV.index("pdfjsFrom(PDFJS)"))
ck("the writer does too",
   PV.index('script(HERE + "pdf-lib.min.js")') < PV.index("script(PDFLIB)"))
ck("the board's worker follows its library",
   'base + "pdf.worker.min.js"' in PV)
ck("an empty load is a failure there too", '"loaded but empty"' in PV)
ck("and the message no longer blames a CDN that is now a fallback",
   "public CDN" not in PV.split("*/", 1)[1],
   "telling a teacher the file comes from a CDN is no help when the "
   "first place it was looked for was this site")

print("\nand nothing warms a connection to a host we hope not to use")
ck("the jsdelivr preconnect is gone",
   'preconnect" href="https://cdn.jsdelivr.net' not in IDX,
   "a DNS lookup and a TLS handshake on every page load, for a fallback")
ck("the font preconnects stay",
   'preconnect" href="https://fonts.googleapis.com' in IDX)

print("\n" + ("PASSED %d   FAILED %d" % (len(P), len(F))))
if F:
    for name in F:
        print("  FAILED: " + name)
    sys.exit(1)
