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
import hashlib
import json
import re

# Six, and the number has now been three things in one day, so here is the
# whole reasoning rather than the latest conclusion.
#
# Ten was chosen so each answer still gets written out properly — twenty and
# the later ones turn into "similarly to Q13". That part has never changed.
#
# Then a five-question paper came back with nothing, and it looked like
# truncation. It was not: the models this key reaches allow 65536 output
# tokens, and the 9000 being asked for was our own limit. What actually
# happened was the clock — one call had 55 seconds, and six dense physics
# questions with four options each are not written in 55 seconds. So it went
# to three, which fit.
#
# The 55 seconds was ALSO ours. It was decided when nothing here reasoned,
# and reasoning is spent before a word of the answer exists; a solving call
# has 100 seconds now, which is the real ceiling for that work. With that
# fixed, three is simply expensive: a thirty-question paper became ten
# solving calls and ten checking calls, one after another, and a teacher
# watched a spinner for a quarter of an hour.
#
# Six halves the calls and still fits the time. What makes that safe rather
# than a gamble is what happens after: every answer is worked a second time
# from the question alone, so a batch that runs long enough to be hurried is
# a batch whose hurry the checking pass will find.
BATCH = 6
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

**Multiple-choice options are part of their question, never questions of
their own.** Write them on their own lines under the question they belong
to, and ALWAYS letter them (A), (B), (C), (D) — even when the paper numbers
them (1), (2), (3), (4), which many do. Keep the wording exactly as
printed; only the label changes.

That relabelling is not cosmetic. A JEE paper numbers the four options of
question 32 as (1) to (4), and written that way they read as questions 1 to
4 — so a two-question paper came out as six, and four options were sent off
to be answered as though somebody had asked them.

(A) ... (B) ... (C) ... (D) ...

Copy any table, data or values a question depends on. If a question refers
to a figure or diagram you cannot read as text, write:
[figure: <what it appears to show>]

**The General Instructions are not questions.** Every board paper opens
with a numbered list — "(i) This question paper contains 38 questions.
(ii) It is divided into five Sections." — and those are about the paper,
not things to answer. Never write one as Q<number>. Put them, and any
section heading or rubric ("Answer any five", "All questions carry equal
marks"), under a line reading exactly:

NOT A QUESTION

and start numbering only where the paper's own questions start.

**A bilingual paper is one paper.** If the same question is printed in two
languages, write it once, in the language it is printed in first, with the
number the paper gives it. Do not renumber the second language's copy as
new questions.

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

      Every step says WHY, not only what. "Divide both sides by 2" is a
      keystroke; "divide both sides by 2 to leave x on its own" is the
      reason a student can use on the next question. Somebody who was
      stuck on this should be able to see the exact step where they went
      wrong and what they should have thought.

  "written" — history, civics, literature, geography, biology theory, an
      explanation, a definition, a comparison, an essay. The ANSWER IS THE
      WRITING. Write what a student should actually put on the page, in
      full sentences and in the right order — not a description of what
      they should write, and not a hint. Never answer a "describe the causes
      of..." question with a single line.

  "choice" — multiple choice. Do the work that finds the answer, the same
      way you would if no options were printed; then give the letter, and
      say briefly why the tempting wrong option is tempting and wrong.
      Never reason backwards from an option — "(D) is 481, which matches"
      is not a solution, and it is how a wrong option gets justified.

**Length follows the marks.** A 1-mark question gets one sentence. A 2-mark
question gets two or three. A 5-mark question gets five or six points or a
full paragraph; an 8- or 10-mark question gets a structured answer with a
short opening, the substance in ordered points, and a closing line. If no
marks are printed, judge from the question: "define" is short, "discuss" is
long. An answer that is too short for its marks is a wrong answer in an exam
hall, however true it is.

**Chemistry is written the way a chemistry paper marks it.** Where an
equation belongs in the answer, write it balanced, and count the atoms on
both sides before you write it down — a correct reaction with a coefficient
missing loses most of the marks. Include state symbols where the paper uses
them. Write formulas as they are printed: H2SO4, Ca(OH)2, CuSO4.5H2O, and
2H2 + O2 -> 2H2O. Where a question asks for a structure that cannot be
drawn here, give the condensed formula and describe the bonding in words
rather than leaving the question short.

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


# A model transcribing a photographed page writes markdown.
#
# "**Q1.** Define osmosis", "## Q1.", "* 1." — every one of those is how a
# vision model formats a question it has just read, and the parser matched
# none of them. A photographed paper came back "No numbered questions were
# found in that", which is the main case this feature exists for.
#
# Stripped rather than allowed for in the number patterns, so there is one
# place that knows about markdown instead of four regexes each carrying a
# copy.
_MD_LEAD = re.compile(r"^\s*(?:[>#]+\s*|[*+-][ 	]+)+")
_MD_BOLD = re.compile(r"^\s*(?:\x2a\x2a(.{1,30}?)\x2a\x2a|__(.{1,30}?)__)")


# ...and sometimes it answers in JSON, having been told to write plain text.
#
# A real JEE Chemistry paper, photographed, came back as an array of
# strings: [ "NOT A QUESTION", "JEE MAINS-9-APRIL-2014", "CHEMISTRY",
# "Q31. In a face centered cubic lattice..." ]. Every line was a question,
# correctly read, wearing a pair of quotes and a comma — and not one of
# them matched, so a perfectly good reading of a real paper parsed as
# nothing.
#
# Unwrapped rather than forbidden in the prompt. The prompt already says to
# write plain lines; a model that formats anyway is a fact about models, not
# a thing to keep asking about, and the parser is the side that can be sure.
# A line that is only brackets, braces and commas: the array that the
# lines were sitting in, not a line of the paper.
_JSON_ONLY = re.compile(r"^[\s\[\]{},]*$")
_JSON_LINE = re.compile(r'^\s*[\[\]{},]*\s*"(.*)"\s*,?\s*$')


def _plain_line(line):
    """One line with the model's own formatting taken off."""
    out = str(line or "")
    m = _JSON_LINE.match(out)
    if m:
        # A JSON string, so JSON decodes its escapes.
        #
        # Undoing them by hand missed the one that matters most. A question
        # carrying a line break arrives as a backslash and an n, and
        # replacing only quotes and backslashes left it sitting there — so a
        # real paper reached a class reading "stated as,np = nRT" and
        # ".nThis equation reduces to", with the break showing as the letter
        # n in the middle of the formula.
        try:
            out = json.loads('"' + m.group(1) + '"')
        except Exception:
            out = (m.group(1).replace(chr(92) + '"', '"')
                   .replace(chr(92) + chr(92), chr(92)))
    out = _MD_LEAD.sub("", out)
    # "**Q1.**" — unwrap only a short leading emphasis, which is a heading
    # marker. A long emphasised run is a model emphasising words inside the
    # question, and the question keeps them.
    m = _MD_BOLD.match(out)
    if m:
        out = (m.group(1) or m.group(2) or "") + out[m.end():]
    return out


def _start_of(line):
    """(number, rest) if this line begins a question, else None.

    Tried in order of how unambiguous the marker is. A bare number needs
    punctuation after it, because "1947 saw the partition of India" is a
    sentence and not question 1947.
    """
    line = _plain_line(line)
    return (_Q_LOOSE.match(line) or _Q_PART.match(line)
            or _Q_STRICT.match(line))


def _number(raw):
    """The number as printed, with a wrapping bracket pair removed.

    "(3)" is question 3 written in brackets; "12(a)" is question 12 part a
    and the brackets are part of its name. Stripping every bracket would
    turn the second into "12a", which is not what the paper says.
    """
    n = " ".join(str(raw or "").split())
    # "Q2)" — the bracket closes the marker, not a bracketed number, and it
    # was ending up inside the number as "2)".
    if n.endswith(")") and "(" not in n:
        n = n[:-1].strip()
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


def _lines(text):
    """The text as lines, with each one unwrapped FIRST.

    Unwrapping has to happen before the split, not during it. A JSON string
    holding a line break is one line until it is decoded and two lines
    after — so parsing line by line and unwrapping each as it arrived left
    "Q32. …formula…next sentence" welded into one line, and a pattern
    anchored to the end of a line matched none of it.
    """
    out = []
    for raw in str(text or "").splitlines():
        got = _plain_line(raw).splitlines()
        for one in (got if got else [""]):
            # Unwrapped AGAIN, because a model that answers in JSON also
            # quotes the lines inside its own string: a question's options
            # arrived as  "(A) ...",  "(B) ...",  with the quotes and commas
            # decoded intact, and reached the class wearing them.
            one = _plain_line(one)
            # Pure JSON furniture — a lone "]" closing the array — is
            # structure, not part of anybody's question.
            if one.strip() and not _JSON_ONLY.match(one):
                out.append(one)
            elif not one.strip():
                out.append("")
    return out


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
        if _KEY_HEAD.match(_plain_line(line)):
            start = i + 1
            break
    if start is None:
        return {}
    out = {}
    for line in lines[start:]:
        if _KEY_HEAD.match(_plain_line(line)):
            continue
        if line.strip().startswith("--- PAGE"):
            continue
        # Unwrapped like every other line: a key inside a JSON array is
        # "31 C", and the quotes would be read as part of the answer.
        line = _plain_line(line)
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


_ROMAN = re.compile(r"^[ivxl]{1,5}$", re.I)
# Where a paper says, in its own words, that what follows is not a question.
# The reading pass is told to write NOT A QUESTION; a paper read as text has
# no reading pass, so its own heading is used instead.
_NOT_Q = re.compile(
    r"^\s*(?:NOT A QUESTION"
    r"|general\s+instructions?"
    r"|सामान्य\s*निर"
    r"्देश)\s*[:.\-–—]?\s*$", re.I)
# ...and where it stops: the first real question, or a section heading.
_SECTION = re.compile(r"^\s*(?:section|part|खण्ड|"
                      r"भाग)\b", re.I)


# An instruction is about the paper; a question asks for something.
#
# Both are numbered sentences, which is why position and numbering alone
# could not separate them: a real JEE sheet lists "1. All questions are
# compulsory" and "2. Use of a calculator is not allowed" and then asks Q31
# and Q32, and a two-question paper was reported as six because four
# instructions were sent off to be answered — and then answered.
#
# What actually differs is the verb. A paper's rubric talks ABOUT the paper:
# its questions, its sections, its marks, its calculator rule. A question
# asks you to find, prove, explain or choose something.
_RUBRIC_WORDS = re.compile(
    r"(?:all questions|this (?:question )?paper|the question paper|"
    r"question paper|attempt|compulsory|calculator|marks are|"
    r"indicate full marks|internal choice|is not allowed|are allowed|"
    r"divided into|sections?.*carry|use of a|figures? to the right|"
    r"write the|answer any|carry equal marks|first attempt|"
    r"will be evaluated|given credit|seat no|max\.? marks|time allowed)",
    re.I)


def _looks_like_question(line):
    """Is this a question, or the paper talking about itself?"""
    return not _RUBRIC_WORDS.search(_plain_line(line))


def _is_option_of(cur, n):
    """Is this number an option of the question already open?"""
    try:
        here = int(str(n).strip())
    except (ValueError, TypeError):
        return False          # (A), (i) — lettered options never collide
    if not (1 <= here <= 6):
        return False          # options are few; a real question 7 is not one
    try:
        open_at = int(str(cur.get("n", "")).strip())
    except (ValueError, TypeError):
        # A genuine SUB-PART — 1(i), 7 (ii) — carries a bracket, and the
        # only numbered thing that follows one is its options. Without this
        # the Maharashtra SSC paper split question 1(i) into its own
        # options.
        #
        # A question numbered in plain romans — i, ii, iii — is not a
        # sub-part, and treating it as one swallowed a whole paper: with
        # "iii" open, questions 1 and 2 were read as its options.
        return "(" in str(cur.get("n", ""))
    # Numbering that goes BACKWARDS. A paper does not run 32 then 1, but it
    # does run 1 then 2, so an ordinary paper is untouched.
    return here <= open_at


def _strip_rubric(lines):
    """Drop the block a paper marks as not being questions.

    Belt and braces with the roman-numeral rule below, and it catches what
    that rule cannot: instructions numbered 1, 2, 3, which some state boards
    do, and which are otherwise indistinguishable from question 1.

    The block ends at a section heading or at the first line that is not
    part of the list, so a paper whose questions begin immediately after the
    instructions loses nothing.
    """
    # Two markers, and they mean opposite things about what follows.
    #
    # "NOT A QUESTION" is the READING pass's own marker, and the prompt tells
    # it to put the rubric there and then "start numbering only where the
    # paper's own questions start". So the first numbered line after it IS a
    # question, and skipping numbered lines past that marker threw away the
    # whole paper: a real JEE sheet reported "no answer came back for
    # questions 1, 2, 3, 4" because the parser had eaten them here.
    #
    # A paper's OWN "General Instructions" heading is the other way round —
    # the numbered items under it are the instructions, which is the case
    # this function was written for.
    out, skipping, model_marked = [], False, False
    for ln in lines:
        plain = _plain_line(ln)
        if _NOT_Q.match(plain):
            skipping = True
            model_marked = "not a question" in plain.strip().lower()
            continue
        if skipping:
            if _SECTION.match(plain):
                skipping = False
            elif model_marked and _start_of(ln) and _looks_like_question(ln):
                # The paper's questions have started.
                skipping = False
            else:
                m = _start_of(ln)
                # A numbered item is more instructions; anything else has
                # ended the list.
                if m or not ln.strip():
                    continue
                skipping = False
        out.append(ln)
    return out


def _drop_instructions(qs):
    """The General Instructions are a numbered list and are not questions.

    Every board paper opens with them — "(i) This question paper contains 38
    questions. (ii) It is divided into five Sections..." — and to a regular
    expression they are indistinguishable from questions, because they are a
    numbered list of sentences. On a real CBSE paper they arrived as nine
    phantom questions, twice over in a bilingual one, and were duly sent off
    to be solved.

    The rule that separates them: a paper that numbers its questions in
    arabic does not also number questions in bare romans. It uses romans for
    the instructions, and for sub-parts — and a sub-part parses as "7 (ii)",
    which is arabic at the top level and is left alone.

    Positional would be wrong, and was: a bilingual paper prints the
    instructions twice, so the English set arrives AFTER question 1 of the
    Hindi half and a "drop until the first arabic question" rule keeps all
    nine of them. A paper genuinely numbered i, ii, iii throughout has no
    arabic questions at all, so nothing is dropped from it.
    """
    if not any(q["n"][:1].isdigit() for q in qs):
        return qs
    return [q for q in qs if not _ROMAN.match(q["n"])]


def _dedupe(qs):
    """One entry per question number, keeping the readable one.

    A CBSE paper is bilingual: every question is printed in Hindi and again
    in English, so a 38-question paper parses as 76 and the second half is
    the first half again. Worse, the Hindi is typeset in a legacy font that
    extracts as mojibake — so the pair is one unreadable copy and one good
    one.

    Keeping the first would keep the broken half. Keeping the readable one
    is right in both directions: when the extraction is clean, both copies
    read properly and the paper's own order wins; when it is not, the half
    that survived is the half that gets solved.
    """
    seen, out = {}, []
    for q in qs:
        key = " ".join(q["n"].split()).lower()
        if key not in seen:
            seen[key] = len(out)
            out.append(q)
            continue
        kept = out[seen[key]]
        try:
            import teachpdf
        except Exception:
            continue
        # Compared, not judged. "Is this document mojibake" needs a
        # threshold and enough words to measure on; "which of these two
        # copies of one question is the better one" only needs to know which
        # is worse, and a question is often a single line.
        if teachpdf.glyph_ratio(q["text"]) < \
                teachpdf.glyph_ratio(kept["text"]):
            out[seen[key]] = q
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
    lines = _lines(text)
    for i, line in enumerate(lines):
        # Everything below an answer-key heading is the key, not questions.
        if _KEY_HEAD.match(_plain_line(line)):
            stop = i
            break
    for line in _strip_rubric(lines[:stop]):
        raw = line.rstrip()
        if not raw.strip():
            continue
        if raw.strip().startswith("--- PAGE"):
            continue
        m = _start_of(raw)
        # A numbered line that is the paper talking ABOUT itself is not a
        # question, wherever it appears.
        #
        # Blocks were not enough. The rubric block ends at the first line
        # that is not a numbered item — and a real JEE sheet puts
        # "JEE MAINS-9-APRIL-2014" and "CHEMISTRY" between the marker and
        # the instructions, so the block closed before reaching them and
        # "1. All questions are compulsory" became question 1. A two-question
        # paper was reported as six, and once the block rule was loosened the
        # model dutifully answered all four instructions.
        if m and not _looks_like_question(raw):
            continue
        # An option, not a question: the numbering went BACKWARDS.
        #
        # A JEE paper labels the four options of question 32 as (1) to (4),
        # and read that way they are questions 1 to 4 — so a two-question
        # paper came out as six and four options were answered as though
        # somebody had asked them.
        #
        # Numbering that restarts below a question already open is the
        # signal, and it cannot misfire on an ordinary paper: with question
        # 1 open, a line numbered 2 is larger, so it opens question 2 as it
        # always did. Only a small number arriving under a bigger one is
        # read as an option, which is the only way options are ever printed.
        if m and cur and _is_option_of(cur, _number(m.group(1))):
            cur["text"] += "\n" + _plain_line(raw).strip()
            continue
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
    out = _drop_instructions(out)
    out = _dedupe(out)
    # A paper with one enormous "question" is a page that was not read as a
    # paper at all — prose, a syllabus, a letter. Better to say so than to
    # hand back one answer to a document.
    return out[:MAX_QUESTIONS]


def fingerprint(n, text):
    """A question's identity, for checking it is on the paper it claims.

    Whitespace-insensitive, because the question travels to the browser as
    JSON and back and a rewrapped line is the same question. Not
    case-folded: a chemistry paper's Mg and mg are different things, and a
    check that cannot tell them apart is not much of a check.
    """
    return " ".join(str(n or "").split()) + "\x1f" + \
        " ".join(str(text or "").split())


def cache_key(q):
    """One question's identity as a cache entry.

    Keyed on the QUESTION, not on the batch it happened to travel in.
    Batching is an artefact of how the work is sent — ten at a time so each
    answer still gets written out properly — and it made the cache useless
    the moment anything shifted: re-running a paper after one bad batch,
    two schools uploading the same paper with the questions grouped
    differently, or a paper that shares a question with another paper. All
    of those paid again for an answer already held.

    The text and the marks, and not the number. A question is the same
    question wherever it is printed, so the same problem numbered 7 on one
    board's paper and 12 on another's reuses the answer — the number is
    re-attached from whichever paper asked. The MARKS are in the key
    because the prompt sizes an answer by them: a two-mark and a five-mark
    version of the same question want different answers, and serving one
    for the other is how a student loses marks for a correct answer.
    """
    body = " ".join(str(q.get("text") or "").split())
    marks = q.get("marks")
    raw = f"{body}{marks if isinstance(marks, int) else ''}"
    return "solveq|" + hashlib.sha256(
        raw.encode("utf-8", "replace")).hexdigest()[:40]



# ---- the second opinion -------------------------------------------------
#
# maths.py substitutes a root back into its own equation and chem.py counts
# the atoms on both sides, and between them they catch a confident wrong
# number in the two places arithmetic can be checked for free. Neither of
# them can tell you that a torque question was answered with the wrong sign,
# or that a physics derivation was right in every step and the answer line
# contradicted it — which is what a real JEE paper came back with.
#
# So the paper is worked TWICE, and the second time the answer is not shown
# until the checker has produced its own.
#
# **Not shown, and that is the whole design.** A model given a question and
# a proposed answer agrees with it: it reads as a reasonable answer, and
# agreeing is the shortest path. Asked to solve the question cold and only
# then told what was proposed, it disagrees when it should. The order is the
# difference between a check and a rubber stamp.
#
# A disagreement is not a correction, and is never presented as one. Two
# workings that reach different answers need the person holding the paper,
# and that person is a teacher who can read both — so both are shown, with
# the question, and neither is quietly picked.
CHECK = """You are checking the worked solutions to a school question paper,
for a teacher who is about to put them in front of a class.

For EVERY question below: work it out yourself, completely, from the
question alone. Do not read the proposed answer until you have your own —
it is at the end of each question and it is there so you can compare, not so
you can agree with it.

Then say which of these it is, in "verdict":

  "agree"     your answer is the same as the proposed one. Small differences
              of wording, rounding or arrangement are still agreement — 0.5
              and 1/2 are the same answer, and so are "2 m/s^2" and "2 ms^-2".
  "disagree"  your answer is genuinely different. Say what you got and why
              the proposed working goes wrong, naming the step.
  "unsure"    you cannot settle it — the question needs a figure you were not
              given, or it is ambiguous as printed. Say what is missing.

An answer that is right for a DIFFERENT question is a disagreement: papers
are misread, and a solution to a similar-looking problem is the failure that
reaches a class looking correct.

Be exact about multiple choice. If the proposed letter is not the option
your own working lands on, that is a disagreement even when the reasoning
either side of it reads well.

Return JSON only:

{"checks": [{"n": "1",
             "verdict": "agree"|"disagree"|"unsure",
             "answer": "<the answer YOU got, always, even when you agree>",
             "why": "<one or two sentences; for a disagreement, name the "
                    "step that goes wrong>"}]}

Every question you were given must appear, with the number the paper used."""


def as_check(solved):
    """One batch of solved questions, written out for the checking pass.

    The proposed answer comes LAST in each block and is labelled as
    something not to read yet. It cannot be withheld — a checker that never
    sees it can only produce a second opinion, and something still has to
    compare the two — but where it sits on the page decides whether the
    model works the question or reads the answer and nods.
    """
    parts = []
    for s in solved or []:
        head = "Q%s." % s.get("n")
        if s.get("marks"):
            head += " [%s marks]" % s["marks"]
        work = " ".join(str(w) for w in (s.get("working") or [])[:8])
        parts.append(
            head + "\n" + str(s.get("question") or "") + "\n"
            + "PROPOSED ANSWER (do not read this until you have your own): "
            + str(s.get("answer") or "") + "\n"
            + "PROPOSED WORKING: " + work[:1200])
    return "THE QUESTIONS:\n\n" + "\n\n".join(parts) + "\n\n" + CHECK


_VERDICTS = ("agree", "disagree", "unsure")


def apply_check(solved, reply):
    """Attach each verdict to its own question. Never rewrites an answer."""
    by_n = {}
    for c in ((reply or {}).get("checks") or []):
        if not isinstance(c, dict):
            continue
        # "2" and "q2" both point at question 2, the same way clean() does
        # it: a model asked about Q2 answers with either, and a verdict
        # filed under a name nothing matches is a verdict that vanishes —
        # which here would read on screen as "not checked".
        n = str(c.get("n") or "").strip().lower().lstrip("q").strip(".")
        if not n:
            continue
        verdict = str(c.get("verdict") or "").strip().lower()
        by_n[n] = {
            "verdict": verdict if verdict in _VERDICTS else "unsure",
            "answer": str(c.get("answer") or "").strip()[:600],
            "why": str(c.get("why") or "").strip()[:600],
        }
    for s in solved or []:
        mine = str(s.get("n") or "").strip().lower()
        got = by_n.get(mine) or by_n.get(mine.lstrip("q").strip("."))
        if not got:
            continue
        # The check is recorded beside the answer, never in place of it.
        # Two workings that disagree need the teacher holding the paper.
        s["check"] = got
        if got["verdict"] == "disagree":
            s.setdefault("doubt", []).append(
                "checked again and got " + (got["answer"] or "a different "
                                            "answer")
                + (" — " + got["why"] if got["why"] else ""))
    return solved

def check_key(s):
    """One CHECKED answer's identity.

    The question and the answer both, because a check is a judgement on a
    pair. The same question answered differently — a re-run, a different
    model, a paper that shares the question — is a different thing to check,
    and serving the old verdict against a new answer would put a tick beside
    something nobody looked at.
    """
    body = " ".join(str(s.get("question") or "").split())
    ans = " ".join(str(s.get("answer") or "").split())
    return "solvechk|" + hashlib.sha256(
        (body + "|" + ans).encode("utf-8", "replace")).hexdigest()[:40]


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
        # The paper's number, not the model's echo of it. Asked for question
        # 2, models answer "n": "Q2" often enough that a real solved paper
        # came back headed "QQ2" — and worse, "Q2" no longer matches "2", so
        # nothing the reading pass found lines up with it.
        "n": (asked or {}).get("n") or n,
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
    # Both "2" and "q2" point at question 2, because a model asked about Q2
    # answers with either and a solution filed under a name nothing matches
    # is a solution that vanishes.
    by_n = {}
    for q in chunk:
        key = str(q["n"]).strip().lower()
        by_n[key] = q
        by_n.setdefault("q" + key, q)
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


# Does the answer say what the working just concluded?
#
# A real JEE Chemistry solution worked correctly to "the ratio is 2 : 5,
# which gives A2B5" and then printed "Answer: A4B5". Every step was right
# and the answer line disagreed with the last of them — which is the one
# failure that reaches a class wrong, because a student copies the answer
# and not the working.
#
# Nothing here judges the chemistry. It asks a narrower question that can be
# asked without knowing any: the working ends in a formula, the answer is a
# formula, and they are not the same formula. Two claims that contradict
# each other need a person, whichever is right.
# No word boundaries anywhere in this file. Three of them have arrived here
# today as literal backspaces, and a pattern that begins with one matches
# nothing at all, silently. Explicit character classes instead.
_FORMULA = re.compile(
    r"(?:^|[^A-Za-z0-9])"
    r"([A-Z][a-z]?[0-9]*(?:[A-Z][a-z]?[0-9]*){1,7})"
    r"(?![A-Za-z0-9])")


def _conclusions(working):
    """The formulas and numbers the last steps of the working land on."""
    tail = " ".join(str(w) for w in (working or [])[-2:])
    return tail


def _disagrees(working, answer):
    """A contradiction, said in the same shape by both sides, or nothing."""
    tail, ans = _conclusions(working), str(answer or "")
    if not tail or not ans:
        return None
    # Chemical-formula shape: A2B5 against A4B5. Compared only when BOTH
    # sides carry one, so an answer in words is never argued with.
    ft = set(_FORMULA.findall(tail))
    fa = set(_FORMULA.findall(ans))
    if ft and fa and not (ft & fa):
        return (f"the working ends on {sorted(fa)[0]!s} vs "
                f"{sorted(ft)[0]!s} — the answer and its own last step do "
                f"not agree")
    return None


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
        # ...the equations it wrote, counted rather than trusted. Balancing
        # is a whole question on a Class 10 paper, and the way a model gets
        # it wrong — right reaction, right formulas, one coefficient short —
        # is the way a student reads straight past.
        try:
            import chem
            bad += chem.unbalanced(text)
        except Exception:
            pass
        # ...and the answer against the working's own conclusion.
        clash = _disagrees(s.get("working"), s.get("answer"))
        if clash:
            bad.append(clash)
        if bad:
            s["doubt"] = bad[:2]
    return solved
