"""A question paper, worked through question by question.

A teacher holds last year's paper and wants a worked solution for every
question on it — to set as practice, to check their own key against, to hand
a class after the test. A student holds the same paper and wants to know
whether what they did was right. Both were doing it one question at a time
through the scanner, which for a sixty-question paper is sixty photographs.

**Reading and solving are two passes, and this is the test that keeps them
apart.** A model asked to read and answer at once paraphrases question 14
into something easier and then answers the thing it wrote. So the reading
prompt is told, in as many words, not to answer anything; and the solved
question that reaches the screen is the one the READING pass copied, not the
one the solving pass echoed back. The echo is exactly where a question
quietly becomes an easier question.

That split is also what makes the whole thing checkable by the person using
it: the questions appear on screen as printed, so a teacher sees the paper
was read correctly before trusting a single answer.

**They are two routes as well, and that part is about time.** Twenty page
reads and six solving calls is minutes — past any request deadline, and a
browser that gives up at the end has thrown away all of it. So the paper is
read in one request and the solutions come a batch at a time, drawn as they
land. A batch that fails costs one batch, and its question numbers are named
rather than silently missing.

**Arithmetic is checked, not trusted.** Where an answer claims a root,
maths.py substitutes it back into the equation the working itself states.
Free, deterministic, and the one place a confident wrong number does the
most damage — a worked solution a class copies into their books.

**And it does not claim to be a marking scheme.** A board's key allocates
marks step by step and this does not know that allocation. That sentence is
produced by the server, so it cannot be dropped by whoever renders it, and
it goes onto the downloaded PDF as well as the screen.
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import solver                                      # noqa: E402

IDX = io.open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
MAIN = io.open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
P, F = [], []


def ck(name, cond, why=""):
    print(("PASS " if cond else "FAIL ") + name + (" — " + why if why else ""),
          flush=True)
    (P if cond else F).append(name)


PAGE = """--- PAGE 1 ---
SECTION A
Answer all questions.

Q1. Solve for x: x^2 - 5x + 6 = 0
[marks: 3]
Q2. A car travels 120 km in 2 hours. Find its average speed.
[marks: 2]
Q3. Which of the following is a noble gas?
(A) Oxygen
(B) Nitrogen
(C) Argon
(D) Chlorine
[marks: 1]
Q4. State Newton's second law of motion and write its equation.
[figure: a block on an inclined plane]
[marks: 4]
"""

print("\nthe paper is read as a paper")
qs = solver.questions(PAGE)
ck("every question is found", len(qs) == 4, str([q["n"] for q in qs]))
ck("the numbering is the paper's own",
   [q["n"] for q in qs] == ["1", "2", "3", "4"])
ck("marks are attached to the question above them",
   [q["marks"] for q in qs] == [3, 2, 1, 4])
ck("multiple-choice options stay with their question",
   "(C) Argon" in qs[2]["text"])
ck("a figure note is kept rather than dropped",
   "[figure:" in qs[3]["text"],
   "a question that depends on a diagram must say so, not be answered as "
   "though the diagram were not there")
ck("the section heading is not mistaken for a question",
   not any("SECTION A" == q["text"] for q in qs))
ck("the page marker is skipped", not any("PAGE" in q["n"] for q in qs))
ck("prose with no numbered questions returns nothing",
   solver.questions("Photosynthesis is the process by which plants make "
                    "food. It happens in the chloroplast.") == [],
   "this solves a paper; a chapter goes to the lesson maker")

print("\nreading is told not to answer")
for phrase in ("Do not answer them", "EXACTLY as printed",
               "Write nothing else"):
    ck("the read prompt says: " + phrase.lower(), phrase in solver.READ)
ck("and not to make a question easier",
   "a question you make easier is a question the paper does not contain"
   in " ".join(solver.READ.split()))
ck("the read prompt is never given a JSON shape to fill",
   "{" not in solver.READ,
   "a model handed a schema invents entries to fill it, and an invented "
   "question on a paper a class is about to sit is the one failure that "
   "cannot be allowed")

print("\nsolving answers what was actually asked")
ck("it is told to answer the question written",
   "Answer the question that is written, not a similar one" in solver.SOLVE)
ck("working is required, not optional",
   "A final answer with no steps is not a solution" in solver.SOLVE)
ck("units are carried through", "Carry units through" in solver.SOLVE)
ck("a gap is preferred to a guess",
   "wrong answer stated confidently is worse than a gap" in solver.SOLVE)
ck("an ungiven figure is not invented",
   "Do not invent the figure" in solver.SOLVE)
ck("maths is written so it reads on paper",
   "No LaTeX commands" in solver.SOLVE,
   "the download is a PDF in a Latin-1 font; typeset commands arrive as "
   "commands")

print("\nwhat comes back is matched to what went out")
reply = {"questions": [
    {"n": "2", "answer": "60 km/h", "working": ["speed = distance / time",
                                                "= 120 / 2 = 60 km/h"]},
    {"n": "1", "question": "Solve x squared minus five x plus six",
     "answer": "x = 2 or x = 3",
     "working": ["x^2 - 5x + 6 = 0", "(x - 2)(x - 3) = 0"]},
    {"n": "3", "choice": "C", "answer": "Argon", "working": ["Group 18."]},
]}
got = solver.clean(reply, qs)
ck("out-of-order replies are matched by number, not by position",
   [g["n"] for g in got] == ["2", "1", "3"] and got[1]["n"] == "1",
   "a dropped question shifts everything after it, and a solution filed "
   "under the wrong number is worse than a missing one")
ck("the question shown is the one the paper had, not the echo",
   got[1]["question"] == qs[0]["text"],
   "the echo is where a question quietly becomes an easier question")
ck("marks come from the paper too", got[1]["marks"] == 3)
ck("the multiple-choice letter is kept", got[2]["choice"] == "C")
ck("an answer with no working is still an answer",
   len(solver.clean({"questions": [{"n": "9", "answer": "42"}]},
                    [{"n": "9", "text": "?", "marks": None}])) == 1)
ck("an entry with no answer is dropped",
   solver.clean({"questions": [{"n": "1", "working": ["..."]}]}, qs) == [])
ck("junk is dropped rather than rendered",
   solver.clean({"questions": ["not a dict", None, 7]}, qs) == [])
ck("what did not come back is named",
   solver.missing(qs, got) == ["4"],
   "a paper handed out with two silent holes in it is worse than one that "
   "says which two")

print("\narithmetic is checked, not trusted")
bad = [{"n": "1", "question": "x^2 - 5x + 6 = 0", "answer": "x = 5",
        "working": ["x^2 - 5*x + 6 = 0", "so x = 5"]}]
solver.verify(bad)
ck("a root that does not satisfy its own equation is flagged",
   bad[0].get("doubt"),
   "the one place a confident wrong number does the most damage is a "
   "worked solution a class copies into their books")
ok = [{"n": "1", "question": "x^2 - 5x + 6 = 0", "answer": "x = 2",
       "working": ["x^2 - 5*x + 6 = 0", "so x = 2"]}]
solver.verify(ok)
ck("a root that does satisfy it is left alone",
   "doubt" not in ok[0],
   "passing means one thing was consistent, not that the solution is "
   "right — nothing is stamped correct")
ck("an answer with no equation in it is not judged",
   "doubt" not in solver.verify([{"n": "1", "question": "Name a noble gas",
                                  "answer": "Argon", "working": []}])[0])
ck("and the screen shows the flag",
   "Check this one:" in IDX)

print("\nbatched, because a paper at a time is minutes")
ck("ten at a time", solver.BATCH == 10,
   "twenty and the later answers become 'similarly to Q13'; one at a time "
   "is sixty calls for a sixty-question paper")
ck("batching splits evenly",
   [len(b) for b in solver.batches(list(range(25)))] == [10, 10, 5])
ck("a paper is capped", solver.MAX_QUESTIONS == 60 and solver.MAX_PAGES == 20)
ck("the client walks the batches and draws each as it lands",
   "for(let i = 0; i < asked.length; i += 10)" in IDX
   and IDX.count("examSolveShow(SOLVED)") >= 2)
ck("one failed batch does not lose the paper",
   "SOLVED.missing.push(...part.map(q => q.n));" in IDX,
   "a teacher would rather have fifty of sixty and know which ten")

print("\nthe cheap path is tried first")
ck("a typed PDF is read as text, not photographed",
   "_teachpdf.extract(raw_files[0][0])" in MAIN
   and "looks_scanned" in MAIN,
   "rasterising twenty pages to recover text the file already contains is "
   "a bill for work that was already done")
ck("only a scan goes to the vision model",
   'raise HTTPException(\n                    422, "SCANNED:' in MAIN)
ck("and the browser renders it, because it has the renderer",
   "if(!/SCANNED/.test(e.message || \"\")) throw e;" in IDX)
ck("reading is cached on the bytes",
   'f"readpaper|{h.hexdigest()[:32]}"' in MAIN,
   "a class of thirty uploading the same paper is one reading")
ck("each batch is cached on its own questions",
   'f"solvebatch|{h.hexdigest()[:32]}"' in MAIN,
   "re-running a paper after one bad batch pays for that batch only")

print("\nit says what it is not")
ck("the caveat is written by the server",
   "not a marking scheme" in MAIN,
   "so it cannot be dropped by whoever renders it")
ck("it reaches the screen", "d.caveat" in IDX)
ck("and it is printed on the downloaded PDF",
   'line(d.caveat || "", 9, "italic", 0);' in IDX,
   "the PDF is what leaves the building")

print("\nreachable, paid for, and downloadable")
ck("the read route exists", '@app.post("/api/exams/read")' in MAIN)
ck("the solve route exists", '@app.post("/api/exams/solve")' in MAIN)
ck("one whole paper is free", '"solve_paper": 1' in MAIN,
   "a teacher has to run one real paper through it before believing any "
   "of it, and a description of what it does is not that")
ck("the trial is spent on success, not on upload",
   '_trial_consume(db, user, "solve_paper")' in MAIN)
ck("a batch is capped server-side",
   "(body.questions or [])[:_solver.BATCH]" in MAIN)
ck("it has its own section on the page", 'tab("solve","Solve a paper")' in IDX)
ck("the solved paper downloads as a PDF",
   'doc.save("solved-paper.pdf")' in IDX)
ck("and the PDF text is made Latin-1 safe",
   "pdfSafe(text)" in IDX,
   "jsPDF's built-in fonts drop maths symbols and mangle the line")

if F:
    print("\n".join("FAIL " + x for x in F))
print("\nPASSED " + str(len(P)) + "   FAILED " + str(len(F)))
sys.exit(1 if F else 0)
