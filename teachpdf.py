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

**Its pictures are not worth keeping.** Images inside a PDF are compressed,
often scanned, frequently a photograph of a whiteboard. They look worse
projected than they did on paper. The lesson gets a real diagram from the
board's own renderers instead, chosen from what the text turns out to be
about.

Nothing here calls a model. It extracts text and hands it on.
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

    return "\n".join(kept)[:MAX_CHARS].strip()


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
- Where a diagram would help, ask for one. The document's own pictures are not
  used: they are compressed, often scanned, and look worse projected than on
  paper.

Reply with ONLY valid JSON in this shape:
{"title":"<what this document is about, 2-8 words>",
 "steps":[{"t":"<several short lines, one idea each, separated by newlines>",
           "where":"","code":"","lang":""}],
 "takeaway":"<the one sentence a student should leave with>"}"""
