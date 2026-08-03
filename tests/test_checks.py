"""The automatic checks, and the rule that a failed one is never cached.

Two lessons prompted all of this. A scanned maths problem answered that
(1, 1, 1) solves x + y + z = xyz — the sum is 3 and the product is 1. And
verify.py, which knows the CODATA constants and can do a lesson's arithmetic,
sat in the repo checking nothing because nothing called it.

The rule that matters most is the caching one. A wrong lesson that is shown is
one person's bad afternoon; a wrong lesson that is cached is served to
everybody who asks that question from then on, free, forever.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "test-secret-long-enough-for-checks")
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["JOBS_ENABLED"] = "0"

import main                                        # noqa: E402
import maths                                       # noqa: E402
import verify                                      # noqa: E402

PASS = FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {name}" + (f"  ({detail})" if detail else ""))
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


# ---- the substitution check -----------------------------------------
BAD = ("The system is x + y + z = xyz and x^2 + y^2 + z^2 = 3. "
       "Testing x = y = z = 1 gives 3, so (1, 1, 1) is a solution. "
       "Another is (2, -1, -1).")
check("a claimed solution that fails is caught",
      bool(maths.check_solutions(BAD)),
      (maths.check_solutions(BAD) or [{}])[0].get("problem", "")[:70])
check("a correct solution is left alone",
      not maths.check_solutions("Here x + y = 5 and x * y = 6, so (2, 3)."))
check("a chained assignment is not read as an equation",
      all(l.strip() != "z" for l, r, v in maths.equations("x = y = z = 1")),
      str(maths.equations("x = y = z = 1")))

# ---- nothing is ever evaluated --------------------------------------
for hostile in ("__import__('os').system('echo hi')",
                "(1).__class__.__bases__",
                "[x for x in range(10)]",
                "2**999999999",
                "lambda: 1",
                "open('/etc/passwd').read()"):
    check(f"refuses {hostile[:30]}", maths.evaluate(hostile, {"x": 1}) is None)

check("real arithmetic still works",
      maths.evaluate("x^2 + y^2 + z^2", {"x": 1, "y": 1, "z": 1}) == 3.0)
check("sqrt works", maths.evaluate("sqrt(16)", {}) == 4.0)
check("implicit multiplication works", maths.evaluate("2x + 3", {"x": 4}) == 11.0)

# ---- the constants and the arithmetic -------------------------------
LIGHT = {"title": "Light", "steps": [{"t": "The speed of light is 2.5 x 10^8 m/s."}],
         "takeaway": ""}
check("a wrong physical constant is caught", bool(verify.run(LIGHT)),
      (verify.run(LIGHT) or [{}])[0].get("problem", "")[:60])
SUM = {"title": "Sums", "steps": [{"t": "So 12 + 15 = 29 in total."}], "takeaway": ""}
check("wrong arithmetic is caught", bool(verify.run(SUM)))
OK = {"title": "Light", "steps": [{"t": "The speed of light is 3.0 x 10^8 m/s."}],
      "takeaway": "It is a constant."}
check("a correct lesson raises nothing", not verify.run(OK), str(verify.run(OK))[:80])

# ---- both lesson shapes ---------------------------------------------
# Ask Axle's steps are strings; the Pro board's are objects. Assuming the
# object shape meant the checks silently never ran on Ask Axle at all.
STRINGS = {"title": "Light", "steps": ["The speed of light is 2.5 x 10^8 m/s."],
           "takeaway": ""}
check("string steps are checked too", bool(verify.run(STRINGS)),
      "Ask Axle's shape")

# ---- the rule that matters ------------------------------------------
found, verdict = main._check_lesson(LIGHT)
check("a lesson with a bad constant is NOT cached", verdict["cache"] is False,
      str(verdict))
found_ok, verdict_ok = main._check_lesson(OK)
check("a clean lesson is cached", verdict_ok["cache"] is True, str(verdict_ok))
check("a clean lesson is high confidence",
      verdict_ok["confidence"] == "high", verdict_ok["confidence"])
check("findings are readable sentences",
      all(isinstance(x, str) and x[:1].isupper()
          for x in main._note_findings(found)),
      str(main._note_findings(found))[:80])

# ---- a checker must never break a lesson ----------------------------
for junk in (None, {}, {"steps": None}, {"steps": [None, 5, {"t": None}]},
             {"steps": "not a list"}, {"steps": [{"t": "x" * 5000}]}):
    try:
        main._check_lesson(junk)
        check(f"survives {str(junk)[:34]}", True)
    except Exception as e:
        check(f"survives {str(junk)[:34]}", False, f"{type(e).__name__}: {e}")

# ---- the Gemini finding, kept honest --------------------------------
# The probe matrix proved gemini-flash-lite-latest returns 400 with
# thinkingConfig and 200 without it.
for model in ("gemini-flash-lite-latest", "gemini-flash-latest"):
    check(f"{model} is sent no thinkingConfig",
          "thinkingConfig" not in main._gen_config(model, 100, 0.4))
for model in ("gemini-2.5-pro", "gemini-3-pro-preview"):
    check(f"{model} still gets thinkingConfig",
          "thinkingConfig" in main._gen_config(model, 100, 0.4))

print(f"\nPASSED {PASS}   FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
