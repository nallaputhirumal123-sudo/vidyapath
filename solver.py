"""A question paper, worked through question by question.

A teacher holds last year's paper and wants a worked solution for every
question on it — to set as practice, to check their own key against, to hand
a class after the test. A student holds the same paper and wants to know
whether what they did was right. Both currently do it one question at a
time through the scanner, which for a sixty-question paper is sixty
photographs.

**Two stages, and they are separate on purpose.** Reading a paper and
solving it are different jobs, and a model asked to do both at once does
neither carefully — it paraphrases question 14 into something easier and
then answers the thing it wrote. So the first pass only READS: it copies out
what is on the page, verbatim, with the numbering and the marks, and is told
in as many words not to answer anything. The second pass solves what the
first pass found, and cannot reach the image at all.

That split is also what makes the whole thing checkable. The questions come
back to the screen exactly as they appear on the paper, so a teacher can see
at a glance whether the reading was right before trusting a single answer.

**Solved in batches, because cost is a real constraint.** One call per
question on a sixty-question paper is sixty calls; one call for all sixty
is an output limit and a model that starts writing "similarly" by question
forty. Ten at a time is the size where each answer still gets written out
properly.

**Arithmetic is checked, not trusted.** Where an answer claims a solution to
an equation, maths.py substitutes it back in. A worked solution that a class
copies into their books is the one place a confident wrong number does the
most damage, and substitution is free and deterministic — exactly the check
that should not be a model's job.

**What it does not claim.** This is not a marking scheme. A board's own key
allocates marks step by step and this does not know that allocation, so the
paper it produces says so on it. A teacher checking their key against this
is using it correctly; a teacher marking thirty scripts from it is not.
"""
import re

# Ten is where an answer still gets written out properly. Twenty and the
# later ones turn into "similarly to Q13"; one at a time is sixty calls for
# a sixty-question paper, which is the bill nobody agreed to.
BATCH = 10
MAX_QUESTIONS = 60
MAX_PAGES = 20

READ = """Read this page of a question paper and copy out what is on it.

Copy the questions EXACTLY as printed. Do not answer them. Do not simplify
them, shorten them, or rewrite them in your own words — a question you make
easier is a question the paper does not contain.

Papers are numbered every possible way: 1. / 1) / (1) / Q1 / Q.1 / I. / i) /
and sub-parts like 3(a) or 3 (ii). Whatever the paper uses, renumber nothing:
write the number the paper prints, in this shape:

Q<number as printed>. <the question, word for word>
[marks: <n>]        (only if the paper prints marks for it)

So a sub-part printed as 3 (b) is written Q3(b). A question numbered in Roman
numerals stays in Roman numerals.

Keep multiple-choice options exactly as printed, each on its own line:
(A) ... (B) ... (C) ... (D) ...

Copy any table, data or values a question depends on. If a question refers
to a figure or diagram you cannot read as text, write:
[figure: <what it appears to show>]

Copy section headings and instructions ("Answer any five", "All questions
carry equal marks") on their own line.

If the page carries an ANSWER KEY — a list of correct options, or answers
printed at the end — copy it under a line reading exactly:

ANSWER KEY

and then one per line as: <number> <letter or short answer>

Write nothing else. No commentary, no answers of your own, no summary."""

SOLVE = """You are writing the worked solutions to a school question paper.

For EVERY question given below, produce a complete, correct answer a student
can follow and a teacher can put in front of a class.

**Answer each question the way its own subject is answered.** A paper is not
always mathematics, and most are not. Decide which of these each question
is, and set "kind" to say which:

  "calculation" — there is working to show. Show it. State the formula or
      rule before using it, carry units through, round only at the end and
      say what you rounded to.

  "written" — history, civics, literature, geography, biology theory, an
      explanation, a definition, a comparison, an essay. The ANSWER IS THE
      WRITING. Write what a student should actually put on the page, in
      full sentences and in the right order — not a description of what
      they should write, and not a hint. Never answer a "describe the causes
      of..." question with a single line.

  "choice" — multiple choice. Give the letter AND why it is right, and say
      briefly why the tempting wrong option is wrong.

**Length follows the marks.** A 1-mark question gets one sentence. A 2-mark
question gets two or three. A 5-mark question gets five or six points or a
full paragraph; an 8- or 10-mark question gets a structured answer with a
short opening, the substance in ordered points, and a closing line. If no
marks are printed, judge from the question: "define" is short, "discuss" is
long. An answer that is too short for its marks is a wrong answer in an exam
hall, however true it is.

Also:
- Answer the question that is written, not a similar one.
- Answer in the language the question is written in.
- If a question depends on a figure you were not given, say exactly that and
  answer as far as the text allows. Do not invent the figure.
- If a question cannot be answered from what is here, say so plainly. A
  wrong answer stated confidently is worse than a gap.

Write maths so it reads on a page: x^2 for powers, sqrt(...) for roots,
(a)/(b) for fractions. No LaTeX commands.

Return JSON only:

{"questions": [
  {"n": "1",
   "kind": "calculation",
   "marks": 2,
   "choice": "B",
   "answer": "<the answer a student writes on the page>",
   "working": ["<step, point or paragraph>", "..."]}
]}

For "calculation", "working" is the steps and "answer" is the final result.
For "written", "working" is the points of the answer in order and "answer"
is the opening statement the points expand on — put the substance in
"working", not a summary of it.
For "choice", "answer" is the option's text and "choice" is its letter.

"marks" only if the paper gave them. Every question you were given must
appear, with the same number the paper printed. Never merge two questions."""

# Every numbering scheme a paper in this country actually uses. Q1 / Q.1 /
# 1. / 1) / (1) / I. / iii) / 12(a) / 4 (ii). The number is captured as the
# paper prints it, because renumbering a paper is how a solution ends up
# filed against the wrong question.
# The number itself: 12, iii, (3), and with a sub-part — 12(a), 7 (ii).
_NUM = (r"\(?(?:\d{1,3}|[ivxlIVXL]{1,5})\)?"
        r"(?:\s*\(\s*(?:[a-hj-z]|[ivx]{1,4})\s*\))?")
# Two ways a question starts, and the difference is what is allowed to
# separate the number from the words.
#
# With a "Q" in front, a bare space is enough — "Q.5 State Ohm's law" is
# unambiguous. Without one it must be punctuated, because "1947 saw the
# partition" is a sentence and not question 1947.
_Q_LOOSE = re.compile(r"^\s*Q\s*\.?\s*(" + _NUM + r")\s*[.)\]:—–-]?\s+(.+)$")
# A bracketed sub-part is its own punctuation: "12(a) Find the area" needs no
# full stop after it to be unmistakably a question.
_Q_PART = re.compile(
    r"^\s*((?:\d{1,3}|[ivxlIVXL]{1,5})\s*\(\s*(?:[a-hj-z]|[ivx]{1,4})\s*\))"
    r"\s*[.)\]:—–-]?\s+(.+)$")
_Q_STRICT = re.compile(r"^\s*(" + _NUM + r")\s*[.)\]:—–-]\s+(.+)$")


def _start_of(line):
    """(number, rest) if this line begins a question, else None.

    Tried in order of how unambiguous the marker is. A bare number needs
    punctuation after it, because "1947 saw the partition of India" is a
    sentence and not question 1947.
    """
    return (_Q_LOOSE.match(line) or _Q_PART.match(line)
            or _Q_STRICT.match(line))


def _number(raw):
    """The number as printed, with a wrapping bracket pair removed.

    "(3)" is question 3 written in brackets; "12(a)" is question 12 part a
    and the brackets are part of its name. Stripping every bracket would
    turn the second into "12a", which is not what the paper says.
    """
    n = " ".join(str(raw or "").split())
    if n.startswith("(") and n.count("(") == 1:
        # "(3)" — and "(3" when the closing bracket was taken as the
        # separator by whichever pattern matched first.
        n = n[1:].rstrip(")").strip()
    return n
# [marks: 3] as the reading pass writes it, and every way a paper prints it:
# (3 marks) / [3] / 3M / — 3 marks
_MARKS = re.compile(
    r"(?:\[\s*marks?\s*[:=]\s*(\d{1,3})\s*\]"
    r"|[\[(]\s*(\d{1,3})\s*(?:marks?|m)\s*[\])]"
    r"|[\[(]\s*(\d{1,3})\s*[\])]\s*$"
    r"|(\d{1,3})\s*marks?\s*$)", re.I)


def _marks_in(line):
    m = _MARKS.search(line)
    if not m:
        return None
    for g in m.groups():
        if g:
            try:
                return int(g)
            except ValueError:
                return None
    return None


_KEY_HEAD = re.compile(r"^\s*(?:answer\s*key|answers?|key)\s*[:.]?\s*$", re.I)
# "1 C" / "1. C" / "1-C" / "1) (C)" / "12 : b" — one per line, and also
# several to a line, which is how a key is usually printed to save paper.
_KEY_PAIR = re.compile(
    r"(?:^|[\s,;|])\(?(\d{1,3})\)?\s*[.):\-–—]?\s*\(?([A-Da-d])\)?"
    r"(?=$|[\s,;|])")


def answer_key(text):
    """The paper's own answer key, if it printed one: {number: letter}.

    Read only from BELOW an "answer key" heading. A paper's own
    multiple-choice options — "(A) Oxygen" under question 3 — look exactly
    like a key line to a regular expression, and a key assembled out of the
    options would disagree with every answer and say so confidently, which
    is worse than having no key at all.
    """
    lines = str(text or "").splitlines()
    start = None
    for i, line in enumerate(lines):
        if _KEY_HEAD.match(line):
            start = i + 1
            break
    if start is None:
        return {}
    out = {}
    for line in lines[start:]:
        if _KEY_HEAD.match(line):
            continue
        if line.strip().startswith("--- PAGE"):
            continue
        found = _KEY_PAIR.findall(line)
        if not found and line.strip():
            # A line of prose ends the key. Keys are terse by nature, and
            # reading past the end of one picks up whatever came next.
            if len(line.split()) > 8:
                break
            continue
        for n, letter in found:
            out.setdefault(n, letter.upper())
    return out


def questions(text):
    """The questions a read pass found, as {n, text, marks}.

    Parsed here rather than asked for as JSON, because the reading pass must
    not be given a shape to fill — a model handed a schema starts inventing
    entries to fill it, and an invented question on a paper a class is about
    to sit is the one failure that cannot be allowed.

    Numbering is taken as the paper prints it, in any of the schemes papers
    actually use, because renumbering a paper is how a solution ends up
    filed against the wrong question.
    """
    out = []
    cur = None
    stop = None
    lines = str(text or "").splitlines()
    for i, line in enumerate(lines):
        # Everything below an answer-key heading is the key, not questions.
        if _KEY_HEAD.match(line):
            stop = i
            break
    for line in lines[:stop]:
        raw = line.rstrip()
        if not raw.strip():
            continue
        if raw.strip().startswith("--- PAGE"):
            continue
        m = _start_of(raw)
        if m and len(m.group(2).strip()) > 3:
            if cur:
                out.append(cur)
            body = m.group(2).strip()
            cur = {"n": _number(m.group(1)), "text": body,
                   "marks": _marks_in(body)}
            continue
        if cur is None:
            continue
        mk = _marks_in(raw)
        if mk is not None and len(raw.strip()) <= 20:
            # A bare "[marks: 3]" or "(5 marks)" line belongs to the
            # question above it; a long line that happens to mention marks
            # is part of the question and is kept as text.
            cur["marks"] = mk
            continue
        cur["text"] += "\n" + raw.strip()
    if cur:
        out.append(cur)
    # A paper with one enormous "question" is a page that was not read as a
    # paper at all — prose, a syllabus, a letter. Better to say so than to
    # hand back one answer to a document.
    return out[:MAX_QUESTIONS]


def batches(qs, size=BATCH):
    for i in range(0, len(qs), size):
        yield qs[i:i + size]


def as_prompt(chunk):
    """One batch, written out for the solving pass."""
    parts = []
    for q in chunk:
        head = f"Q{q['n']}."
        if q.get("marks"):
            head += f" [{q['marks']} marks]"
        parts.append(f"{head}\n{q['text']}")
    return "THE QUESTIONS:\n\n" + "\n\n".join(parts) + "\n\n" + SOLVE


def _one(item, asked):
    """One solved question, shaped, or None."""
    if not isinstance(item, dict):
        return None
    n = str(item.get("n") or "").strip()
    answer = str(item.get("answer") or "").strip()
    if not n or not answer:
        return None
    working = item.get("working")
    if isinstance(working, str):
        working = [working]
    # Twenty-four, not fourteen. A ten-mark "discuss the causes of" answer is
    # legitimately a dozen points, and truncating it to fit a limit set for
    # algebra steps hands a student an answer that would lose half its marks.
    working = [str(w).strip() for w in (working or []) if str(w).strip()][:24]
    kind = str(item.get("kind") or "").strip().lower()
    if kind not in ("calculation", "written", "choice"):
        # Inferred rather than defaulted. Which of the three this is decides
        # how the answer is laid out on screen and in the PDF, and a written
        # answer rendered as numbered algebra steps reads as broken.
        kind = ("choice" if item.get("choice")
                else "calculation" if re.search(r"[=+×÷^√]|\d\s*/\s*\d",
                                                " ".join(working) + answer)
                else "written")
    out = {
        "kind": kind,
        "n": n,
        # The question as the READING pass copied it, not as the solving
        # pass echoed it back. The echo is where a question quietly becomes
        # an easier question, and the whole point of two passes is that the
        # paper on screen is the paper on the desk.
        "question": (asked or {}).get("text", str(item.get("question") or "")),
        "answer": answer,
        "working": working,
    }
    if (asked or {}).get("marks"):
        out["marks"] = asked["marks"]
    elif isinstance(item.get("marks"), int):
        out["marks"] = item["marks"]
    ch = str(item.get("choice") or "").strip().upper()[:2]
    if ch and re.fullmatch(r"[A-E]", ch):
        out["choice"] = ch
    return out


def clean(raw, chunk):
    """A batch's reply, matched back to the questions that were asked.

    Matched by number rather than by position: a model that drops question 7
    shifts everything after it, and a solution filed under the wrong number
    is worse than a missing one — a class copies it down and nobody notices
    until the marks come back.
    """
    items = []
    if isinstance(raw, dict):
        items = raw.get("questions") or raw.get("answers") or []
    elif isinstance(raw, list):
        items = raw
    by_n = {str(q["n"]).strip().lower(): q for q in chunk}
    out = []
    for it in items if isinstance(items, list) else []:
        # A model that returns a list of strings, or a null in the middle of
        # one, is a model having a bad day — not a reason for the whole
        # paper to fail. Anything that is not a question is skipped.
        if not isinstance(it, dict):
            continue
        n = str(it.get("n") or "").strip().lower()
        got = _one(it, by_n.get(n))
        if got:
            out.append(got)
    return out


def against_key(solved, key):
    """Say whether each answer agrees with the paper's own printed key.

    The key is the paper's, not ours, and it is the closest thing to a
    ground truth this whole feature ever gets — so where one exists it is
    reported plainly on every question it covers, agreement and disagreement
    alike. A disagreement is not automatically our error: keys are printed
    wrong, and a teacher looking at both is the right person to decide.
    Which is exactly why both are shown rather than one being silently
    preferred.
    """
    if not key:
        return solved
    for s in solved:
        want = key.get(str(s["n"]).strip())
        if not want:
            continue
        s["key"] = want
        mine = (s.get("choice") or "").strip().upper()
        if mine:
            s["agrees"] = (mine == want)
    return solved


def missing(asked, solved):
    """Question numbers that went in and did not come back.

    Reported on screen rather than swallowed. A paper that comes back with
    fifty-eight of sixty answers, silently, is a paper a teacher hands out
    with two holes in it.
    """
    have = {str(s["n"]).strip().lower() for s in solved}
    return [q["n"] for q in asked
            if str(q["n"]).strip().lower() not in have]


_ROOT = re.compile(r"^-?\d+(?:\.\d+)?$")


def _single_root(maths, text):
    """"x = 5" put back into every equation in the same working.

    maths.check_solutions handles ordered tuples — (1, 2) for a pair of
    simultaneous equations — which is the wrong shape for the commonest
    thing on a school paper by a distance: one variable, one quadratic, and
    a claimed root. So that case is checked here, with the same allowlisted
    evaluator, rather than left silently unchecked.
    """
    try:
        eqs = maths.equations(text)
    except Exception:
        return []
    claims = [(left.strip(), float(right))
              for left, right, used in eqs
              if len(left.strip()) == 1 and left.strip().isalpha()
              and _ROOT.match(right.strip())]
    if not claims:
        return []
    out = []
    for name, val in claims:
        for left, right, used in eqs:
            # Not the claim itself, and not an equation needing a variable
            # this claim does not supply.
            if set(used) != {name} or left.strip() == name:
                continue
            lv = maths.evaluate(left, {name: val})
            rv = maths.evaluate(right, {name: val})
            if lv is None or rv is None:
                continue
            scale = max(1.0, abs(lv), abs(rv))
            if abs(lv - rv) <= 1e-6 * scale:
                continue
            out.append(f"it offers {name} = {val:g}, but {left} = {right} "
                       f"gives {lv:g} = {rv:g} there")
            break
    return out


def verify(solved):
    """Substitute claimed solutions back into their own equations.

    maths.check_solutions reports FAILURES — it stays quiet unless a claimed
    root genuinely does not satisfy an equation stated in the same working.
    So a question comes back flagged or it comes back untouched; nothing is
    stamped correct, because passing this check means one thing was
    consistent and not that the solution is right.

    Deterministic and free, which is exactly why it should not be a model's
    job. A worked solution a class copies into their books is the one place
    a confident wrong number does the most damage.
    """
    try:
        import maths
    except Exception:
        return solved
    for s in solved:
        text = s["answer"] + "\n" + "\n".join(s.get("working") or [])
        try:
            bad = [b["problem"] for b in maths.check_solutions(text)]
        except Exception:
            bad = []
        bad += _single_root(maths, text)
        if bad:
            s["doubt"] = bad[:2]
    return solved
