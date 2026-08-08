"""A teacher's own PDF, turned into something a board can teach from.

A teacher has the material already — a chapter, a worksheet, a set of notes —
and what they lack is a way to put it on the board in a shape a class can
follow. Reading a PDF aloud from a screen is not teaching, and a PDF projected
at the front of a room is a wall of text nobody at the back can read.

Three decisions worth stating.

**Simple, not exact.** This is not the resume path, which reproduces a
document line for line because an employer will compare it against the
original. Here the document is the source and the lesson is the output: the
board should say what the chapter means in its own short lines, not reprint
it. A faithful reproduction of a dense page is the same unreadable page.

**The document is the only source.** Everything else on this site reaches for
Wolfram, PubChem, NASA or the model's own knowledge. A teacher who uploads
their syllabus chapter is telling us what to teach, and pulling in outside
material would quietly teach something the exam does not cover. So the lesson
is built from the extracted text and nothing else.

**Its pictures ARE kept.** This said the opposite for a long time, on the
grounds that images in a PDF are compressed, often scanned and worse
projected than on paper. True of some of them, and the wrong rule: it threw
away the case that matters most, a chapter whose whole point is the diagram.
A lesson about a ray diagram, a circuit or a labelled cell is not that lesson
with the picture removed — it is a paragraph about a picture nobody can see.
They are filtered instead, in `pictures()`, and the board still adds a drawn
diagram of its own where the text asks for one.

Nothing here calls a model. It extracts text and pictures and hands them on.
"""
import io
import re

MAX_MB = 25
MAX_PAGES = 40
MAX_CHARS = 24000

# Things that appear on every page and say nothing about the subject.
_FURNITURE = re.compile(
    r"^\s*(?:page\s*\d+(?:\s*of\s*\d+)?|\d+\s*\|.*|"
    r"(?:copyright|©).{0,60}|all rights reserved.*|"
    r"confidential.*|draft.*|printed on.*)\s*$", re.I)


def extract(raw):
    """The readable text of a PDF, or an empty string.

    Never raises. A PDF that will not open is a PDF the teacher should be
    told about, not a stack trace.
    """
    try:
        import pdfplumber
    except Exception:
        print("teachpdf: pdfplumber is not installed")
        return ""
    try:
        doc = pdfplumber.open(io.BytesIO(raw))
    except Exception as e:
        print(f"teachpdf: will not open ({type(e).__name__})")
        return ""

    lines = []
    total_pages = len(doc.pages)
    read_pages = 0
    try:
        for page in doc.pages[:MAX_PAGES]:
            try:
                text = page.extract_text() or ""
            except Exception:
                continue
            for ln in text.splitlines():
                ln = " ".join(ln.split())
                if not ln or _FURNITURE.match(ln):
                    continue
                lines.append(ln)
            # A table is not prose and extract_text does not treat it as one.
            #
            # It returns the cells in reading order with nothing to say which
            # row or column they came from, so "Year 2019 2020 Revenue 4.2
            # 5.1" is what the model sees — and an Accountancy or Economics
            # chapter is largely tables. Laid out with separators, the same
            # table is readable, and the rule about keeping numbers exactly
            # has something to be exact ABOUT.
            try:
                for tbl in (page.extract_tables() or [])[:4]:
                    rows = []
                    for row in tbl:
                        cells = [(c or "").strip().replace("\n", " ")
                                 for c in row]
                        filled = [c for c in cells if c]
                        # Two filled cells at minimum, and something actually
                        # in them. A ruled box round a paragraph and the
                        # numbering beside a worked example both come back as
                        # "tables", and " | 3" teaches nobody anything.
                        if len(filled) >= 2 and len(" ".join(filled)) >= 8:
                            rows.append(" | ".join(cells))
                    if len(rows) >= 2:
                        lines.append("TABLE:")
                        lines.extend(rows[:30])
            except Exception:
                pass
            read_pages += 1
            if sum(len(x) for x in lines) > MAX_CHARS:
                break
    finally:
        try:
            doc.close()
        except Exception:
            pass

    # A running header repeats on every page and is not content. Anything
    # appearing more than three times and short enough to be a header goes.
    seen = {}
    for ln in lines:
        if len(ln) <= 90:
            seen[ln] = seen.get(ln, 0) + 1
    repeated = {ln for ln, n in seen.items() if n > 3}
    kept = [ln for ln in lines if ln not in repeated]

    out = "\n".join(kept)[:MAX_CHARS].strip()
    # How much of the document this actually is.
    #
    # A long chapter is cut at MAX_PAGES or MAX_CHARS and the cut was
    # SILENT: the teacher got a confident lesson covering the first part of
    # their chapter with nothing to say the rest had been dropped. They find
    # out when the class reaches a topic the board never mentioned. The
    # caller reports this, so a partial reading is a sentence on the screen
    # rather than a discovery.
    extract.last = {
        "pages_read": read_pages,
        "pages_total": total_pages,
        "complete": read_pages >= total_pages and len("\n".join(kept)) <= MAX_CHARS,
    }
    return out


extract.last = {"pages_read": 0, "pages_total": 0, "complete": True}


def looks_scanned(text, pages_hint=1):
    """Did this PDF have almost no text in it?

    A scan is a picture of a page. pdfplumber returns nothing useful and the
    honest answer is to say so rather than build a lesson out of the little
    that came back.
    """
    return len(text) < max(120, 40 * max(pages_hint, 1))


def title_of(text):
    """A name for the lesson, taken from the document's own first real line."""
    for ln in (text or "").splitlines():
        ln = ln.strip()
        # A heading, not a sentence: short, and not ending mid-thought.
        if 4 <= len(ln) <= 90 and not ln.endswith((",", ";", "and", "or")):
            return ln[:90]
    return "This document"


PROMPT = """Teach what this document says, for a class.

THE DOCUMENT IS THE ONLY SOURCE. A teacher uploaded this because it is what
their class is being examined on. Do not add material it does not contain, do
not correct it, and do not reach for anything you know that is not in it. If
it is wrong, it is still what is being taught, and adding what it left out
teaches something the exam does not cover.

Do not reproduce it. It is already a document; reprinting it on a board helps
nobody. Say what it MEANS, in the board's own short lines.

- One idea per line, with a newline between each. Not paragraphs.
- Simple language. This is being read from the back of a room.
- Where the document gives a definition, a formula, a date or a number, keep
  it exactly. Everything else is yours to put plainly.
- If a step in the document does not follow, teach it as the document has it
  and say plainly that it is stated without being shown.
- Where a diagram would help, ask for one. The document's own pictures are
  shown alongside the lesson, so a drawn diagram is for what the document
  explains WITHOUT a picture — not a second copy of one it already has.
- A block marked TABLE: is a real table, one row per line, columns separated
  by |. Teach what it SHOWS — the trend, the comparison, the odd one out —
  and quote the figures you use exactly. Do not reprint the whole table; a
  class can read a table, and what they need is what it means.
- Teach the whole document, not its first page. Give every substantial
  section of it at least one line, in the order the document has them, so a
  teacher can follow their chapter down the board.

HOW LONG. A chapter is not a question, and this is the longest thing this
board is asked to teach. Give it TEN TO EIGHTEEN steps — one per section or
idea the document actually has, not padding. A six-step summary of a
forty-page chapter is a contents page, and the teacher who uploaded it still
has to teach the chapter afterwards; length here is the whole point of
uploading the file rather than asking a question.

SHAPE OF A STEP. Open it with a short heading line — a few words, no full
stop — then the lines that explain it underneath, one idea each. The board
sets that first line as a heading and the rest as the body, so a step
written this way reads as a section of a lesson rather than a paragraph of
text. Do not number the headings; the order is already the order.

Reply with ONLY valid JSON in this shape:
{"title":"<what this document is about, 2-8 words>",
 "steps":[{"t":"<several short lines, one idea each, separated by newlines>",
           "where":"","code":"","lang":""}],
 "takeaway":"<the one sentence a student should leave with>"}"""


# --------------------------------------------------------------------------
# The document's own pictures.
#
# This file used to say they were not worth keeping — compressed, often
# scanned, frequently a photograph of a whiteboard, and worse projected than
# they were on paper. That is true of SOME of them and it was the wrong rule,
# because it threw away the case that matters most: a chapter whose whole
# point is the diagram. A lesson about a ray diagram, a circuit, a labelled
# cell or a graph is not that lesson with the picture taken out — it is a
# paragraph about a picture nobody can see.
#
# So they are kept, and the filtering does the work the blanket rule was
# doing badly. What comes out is the ORIGINAL image, embedded in the PDF, not
# a re-render of the page: it is what the author put there, at the resolution
# they put it at.

PIC_MAX = 8              # per document
PIC_MIN_PX = 120         # smaller than this is a bullet, a rule or a logo
PIC_MAX_EDGE = 1400      # downscaled to this, which is more than a board shows
PIC_MAX_BYTES = 320_000  # per picture, after downscaling
PIC_TOTAL_BYTES = 1_600_000


def _worth_showing(im):
    """Is this a picture, or is it furniture?

    Three things get thrown out, and each of them appears on nearly every
    real document: anything too small to be a diagram, anything so thin it is
    a rule or a border, and anything almost entirely one colour, which is how
    a background panel or a watermark arrives.
    """
    w, h = im.size
    if w < PIC_MIN_PX or h < PIC_MIN_PX:
        return False
    if w > 12 * h or h > 12 * w:
        return False
    try:
        small = im.convert("RGB").resize((32, 32))
        colours = small.getcolors(32 * 32) or []
        if colours:
            top = max(c[0] for c in colours)
            if top / float(32 * 32) > 0.97:
                return False
    except Exception:
        pass
    return True


def pictures(raw):
    """The pictures inside a PDF, in page order, as data URLs.

    Never raises. A document whose images cannot be read is a document with
    no pictures, not a failed upload — the words are the part that must
    always arrive.
    """
    try:
        import base64
        import hashlib
        from pypdf import PdfReader
        from PIL import Image
    except Exception as e:
        print(f"teachpdf: no image support ({type(e).__name__})")
        return []

    try:
        reader = PdfReader(io.BytesIO(raw))
    except Exception as e:
        print(f"teachpdf: will not open for images ({type(e).__name__})")
        return []

    out, total, seen = [], 0, set()
    for pno, page in enumerate(reader.pages[:MAX_PAGES], 1):
        try:
            imgs = _drawn_on(page)
        except Exception:
            try:
                imgs = list(page.images)
            except Exception:
                continue
        for item in imgs:
            if len(out) >= PIC_MAX or total >= PIC_TOTAL_BYTES:
                return out
            # The same picture, once.
            #
            # Two pages of a chapter very often share one /Resources
            # dictionary, and pypdf enumerates what a page CAN draw rather
            # than what it does — so a two-page chapter with one diagram
            # hands back that diagram twice, and a ten-page one hands it back
            # ten times. Hashing the bytes is exact and costs nothing, and it
            # also catches the honest case: a figure genuinely repeated on
            # several pages is still one figure.
            digest = hashlib.sha1(item.data).hexdigest()
            if digest in seen:
                continue
            seen.add(digest)
            try:
                im = Image.open(io.BytesIO(item.data))
                im.load()
            except Exception:
                continue
            if not _worth_showing(im):
                continue
            try:
                if im.mode not in ("RGB", "L"):
                    im = im.convert("RGB")
                if max(im.size) > PIC_MAX_EDGE:
                    im.thumbnail((PIC_MAX_EDGE, PIC_MAX_EDGE))
                buf = io.BytesIO()
                # PNG for line art, which is what a diagram is; JPEG only when
                # PNG comes out too big, which means it is a photograph.
                im.save(buf, "PNG", optimize=True)
                data, kind = buf.getvalue(), "png"
                if len(data) > PIC_MAX_BYTES:
                    buf = io.BytesIO()
                    im.convert("RGB").save(buf, "JPEG", quality=82,
                                           optimize=True)
                    data, kind = buf.getvalue(), "jpeg"
                if len(data) > PIC_MAX_BYTES:
                    continue
            except Exception:
                continue
            total += len(data)
            out.append({
                "src": f"data:image/{kind};base64,"
                       + base64.b64encode(data).decode(),
                "page": pno,
                "w": im.size[0], "h": im.size[1],
            })
    return out


# Which pictures a page actually DRAWS.
#
# `page.images` walks the page's /Resources, and a resource dictionary is
# very often shared between every page of a chapter — so a two-page document
# with one diagram reports that diagram on both pages, and a forty-page
# textbook reports every figure on all forty. Hashing caught the duplicates,
# but the page number attached to the survivor was then whichever page
# happened to be enumerated first, which is not where the picture is.
#
# The page number is not decoration: it is what decides where in the lesson a
# picture appears. Getting it from the wrong place put every figure of a
# chapter on the same step.
#
# A page's content stream says what it draws: `/Im1 Do`. Reading those names,
# in the order they occur, gives both the right page and the right order
# within it. If the stream cannot be read — it is compressed with something
# unusual, or the page has none — the caller falls back to /Resources, which
# is what this did before and is wrong less often than showing nothing.
_XOBJ_DO = re.compile(rb"/([A-Za-z0-9_.#-]+)\s+Do\b")


def _drawn_on(page):
    """The page's image XObjects, in the order the page paints them."""
    res = page.get("/Resources")
    res = res.get_object() if hasattr(res, "get_object") else res
    xo = (res or {}).get("/XObject")
    xo = xo.get_object() if hasattr(xo, "get_object") else xo
    if not xo:
        return []

    data = page.get_contents()
    raw = data.get_data() if data is not None else b""
    if not raw:
        raise ValueError("no content stream")

    seen_names, order = set(), []
    for m in _XOBJ_DO.finditer(raw):
        name = "/" + m.group(1).decode("latin-1")
        if name in seen_names:
            continue
        seen_names.add(name)
        order.append(name)

    out = []
    for name in order:
        try:
            obj = xo[name].get_object()
            if obj.get("/Subtype") != "/Image":
                continue
            out.append(_ImageOnPage(obj))
        except Exception:
            continue
    return out


class _ImageOnPage:
    """Just enough of pypdf's ImageFile to stand in for it here.

    `.data` is the decoded image bytes. pypdf's own decoder handles the
    filters and the colour spaces, which is a great deal of work not worth
    repeating for the sake of a page number.
    """

    __slots__ = ("_obj", "_data")

    def __init__(self, obj):
        self._obj = obj
        self._data = None

    @property
    def data(self):
        if self._data is None:
            img = self._obj.decode_as_image()
            # PNG cannot hold CMYK, and a book is a PRINT document — NCERT's
            # PDFs are full of CMYK images. `img.save(buf, "PNG")` raised
            # OSError on the first one, the exception left pictures()
            # entirely, and the caller recorded "no pictures in this
            # document". One print-origin diagram cost every picture in the
            # chapter, on the feature whose whole point is the diagram.
            #
            # Paletted and 16-bit greyscale go the same way for the same
            # reason: convert to something PNG can actually write.
            if img.mode not in ("RGB", "RGBA", "L", "P", "1"):
                img = img.convert("RGBA" if "A" in img.mode else "RGB")
            buf = io.BytesIO()
            try:
                img.save(buf, "PNG")
            except OSError:
                # Whatever it was, RGB can hold it.
                buf = io.BytesIO()
                img.convert("RGB").save(buf, "PNG")
            self._data = buf.getvalue()
        return self._data
