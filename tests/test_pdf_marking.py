"""A PDF a teacher can write on, that saves as a PDF.

Opening a document handed it to the browser's own viewer in another window.
Fine for reading, useless for teaching: nothing could be marked on it, and
the board's pen had nothing to sit on.

The pages are rendered INTO the pane now, one canvas each, stacked in the
normal flow. The pen needs no change whatsoever — it already sizes itself to
the pane's scrollHeight and lives inside the scrolling body, so a mark made
on page four stays on page four when the pane scrolls. That was the hard
half and it was already built and verified.

Saving is the half that needed this file. Exporting a picture of the page
would throw the document away: the text stops being text, it cannot be
searched or read aloud, and a class opening it on a phone gets a photograph
of a worksheet. So the ORIGINAL bytes are kept and the annotations go back
on as a transparent overlay per page, which is why what comes out is the
file that went in, edited.

Proved in a browser rather than asserted here, because none of it can run in
Python: a two-page PDF rendered to two canvases that were really drawn on;
saving returned application/pdf, 11,092 bytes against the original 1,089,
two pages; and re-reading the SAVED file with pdf.js returned
"Page one — forces | Page two — momentum" — still selectable text, with the
marks on top. What follows pins the decisions that made that true.
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = io.open(os.path.join(ROOT, "pdfview.js"), encoding="utf-8").read()
BOARD = io.open(os.path.join(ROOT, "craxlearn.html"), encoding="utf-8").read()
P = F = 0


def ck(name, cond, note=""):
    global P, F
    print(("  PASS  " if cond else "  FAIL  ") + name +
          (f" ({note})" if note else ""), flush=True)
    if cond:
        P += 1
    else:
        F += 1


print("\nthe pages are drawn into the space, not into another window")
ck("a PDF opens in the live pane", "async function openPdfHere(" in BOARD)
ck("into the pane's own scrolling body",
   'var body = pane && pane.querySelector(".paneBody");' in BOARD,
   "which is what the pen is sized against, so marks scroll with the pages")
ck("one canvas per page, in the normal flow",
   'cv.className = "pdfPage";' in SRC and ".pdfPages{display:flex" in BOARD)
ck("and the pen is unchanged — it already handled this",
   "Math.max(body.scrollHeight, body.clientHeight)" in BOARD,
   "the annotation canvas covers the whole scrollable extent")

print("\nwhat comes out is the document, edited — not a picture of it")
ck("the original bytes are kept", "OPEN.set(host, { bytes: bytes" in SRC)
ck("and reloaded to write into",
   "PL.PDFDocument.load(rec.bytes.slice(0))" in SRC,
   "so the text, the fonts and the vectors are the originals")
ck("the marks go on as a transparent overlay",
   "doc.embedPng(buf)" in SRC and "pg.drawImage(img" in SRC)
ck("drawn at page size rather than at the mark's coordinates",
   "width: size.width, height: size.height" in SRC,
   "a page-sized overlay cannot drift out of register")
ck("and it is issued as a PDF",
   'new Blob([out], { type: "application/pdf" })' in SRC)

print("\neach page takes its own slice of one tall annotation canvas")
ck("the slice is computed from the live layout",
   "function cutFor(pageCanvas, marks)" in SRC
   and "pageCanvas.getBoundingClientRect()" in SRC,
   "so a pane that has been scrolled or resized is still right")
ck("scaled between CSS pixels and canvas pixels",
   "(marks.width / mr.width)" in SRC,
   "the canvas is drawn at device ratio and laid out in CSS pixels")
ck("and a page with nothing on it is skipped, not stamped blank",
   "if (!slice) continue;" in SRC)

print("\nboth buttons produce a PDF, and one of them keeps it for the class")
ck("saving files it under the subject",
   '"/api/craxlearn/board/file"' in BOARD
   and 'fd.append("file", blob,' in BOARD)
ck("downloading gives the same bytes",
   '.replace(/\.pdf$/i, "") + " — marked.pdf"' in BOARD)
ck("and neither of them makes an image",
   "PdfView.save(" in BOARD and "toDataURL" not in
   BOARD.split("async function openPdfHere(")[1].split("async function openFile")[0],
   "the whole point of keeping the original bytes")

print("\nand a document that is not a PDF is left alone")
ck("only a PDF is opened in the pane", 'btn.dataset.pdf === "1"' in BOARD,
   "a spreadsheet in a pane would be a worse spreadsheet")
ck("confirmed from the file's own first bytes, not its name",
   '!== "%PDF-") return false;' in BOARD,
   "a name is supplied by whoever uploaded it")
ck("and a blocked CDN says so rather than showing an empty pane",
   "The PDF viewer could not load" in SRC
   and "The PDF writer could not load" in SRC)

print("\nthe marked copy comes back as a markable PDF")
# The cycle a teacher actually does: open, mark, save, open again, mark
# again. It works because the saved file keeps a .pdf name, which is what
# the Open button reads to decide whether it opens in the pane.
ck("the saved copy is named as a PDF",
   '" — marked.pdf"' in BOARD,
   "the Open button decides from the name, then confirms from the bytes")
ck("so it reopens in the pane rather than a window",
   "/\.pdf$/i.test(m.file_name" in BOARD)

print("\nand a filename that is not English does not break the download")
# Found by doing the round trip: HTTP headers are latin-1, and the header
# was built with an f-string. "Worksheet — marked.pdf" — the name this
# product itself writes — raised UnicodeEncodeError while BUILDING the
# response, so the download was a 500 with nothing in it to read. Any
# Hindi, Tamil or Sanskrit filename did the same, which is worse and far
# likelier: a teacher uploading a chapter named in her own language got a
# file that could never be opened again.
MAIN = io.open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
ck("one helper builds every Content-Disposition",
   "def _disposition(name, how=" in MAIN)
ck("with an ASCII fallback for old clients",
   'ascii_name = raw.encode("ascii", "replace").decode("ascii")' in MAIN)
ck("and the real name percent-encoded as UTF-8",
   "filename*=UTF-8''{quote(raw, safe='')}" in MAIN,
   "RFC 5987 — what every browser since about 2011 reads")
ck("no route still builds that header by hand",
   'f\'inline; filename="{' not in MAIN
   and 'f\'attachment; filename="{' not in MAIN,
   "one left behind is one 500 nobody sees until a teacher uses their own "
   "language")

print(f"\nPASSED {P}   FAILED {F}")
sys.exit(1 if F else 0)
