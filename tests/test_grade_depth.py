"""Teach to the class standing in front of the board.

The board knows which room it is in — a subject code names one class — and
the lesson never used it. "Explain refraction" was answered identically for
a class of thirteen-year-olds and a class sitting board exams, which means
it was wrong for at least one of them: too thin to be useful, or pitched
over their heads and quietly abandoned.

The year is read from the class NAME, because that is the thing a school
types, and it comes in three shapes:

    digits      9-A, 10-B, Class 5
    typed out   9th class a, 11th std
    romans      VIII-B, IX A, Std X, XII Commerce

All three are read. A name with no year in it is left ALONE rather than
guessed at: a lesson calibrated to the wrong year is confidently wrong,
which is worse than one that was never calibrated at all.

Two orderings in here are bugs that were caught rather than choices:

Digits are tried before roman numerals. Scanning for romans first found the
"i" inside "Class 11 Science" and answered class 1 — and made "Rainbow" and
"Section Blue" class 1 by the same route.

And the ordinal form is tried before plain digits, because "9th" has no word
boundary between the 9 and the th, so the plain digit pattern never matched
the one form a school is most likely to type.

The class also goes into the cache key. Class 9 and class 12 asking about
refraction are two different lessons now, and sharing one entry would hand
whichever asked second the other year's answer.
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"
os.environ["JOBS_ENABLED"] = "0"

import main                                        # noqa: E402

MAIN = io.open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
P, F = [], []


def ck(n, c, d=""):
    print(("PASS " if c else "FAIL ") + n + (f" — {d}" if d else ""),
          flush=True)
    (P if c else F).append(n)


print("\nthe three shapes a school writes a class in")
DIGITS = {"9-A": 9, "10-B": 10, "Class 5": 5, "6-A": 6, "10-B 178": 10}
TYPED = {"9th class a": 9, "11th std": 11, "1st A": 1, "3rd B": 3}
ROMAN = {"VIII-B": 8, "IX A": 9, "Std X": 10, "XII Commerce": 12, "VII": 7}
for label, cases in (("digits", DIGITS), ("typed out", TYPED),
                     ("romans", ROMAN)):
    wrong = {k: main._grade_of(k) for k, v in cases.items()
             if main._grade_of(k) != v}
    ck(f"{label} read correctly", not wrong, str(wrong) or f"{len(cases)} names")

print("\nand a name with no year in it is left alone")
for name in ("Rainbow", "Section Blue", "Blue House", "", "Alpha"):
    ck(f"{name or '(empty)'} is not given a year", main._grade_of(name) == 0,
       f"got {main._grade_of(name)}")
ck("Class 11 Science is 11, not 1",
   main._grade_of("Class 11 Science") == 11,
   "the roman scan used to find the i in Science")
ck("digits are tried before romans",
   MAIN.index("1[0-2]|[1-9])") < MAIN.index("[ivx]+"))
ck("and the ordinal form before plain digits",
   MAIN.index("st|nd|rd|th") < MAIN.index("for word in re.findall"),
   "9th has no word boundary between the 9 and the th")
ck("a bare i is never a year", '"ii": 2' in MAIN and '"i": 1' not in MAIN,
   "one letter inside an ordinary word is not a year group")

print("\nthe lesson is told which year it is teaching")
p9 = main._board_prompt("refraction", "Intermediate", "9-A")
p12 = main._board_prompt("refraction", "Intermediate", "XII Commerce")
plain = main._board_prompt("refraction", "Intermediate")
ck("class 9 is named in the prompt", "CLASS 9." in p9)
ck("class 12 is named in the prompt", "CLASS 12." in p12)
ck("and the two prompts really differ", p9 != p12)
ck("a class with no year changes nothing",
   main._board_prompt("refraction", "Intermediate", "Rainbow") == plain,
   "no instruction beats a wrong one")
ck("it forbids reaching into a later year",
   "not reach for mathematics or vocabulary from a later" in p9,
   "the short way is often the one that needs a tool they have not met")
ck("and says where the syllabus stops rather than pretending",
   "there is more to it later" in p9)

print("\nthe year is taken from the board's token, not the request")
ck("the class comes from the grant",
   'k = db.get(Klass, int(grant.get("class_id") or 0))' in MAIN,
   "a browser could claim any year, and the year decides the pitch")
ck("and it is part of the cache key",
   '_norm_q(f"{_grade_of(klass)}|{topic}")' in MAIN,
   "otherwise class 12 gets whatever class 9 asked first")
ck("one reader for both", "def _grade_of(klass: str) -> int:" in MAIN,
   "a lesson pitched at one year and filed under another is the bug this "
   "shape prevents")

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\nPASSED {len(P)}   FAILED {len(F)}")
sys.exit(1 if F else 0)
