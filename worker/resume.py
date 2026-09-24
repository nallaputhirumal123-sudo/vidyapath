"""The file that gets attached, built from the resume text we hold.

A plain statement of a real limitation, because it should be obvious to
whoever reads this next rather than discovered from a candidate's complaint:

**the original upload is not kept anywhere.** `/api/resume/parse` reads a
PDF or DOCX, extracts the text, stores the text and the structured fields,
and discards the bytes. So the file this worker attaches is not the
candidate's own document — it is their own words, re-typeset. Formatting,
layout and any design they chose are gone.

That is acceptable for slice 1 and it is not acceptable forever. Keeping the
uploaded file needs a storage decision (object store or a bytes column, plus
a retention rule and a deletion path) that is outside this slice's schema.
When it lands, this module becomes a fallback for accounts that only ever
typed a resume into the builder, and `resume_path` starts pointing at the
real upload.

The writer below is deliberately dependency-free. reportlab would be the
obvious answer and it is another package in an image that already has to
carry Chromium; a text-only PDF is a few hundred lines of PostScript
operators and a cross-reference table, and it has no install to go wrong on
a deploy at midnight.
"""
import os
import tempfile

# Helvetica at 10pt on A4 with a 56pt margin. Not a design — a legible
# default that an ATS parser reads cleanly, which is the only thing this
# document has to do.
PAGE_W, PAGE_H = 595, 842
MARGIN = 56
FONT_SIZE = 10
LEADING = 13.2
# Conservative for a proportional font: Helvetica averages about 0.5em, so
# 95 characters is comfortably inside the measure and nothing overruns.
WRAP_AT = 95
LINES_PER_PAGE = int((PAGE_H - MARGIN * 2) / LEADING)


def _wrap(text):
    """Text into lines that fit, keeping blank lines as spacing.

    Word wrap rather than character wrap, except for a single word longer
    than the measure — a URL, usually — which is cut rather than allowed to
    run off the edge of the page.
    """
    out = []
    flat = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    for raw in flat.split("\n"):
        line = raw.rstrip()
        if not line:
            out.append("")
            continue
        cur = ""
        for word in line.split(" "):
            while len(word) > WRAP_AT:
                if cur:
                    out.append(cur)
                    cur = ""
                out.append(word[:WRAP_AT])
                word = word[WRAP_AT:]
            if not cur:
                cur = word
            elif len(cur) + 1 + len(word) <= WRAP_AT:
                cur += " " + word
            else:
                out.append(cur)
                cur = word
        if cur:
            out.append(cur)
    return out


def _esc(s):
    """Into something a PDF string literal can hold.

    WinAnsi is a single-byte encoding, so anything outside it is transliterated
    where there is an obvious equivalent and dropped where there is not. A
    smart quote silently becoming a mojibake pair in somebody's job
    application is worse than it becoming a straight quote.
    """
    swaps = {"‘": "'", "’": "'", "“": '"', "”": '"',
             "–": "-", "—": "-", "•": "-", " ": " ",
             "…": "..."}
    for bad, good in swaps.items():
        s = s.replace(bad, good)
    s = s.encode("cp1252", "replace").decode("cp1252")
    return s.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def build_pdf(text, path):
    """Write the resume text to `path` as a PDF. Returns the path."""
    lines = _wrap(text)
    pages = [lines[i:i + LINES_PER_PAGE]
             for i in range(0, max(len(lines), 1), LINES_PER_PAGE)] or [[]]

    objects = []            # 1-indexed in the file; index 0 here is object 1

    def add(body):
        objects.append(body)
        return len(objects)

    catalog = add("")       # patched below, once the page ids are known
    pages_obj = add("")
    font = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
               "/Encoding /WinAnsiEncoding >>")

    kids = []
    for page_lines in pages:
        parts = ["BT", f"/F1 {FONT_SIZE} Tf", f"{LEADING} TL",
                 f"1 0 0 1 {MARGIN} {PAGE_H - MARGIN} Tm"]
        for line in page_lines:
            parts.append(f"({_esc(line)}) Tj T*")
        parts.append("ET")
        stream = "\n".join(parts)
        size = len(stream.encode("cp1252", "replace"))
        content = add(f"<< /Length {size} >>"
                      f"\nstream\n{stream}\nendstream")
        page = add(f"<< /Type /Page /Parent {pages_obj} 0 R "
                   f"/MediaBox [0 0 {PAGE_W} {PAGE_H}] "
                   f"/Resources << /Font << /F1 {font} 0 R >> >> "
                   f"/Contents {content} 0 R >>")
        kids.append(page)

    objects[catalog - 1] = f"<< /Type /Catalog /Pages {pages_obj} 0 R >>"
    objects[pages_obj - 1] = (
        "<< /Type /Pages /Kids [" + " ".join(f"{k} 0 R" for k in kids)
        + f"] /Count {len(kids)} >>")

    # Assembled as bytes with real offsets: an xref table whose numbers are
    # wrong produces a file that some readers open and an ATS parser rejects,
    # which is the worst of both.
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{body}\nendobj\n".encode("cp1252", "replace")
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root {catalog} 0 R >>\n"
            f"startxref\n{xref_at}\n%%EOF\n").encode()

    with open(path, "wb") as fh:
        fh.write(bytes(out))
    return path


def resume_file_for(db, user_id, main_mod, directory=None):
    """The resume file to attach for this candidate, or None.

    None is a real answer and the caller must treat it as one: a row whose
    candidate has no resume text cannot be applied for, and should fail
    saying exactly that rather than submitting a form with no attachment.
    """
    note = db.query(main_mod.Note).filter(
        main_mod.Note.user_id == user_id,
        main_mod.Note.k == "resume_uptext").first()
    text = (note.v if note and note.v else "").strip()
    if len(text) < 40:
        return None
    directory = directory or tempfile.mkdtemp(prefix="vpresume")
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"resume-{user_id}.pdf")
    return build_pdf(text, path)
