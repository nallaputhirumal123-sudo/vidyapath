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

For every question on the page write:

Q<number>. <the question, word for word>
[marks: <n>]        (only if the paper prints marks for it)

Keep multiple-choice options exactly as printed, each on its own line:
(A) ... (B) ... (C) ... (D) ...

Copy any table, data or values a question depends on. If a question refers
to a figure or diagram you cannot read as text, write:
[figure: <what it appears to show>]

Copy section headings and instructions (\"Answer any five\", \"All questions
carry equal marks\") on their own line.

Write nothing else. No commentary, no answers, no summary."""

SOLVE = """You are writing the worked solutions to a school question paper.

For EVERY question given below, produce a complete, correct solution a
student can follow and a teacher can put in front of a class.

Rules:
- Answer the question that is written, not a similar one.
- Show the working. A final answer with no steps is not a solution.
- State the formula or rule before using it, once, in the step that uses it.
- Carry units through the working and put them on the final answer.
- For multiple choice, give the letter AND why it is right.
- Round only at the end, and say what you rounded to.
- If a question depends on a figure you were not given, say exactly that in
  the answer and solve as far as the text allows. Do not invent the figure.
- If a question cannot be answered from what is here, say so plainly. A
  wrong answer stated confidently is worse than a gap.

Write maths so it reads on a page: x^2 for powers, sqrt(...) for roots,
(a)/(b) for fractions. No LaTeX commands.

Return JSON only:

{"questions": [
  {"n": "1",
   "question": "<the question, as given to you>",
   "marks": 2,
   "choice": "B",
   "answer": "<the final answer, one line>",
   "working": ["<step>", "<step>", "..."]}
]}

"marks" only if the paper gave them. "choice" only for multiple choice.
Every question you were given must appear, in the same order, with the same
number. Never merge two questions into one."""

_Q = re.compile(r"^\s*Q?\s*(\d+[a-z]?(?:\s*\([a-z ivx]+\))?)\s*[.)]\s*(.+)$",
                re.I)
_MARKS = re.compile(r"\[?\s*marks?\s*[:=]\s*(\d+)\s*\]?", re.I)


def questions(text):
    """The questions a read pass found, as {n, text, marks}.

    Parsed here rather than asked for as JSON, because the reading pass must
    not be given a shape to fill — a model handed a schema starts inventing
    entries to fill it, and an invented question on a paper a class is about
    to sit is the one failure that cannot be allowed.
    """
    out = []
    cur = None
    for line in str(text or "").splitlines():
        raw = line.rstrip()
        if not raw.strip():
            continue
        if raw.strip().startswith("--- PAGE"):
            continue
        m = _Q.match(raw)
        if m and len(m.group(2).strip()) > 3:
            if cur:
                out.append(cur)
            cur = {"n": m.group(1).strip(), "text": m.group(2).strip(),
                   "marks": None}
            continue
        if cur is None:
            continue
        mk = _MARKS.search(raw)
        if mk and len(raw.strip()) <= 20:
            # A bare "[marks: 3]" line belongs to the question above it; a
            # long line that happens to mention marks is part of the
            # question and is kept as text.
            try:
                cur["marks"] = int(mk.group(1))
            except ValueError:
                pass
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
    working = [str(w).strip() for w in (working or []) if str(w).strip()][:14]
    out = {
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
