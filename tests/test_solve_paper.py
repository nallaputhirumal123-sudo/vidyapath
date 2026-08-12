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
import json as _json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import solver                                      # noqa: E402

IDX = io.open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
MAIN = io.open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
SRC = io.open(os.path.join(ROOT, "solver.py"), encoding="utf-8").read()
# Just the solve route, so a phrase that appears elsewhere in main.py
# cannot pass for one that appears in it.
SOLVE_SRC = MAIN.split('@app.post("/api/exams/solve")')[1].split("\n@app.")[0]
READ_SRC = MAIN.split('@app.post("/api/exams/read")')[1].split("\n@app.")[0]
P, F = [], []
# Prompt text is wrapped for reading; compare it the way a model receives it.
READ1 = " ".join(solver.READ.split())
SOLVE1 = " ".join(solver.SOLVE.split())


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
    ck("the read prompt says: " + phrase.lower(), phrase in READ1)
ck("and not to make a question easier",
   "a question you make easier is a question the paper does not contain"
   in READ1)
ck("the read prompt is never given a JSON shape to fill",
   "{" not in solver.READ,
   "a model handed a schema invents entries to fill it, and an invented "
   "question on a paper a class is about to sit is the one failure that "
   "cannot be allowed")

print("\nsolving answers what was actually asked")
ck("it is told to answer the question written",
   "Answer the question that is written, not a similar one" in SOLVE1)
ck("working is required where there is working",
   "there is working to show. Show it" in SOLVE1)
ck("units are carried through", "carry units through" in SOLVE1)
ck("a gap is preferred to a guess",
   "wrong answer stated confidently is worse than a gap" in SOLVE1)
ck("every step says why, not only what",
   "Every step says WHY, not only what" in SOLVE1,
   "'divide both sides by 2' is a keystroke; the reason is the thing a "
   "student can use on the next question")
ck("a multiple choice is worked, not reverse-engineered",
   "Never reason backwards from an option" in SOLVE1,
   "'(D) is 481, which matches' is how a wrong option gets justified")
ck("an ungiven figure is not invented",
   "Do not invent the figure" in SOLVE1)
ck("maths is written so it reads on paper",
   "No LaTeX commands" in SOLVE1,
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
ck("and so does the number, whatever the model calls it",
   [g["n"] for g in solver.clean(
       {"questions": [{"n": "Q2", "answer": "60 km/h"}]}, qs)] == ["2"],
   "a model asked about question 2 answers 'Q2' often enough that a real "
   "solved paper came back headed QQ2 — and 'Q2' matches nothing the "
   "reading pass found, so the solution vanishes")
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

print("\na real CBSE paper, which broke all of this")
# A bilingual Applied Mathematics paper, run through the live product. Four
# separate faults, and the first is the one that matters: CBSE typesets its
# Hindi in a legacy non-Unicode font, so pdfplumber returns the glyph bytes
# as Latin letters — "1 km H$s Xm¡S> _|, {IbmS>r P". The file HAS text, so
# the cheap path was taken, and a model handed mojibake does not refuse it.
# It invented a question and answered the one it invented, and the solved
# paper came back with a confident final answer to something that is not on
# the paper.
import teachpdf                                    # noqa: E402
MOJI = ("1 km H$s Xm¡S> _|, {IbmS>r P, {IbmS>r Q H$mo 18 _rQ>a `m 9 goH§$S> "
        "go ham XoVm h¡ & Xm¡S nyar H$aZo Ho$ {bE P H$m g_` `m h¡ ? "
        "àíZ -nÌ _| 38 àíZ h¢ & g^r àíZ A{Zdm`© h¢ & `h àíZ -nÌ nm±M "
        "IÊS>m| _| {d^m{OV h¡ – H$, I, J, K Ed§ L> & IÊS> H$ _| àíZ "
        "g§»`m 1 go 18 VH$ ~hþ{dH$ënr` VWm àíZ g§»`m 19 Ed & H¡$ëHw$boQ>a "
        "H$m Cn`moJ d{O©V h¡ & Bg IÊS> _| ~hþ{dH$ënr` àíZ h¢ Am¡a CÎma &")
ENGLISH_MATHS = (
    "In Section A, Questions no. 1 to 18 are multiple choice questions. "
    "Find the value of x if 2x + 3 = 11 and show your working clearly. "
    "Show that (a+b)^2 = a^2 + 2ab + b^2 for all real a and b. "
    "The set {1, 2, 3} has 8 subsets in total. If x < y and y < z then "
    "x < z. A car travels 120 km in 2 hours; find its average speed. "
    "Evaluate the integral of x^2 dx between 0 and 3, and state Bayes "
    "theorem. The probability of an event lies between 0 and 1 always.")
ck("mojibake is recognised as not being language",
   teachpdf.garbled(MOJI),
   "the file has text, so nothing downstream could tell it was not English")
ck("and ordinary maths in English is not",
   not teachpdf.garbled(ENGLISH_MATHS),
   "a paper full of x^2, {1,2} and a<b must not be sent down the "
   "expensive path by a checker that cries wolf")
ck("real Unicode Hindi is not either",
   not teachpdf.garbled(
       "यह प्रश्न पत्र पांच खंडों में विभाजित है और सभी प्रश्न "
       "अनिवार्य हैं। एक कार 120 किलोमीटर की दूरी 2 घंटे में तय करती "
       "है। उसकी औसत चाल ज्ञात कीजिए। कैलकुलेटर का उपयोग वर्जित है। "
       "प्रत्येक प्रश्न के लिए एक अंक निर्धारित किया गया है यहाँ।"),
   "properly encoded Devanagari arrives as Devanagari and is fine")
ck("a short line is never called garbled",
   not teachpdf.garbled("H$s Xm¡S> {IbmS>r"),
   "too little to measure a proportion on is not evidence")
ck("and such a paper is sent to be read by sight instead",
   "legacy font" in MAIN and MAIN.count("SCANNED:") == 2,
   "the pages carry Devanagari that a vision model reads properly")

print("\nthe instructions are not questions")
GENERAL = """(i) This question paper contains 38 questions, all compulsory.
(ii) This question paper is divided into five Sections A, B, C, D and E.
(iii) In Section A, Questions no. 1 to 18 are multiple choice questions.
1. In a 1 km race, player P beats player Q by 18 metres. Find the time.
2. If x > y and z < 0, then which of the following is true here?
(i) This question paper contains 38 questions, all compulsory.
(ii) This question paper is divided into five Sections A, B, C, D and E.
"""
gen = solver.questions(GENERAL)
ck("a paper's General Instructions are dropped",
   [q["n"] for q in gen] == ["1", "2"],
   "they are a numbered list of sentences and parsed as nine questions — "
   "twice over on a bilingual paper")
ck("including the set printed after question 1 in the other language",
   not any(q["n"] == "i" for q in gen),
   "a positional rule kept those, which is how the live paper got them")
ck("a paper numbered in romans throughout keeps every one",
   [q["n"] for q in solver.questions(
       "i. Define osmosis clearly.\nii. Name the capital of Assam.\n"
       "iii. State Ohm's law now.")] == ["i", "ii", "iii"],
   "there is no arabic numbering for the rule to key on, so nothing is "
   "an instruction")
ck("instructions numbered 1, 2, 3 are dropped too",
   [q["n"] for q in solver.questions(
       "\n".join([
           "GENERAL INSTRUCTIONS",
           "1. This question paper contains 38 questions, all compulsory.",
           "2. The paper is divided into five sections A, B, C, D and E.",
           "SECTION A",
           "1. In a 1 km race, P beats Q by 18 metres. Find the time.",
           "2. If x > y and z < 0, which of the following is true?",
       ]))] == ["1", "2"],
   "some state boards number their instructions in arabic, which the "
   "roman rule cannot catch and which is otherwise indistinguishable "
   "from question 1")
ck("the reading pass is told they are not questions",
   "The General Instructions are not questions" in SOLVE1 + READ1
   and "NOT A QUESTION" in READ1)
ck("and told a bilingual paper is one paper",
   "A bilingual paper is one paper" in READ1,
   "otherwise it renumbers the second language as new questions")
ck("and a roman SUB-part is untouched",
   [q["n"] for q in solver.questions(
       "7 (ii) Balance the equation for burning magnesium.")] == ["7 (ii)"])

print("\na bilingual paper is one paper, not two")
BOTH = """1. एक कार 120 किलोमीटर की दूरी 2 घंटे में तय करती है।
2. `{X x > y VWm z < 0 hmo Vmo H$m¡Z-gm ghr h¡ ?
1. A car travels 120 km in 2 hours. Find its average speed.
2. If x > y and z < 0, which of the following is true?
"""
both = solver.questions(BOTH)
ck("each number appears once", [q["n"] for q in both] == ["1", "2"],
   "every question is printed in Hindi and again in English, so a "
   "38-question paper parsed as 76 and hit the cap")
ck("and the readable copy is the one kept",
   "x > y and z < 0" in both[1]["text"],
   "when one half extracts as mojibake, keeping the first would keep the "
   "broken one")
ck("when both halves read properly the paper's own order wins",
   "किलोमीटर" in both[0]["text"])

print("\nany paper, however it numbers itself")
MIXED = """1. Define osmosis.
(2 marks)
2) Name the capital of Assam. [1]
(3) Who wrote the Indian Constitution's preamble? 2 marks
Q4. Explain the water cycle.
Q.5 State Ohm's law.
12(a) Find the area of a circle of radius 7 cm.
7 (ii) Balance the equation: H2 + O2 -> H2O
"""
mix = solver.questions(MIXED)
ck("every numbering style a paper uses is read", len(mix) == 7,
   str([q["n"] for q in mix]))
ck("the number is the paper's own, not renumbered",
   [q["n"] for q in mix] == ["1", "2", "3", "4", "5", "12(a)", "7 (ii)"],
   "renumbering a paper is how a solution ends up filed against the wrong "
   "question")
ck("marks are read however the paper prints them",
   [q["marks"] for q in mix[:3]] == [2, 1, 2],
   "(2 marks), [1] and a bare '2 marks' are all the same instruction")
ck("a sub-part is its own question", mix[5]["n"] == "12(a)")

print("\na model transcribing a photo writes markdown")
# The failure you hit: a photograph of a paper, wrapped in a PDF by Google
# Photos, came back "No numbered questions were found in that" — which is
# the main case this feature exists for. A vision model reading a page
# FORMATS what it read, so it returns "**Q1.**" or "## Q1." or "* 1.", and
# the parser matched none of them.
#
# Stripped in one place rather than allowed for in each number pattern, so
# there are not four regexes each carrying a copy of what markdown is.
MD = [("**Q1.** Define osmosis and give an example.", "1"),
      ("__Q3.__ State Ohm's law in full.", "3"),
      ("## Q1. Define osmosis and give an example.", "1"),
      ("### 2. Name the capital of Assam.", "2"),
      ("* 1. Define osmosis and give an example.", "1"),
      ("- Q2) Name the capital of Assam here.", "2"),
      ("> 4. Explain the water cycle briefly.", "4"),
      ("**1.** Define osmosis and give an example.", "1")]
for _line, _want in MD:
    _m = solver._start_of(_line)
    ck("markdown: " + _line[:34],
       bool(_m) and solver._number(_m.group(1)) == _want,
       "got " + (repr(solver._number(_m.group(1))) if _m else "no match"))
ck("emphasis inside a question is left alone",
   solver._plain_line("3. Find x when **2x = 8** and explain it.")
   == "3. Find x when **2x = 8** and explain it.",
   "a long emphasised run is the model emphasising words in the question, "
   "not a heading marker")
ck("and prose is still not a question",
   solver._start_of("1947 saw the partition of India.") is None)
ck("a bracket that closes the marker is not part of the number",
   solver._number(solver._start_of("Q2) Name the capital.").group(1)) == "2",
   "it was ending up inside the number as '2)'")

print("\nand sometimes it answers in JSON, having been told not to")
# The second half of the same failure, from the same photographed paper — a
# real JEE Mains Chemistry sheet. The diagnostic printed what had been read
# and it was this: an array of strings.
#
#   [ "NOT A QUESTION", "JEE MAINS-9-APRIL-2014", "CHEMISTRY",
#     "Q31. In a face centered cubic lattice atoms A are at the corner..."
#
# Every line was a question, correctly read, wearing a pair of quotes and a
# comma. Not one matched. A perfectly good reading of a real paper parsed
# as nothing, and the teacher was told no questions were found in it.
JSONED = "\n".join([
    '[ "NOT A QUESTION",',
    '  "JEE MAINS-9-APRIL-2014",',
    '  "CHEMISTRY",',
    '  "Q31. In a face centered cubic lattice atoms A are at the corners",',
    '  "[marks: 4]",',
    '  "Q32. Which of the following is correct?",',
    '  "ANSWER KEY",',
    '  "31 C",',
    '  "32 A"',
    ']'])
_j = solver.questions(JSONED)
ck("a JSON-wrapped reading still finds its questions",
   [q["n"] for q in _j] == ["31", "32"], str([q["n"] for q in _j]))
ck("with the marks that were on the paper",
   [q["marks"] for q in _j] == [4, None])
ck("and the quotes are not part of the question",
   _j[0]["text"].startswith("In a face centered"),
   "a question that begins with a quotation mark is a question nobody asked")
ck("the answer key survives the same wrapping",
   solver.answer_key(JSONED) == {"31": "C", "32": "A"})
ck("plain text is untouched by any of it",
   [(q["n"], q["marks"]) for q in solver.questions(
       "Q1. Define osmosis.\n[marks: 2]")] == [("1", 2)],
   "the unwrapping must not cost the ordinary case")

print("\nthe options came quoted inside the question")
# A Maharashtra SSC Algebra paper, solved correctly — and the question on
# screen read:
#     "(A) 5/x - 3 = x^2",
#     "(B) x(x + 5) = 2",
#     ]
# A model that answers in JSON also quotes the lines INSIDE its own string,
# so the options arrived correctly decoded and still wearing their quotes,
# their commas, and the bracket that closed the array.
_inner = "\n".join([
    "Q1(i). Which one is the quadratic equation ?",
    '"(A) 5/x - 3 = x^2",',
    '"(B) x(x + 5) = 2",',
    '"(C) n - 1 = 2n",',
    '"(D) (1/x^2)(x + 2) = x"',
    "]"])
_ssc = "[\n" + _json.dumps(_inner) + '\n"[marks: 4]"\n]'
_q = solver.questions(_ssc)
ck("the SSC paper parses to one question", len(_q) == 1, str(len(_q)))
ck("keeping the number the paper printed", bool(_q) and _q[0]["n"] == "1(i)")
ck("and its marks", bool(_q) and _q[0]["marks"] == 4)
ck("the options carry no quotes",
   bool(_q) and '"' not in _q[0]["text"],
   "an option reading '\"(A) x(x+5)=2\",' is an option nobody printed")
ck("nor the bracket that closed the array",
   bool(_q) and not _q[0]["text"].rstrip().endswith("]"))
ck("and all four options survive",
   bool(_q) and all(o in _q[0]["text"] for o in ("(A)", "(B)", "(C)", "(D)")))

print("\na two-question paper is two questions")
# You said it plainly: there are only two questions in that paper, and it
# reported six. The four extra were the paper's own instructions.
#
# Blocks could not separate them. The rubric block ends at the first line
# that is not a numbered item, and a real JEE sheet puts
# "JEE MAINS-9-APRIL-2014" and "CHEMISTRY" between the marker and the
# instructions — so the block closed before reaching them and "1. All
# questions are compulsory" became question 1. Loosening the block rule only
# made it worse: the model then answered all four.
#
# What separates them is what they SAY. A rubric talks about the paper — its
# questions, its sections, its marks, its calculator rule. A question asks
# for something.
JEE = "\n".join([
    "NOT A QUESTION", "JEE MAINS-9-APRIL-2014", "CHEMISTRY",
    "1. All questions are compulsory.",
    "2. Use of a calculator is not allowed.",
    "3. The numbers to the right of the questions indicate full marks.",
    "4. In case of MCQs only the first attempt will be evaluated.",
    "Q31. In a face centered cubic lattice atoms A are at the corners.",
    "[marks: 4]",
    "Q32. Vander Waals equation for a gas is stated as follows."])
ck("the JEE paper is two questions, not six",
   [q["n"] for q in solver.questions(JEE)] == ["31", "32"],
   str([q["n"] for q in solver.questions(JEE)]))
SSC = "\n".join([
    "NOT A QUESTION", "MATHEMATICS ALGEBRA PART I",
    "1. All questions are compulsory.",
    "2. Use of a calculator is not allowed.",
    "3. The numbers to the right of the questions indicate full marks.",
    "Q1(i). Which one is the quadratic equation ?",
    "Q1(ii). Determine whether 2 is a root of the quadratic equation."])
ck("and the SSC paper is its two subquestions",
   [q["n"] for q in solver.questions(SSC)] == ["1(i)", "1(ii)"],
   str([q["n"] for q in solver.questions(SSC)]))
ck("a rubric line is recognised wherever it sits",
   not solver._looks_like_question("1. All questions are compulsory."))
ck("and a real question is not mistaken for one",
   solver._looks_like_question(
       "Q31. In a face centered cubic lattice atoms A are at the corners."))
ck("an ordinary paper is untouched",
   [q["n"] for q in solver.questions(
       "Q1. Solve for x: x^2 = 4\nQ2. Find the speed.")] == ["1", "2"])

# Three times this session a backslash-b has reached this file as a literal
# backspace, and a pattern beginning with one can never match anything. It
# is the same latent fault already flagged in main.py.
ck("no control character has crept into the patterns",
   not re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", SRC),
   "a regex starting with a backspace matches nothing, silently")

print("\nand papers that are not mathematics")
ck("the solver is told a paper is usually not maths",
   "A paper is not always mathematics, and most are not" in SOLVE1)
ck("a written answer is the writing, not a description of it",
   "not a description of what they should write" in SOLVE1
   and "ANSWER IS THE WRITING" in SOLVE1,
   "answering 'describe the causes of' with a hint is not an answer a "
   "student can hand in")
ck("length follows the marks",
   "Length follows the marks" in SOLVE1
   and "too short for its marks is a wrong answer" in SOLVE1)
ck("history, civics and literature are named",
   "history, civics, literature" in SOLVE1)
ck("and it answers in the language the question is in",
   "Answer in the language the question is written in" in SOLVE1)
essay = solver.clean({"questions": [{
    "n": "1", "kind": "written",
    "answer": "The Revolt of 1857 had military, political and economic "
              "causes.",
    "working": ["The greased cartridge was the immediate trigger.",
                "The Doctrine of Lapse annexed Indian states.",
                "Heavy land revenue impoverished the peasantry."]}]},
    [{"n": "1", "text": "Describe the causes of the Revolt of 1857.",
      "marks": 5}])
ck("a written answer keeps its kind", essay[0]["kind"] == "written")
ck("a long answer is not truncated to fit algebra steps",
   len(solver.clean({"questions": [{"n": "1", "kind": "written",
                                    "answer": "x",
                                    "working": ["p"] * 20}]},
                    [{"n": "1", "text": "?", "marks": 10}])[0]["working"])
   == 20,
   "a ten-mark answer is legitimately a dozen points")
ck("the kind is inferred when the model forgets to say",
   solver.clean({"questions": [{"n": "1", "answer": "Argon",
                                "choice": "C"}]},
                [{"n": "1", "text": "?", "marks": 1}])[0]["kind"] == "choice")
ck("and prose is not mistaken for a calculation",
   solver.clean({"questions": [{"n": "1", "answer": "Dispersal by wind.",
                                "working": ["Seeds are light."]}]},
                [{"n": "1", "text": "?", "marks": 2}])[0]["kind"]
   == "written")
ck("the screen lays the three out differently",
   'const written = q.kind === "written";' in IDX
   and 'written?"•":(i+1)+"."' in IDX,
   "a written answer set out as Step 1, Step 2 reads as broken")
ck("and so does the PDF", 'if(q.kind === "written"){' in IDX)

print("\nthe paper's own answer key, where it printed one")
KEYED = PAGE + """
ANSWER KEY
1 C
2. A
3 - D
"""
key = solver.answer_key(KEYED)
ck("a printed key is read", key == {"1": "C", "2": "A", "3": "D"}, str(key))
ck("several to a line works too",
   solver.answer_key("ANSWER KEY\n1 C  2 A  3 D  4 B")
   == {"1": "C", "2": "A", "3": "D", "4": "B"},
   "a key is usually printed compactly to save paper")
ck("a paper's own options are NOT mistaken for a key",
   solver.answer_key(PAGE) == {},
   "'(A) Oxygen' under question 3 looks exactly like a key line, and a key "
   "built out of the options would disagree with every answer and say so "
   "confidently")
ck("only what is below the heading counts",
   "1" not in solver.answer_key("Q1. Which is a noble gas?\n(A) Oxygen"))
ck("the key is not swallowed into the questions",
   [q["n"] for q in solver.questions(KEYED)] == ["1", "2", "3", "4"],
   "everything below an ANSWER KEY heading is the key, not question five")
ck("the reading pass is told to copy a key if there is one",
   "ANSWER KEY" in READ1 and "no answers of your own" in READ1)

agreed = [{"n": "1", "choice": "C", "answer": "Argon", "working": []},
          {"n": "2", "choice": "B", "answer": "Nitrogen", "working": []},
          {"n": "9", "choice": "A", "answer": "?", "working": []}]
solver.against_key(agreed, {"1": "C", "2": "A"})
ck("an answer that matches the key says so", agreed[0]["agrees"] is True)
ck("one that disagrees says that too, with the key's letter",
   agreed[1]["agrees"] is False and agreed[1]["key"] == "A",
   "a printed key can be wrong; showing both is what lets a teacher decide")
ck("a question the key does not cover is left alone",
   "key" not in agreed[2] and "agrees" not in agreed[2])
ck("no key, no claims",
   all("key" not in q for q in solver.against_key(
       [{"n": "1", "choice": "C", "answer": "x", "working": []}], {})))
ck("the key travels with the batch", '"key": _solver.answer_key(read)' in MAIN
   and "key: dict = {}" in MAIN and "key: SOLVED.key" in IDX)
ck("the screen shows agreement and disagreement differently",
   "Matches the paper's own answer key" in IDX
   and "printed keys are wrong too" in IDX)
ck("and the PDF prints it as well",
   "The paper's key says ${q.key}" in IDX,
   "the PDF is what leaves the building")

print("\nan answer that argues with its own working")
# From your JEE Chemistry paper. Every step was right — "the ratio is 2 : 5,
# which gives A2B5" — and the answer line printed A4B5. That is the failure
# that actually reaches a class wrong, because a student copies the answer
# and not the working.
#
# Nothing here judges chemistry. It asks the narrower question that can be
# asked without knowing any: the working ends on a formula, the answer is a
# formula, and they are not the same formula.
_clash = [{"n": "31", "answer": "A4B5",
           "working": ["Atoms A give 1 per unit cell.",
                       "The ratio of A to B is 1 : (5/2), which simplifies "
                       "to 2 : 5. Multiplying by 2 gives A2B5."]}]
solver.verify(_clash)
ck("an answer contradicting its own last step is flagged",
   bool(_clash[0].get("doubt")),
   "a student copies the answer, not the working")
ck("and the flag names both", bool(_clash[0].get("doubt"))
   and "A4B5" in _clash[0]["doubt"][0] and "A2B5" in _clash[0]["doubt"][0],
   "whichever is right, two claims that disagree need a person")

_agree = [{"n": "1", "answer": "A2B5",
           "working": ["ratio 2 : 5", "which gives A2B5"]}]
solver.verify(_agree)
ck("an answer that agrees is left alone", "doubt" not in _agree[0])
_words = [{"n": "2", "answer": "Because the tribals lost their land.",
           "working": ["The Doctrine of Lapse annexed states."]}]
solver.verify(_words)
ck("a written answer is never argued with", "doubt" not in _words[0],
   "it is compared only when BOTH sides carry a formula")
_mc = [{"n": "3", "answer": "Argon", "choice": "C",
        "working": ["Group 18 is the noble gases."]}]
solver.verify(_mc)
ck("nor a one-word answer", "doubt" not in _mc[0])

print("\nbatched, because a paper at a time is minutes")
ck("three at a time", solver.BATCH == 3,
   "one call has 55 seconds before it is abandoned, and six dense physics "
   "questions are not written in 55 seconds — a five-question paper is one "
   "batch, and one batch failing is nought out of five solved")
ck("batching splits evenly",
   [len(b) for b in solver.batches(list(range(25)))] == [3, 3, 3, 3, 3, 3, 3, 3, 1])
ck("a paper is capped", solver.MAX_QUESTIONS == 60 and solver.MAX_PAGES == 20)
ck("the client walks the batches and draws each as it lands",
   "for(let i = 0; i < asked.length; i += 3)" in IDX
   and IDX.count("examSolveShow(SOLVED)") >= 2)
ck("one failed batch does not lose the paper",
   "SOLVED.missing.push(...part.map(q => q.n));" in IDX,
   "a teacher would rather have fifty of sixty and know which ten")

print("\none free paper, and it has to actually be one whole paper")
# This was broken and shipped. The read spent the single free go, and then
# the first batch of the very paper it had just given away re-checked the
# same allowance and was refused — so one free paper meant no free paper at
# all. The free go is charged once, on the read, and the batches that solve
# it are let through on the receipt the read hands back.
ck("the allowance is one paper", '"solve_paper": 1' in MAIN)
read_src = MAIN.split('@app.post("/api/exams/read")')[1].split("\n@app.")[0]
solve_src = MAIN.split('@app.post("/api/exams/solve")')[1].split("\n@app.")[0]
ck("it is spent on the read", "require_paid_or_trial" in read_src
   and '_trial_consume(db, user, "solve_paper")' in read_src)
ck("and NOT charged a second time per batch",
   "require_paid_or_trial" not in solve_src,
   "charging both is what made one free paper mean none: reading spent the "
   "go, and the first batch of that same paper was refused for having "
   "spent it")
ck("a paper already read is handed back without paying again",
   read_src.index("if cached:") < read_src.index("require_paid_or_trial"),
   "a teacher unable to reopen the paper they spent their free go on "
   "reads as the product taking back the thing it just sold them")
ck("the read returns a receipt", '"paper": digest,' in read_src)
ck("and the browser quotes it on every batch",
   "paper: SOLVED.paper" in IDX and 'paper: str = Field(' in MAIN)

print("\nand the receipt is a bill, not a password")
ck("a batch for a paper never read is refused",
   "Upload the paper first" in solve_src)
ck("questions that are not on that paper are refused too",
   "Those questions are not on the paper that was read" in solve_src,
   "otherwise one real paper buys unlimited questions about anything, "
   "which is free-form model access on somebody else's key")
ck("the paper id cannot be anything but a digest",
   'r"[^0-9a-f]", "", (body.paper or "").lower())[:32]' in solve_src)
ck("questions are matched on their identity, not their whitespace",
   "def fingerprint(" in io.open(os.path.join(ROOT, "solver.py"),
                                 encoding="utf-8").read(),
   "a question rewrapped by a round trip through JSON is the same question")
ck("and identity is case-sensitive",
   solver.fingerprint("1", "Mg burns") != solver.fingerprint("1", "mg burns"),
   "a chemistry paper's Mg and mg are different things")
ck("but not whitespace-sensitive",
   solver.fingerprint("1", "a  b\nc") == solver.fingerprint(" 1 ", "a b c"))

print("\nan answer is paid for once, not once per batch")
# The cache was keyed on the BATCH of ten. Batching is an artefact of how
# the work is sent — ten at a time so each answer still gets written out
# properly — and keying on it made the cache useless the moment anything
# shifted: re-running a paper after one bad batch, two schools uploading the
# same paper grouped differently, or two boards printing the same problem.
# All of them paid again for an answer already held, and cost is the
# constraint this whole product is designed around.
ck("a question is keyed on itself, not on its batch",
   "def cache_key(q)" in SRC and '"solveq|"' in SRC)
ck("the same question reuses its answer wherever it is printed",
   solver.cache_key({"n": "7", "text": "Solve  x^2 = 4", "marks": 3})
   == solver.cache_key({"n": "12", "text": "Solve x^2 = 4", "marks": 3}),
   "the same problem is numbered 7 on one board's paper and 12 on "
   "another's, and whitespace differs between two readings of one page")
ck("but marks are part of its identity",
   solver.cache_key({"n": "1", "text": "Explain photosynthesis", "marks": 2})
   != solver.cache_key({"n": "1", "text": "Explain photosynthesis",
                        "marks": 5}),
   "the prompt sizes an answer by its marks; serving a two-mark answer for "
   "a five-mark question loses a student marks for being right")
ck("only what has never been asked reaches the model",
   "if missing:" in SOLVE_SRC and "as_prompt(missing)" in SOLVE_SRC)
ck("each answer is saved under its own question",
   'level="question"' in SOLVE_SRC)
ck("a cached answer wears the number of the paper asking",
   'held[q["n"]] = {**got, "n": q["n"]' in SOLVE_SRC,
   "the same question is numbered differently on two boards' papers")
ck("and the order the paper asks in is restored",
   'solved = [held.get(q["n"]) or got_fresh.get(str(q["n"]))' in SOLVE_SRC,
   "a solved paper that jumps from question 3 to 7 and back is not one")
ck("how much was reused is reported rather than asserted",
   '"reused": len(held)' in SOLVE_SRC)

print("\nand a scan is read as a document, not posted back as pictures")
# A scanned paper used to make a round trip: the server refused it, the
# browser loaded pdf.js, rendered every page to a PNG and posted them back —
# a megabyte a page over a school's connection, and pdf.js loaded on a phone
# to do it. Gemini reads the PDF itself, keeping the page order and the
# layout that rasterising throws away.
ck("a PDF is read as a document first",
   "_ai_pdf(_solver.READ" in READ_SRC,
   "the pages a browser renders lose the layout the paper was set in")
ck("only by a provider that can actually read one",
   'PDF_PROVIDERS = ("gemini",)' in MAIN,
   "the other two are handed an image they cannot decode")
ck("and only when it is small enough to send inline",
   "PDF_INLINE_MAX" in MAIN and "len(raw) > PDF_INLINE_MAX" in MAIN)
ck("the browser round trip is still the fallback",
   'SCANNED:' in READ_SRC,
   "a school with no key for this still gets its paper read")
ck("and the fallback is reached by returning nothing, not by raising",
   "falling back to pages" in MAIN,
   "an upstream refusal must not become the teacher's error message")

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
   'digest = h.hexdigest()[:32]' in MAIN
   and 'qkey = f"readpaper|{digest}"' in MAIN,
   "a class of thirty uploading the same paper is one reading")
ck("nothing is cached on the batch any more",
   "solvebatch|" not in MAIN,
   "the batch is an artefact of how the work is sent; keying on it made "
   "the cache miss every time the grouping shifted")

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
print("\nthe client is the one that gives up last")
# Not a detail, and it broke twice in one day. A server that keeps working
# past the moment its client stopped listening reports a failure on a
# request it would have finished — and the reasoning budgets added today
# are spent BEFORE a word of the answer exists, so every one of these
# windows was sized when nothing here could think.
ck("a solve batch gets two minutes from the client",
   "timeout: 130000" in IDX,
   "three questions on the strongest model with a reasoning budget is "
   "the longest thing this site asks anybody to wait for")
ck("and the server stops before that",
   "min(_cap, 18.0 + max_tokens / 110.0 + _think / 110.0)" in MAIN
   and "(100.0, 110) if _think else (60.0, 70)" in MAIN)
ck("an ordinary call keeps the shorter window",
   "opts.timeout || 75000" in IDX,
   "the long one is only for the calls that are buying reasoning; a "
   "lesson on the default 75 seconds must not meet a server willing to "
   "work for 100")
ck("the thinking is counted into the wait, not just the writing",
   "_think / 110.0" in MAIN and "int(think or 0)) / 110.0" in MAIN,
   "the scanner was given a budget and 57 seconds to use it, so every "
   "photographed problem was abandoned server-side and showed nothing")

print("\nthe paper is worked twice, and the second one is not shown the answer first")
# maths.py puts a root back into its own equation and chem.py counts atoms.
# Neither can tell you a torque came back with the wrong sign, or that a
# derivation was right in every step and the answer line contradicted it.
# So every answer is worked again from the question alone.
ck("the checker is told to solve it before reading the answer",
   "Do not read the proposed answer until you have your own"
   in " ".join(solver.CHECK.split()),
   "a model shown an answer agrees with it, because agreeing is the "
   "shortest path — that is a rubber stamp and not a check")
ck("and the proposed answer sits last on the page",
   solver.as_check([{"n": "1", "question": "Q", "answer": "A",
                     "working": ["w"]}]).index("PROPOSED ANSWER")
   > solver.as_check([{"n": "1", "question": "Q", "answer": "A",
                       "working": ["w"]}]).index("Q"))
ck("rounding and arrangement still count as agreement",
   "0.5 and 1/2 are the same answer" in " ".join(solver.CHECK.split()),
   "a checker that calls every rewriting a disagreement is noise, and "
   "noise is ignored")
ck("a wrong multiple-choice letter is a disagreement whatever the prose",
   "not the option your own working lands on"
   in " ".join(solver.CHECK.split()))

_chk = solver.apply_check(
    [{"n": "1", "answer": "m y a w^2 k"}],
    {"checks": [{"n": "Q1", "verdict": "disagree", "answer": "-m y a w^2 k",
                 "why": "j x i is -k"}]})
ck("a verdict finds its question whether or not it carries the Q",
   _chk[0].get("check", {}).get("verdict") == "disagree",
   "a verdict filed under a name nothing matches reads on screen as "
   "not checked")
ck("a disagreement becomes a doubt on the answer",
   any("checked again" in d for d in _chk[0].get("doubt", [])))
ck("and the answer is never rewritten",
   _chk[0]["answer"] == "m y a w^2 k",
   "two workings that reach different answers need the teacher holding "
   "the paper; picking one for them is the thing this must not do")
_ag = solver.apply_check([{"n": "2", "answer": "0.5"}],
                         {"checks": [{"n": "2", "verdict": "agree",
                                      "answer": "1/2"}]})
ck("agreement adds no doubt", "doubt" not in _ag[0])
ck("an unknown verdict is treated as unsure, not as agreement",
   solver.apply_check([{"n": "3", "answer": "x"}],
                      {"checks": [{"n": "3", "verdict": "looks fine"}]}
                      )[0]["check"]["verdict"] == "unsure")

ck("the check is keyed on the question AND the answer",
   solver.check_key({"question": "Q", "answer": "A"})
   != solver.check_key({"question": "Q", "answer": "B"}),
   "serving an old verdict against a new answer puts a tick beside "
   "something nobody looked at")
ck("and it is its own request, so a slow check cannot lose the answers",
   '"/api/exams/check"' in IDX and "examSolveShow(SOLVED);" in IDX)
ck("a check that fails leaves the answers standing",
   "A check that will not run is not a solved paper lost" in IDX)

print("\nPASSED " + str(len(P)) + "   FAILED " + str(len(F)))
sys.exit(1 if F else 0)
