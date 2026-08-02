"""Photograph anything you are stuck on, and get it taught back to you.

Not a maths scanner and not a code scanner. This is an adult product and the
people using it are studying whatever they are studying — organic chemistry,
financial accounting, a statistics paper, contract law, a physics problem set,
a stack trace, a page of Spanish. Restricting the subject would be inventing a
limit the users do not have.

So the model is not told what subject to expect. It is told to work out what
it is looking at and to teach that, and the only thing this module fixes is
*how* an explanation is shaped: read it back, work through it in steps, give
the answer last. Giving the answer instead of the working is the failure mode
that makes a scanner worthless — somebody copies a number, learns nothing, and
meets the same question again in the exam.

`kind` is a teaching shape, not a subject. A titration calculation and a
compound-interest question are both "worked"; a case summary and a question
about photosynthesis are both "concept". The subject itself is free text,
because there is no list of subjects that would not eventually be wrong.

Nothing here is rendered as markup. Every field is plain text and the page
escapes it on the way in, the same rule the smart board follows: a model that
could emit HTML into this would be emitting it into somebody else's session.
"""
import re

# How the explanation is laid out — not what it is about.
KINDS = (
    "worked",   # anything with steps to show: maths, physics, chemistry,
                # statistics, accounting, electronics, quantitative aptitude
    "code",     # a program, function, query or snippet
    "error",    # an error message, stack trace, failing test, console output
    "concept",  # a question answered in prose: biology, history, law, theory
    "other",
)

# Captions, not execution targets — the page prints this above a snippet.
LANGS = {
    "python", "javascript", "typescript", "java", "c", "cpp", "csharp", "go",
    "rust", "ruby", "php", "sql", "bash", "shell", "powershell", "html",
    "css", "r", "kotlin", "swift", "scala", "matlab", "vhdl", "verilog",
    "assembly", "text",
}

MAX_MB = 8.0
MIMES = ("image/jpeg", "image/png", "image/webp", "image/heic", "image/heif")


def prompt():
    return """Someone has photographed something they are stuck on. You are
their tutor. They are an adult studying at their own level — capable, not a
child, and not necessarily a programmer. It could be any subject at all.

FIRST work out how this needs to be taught, and set "kind":
  "worked"   there is something to calculate or derive — maths, physics,
             chemistry, statistics, accounting, engineering, aptitude
  "code"     a program, function, query or snippet
  "error"    an error message, stack trace, failing test or console output
  "concept"  a question answered in words rather than working — biology,
             history, law, economics, theory, definitions, language
  "other"    none of those

Set "subject" to the actual subject in two or three words, whatever it is.
Do not force it into a list.

THEN read what is in the image and write it out in "read", exactly as it
appears. Keep the original line breaks and indentation. If there are several
questions, take the first and say so. If you cannot read it, set "readable" to
false and say what you can actually see in "next", rather than guessing.

THEN teach it, in "steps":
  worked   Work through it line by line with the actual arithmetic in
           "working", so they could do the next one alone.
  code     Say what the code really does, then what is wrong or what is being
           asked. Put the corrected or relevant lines in "working".
  error    Name the actual cause, not the symptom. "working" holds the line to
           change. Say how they could have found it themselves — reading a
           traceback from the bottom up is a skill nobody is taught.
  concept  Build the explanation up in stages, each one resting on the last.
           Use "working" for a concrete example, and leave it empty if a
           worked example would be forced.
  other    One step describing what you can see.

Give the final answer in "answer", never instead of the working.

Return JSON only:
{"readable": true,
 "kind": "worked"|"code"|"error"|"concept"|"other",
 "subject": "the actual subject, 2-3 words",
 "lang": "python"|"sql"|... (empty unless it is code),
 "read": "what the photo said, written out",
 "steps": [{"heading": "short label",
            "teach": "2-5 sentences explaining this move",
            "working": "the arithmetic, the code, or a concrete example"}],
 "answer": "the final answer, the fix, or the short answer",
 "next": "one sentence on what to practise so this becomes easy"}

Rules:
- 2 to 6 steps.
- Plain text everywhere. No markdown, no backticks, no HTML.
- Explain in plain language, and define any term the first time you use it.
- Never invent a question the photo does not contain."""


def _plain(v, n):
    """Trim to something printable. Control characters out, tabs and newlines
    kept — losing the line breaks in a code snippet or a derivation would make
    the one field that has to keep its shape lose it."""
    s = str(v or "")
    s = "".join(c for c in s if c in "\n\t" or ord(c) >= 32)
    return s.strip()[:n]


def clean(d):
    """Rebuild the model's reply field by field.

    Rebuilt rather than filtered: anything not named here does not survive, so
    a field nobody anticipated cannot arrive alongside the rest and be
    rendered.
    """
    if not isinstance(d, dict):
        d = {}
    steps = []
    for st in (d.get("steps") or [])[:6]:
        if not isinstance(st, dict):
            continue
        step = {"heading": _plain(st.get("heading"), 120),
                "teach": _plain(st.get("teach"), 900),
                "working": _plain(st.get("working"), 900)}
        if step["teach"] or step["working"]:
            steps.append(step)

    kind = str(d.get("kind") or "").strip().lower()
    lang = str(d.get("lang") or "").strip().lower()
    return {
        # Readable means "and there is something to show for it". A model that
        # claims readable while returning no steps has not read anything, and
        # letting that through would cache an empty answer forever.
        "readable": bool(d.get("readable", True)) and bool(steps),
        "kind": kind if kind in KINDS else "other",
        "subject": _plain(d.get("subject"), 60),
        "lang": lang if lang in LANGS else "",
        "read": _plain(d.get("read"), 2000),
        "steps": steps,
        "answer": _plain(d.get("answer"), 800),
        "next": _plain(d.get("next"), 300),
    }


def title(out):
    """A short name for the saved-answers list."""
    for line in _plain(out.get("read"), 200).splitlines():
        if line.strip():
            return re.sub(r"\s+", " ", line.strip())[:80]
    return (out.get("subject") or "").strip() or "A scan"
