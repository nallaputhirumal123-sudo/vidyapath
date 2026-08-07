"""A teacher's own chapter, turned into a lesson worth putting on a board.

Two faults, and both are the kind that produce a confident wrong answer
rather than an error.

**Tables were fed to the model as prose.** `extract_text` returns a table's
cells in reading order with nothing to say which row or column they came
from, so a balance sheet arrived as "Liabilities Amount Assets Amount Capital
5,00,000 Cash in hand 5,00,000". The prompt tells the model to keep every
figure exactly, and that instruction had nothing to be exact ABOUT — the
numbers had already lost the rows they belonged to. An Accountancy or
Economics chapter is mostly tables, which became a great deal more relevant
the day those books went into the corpus.

**A long chapter was cut in silence.** Forty pages or twenty-four thousand
characters, whichever comes first. A real NCERT Accountancy chapter is
fifty-three pages: the teacher got a confident lesson built from the first
fourteen, with nothing anywhere to say the rest had been dropped. They find
out when the class reaches a topic the board never mentioned — which is the
worst possible moment and the hardest to trace back to here.

Both are checked against a REAL NCERT PDF when the network allows, because
the fault was in what a real document does to a real extractor, and a
synthetic PDF would have passed the old code too. Skipped, not failed, when
the network is not there.
"""
import io
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import teachpdf                                    # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P, F, S = [], [], []


def ck(n, c, d=""):
    print(("PASS " if c else "FAIL ") + n + (f" — {d}" if d else ""),
          flush=True)
    (P if c else F).append(n)


def skip(n, why):
    print(f"SKIP {n} — {why}", flush=True)
    S.append(n)


print("\nthe extractor reports how much it read")
ck("there is a report at all", hasattr(teachpdf.extract, "last"))
ck("with the pages it read and the pages there were",
   {"pages_read", "pages_total", "complete"} <= set(teachpdf.extract.last),
   str(teachpdf.extract.last))

src = io.open(os.path.join(ROOT, "teachpdf.py"), encoding="utf-8").read()
ck("tables are pulled out as tables", "page.extract_tables()" in src,
   "extract_text gives the cells with no rows or columns attached")
ck("laid out with a separator the model can read", '" | ".join(cells)' in src)
ck("and marked, so it knows what it is looking at", '"TABLE:"' in src)
ck("furniture is not mistaken for a table",
   'len(filled) >= 2 and len(" ".join(filled)) >= 8' in src,
   "a ruled box round a paragraph came back as a table reading ' | 3'")

print("\nand the prompt uses both")
ck("it is told what a TABLE block is", "A block marked TABLE:" in
   teachpdf.PROMPT)
ck("to teach what it shows rather than reprint it",
   "Do not reprint the whole table" in teachpdf.PROMPT,
   "a class can read a table; what they need is what it means")
ck("and to cover the whole document",
   "not its first page" in teachpdf.PROMPT)

main_src = io.open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
ck("the route reads the report straight after extracting",
   "read = dict(_teachpdf.extract.last)" in main_src,
   "anything else calling extract() first would overwrite it")
ck("and a partial reading is said on the lesson",
   'lesson["partial"] = (' in main_src)
ck("naming both numbers", "of\\n            f\"{read['pages_total']} pages" in
   main_src or "read['pages_total']" in main_src,
   "'some of it' is not something a teacher can act on")

print("\nagainst a real NCERT chapter")
# NCERT Class 11 Accountancy chapter 3 — 53 pages, tables on most of them.
URL = "https://ncert.nic.in/textbook/pdf/keac103.pdf"
raw = None
try:
    req = urllib.request.Request(
        URL, headers={"User-Agent": "craxle-education/1.0 (+craxle.com)"})
    raw = urllib.request.urlopen(req, timeout=60).read()
except Exception as e:
    skip("a real chapter can be fetched", f"{type(e).__name__}")

if raw:
    text = teachpdf.extract(raw)
    report = dict(teachpdf.extract.last)
    ck("it extracts something teachable", len(text) > 5000, str(len(text)))
    rows = [ln for ln in text.splitlines() if "|" in ln]
    ck("the tables in it come out as rows", len(rows) >= 5, str(len(rows)))
    ck("with more than one column", any(ln.count("|") >= 2 for ln in rows),
       "a single pipe is a line, not a table")
    ck("and none of them is furniture",
       all(len(ln.replace("|", "").strip()) >= 8 for ln in rows),
       str([ln for ln in rows if len(ln.replace('|', '').strip()) < 8][:3]))
    ck("a balance sheet keeps its figures beside their labels",
       any("Liabilities" in ln and "Assets" in ln for ln in rows),
       str(rows[:2]))

    # The honesty half. This document is longer than one lesson, and the
    # whole point is that the teacher is told so.
    ck("it notices it did not read the whole thing",
       report["complete"] is False, str(report))
    ck("and knows how much it did", 0 < report["pages_read"]
       < report["pages_total"], str(report))
    print(f"       (read {report['pages_read']} of "
          f"{report['pages_total']} pages)")

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\n{len(P)} passed, {len(F)} failed, {len(S)} skipped")
sys.exit(1 if F else 0)
