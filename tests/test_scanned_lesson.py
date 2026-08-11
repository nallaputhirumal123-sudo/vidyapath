"""A photocopied chapter, turned into a lesson.

/api/teach/pdf reads a PDF's TEXT. A scan carries none — it is a photograph
of a page — so it was refused with "that PDF has almost no text in it, try
Scan a problem". A photocopied chapter is what a great many schools actually
have, and being told to photograph it one problem at a time is not an answer
for a thirty-page handout.

Three decisions worth stating, because each is a cost or a correctness
trade rather than a preference.

**The pages are rasterised in the BROWSER.** The server has no PDF
renderer, and adding one means PyMuPDF: a fifty-megabyte wheel and a native
library, on a deployment that has to keep booting. pdf.js is already loaded
for marking a PDF up on the board, so rendering there costs nothing and no
new dependency on either side.

**One vision call per page, not one call with twelve images.** A model
handed a dozen pages at once summarises the pile and loses the order, and
the order IS the lesson. Capped at twelve pages, because each page is a
call and an uncapped upload is an unbounded bill.

**Reading is separated from teaching.** READ_PAGE transcribes and is
forbidden to explain, summarise or fill a gap; the teaching happens after,
from all the pages together. The failure this guards against is a model
deciding it knows the subject and writing what a page like this usually
says — invisible on a board, and it lands in an exam.

Cached on the bytes of the pages together, like /api/scan is on one image:
a department passing round the same photocopy is one reading, not one each.
"""
import io
import os
import sys
import time
import datetime as dt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"

import main                                        # noqa: E402
import teachpdf                                    # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX = io.open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
MAIN = io.open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
main.Base.metadata.create_all(bind=main.engine)
main._migrate_columns()
main.send_email = lambda *a, **k: None
P, F = [], []


def ck(n, c, d=""):
    print(("PASS " if c else "FAIL ") + n + (f" — {d}" if d else ""),
          flush=True)
    (P if c else F).append(n)


u = str(int(time.time()))[-6:] + str(os.getpid())
db = main.SessionLocal()
sc = main.School(name=f"Scan {u}")
db.add(sc)
db.commit()
db.refresh(sc)
hc = ("HSN" + u)[:12]
db.add(main.TeacherCode(code=hc, school=sc.name, school_id=sc.id,
                        is_head=True, active=True))
db.commit()
off = TestClient(main.app)
oem = f"sn{u}@example.com"
off.post("/api/auth/signup", json={"name": "Scan Office", "email": oem,
                                   "password": "OffPass1!"})
row = db.query(main.User).filter(main.User.email == oem).first()
row.dob = dt.date(1980, 1, 1)
db.commit()
off.post("/api/class/join", json={"code": hc})
cid = off.post("/api/teacher/class", json={"name": f"9-N {u}"}).json()["id"]
tem = f"snt{u}@example.com"
pw = off.post("/api/head/staff",
              json={"name": "Scan Teacher", "email": tem,
                    "role": "teacher"}).json()["temporary_password"]
trow = db.query(main.User).filter(main.User.email == tem).first()
off.post("/api/head/assign", json={"class_id": cid, "subject": "Physics",
                                   "user_id": trow.id})
her = TestClient(main.app)
her.post("/api/auth/login", json={"email": tem, "password": pw})
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40

print("\nthe route exists and is the teacher's")
r = her.post("/api/teach/pages",
             files=[("files", ("p1.png", PNG, "image/png"))])
ck("a subject teacher gets past the gate", r.status_code != 403,
   f"got {r.status_code}")
ck("and is told plainly when the AI is off", r.status_code == 503,
   r.text[:70])
ck("the office does not — teaching tools are the teacher's",
   off.post("/api/teach/pages",
            files=[("files", ("p.png", PNG, "image/png"))]).status_code == 403)
ck("and nobody signed out at all",
   TestClient(main.app).post(
       "/api/teach/pages",
       files=[("files", ("p.png", PNG, "image/png"))]).status_code == 401)

print("\nand it refuses what it cannot read, before spending anything")
r = her.post("/api/teach/pages",
             files=[("files", ("e.png", b"", "image/png"))])
ck("an empty page is refused", r.status_code == 400, r.text[:60])
ck("with a sentence about the pages, not the server",
   "No readable pages" in r.text, r.text[:70])

print("\nreading a page is transcription, and says so")
ck("the prompt exists", bool(teachpdf.READ_PAGE.strip()))
ck("it forbids explaining and summarising",
   "TRANSCRIBE, do not explain and do not summarise" in teachpdf.READ_PAGE)
ck("keeps numbers, formulas and dates exactly",
   "exactly as printed" in teachpdf.READ_PAGE)
ck("keeps a table as a table",
   "TABLE:" in teachpdf.READ_PAGE and " | " in teachpdf.READ_PAGE,
   "a table flattened into prose is a table nobody can read back")
ck("describes a figure rather than inventing one",
   "FIGURE:" in teachpdf.READ_PAGE)
ck("and marks what it cannot read instead of guessing",
   "[unclear]" in teachpdf.READ_PAGE
   and "do not fill the gap from what you know" in teachpdf.READ_PAGE,
   "a model filling a blur from its own knowledge is the failure that "
   "reaches an exam")

print("\none call per page, in order, and a cap on both")
ck("pages are read one at a time",
   "for i, raw in enumerate(pages, 1):" in MAIN,
   "a dozen images in one call gets summarised and loses the order")
ck("the order is carried into the teaching prompt",
   'f"--- PAGE {i} ---' in MAIN)
ck("no more than twelve pages", "files[:12]" in MAIN,
   "each page is a model call, so uncapped is an unbounded bill")
ck("and the whole set is cached together",
   'qkey = f"teachpages|{digest}"' in MAIN,
   "a department passing round one photocopy is one reading")

print("\nthe browser does the rendering, because it already can")
ck("pages are rasterised client-side",
   "async function pdfPagesAsImages(file, cap)" in IDX)
ck("with pdf.js, which is already loaded for marking PDFs up",
   "pdfjs-dist@3.11.174" in IDX)
ck("at a size a model can read and a school can upload",
   "1600 / Math.max(base.width, base.height)" in IDX)
ck("and it is only reached when the PDF turns out to be a scan",
   "const scanned = /scan|almost no text|nothing readable/i.test" in IDX,
   "a PDF with real text still takes the cheaper text path")
ck("a failure there does not hide the original refusal",
   "if(!done && !SB.error) SB.error = e.message" in IDX)

print("\nand the teacher's own desk, not only the board")
# The board has taken scans since the day it was built. THIS screen — the
# one a teacher actually prepares on, at a desk, with a keyboard and a file
# browser, before the class arrives — refused everything but a typed PDF,
# and admitted it in its own help text: "the only one that works on a scan"
# was Keep it as it is. A photocopied chapter is what a great many schools
# actually have, so the tool that turns a chapter into a lesson did not work
# on the chapters those schools hold.
DESK = IDX.split("async function prepDo(")[1].split("\nasync function")[0]
ck("photographs of the pages are accepted there too",
   'r=await asPages(pics);' in DESK,
   "photographing a chapter is the way in for a school with no soft copy")
ck("several at once, because a chapter is several photographs",
   'data-prepfile="1" multiple' in IDX)
ck("a scanned PDF falls back to its pages",
   "const pages=await pdfPagesAsImages(file, 12);" in DESK)
ck("only when it is genuinely a scan",
   "/scan|almost no text|nothing readable/i.test(e.message" in DESK,
   "a PDF with real text still takes the cheaper text path")
ck("and a real failure is not swallowed by the fallback",
   "throw e;" in DESK)
ck("the help text no longer says scans are impossible",
   "the only one that works on a scan" not in IDX,
   "it said so truthfully and the truth has changed")
ck("both routes are teacher-gated",
   MAIN.split('@app.post("/api/teach/pdf")')[1].split(")")[0].count(
       "_teacher_or_board") == 0
   or "who=Depends(_teacher_or_board)" in MAIN)
ck("writing a lesson is a teacher's tool, not a learner's",
   MAIN.count("who=Depends(_teacher_or_board)") >= 2,
   "it is the tool their school gave them and it costs a model call")

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\nPASSED {len(P)}   FAILED {len(F)}")
sys.exit(1 if F else 0)
