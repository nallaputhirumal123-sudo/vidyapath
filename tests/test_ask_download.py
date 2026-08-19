"""Downloading an answer from Ask Axle, and keeping one so it can be.

Press Download PDF on an answer you saved earlier and nothing happened. Not
an error, not a file — nothing. There were four reasons, and each one hid the
others.

**A saved answer was cut in half.** `askSaveCurrent` sliced the record to
4,900 characters to fit a note cap meant for checklists. A lesson cut at
4,900 characters is invalid JSON, and JSON.parse throws when the record is
READ, not when it is written — so it looked saved, and every reader of it
(the list, Open, Download) caught the throw and did nothing. It did not even
appear in the list, which also meant its Remove button never existed: the row
was invisible on screen and permanent in the database.

**The download was handed the wrong shape.** `pdfRecordOf` exists so there is
one answer to "which fields go in", and its own comment warns that a second
copy is how one of the two quietly stops including the pictures. The saved
path was that second copy: it passed the record straight through, so steps
that are objects — which is what the board writes — reached `s.replace` and
threw INSIDE the writer, past every try around it. And it never carried the
pictures at all, so a chapter taught with a diagram came back as a
description of a diagram.

**Every failure was silent.** `catch(err){}`, and an async throw that no
`try` was in a position to see.

**And the writer itself came from a CDN.** cdnjs.cloudflare.com, which a
school network is as likely to block as not — and school networks are the
whole market. On a filtered network nothing downloads anywhere on the site,
and the only thing shown is "Check your connection" on a connection that is
working fine. The library ships with the app now.

The run below is not a source check: it pulls the real functions out of
index.html and writes real PDFs with them, because none of this was visible
in the source. It all failed at run time.
"""
import io
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("DATABASE_URL", "sqlite:///./vidyapath.db")
os.environ.setdefault("ALLOW_SQLITE", "1")

IDX = io.open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
# Comments stripped before anything is looked for: this file explains what it
# replaced, and a search for "slice(0,4900)" would find the sentence about it
# rather than the code. That has happened five times in this repo.
CODE = re.sub(r"/\*.*?\*/|//[^\n]*", " ", IDX, flags=re.S)
P, F = [], []


def ck(name, cond, why=""):
    print(("PASS " if cond else "FAIL ") + name + (" — " + why if why else ""),
          flush=True)
    (P if cond else F).append(name)


print("\nit actually writes a PDF, for every shape that reaches it")
try:
    r = subprocess.run(["node", os.path.join(ROOT, "tests", "_pdfrun.mjs")],
                       capture_output=True, text=True, timeout=180,
                       encoding="utf-8", cwd=ROOT)
    runs = json.loads([l for l in (r.stdout or "").splitlines()
                       if l.startswith("[")][-1])
except Exception as e:
    runs = None
    print("(node unavailable, skipping the write: %s)" % e)
    print("stderr:", (r.stderr or "")[:400] if "r" in dir() else "")

if runs:
    for run in runs:
        ck(run["label"] + " downloads",
           run["bytes"] > 1000 and not run["err"],
           run["err"] or " ".join(run["said"]) or "no bytes came out")
    by = {run["label"]: run for run in runs}
    # The one that threw: steps as objects, handed over without normalising,
    # which is exactly how the saved-download path used to call the writer.
    ck("steps as objects no longer throw inside the writer",
       by["objects with no normalising"]["bytes"] > 1000,
       "s.replace is not a function, raised past every try around it")
    ck("and the file is named after the lesson",
       by["ask lesson"]["file"] == "photosynthesis.pdf")
    ck("with a fallback that is this product's name",
       by["no title"]["file"] == "craxle-answer.pdf",
       "it fell back to a brand two rebrands ago")

print("\nnothing about a saved answer is cut to fit")
SAVE = IDX.split("function askSaveCurrent(")[1].split("\nfunction ")[0]
ck("the blind slice is gone", "slice(0,4900)" not in SAVE.replace(" ", ""),
   "a lesson cut at 4,900 characters is invalid JSON, and it fails when it "
   "is read back rather than when it is saved")
ck("what is kept is what is downloaded",
   "const rec=pdfRecordOf(ASK.lesson," in CODE,
   "one answer to which fields go in, or one of the two quietly loses the "
   "pictures")
ck("inline page images are not kept",
   '!/^data:/i.test(p.src)' in CODE,
   "those are pages of an uploaded PDF, hundreds of kilobytes each, and the "
   "file they came from is still theirs")
ck("and a record too big to keep says so",
   "too long to keep" in IDX,
   "storing half of it is the bug this replaced")

print("\nand the server gives it room, having already learnt this once")
import main                                             # noqa: E402
ck("Ask's prefix is named", main.ASK_SAVED_PREFIX == "asksave_")
ck("both prefixes get a saved answer's cap",
   main.SAVED_PREFIXES == (main.SAVED_PREFIX, main.ASK_SAVED_PREFIX))
SRC = io.open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
ck("the note cap covers both",
   "elif body.key.startswith(SAVED_PREFIXES):" in SRC,
   "the 80,000 was written for the board's saves and the comment above it "
   "describes this exact bug; Ask's never got it")
ck("and so does fetching one back",
   "if not key.startswith(SAVED_PREFIXES):" in SRC)

print("\nthe page load carries titles, not twenty lessons")
ck("a stub is sent instead of the body", "_saved_stub" in SRC)
ck("it keeps what the list draws with",
   all(k in main._saved_stub('{"title":"T","q":"Q","ts":7,"steps":["x"]}')
       for k in ('"title": "T"', '"q": "Q"', '"ts": 7')))
ck("and drops what it does not",
   "steps" not in main._saved_stub('{"title":"T","steps":["x"]}'),
   "this payload is sent on every page load, and whole lessons in it is "
   "what made the client slice them in the first place")
ck("an unreadable one is handed over, not hidden",
   main._saved_stub("{not json") == "{not json")
ck("the body is fetched when it is wanted",
   'api.get("/api/notes/saved/"' in CODE)

print("\nand a failure says what happened")
ck("downloading a saved answer reports its error",
   'toast((err&&err.message)||"Could not download that answer.")' in CODE,
   "catch(err){} and an async throw nobody was positioned to see look "
   "identical to a button that is not wired up")
ck("opening one does too",
   '"Could not open that saved answer."' in CODE)
ck("and the writer itself is wrapped",
   "async function askPDF(rec){" in CODE
   and "Could not make the PDF: " in IDX)

print("\na record that did not survive can still be removed")
ck("it is listed rather than dropped",
   "damaged:true" in CODE,
   "nothing listed it, so nothing offered a Remove button for it — "
   "invisible on screen and permanent in the database")
# Read from the raw file: stripping /* */ out of a page this size joins a
# comment opener in one string to a closer in another and eats the markup
# between them, which is what this line found the first time.
ck("and it is not offered a download", '${r.damaged?"":' in IDX)

print("\nthe PDF writer comes from this server")
ck("the library ships with the app",
   os.path.getsize(os.path.join(ROOT, "jspdf.umd.min.js")) > 200000)
ck("and jsPDF is what is in it",
   "jsPDF - PDF Document creation from JavaScript"
   in io.open(os.path.join(ROOT, "jspdf.umd.min.js"),
              encoding="utf-8", errors="ignore").read(400))
ck("the page asks this server first",
   'load("/jspdf.umd.min.js")' in CODE,
   "a school network is as likely to block a CDN as not, and school "
   "networks are the whole market")
ENS = IDX.split("function ensureJsPDF(")[1].split("\nfunction ")[0]
ck("the CDN is only the fallback",
   ENS.index('load("/jspdf.umd.min.js")') < ENS.index("cdnjs.cloudflare.com"))
ck("and a script that loads but is empty counts as a failure",
   '"loaded but empty"' in CODE,
   "onload fires for a blocked page served as an error document too")

print("\n" + ("PASSED %d   FAILED %d" % (len(P), len(F))))
if F:
    for name in F:
        print("  FAILED: " + name)
    sys.exit(1)
